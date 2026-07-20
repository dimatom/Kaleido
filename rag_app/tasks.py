# tasks.py
# Celery 异步任务示例
import os
import time

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded

from Kaleido.logger import logger
from rag_app import task_store


@shared_task(bind=True)
def long_running_task(self, total_steps):
    """模拟耗时任务，并上报进度"""
    for i in range(total_steps):
        time.sleep(0.1)
        self.update_state(
            state='PROGRESS',
            meta={
                'current': i + 1,
                'total': total_steps,
                'progress': int((i + 1) / total_steps * 100)
            }
        )
    logger.info(f"长任务完成，共 {total_steps} 步")
    return {'status': 'completed', 'result': '任务完成'}


_STAGE_OFFSET = {'loading': 0, 'splitting': 1, 'saving': 2}
_STAGE_TEXT = {'loading': '加载中', 'splitting': '分块中', 'saving': '向量入库中'}


@shared_task(bind=True)
def parse_documents_task(self, km_id, km_name, document_ids, user_id):
    """
    文档解析异步任务。

    参数:
        km_id: 知识库 ID（str）
        km_name: 知识库名称
        document_ids: 文档 UUID 字符串列表
        user_id: 用户 ID（str，仅用于日志/调试，权限已在提交接口校验）
    """
    from rag_app.models import Document
    from rag_app.rag_core import RAGCore

    task_id = self.request.id
    logger.info(f"开始解析任务 [{task_id}]，用户：{user_id}，知识库：{km_name}，文档数：{len(document_ids)}")

    try:
        documents = list(Document.objects.filter(pk__in=document_ids))
        if not documents:
            task_store.finish_task(task_id, 'FAILURE', '解析失败', error='未找到需要解析的文档')
            return {'status': 'failed', 'reason': 'no_documents'}

        # 构造 RAGCore 输入，并建立 document_id -> name 映射用于状态文案
        name_map = {str(doc.id): doc.name for doc in documents}
        document_list = []
        for doc in documents:
            document_list.append({
                'path': doc.filedata.path,
                'metadata': {'document_id': str(doc.id)}
            })
        total = len(document_list)

        def progress_callback(index, total_docs, stage, doc):
            doc_id = doc['metadata'].get('document_id')
            doc_name = name_map.get(doc_id) or os.path.basename(doc.get('path') or '')
            if stage == 'done':
                done_units = index * 3
                current = index
                context = f'已完成 {index}/{total_docs}：{doc_name}'
            else:
                done_units = index * 3 + _STAGE_OFFSET[stage]
                current = index
                context = f'正在解析 {index + 1}/{total_docs}：{doc_name} · {_STAGE_TEXT[stage]}'
            progress = min(99, int(done_units * 100 / (total_docs * 3))) if total_docs else 0

            # 双写：Celery result backend（沿用协议）+ 业务 Redis（前端数据源）
            self.update_state(
                state='PROGRESS',
                meta={
                    'current': current,
                    'total': total_docs,
                    'progress': progress,
                    'context': context,
                }
            )
            task_store.update_task_progress(task_id, current, total_docs, progress, context)

        rag = RAGCore(str(km_id))
        parse_result = rag.parse_document(document_list, progress_callback=progress_callback)

        # 回写成功文档的 chunk 与 parse_status
        parsed_ids = set()
        for item in parse_result:
            doc_id = item.get('document_id')
            chunk_count = item.get('chunk_count')
            if doc_id and chunk_count is not None:
                Document.objects.filter(pk=doc_id).update(chunk=chunk_count, parse_status='parsed')
                parsed_ids.add(str(doc_id))

        # 失败文档回写 parse_status='failed'
        failed_ids = [doc_id for doc_id in document_ids if doc_id not in parsed_ids]
        if failed_ids:
            Document.objects.filter(pk__in=failed_ids).update(parse_status='failed')

        failed_count = len(failed_ids)
        if failed_count == total:
            task_store.finish_task(task_id, 'FAILURE', '解析失败', error='所有文档均解析失败')
            return {'status': 'failed', 'success': 0, 'failed': failed_count}

        context = f'解析完成：成功 {len(parsed_ids)}/{total} 个文档'
        if failed_count:
            context += f'，{failed_count} 个失败'
        task_store.finish_task(task_id, 'SUCCESS', context)
        logger.info(f"解析任务完成 [{task_id}]：{context}")
        return {'status': 'completed', 'success': len(parsed_ids), 'failed': failed_count}

    except SoftTimeLimitExceeded:
        logger.exception(f"解析任务软超时 [{task_id}]")
        task_store.finish_task(task_id, 'FAILURE', '解析失败：任务超时', error='任务执行超时')
        # 将进行中文档回写为失败，避免状态永远停留在 parsing
        try:
            Document.objects.filter(pk__in=document_ids, parse_status='parsing').update(parse_status='failed')
        except Exception:
            pass
        raise
    except Exception as e:
        logger.exception(f"解析任务异常 [{task_id}]")
        task_store.finish_task(task_id, 'FAILURE', '解析失败', error=str(e)[:500])
        try:
            Document.objects.filter(pk__in=document_ids, parse_status='parsing').update(parse_status='failed')
        except Exception:
            pass
        raise
    finally:
        task_store.clear_task_indexes(task_id)

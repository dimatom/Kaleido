# tasks.py
# Celery 异步任务示例
import os
import time
from django.core.files.base import ContentFile
from django.utils import timezone

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


@shared_task(bind=True)
def run_evaluation_task(self, run_id):
    """执行一次 RAG 配置评估并生成 Excel 报告。"""
    from rag_app.evaluation_service import (
        adapt_ragas_dataframe,
        aggregate_metrics,
        create_excel_report,
        history_context_to_messages,
        normalize_rag_config,
    )
    from rag_app.models import Document, EvaluationData, EvaluationRun
    from rag_app.rag_core import RAGCore

    task_id = self.request.id
    temporary_rag = None
    run = None
    try:
        run = EvaluationRun.objects.select_related(
            'dim_evaluation_task_id__dim_evaluation_id__dim_knowledge_repository_id'
        ).get(pk=run_id)
        evaluation_task = run.dim_evaluation_task_id
        evaluation = evaluation_task.dim_evaluation_id
        repository = evaluation.dim_knowledge_repository_id
        data_items = list(EvaluationData.objects.filter(dim_evaluation_id=evaluation).order_by('createdon'))
        if not data_items:
            raise ValueError('评估数据集为空')

        run.status = 'PROGRESS'
        run.started_at = timezone.now()
        run.error_message = ''
        run.save(update_fields=['status', 'started_at', 'error_message'])
        evaluation_task.status = 'running'
        evaluation_task.save(update_fields=['status', 'modifiedon'])

        config = normalize_rag_config(evaluation_task.rag_config)
        collection_name = f'eval_{str(run.id).replace("-", "")}'
        temporary_rag = RAGCore(
            str(repository.id),
            rag_config=config,
            collection_name=collection_name,
        )
        documents = list(Document.objects.filter(dim_knowledge_repository_id=repository))
        if not documents:
            raise ValueError('知识库没有可用于评估的文档')
        parse_result = temporary_rag.parse_document([
            {'path': document.filedata.path, 'metadata': {'document_id': str(document.id)}}
            for document in documents
        ])
        if not parse_result:
            raise ValueError('临时索引构建失败，未解析出有效文档')

        generated_records = []
        total = len(data_items)
        for index, item in enumerate(data_items, start=1):
            answer, retrieved_documents = temporary_rag.build_evaluation_answer(
                item.question,
                history_context_to_messages(item.history_context),
                repository.system_prompt,
            )
            generated_records.append({
                'question': item.question,
                'ground_truth': item.reference_answer,
                'answer': answer,
                'contexts': [document.page_content for document in retrieved_documents],
            })
            progress = min(90, int(index * 90 / total))
            context = f'正在评估 {index}/{total} 条数据'
            self.update_state(state='PROGRESS', meta={
                'current': index, 'total': total, 'progress': progress, 'context': context,
            })
            task_store.update_task_progress(task_id, index, total, progress, context)

        try:
            from datasets import Dataset
            from ragas import evaluate
            from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
        except ImportError as exc:
            raise RuntimeError('未安装与当前 LangChain 版本兼容的 ragas，无法执行自动指标评估') from exc

        dataset = Dataset.from_dict({
            'question': [item['question'] for item in generated_records],
            'answer': [item['answer'] for item in generated_records],
            'contexts': [item['contexts'] for item in generated_records],
            'ground_truth': [item['ground_truth'] for item in generated_records],
        })
        ragas_result = evaluate(
            dataset=dataset,
            llm=temporary_rag.llm_client,
            embeddings=temporary_rag.llm_embeddings,
            metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
            raise_exceptions=False,
        )
        metric_records = adapt_ragas_dataframe(ragas_result.to_pandas())
        for original, metric in zip(generated_records, metric_records):
            original.update(metric)
        summary = aggregate_metrics(generated_records)
        report = create_excel_report(generated_records, config)
        report_name = f'evaluation_{run.id}.xlsx'
        run.file.save(report_name, ContentFile(report.read()), save=False)
        run.result = summary
        run.status = 'SUCCESS'
        run.finished_at = timezone.now()
        run.save(update_fields=['file', 'result', 'status', 'finished_at'])
        evaluation_task.status = 'success'
        evaluation_task.save(update_fields=['status', 'modifiedon'])
        task_store.finish_task(task_id, 'SUCCESS', f'评估完成：共处理 {total} 条数据')
        return {'status': 'completed', 'result': summary}
    except SoftTimeLimitExceeded:
        logger.exception(f'评估任务软超时 [{task_id}]')
        error_message = '评估任务执行超时'
        if run:
            run.status = 'FAILURE'
            run.error_message = error_message
            run.finished_at = timezone.now()
            run.save(update_fields=['status', 'error_message', 'finished_at'])
            run.dim_evaluation_task_id.status = 'failed'
            run.dim_evaluation_task_id.save(update_fields=['status', 'modifiedon'])
        task_store.finish_task(task_id, 'FAILURE', '评估失败：任务超时', error=error_message)
        raise
    except Exception as exc:
        logger.exception(f'评估任务异常 [{task_id}]')
        error_message = str(exc)[:500]
        if run:
            run.status = 'FAILURE'
            run.error_message = error_message
            run.finished_at = timezone.now()
            run.save(update_fields=['status', 'error_message', 'finished_at'])
            run.dim_evaluation_task_id.status = 'failed'
            run.dim_evaluation_task_id.save(update_fields=['status', 'modifiedon'])
        task_store.finish_task(task_id, 'FAILURE', '评估失败', error=error_message)
        raise
    finally:
        if temporary_rag is not None:
            temporary_rag.delete_collection()
        task_store.clear_task_indexes(task_id)


@shared_task(bind=True)
def rebuild_knowledge_repository_index_task(self, km_id, user_id):
    """按当前知识库 RAG 配置重建全部文档索引。"""
    from rag_app.models import Document, KnowledgeRepository
    from rag_app.rag_core import RAGCore

    task_id = self.request.id
    try:
        repository = KnowledgeRepository.objects.get(pk=km_id)
        documents = list(Document.objects.filter(dim_knowledge_repository_id=repository))
        rag = RAGCore(str(repository.id), rag_config=repository.rag_config)
        rag.delete_collection()
        rag = RAGCore(str(repository.id), rag_config=repository.rag_config)
        Document.objects.filter(pk__in=[document.id for document in documents]).update(parse_status='parsing', chunk=0)

        def progress_callback(index, total, stage, document):
            progress = min(99, int(index * 100 / total)) if total else 0
            context = f'正在重建索引 {index + 1}/{total}' if stage != 'done' else f'已完成 {index}/{total}'
            self.update_state(state='PROGRESS', meta={
                'current': index, 'total': total, 'progress': progress, 'context': context,
            })
            task_store.update_task_progress(task_id, index, total, progress, context)

        result = rag.parse_document([
            {'path': document.filedata.path, 'metadata': {'document_id': str(document.id)}}
            for document in documents
        ], progress_callback=progress_callback)
        parsed = {str(item['document_id']): item['chunk_count'] for item in result}
        for document_id, chunk_count in parsed.items():
            Document.objects.filter(pk=document_id).update(chunk=chunk_count, parse_status='parsed')
        Document.objects.filter(pk__in=[document.id for document in documents if str(document.id) not in parsed]).update(parse_status='failed')
        task_store.finish_task(task_id, 'SUCCESS', f'索引重建完成：成功 {len(parsed)}/{len(documents)} 个文档')
        return {'status': 'completed', 'success': len(parsed), 'total': len(documents)}
    except Exception as exc:
        logger.exception(f'索引重建任务异常 [{task_id}]')
        task_store.finish_task(task_id, 'FAILURE', '索引重建失败', error=str(exc)[:500])
        raise
    finally:
        task_store.clear_task_indexes(task_id)

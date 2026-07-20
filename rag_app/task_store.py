# rag_app/task_store.py
# Redis 任务元数据管理（web 进程与 Celery worker 共用）
import json
import time
from typing import Optional

import redis
from django.conf import settings

from Kaleido.logger import logger

KEY_PREFIX = 'kaleido:task'
META_KEY = f'{KEY_PREFIX}:meta:%s'
USER_INDEX_KEY = f'{KEY_PREFIX}:user:%s'
KM_INDEX_KEY = f'{KEY_PREFIX}:km:%s'
DOC_INDEX_KEY = f'{KEY_PREFIX}:doc:%s'

TASK_META_TTL = 24 * 3600          # 任务元数据保留 24h（含已完成记录）
USER_INDEX_TTL = 24 * 3600         # 用户任务列表索引滑动 TTL
USER_INDEX_MAX = 100               # 单个用户最多保留最近 100 条任务
# 任务超时判定：Celery 硬超时 + 120s 缓冲；进行中任务超过此时间未更新视为已死
STALE_SECONDS = getattr(settings, 'CELERY_TASK_TIME_LIMIT', 30 * 60) + 120
RUNNING_STATUSES = ('PENDING', 'PROGRESS')

_redis_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    """获取 Redis 连接（惰性单例）"""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            getattr(settings, 'CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0'),
            decode_responses=True,
        )
    return _redis_client


def _now() -> float:
    return time.time()


def _serialize_meta(raw: dict) -> dict:
    """将 Redis HASH 中的字符串值反序列化为合适类型"""
    meta = dict(raw)
    int_fields = ('doc_count', 'current', 'total', 'progress')
    float_fields = ('created_at', 'updated_at')
    for f in int_fields:
        if f in meta and meta[f] not in (None, ''):
            try:
                meta[f] = int(meta[f])
            except (TypeError, ValueError):
                meta[f] = 0
    for f in float_fields:
        if f in meta and meta[f] not in (None, ''):
            try:
                meta[f] = float(meta[f])
            except (TypeError, ValueError):
                meta[f] = 0.0
    if 'doc_ids' in meta and meta['doc_ids']:
        try:
            meta['doc_ids'] = json.loads(meta['doc_ids'])
        except json.JSONDecodeError:
            meta['doc_ids'] = []
    else:
        meta['doc_ids'] = []
    return meta


def create_task(task_id: str, user_id: str, km_id: str, km_name: str, doc_ids: list) -> dict:
    """创建任务元数据并建立索引（提交任务前调用）"""
    r = get_redis()
    now = _now()
    meta = {
        'task_id': task_id,
        'user_id': str(user_id),
        'km_id': str(km_id),
        'km_name': km_name or '',
        'doc_ids': json.dumps([str(d) for d in doc_ids]),
        'doc_count': len(doc_ids),
        'status': 'PENDING',
        'current': 0,
        'total': len(doc_ids),
        'progress': 0,
        'context': '排队等待中',
        'error': '',
        'created_at': now,
        'updated_at': now,
    }
    pipe = r.pipeline()
    pipe.hset(META_KEY % task_id, mapping=meta)
    pipe.expire(META_KEY % task_id, TASK_META_TTL)
    # 用户索引：按时间倒序排列，同时清理过期和超额成员
    pipe.zadd(USER_INDEX_KEY % user_id, {task_id: now})
    pipe.zremrangebyscore(USER_INDEX_KEY % user_id, '-inf', now - USER_INDEX_TTL)
    pipe.zremrangebyrank(USER_INDEX_KEY % user_id, 0, -(USER_INDEX_MAX + 1))
    pipe.expire(USER_INDEX_KEY % user_id, USER_INDEX_TTL)
    # 知识库/文档进行中索引
    pipe.sadd(KM_INDEX_KEY % km_id, task_id)
    for doc_id in doc_ids:
        pipe.sadd(DOC_INDEX_KEY % doc_id, task_id)
    pipe.execute()
    return _serialize_meta(meta)


def update_task_progress(task_id: str, current: int, total: int, progress: int, context: str) -> None:
    """更新任务进度（worker 回调中调用）；进度丢失可容忍，不抛异常"""
    try:
        r = get_redis()
        r.hset(META_KEY % task_id, mapping={
            'status': 'PROGRESS',
            'current': current,
            'total': total,
            'progress': progress,
            'context': context or '',
            'updated_at': _now(),
        })
    except Exception as e:
        logger.warning(f'更新任务进度失败 [{task_id}]: {e}')


def finish_task(task_id: str, status: str, context: str, error: str = '') -> None:
    """标记任务结束（成功/失败），并重设 TTL、清理进行中索引"""
    try:
        r = get_redis()
        now = _now()
        updates = {
            'status': status,
            'context': context or '',
            'error': error or '',
            'updated_at': now,
        }
        if status == 'SUCCESS':
            updates['progress'] = 100
        pipe = r.pipeline()
        pipe.hset(META_KEY % task_id, mapping=updates)
        pipe.expire(META_KEY % task_id, TASK_META_TTL)
        pipe.execute()
        clear_task_indexes(task_id)
    except Exception as e:
        logger.warning(f'结束任务失败 [{task_id}]: {e}')


def clear_task_indexes(task_id: str) -> None:
    """幂等清理 km/doc 进行中索引；meta 已丢失也能安全执行"""
    try:
        r = get_redis()
        raw = r.hgetall(META_KEY % task_id)
        if not raw:
            return
        meta = _serialize_meta(raw)
        km_id = meta.get('km_id')
        doc_ids = meta.get('doc_ids') or []
        pipe = r.pipeline()
        if km_id:
            pipe.srem(KM_INDEX_KEY % km_id, task_id)
        for doc_id in doc_ids:
            pipe.srem(DOC_INDEX_KEY % doc_id, task_id)
        pipe.execute()
    except Exception as e:
        logger.warning(f'清理任务索引失败 [{task_id}]: {e}')


def get_task_meta(task_id: str) -> Optional[dict]:
    """获取单个任务元数据"""
    try:
        r = get_redis()
        raw = r.hgetall(META_KEY % task_id)
        return _serialize_meta(raw) if raw else None
    except Exception as e:
        logger.warning(f'获取任务元数据失败 [{task_id}]: {e}')
        return None


def _is_effectively_running(meta: Optional[dict]) -> bool:
    """判断任务是否真正进行中（已终态或超时的不算）"""
    if not meta:
        return False
    if meta.get('status') not in RUNNING_STATUSES:
        return False
    updated_at = meta.get('updated_at') or 0
    return (_now() - updated_at) <= STALE_SECONDS


def _apply_stale_display(meta: dict) -> dict:
    """读侧兜底：进行中但已超时的任务在展示层标为失败（不回写 Redis）"""
    if meta.get('status') in RUNNING_STATUSES:
        updated_at = meta.get('updated_at') or meta.get('created_at') or 0
        if (_now() - updated_at) > STALE_SECONDS:
            meta['status'] = 'FAILURE'
            meta['context'] = '任务超时或已中断'
    return meta


def list_user_tasks(user_id: str, limit: int = 50) -> list:
    """获取用户任务列表（时间倒序），自动清理失效成员和 stale 展示"""
    try:
        r = get_redis()
        key = USER_INDEX_KEY % user_id
        # 先清理过期的 score 成员
        r.zremrangebyscore(key, '-inf', _now() - USER_INDEX_TTL)
        task_ids = r.zrevrange(key, 0, limit - 1)
        if not task_ids:
            return []

        pipe = r.pipeline()
        for tid in task_ids:
            pipe.hgetall(META_KEY % tid)
        results = pipe.execute()

        tasks = []
        expired_ids = []
        for tid, raw in zip(task_ids, results):
            if not raw:
                expired_ids.append(tid)
                continue
            meta = _apply_stale_display(_serialize_meta(raw))
            tasks.append(meta)

        if expired_ids:
            r.zrem(key, *expired_ids)
        return tasks
    except Exception as e:
        logger.warning(f'获取用户任务列表失败 [{user_id}]: {e}')
        return []


def _has_running_task_in_index(index_key: str) -> bool:
    """检查某个索引中是否存在真正进行中的任务，并惰性清理死成员"""
    try:
        r = get_redis()
        task_ids = r.smembers(index_key)
        if not task_ids:
            return False

        pipe = r.pipeline()
        for tid in task_ids:
            pipe.hgetall(META_KEY % tid)
        results = pipe.execute()

        dead_ids = []
        for tid, raw in zip(task_ids, results):
            meta = _serialize_meta(raw) if raw else None
            if _is_effectively_running(meta):
                return True
            dead_ids.append(tid)

        if dead_ids:
            r.srem(index_key, *dead_ids)
        return False
    except Exception as e:
        logger.warning(f'检查进行中任务失败 [{index_key}]: {e}')
        return False


def km_has_running_task(km_id: str) -> bool:
    return _has_running_task_in_index(KM_INDEX_KEY % km_id)


def doc_has_running_task(doc_id: str) -> bool:
    return _has_running_task_in_index(DOC_INDEX_KEY % doc_id)


def docs_running_conflict(doc_ids: list) -> list:
    """返回已有进行中任务的 doc_id 列表（含惰性清理）"""
    conflict = []
    for doc_id in doc_ids:
        if doc_has_running_task(str(doc_id)):
            conflict.append(str(doc_id))
    return conflict

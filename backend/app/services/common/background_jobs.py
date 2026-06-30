"""
后台任务管理器 (D17: 纯内存 + events 审计)

- _jobs 纯内存 dict，不再持久化到 conversation_user_meta
- Job 完成后写 events 表做审计 (event_type='background_job_done')
- 服务重启丢失的 job 由前端 SSE 重连重试
"""
from __future__ import annotations
import asyncio
import json
import logging
import time
from app.schemas.conversation import BackgroundJob

logger = logging.getLogger(__name__)

class BackgroundJobManager:
    def __init__(self):
        self._jobs: dict[str, BackgroundJob] = {}
        self._handlers: dict[str, callable] = {}
        self._running: dict[str, asyncio.Task] = {}

    def register_handler(self, tool_name: str, handler):
        self._handlers[tool_name] = handler

    async def submit(self, user_id: str, tool_name: str, params: dict, block_id: str, dir_id: str, conv_id: str) -> BackgroundJob:
        job = BackgroundJob(
            tool_name=tool_name,
            params=params,
            block_id=block_id,
            dir_id=dir_id,
            conv_id=conv_id,
        )
        self._jobs[job.id] = job

        # 异步执行
        task = asyncio.create_task(self._run_job(user_id, job.id))
        self._running[job.id] = task

        return job

    async def _run_job(self, user_id: str, job_id: str):
        job = self._jobs.get(job_id)
        if not job:
            return

        job.status = "processing"

        try:
            handler = self._handlers.get(job.tool_name)
            if not handler:
                raise ValueError(f"No handler for {job.tool_name}")

            result = await handler(job.params)
            job.result = result
            job.status = "done"
            job.completed_at = time.time()

            # 更新关联的 ResponseBlock
            from app.services.common import get_data_repo
            data = get_data_repo().load(user_id)
            block = data.response_blocks.get(job.block_id)
            if block:
                block.status = "ready"
                block.content.update(result)
                block.updated_at = time.time()
            get_data_repo().save(user_id, data)

        except Exception as e:
            logger.error("Job %s failed: %s", job_id, e)
            job.status = "failed"
            job.error = str(e)
            job.completed_at = time.time()

            # 更新关联的 ResponseBlock
            from app.services.common import get_data_repo
            data = get_data_repo().load(user_id)
            block = data.response_blocks.get(job.block_id)
            if block:
                block.status = "failed"
                block.content["error"] = str(e)
                block.updated_at = time.time()
            get_data_repo().save(user_id, data)

        # D17: 写入 events 审计表
        self._record_audit_event(user_id, job)

    def _record_audit_event(self, user_id: str, job: BackgroundJob) -> None:
        """写入 events 表做审计"""
        try:
            from app.infrastructure.db.database import get_db
            import uuid
            db = get_db()
            db.execute(
                """INSERT INTO events (id, user_id, event_type, source_type, source_id,
                   status, status_msg, payload, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())""",
                (
                    str(uuid.uuid4()),
                    user_id,
                    "background_job_done",
                    "system",
                    job.id,
                    "done" if job.status == "done" else "failed",
                    job.error or "",
                    json.dumps({
                        "tool_name": job.tool_name,
                        "block_id": job.block_id,
                        "conv_id": job.conv_id,
                        "duration_seconds": (job.completed_at - job.created_at) if job.completed_at else 0,
                    }, ensure_ascii=False),
                ),
            )
        except Exception as e:
            logger.warning("写入审计事件失败: %s", e)

    def get_job(self, job_id: str) -> BackgroundJob | None:
        """从内存读取 job 状态（D17: 不再查 DB）"""
        return self._jobs.get(job_id)

    async def cancel(self, user_id: str, job_id: str) -> bool:
        task = self._running.pop(job_id, None)
        if task:
            task.cancel()
            job = self._jobs.get(job_id)
            if job:
                job.status = "failed"
                job.error = "Cancelled"
            return True
        return False

job_manager = BackgroundJobManager()

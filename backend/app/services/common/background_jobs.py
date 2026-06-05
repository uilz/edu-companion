"""
后台任务管理器
"""
from __future__ import annotations
import asyncio
import logging
import time
from app.schemas.conversation import BackgroundJob
from app.services.common.storage import storage

logger = logging.getLogger(__name__)

class BackgroundJobManager:
    def __init__(self):
        self._jobs: dict[str, BackgroundJob] = {}
        self._handlers: dict[str, callable] = {}
        self._running: dict[str, asyncio.Task] = {}

    def register_handler(self, tool_name: str, handler):
        self._handlers[tool_name] = handler

    async def submit(self, user_id: str, tool_name: str, params: dict, block_id: str, partition_id: str, conversation_id: str) -> BackgroundJob:
        job = BackgroundJob(
            tool_name=tool_name,
            params=params,
            block_id=block_id,
            partition_id=partition_id,
            conversation_id=conversation_id,
        )
        self._jobs[job.id] = job

        # 保存到存储
        data = storage.load(user_id)
        data.background_jobs[job.id] = job
        storage.save(user_id, data)

        # 异步执行
        task = asyncio.create_task(self._run_job(user_id, job.id))
        self._running[job.id] = task

        return job

    async def _run_job(self, user_id: str, job_id: str):
        job = self._jobs.get(job_id)
        if not job:
            return

        job.status = "processing"
        self._save_job(user_id, job)

        try:
            handler = self._handlers.get(job.tool_name)
            if not handler:
                raise ValueError(f"No handler for {job.tool_name}")

            result = await handler(job.params)
            job.result = result
            job.status = "done"
            job.completed_at = time.time()

            # 更新关联的 ResponseBlock
            data = storage.load(user_id)
            block = data.response_blocks.get(job.block_id)
            if block:
                block.status = "ready"
                block.content.update(result)
                block.updated_at = time.time()
            storage.save(user_id, data)

        except Exception as e:
            logger.error("Job %s failed: %s", job_id, e)
            job.status = "failed"
            job.error = str(e)
            job.completed_at = time.time()

            # 更新关联的 ResponseBlock
            data = storage.load(user_id)
            block = data.response_blocks.get(job.block_id)
            if block:
                block.status = "failed"
                block.content["error"] = str(e)
                block.updated_at = time.time()
            storage.save(user_id, data)

    def _save_job(self, user_id: str, job: BackgroundJob):
        data = storage.load(user_id)
        data.background_jobs[job.id] = job
        storage.save(user_id, data)

    def get_job(self, user_id: str, job_id: str) -> BackgroundJob | None:
        data = storage.load(user_id)
        return data.background_jobs.get(job_id)

    async def cancel(self, user_id: str, job_id: str) -> bool:
        task = self._running.pop(job_id, None)
        if task:
            task.cancel()
            job = self._jobs.get(job_id)
            if job:
                job.status = "failed"
                job.error = "Cancelled"
                self._save_job(user_id, job)
            return True
        return False

job_manager = BackgroundJobManager()

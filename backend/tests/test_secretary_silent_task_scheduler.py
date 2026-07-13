"""SilentTask 全局调度器测试 (ADR 0019)

验证:
  1. SilentTaskStore.claim_next_pending_global 能按优先级批量认领任务
  2. SilentTaskManager.run_pending_global 能执行认领到的任务
  3. silent_task_tick 调度入口能正常调用
"""

from __future__ import annotations

import os
import sys
import uuid
from typing import Any

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)


@pytest.fixture
def user_id() -> str:
    return f"st_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def other_user_id() -> str:
    return f"st_b_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def db():
    try:
        from app.infrastructure.db.database import get_db
        d = get_db()
        d.fetchone("SELECT 1", ())
        from app.infrastructure.db.secretary_schema import _ensure_tables
        _ensure_tables()
        return d
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"数据库不可用: {exc}")


@pytest.fixture(autouse=True)
def cleanup_test_data(db, user_id, other_user_id):
    yield
    try:
        for uid in (user_id, other_user_id):
            try:
                db.execute("DELETE FROM secretary_silent_tasks WHERE user_id = %s", (uid,))
            except Exception:
                pass
    except Exception:
        pass


class TestSilentTaskStoreGlobalClaim:
    """SilentTaskStore.claim_next_pending_global"""

    def _save_task(self, store, user_id: str, task_type: str, priority: int = 3, status: str = "pending"):
        from app.domain.secretary.models import SilentTask
        task = SilentTask(
            user_id=user_id,
            task_type=task_type,
            priority=priority,
            status=status,
            payload={"test": True},
        )
        return store.save_task(task)

    def test_claim_next_pending_global_basic(self, db, user_id, other_user_id):
        from app.infrastructure.db.silent_task_store import SilentTaskStore
        store = SilentTaskStore()

        id1 = self._save_task(store, user_id, "compute_diagnosis", priority=1)
        id2 = self._save_task(store, other_user_id, "generate_daily_brief", priority=2)
        self._save_task(store, user_id, "expand_knowledge_graph", priority=3)

        claimed = store.claim_next_pending_global(limit=2)
        ids = {t.id for t in claimed}

        assert len(claimed) == 2
        assert id1 in ids
        assert id2 in ids
        for t in claimed:
            assert t.status == "running"

        # 未认领的任务仍是 pending
        remaining = store.list_tasks(user_id, status="pending")
        assert len(remaining) == 1
        assert remaining[0].task_type == "expand_knowledge_graph"

    def test_claim_next_pending_global_order(self, db, user_id):
        from app.infrastructure.db.silent_task_store import SilentTaskStore
        store = SilentTaskStore()

        # 故意先插入低优先级
        self._save_task(store, user_id, "generate_daily_brief", priority=4)
        id_high = self._save_task(store, user_id, "compute_diagnosis", priority=1)
        self._save_task(store, user_id, "pre_generate_quiz", priority=2)

        claimed = store.claim_next_pending_global(limit=1)
        assert len(claimed) == 1
        assert claimed[0].id == id_high
        assert claimed[0].task_type == "compute_diagnosis"

    def test_claim_next_pending_global_skip_locked(self, db, user_id):
        from app.infrastructure.db.silent_task_store import SilentTaskStore
        store = SilentTaskStore()

        self._save_task(store, user_id, "compute_diagnosis", priority=1)

        # 先通过单用户 claim 占住一个 running 任务
        single = store.claim_next_pending(user_id)
        assert single is not None
        assert single.status == "running"

        # 全局 claim 不应重复领取 running 任务
        claimed = store.claim_next_pending_global(limit=10)
        assert len(claimed) == 0


class TestSilentTaskManagerGlobalRun:
    """SilentTaskManager.run_pending_global"""

    def _save_task(self, store, user_id: str, task_type: str, priority: int = 3):
        from app.domain.secretary.models import SilentTask
        task = SilentTask(
            user_id=user_id,
            task_type=task_type,
            priority=priority,
            payload={"test": True},
        )
        return store.save_task(task)

    @pytest.mark.asyncio
    async def test_run_pending_global_executes_unknown_type(self, db, user_id):
        from app.domain.secretary.engines.silent_task_manager import SilentTaskManager
        from app.infrastructure.db.silent_task_store import SilentTaskStore

        store = SilentTaskStore()
        task_id = self._save_task(store, user_id, "unknown_task_for_test", priority=1)

        manager = SilentTaskManager(store=store)
        completed = await manager.run_pending_global(max_tasks=10)

        assert len(completed) == 1
        assert completed[0].id == task_id
        assert completed[0].status == "failed"

    @pytest.mark.asyncio
    async def test_run_pending_global_respects_max_tasks(self, db, user_id):
        from app.domain.secretary.engines.silent_task_manager import SilentTaskManager
        from app.infrastructure.db.silent_task_store import SilentTaskStore

        store = SilentTaskStore()
        for i in range(5):
            self._save_task(store, user_id, f"unknown_task_{i}", priority=i + 1)

        manager = SilentTaskManager(store=store)
        completed = await manager.run_pending_global(max_tasks=2)

        assert len(completed) == 2
        pending = store.list_tasks(user_id, status="pending")
        assert len(pending) == 3


class TestSilentTaskSchedulerTick:
    """scheduler/tasks.py silent_task_tick"""

    def _save_task(self, store, user_id: str, task_type: str):
        from app.domain.secretary.models import SilentTask
        task = SilentTask(
            user_id=user_id,
            task_type=task_type,
            payload={"test": True},
        )
        return store.save_task(task)

    @pytest.mark.asyncio
    async def test_silent_task_tick(self, db, user_id):
        from app.infrastructure.db.silent_task_store import SilentTaskStore
        from app.infrastructure.scheduler.tasks import silent_task_tick

        store = SilentTaskStore()
        task_id = self._save_task(store, user_id, "unknown_tick_task")

        await silent_task_tick()

        task = store.get_task(task_id)
        assert task is not None
        assert task.status in ("ready", "failed", "running")

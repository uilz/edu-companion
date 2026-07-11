"""静默任务管理器 — 调度与执行秘书后台预计算任务

职责:
  1. schedule()   — 根据事件/场景创建 SilentTask 并持久化
  2. execute()    — 执行单个任务，更新状态，发布 SilentTaskCompleted
  3. run_pending() — 批量执行某用户的 pending 任务
  4. get_result() — 获取任务结果

任务类型:
  - prepare_review_list:   预生成今日复习列表
  - pre_generate_quiz:     预生成针对薄弱点的测验
  - compute_diagnosis:     预计算诊断报告
  - generate_daily_brief:  预生成每日简报
  - expand_knowledge_graph: 触发知识图谱扩展
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Coroutine

from app.domain.secretary.models import SilentTask
from app.infrastructure.db.silent_task_store import SilentTaskStore
from shared.events import SilentTaskCreated, SilentTaskCompleted

logger = logging.getLogger(__name__)


class SilentTaskManager:
    """静默任务调度与执行器"""

    # 任务默认优先级（越小越优先）
    _DEFAULT_PRIORITY: dict[str, int] = {
        "compute_diagnosis": 1,
        "prepare_review_list": 2,
        "pre_generate_quiz": 3,
        "generate_daily_brief": 4,
        "expand_knowledge_graph": 5,
    }

    def __init__(
        self,
        store: SilentTaskStore | None = None,
        event_bus: Any | None = None,
    ) -> None:
        self._store = store or SilentTaskStore()
        self._event_bus = event_bus
        self._executors: dict[str, Callable[[SilentTask], Coroutine[Any, Any, dict[str, Any]]]] = {
            "prepare_review_list": self._exec_prepare_review_list,
            "pre_generate_quiz": self._exec_pre_generate_quiz,
            "compute_diagnosis": self._exec_compute_diagnosis,
            "generate_daily_brief": self._exec_generate_daily_brief,
            "expand_knowledge_graph": self._exec_expand_knowledge_graph,
        }

    def set_event_bus(self, bus: Any) -> None:
        """注入事件总线（可选，用于发布 SilentTaskCreated/Completed）"""
        self._event_bus = bus

    async def schedule(
        self,
        user_id: str,
        task_type: str,
        payload: dict | None = None,
        priority: int | None = None,
        caused_by_event_id: str | None = None,
    ) -> str:
        """调度一个静默任务，返回任务 ID"""
        task = SilentTask(
            user_id=user_id,
            task_type=task_type,
            payload=payload or {},
            priority=priority if priority is not None else self._DEFAULT_PRIORITY.get(task_type, 3),
            status="pending",
        )
        task_id = self._store.save_task(task)

        # 发布创建事件
        if self._event_bus:
            try:
                await self._event_bus.publish(SilentTaskCreated(
                    user_id=user_id,
                    source_module="secretary",
                    task_id=task_id,
                    task_type=task_type,
                    payload=task.payload,
                    priority=task.priority,
                    caused_by_event_id=caused_by_event_id,
                ))
            except Exception as e:
                logger.debug("SilentTaskCreated 发布失败: %s", e)
        return task_id

    async def execute(self, task: SilentTask) -> SilentTask:
        """执行单个任务并返回更新后的任务"""
        if task.status not in ("pending", "running"):
            return task

        # 确保状态为 running
        if task.status == "pending":
            self._store.update_status(task.id, "running")
            task.status = "running"

        executor = self._executors.get(task.task_type)
        result_payload: dict[str, Any] = {}
        result_ref = ""
        final_status = "failed"

        try:
            if executor:
                result_payload = await executor(task)
                result_ref = result_payload.get("result_ref", "")
                final_status = "ready"
            else:
                result_payload = {"error": f"未知任务类型: {task.task_type}"}
                final_status = "failed"
        except Exception as e:
            logger.warning("静默任务执行失败: %s %s — %s", task.user_id, task.task_type, e)
            result_payload = {"error": str(e)}
            final_status = "failed"

        self._store.update_status(
            task.id,
            status=final_status,
            result_ref=result_ref,
            result_payload=result_payload,
        )
        task.status = final_status
        task.result_ref = result_ref
        task.ready_at = time.time()

        if self._event_bus:
            try:
                await self._event_bus.publish(SilentTaskCompleted(
                    user_id=task.user_id,
                    source_module="secretary",
                    task_id=task.id,
                    task_type=task.task_type,
                    status=final_status,
                    result_ref=result_ref,
                    result_payload=result_payload,
                ))
            except Exception as e:
                logger.debug("SilentTaskCompleted 发布失败: %s", e)

        return task

    async def run_pending(
        self,
        user_id: str,
        task_type: str | None = None,
        max_tasks: int = 5,
    ) -> list[SilentTask]:
        """批量执行某用户的 pending 任务"""
        completed: list[SilentTask] = []
        for _ in range(max_tasks):
            task = self._store.claim_next_pending(user_id, task_type=task_type)
            if not task:
                break
            try:
                completed.append(await self.execute(task))
            except Exception as e:
                logger.warning("批量执行静默任务失败: %s", e)
        return completed

    def get_result(self, task_id: str, user_id: str | None = None) -> SilentTask | None:
        """获取任务结果"""
        return self._store.get_task(task_id, user_id=user_id)

    def list_tasks(
        self,
        user_id: str,
        status: str | None = None,
        task_type: str | None = None,
        limit: int = 50,
    ) -> list[SilentTask]:
        """获取任务列表"""
        return self._store.list_tasks(user_id, status=status, task_type=task_type, limit=limit)

    # ═══════════════════════════════════════════
    # 任务执行器
    # ═══════════════════════════════════════════

    async def _exec_prepare_review_list(self, task: SilentTask) -> dict[str, Any]:
        """预生成复习列表"""
        user_id = task.user_id
        try:
            from ..analysis import rank_recommendations
            recs = rank_recommendations(user_id=user_id)
            items = [
                {
                    "node_id": i.node_id,
                    "label": i.label,
                    "urgency": i.norm_urgency,
                    "priority": i.norm_priority,
                }
                for i in recs.items[:10]
            ]
            return {
                "result_ref": f"review_list:{user_id}:{int(time.time())}",
                "item_count": len(items),
                "items": items,
            }
        except Exception as e:
            return {"error": f"复习列表生成失败: {e}"}

    async def _exec_pre_generate_quiz(self, task: SilentTask) -> dict[str, Any]:
        """预生成薄弱点测验"""
        user_id = task.user_id
        kp_id = (task.payload or {}).get("kp_id", "")
        try:
            from app.domain.cognitive import get_repo
            node = get_repo().get_node(user_id, kp_id) if kp_id else None
            return {
                "result_ref": f"quiz:{user_id}:{kp_id or 'general'}:{int(time.time())}",
                "kp_id": kp_id,
                "node_label": node.id if node else (kp_id or "general"),
                "question_count": 3,
            }
        except Exception as e:
            return {"error": f"测验预生成失败: {e}"}

    async def _exec_compute_diagnosis(self, task: SilentTask) -> dict[str, Any]:
        """预计算诊断报告"""
        user_id = task.user_id
        try:
            from ..diagnosis import DiagnosisEngine
            engine = DiagnosisEngine()
            report = await engine.diagnose(user_id=user_id)
            return {
                "result_ref": report.snapshot_id,
                "weak_count": len(report.weak_points),
                "cognitive_load": report.cognitive_load,
                "summary": report.summary,
            }
        except Exception as e:
            return {"error": f"诊断计算失败: {e}"}

    async def _exec_generate_daily_brief(self, task: SilentTask) -> dict[str, Any]:
        """预生成每日简报"""
        user_id = task.user_id
        try:
            from ..diagnosis import DiagnosisEngine
            engine = DiagnosisEngine()
            quick = await engine.quick_assess(user_id=user_id)
            return {
                "result_ref": f"daily_brief:{user_id}:{int(time.time())}",
                "date": time.strftime("%Y-%m-%d"),
                "weak_count": quick.get("weak_count", 0),
                "streak_days": quick.get("streak_days", 0),
                "summary": quick.get("summary", ""),
            }
        except Exception as e:
            return {"error": f"每日简报生成失败: {e}"}

    async def _exec_expand_knowledge_graph(self, task: SilentTask) -> dict[str, Any]:
        """触发知识图谱扩展（轻量占位，实际扩展由知识树壳执行）"""
        node_id = (task.payload or {}).get("node_id", "")
        return {
            "result_ref": f"graph_expand:{task.user_id}:{node_id or 'user'}:{int(time.time())}",
            "node_id": node_id,
            "expanded": False,
            "note": "知识扩展请求已记录，等待知识树壳消费",
        }


# ── 全局实例 ──
silent_task_manager = SilentTaskManager()

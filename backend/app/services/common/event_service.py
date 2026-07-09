"""
Event Service — 事件驱动联动

桥接 in-memory EventBus + cognitive_events 持久化 + 后台消费。

职责：
1. 订阅所有 DomainEvent → 持久化到 cognitive_events 表
2. 提供业务事件 emit 辅助方法
3. 后台消费轮询未处理事件，分发到 handler
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

from shared.events import (
    DomainEvent,
    MessageClassified,
    PracticeSubmitted,
    NodeCreated,
    ProposalAccepted,
    EVENT_TYPES,
)
from shared.log_utils import log_event_processed, log_ripple_edge

logger = logging.getLogger(__name__)

# ── 事件类型常量 ──

EVT_MESSAGE_CLASSIFIED = "MessageClassified"
EVT_PRACTICE_SUBMITTED = "PracticeSubmitted"
EVT_NODE_CREATED = "NodeCreated"
EVT_PROPOSAL_ACCEPTED = "ProposalAccepted"

# ── Consumer 间隔 ──
_POLL_INTERVAL = 5  # 秒
_MAX_BATCH = 20


class EventService:
    """事件服务 — 桥接 in-memory EventBus + DB 持久化 + 后台消费"""

    def __init__(self, repo=None):
        self._consumer_task: asyncio.Task | None = None
        self._running = False
        self._container = None
        self._repo = repo

    def _lazy_repo(self):
        """Fallback: get events repo from container when not injected."""
        from app.infrastructure.db.events_repository import get_events_repo
        self._repo = get_events_repo()
        return self._repo

    # ─── 持久化桥接 ──────────────────────────────

    def subscribe_persist(self, event_bus) -> None:
        """订阅所有 DomainEvent → 持久化到 cognitive_events"""
        for event_type, cls in EVENT_TYPES.items():
            event_bus.subscribe(event_type, self._persist_handler(event_type))
        logger.info("📝 EventService 已订阅 %d 个事件类型 → 持久化", len(EVENT_TYPES))

    @staticmethod
    def _persist_handler(event_type: str):
        """返回一个 closure handler，将 DomainEvent 写入 events 表"""

        async def handler(event: DomainEvent) -> None:
            try:
                from app.infrastructure.db.events_repository import Event, get_events_repo

                ce = Event(
                    event_type=event_type,
                    user_id=getattr(event, "user_id", ""),
                    source_type="system",
                    source_id=getattr(event, "event_id", ""),
                    payload={
                        **(_domain_event_to_payload(event, event_type)),
                        "node_id": getattr(event, "node_id", ""),
                    },
                )
                get_events_repo().insert(ce)
            except Exception:
                logger.debug("持久化事件失败 (fire-and-forget): %s", event_type, exc_info=True)

        return handler

    # ─── 业务 emit ────────────────────────────

    @staticmethod
    def emit_event(
        event_type: str,
        user_id: str = "",
        node_id: str = "",
        payload: dict[str, Any] | None = None,
    ) -> str:
        """直接写入 events 表（同步）"""
        from app.infrastructure.db.events_repository import Event, get_events_repo

        ce = Event(
            event_type=event_type,
            user_id=user_id,
            source_type="system",
            payload={
                **(payload or {}),
                "node_id": node_id,
            },
        )
        get_events_repo().insert(ce)
        return ce.id

    @staticmethod
    def emit_message_classified(
        user_id: str,
        message_id: str,
        conv_id: str,
        topic_node_ids: list[str] | None = None,
        atom_node_ids: list[str] | None = None,
        mode: str = "confirm",
    ) -> str:
        """写入 message.classified 事件"""
        return EventService.emit_event(
            EVT_MESSAGE_CLASSIFIED,
            user_id=user_id,
            payload={
                "message_id": message_id,
                "conv_id": conv_id,
                "topic_node_ids": topic_node_ids or [],
                "atom_node_ids": atom_node_ids or [],
                "mode": mode,
            },
        )

    @staticmethod
    def emit_practice_submitted(
        user_id: str,
        atom_node_ids: list[str] | None = None,
        correctness: float = 0.0,
        latency_ms: float = 0.0,
    ) -> str:
        return EventService.emit_event(
            EVT_PRACTICE_SUBMITTED,
            user_id=user_id,
            payload={
                "atom_node_ids": atom_node_ids or [],
                "correctness": correctness,
                "latency_ms": latency_ms,
            },
        )

    @staticmethod
    def emit_node_created(
        user_id: str,
        node_id: str,
        parent_id: str = "",
        level: str = "atom",
        created_by: str = "user",
    ) -> str:
        return EventService.emit_event(
            EVT_NODE_CREATED,
            user_id=user_id,
            node_id=node_id,
            payload={
                "parent_id": parent_id,
                "level": level,
                "created_by": created_by,
            },
        )

    @staticmethod
    def emit_proposal_accepted(
        user_id: str,
        proposal_id: str,
        action_type: str,
        target_node_id: str = "",
        payload: Optional[dict] = None,
    ) -> str:
        full_payload = {
            "proposal_id": proposal_id,
            "action_type": action_type,
            "target_node_id": target_node_id,
        }
        if payload:
            full_payload.update(payload)
        return EventService.emit_event(
            EVT_PROPOSAL_ACCEPTED,
            user_id=user_id,
            node_id=target_node_id,
            payload=full_payload,
        )

    # ─── 后台消费者 ──────────────────────────────

    def start_consumer(self) -> None:
        """启动后台事件消费者（保留兼容，推荐由中央调度器管理）"""
        if self._running:
            return
        self._running = True
        self._consumer_task = asyncio.create_task(self._consume_loop())
        logger.info("🔄 EventService 消费者已启动 (间隔 %ds)", _POLL_INTERVAL)

    async def stop_consumer(self) -> None:
        """停止后台消费者"""
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
            self._consumer_task = None
            logger.info("🔄 EventService 消费者已停止")

    async def _consume_once(self) -> None:
        """单次消费未处理事件（供调度器周期调用）

        同步 DB 调用通过 run_in_executor 放入线程池。
        """
        loop = asyncio.get_event_loop()
        repo = self._repo or self._lazy_repo()

        try:
            events = await loop.run_in_executor(
                None, repo.get_unprocessed_events, _MAX_BATCH
            )
            for evt in events:
                await self._dispatch(evt)
                await loop.run_in_executor(None, repo.mark_event_processed, evt.id)
        except Exception:
            logger.exception("事件消费异常")

    async def _consume_loop(self) -> None:
        """轮询未处理 cognitive_events，按类型分发（保留兼容）"""
        repo = self._repo or self._lazy_repo()

        while self._running:
            try:
                events = repo.get_unprocessed_events(limit=_MAX_BATCH)
                for evt in events:
                    await self._dispatch(evt)
                    repo.mark_event_processed(evt.id)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("事件消费循环异常")
            await asyncio.sleep(_POLL_INTERVAL)

    async def _dispatch(self, evt) -> None:
        """按事件类型分发到 handler"""
        import time as _time
        start = _time.time()
        handler_name = f"_handle_{evt.event_type}"
        try:
            handler = getattr(self, handler_name, None)
            if handler:
                await handler(evt)
                dur = (_time.time() - start) * 1000
                log_event_processed(
                    evt.event_type, evt.id,
                    handler_name, dur, success=True,
                )
            else:
                logger.debug("事件 %s 无 handler，标记为已处理", evt.event_type)
        except Exception:
            dur = (_time.time() - start) * 1000
            log_event_processed(
                evt.event_type, evt.id,
                handler_name, dur, success=False,
            )

    # ─── Handler 实现 ────────────────────────────

    async def _handle_MessageClassified(self, evt) -> None:
        """
        message.classified → 可见性级联 + 结构扩展检查

        1. 级联祖先可见性
        2. 统计父节点下可见子节点活动频率 → 达标则生成横向扩展提案
        """
        repo = self._repo or self._lazy_repo()
        payload = evt.payload or {}
        node_ids = payload.get("topic_node_ids", []) + payload.get("atom_node_ids", [])
        for nid in node_ids:
            try:
                _cascade_ancestor_visibility(nid, evt.user_id, repo)
            except Exception:
                logger.debug("级联可见性失败: %s", nid, exc_info=True)

        # 6.1 结构扩展建议：检查父节点下子节点活跃度
        try:
            topic_ids = payload.get("topic_node_ids", [])
            if topic_ids:
                parent_candidates: set[str] = set()
                for tid in topic_ids:
                    node = repo.get_node(tid, evt.user_id)
                    if node and node.parent:
                        parent_candidates.add(node.parent)

                for pid in parent_candidates:
                    children = repo.get_children(pid, evt.user_id)
                    active_children = [c for c in children if c.is_visible and c.is_active]
                    if len(active_children) >= 3:
                        # 生成横向扩展提案
                        _generate_proposal(
                            user_id=evt.user_id,
                            emoji="🌿",
                            title=f"探索「{_get_node_label(pid, evt.user_id, repo)}」下的更多专题",
                            description=(
                                f"该分类下已有 {len(active_children)} 个活跃子专题。"
                                "需要自动生成更多拓展方向吗？"
                            ),
                            action_type="explore",
                            priority=2,
                            payload={
                                "parent_id": pid,
                                "parent_label": _get_node_label(pid, evt.user_id, repo),
                                "visible_count": len(active_children),
                            },
                            generated_by="event_handler",
                            insight_source="structure_expansion",
                        )
        except Exception:
            logger.debug("结构扩展检查失败", exc_info=True)

    async def _handle_PracticeSubmitted(self, evt) -> None:
        """practice.submitted → 更新涉及 atom node 的掌握度（真实数据）

        PracticeSubmitted 是多 node batch 事件，payload 中
        atom_node_ids: list[str]、correctness: float ∈ [0,1]、latency_ms: float。
        对每个 node:
          - 加载 CognitiveNode（不存在则用占位）
          - 贝叶斯更新 belief.alpha/beta（α 增答对、β 增答错）
          - 更新 practice_summary.total/correct/last_practiced
          - 重新计算 proficiency_mean
        """
        repo = self._repo or self._lazy_repo()
        payload = evt.payload or {}
        atom_ids: list[str] = payload.get("atom_node_ids", []) or []
        correctness: float = float(payload.get("correctness", 0.0) or 0.0)
        latency_ms: float = float(payload.get("latency_ms", 0.0) or 0.0)
        user_id: str = evt.user_id or ""
        if not user_id or not atom_ids:
            return
        # 只在第一次答对/答错生效
        is_correct = correctness >= 0.5

        try:
            from app.domain.cognitive.models import CognitiveNode, PracticeSummary
            now = time.time()
            updated = 0
            for nid in atom_ids:
                if not nid:
                    continue
                node = repo.get_node(nid, user_id)
                if node is None:
                    # 新题 → 创建占位 atom node
                    node = CognitiveNode(id=nid, label=nid, level="atom")

                # ── 贝叶斯更新 ──
                belief = node.belief
                if is_correct:
                    belief.alpha = float(belief.alpha) + 1.0
                else:
                    belief.beta = float(belief.beta) + 1.0
                # 重算 mean / peak
                alpha = float(belief.alpha)
                beta = float(belief.beta)
                belief.proficiency_mean = max(0.0, min(1.0, alpha / (alpha + beta)))
                belief.peak_proficiency = max(
                    float(belief.peak_proficiency), belief.proficiency_mean
                )
                belief.last_updated = now

                # ── 练习摘要更新 ──
                ps = node.practice_summary
                ps.total_attempts = int(ps.total_attempts) + 1
                if is_correct:
                    ps.correct_attempts = int(ps.correct_attempts) + 1
                ps.total_time_spent = float(ps.total_time_spent) + (latency_ms / 1000.0)
                ps.last_practiced = now

                repo.upsert_node(node, user_id)
                updated += 1

            logger.info(
                "✅ PracticeSubmitted 掌握度更新: user=%s nodes=%d correct=%s",
                user_id, updated, is_correct,
            )
        except Exception as e:
            logger.warning("PracticeSubmitted 掌握度更新失败: %s", e)

    async def _handle_NodeCreated(self, evt) -> None:
        """
        node.created → 波纹边确认（Phase 6.2）

        1. 获取新节点的 embedding
        2. 在相同层级检索语义邻居
        3. 创建 pending_confirm 边
        4. 生成边确认提案
        """
        repo = self._repo or self._lazy_repo()
        payload = evt.payload or {}
        node_id = evt.node_id
        user_id = evt.user_id
        level = payload.get("level", "atom")

        if not node_id or not user_id:
            return

        try:
            from app.infrastructure.db.cognitive_edge_storage import upsert_edge, get_edges_for_node
            from app.domain.cognitive.edge_models import KnowledgeEdge

            node = repo.get_node(node_id, user_id)
            if not node or not node.embedding:
                logger.debug("节点 %s 无 embedding，跳过波纹检测", node_id)
                return

            # 检索语义邻居（同层级，排除自身）
            neighbors = repo.vector_search(
                node.embedding, user_id,
                level=level, limit=5, min_similarity=0.3,
            )
            neighbors = [n for n in neighbors if n.get("id") != node_id]

            # 获取现有边避免重复
            existing_edges = get_edges_for_node(node_id, user_id)
            existing_targets = {
                e.target_node_id if e.source_node_id == node_id else e.source_node_id
                for e in existing_edges
            }

            # 为未连接的邻居创建 pending_confirm 边
            from datetime import datetime, timezone
            now_iso = datetime.now(timezone.utc).isoformat()
            pending_edges: list[dict] = []

            for nbr in neighbors[:3]:
                nid = nbr.get("id")
                if nid in existing_targets:
                    continue

                sim = nbr.get("similarity", 0.5)
                edge = KnowledgeEdge(
                    user_id=user_id,
                    source_node_id=node_id,
                    target_node_id=nid,
                    edge_type="related_to",
                    strength=sim,
                    trust_score=sim * 0.8,
                    edge_status="pending_confirm",
                    created_by="system",
                )
                upsert_edge(edge)
                pending_edges.append({
                    "edge_id": edge.id,
                    "source_label": node.label,
                    "target_label": nbr.get("label", nid),
                    "similarity": sim,
                    "target_node_id": nid,
                })

            if pending_edges:
                logger.info(
                    "🔗 波纹边检测: %s 生成 %d 条 pending_confirm 边",
                    node.label, len(pending_edges),
                )
                log_ripple_edge(
                    node.label,
                    pending_edges[0]["target_label"],
                    pending_edges[0]["similarity"],
                    len(pending_edges),
                )
                # 生成边确认提案（取相似度最高的第一个）
                top = pending_edges[0]
                _generate_proposal(
                    user_id=user_id,
                    emoji="🔗",
                    title=f"关联知识点「{top['target_label']}」",
                    description=(
                        f"新知识点「{top['source_label']}」与已学知识点"
                        f"「{top['target_label']}」语义相似度 {top['similarity']:.0%}，"
                        "是否建立关联？"
                    ),
                    action_type="explore",
                    priority=3,
                    payload={
                        "edge_id": top["edge_id"],
                        "source_node_id": node_id,
                        "target_node_id": top["target_node_id"],
                        "source_label": top["source_label"],
                        "target_label": top["target_label"],
                        "similarity": top["similarity"],
                        "pending_count": len(pending_edges),
                    },
                    generated_by="event_handler",
                    insight_source="ripple_edge",
                )
        except Exception:
            logger.exception("波纹边检测失败: node=%s", node_id)

    async def _handle_ProposalAccepted(self, evt) -> None:
        """
        proposal.accepted → 执行秘书提案动作

        支持的 action_type:
        - explore + parent_id → mark_expanded（标记已扩展抑制重复）
        - review / practice → （未来实现）
        """
        repo = self._repo or self._lazy_repo()
        payload = evt.payload or {}
        action_type = payload.get("action_type", "")
        target_node_id = payload.get("target_node_id", "")
        user_id = evt.user_id

        if action_type == "explore" and target_node_id:
            try:
                from app.domain.cognitive.growth_engine import growth_engine
                growth_engine.mark_expanded(user_id, target_node_id)
                logger.info("✅ 提案已执行: mark_expanded(user=%s, node=%s)", user_id, target_node_id)
            except Exception as e:
                logger.warning("mark_expanded 执行失败: %s", e)
        elif action_type in ("review", "practice"):
            # 记录用户已接受复习/练习事件，便于 dashboard 展示承诺
            # 该事件无需后续处理（processed=true），但留作历史/统计来源
            kp_id = payload.get("kp_id") or payload.get("target_node_id", "")
            try:
                from app.infrastructure.db.events_repository import Event, get_events_repo
                ce = Event(
                    event_type=f"{action_type.capitalize()}Accepted",
                    user_id=user_id,
                    source_type="system",
                    payload={
                        "proposal_id": payload.get("proposal_id", ""),
                        "node_id": kp_id,
                        "action_type": action_type,
                        "mastery": payload.get("mastery", 0.0),
                        "urgency": payload.get("urgency", 0.0),
                    },
                )
                repo.append_event(ce)
                # 立即 mark 为 processed（无需 handler）
                repo.mark_event_processed(ce.event_id)
                logger.info(
                    "✅ 提案已记录: %sAccepted(user=%s, kp=%s, mastery=%.0f%%)",
                    action_type, user_id, kp_id, (payload.get("mastery", 0.0) or 0.0) * 100,
                )
            except Exception as e:
                logger.warning("记录 %s 接受事件失败: %s", action_type, e)

    async def _handle_PendingCrossTopic(self, evt) -> None:
        """
        深度沉浸延后处理

        会话结束/空闲时，读取被抑制的跨主题候选，
        生成"本次对话涉及多个话题，是否关联？"的确认提案。
        """
        repo = self._repo or self._lazy_repo()
        candidates = evt.candidates if hasattr(evt, "candidates") else (evt.payload or {}).get("candidates", [])
        if not candidates:
            return

        logger.info(
            "📌 深度沉浸抑制跨主题建议: %d 个候选 (depth>=%d)",
            len(candidates), getattr(evt, "suppressed_at_depth", 0) or (evt.payload or {}).get("suppressed_at_depth", 16),
        )

        try:
            from app.infrastructure.db.cognitive_edge_storage import get_edges_for_node

            user_id = evt.user_id
            for cand in candidates[:2]:
                cid = cand.get("id", "")
                clabel = cand.get("label", "")
                cscore = cand.get("score", 0)
                if not cid:
                    continue

                # 检查候选节点是否存在
                node = repo.get_node(cid, user_id)
                if not node:
                    continue

                # 检查是否已有边连接
                edges = get_edges_for_node(cid, user_id)
                if edges:
                    # 已有边 → 说明已关联，跳过
                    continue

                # 生成跨主题关联提案
                _generate_proposal(
                    user_id=user_id,
                    emoji="🔀",
                    title=f"关联新话题「{clabel}」",
                    description=(
                        f"本次对话涉及了「{clabel}」相关内容"
                        f"（匹配度 {cscore:.0%}），"
                        "是否需要将它关联到当前知识图谱？"
                    ),
                    action_type="explore",
                    priority=2,
                    payload={
                        "candidate_node_id": cid,
                        "candidate_label": clabel,
                        "score": cscore,
                        "source": "deep_immersion_deferred",
                    },
                    generated_by="event_handler",
                    insight_source="pending_cross_topic",
                )
        except Exception:
            logger.exception("深度沉浸延后处理失败")


# ─── 可见性级联 ──────────────────────────────


def _cascade_ancestor_visibility(
    node_id: str, user_id: str,
    repo: CognitiveNodeRepository | None = None,
) -> None:
    """
    级联更新祖先可见性：向上递归查找父节点，
    若其不可见则设为可见，直到根或已可见节点。
    """
    if repo is None:
        from app.domain.cognitive import get_repo
        repo = get_repo()

    visited = set()
    current_id = node_id
    while current_id and current_id not in visited:
        visited.add(current_id)
        node = repo.get_node(current_id, user_id)
        if node is None:
            break
        # CognitiveNode 是 Pydantic 对象，使用属性访问
        if node.is_visible:
            break  # 已可见 → 祖先也应该已可见
        repo.set_node_visible(current_id, user_id, visible=True)
        current_id = node.parent


# ─── 工具 ──────────────────────────────────


def _domain_event_to_payload(event: DomainEvent, event_type: str) -> dict[str, Any]:
    """将 DomainEvent 转为 payload dict（排除 event_id/occurred_at）"""
    from dataclasses import asdict

    raw = asdict(event)
    raw.pop("event_id", None)
    raw.pop("occurred_at", None)
    # 序列化 list[UUID]
    for k, v in raw.items():
        if isinstance(v, list):
            raw[k] = [str(x) for x in v]
    return raw


# ─── 辅助 ──────────────────────────


def _generate_proposal(
    user_id: str,
    emoji: str,
    title: str,
    description: str,
    action_type: str,
    priority: int,
    payload: dict[str, Any] | None = None,
    generated_by: str = "event_handler",
    insight_source: str = "",
) -> None:
    """通过 ProposalStore 持久化一条提案（fire-and-forget）"""
    try:
        from app.domain.secretary.models import Proposal
        from app.infrastructure.db.proposal_store import ProposalStore

        proposal = Proposal(
            emoji=emoji,
            title=title,
            description=description,
            action_type=action_type,
            priority=priority,
            payload=payload or {},
            generated_by=generated_by,
            insight_source=insight_source,
        )
        store = ProposalStore()
        store.save_proposal(proposal, user_id=user_id)
        logger.info(
            "📋 提案已保存: [%s] %s (priority=%d, source=%s)",
            action_type, title, priority, insight_source,
        )
    except Exception:
        logger.debug("提案保存失败 (fire-and-forget): %s", title, exc_info=True)


def _get_node_label(
    node_id: str, user_id: str,
    repo: CognitiveNodeRepository | None = None,
) -> str:
    """获取节点 label（安全降级）"""
    try:
        if repo is None:
            from app.domain.cognitive import get_repo
            repo = get_repo()

        node = repo.get_node(node_id, user_id)
        if node:
            return node.label or node_id
    except Exception:
        pass
    return node_id or "unknown"


# ─── 单例 ──────────────────────────────────

event_service = EventService()

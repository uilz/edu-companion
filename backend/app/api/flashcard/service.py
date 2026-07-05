"""
FlashCard Service - 业务逻辑层

负责:
- 卡片 CRUD (含字段级粒度版本控制 field_versions)
- FSRS 调度计算 (调用 fsrs_scheduler)
- Belief 回写 (调用 belief_writer)
- 复习会话管理
- 错题本/文本导入

依据: docs/modules/flashcard/data-model.md + events.md + ADR 0002
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from app.infrastructure.db.database import get_db
from app.infrastructure.event_bus_utils import publish_event_safe
from app.services.flashcard.fsrs_scheduler import (
    FSRScheduler,
    FSRSState,
    DEFAULT_TARGET_RETENTION,
)
from app.services.flashcard.belief_writer import get_belief_writer
from shared.events import (
    FlashCardCreated,
    FlashCardUpdated,
    FlashCardReviewed,
    FlashCardStatusChanged,
    FlashCardSuspended,
    FlashCardResumed,
    FlashCardReset,
    FlashCardArchived,
    FlashCardDeleted,
    FlashCardSessionStarted,
    FlashCardSessionEnded,
)

logger = logging.getLogger(__name__)


# ── 工具函数 ──


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _ensure_tables() -> None:
    """幂等建表 (与 _deserialize 中的 JSON 列配合)"""
    db = get_db()
    sql_path_options = [
        "app/infrastructure/db/flashcard_schema.sql",
        "backend/app/infrastructure/db/flashcard_schema.sql",
    ]
    sql_path = None
    import os
    for p in sql_path_options:
        if os.path.exists(p):
            sql_path = p
            break
    if not sql_path:
        # 相对路径 (从 backend 工作目录)
        candidate = os.path.join(
            os.path.dirname(__file__), "../../infrastructure/db/flashcard_schema.sql"
        )
        if os.path.exists(candidate):
            sql_path = candidate
    if not sql_path:
        logger.error("找不到 flashcard_schema.sql")
        return
    with open(sql_path) as f:
        sql = f.read()
    for stmt in sql.split(";"):
        s = stmt.strip()
        if s:
            try:
                db.execute(s)
            except Exception as e:
                logger.warning("建表异常: %s", e)


def _row_to_dict(row: dict) -> dict:
    """DB 行 -> dict, JSON 列还原"""
    if row is None:
        return None
    out = dict(row)
    json_cols = {
        "source_ref", "linked_node_ids", "node_link_roles",
        "tags", "response_history", "field_versions",
    }
    for col in json_cols:
        v = out.get(col)
        if isinstance(v, str):
            try:
                out[col] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                pass
    return out


def _bump_field_version(field_versions: dict, field_name: str) -> dict:
    """字段级粒度版本控制: 字段被修改时 version + 1"""
    out = dict(field_versions or {})
    out[field_name] = int(out.get(field_name, 0)) + 1
    return out


def _json(v: Any) -> str:
    """统一 JSON 序列化"""
    return json.dumps(v, ensure_ascii=False, default=str)


# ── 卡片服务 ──


class FlashCardService:
    """FlashCard 业务逻辑

    设计要点:
    - 所有写操作都通过事件总线发布相应事件 (events.md)
    - FSRS 计算透明, 用户可手动覆盖
    - 字段级粒度版本控制 (field_versions)
    """

    def __init__(self, event_bus=None):
        self._bus = event_bus
        # 注入 event bus 后, 让 belief writer 也能用
        if event_bus:
            get_belief_writer().set_event_bus(event_bus)

    def set_event_bus(self, event_bus) -> None:
        self._bus = event_bus
        get_belief_writer().set_event_bus(event_bus)

    # ── 建表 ──

    @staticmethod
    def ensure_tables() -> None:
        _ensure_tables()

    # ── 创建 ──

    def create_card(self, user_id: str, payload: dict) -> dict:
        _ensure_tables()
        db = get_db()
        card_id = _uid("fc")
        now = _now()
        # FSRS 初始状态
        initial = FSRScheduler.initial_state(
            target_retention=payload.get("target_retention", DEFAULT_TARGET_RETENTION)
        )
        # ── source 字段语义 (依据 data-model.md §5.2, 7 种来源)
        # 卡片真正的 source 应保持用户提供的值, 不要被 cross_module_source 覆盖
        # cross_module_source 仅用于事件发布时补充标记
        cross_src = payload.get("cross_module_source")
        source = payload.get("source", "manual")
        # 关联角色规范化: linked_node_ids 与 node_link_roles 一致
        linked_nodes = payload.get("linked_node_ids", [])
        node_roles = dict(payload.get("node_link_roles", {}))
        # 默认第一个为 primary, 其余为 secondary
        if linked_nodes and not any(node_roles.get(n) == "primary" for n in linked_nodes):
            node_roles[linked_nodes[0]] = "primary"
        for n in linked_nodes:
            if n not in node_roles:
                node_roles[n] = "secondary"

        row = {
            "id": card_id,
            "user_id": user_id,
            "type": int(payload.get("type", 1)),
            "source": source,
            "front_text": payload.get("front_text", ""),
            "back_text": payload.get("back_text", ""),
            "back_context": payload.get("back_context", ""),
            "language": payload.get("language", ""),
            "source_ref": _json(payload.get("source_ref", {})),
            "status": payload.get("status", "pending"),
            "is_resolved": False,
            "stability": initial.stability,
            "difficulty": initial.difficulty,
            "forgetting_rate": initial.forgetting_rate,
            "last_review_at": None,
            "next_review_at": initial.next_review_at,
            "review_count": 0,
            "lapse_count": 0,
            "target_retention": initial.target_retention,
            "linked_node_ids": _json(linked_nodes),
            "node_link_roles": _json(node_roles),
            "tags": _json(payload.get("tags", [])),
            "error_book_entry_id": payload.get("error_book_entry_id", "") or None,
            "response_history": _json([]),
            "field_versions": _json({}),
            "created_at": now,
            "updated_at": now,
            "deleted_at": None,
        }
        cols = ", ".join(row.keys())
        placeholders = ", ".join(["%s"] * len(row))
        db.execute(
            f"INSERT INTO flashcards ({cols}) VALUES ({placeholders})",
            tuple(row.values()),
        )
        # 发布事件
        if self._bus:
            publish_event_safe(
                FlashCardCreated(
                    user_id=user_id,
                    card_id=card_id,
                    type=int(payload.get("type", 1)),
                    source="system" if cross_src else "manual",
                    cross_module_source=cross_src,
                    linked_node_ids=linked_nodes,
                    source_ref=payload.get("source_ref"),
                    created_at=now,
                ),
                bus=self._bus,
            )

        logger.info("📝 FlashCard 创建: %s (type=%s source=%s)", card_id, row["type"], row["source"])
        return self.get_card(user_id, card_id)

    # ── 查询 ──

    def get_card(self, user_id: str, card_id: str) -> dict | None:
        _ensure_tables()
        db = get_db()
        row = db.fetchone(
            "SELECT * FROM flashcards WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
            (card_id, user_id),
        )
        return _row_to_dict(row) if row else None

    def list_cards(
        self,
        user_id: str,
        status: str | None = None,
        type_: int | None = None,
        source: str | None = None,
        tag: str | None = None,
        node_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        _ensure_tables()
        db = get_db()
        conditions = ["user_id = %s", "deleted_at IS NULL"]
        params: list[Any] = [user_id]
        if status:
            conditions.append("status = %s")
            params.append(status)
        if type_ is not None:
            conditions.append("type = %s")
            params.append(int(type_))
        if source:
            conditions.append("source = %s")
            params.append(source)
        if tag:
            conditions.append("tags @> %s::jsonb")
            params.append(_json([tag]))
        if node_id:
            conditions.append("linked_node_ids @> %s::jsonb")
            params.append(_json([node_id]))
        where = " AND ".join(conditions)
        total_row = db.fetchone(
            f"SELECT COUNT(*) AS c FROM flashcards WHERE {where}", tuple(params)
        )
        total = int(total_row["c"]) if total_row else 0
        rows = db.fetchall(
            f"SELECT * FROM flashcards WHERE {where} "
            f"ORDER BY updated_at DESC LIMIT %s OFFSET %s",
            tuple(params) + (limit, offset),
        )
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "cards": [_row_to_dict(r) for r in rows],
        }

    def get_due_cards(
        self,
        user_id: str,
        limit: int = 20,
        node_id: str | None = None,
    ) -> dict:
        _ensure_tables()
        db = get_db()
        conditions = [
            "user_id = %s",
            "deleted_at IS NULL",
            "status = 'pending'",
        ]
        params: list[Any] = [user_id]
        if node_id:
            conditions.append("linked_node_ids @> %s::jsonb")
            params.append(_json([node_id]))
        where = " AND ".join(conditions)
        rows = db.fetchall(
            f"SELECT * FROM flashcards WHERE {where} "
            f"AND (next_review_at IS NULL OR next_review_at <= NOW()) "
            f"ORDER BY next_review_at ASC NULLS FIRST LIMIT %s",
            tuple(params) + (limit,),
        )
        cards = [_row_to_dict(r) for r in rows]
        return {"total": len(cards), "cards": cards}

    # ── 更新 ──

    def update_card(
        self,
        user_id: str,
        card_id: str,
        payload: dict,
        reset_scheduling: bool = False,
    ) -> dict | None:
        _ensure_tables()
        db = get_db()
        existing = self.get_card(user_id, card_id)
        if not existing:
            return None
        changed_fields: list[str] = []
        field_versions = dict(existing.get("field_versions") or {})
        # 白名单字段
        allowed = {
            "type", "front_text", "back_text", "back_context", "language",
            "source_ref", "status", "target_retention",
            "linked_node_ids", "node_link_roles", "tags",
        }
        updates: dict[str, Any] = {}
        for k in allowed:
            if k in payload and payload[k] is not None:
                old_v = existing.get(k)
                new_v = payload[k]
                if old_v != new_v:
                    changed_fields.append(k)
                    field_versions = _bump_field_version(field_versions, k)
                if k in {"source_ref", "linked_node_ids", "node_link_roles", "tags"}:
                    updates[k] = _json(new_v)
                else:
                    updates[k] = new_v
        if reset_scheduling:
            initial = FSRScheduler.initial_state(
                target_retention=updates.get("target_retention", existing.get("target_retention", 0.85))
            )
            updates["stability"] = initial.stability
            updates["difficulty"] = initial.difficulty
            updates["forgetting_rate"] = initial.forgetting_rate
            updates["review_count"] = 0
            updates["lapse_count"] = 0
            updates["next_review_at"] = initial.next_review_at
            updates["last_review_at"] = None
            changed_fields.append("scheduling")
        if not updates and not reset_scheduling:
            return existing
        updates["updated_at"] = _now()
        if field_versions:
            updates["field_versions"] = _json(field_versions)
        # status 变更事件
        old_status = existing.get("status")
        new_status = updates.get("status", old_status)
        # build UPDATE
        set_clause = ", ".join(f"{k} = %s" for k in updates.keys())
        params = list(updates.values()) + [card_id, user_id]
        db.execute(
            f"UPDATE flashcards SET {set_clause} "
            f"WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
            tuple(params),
        )
        # 发布事件
        if self._bus:
            self._safe_publish(FlashCardUpdated(
                user_id=user_id,
                card_id=card_id,
                changed_fields=changed_fields,
                reset_scheduling=reset_scheduling,
                updated_at=updates["updated_at"],
            ))
            if old_status != new_status:
                self._safe_publish(FlashCardStatusChanged(
                    user_id=user_id,
                    card_id=card_id,
                    old_status=old_status,
                    new_status=new_status,
                    changed_at=updates["updated_at"],
                ))
        return self.get_card(user_id, card_id)

    def _safe_publish(self, event) -> None:
        """发布事件 (失败不影响主流程) — 委托给 publish_event_safe"""
        if not self._bus:
            return
        publish_event_safe(event, bus=self._bus)

    # ── 删除 (软删除) ──

    def soft_delete(self, user_id: str, card_id: str) -> bool:
        _ensure_tables()
        db = get_db()
        existing = self.get_card(user_id, card_id)
        if not existing:
            return False
        now = _now()
        db.execute(
            "UPDATE flashcards SET deleted_at = %s, status = 'archived', updated_at = %s "
            "WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
            (now, now, card_id, user_id),
        )
        if self._bus:
            self._safe_publish(FlashCardDeleted(
                user_id=user_id, card_id=card_id, deleted_at=now,
            ))
        return True

    # ── 复习会话 ──

    def start_session(self, user_id: str, source_module: str = "manual", limit: int = 20) -> dict:
        _ensure_tables()
        session_id = _uid("rvs")
        now = _now()
        due = self.get_due_cards(user_id, limit=limit)
        db = get_db()
        db.execute(
            "INSERT INTO review_sessions (id, user_id, started_at, source_module, card_count) "
            "VALUES (%s, %s, %s, %s, %s)",
            (session_id, user_id, now, source_module, len(due["cards"])),
        )
        if self._bus:
            self._safe_publish(FlashCardSessionStarted(
                user_id=user_id,
                session_id=session_id,
                source_module=source_module,
                initial_card_count=len(due["cards"]),
                started_at=now,
            ))
        return {
            "session_id": session_id,
            "started_at": now.isoformat(),
            "initial_card_count": len(due["cards"]),
            "cards": due["cards"],
        }

    def end_session(
        self,
        user_id: str,
        session_id: str,
        difficult_count: int = 0,
        good_count: int = 0,
        easy_count: int = 0,
        duration_seconds: int = 0,
    ) -> dict:
        db = get_db()
        now = _now()
        total = difficult_count + good_count + easy_count
        db.execute(
            "UPDATE review_sessions SET ended_at = %s, card_count = %s, "
            "difficult_count = %s, good_count = %s, easy_count = %s, duration_seconds = %s "
            "WHERE id = %s AND user_id = %s",
            (now, total, difficult_count, good_count, easy_count, duration_seconds, session_id, user_id),
        )
        if self._bus:
            self._safe_publish(FlashCardSessionEnded(
                user_id=user_id,
                session_id=session_id,
                total_cards=total,
                difficult_count=difficult_count,
                good_count=good_count,
                easy_count=easy_count,
                duration_seconds=duration_seconds,
                ended_at=now,
            ))
        return {"session_id": session_id, "ended_at": now.isoformat(), "total": total}

    # ── 复习提交 (核心) ──

    async def submit_review(
        self,
        user_id: str,
        card_id: str,
        self_assessment: str,
        session_id: str = "",
    ) -> dict:
        _ensure_tables()
        card = self.get_card(user_id, card_id)
        if not card:
            raise ValueError(f"卡片不存在: {card_id}")
        if self_assessment not in ("difficult", "good", "easy"):
            raise ValueError(f"无效自评: {self_assessment}")

        # 当前 FSRS 状态
        # last_review_at 从 DB 读出是 naive datetime (TIMESTAMP 无时区),
        # 需显式补 UTC, 避免与 timezone-aware now 相减抛 TypeError
        last_review_raw = card.get("last_review_at")
        if last_review_raw is not None and last_review_raw.tzinfo is None:
            last_review_raw = last_review_raw.replace(tzinfo=timezone.utc)
        next_review_raw = card.get("next_review_at")
        if next_review_raw is not None and next_review_raw.tzinfo is None:
            next_review_raw = next_review_raw.replace(tzinfo=timezone.utc)
        current_state = FSRSState(
            stability=card.get("stability") or 2.5,
            difficulty=card.get("difficulty") or 5.0,
            forgetting_rate=card.get("forgetting_rate") or 0.0,
            last_review_at=last_review_raw,
            next_review_at=next_review_raw,
            review_count=card.get("review_count") or 0,
            lapse_count=card.get("lapse_count") or 0,
            target_retention=card.get("target_retention") or DEFAULT_TARGET_RETENTION,
        )
        result = FSRScheduler.review(current_state, self_assessment)  # type: ignore[arg-type]
        new_state = result.state

        # 持久化
        db = get_db()
        now = _now()
        is_lapse = (self_assessment == "difficult")
        db.execute(
            "UPDATE flashcards SET stability = %s, difficulty = %s, forgetting_rate = %s, "
            "last_review_at = %s, next_review_at = %s, review_count = %s, lapse_count = %s, "
            "updated_at = %s "
            "WHERE id = %s AND user_id = %s",
            (
                new_state.stability, new_state.difficulty, new_state.forgetting_rate,
                new_state.last_review_at, new_state.next_review_at,
                new_state.review_count, new_state.lapse_count,
                now,
                card_id, user_id,
            ),
        )
        # 写入 review_history
        rh_id = _uid("rh")
        # 兜底: 若调用方传了 session_id 但 review_sessions 没有该 row
        # (例如测试用 stub session_id), 自动创建占位 row, 避免 FK 违反
        actual_session_id = session_id or None
        if actual_session_id:
            sess_row = db.fetchone(
                "SELECT id FROM review_sessions WHERE id = %s",
                (actual_session_id,),
            )
            if not sess_row:
                try:
                    db.execute(
                        "INSERT INTO review_sessions (id, user_id, started_at, source_module) "
                        "VALUES (%s, %s, %s, %s)",
                        (actual_session_id, user_id, now, "manual"),
                    )
                except Exception:
                    # 如果并发创建失败, 降级为 None
                    logger.debug("review_sessions 自动创建失败, 降级 session_id=None")
                    actual_session_id = None
        db.execute(
            "INSERT INTO review_history "
            "(id, card_id, session_id, user_id, self_assessment, "
            "stability_before, stability_after, difficulty_before, difficulty_after, "
            "interval_before, interval_after, elapsed_days, reviewed_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                rh_id, card_id, actual_session_id, user_id, self_assessment,
                result.stability_before, result.stability_after,
                result.difficulty_before, result.difficulty_after,
                result.interval_days, result.interval_days,  # interval_after == 实际新间隔
                result.elapsed_days, now,
            ),
        )

        # 发布 FlashCardReviewed 事件
        review_event = FlashCardReviewed(
            user_id=user_id,
            card_id=card_id,
            session_id=session_id,
            self_assessment=self_assessment,  # type: ignore[arg-type]
            stability_before=result.stability_before,
            stability_after=result.stability_after,
            difficulty_before=result.difficulty_before,
            difficulty_after=result.difficulty_after,
            interval_before=result.interval_days,  # 当前计算的间隔
            interval_after=result.interval_days,
            elapsed_days=result.elapsed_days,
            linked_node_ids=card.get("linked_node_ids") or [],
            node_link_roles=card.get("node_link_roles") or {},
            next_review_at=new_state.next_review_at,
            reviewed_at=now,
        )
        if self._bus:
            try:
                await self._bus.publish(review_event)
            except Exception:
                logger.exception("发布 FlashCardReviewed 失败")

        # Belief 回写 (同步执行, 失败不影响主流程)
        # 始终计算 deltas (供前端展示), 仅在有 event_bus 时发布事件
        belief_deltas: list[dict] = []
        try:
            from app.services.flashcard.belief_writer import BeliefWriter
            belief_deltas = BeliefWriter.compute_belief_delta(review_event)
        except Exception:
            logger.exception("计算 Belief delta 失败")
        if self._bus:
            try:
                from app.services.flashcard.belief_writer import BeliefWriter
                writer = BeliefWriter(self._bus)
                await writer.write_belief(review_event)
                await writer.sync_error_book(review_event, card)
            except Exception:
                logger.exception("Belief 回写失败")

        return {
            "card_id": card_id,
            "self_assessment": self_assessment,
            "stability_before": result.stability_before,
            "stability_after": result.stability_after,
            "difficulty_before": result.difficulty_before,
            "difficulty_after": result.difficulty_after,
            "forgetting_rate_after": result.forgetting_rate_after,
            "interval_before": result.interval_days,  # 当前复习实际产生的间隔
            "interval_after": result.interval_days,
            "elapsed_days": result.elapsed_days,
            "retrievability_before": result.retrievability_before,
            # 累计指标 (供前端展示, 与 DB 一致)
            "review_count": new_state.review_count,
            "lapse_count": new_state.lapse_count,
            "next_review_at": new_state.next_review_at,
            "reviewed_at": now,
            "explanation": result.explanation,
            "belief_deltas": belief_deltas,
        }

    # ── 手动覆盖 FSRS 参数 ──

    def override_scheduling(
        self,
        user_id: str,
        card_id: str,
        stability: float | None = None,
        difficulty: float | None = None,
        target_retention: float | None = None,
        next_review_at: datetime | None = None,
    ) -> dict | None:
        existing = self.get_card(user_id, card_id)
        if not existing:
            return None
        # 与 submit_review 同样修复: naive datetime 补 UTC
        last_raw = existing.get("last_review_at")
        if last_raw is not None and last_raw.tzinfo is None:
            last_raw = last_raw.replace(tzinfo=timezone.utc)
        next_raw = existing.get("next_review_at")
        if next_raw is not None and next_raw.tzinfo is None:
            next_raw = next_raw.replace(tzinfo=timezone.utc)
        current = FSRSState(
            stability=existing.get("stability") or 2.5,
            difficulty=existing.get("difficulty") or 5.0,
            forgetting_rate=existing.get("forgetting_rate") or 0.0,
            last_review_at=last_raw,
            next_review_at=next_raw,
            review_count=existing.get("review_count") or 0,
            lapse_count=existing.get("lapse_count") or 0,
            target_retention=existing.get("target_retention") or DEFAULT_TARGET_RETENTION,
        )
        new_state = FSRScheduler.override(
            current,
            stability=stability,
            difficulty=difficulty,
            target_retention=target_retention,
            next_review_at=next_review_at,
        )
        db = get_db()
        db.execute(
            "UPDATE flashcards SET stability = %s, difficulty = %s, forgetting_rate = %s, "
            "target_retention = %s, next_review_at = %s, updated_at = %s "
            "WHERE id = %s AND user_id = %s",
            (
                new_state.stability, new_state.difficulty, new_state.forgetting_rate,
                new_state.target_retention, new_state.next_review_at, _now(),
                card_id, user_id,
            ),
        )
        return self.get_card(user_id, card_id)

    # ── 暂停/恢复/重置 ──

    def suspend(self, user_id: str, card_id: str) -> dict | None:
        db = get_db()
        now = _now()
        db.execute(
            "UPDATE flashcards SET status = 'suspended', suspended_at = %s, updated_at = %s "
            "WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
            (now, now, card_id, user_id),
        )
        card = self.get_card(user_id, card_id)
        if card and self._bus:
            self._safe_publish(FlashCardSuspended(
                user_id=user_id, card_id=card_id, suspended_at=now,
            ))
        return card

    def resume(self, user_id: str, card_id: str) -> dict | None:
        db = get_db()
        now = _now()
        db.execute(
            "UPDATE flashcards SET status = 'pending', suspended_at = NULL, updated_at = %s "
            "WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
            (now, card_id, user_id),
        )
        card = self.get_card(user_id, card_id)
        if card and self._bus:
            self._safe_publish(FlashCardResumed(
                user_id=user_id, card_id=card_id, resumed_at=now,
            ))
        return card

    def reset_scheduling(self, user_id: str, card_id: str) -> dict | None:
        existing = self.get_card(user_id, card_id)
        if not existing:
            return None
        initial = FSRScheduler.reset_scheduling(existing.get("target_retention", DEFAULT_TARGET_RETENTION))
        db = get_db()
        now = _now()
        db.execute(
            "UPDATE flashcards SET stability = %s, difficulty = %s, forgetting_rate = %s, "
            "last_review_at = NULL, next_review_at = %s, review_count = 0, lapse_count = 0, "
            "updated_at = %s WHERE id = %s AND user_id = %s",
            (
                initial.stability, initial.difficulty, initial.forgetting_rate,
                initial.next_review_at, now, card_id, user_id,
            ),
        )
        if self._bus:
            self._safe_publish(FlashCardReset(
                user_id=user_id, card_id=card_id, reset_at=now,
                previous_review_count=existing.get("review_count") or 0,
            ))
        return self.get_card(user_id, card_id)

    def archive(self, user_id: str, card_id: str) -> dict | None:
        db = get_db()
        now = _now()
        db.execute(
            "UPDATE flashcards SET status = 'archived', updated_at = %s "
            "WHERE id = %s AND user_id = %s AND deleted_at IS NULL",
            (now, card_id, user_id),
        )
        card = self.get_card(user_id, card_id)
        if card and self._bus:
            self._safe_publish(FlashCardArchived(
                user_id=user_id, card_id=card_id, archived_at=now,
            ))
        return card

    # ── 导入: 错题本 → FlashCard ──

    def import_from_errorbook(self, user_id: str, error_id: str) -> dict:
        """从 ErrorBookEntry 生成 FlashCard 预览 (GET)

        依据 ADR 0002 §9 决策 2: 错题卡绑定 error_book_entry_id,
        自评 easy 触发 ErrorBookEntry.is_resolved = true
        """
        _ensure_tables()
        db = get_db()
        err = db.fetchone(
            "SELECT * FROM error_book WHERE entry_id = %s AND user_id = %s",
            (error_id, user_id),
        )
        if not err:
            raise ValueError(f"错题本记录不存在: {error_id}")
        # 检查是否已经导入过
        existing = db.fetchone(
            "SELECT id FROM flashcards WHERE error_book_entry_id = %s AND user_id = %s "
            "AND deleted_at IS NULL",
            (error_id, user_id),
        )
        # 关联的认知节点 (从 error_book.skill_id 通过 knowledge_nodes 查询)
        node_ids: list[str] = []
        skill_id = err.get("skill_id", "")
        if skill_id:
            rows = db.fetchall(
                "SELECT id FROM knowledge_nodes WHERE user_id = %s AND path_id LIKE %s "
                "AND deleted_at IS NULL LIMIT 5",
                (user_id, f"%{skill_id}%"),
            )
            node_ids = [r["id"] for r in rows]
        return {
            "error_entry_id": error_id,
            "suggested_front": err.get("question_text", ""),
            "suggested_back": f"正确答案: {err.get('correct_answer', '')}\n你的答案: {err.get('user_answer', '')}",
            "question_id": err.get("question_id", ""),
            "skill_id": skill_id,
            "suggested_linked_node_ids": node_ids,
            "already_imported": existing is not None,
            "existing_card_id": existing["id"] if existing else None,
        }

    def confirm_import_from_errorbook(self, user_id: str, error_id: str, extra: dict | None = None) -> dict:
        """确认导入 (POST)"""
        preview = self.import_from_errorbook(user_id, error_id)
        if preview.get("already_imported"):
            return {"created": False, "card_id": preview["existing_card_id"], "message": "已存在对应 FlashCard"}
        extra = extra or {}
        payload = {
            "type": 6,  # 错题溯源
            "source": "practice_error",  # 依据 data-model.md §5.2
            "cross_module_source": "practice_error",
            "front_text": preview["suggested_front"],
            "back_text": preview["suggested_back"],
            "back_context": f"关联错题: {error_id}\n错题类型: {extra.get('error_type', 'unknown')}",
            "linked_node_ids": preview["suggested_linked_node_ids"],
            "tags": extra.get("tags", ["错题"]),
            "error_book_entry_id": error_id,
            "language": extra.get("language", ""),
        }
        card = self.create_card(user_id, payload)
        return {"created": True, "card": card}

    # ── 导入: 文本 → FlashCard ──

    def import_from_text(self, user_id: str, payload: dict) -> dict:
        """从对话/阅读文本提取 FlashCard 预览 (POST)

        简化实现: 用段落分隔 + 问号启发式判断正反面
        """
        text = (payload.get("text") or "").strip()
        if not text:
            raise ValueError("text 不能为空")
        # 简单分段: 中英文句号 / 问号 / 感叹号 / 换行
        segments = [s.strip() for s in re.split(r"[。！？.!?\n]+", text) if s.strip()]
        items = []
        node_ids = payload.get("default_linked_node_ids", [])
        # 启发式问题识别: 以疑问词开头 或 包含 "?" 残留
        question_prefixes = ("什么是", "如何", "为什么", "怎么", "何时", "何地", "何人",
                             "哪", "多少", "能否", "可否", "是不是", "应否", "是否")
        for seg in segments:
            if len(seg) < 4:
                continue
            # 问题判断: 以疑问词开头
            is_question = any(seg.startswith(p) for p in question_prefixes)
            if is_question:
                front = seg
                back = ""  # 留空, 用户填写
                confidence = 0.7
            else:
                front = f"什么是: {seg[:30]}{'...' if len(seg) > 30 else ''}"
                back = seg
                confidence = 0.5
            items.append({
                "suggested_front": front,
                "suggested_back": back,
                "confidence": confidence,
                "suggested_node_ids": node_ids,
            })
            if len(items) >= 20:
                break
        return {"items": items, "total": len(items)}

    def confirm_import_from_text(self, user_id: str, items: list[dict], default_payload: dict | None = None) -> list[dict]:
        """确认文本导入 (批量创建)"""
        default_payload = default_payload or {}
        # 跨模块来源标签, 仅用于事件发布 (与 source 区分)
        cross_src = default_payload.get("cross_module_source", "conversation")
        # 默认 source: 文本导入视为对话来源
        default_source = "conversation"
        created = []
        for it in items:
            payload = {
                "type": default_payload.get("type", 1),
                "source": default_source,
                "cross_module_source": cross_src,
                "front_text": it.get("suggested_front", ""),
                "back_text": it.get("suggested_back", ""),
                "linked_node_ids": it.get("suggested_node_ids", []) or default_payload.get("default_linked_node_ids", []),
                "tags": default_payload.get("tags", []),
                "language": default_payload.get("language", ""),
            }
            try:
                card = self.create_card(user_id, payload)
                created.append(card)
            except Exception as e:
                logger.warning("批量导入单条失败: %s", e)
        return created

    # ── 统计 ──

    def get_stats(self, user_id: str) -> dict:
        _ensure_tables()
        db = get_db()
        total_row = db.fetchone(
            "SELECT COUNT(*) AS c FROM flashcards WHERE user_id = %s AND deleted_at IS NULL",
            (user_id,),
        )
        total = int(total_row["c"]) if total_row else 0
        # by_type
        by_type = {str(i): 0 for i in range(1, 8)}
        for r in db.fetchall(
            "SELECT type, COUNT(*) AS c FROM flashcards WHERE user_id = %s AND deleted_at IS NULL "
            "GROUP BY type", (user_id,)
        ):
            by_type[str(r["type"])] = int(r["c"])
        # by_source
        by_source: dict[str, int] = {}
        for r in db.fetchall(
            "SELECT source, COUNT(*) AS c FROM flashcards WHERE user_id = %s AND deleted_at IS NULL "
            "GROUP BY source", (user_id,)
        ):
            by_source[r["source"]] = int(r["c"])
        # by_status
        by_status: dict[str, int] = {}
        for r in db.fetchall(
            "SELECT status, COUNT(*) AS c FROM flashcards WHERE user_id = %s AND deleted_at IS NULL "
            "GROUP BY status", (user_id,)
        ):
            by_status[r["status"]] = int(r["c"])
        # due counts
        due_today = db.fetchone(
            "SELECT COUNT(*) AS c FROM flashcards WHERE user_id = %s AND deleted_at IS NULL "
            "AND status = 'pending' AND (next_review_at IS NULL OR next_review_at <= NOW())",
            (user_id,),
        )
        due_7d = db.fetchone(
            "SELECT COUNT(*) AS c FROM flashcards WHERE user_id = %s AND deleted_at IS NULL "
            "AND status = 'pending' AND (next_review_at IS NULL OR next_review_at <= NOW() + INTERVAL '7 days')",
            (user_id,),
        )
        # 平均 FSRS 参数
        avg_row = db.fetchone(
            "SELECT AVG(stability) AS s, AVG(difficulty) AS d, AVG(forgetting_rate) AS f "
            "FROM flashcards WHERE user_id = %s AND deleted_at IS NULL",
            (user_id,),
        )
        return {
            "total": total,
            "by_type": by_type,
            "by_source": by_source,
            "by_status": by_status,
            "due_today": int(due_today["c"]) if due_today else 0,
            "due_7d": int(due_7d["c"]) if due_7d else 0,
            "average_stability": float(avg_row["s"]) if avg_row and avg_row["s"] else 0.0,
            "average_difficulty": float(avg_row["d"]) if avg_row and avg_row["d"] else 0.0,
            "average_forgetting_rate": float(avg_row["f"]) if avg_row and avg_row["f"] else 0.0,
        }


# ── 全局单例 ──

_service: FlashCardService | None = None


def get_flashcard_service(event_bus=None) -> FlashCardService:
    """获取 FlashCardService 全局单例

    Args:
        event_bus: 可选 — 显式传入 EventBus 实例
            - 若单例尚未创建, 直接使用
            - 若单例已存在但 _bus 为 None, 注入传入的 bus
            - 若两者都有, 单例保持原 bus (避免测试间相互污染)
    如果 event_bus 未传入, 尝试从 DI 容器懒加载, 避免 event bus 缺失导致事件
    链路静默失败 (修复: interest_explorer 跨模块导入不发布 FlashCardCreated)。
    """
    global _service
    if event_bus is None:
        # 兜底: 从 DI 容器懒加载, 保证事件能正常发布
        try:
            from app.application.di import container
            event_bus = getattr(container, "event_bus", None)
        except Exception:
            event_bus = None
    if _service is None:
        _service = FlashCardService(event_bus=event_bus)
    elif event_bus and _service._bus is None:
        _service.set_event_bus(event_bus)
    return _service

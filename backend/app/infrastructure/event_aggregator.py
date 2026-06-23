"""
EventAggregator — 事件聚合引擎

将原子事件聚合为高层摘要:
- MessageSent × N  → ConversationDigest   (每N条消息)
- AnswerSubmitted × N → PracticeSessionSummary (会话结束时)
- DailyDigest × 7 → WeeklyLearningReport (每周)

聚合结果作为新事件写回 EventStore，形成事件层级。
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Optional

from app.infrastructure.event_store import EventRecord, get_event_store

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 聚合阈值配置
# ═══════════════════════════════════════════

class AggregationThresholds:
    """聚合触发阈值"""
    MESSAGES_PER_CONVERSATION_DIGEST = 6   # 每6条消息生成对话摘要
    ANSWERS_PER_SESSION = 5                 # 每5次答题检查聚合
    SESSION_COMPLETE = True                 # 会话完成时聚合
    DAILY_DIGEST_HOUR = 23                  # 每日23点生成日报 (或手动触发)


# ═══════════════════════════════════════════
# EventAggregator
# ═══════════════════════════════════════════

class EventAggregator:
    """事件聚合引擎"""

    def __init__(self):
        # 计数器: user_id:stream_id → count
        self._msg_counts: dict[str, int] = defaultdict(int)
        self._answer_counts: dict[str, int] = defaultdict(int)

    # ── 事件入口 ──

    async def on_event(self, event: EventRecord) -> Optional[EventRecord]:
        """每次事件后检查聚合条件, 返回聚合事件 (如果有)"""
        event_type = event.event_type
        key = f"{event.user_id}:{event.stream_id}"

        if event_type == "AssistantReplied":
            return await self._check_conversation_digest(event, key)
        elif event_type == "AnswerSubmitted":
            return await self._check_answer_aggregation(event, key)
        elif event_type == "SessionCompleted":
            return await self._on_session_completed(event)

        return None

    # ── 对话聚合 ──

    async def _check_conversation_digest(
        self, event: EventRecord, key: str
    ) -> Optional[EventRecord]:
        self._msg_counts[key] += 1
        if self._msg_counts[key] >= AggregationThresholds.MESSAGES_PER_CONVERSATION_DIGEST:
            self._msg_counts[key] = 0
            return await self.aggregate_conversation_digest(
                event.user_id, event.stream_id
            )
        return None

    async def aggregate_conversation_digest(
        self, user_id: str, conversation_id: str
    ) -> Optional[EventRecord]:
        """聚合最近 N 条消息为对话摘要"""
        store = get_event_store()
        events = await store.stream("conversation", conversation_id, limit=20)

        # 取最近 N 条 AssistantReplied 事件
        msg_events = [
            e for e in events
            if e.event_type in ("AssistantReplied", "MessageClassified")
        ][-AggregationThresholds.MESSAGES_PER_CONVERSATION_DIGEST:]

        if not msg_events:
            return None

        # 提取摘要内容
        topics = set()
        content_snippets = []
        for e in msg_events:
            if e.event_type == "AssistantReplied":
                content = e.payload.get("content", "")
                if content:
                    content_snippets.append(content[:200])
            if e.event_type == "MessageClassified":
                for nid in e.payload.get("topic_node_ids", []):
                    topics.add(nid)

        digest_text = " | ".join(content_snippets)

        # 生成聚合事件
        try:
            ai_summary = await self._generate_summary(digest_text, user_id)
        except Exception:
            ai_summary = digest_text[:500]

        aggregate_event = EventRecord(
            id=f"agg_{int(time.time()*1000)}",
            user_id=user_id,
            event_type="ConversationDigest",
            stream_type="conversation",
            stream_id=conversation_id,
            source_type="aggregator",
            source_id=conversation_id,
            payload={
                "message_count": len(msg_events),
                "topics": list(topics),
                "digest_text": digest_text[:1000],
            },
            summary=ai_summary,
            importance=0.5,
            created_at=time.time(),
        )
        return aggregate_event

    # ── 练习聚合 ──

    async def _check_answer_aggregation(
        self, event: EventRecord, key: str
    ) -> Optional[EventRecord]:
        self._answer_counts[key] += 1
        # 每 N 次答题不单独聚合，由 SessionCompleted 统一处理
        return None

    async def _on_session_completed(
        self, event: EventRecord
    ) -> Optional[EventRecord]:
        return await self.aggregate_practice_session(
            event.user_id, event.stream_id
        )

    async def aggregate_practice_session(
        self, user_id: str, session_id: str
    ) -> Optional[EventRecord]:
        """聚合练习会话为摘要"""
        store = get_event_store()
        events = await store.stream("practice", session_id, limit=200)

        answers = [e for e in events if e.event_type == "AnswerSubmitted"]
        if not answers:
            return None

        correct = sum(1 for a in answers if a.payload.get("is_correct"))
        total = len(answers)
        accuracy = correct / total if total > 0 else 0

        # 技能覆盖
        skills = set()
        for a in answers:
            sid = a.payload.get("skill_id", "")
            if sid:
                skills.add(sid)

        summary_text = (
            f"练习完成: {total}题, 正确{correct}题, 准确率{accuracy:.0%}, "
            f"涉及{len(skills)}个知识点"
        )

        aggregate_event = EventRecord(
            id=f"agg_{int(time.time()*1000)}",
            user_id=user_id,
            event_type="PracticeSessionSummary",
            stream_type="practice",
            stream_id=session_id,
            source_type="aggregator",
            source_id=session_id,
            payload={
                "total_questions": total,
                "correct_count": correct,
                "accuracy": accuracy,
                "skills": list(skills),
            },
            summary=summary_text,
            importance=0.6,
            created_at=time.time(),
        )
        return aggregate_event

    # ── 每日聚合 ──

    async def aggregate_daily(
        self, user_id: str, date_str: str = ""
    ) -> Optional[EventRecord]:
        """聚合每日事件为日报"""
        import datetime

        if not date_str:
            date_str = datetime.date.today().isoformat()

        # 日期范围
        dt = datetime.date.fromisoformat(date_str)
        since = datetime.datetime(
            dt.year, dt.month, dt.day, tzinfo=datetime.timezone.utc
        ).timestamp()
        until = since + 86400

        store = get_event_store()
        events = await store.replay(user_id, since, until, limit=500)

        if not events:
            return None

        # 统计
        total_conv = len(set(
            e.stream_id for e in events
            if e.stream_type == "conversation" and e.stream_id
        ))
        total_practice = len(set(
            e.stream_id for e in events
            if e.stream_type == "practice" and e.stream_id
        ))
        answers = [e for e in events if e.event_type == "AnswerSubmitted"]
        correct = sum(1 for a in answers if a.payload.get("is_correct"))

        summary_text = (
            f"今日学习: {total_conv}次对话, {total_practice}次练习, "
            f"{len(answers)}题, 正确{correct}题"
        )

        aggregate_event = EventRecord(
            id=f"agg_{int(time.time()*1000)}",
            user_id=user_id,
            event_type="DailyDigest",
            stream_type="user",
            stream_id=user_id,
            source_type="aggregator",
            source_id=date_str,
            payload={
                "date": date_str,
                "conversation_count": total_conv,
                "practice_count": total_practice,
                "answer_count": len(answers),
                "correct_count": correct,
            },
            summary=summary_text,
            importance=0.8,
            created_at=time.time(),
        )
        return aggregate_event

    # ── AI 摘要生成 ──

    async def _generate_summary(self, text: str, user_id: str) -> str:
        """使用 LLM 生成事件摘要"""
        if len(text) < 50:
            return text
        try:
            from app.infrastructure.llm.llm_service import get_llm_service
            llm = get_llm_service()
            prompt = (
                "用一句话(不超过100字)总结以下学习对话内容，"
                "聚焦于知识点和学生的理解状态:\n\n"
                f"{text[:2000]}"
            )
            result = await llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=150,
            )
            return result.strip()
        except Exception as e:
            logger.warning("摘要生成失败: %s", e)
            return text[:200]


# ── 全局单例 ──

_aggregator: Optional[EventAggregator] = None


def get_event_aggregator() -> EventAggregator:
    global _aggregator
    if _aggregator is None:
        _aggregator = EventAggregator()
    return _aggregator
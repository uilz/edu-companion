"""
EventMemory — 四级事件记忆系统

ShortTerm:  内存 RingBuffer, 最近 N 条事件, 用于当前对话上下文
Working:    当前会话事件列表, 会话结束时清空
LongTerm:   pgvector 语义搜索, 跨会话回忆
Episodic:   高重要性事件 (importance>0.7), 里程碑/突破点

用法:
    memory = EventMemory()
    memory.remember(user_id, event)           # 写入短期记忆
    recent = memory.short_term(user_id)        # 最近事件
    memory.working_start(user_id, "s1")        # 开始会话
    memory.working_end(user_id)                # 结束会话
    results = await memory.search(user_id, "三角函数")  # 语义搜索
"""
from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Optional

from app.infrastructure.event_store import EventRecord, get_event_store

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 短期记忆 RingBuffer
# ═══════════════════════════════════════════

class ShortTermMemory:
    """固定容量环形缓冲区, 每用户独立"""

    def __init__(self, capacity: int = 100):
        self._capacity = capacity
        self._buffers: dict[str, deque[EventRecord]] = defaultdict(
            lambda: deque(maxlen=capacity)
        )

    def remember(self, user_id: str, event: EventRecord) -> None:
        self._buffers[user_id].append(event)

    def recall(self, user_id: str, limit: int = 20) -> list[EventRecord]:
        buf = self._buffers.get(user_id)
        if not buf:
            return []
        return list(buf)[-limit:]

    def clear(self, user_id: str) -> None:
        self._buffers.pop(user_id, None)


# ═══════════════════════════════════════════
# 工作记忆 Session
# ═══════════════════════════════════════════

class WorkingMemory:
    """当前会话事件列表"""

    def __init__(self):
        self._sessions: dict[str, list[EventRecord]] = defaultdict(list)

    def start(self, user_id: str, session_id: str) -> None:
        key = f"{user_id}:{session_id}"
        self._sessions[key] = []

    def remember(self, user_id: str, session_id: str, event: EventRecord) -> None:
        key = f"{user_id}:{session_id}"
        if key in self._sessions:
            self._sessions[key].append(event)

    def recall(self, user_id: str, session_id: str = "") -> list[EventRecord]:
        if session_id:
            key = f"{user_id}:{session_id}"
            return self._sessions.get(key, [])
        # 返回用户所有活跃会话的事件
        prefix = f"{user_id}:"
        all_events = []
        for key, events in self._sessions.items():
            if key.startswith(prefix):
                all_events.extend(events)
        return all_events

    def end(self, user_id: str, session_id: str) -> list[EventRecord]:
        key = f"{user_id}:{session_id}"
        return self._sessions.pop(key, [])


# ═══════════════════════════════════════════
# EventMemory — 四级记忆聚合
# ═══════════════════════════════════════════

class EventMemory:
    """四级事件记忆系统"""

    def __init__(self):
        self._short_term = ShortTermMemory(capacity=100)
        self._working = WorkingMemory()

    # ── 短期记忆 ──

    def remember(self, user_id: str, event: EventRecord) -> None:
        """写入短期记忆 (自动所有事件)"""
        self._short_term.remember(user_id, event)

    def short_term(self, user_id: str, limit: int = 20) -> list[EventRecord]:
        """获取最近 N 条事件"""
        return self._short_term.recall(user_id, limit)

    # ── 工作记忆 ──

    def working_start(self, user_id: str, session_id: str) -> None:
        """开始会话工作记忆"""
        self._working.start(user_id, session_id)

    def working_event(self, user_id: str, session_id: str, event: EventRecord) -> None:
        """记录会话内事件"""
        self._working.remember(user_id, session_id, event)

    def working_events(
        self, user_id: str, session_id: str = ""
    ) -> list[EventRecord]:
        """获取当前会话事件"""
        return self._working.recall(user_id, session_id)

    def working_end(
        self, user_id: str, session_id: str
    ) -> list[EventRecord]:
        """结束会话, 返回所有事件"""
        events = self._working.end(user_id, session_id)
        return events

    # ── 长期记忆 (语义搜索) ──

    async def search(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> list[EventRecord]:
        """语义搜索长期记忆"""
        store = get_event_store()
        return await store.search_similar(
            query, user_id=user_id, limit=limit, min_importance=0.3
        )

    # ── 情节记忆 (里程碑) ──

    async def episodic(
        self, user_id: str, limit: int = 20
    ) -> list[EventRecord]:
        """获取高重要性里程碑事件"""
        store = get_event_store()
        return await store.query(
            user_id, min_importance=0.7, limit=limit
        )

    # ── 上下文构建 (给 LLM 注入) ──

    def build_context(
        self,
        user_id: str,
        session_id: str = "",
        short_term_limit: int = 10,
    ) -> str:
        """构建 AI 上下文: 短期记忆 + 工作记忆

        Returns:
            格式化的上下文文本, 可直接注入 LLM system/user prompt
        """
        parts = []

        # 短期记忆 (最近事件)
        recent = self.short_term(user_id, short_term_limit)
        if recent:
            lines = ["## 最近事件"]
            for r in recent:
                ts = ""
                if r.created_at:
                    from datetime import datetime, timezone
                    ts = datetime.fromtimestamp(
                        r.created_at, tz=timezone.utc
                    ).strftime("%H:%M")
                lines.append(f"- [{ts}] {r.event_type}: {r.summary or r._brief()}")
            parts.append("\n".join(lines))

        # 工作记忆 (当前会话)
        working = self.working_events(user_id, session_id)
        if working:
            lines = ["## 当前会话事件"]
            for w in working:
                lines.append(f"- {w.event_type}: {w.summary or w._brief()}")
            parts.append("\n".join(lines))

        return "\n\n".join(parts)


# ── 全局单例 ──

_memory: Optional[EventMemory] = None


def get_event_memory() -> EventMemory:
    global _memory
    if _memory is None:
        _memory = EventMemory()
    return _memory


# ── EventRecord 辅助方法 ──

def _event_brief(self: EventRecord) -> str:
    """生成事件简短描述"""
    p = self.payload
    if self.event_type == "AnswerSubmitted":
        correct = "✓" if p.get("is_correct") else "✗"
        return f"答题{correct} {p.get('skill_id', '')}"
    if self.event_type == "AssistantReplied":
        content = p.get("content", "")
        return content[:80] + ("..." if len(content) > 80 else "")
    if self.event_type == "SessionCompleted":
        return f"练习完成 准确率{p.get('accuracy', 0):.0%}"
    if self.event_type == "CognitiveNodeUpdated":
        return f"知识更新 {p.get('label', '')} {p.get('proficiency_before', 0):.2f}→{p.get('proficiency_after', 0):.2f}"
    return p.get("label", "") or p.get("question", "") or ""


EventRecord._brief = _event_brief
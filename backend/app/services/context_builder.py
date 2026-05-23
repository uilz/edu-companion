"""对话上下文构建器

构建发送给 LLM 的消息列表，集成以下上下文注入：
- 系统提示（苹小果人格设定）
- 多维情绪感知
- 统一知识状态
- 练习上下文（进行中 + 回顾）
- 知识图谱（已掌握/薄弱/未接触）
- 上下文感知选题建议
"""

from __future__ import annotations

import logging
from typing import Any

from app.schemas.conversation import (
    Partition,
    Conversation,
    TreeNode,
    TextBlock,
)
from app.services.emotion_analyzer import emotion_analyzer
from app.services.prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)


# ── 上下文消息构建 ──


def _build_context_messages(
    partition: Partition,
    conversation: Conversation,
    recent_messages: list[TreeNode],
    user_text: str,
    user_id: str = "",
) -> list[dict[str, str]]:
    """
    Build the message list sent to the LLM (replaces the old branch-based approach).

    Constructs a system message enriched with dynamic context layers, then appends
    recent conversation history and the current user utterance.

    Layers injected (in order):
        1. Base system prompt (苹小果 personality)
        2. Emotion context (session-level)
        3. Knowledge state (global)
        4. Emotion detection on current message (instant strategy)
        5. Practice context (current practice sessions)
        6. Practice recall data (if user asks about past practice)
        7. Context-aware practice suggestions (topic, Bloom level, difficulty)
        8. Partition summary & name
        9. Knowledge graph mastery overview
    """
    messages: list[dict[str, str]] = []

    # ── 1. Base system prompt ──
    system_content = SYSTEM_PROMPT

    # ── 2. Session-level emotion context ──
    emotion_ctx = emotion_analyzer.build_emotion_context(user_id)
    if emotion_ctx:
        system_content += emotion_ctx

    # ── 3. Global knowledge state ──
    try:
        from app.services.knowledge_bridge import knowledge_bridge

        knowledge_ctx = knowledge_bridge.get_knowledge_context()
        if knowledge_ctx:
            system_content += f"\n\n{knowledge_ctx}"
    except Exception:
        pass

    # ── 4. Instant emotion detection on current message ──
    try:
        quick_emotion = emotion_analyzer.quick_detect(user_text)
    except Exception:
        quick_emotion = None

    if quick_emotion:
        severity = (
            "negative"
            if quick_emotion
            in ("frustration", "anxiety", "overwhelm", "boredom", "procrastination")
            else "neutral"
        )
        if severity == "negative":
            strategy = (
                "\n\n⚠️ 学生当前表现出负面情绪（{label}）。请优先共情和鼓励，"
                "不要急于纠正或给建议。先肯定ta的努力，再温和地提供帮助。"
                "语气要比平时更温暖、更有耐心。"
            ).format(
                label={
                    "frustration": "挫败",
                    "anxiety": "焦虑",
                    "overwhelm": "压力大",
                    "boredom": "无聊",
                    "procrastination": "拖延",
                }.get(quick_emotion, quick_emotion)
            )
            system_content += strategy
        elif quick_emotion == "motivated":
            system_content += "\n\n💪 学生充满动力，可以适当加难度，趁热打铁！"
        elif quick_emotion == "achievement":
            system_content += "\n\n🎉 学生取得了进展，请肯定ta的具体进步。"

    # ── 5. Inject active practice context ──
    try:
        from app.services.practice_integrator import inject_practice_context

        practice_ctx = inject_practice_context(user_id, partition.id)
        if practice_ctx:
            system_content += f"\n\n{practice_ctx}"
    except Exception:
        pass

    # ── 6. Practice recall (when user asks about past practice) ──
    try:
        from app.services.practice_recall import practice_recall

        if practice_recall.is_recall_query(user_text):
            from app.shared.state import active_practice_sessions

            recall_sessions = list(active_practice_sessions.values())
            if recall_sessions:
                recall_text = practice_recall.generate_recall(
                    sessions=recall_sessions,
                    days=7,
                    subject_filter=partition.subject or "",
                )
                system_content += (
                    f"\n\n[练习回顾]\n{recall_text}\n\n"
                    "请在回复中自然地引用这些练习数据来回答用户。"
                )
    except Exception:
        pass

    # ── 7. Context-aware practice suggestion ──
    try:
        from app.services.context_trigger import context_trigger
        from app.services.storage import storage as _storage2

        data = _storage2.load(user_id)
        if conversation:
            recent_msgs = []
            for nid in conversation.path[-5:]:
                node = data.nodes.get(nid)
                if node and not node.is_deleted:
                    recent_msgs.append(node)
            ctx = context_trigger.trigger(
                user_id=user_id,
                conversation=conversation,
                recent_messages=recent_msgs,
            )
            system_content += (
                f"\n\n[选题建议] 当前对话主题涉及: {ctx['skill_ids']}, "
                f"Bloom: {ctx['bloom_level']}, 推荐难度: {ctx['difficulty']:.2f}"
            )
            if ctx.get("confused"):
                system_content += ", ⚠️ 检测到困惑信号"
            if any(s for s in ctx.get("skill_ids", []) if s != "general_practice"):
                system_content += (
                    "\n[Media] 如果用户需要视频讲解，"
                    "推荐生成多平台搜索链接(B站/YouTube/知乎)"
                )
    except Exception:
        pass

    # ── 8. Partition summary ──
    if partition.context_summary:
        system_content += f"\n\n当前分区：{partition.name}"
        system_content += f"\n分区摘要：{partition.context_summary}"

    # ── 9. Knowledge graph mastery overview ──
    try:
        graph = data.knowledge_graphs.get(partition.id)
        if graph and graph.nodes:
            nodes_list = list(graph.nodes.values())
            mastered = [n.label for n in nodes_list if n.mastery >= 80]
            weak = [n.label for n in nodes_list if 10 <= n.mastery < 50]
            untouched = [n.label for n in nodes_list if n.mastery == 0]

            system_content += f"\n\n📊 知识图谱 ({len(nodes_list)}个知识点):"
            if mastered:
                system_content += f"\n   ✅ 已掌握: {', '.join(mastered[:5])}"
            if weak:
                system_content += f"\n   🔶 薄弱: {', '.join(weak[:5])}"
            if untouched:
                system_content += f"\n   ⬜ 未接触: {', '.join(untouched[:3])}"

            ready_to_learn = [
                n for n in nodes_list if n.mastery == 0 and n.priority >= 5
            ]
            if ready_to_learn:
                next_up = sorted(ready_to_learn, key=lambda n: -n.priority)[:3]
                system_content += f"\n   🎯 建议下一步: {', '.join(n.label for n in next_up)}"

            all_labels = [n.label for n in nodes_list[:15]]
            system_content += f"\n\n可引用的知识点: {', '.join(all_labels)}"
            system_content += "\n回答涉及这些知识点时，在末尾标注 [来源: 知识点名称]。"
    except Exception:
        pass

    messages.append({"role": "system", "content": system_content})

    # ── Recent conversation history (last 8 messages) ──
    for msg in recent_messages[-8:]:
        if msg.is_deleted:
            continue
        text_parts = []
        for block in msg.content_blocks:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
            elif hasattr(block, "text"):
                text_parts.append(block.text)
        text = " ".join(text_parts) if text_parts else "[媒体内容]"

        if len(text) > 500:
            text = text[:500] + "..."

        role = msg.role if msg.role in ("user", "assistant") else "assistant"
        messages.append({"role": role, "content": text})

    # ── Current user message ──
    messages.append({"role": "user", "content": user_text})

    return messages

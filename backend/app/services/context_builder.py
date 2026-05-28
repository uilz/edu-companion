"""对话上下文构建器

构建发送给 LLM 的消息列表，集成以下上下文注入：
- 系统提示（苹小果人格设定）
- 多维情绪感知
- 统一知识状态
- 练习上下文（进行中 + 回顾）
- 知识图谱（已掌握/薄弱/未接触）
- 认知画像（CognitiveNode 掌握度/趋势/负荷/错误模式）
- 上下文感知选题建议
"""

from __future__ import annotations

import logging

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
        7.5. CognitiveNode cognitive profile (mastery, trend, load, errors)
        8. Partition summary & name
        9. Knowledge graph mastery overview
        10. Tool availability hint (available tools for the LLM to suggest)
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

        knowledge_ctx = knowledge_bridge.get_knowledge_context(user_id)
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
            from shared.state import active_practice_sessions

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
    except Exception as e:
        logger.debug(f"知识图谱概览注入跳过: {e}")

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

    # ── 7.5 CognitiveNode 认知画像注入 ──
    try:
        from app.cognitive.storage import get_node, find_node_by_label

        cog_node = None
        # 优先用 partition.id 直接查找
        if partition.id:
            cog_node = get_node(partition.id, user_id)
        # 尝试用 subject (可能含 skill_id) 查找
        if not cog_node and partition.subject:
            cog_node = get_node(partition.subject, user_id)
        if not cog_node and partition.subject:
            cog_node = find_node_by_label(partition.subject, user_id)
        # 最后用分区名查找
        if not cog_node and partition.name:
            cog_node = find_node_by_label(partition.name, user_id)

        if cog_node:
            prof = cog_node.belief.proficiency_mean
            alpha = cog_node.belief.alpha
            beta_val = cog_node.belief.beta
            load = cog_node.cognitive_load.intrinsic
            streak = cog_node.engagement.streak_current
            xp = cog_node.engagement.xp
            direction = cog_node.trend.direction
            stagnation = cog_node.trend.stagnation_days
            cal_err = cog_node.metacognition.calibration_error

            # 掌握等级描述
            if prof >= 0.85:
                mastery_desc = "精通"
            elif prof >= 0.65:
                mastery_desc = "熟练"
            elif prof >= 0.4:
                mastery_desc = "学习中"
            elif prof >= 0.2:
                mastery_desc = "初学"
            else:
                mastery_desc = "未掌握"

            # 认知负荷描述
            if load >= 0.75:
                load_desc = "高负荷"
            elif load >= 0.45:
                load_desc = "适中"
            else:
                load_desc = "低负荷"

            # 趋势中文映射
            trend_map = {
                "ascending": "上升中 ↑",
                "descending": "下降中 ↓",
                "plateau": "平台期 →",
                "volatile": "波动中 ↕",
                "improving": "上升中 ↑",
                "stable": "稳定 →",
                "declining": "下降中 ↓",
                "stagnant": "停滞 →",
            }
            trend_desc = trend_map.get(direction, direction)

            # 元认知描述
            if cal_err > 0.3:
                cal_desc = "过度自信"
            elif cal_err < -0.3:
                cal_desc = "信心不足"
            else:
                cal_desc = "评估准确"

            lines = [
                f"\n\n[认知画像] {cog_node.label or partition.name}",
                f"  掌握度: {prof:.0%} ({mastery_desc})",
                f"  信念参数: α={alpha:.1f}, β={beta_val:.1f}",
                f"  趋势: {trend_desc}",
            ]
            if stagnation > 3:
                lines.append(f"  ⚠️ 已停滞 {stagnation:.0f} 天，需要关注")
            lines.append(f"  认知负荷: {load_desc} ({load:.0%})")
            lines.append(f"  元认知: {cal_desc}")
            if streak > 0:
                lines.append(f"  🔥 连续学习 {streak} 天 | XP: {xp:.0f}")

            # 错误模式
            if cog_node.error_clusters:
                top_errors = cog_node.error_clusters[:3]
                error_descs = [
                    f"{ec.cluster_id}({ec.count}次)" for ec in top_errors
                ]
                lines.append(f"  常见错误: {', '.join(error_descs)}")

            # 最近对话上下文
            if cog_node.dialogue_contexts:
                last_ctx = cog_node.dialogue_contexts[-1]
                if last_ctx.summary_text:
                    lines.append(
                        f"  上次讨论: {last_ctx.summary_text[:80]}"
                    )

            # 教学建议
            suggestions = []
            if prof < 0.4:
                suggestions.append("降低难度，多用具体例子")
            elif prof >= 0.85:
                suggestions.append("可适当拓展深度或交叉联系")
            if load >= 0.75:
                suggestions.append("认知负荷高，减少信息量，分步讲解")
            if stagnation > 5:
                suggestions.append("换角度或换题型突破平台期")
            if cal_err > 0.3:
                suggestions.append("学生过度自信，适当引入挑战性问题")
            elif cal_err < -0.3:
                suggestions.append("学生信心不足，多肯定进步")
            if suggestions:
                lines.append(f"  教学建议: {'; '.join(suggestions)}")

            system_content += "\n".join(lines)
    except Exception:
        logger.debug("CognitiveNode 上下文注入跳过", exc_info=True)

    # ── 8. Partition summary ──
    if partition.context_summary:
        system_content += f"\n\n当前分区：{partition.name}"
        system_content += f"\n分区摘要：{partition.context_summary}"

    # ── 9. Knowledge graph mastery overview ──
    try:
        if "data" not in dir():
            from app.services.storage import storage as _s3
            data = _s3.load(user_id)
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

    # ── 10. Tool availability hint ──
    try:
        from app.services.tool_executor import TOOL_DEFINITIONS

        tool_hints = []
        for tool_def in TOOL_DEFINITIONS:
            name = tool_def["function"]["name"]
            desc = tool_def["function"]["description"]
            tool_hints.append(f"  - {name}: {desc}")

        if tool_hints:
            system_content += (
                "\n\n🔧 你可以使用以下工具（在回复中自然地建议用户使用）:\n"
                + "\n".join(tool_hints)
                + "\n当用户需要视频讲解时，建议 search_media；"
                "当需要练习时，建议 generate_practice；"
                "当需要可视化时，建议 generate_image；"
                "当需要整理知识时，建议 generate_mindmap；"
                "当需要笔记时，建议 generate_document。"
            )
    except Exception:
        logger.debug("Tool availability hint injection skipped", exc_info=True)

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

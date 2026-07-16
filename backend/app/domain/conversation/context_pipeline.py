"""
ContextPipeline — 上下文构建管线

将 LLM 上下文构建从单一函数 _build_context_messages 深化为 Provider 管线。
按序执行 6 个 Provider，收集产出 → 合并为 system message → 追加历史 + 用户消息。

Provider 独立访问数据源，通过 previous_payloads 实现跨 Provider 引用。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Protocol

from app.schemas.conversation import (
    Conversation,
    TreeNode,
    TextBlock,
    ReasoningBlock,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════
# 数据模型
# ═══════════════════════════════════════════════


@dataclass
class ContextInput:
    """进入管线的原始输入"""
    user_id: str
    dir_id: str
    user_text: str
    conv_id: str = ""
    previous_payloads: dict[str, Any] = field(default_factory=dict)
    agent_label: str = ""  # kept for backward compat


@dataclass
class SystemChunk:
    """纯文本片段 — 将被拼接到 system message"""
    text: str


@dataclass
class ContextPayload:
    """结构化上下文 — key=data 供后续 Provider 引用，render 为 LLM 可见文本"""
    key: str
    data: dict
    render: str


ContextOutput = SystemChunk | ContextPayload


# ═══════════════════════════════════════════════
# Provider 协议
# ═══════════════════════════════════════════════


class ContextProvider(Protocol):
    """上下文提供者接口 — 返回 None 表示本 Provider 不产出内容"""

    async def build(self, input: ContextInput) -> ContextOutput | None: ...


# ═══════════════════════════════════════════════
# Pipeline
# ═══════════════════════════════════════════════


class ContextPipeline:
    """按序执行 Provider 列表，组装 LLM messages"""

    def __init__(self, providers: list[ContextProvider]) -> None:
        self._providers = providers

    async def assemble(self, input: ContextInput) -> list[dict[str, str]]:
        """
        1. 遍历 providers → 收集 outputs
        2. SystemChunk text 合并为一个 system message
        3. ContextPayload.render 追加到 system message
        4. 追加历史消息 + 用户消息
        返回 LLM 格式的 messages 列表
        """
        messages: list[dict[str, str]] = []
        system_parts: list[str] = []

        # 执行所有 Provider
        for provider in self._providers:
            try:
                output = await provider.build(input)
                if output is None:
                    continue
                if isinstance(output, SystemChunk):
                    system_parts.append(output.text)
                elif isinstance(output, ContextPayload):
                    system_parts.append(output.render)
                    input.previous_payloads[output.key] = output.data
            except Exception:
                logger.debug(
                    "Provider %s failed, skipping", type(provider).__name__,
                    exc_info=True,
                )

        # 组装 system message
        if system_parts:
            messages.append({
                "role": "system",
                "content": "\n\n".join(system_parts),
            })

        return messages


# ═══════════════════════════════════════════════
# Provider 1: ConversationMode — AI 对话模式人格
# ═══════════════════════════════════════════════

FEYNMAN_PROMPT = """你是一个刚开始学习这个知识点的学生。
你的角色要求：
1. 认真听对方讲解，像真实学生一样提出追问
2. 追问要层层递进——基本理解 → 联系已有 → 边界情况 → 应用
3. 当对方回答正确时，用追问确认他真的懂了
4. 当对方回答模糊时，指出矛盾点
5. 不要假装听不懂——诚实地根据讲解质量做回应
6. 对话结束时输出结构化评估（JSON格式）

## 评估输出格式
在对话结束时（用户多次无新问题或表示结束），你需要在回复末尾附加以下JSON:
```json
{
  "feynman_evaluation": {
    "highlights": ["亮点1", "亮点2"],
    "weaknesses": ["不足之处1"],
    "mastery_level": "high" | "medium" | "low",
    "summary": "总体评价一句话"
  }
}
```

## 行为准则
- 不要使用 <!--FOLLOW_UP--> 标注块
- 不要推荐工具（出题、视频、文档等）
- 不要主动引导去练习或看视频
- 保持学生角色，专注于理解和追问
- 追问语气自然，像课堂上的学生"""

PEER_PROMPT = ""  # P2 实现


class ConversationModeProvider:
    """根据对话 mode 注入对应人格 system prompt。

    mode 存储在 conversation (DirectoryNode) 的 metadata.mode 中。
    - "tutor" → 现有 TutorPersona 逻辑
    - "feynman" → 费曼学生角色
    - "peer" → 暂留空（P2）
    """

    def __init__(self) -> None:
        from app.infrastructure.llm.prompts import SYSTEM_PROMPT
        self._tutor_prompt = SYSTEM_PROMPT
        self._feynman_prompt = FEYNMAN_PROMPT

    def _resolve_mode(self, input: ContextInput) -> str:
        """从对话 metadata 解析 mode，默认 "tutor" """
        if not input.conv_id:
            return "tutor"
        try:
            from app.services.common import get_data_repo
            data = get_data_repo().load(input.user_id)
            conv = data.directory_nodes.get(input.conv_id)
            if conv and conv.node_type == "conv":
                return conv.metadata.get("mode", "tutor")
        except Exception:
            pass
        return "tutor"

    async def build(self, input: ContextInput) -> ContextOutput | None:
        mode = self._resolve_mode(input)
        if mode == "feynman":
            return SystemChunk(text=self._feynman_prompt)
        elif mode == "peer":
            # P2: return SystemChunk(text=PEER_PROMPT) when implemented
            return SystemChunk(text=self._tutor_prompt)
        else:
            return SystemChunk(text=self._tutor_prompt)


# ═══════════════════════════════════════════════
# Provider 2: ConversationLocation — 对话层级位置
# ═══════════════════════════════════════════════


class ConversationLocation:
    """注入对话的层级位置 + 分区摘要 (DirectoryNode 版本)"""

    async def build(self, input: ContextInput) -> ContextOutput | None:
        from app.services.common import get_data_repo

        data = get_data_repo().load(input.user_id)

        parts: list[str] = []
        location_data: dict[str, Any] = {
            "dir_id": input.dir_id,
        }

        # 获取 conv 节点
        conv_node = None
        if input.conv_id:
            conv_node = data.directory_nodes.get(input.conv_id)
            if conv_node and conv_node.node_type != "conv":
                conv_node = None

        # 从 DirectoryNode path 构建层级位置
        # path = ["root_id", "l1_id", ..., "this_conv_id"]
        if conv_node and conv_node.path:
            ancestor_ids = conv_node.path[:-1]  # 除自身外的所有祖先 dir ID

            # 遍历祖先目录节点收集名称
            hierarchy_dirs: list[tuple[str, str]] = []  # (id, display_name)
            for dir_id in ancestor_ids:
                dn = data.directory_nodes.get(dir_id)
                if dn and dn.node_type == "dir":
                    hierarchy_dirs.append((dn.id, dn.display_name))

            # hierarchy_dirs 从最外层（partition）到最内层（topic）
            if hierarchy_dirs:
                location_data["partition_name"] = hierarchy_dirs[0][1]
                # 如果有超过两层的路由，最内层祖先视为 topic，其上一级视为 domain
                if len(hierarchy_dirs) > 2:
                    location_data["domain_name"] = hierarchy_dirs[-2][1]
                    parts.append(f"领域：{hierarchy_dirs[-2][1]}")
                if len(hierarchy_dirs) > 1:
                    location_data["topic_name"] = hierarchy_dirs[-1][1]
                    parts.append(f"专题：{hierarchy_dirs[-1][1]}")

            location_data["conversation_name"] = conv_node.display_name
            location_data["conv_id"] = conv_node.id
            location_data["level"] = "PDTC"
        elif input.dir_id:
            pn = data.directory_nodes.get(input.dir_id)
            if pn and pn.node_type == "dir":
                location_data["partition_name"] = pn.display_name
                location_data["level"] = "PC"
            else:
                location_data["level"] = "root"
        else:
            location_data["level"] = "root"

        # 分区摘要（使用 dir 节点的 summary_short）
        partition_node = data.directory_nodes.get(input.dir_id)
        if partition_node and partition_node.node_type == "dir" and partition_node.summary_short:
            parts.append(f"分区摘要：{partition_node.summary_short}")

        # 首行渲染
        partition_name = partition_node.display_name if (partition_node and partition_node.node_type == "dir") else "默认分区"
        render = f"当前分区：{partition_name}"
        if parts:
            render += "\n" + "\n".join(parts)

        return ContextPayload(
            key="location",
            data=location_data,
            render=render,
        )


# ═══════════════════════════════════════════════
# Provider 3: SecretaryContext — 秘书注入的学习上下文
# ═══════════════════════════════════════════════


class SecretaryContext:
    """注入秘书系统推送的学习状态、计划与提案上下文。"""

    async def build(self, input: ContextInput) -> ContextOutput | None:
        from app.domain.conversation.context_hooks import get_injected_context

        ctx = get_injected_context(input.user_id, input.conv_id)
        if not ctx:
            return None

        parts: list[str] = []

        active_goals = ctx.get("active_goals", [])
        if active_goals:
            lines = [f"- {g.get('title', '')}" for g in active_goals if g.get("title")]
            if lines:
                parts.append("🎯 活跃目标:\n" + "\n".join(lines))

        due_items = ctx.get("due_plan_items", [])
        if due_items:
            lines = [f"- {i.get('title', '')}" for i in due_items if i.get("title")]
            if lines:
                parts.append("📋 今日待办:\n" + "\n".join(lines))

        pending_proposals = ctx.get("pending_proposals", [])
        if pending_proposals:
            lines = [f"- {p.get('title', '')}" for p in pending_proposals if p.get("title")]
            if lines:
                parts.append("💡 秘书建议:\n" + "\n".join(lines))

        suggested_topics = ctx.get("suggested_topics", [])
        if suggested_topics:
            parts.append("🔍 建议话题: " + ", ".join(suggested_topics))

        summary = ctx.get("recent_learning_summary", "")
        if summary:
            parts.append(f"📊 学习状态摘要: {summary}")

        style_hint = ctx.get("response_style_hint", "")
        if style_hint:
            parts.append(f"🎨 回复风格: {style_hint}")

        if ctx.get("should_avoid_proactive_suggestions"):
            parts.append("⚠️ 当前避免主动推销建议，先回应用户问题。")

        if not parts:
            return None

        return SystemChunk(
            text="## 秘书注入上下文\n\n" + "\n\n".join(parts),
        )


# ═══════════════════════════════════════════════
# Provider 4: LearnerEmotion — 情绪感知
# ═══════════════════════════════════════════════


class LearnerEmotion:
    """注入会话情绪上下文 + 即时情绪检测 + 策略建议"""

    async def build(self, input: ContextInput) -> ContextOutput | None:
        from app.services.analytics.emotion_analyzer import emotion_analyzer

        parts: list[str] = []
        emotion_data: dict[str, Any] = {}

        # 会话级情绪
        try:
            emotion_ctx = emotion_analyzer.build_emotion_context(input.user_id)
            if emotion_ctx:
                parts.append(emotion_ctx)
                emotion_data["session_emotion"] = emotion_ctx
        except Exception:
            logger.debug("会话情绪上下文注入跳过", exc_info=True)

        # 即时情绪检测
        try:
            quick_emotion = emotion_analyzer.quick_detect(input.user_text)
        except Exception:
            quick_emotion = None

        if quick_emotion:
            emotion_data["instant_emotion"] = quick_emotion
            severity = (
                "negative"
                if quick_emotion
                in ("frustration", "anxiety", "overwhelm", "boredom", "procrastination")
                else "neutral"
            )
            if severity == "negative":
                label_map = {
                    "frustration": "挫败",
                    "anxiety": "焦虑",
                    "overwhelm": "压力大",
                    "boredom": "无聊",
                    "procrastination": "拖延",
                }
                label_cn = label_map.get(quick_emotion, quick_emotion)
                strategy = (
                    f"\n\n⚠️ 学生当前表现出负面情绪（{label_cn}）。请优先共情和鼓励，"
                    "不要急于纠正或给建议。先肯定ta的努力，再温和地提供帮助。"
                    "语气要比平时更温暖、更有耐心。"
                )
                parts.append(strategy)
            elif quick_emotion == "motivated":
                parts.append("\n\n💪 学生充满动力，可以适当加难度，趁热打铁！")
            elif quick_emotion == "achievement":
                parts.append("\n\n🎉 学生取得了进展，请肯定ta的具体进步。")

        if not parts:
            return None

        return ContextPayload(
            key="emotion",
            data=emotion_data,
            render="\n".join(parts),
        )


# ═══════════════════════════════════════════════
# Provider 4: LearnerCognition — 认知画像
# ═══════════════════════════════════════════════


class LearnerCognition:
    """注入知识状态 + BKT 信念 + 认知画像 + 知识点掌握分布"""

    async def build(self, input: ContextInput) -> ContextOutput | None:
        from app.services.common import get_data_repo

        parts: list[str] = []
        cognition_data: dict[str, Any] = {}

        # 全局知识状态
        try:
            from app.domain.knowledge import get_knowledge_query
            knowledge_ctx = get_knowledge_query().get_knowledge_context(input.user_id)
            if knowledge_ctx:
                parts.append(knowledge_ctx)
                cognition_data["knowledge_context"] = knowledge_ctx
        except Exception:
            logger.debug("知识状态上下文注入跳过", exc_info=True)

        # CognitiveNode 认知画像
        try:
            from app.domain.cognitive import get_repo

            data = get_data_repo().load(input.user_id)
            partition = data.directory_nodes.get(input.dir_id)

            cog_node = None
            if partition and partition.node_type == "dir":
                if partition.id:
                    cog_node = get_repo().get_node(partition.id, input.user_id)
                if not cog_node and partition.name:
                    cog_node = get_repo().find_node_by_label(partition.name, input.user_id)

            if cog_node:
                from app.domain.cognitive import extract_mastery_atom

                atom = extract_mastery_atom(cog_node)
                prof = atom.proficiency_mean
                alpha = cog_node.belief.alpha
                beta_val = cog_node.belief.beta
                load = cog_node.cognitive_load.intrinsic
                streak = cog_node.engagement.streak_current
                xp = cog_node.engagement.xp
                direction = cog_node.trend.direction
                stagnation = cog_node.trend.stagnation_days
                cal_err = cog_node.metacognition.calibration_error

                # 掌握等级描述
                mastery_desc = atom.mastery_level

                # 认知负荷描述
                if load >= 0.75:
                    load_desc = "高负荷"
                elif load >= 0.45:
                    load_desc = "适中"
                else:
                    load_desc = "低负荷"

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

                if cal_err > 0.3:
                    cal_desc = "过度自信"
                elif cal_err < -0.3:
                    cal_desc = "信心不足"
                else:
                    cal_desc = "评估准确"

                node_label = atom.label or (partition.name if partition else "")
                lines = [
                    f"\n\n[认知画像] {node_label}",
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

                if cog_node.error_clusters:
                    top_errors = cog_node.error_clusters[:3]
                    error_descs = [
                        f"{ec.cluster_id}({ec.count}次)" for ec in top_errors
                    ]
                    lines.append(f"  常见错误: {', '.join(error_descs)}")

                if cog_node.dialogue_contexts:
                    last_ctx = cog_node.dialogue_contexts[-1]
                    if last_ctx.summary_text:
                        lines.append(f"  上次讨论: {last_ctx.summary_text[:80]}")

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

                parts.append("\n".join(lines))

                cognition_data["cognitive_profile"] = {
                    "proficiency": prof,
                    "mastery_desc": mastery_desc,
                    "alpha": alpha,
                    "beta": beta_val,
                    "trend": direction,
                    "trend_desc": trend_desc,
                    "cognitive_load": load,
                    "calibration_error": cal_err,
                    "streak": streak,
                    "stagnation_days": stagnation,
                }
        except Exception:
            logger.debug("CognitiveNode 上下文注入跳过", exc_info=True)

        # 知识图谱掌握概览
        try:
            data = get_data_repo().load(input.user_id)
            graph = data.knowledge_graphs.get(input.dir_id)
            if graph and graph.nodes:
                nodes_list = list(graph.nodes.values())
                mastered = [n.label for n in nodes_list if n.mastery >= 80]
                weak = [n.label for n in nodes_list if 10 <= n.mastery < 50]
                untouched = [n.label for n in nodes_list if n.mastery == 0]

                kg_lines = [f"\n\n📊 知识图谱 ({len(nodes_list)}个知识点):"]
                if mastered:
                    kg_lines.append(f"   ✅ 已掌握: {', '.join(mastered[:5])}")
                if weak:
                    kg_lines.append(f"   🔶 薄弱: {', '.join(weak[:5])}")
                if untouched:
                    kg_lines.append(f"   ⬜ 未接触: {', '.join(untouched[:3])}")

                ready_to_learn = [
                    n for n in nodes_list if n.mastery == 0 and n.priority >= 5
                ]
                if ready_to_learn:
                    next_up = sorted(ready_to_learn, key=lambda n: -n.priority)[:3]
                    kg_lines.append(f"   🎯 建议下一步: {', '.join(n.label for n in next_up)}")

                all_labels = [n.label for n in nodes_list[:15]]
                kg_lines.append(f"\n可引用的知识点: {', '.join(all_labels)}")
                kg_lines.append("回答涉及这些知识点时，在末尾标注 [来源: 知识点名称]。")

                parts.append("\n".join(kg_lines))
                cognition_data["knowledge_graph"] = {
                    "total": len(nodes_list),
                    "mastered": mastered[:5],
                    "weak": weak[:5],
                    "untouched": untouched[:3],
                }
        except Exception:
            logger.debug("知识图谱概览注入跳过", exc_info=True)

        if not parts:
            return None

        return ContextPayload(
            key="cognition",
            data=cognition_data,
            render="\n".join(parts),
        )


# ═══════════════════════════════════════════════
# Provider 5: LearningActivity — 练习上下文
# ═══════════════════════════════════════════════


class LearningActivity:
    """注入练习上下文 + 练习回顾 + 选题建议"""

    async def build(self, input: ContextInput) -> ContextOutput | None:
        from app.services.common import get_data_repo

        parts: list[str] = []
        activity_data: dict[str, Any] = {}

        # 练习上下文
        try:
            from app.services.practice.practice_integrator import inject_practice_context
            practice_ctx = inject_practice_context(input.user_id, input.dir_id)
            if practice_ctx:
                parts.append(practice_ctx)
                activity_data["practice_context"] = practice_ctx
        except Exception:
            logger.debug("练习上下文注入跳过", exc_info=True)

        # 练习回顾
        try:
            from app.services.practice.practice_recall import practice_recall
            if practice_recall.is_recall_query(input.user_text):
                from shared.state import active_practice_sessions
                recall_sessions = list(active_practice_sessions.values())
                if recall_sessions:
                    data = get_data_repo().load(input.user_id)
                    partition = data.directory_nodes.get(input.dir_id)
                    subject = partition.name if partition and partition.node_type == "dir" else ""
                    recall_text = practice_recall.generate_recall(
                        sessions=recall_sessions,
                        days=7,
                        subject_filter=subject,
                    )
                    recall_block = (
                        f"\n\n[练习回顾]\n{recall_text}\n\n"
                        "请在回复中自然地引用这些练习数据来回答用户。"
                    )
                    parts.append(recall_block)
                    activity_data["practice_recall"] = recall_text
        except Exception:
            logger.debug("练习回顾注入跳过", exc_info=True)

        # 选题建议
        try:
            from app.services.conversation.context_trigger import context_trigger
            data = get_data_repo().load(input.user_id)
            conversation = data.directory_nodes.get(input.conv_id) if input.conv_id else None
            if conversation and conversation.node_type == "conv":
                recent_msgs = []
                for nid in conversation.path[-5:]:
                    node = data.nodes.get(nid)
                    if node and not node.is_deleted:
                        recent_msgs.append(node)
                ctx = context_trigger.trigger(
                    user_id=input.user_id,
                    conversation=conversation,
                    recent_messages=recent_msgs,
                )
                suggestion = (
                    f"\n\n[选题建议] 当前对话主题涉及: {ctx['skill_ids']}, "
                    f"Bloom: {ctx['bloom_level']}, 推荐难度: {ctx['difficulty']:.2f}"
                )
                if ctx.get("confused"):
                    suggestion += ", ⚠️ 检测到困惑信号"
                if any(s for s in ctx.get("skill_ids", []) if s != "general_practice"):
                    suggestion += (
                        "\n[Media] 如果用户需要视频讲解，"
                        "推荐生成多平台搜索链接(B站/YouTube/知乎)"
                    )
                parts.append(suggestion)
                activity_data["practice_suggestion"] = ctx
        except Exception:
            logger.debug("选题建议上下文注入跳过", exc_info=True)

        if not parts:
            return None

        return ContextPayload(
            key="activity",
            data=activity_data,
            render="\n".join(parts),
        )


# ═══════════════════════════════════════════════
# Provider 6: TutorCapability — 工具 + RAG + 题库
# ═══════════════════════════════════════════════


class TutorCapability:
    """注入可用工具 + RAG 资料 + 题库上下文"""

    async def build(self, input: ContextInput) -> ContextOutput | None:
        parts: list[str] = []
        capability_data: dict[str, Any] = {}

        # 工具可用性提示
        try:
            from app.infrastructure.llm.tool_repository import TOOL_DEFINITIONS
            tool_hints = []
            for tool_def in TOOL_DEFINITIONS:
                name = tool_def["function"]["name"]
                desc = tool_def["function"]["description"]
                tool_hints.append(f"  - {name}: {desc}")
            if tool_hints:
                tool_text = (
                    "\n\n🔧 你可以使用以下工具（在回复中自然地建议用户使用）:\n"
                    + "\n".join(tool_hints)
                    + "\n当用户需要视频讲解时，建议 search_media；"
                    "当需要练习时，建议 generate_practice；"
                    "当需要可视化时，建议 generate_image；"
                    "当需要整理知识时，建议 generate_mindmap；"
                    "当需要笔记时，建议 generate_document；"
                    "当需要向学生提问时，使用 ask_question（选择题或开放题）。"
                )
                parts.append(tool_text)
                capability_data["tools"] = [t["function"]["name"] for t in TOOL_DEFINITIONS]
        except Exception:
            logger.debug("工具可用性提示注入跳过", exc_info=True)

        # 题库上下文
        try:
            from app.services.practice.practice_question_bank import list_banks
            banks = list_banks(input.user_id)
            if banks:
                bank_lines = ["\n\n📚 已有题库:"]
                for b in banks[:8]:
                    name = b.get("name", "未命名")
                    qc = b.get("real_count") or b.get("question_count", 0)
                    bid = b.get("id", "")[:12]
                    bank_lines.append(f"  - {name} ({qc}道题, ID: {bid})")
                bank_lines.append(
                    "用户问练习题时，可先调用 query_question_banks 查看现有题库，再决定出题方式。"
                )
                parts.append("\n".join(bank_lines))
                capability_data["question_banks"] = [b.get("name") for b in banks[:8]]
        except Exception:
            logger.debug("题库上下文注入跳过", exc_info=True)

        # RAG 资料
        try:
            from app.infrastructure.files.search import material_search
            from app.services.common import get_data_repo
            data = get_data_repo().load(input.user_id)
            rag_results = material_search.search_sync(
                user_id=data.user_id,
                query=input.user_text,
                top_k=3,
            )
            if rag_results and material_search.should_inject_rag(rag_results):
                rag_ctx = material_search.format_rag_context(rag_results)
                rag_text = (
                    "\n\n📚 以下是你可引用的资料内容（来自用户的知识库）：\n"
                    + rag_ctx
                    + "\n\n请基于以上资料回答。如果资料中没有相关信息，按自己的知识回答，不要编造。"
                    "引用资料时标注 [来源：文件名]。"
                )
                parts.append(rag_text)
                capability_data["rag_injected"] = True
        except Exception:
            logger.debug("RAG 资料注入跳过", exc_info=True)

        if not parts:
            return None

        return ContextPayload(
            key="capability",
            data=capability_data,
            render="\n".join(parts),
        )


# ═══════════════════════════════════════════════
# 工厂函数
# ═══════════════════════════════════════════════

_context_pipeline: ContextPipeline | None = None


def get_context_pipeline() -> ContextPipeline:
    global _context_pipeline
    if _context_pipeline is None:
        from app.domain.conversation.providers.session_mission_provider import (
            SessionMissionProvider,
        )
        _context_pipeline = ContextPipeline([
            ConversationModeProvider(),
            ConversationLocation(),
            SessionMissionProvider(),  # LI-04: Mission 上下文注入
            SecretaryContext(),
            LearnerEmotion(),
            LearnerCognition(),
            LearningActivity(),
            TutorCapability(),
        ])
    return _context_pipeline


async def build_llm_messages(
    partition: Any,
    conversation: Any,
    recent_messages: list[Any],
    user_text: str,
    user_id: str = "",
    agent_label: str = "",
    tool_result: Any = None,
) -> list[dict[str, str]]:
    """
    兼容旧 _build_context_messages 签名的新管道调用。
    内部调用 ContextPipeline.assemble() 构建 system message，
    然后追加历史消息和用户消息。

    tool_result: 保留参数以兼容旧调用方，方案A中不再使用此路径注入 tool result。
    """
    pipeline = get_context_pipeline()

    input = ContextInput(
        user_id=user_id,
        dir_id=partition.id if partition else "",
        user_text=user_text,
        conv_id=conversation.id if conversation else "",
        agent_label=agent_label,
    )
    messages = await pipeline.assemble(input)

    # 追加最近历史消息
    for msg in recent_messages[-8:]:
        if msg.is_deleted:
            continue
        text_parts = []
        reasoning_parts: list[str] = []
        for block in msg.content_blocks:
            if isinstance(block, dict):
                btype = block.get("type")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "reasoning":
                    t = block.get("text", "")
                    if t:
                        reasoning_parts.append(t)
            elif isinstance(block, TextBlock):
                text_parts.append(block.text)
            elif isinstance(block, ReasoningBlock) and block.text:
                reasoning_parts.append(block.text)
            elif hasattr(block, "text") and not isinstance(block, (TextBlock, ReasoningBlock)):
                text_parts.append(block.text)
        content = "\n".join(text_parts) if text_parts else ""
        if not content.strip():
            # assistant 消息仅含 reasoning（推理模型溢出）时也要回传
            if msg.role != "assistant" or not reasoning_parts:
                continue
        # deepseek 思考模式：assistant 消息若有 reasoning_content 必须传回 API
        reasoning_content = "\n".join(reasoning_parts) if reasoning_parts else None
        msg_dict: dict = {
            "role": msg.role,
            "content": content or None,
        }
        if reasoning_content and msg.role == "assistant":
            msg_dict["reasoning_content"] = reasoning_content
        messages.append(msg_dict)

    # 追加当前用户消息
    messages.append({"role": "user", "content": user_text})

    return messages
"""
对话系统 LLM 服务
基于树结构构建上下文，调用 LLM 生成回复
支持多模态响应块（ResponseBlock）集成
"""

from __future__ import annotations

import logging
import re
from typing import AsyncGenerator

from app.schemas.conversation import (
    ContentBlock,
    TextBlock,
    TreeNode,
    Partition,
    Branch,
    ResponseBlock,
)
from app.services.llm_service import llm_service
from app.services.storage import storage
from app.services.tree_ops import tree_ops
from app.services.tool_executor import tool_executor, predict_tools, SLOW_TOOLS

logger = logging.getLogger(__name__)


# P0: Post-message hooks (meta history + branch auto-rename)
def _p0_post_message_hooks(user_id: str, partition_id: str, node: TreeNode) -> None:
    """消息存储后的P0钩子：异步写元历史 + 触发分支命名/摘要"""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            from app.services.meta_history import write_to_meta_history
            loop.create_task(write_to_meta_history(user_id, node))

            data = storage.load(user_id)
            branch = data.branches.get(node.branch_id) if node.branch_id else None
            if branch:
                msg_count = len(branch.path)
                from app.services.branch_summarizer import (
                    try_auto_rename_branch, generate_branch_summary, update_partition_context,
                )

                async def _do_rename():
                    new_name = await try_auto_rename_branch(user_id, node.branch_id, msg_count)
                    if new_name:
                        _data = storage.load(user_id)
                        _branch = _data.branches.get(node.branch_id)
                        if _branch:
                            _branch.name = new_name
                            storage.save(user_id, _data)

                loop.create_task(_do_rename())

                if msg_count >= 10 and msg_count % 10 == 0:
                    generate_branch_summary(user_id, node.branch_id)
                if msg_count % 5 == 0:
                    update_partition_context(user_id, partition_id)
    except Exception:
        logger.debug("P0 hooks skipped")

# ── System Prompt ──

SYSTEM_PROMPT = """你是「苹小果」，一个温暖的智能伴学助手。你像一位耐心的学长/学姐，陪伴学生度过学习中的每一个时刻。

## 人格特质
- **温暖陪伴**：用亲切自然的语气交流，像朋友一样。适当使用 emoji 传递温度 🌱
- **情绪感知**：如果学生表现出挫败、焦虑或疲惫，先共情安慰，再给建议。不说"别紧张"这类否定情绪的话，而是"这确实不容易，你已经很努力了"
- **真诚鼓励**：表扬具体行为（"这道题的思路很清晰"），不空洞夸赞
- **耐心启发**：对于概念性问题，先反问引导学生自己思考，再给出答案。如"你觉得这个现象背后的原因可能是什么？"
- **适度幽默**：在合适的时候可以轻松一下，但不过度

## 回答规范
- 用通俗易懂的语言解释概念，避免堆砌术语
- **数学公式**：使用 LaTeX 格式（$...$ 行内，$$...$$ 块级），所有数学符号都用 LaTeX，不用 Unicode 近似
- **代码块**：涉及代码或算法时，必须使用 \`\`\`语言名 包裹。例如：
  \`\`\`python
  def binary_search(arr, target):
      left, right = 0, len(arr) - 1
      while left <= right:
          mid = (left + right) // 2
          if arr[mid] == target:
              return mid
          elif arr[mid] < target:
              left = mid + 1
          else:
              right = mid - 1
      return -1
  \`\`\`
  不要输出裸代码（不带 \`\`\` 包裹），不要用中文标点代替英文标点
- 回复简洁但完整，每次控制在合理长度
- **引用溯源**：如果回答涉及具体知识点，在末尾用 [来源: 知识点名称] 标注。如 [来源: 导数与微分] [来源: 牛顿第二定律]
- 涉及多个知识点时，分别标注

## 场景策略
- **学生提问概念**："为什么XXX？" → 先反问引导思考 → 再解释核心原理 → 举例说明
- **学生做错题**：先理解错因 → 针对性解释 → 鼓励重试 → 标注相关知识点
- **学生说累/难**：先共情 → 简短建议（休息/换个方式）→ 不强行推学习
- **学生求鼓励**：回顾其进步 → 具体肯定 → 设定小目标

## 启发式追问规则（苏格拉底教学法）
当学生提问概念性、方法性或原理性问题时，不要直接给答案。按以下规则：

### 触发条件
1. 概念定义类：「什么是X？」「X的定义？」→ 反问相关前置概念
2. 方法步骤类：「怎么做？」「如何推导？」→ 反问「你试过哪些思路？」
3. 原理原因类：「为什么X成立？」「为什么这样算？」→ 反问「你猜测可能是什么原因？」

### 追问示例
- 学生：「什么是导数？」
  → 你：「好问题！在回答之前，你能先说说'瞬时变化率'是什么意思吗？不用担心说错～」
- 学生：「怎么求极限？」
  → 你：「你先试试看？你目前想到的方法是什么？」

### 追问后
- 学生回答后：先肯定（「很好！你已经抓住了关键」），再基于其回答水平调整讲解深度
- 学生说不知道：给提示（「可以从这个角度想……」），再逐步讲解
- 追问不超过 1 轮——如果学生第二次仍说不知道，直接给出完整解释

### 例外（不追问，直接回答）
- 学生明确说「直接告诉我」「快说答案」「别反问」
- 纯计算题（「求 f(x)=x^2 的导数」）
- 学生连续问了 3+ 个独立问题（避免节奏过慢）
- 学生情绪明显挫败或急躁（先安慰，再回答）

## 主动引导
- **概念讲解后**：自然地邀请学生做练习巩固。如"要不要来两道题试试？💪"
- **学生表示理解时**：建议搜索相关视频加深印象。如"需要我帮你搜一下B站上这个知识点的讲解视频吗？"
- **学生卡住时**：推荐换个学习方式。如"要不要先看个视频换个角度理解？"
- **学生复习整理时**：可以生成思维导图或学习笔记。如"我帮你整理成思维导图吧？📋"
- **不要每个回复都推荐**，只在合适时机自然提起

## 可用功能（你可以主动提供）
你能帮助学生做以下事情，请在合适的时机自然地提供：
- **📝 生成练习题**：针对当前知识点出题，支持基础和进阶难度
- **🔍 搜索视频讲解**：在B站、YouTube、知乎等平台搜索教程
- **🧠 生成思维导图**：整理知识结构，可视化学习内容
- **📄 生成学习笔记**：输出 Markdown、PDF 等格式的复习文档
- **🖼️ 生成示意图**：函数图像、概念图、流程图等
学生不需要知道这些功能的名字，你只需像朋友一样说"我帮你搜个视频？"或"要不要做两道题？"

## 数学公式
- **行内公式**使用 $...$，如 $f(x) = x^2$
- **块级公式**使用 $$...$$，单独成行，如 $$\\int_0^1 x^2 dx = \\frac{1}{3}$$
- 所有数学符号都用 LaTeX 写，不用 Unicode 近似

## 安全边界
- 不替代专业心理咨询，如果学生表现出严重心理问题，建议寻求专业帮助
- 不提供考试作弊、论文代写等违规帮助
- 涉及医学、法律等专业领域时，声明建议仅供参考"""

# ── 情绪分析（多维分类，替代旧关键词匹配）──

from app.services.emotion_analyzer import emotion_analyzer

# 向后兼容的快捷函数
def detect_frustration(text: str) -> bool:
    """检测用户消息是否包含挫败信号（兼容旧接口）"""
    result = emotion_analyzer.quick_detect(text)
    return result == "frustration"


# ── 引用溯源解析 ──

SOURCE_PATTERN = re.compile(r'\[来源:\s*([^\]]+)\]')

def parse_sources(text: str) -> tuple[str, list[str]]:
    """从回复文本中提取 [来源: xxx] 标记，返回 (清理后文本, 来源列表)"""
    sources = SOURCE_PATTERN.findall(text)
    cleaned = SOURCE_PATTERN.sub('', text).strip()
    # 清理多余空行
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    return cleaned, sources


def _build_context_messages(
    partition: Partition,
    branch: Branch,
    recent_messages: list[TreeNode],
    user_text: str,
    user_id: str = "",
) -> list[dict[str, str]]:
    """
    构建发给 LLM 的消息列表。
    使用紧凑格式节省 token。
    """
    messages: list[dict[str, str]] = []

    # 系统提示
    system_content = SYSTEM_PROMPT

    # P0: 多维情绪感知 → 注入情绪上下文
    emotion_ctx = emotion_analyzer.build_emotion_context(user_id)
    if emotion_ctx:
        system_content += emotion_ctx

    # P0: 统一知识状态 → 注入 LLM 上下文
    try:
        from app.services.knowledge_bridge import knowledge_bridge
        knowledge_ctx = knowledge_bridge.get_knowledge_context()
        if knowledge_ctx:
            system_content += f"\n\n{knowledge_ctx}"
    except Exception:
        pass

    # P0: 当前消息情绪检测 → 注入即时策略
    quick_emotion = emotion_analyzer.quick_detect(user_text)
    if quick_emotion:
        severity = "negative" if quick_emotion in ("frustration", "anxiety", "overwhelm", "boredom", "procrastination") else "neutral"
        if severity == "negative":
            strategy = (
                "\n\n⚠️ 学生当前表现出负面情绪（{label}）。请优先共情和鼓励，"
                "不要急于纠正或给建议。先肯定ta的努力，再温和地提供帮助。"
                "语气要比平时更温暖、更有耐心。"
            ).format(label={"frustration": "挫败", "anxiety": "焦虑", "overwhelm": "压力大", "boredom": "无聊", "procrastination": "拖延"}.get(quick_emotion, quick_emotion))
            system_content += strategy
        elif quick_emotion == "motivated":
            system_content += "\n\n💪 学生充满动力，可以适当加难度，趁热打铁！"
        elif quick_emotion == "achievement":
            system_content += "\n\n🎉 学生取得了进展，请肯定ta的具体进步。"

    # P0: 最近对话挫败模式检测

    # P1: 注入练习上下文
    try:
        from app.services.practice_integrator import inject_practice_context
        practice_ctx = inject_practice_context(user_id, partition.id)
        if practice_ctx:
            system_content += f"\n\n{practice_ctx}"
    except Exception:
        pass

    # P2: 检测练习回顾查询，注入回顾数据
    try:
        from app.services.practice_recall import practice_recall
        if practice_recall.is_recall_query(user_text):
            from app.services.storage import storage as _storage
            from app.api.practice import _sessions as _p_sessions
            recall_sessions = list(_p_sessions.values())
            if recall_sessions:
                recall_text = practice_recall.generate_recall(
                    sessions=recall_sessions,
                    days=7,
                    subject_filter=partition.subject or "",
                )
                system_content += f"\n\n[练习回顾]\n{recall_text}\n\n请在回复中自然地引用这些练习数据来回答用户。"
    except Exception:
        pass

    # P2: 上下文感知练习选题建议
    try:
        from app.services.context_trigger import context_trigger
        from app.services.storage import storage as _storage2
        data = _storage2.load(user_id)
        if branch:
            recent_msgs = []
            for nid in branch.path[-5:]:
                node = data.nodes.get(nid)
                if node and not node.is_deleted:
                    recent_msgs.append(node)
            ctx = context_trigger.trigger(
                user_id=user_id,
                branch=branch,
                recent_messages=recent_msgs,
            )
            system_content += f"\n\n[选题建议] 当前对话主题涉及: {ctx['skill_ids']}, Bloom: {ctx['bloom_level']}, 推荐难度: {ctx['difficulty']:.2f}"
            if ctx.get('confused'):
                system_content += ", ⚠️ 检测到困惑信号"
            # 推荐多平台视频搜索
            if any(s for s in ctx.get('skill_ids', []) if s != 'general_practice'):
                system_content += "\n[Media] 如果用户需要视频讲解，推荐生成多平台搜索链接(B站/YouTube/知乎)"
    except Exception:
        pass

    # 添加分区上下文
    if partition.context_summary:
        system_content += f"\n\n当前分区：{partition.name}"
        system_content += f"\n分区摘要：{partition.context_summary}"

    # 注入可用知识点（供引用溯源）
    try:
        from domain.knowledge.prerequisites import ALL_PREREQUISITES, SKILL_TO_SUBJECT
        subject = partition.subject or ""
        relevant_skills = []
        if subject and subject in SKILL_TO_SUBJECT:
            relevant_skills = SKILL_TO_SUBJECT[subject][:15]
        else:
            relevant_skills = list(ALL_PREREQUISITES.keys())[:15]
        if relevant_skills:
            system_content += f"\n\n可引用的知识点: {', '.join(relevant_skills)}\n回答涉及这些知识点时，在末尾标注 [来源: 知识点名称]。"
    except Exception:
        pass

    messages.append({"role": "system", "content": system_content})

    # 添加历史消息（最多最近8条）
    for msg in recent_messages[-8:]:
        if msg.is_deleted:
            continue
        # 提取文本内容
        text_parts = []
        for block in msg.content_blocks:
            if isinstance(block, TextBlock):
                text_parts.append(block.text)
            elif hasattr(block, "text"):
                text_parts.append(block.text)
        text = " ".join(text_parts) if text_parts else "[媒体内容]"

        # 截断过长的消息
        if len(text) > 500:
            text = text[:500] + "..."

        role = msg.role if msg.role in ("user", "assistant") else "assistant"
        messages.append({"role": role, "content": text})

    # 添加当前用户消息
    messages.append({"role": "user", "content": user_text})

    return messages


async def generate_reply(
    user_id: str,
    partition_id: str,
    user_text: str,
) -> str:
    """
    生成助手回复（非流式）。
    1. 加载分区上下文
    2. 构建消息列表
    3. 调用 LLM
    4. 返回完整回复
    """
    data = storage.load(user_id)
    partition = data.partitions.get(partition_id)
    if not partition:
        raise ValueError(f"Partition {partition_id} not found")

    branch = data.branches.get(partition.active_branch_id)
    if not branch:
        raise ValueError(f"Active branch not found")

    # 获取最近消息
    recent_messages = []
    for nid in branch.path[-8:]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted:
            recent_messages.append(node)

    # 构建上下文
    llm_messages = _build_context_messages(partition, branch, recent_messages, user_text, user_id)

    # 调用 LLM
    reply = await llm_service.generate(
        messages=llm_messages,
        task_type="chat",
        temperature=0.7,
        max_tokens=2048,
    )

    return reply


# ── 工具调用辅助函数 ──

def _build_tool_params(tool_name: str, user_text: str, partition) -> dict:
    """根据工具类型从用户输入构建参数"""
    subject = getattr(partition, "subject", "") or "通用"
    if tool_name == "search_media":
        return {"query": user_text, "platforms": ["bilibili", "zhihu", "youtube"]}
    elif tool_name == "generate_practice":
        return {
            "subject": subject,
            "knowledge_point": user_text[:80],
            "difficulty": "进阶",
            "count": 2,
        }
    elif tool_name == "generate_image":
        return {"prompt": user_text}
    elif tool_name == "generate_mindmap":
        return {"topic": user_text, "depth": 3}
    elif tool_name == "generate_document":
        return {"topic": user_text, "format": "markdown"}
    return {"query": user_text}


def _summarize_tool_result(tool_name: str, block: ResponseBlock) -> str:
    """提取工具结果中的关键信息，供 LLM 引用"""
    content = block.content or {}
    if tool_name == "search_media":
        platforms = content.get("platforms", [])
        links_count = sum(len(p.get("links", [])) for p in platforms)
        names = [p.get("name", "") for p in platforms[:3]]
        return f"搜索到{links_count}个视频链接（{', '.join(names)}）"
    elif tool_name == "generate_practice":
        questions = content.get("questions", [])
        return f"生成{len(questions)}道练习题"
    elif tool_name == "generate_image":
        return "已生成图片"
    elif tool_name == "generate_mindmap":
        return "已生成思维导图"
    elif tool_name == "generate_document":
        return "已生成文档"
    return f"工具{tool_name}执行完成"


def _build_tool_context(tool_results: list[dict]) -> str:
    """构建注入 LLM 的工具结果上下文"""
    lines = ["[工具执行结果] 以下内容已展示给学生，请在回复中自然地引用："]
    for r in tool_results:
        if "error" in r:
            lines.append(f"- {r['tool']}: 执行失败 ({r['error']})")
        else:
            lines.append(f"- {r['tool']}: {r['summary']}")
    lines.append("\n请在回复中引导学生查看上面的卡片/结果。如果是练习题，鼓励学生作答。")
    return "\n".join(lines)


async def generate_reply_with_tools(
    user_id: str,
    partition_id: str,
    user_text: str,
) -> list[ResponseBlock]:
    """
    生成助手回复，集成工具调用。
    返回 ResponseBlock 列表：第一个是文本回复，后续是工具结果块。
    """
    data = storage.load(user_id)
    partition = data.partitions.get(partition_id)
    if not partition:
        raise ValueError(f"Partition {partition_id} not found")

    branch = data.branches.get(partition.active_branch_id)
    if not branch:
        raise ValueError(f"Active branch not found")

    # 获取最近消息
    recent_messages = []
    for nid in branch.path[-8:]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted:
            recent_messages.append(node)

    # 意图预判（含上下文感知：AI建议→用户同意）
    last_ai_text = ""
    for msg in reversed(recent_messages):
        if msg.role == "assistant":
            last_ai_text = msg.text_summary or ""
            break
    detected_tools = predict_tools(user_text, last_ai_text)
    logger.info("Detected tools: %s for text: %s", detected_tools, user_text[:50])

    # 构建上下文
    llm_messages = _build_context_messages(partition, branch, recent_messages, user_text, user_id)

    response_blocks: list[ResponseBlock] = []
    order = 0

    if detected_tools:
        # 🔧 修复：先执行工具 → 注入结果 → LLM统一回复
        tool_results: list[dict] = []
        for tool_name in detected_tools:
            try:
                # 构建工具参数
                params = _build_tool_params(tool_name, user_text, partition)
                tool_block = await tool_executor.execute(tool_name, params)
                tool_block.order = order
                response_blocks.append(tool_block)
                order += 1
                
                # 提取有用信息注入LLM上下文
                tool_results.append({
                    "tool": tool_name,
                    "summary": _summarize_tool_result(tool_name, tool_block),
                })
                
                # 慢任务：提交后台作业
                if tool_name in SLOW_TOOLS:
                    from app.services.background_jobs import job_manager
                    job = await job_manager.submit(
                        user_id=user_id,
                        tool_name=tool_name,
                        params=params,
                        block_id=tool_block.id,
                        partition_id=partition_id,
                        branch_id=branch.id if branch else "",
                    )
                    data.response_blocks[tool_block.id] = tool_block
                    storage.save(user_id, data)
            except Exception as e:
                logger.error(f"Tool {tool_name} failed: {e}")
                tool_results.append({"tool": tool_name, "error": str(e)})
        
        # 将工具结果注入 LLM 上下文
        if tool_results:
            tool_context = _build_tool_context(tool_results)
            llm_messages.append({"role": "system", "content": tool_context})
        
        # 调用 LLM 生成最终回复（含工具结果引用）
        try:
            reply = await llm_service.generate(
                messages=llm_messages,
                task_type="chat",
                temperature=0.7,
                max_tokens=2048,
            )
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            reply = "我帮你准备了一些学习资料，请看上面的卡片 👆"

        # 创建文本 ResponseBlock
        cleaned_text, sources = parse_sources(reply)
        text_block = ResponseBlock(
            type="text",
            status="ready",
            content={"text": cleaned_text},
            sources=sources,
            order=0,  # 文本放最前面
        )
        # 插入到开头
        response_blocks.insert(0, text_block)
        # 重新编号
        for i, b in enumerate(response_blocks):
            b.order = i
    else:
        # 无工具调用，纯文本回复
        try:
            reply = await llm_service.generate(
                messages=llm_messages,
                task_type="chat",
                temperature=0.7,
                max_tokens=2048,
            )
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            reply = "抱歉，生成回复时遇到了问题。"

        cleaned_text, sources = parse_sources(reply)
        text_block = ResponseBlock(
            type="text",
            status="ready",
            content={"text": cleaned_text},
            sources=sources,
            order=0,
        )
        response_blocks.append(text_block)

    # 存储所有 ResponseBlocks
    data = storage.load(user_id)
    for block in response_blocks:
        data.response_blocks[block.id] = block
    storage.save(user_id, data)

    return response_blocks


async def generate_reply_stream(
    user_id: str,
    partition_id: str,
    user_text: str,
) -> AsyncGenerator[str, None]:
    """
    生成助手回复（流式）。
    逐 token 产出回复文本。
    """
    data = storage.load(user_id)
    partition = data.partitions.get(partition_id)
    if not partition:
        raise ValueError(f"Partition {partition_id} not found")

    branch = data.branches.get(partition.active_branch_id)
    if not branch:
        raise ValueError(f"Active branch not found")

    # 获取最近消息
    recent_messages = []
    for nid in branch.path[-8:]:
        node = data.nodes.get(nid)
        if node and not node.is_deleted:
            recent_messages.append(node)

    # 构建上下文
    llm_messages = _build_context_messages(partition, branch, recent_messages, user_text, user_id)

    # 流式调用 LLM
    async for chunk in llm_service.generate_stream(
        messages=llm_messages,
        task_type="chat",
        temperature=0.7,
        max_tokens=2048,
    ):
        yield chunk


# ── 对话知识证据分析（异步，不阻塞回复） ──

async def _analyze_conversation_evidence(
    user_id: str,
    partition_id: str,
    user_text: str,
    assistant_reply: str,
):
    """分析一轮对话，提取知识证据写入 SharedKnowledgeState"""
    try:
        from app.services.knowledge_bridge import knowledge_bridge
        from app.services.storage import storage as _st

        # 从 partition 推断涉及的技能
        data = _st.load(user_id)
        partition = data.partitions.get(partition_id)
        skill_ids = []
        if partition and partition.subject:
            skill_ids = [partition.subject]

        if skill_ids:
            await knowledge_bridge.deep_evidence_analysis(
                user_text=user_text,
                assistant_reply=assistant_reply,
                skill_ids=skill_ids,
                branch_id=partition.active_branch_id if partition else "",
            )
    except Exception as e:
        logger.debug(f"知识证据分析跳过: {e}")


async def send_and_reply(
    user_id: str,
    partition_id: str,
    user_text: str,
    content_blocks: list[ContentBlock] | None = None,
) -> dict:
    """
    完整流程：存用户消息 → 生成回复（含工具） → 存助手消息。
    返回两条消息和 response_blocks。
    """
    # 1. 存用户消息
    blocks = content_blocks or [TextBlock(text=user_text)]
    user_node = tree_ops.add_message(
        user_id, partition_id, "user", blocks, user_text
    )

    # P0: 异步写入元历史 + 触发分支自动命名
    _p0_post_message_hooks(user_id, partition_id, user_node)

    # P0: 异步情绪追踪（LLM 分类 + 缓存）
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(emotion_analyzer.classify(user_text, user_id))
    except Exception:
        pass

    # 2. 生成回复（含工具调用）
    response_blocks = await generate_reply_with_tools(user_id, partition_id, user_text)

    # 提取文本内容用于存储助手消息
    text_parts = []
    for block in response_blocks:
        if block.type == "text":
            text_parts.append(block.content.get("text", ""))
    reply_text = "\n\n".join(text_parts) if text_parts else ""

    # 3. 存助手消息
    reply_blocks = [TextBlock(text=reply_text)] if reply_text else [TextBlock(text="[工具响应]")]
    assistant_node = tree_ops.add_message(
        user_id, partition_id, "assistant", reply_blocks, reply_text
    )

    # P0: 异步写入助手消息的元历史
    _p0_post_message_hooks(user_id, partition_id, assistant_node)

    # P0: 异步知识证据分析（对话 → SharedKnowledgeState）
    import asyncio as _asyncio
    try:
        loop = _asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(_analyze_conversation_evidence(
                user_id, partition_id, user_text, reply_text
            ))
    except Exception:
        pass

    return {
        "user_message": user_node,
        "assistant_message": assistant_node,
        "partition_id": partition_id,
        "response_blocks": [b.model_dump() for b in response_blocks],
    }


async def send_and_reply_stream(
    user_id: str,
    partition_id: str,
    user_text: str,
    content_blocks: list[ContentBlock] | None = None,
) -> AsyncGenerator[dict, None]:
    """
    完整流程（流式）：存用户消息 → 流式生成回复 → 存助手消息。
    产出事件：{"type": "token", "content": ...} / {"type": "done", "assistant_message": ...}
    """
    # 1. 存用户消息
    blocks = content_blocks or [TextBlock(text=user_text)]
    user_node = tree_ops.add_message(
        user_id, partition_id, "user", blocks, user_text
    )

    # P0: async meta history
    _p0_post_message_hooks(user_id, partition_id, user_node)

    # P0: 异步情绪追踪
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(emotion_analyzer.classify(user_text, user_id))
    except Exception:
        pass

    yield {"type": "user_message", "message": user_node}

    # 2. 流式生成回复
    full_reply = ""
    async for chunk in generate_reply_stream(user_id, partition_id, user_text):
        full_reply += chunk
        yield {"type": "token", "content": chunk}

    # 3. 存助手消息
    reply_blocks = [TextBlock(text=full_reply)]
    assistant_node = tree_ops.add_message(
        user_id, partition_id, "assistant", reply_blocks, full_reply
    )

    # P0: async meta history for assistant
    _p0_post_message_hooks(user_id, partition_id, assistant_node)

    # 4. 检测工具调用并生成响应块（含上下文感知）
    last_ai_text = full_reply  # 当前AI回复本身可能建议了工具
    detected_tools = predict_tools(user_text, last_ai_text)
    response_blocks = []

    if detected_tools:
        order = 0
        for tool_name in detected_tools:
            tool_block = await tool_executor.execute(tool_name, {
                "query": user_text,
                "subject": user_text,
                "topic": user_text,
                "prompt": user_text,
            })
            tool_block.order = order
            response_blocks.append(tool_block)
            order += 1

            # 慢任务：提交后台作业
            if tool_name in SLOW_TOOLS:
                from app.services.background_jobs import job_manager
                job = await job_manager.submit(
                    user_id=user_id,
                    tool_name=tool_name,
                    params=tool_block.content.get("params", {}),
                    block_id=tool_block.id,
                    partition_id=partition_id,
                    branch_id="",
                )

        # 存储响应块
        data = storage.load(user_id)
        for block in response_blocks:
            data.response_blocks[block.id] = block
        storage.save(user_id, data)

    yield {
        "type": "done",
        "assistant_message": assistant_node,
        "response_blocks": [b.model_dump() for b in response_blocks],
    }

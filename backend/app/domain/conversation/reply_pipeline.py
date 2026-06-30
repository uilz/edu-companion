"""
ReplyPipeline — 统一回复管线 (orchestrator)

invoke() 为单一入口，产出 ReplyEvent 流。

5 阶段委托给 pipeline_stages.py:
  Stage 1 (ClassifyStage): 分类器 → context_switch
  Stage 2 (SaveMessageStage): 存用户消息 → user_message
  Stage 3 (ToolLoopStage): LLM tool loop
  Stage 4 (PostProcessStage): blocking 后处理器链
  Stage 5 (DoneStage): done 事件

PostProcessor 接口及内置实现 (SourceParser/SocraticCounter/ResponseBlockSaver/
CognitivePathAutoCreator) 保留在本模块，供 PostProcessStage 使用。

副作用处理器 (CognitiveSyncHook/KnowledgeEvidenceHook/MetaHistoryHook)
已迁移到 reply_hooks.py，通过 AssistantReplied 事件驱动。
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from app.schemas.conversation import ContentBlock, ResponseBlock
from app.domain.conversation.pipeline_stages import (
    PipelineCtx,
    ToolResult,
    ReplyEvent,
    PostProcessInput,
    FEYNMAN_ALLOWED_TOOLS,
    ClassifyStage,
    SaveMessageStage,
    ToolLoopStage,
    PostProcessStage,
    DoneStage,
)

logger = logging.getLogger(__name__)

AGENT_LABEL = "tutor"


# ═══════════════════════════════════════════════
# PostProcessor 接口 & 内置实现
# ═══════════════════════════════════════════════


class PostProcessor(Protocol):
    """后处理器接口"""
    is_blocking: bool  # True → await, False → create_task

    async def process(self, input: PostProcessInput) -> None: ...


class SourceParser(PostProcessor):
    """来源解析 → 提取 [来源: xxx] 标注 → 事件化
    
    skill_ids 通过类级别缓存 _skill_ids_by_node 传递给外部 hooks (reply_hooks.py)。
    """
    is_blocking = True
    _skill_ids_by_node: dict[str, list[str]] = {}

    async def process(self, input: PostProcessInput) -> None:
        from app.infrastructure.llm.llm_core import parse_sources, _resolve_skill_ids

        _, source_labels = parse_sources(input.reply_text)
        if not source_labels:
            return

        skill_ids = _resolve_skill_ids(source_labels, input.dir_id, input.user_id)
        if not skill_ids:
            return

        SourceParser._skill_ids_by_node[input.assistant_node.id] = skill_ids
        logger.info("消息 %s 标注知识点: %s", input.assistant_node.id[:8], skill_ids)

        from app.services.analytics.learning_events import record_event
        from app.schemas.learning_event import EventType
        conv_id = input.conversation.id if input.conversation else None
        for sid in skill_ids:
            record_event(
                EventType.SKILL_DISCUSSED,
                user_id=input.user_id,
                dir_id=input.dir_id,
                conv_id=conv_id,
                skill_ids=[sid],
            )


class SocraticCounter(PostProcessor):
    """苏格拉底追问计数"""
    is_blocking = True

    async def process(self, input: PostProcessInput) -> None:
        from app.services.common import get_data_repo
        data = get_data_repo().load(input.user_id)
        conv = data.directory_nodes.get(input.conv_id)
        if conv and conv.node_type != "conv":
            conv = None
        if not conv:
            return
        meta = getattr(conv, 'metadata', None) or {}
        count = meta.get('socratic_question_count', 0)

        stripped = input.reply_text.strip()
        if stripped and (stripped.endswith('?') or stripped.endswith('？')):
            count += 1
        else:
            count = 0

        conv.metadata = meta
        conv.metadata['socratic_question_count'] = count
        get_data_repo().save(input.user_id, data)
        if count >= 3:
            logger.info("Socratic limit: %d consecutive questions in conv %s", count, input.conv_id[:8])


class ResponseBlockSaver(PostProcessor):
    """回填 response_blocks 的 message_id 并持久化"""
    is_blocking = True

    async def process(self, input: PostProcessInput) -> None:
        if not input.response_blocks:
            return
        from app.services.common import get_data_repo
        data = get_data_repo().load(input.user_id)
        for block in input.response_blocks:
            block.message_id = input.assistant_node.id
            data.response_blocks[block.id] = block
        get_data_repo().save(input.user_id, data)


class CognitivePathAutoCreator(PostProcessor):
    """AI回复后，若对话在临时目录且匹配到知识树节点，自动创建目录路径并迁移。"""
    is_blocking = False

    async def process(self, input: PostProcessInput) -> None:
        from app.services.common import get_data_repo
        from app.schemas.conversation import DirectoryNode
        import time

        try:
            if not input.conversation:
                return

            data = get_data_repo().load(input.user_id)
            conv = data.directory_nodes.get(input.conv_id)
            if not conv or conv.node_type != "conv":
                return

            parent = data.directory_nodes.get(conv.parent_id) if conv.parent_id else None
            if parent:
                return  # Already categorized

            skill_ids = SourceParser._skill_ids_by_node.pop(input.assistant_node.id + "_auto_create", [])
            if not skill_ids:
                skill_ids = SourceParser._skill_ids_by_node.get(input.assistant_node.id, [])

            if not skill_ids:
                return

            from app.domain.cognitive import get_repo as get_cog_repo
            cog_repo = get_cog_repo()

            matched_path_id = None
            matched_label = None

            for skill_id in skill_ids:
                cog_node = cog_repo.get_node(skill_id, input.user_id)
                if cog_node and cog_node.path_id:
                    matched_path_id = cog_node.path_id
                    matched_label = cog_node.label or skill_id
                    break

            if not matched_path_id:
                return

            segments = matched_path_id.split(".")
            current_parent_id = None

            root = None
            for dn in data.directory_nodes.values():
                if dn.node_type == "dir" and dn.parent_id is None:
                    root = dn
                    break
            if not root:
                return

            current_parent_id = root.id
            last_dir_id = None

            for segment in segments:
                existing = None
                for dn in data.directory_nodes.values():
                    if (dn.parent_id == current_parent_id and
                        dn.node_type == "dir" and
                        dn.name == segment):
                        existing = dn
                        break

                if existing:
                    current_parent_id = existing.id
                    last_dir_id = existing.id
                else:
                    parent_dir = data.directory_nodes.get(current_parent_id)
                    new_dir = DirectoryNode(
                        user_id=input.user_id,
                        parent_id=current_parent_id,
                        node_type="dir",
                        kind="general",
                        name=segment,
                        path=(parent_dir.path + [parent_dir.id]) if parent_dir else [],
                    )
                    if parent_dir:
                        parent_dir.add_child(new_dir.id)
                    data.directory_nodes[new_dir.id] = new_dir
                    current_parent_id = new_dir.id
                    last_dir_id = new_dir.id

            if not last_dir_id:
                return

            if last_dir_id != conv.parent_id:
                if conv.parent_id:
                    old_parent = data.directory_nodes.get(conv.parent_id)
                    if old_parent:
                        old_parent.remove_child(conv.id)

                conv.parent_id = last_dir_id
                target_parent = data.directory_nodes.get(last_dir_id)
                if target_parent:
                    conv.path = target_parent.path + [target_parent.id]
                    target_parent.add_child(conv.id)
                conv.kind = "general"
                conv.metadata["last_active"] = time.time()
                conv.updated_at = time.time()

                get_data_repo().save(input.user_id, data)
                logger.info(
                    "CognitivePathAutoCreator: migrated conv %s to %s (path: %s)",
                    input.conv_id, matched_path_id, segments,
                )
        except Exception:
            logger.debug("CognitivePathAutoCreator failed (non-critical)", exc_info=True)


# ═══════════════════════════════════════════════
# ReplyPipeline — 编排器
# ═══════════════════════════════════════════════


class ReplyPipeline:
    """回复管线 — 单一入口 invoke()，产出 ReplyEvent 流。

    内部委托给 5 个 PipelineStage:
      ClassifyStage → SaveMessageStage → ToolLoopStage → PostProcessStage → DoneStage
    """

    def __init__(
        self,
        post_processors: list[PostProcessor] | None = None,
        agent_label: str = AGENT_LABEL,
    ) -> None:
        self._post_processors = post_processors or _default_post_processors()
        self.agent_label = agent_label
        self._stages = [
            ClassifyStage(),
            SaveMessageStage(),
            ToolLoopStage(),
            PostProcessStage(processors=self._post_processors),
            DoneStage(),
        ]

    async def invoke(
        self,
        user_id: str,
        dir_id: str,
        user_text: str,
        content_blocks: list[ContentBlock] | None = None,
        conv_id: str = "",
        pending_quote: dict | None = None,
        knowledge_node_id: str | None = None,
        tool_result: ToolResult | None = None,
        resume_state: dict | None = None,
    ) -> AsyncGenerator[ReplyEvent, None]:
        """流式执行完整回复流程，产出事件序列

        resume_state: 挂起恢复时传入 {llm_messages, tools, _round}，跳过阶段 1-2
        """
        ctx = PipelineCtx(
            user_id=user_id,
            dir_id=dir_id,
            user_text=user_text,
            content_blocks=content_blocks,
            conv_id=conv_id,
            pending_quote=pending_quote,
            knowledge_node_id=knowledge_node_id,
            agent_label=self.agent_label,
            tool_result=tool_result,
        )
        if resume_state is not None:
            ctx._resume_state = resume_state

        try:
            for stage in self._stages:
                # 恢复模式：跳过已完成的分类和保存阶段
                if resume_state is not None and stage.name in ("classify", "save_message"):
                    continue

                try:
                    async for event in stage.invoke(ctx):
                        yield event
                except Exception as stage_err:
                    logger.error(
                        "Stage [%s] failed for conv %s: %s",
                        stage.name, ctx.conv_id[:8] if ctx.conv_id else "?", stage_err,
                        exc_info=True,
                    )
                    yield ReplyEvent(type="error", data={"error": str(stage_err)})
                    # tool_loop 失败不继续执行后续阶段
                    if stage.name in ("tool_loop",):
                        break

                # 挂起检测：tool_loop 阶段挂起后不再执行后续阶段
                if stage.name == "tool_loop" and ctx._suspended:
                    logger.info("Pipeline suspended at tool_loop, conv=%s", ctx.conv_id[:8])
                    break
        except Exception as e:
            logger.error("ReplyPipeline failed: %s", e, exc_info=True)
            yield ReplyEvent(type="error", data={"error": str(e)})


# ═══════════════════════════════════════════════
# 处理器列表
# ═══════════════════════════════════════════════


def _default_post_processors() -> list[PostProcessor]:
    """只保留 blocking 处理器。副作用处理器 (CognitiveSyncHook/KnowledgeEvidenceHook/MetaHistoryHook)
    已迁移到 domain/conversation/reply_hooks.py，通过 AssistantReplied 事件驱动。"""
    return [
        SocraticCounter(),
        SourceParser(),
        CognitivePathAutoCreator(),
        ResponseBlockSaver(),
    ]

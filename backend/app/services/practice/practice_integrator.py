"""
练习结果 → 对话记忆集成

将练习session的结果自动写入对话branch，确保：
1. 对话branch知道"我们在这个分支练过"
2. 分区摘要包含练习情况
3. AI下次回复时注入练习上下文
"""

from __future__ import annotations

import logging
from datetime import datetime

from app.schemas.conversation import TextBlock, TreeNode
from app.schemas.practice import PracticeSession
from app.services.common import get_data_repo
from app.services.knowledge.tree_service import tree_ops

logger = logging.getLogger(__name__)


async def integrate_practice_to_branch(
    user_id: str,
    session: PracticeSession,
    dir_id: str,
    branch_id: str,
) -> TreeNode | None:
    """
    将练习结果写入对话branch
    
    在branch中追加一条系统元数据消息（不占token），
    记录练习结果和薄弱点。
    """
    data = get_data_repo().load(user_id)
    branch = data.directory_nodes.get(branch_id)
    if not branch or branch.node_type != "conv":
        logger.warning(f"Branch {branch_id} not found for practice integration")
        return None

    # 构建练习摘要文本
    summary_parts = [
        f"练习记录：{session.correct_count}/{len(session.question_ids)}正确",
        f"用时{session.duration_minutes:.0f}分钟",
    ]
    if session.struggling_skills:
        summary_parts.append(f"薄弱点：{', '.join(session.struggling_skills[:3])}")

    summary_text = "，".join(summary_parts)

    # 创建系统元数据节点
    system_node = tree_ops.add_message(
        user_id, dir_id, "system",
        [TextBlock(text=summary_text)],
        summary_text,
        metadata={
            "type": "practice_summary",
            "session_id": session.session_id,
            "accuracy": session.accuracy,
            "skills_tested": session.planned_skills,
            "error_patterns": [
                a.error_analysis.error_type.value
                for a in session.attempts
                if a.error_analysis and not a.is_correct
            ],
        },
    )

    # 更新branch的练习字段（metadata 方式）
    branch.metadata.setdefault("practice_sessions", []).append(session.session_id)
    branch.metadata["practice_summary"] = (
        f"已练{len(session.question_ids)}题,"
        f"正确率{session.accuracy:.0%},"
        f"薄弱:{','.join(session.struggling_skills[:2]) or '无'}"
    )

    # 更新分区上下文
    partition = data.directory_nodes.get(dir_id)
    if partition and partition.node_type == "dir":
        partition.summary_short += (
            f"\n练习({datetime.now().strftime('%m/%d')}): "
            f"{session.planned_skills} 正确率{session.accuracy:.0%}"
        )

    get_data_repo().save(user_id, data)

    logger.info(
        f"练习结果已写入branch {branch_id}: "
        f"{session.accuracy:.0%} 准确率"
    )

    # P2: 练习错误时搜索关联用户资料
    try:
        from app.infrastructure.files.search import material_search as ms
        enriched = []
        for skill in (session.struggling_skills or [])[:3]:
            chunks = await ms.search(user_id, query=skill, top_k=2)
            for c in chunks:
                src = c.get("material_name", c.get("source_file", "未知"))
                label = src
                enriched.append(label)
        if enriched:
            branch.metadata["practice_summary"] += " | 资料引用: " + "; ".join(enriched[:2])
            get_data_repo().save(user_id, data)
    except Exception as e:
        logger.warning("Failed to enrich practice summary with references: %s", e)

    return system_node


def inject_practice_context(user_id: str, dir_id: str) -> str:
    """
    获取练习上下文，注入到LLM系统提示中
    
    格式：
    [Practice] 最近练习: 极限(70%), 导数(40%←薄弱), 积分(85%)
    """
    data = get_data_repo().load(user_id)
    partition = data.directory_nodes.get(dir_id)
    if not partition or partition.node_type != "dir":
        return ""

    branches = [
        b for b in data.directory_nodes.values()
        if b.node_type == "conv"
        and b.parent_id == dir_id
        and b.metadata.get("practice_summary", "")
    ]

    if not branches:
        return ""

    recent = branches[-3:]  # 最近3个有练习记录的分支
    lines = []
    for b in recent:
        lines.append(f"- {b.display_name}: {b.metadata.get('practice_summary', '')}")

    context = "[Practice]\n" + "\n".join(lines)
    return context

"""
练习结果 → 对话记忆集成

将练习session的结果自动写入对话branch，确保：
1. 对话branch知道"我们在这个分支练过"
2. 分区摘要包含练习情况
3. AI下次回复时注入练习上下文
"""

from __future__ import annotations

import json
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

    # ── 从 DB 查询错题详情（替代旧的 session.attempts / question_ids / struggling_skills） ──
    from app.infrastructure.db.database import get_db
    db = get_db()

    # 查询本 session 中答错的题目及其认知节点 + 错因分析
    wrong_attempts = db.fetchall(
        """SELECT pa.error_analysis, q.cognitive_node_ids
           FROM practice_attempts pa
           JOIN questions q ON pa.question_id = q.id
           WHERE pa.session_id = %s AND pa.is_wrong = true""",
        (session.id,),
    )

    error_patterns: list[str] = []
    struggling_nodes: list[str] = []
    for wa in wrong_attempts:
        # error_analysis: JSONB 字段，可能是 dict 或 str
        ea = wa.get("error_analysis") or {}
        if isinstance(ea, str):
            try:
                ea = json.loads(ea)
            except (json.JSONDecodeError, TypeError):
                ea = {}
        et = ea.get("error_type", "")
        if et:
            error_patterns.append(et)
        nodes = wa.get("cognitive_node_ids") or []
        struggling_nodes.extend(nodes)

    # 去重
    struggling_skills = list(dict.fromkeys(struggling_nodes))

    total_questions = session.total_count or 0
    duration_min = (session.duration_seconds or 0) / 60
    skills_tested = session.cognitive_node_ids or []

    # 构建练习摘要文本
    summary_parts = [
        f"练习记录：{session.correct_count}/{total_questions}正确",
        f"用时{duration_min:.0f}分钟",
    ]
    if struggling_skills:
        summary_parts.append(f"薄弱点：{', '.join(struggling_skills[:3])}")

    summary_text = "，".join(summary_parts)

    # 创建系统元数据节点
    system_node = tree_ops.add_message(
        user_id, dir_id, "system",
        [TextBlock(text=summary_text)],
        summary_text,
        metadata={
            "type": "practice_summary",
            "session_id": session.id,
            "accuracy": session.accuracy,
            "skills_tested": skills_tested,
            "error_patterns": error_patterns,
        },
    )

    # 更新branch的练习字段（metadata 方式）
    branch.metadata.setdefault("practice_sessions", []).append(session.id)
    branch.metadata["practice_summary"] = (
        f"已练{total_questions}题,"
        f"正确率{session.accuracy:.0%},"
        f"薄弱:{','.join(struggling_skills[:2]) or '无'}"
    )

    # 更新分区上下文
    partition = data.directory_nodes.get(dir_id)
    if partition and partition.node_type == "dir":
        partition.summary_short += (
            f"\n练习({datetime.now().strftime('%m/%d')}): "
            f"{skills_tested} 正确率{session.accuracy:.0%}"
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
        for skill in struggling_skills[:3]:
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

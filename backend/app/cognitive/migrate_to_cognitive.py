"""
Phase 6.4: 旧知识图谱 + BKT → CognitiveNode 迁移脚本 (DEPRECATED)

⚠️ 迁移已在 Phase 6 完成，此脚本保留供参考，请不要再执行。

原迁移流程:
  1. 从 JSON userData.json 读取 knowledge_graphs (图谱结构)
  2. 从 PG knowledge_states 读取旧 BKT 掌握度
  3. 从 JSON userData.json 读取 practice_sessions + event_log (练习历史)
  4. 为每个 KGNode 创建/更新 CognitiveNode (含 Belief Beta 分布映射)
  5. 重建图谱层级结构 (partition → domain → topic → concept → atom)
  6. 迁移练习事件 → cognitive_events 表

原使用:
  python -m app.cognitive.migrate_to_cognitive --user default_user
  python -m app.cognitive.migrate_to_cognitive --user default_user --dry-run

向后兼容: 旧 knowledge_states 表不删除, 仅标记 deprecated。
"""

from __future__ import annotations
from app.shared.constants import DEFAULT_USER_ID
import json
import logging
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 数据读取
# ──────────────────────────────────────────────


def _load_user_data(user_id: str = DEFAULT_USER_ID) -> dict:
    """从 JSON 文件加载 UserData"""
    import os
    base = os.path.expanduser("~/.companion/data")
    path = Path(base) / user_id / "userData.json"
    if not path.exists():
        logger.warning(f"userData.json not found: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_pg_knowledge_states(user_id: str) -> list[dict]:
    """从 PG knowledge_states 表加载旧 BKT 数据"""
    from app.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM knowledge_states WHERE user_id = %s",
        (user_id,)
    )
    return rows


def _load_pg_practice_attempts(user_id: str) -> list[dict]:
    """从 PG attempts 表加载练习记录"""
    from app.db.database import get_db
    db = get_db()
    rows = db.fetchall(
        "SELECT * FROM attempts WHERE user_id = %s ORDER BY submitted_at ASC",
        (user_id,)
    )
    return rows


# ──────────────────────────────────────────────
# Beta 分布映射
# ──────────────────────────────────────────────


def _bkt_to_beta(p_known: float, n_observations: int = 0) -> dict:
    """
    将旧 BKT p_known 映射为 Beta 分布 (α, β)。

    映射公式（文档 6.6 节）:
      α = max(p_known * K + α_prior, α_min)
      β = max((1 - p_known) * K + β_prior, β_min)

    其中 K = min(n_observations * 2 + 4, 40)  — 样本量映射
    """
    BETA_ALPHA_MIN = 2.0
    BETA_BETA_MIN = 2.0
    ALPHA_PRIOR = 1.0
    BETA_PRIOR = 1.0

    p = max(0.01, min(0.99, p_known))
    K = min(max(n_observations * 2, 4), 40)

    alpha = max(p * K + ALPHA_PRIOR, BETA_ALPHA_MIN)
    beta = max((1 - p) * K + BETA_PRIOR, BETA_BETA_MIN)

    # 精度 = 1/(α+β)，即样本量倒数
    precision = 1.0 / (alpha + beta)

    return {
        "alpha": round(alpha, 4),
        "beta": round(beta, 4),
        "proficiency_mean": round(p, 4),
        "proficiency_precision": round(precision, 6),
        "peak_proficiency": round(p, 4),
        "last_updated": time.time(),
    }


def _estimate_level_from_graph(
    node_id: str, graph: dict, known_levels: dict[str, str]
) -> str:
    """
    从图谱结构推断知识层级。

    启发式规则:
      1. 如果节点已在 known_levels 中 (手动指定)，直接使用
      2. 根节点 (入度为 0) → 'domain' 或 'topic'
      3. 叶节点 (出度为 0) → 'atom'
      4. 中间节点 → 'concept'
    """
    if node_id in known_levels:
        return known_levels[node_id]

    edges = graph.get("edges", [])
    in_degree = sum(1 for e in edges if e.get("to_id") == node_id)
    out_degree = sum(1 for e in edges if e.get("from_id") == node_id)

    if in_degree == 0:
        return "topic"
    if out_degree == 0:
        return "atom"
    return "concept"


def _collect_all_practice_events(
    user_data: dict, user_id: str, pg_attempts: list[dict]
) -> dict[str, list[dict]]:
    """
    收集所有旧练习事件，按 skill_id 分组。

    来源:
      - PG attempts 表 (按 question_id 关联 skill_id)
      - userData.practice_sessions
      - userData.event_log (PRACTICE_SUBMIT 类型)
    """
    from collections import defaultdict
    events_by_skill: dict[str, list[dict]] = defaultdict(list)

    # 1. PG attempts
    for a in pg_attempts:
        skill_id = a.get("skill_id", "") or a.get("skill_ids", [""])[0] if a.get("skill_ids") else ""
        if skill_id:
            events_by_skill[skill_id].append({
                "type": "practice_response",
                "correct": a.get("is_correct", False),
                "time_spent": a.get("time_spent_seconds", 0),
                "timestamp": a.get("submitted_at", time.time()),
            })

    # 2. event_log
    for ev in user_data.get("event_log", []):
        if ev.get("type") in ("PRACTICE_SUBMIT", "practice_submit"):
            for sid in ev.get("skill_ids", []):
                events_by_skill[sid].append({
                    "type": "practice_response",
                    "correct": ev.get("data", {}).get("correct", False),
                    "time_spent": ev.get("data", {}).get("time_spent", 0),
                    "timestamp": ev.get("timestamp", time.time()),
                })

    return dict(events_by_skill)


def _build_practice_summary(events: list[dict]) -> dict:
    """从练习事件列表构建 PracticeSummary"""
    total = len(events)
    correct = sum(1 for e in events if e.get("correct"))
    total_time = sum(e.get("time_spent", 0) for e in events)

    # 最近7天成功率
    now = time.time()
    week_ago = now - 7 * 86400
    recent = [e for e in events if e.get("timestamp", 0) >= week_ago]
    recent_correct = sum(1 for e in recent if e.get("correct"))

    return {
        "total_attempts": total,
        "correct_attempts": correct,
        "total_time_spent": round(total_time, 2),
        "recent_success_rate_7d": round(recent_correct / max(len(recent), 1), 4),
        "decayed_event_count": total,
        "last_practiced": events[-1]["timestamp"] if events else None,
    }


def _build_cognitive_node(
    node_id: str, label: str, level: str, parent: str | None,
    is_core: bool, p_known: float, n_obs: int, beta_data: dict,
    practice_summary: dict, graph_edges: list[dict] | None = None,
    graph_nodes: dict | None = None,
):
    """构造 CognitiveNode（KG 和题库技能共用）"""
    from app.cognitive.models import (
        CognitiveNode, Activation, Belief, Scheduling,
        PracticeSummary, Trend, Prerequisite, Unlock, Associate, MetaInfo,
    )

    prerequisites, unlocks, associates = [], [], []
    if graph_edges and graph_nodes:
        for edge in graph_edges:
            fid, tid, rel = edge.get("from_id",""), edge.get("to_id",""), edge.get("relation","prerequisite")
            if fid == node_id and rel in ("prerequisite","builds_on"):
                unlocks.append(Unlock(id=tid))
            if tid == node_id and rel == "prerequisite":
                prerequisites.append(Prerequisite(id=fid, type="strict"))

    return CognitiveNode(
        id=node_id, label=label, level=level, parent=parent, is_core=is_core,
        path_id=node_id, is_visible=True,
        activation=Activation(base_level=math.log(max(n_obs,1)+1)/math.log(10), recency=0.0, spread_targets=[]),
        belief=Belief(alpha=beta_data["alpha"], beta=beta_data["beta"], proficiency_mean=beta_data["proficiency_mean"],
                      proficiency_precision=beta_data["proficiency_precision"], peak_proficiency=beta_data["peak_proficiency"],
                      last_updated=beta_data["last_updated"]),
        trend=Trend(velocity=0.0, direction="stable", stagnation_days=0),
        scheduling=Scheduling(next_review=time.time()+86400*(7 if p_known>=0.8 else 1), review_urgency=max(0.0,1.0-p_known), estimated_mastery_time=0),
        practice_summary=PracticeSummary(**practice_summary),
        prerequisites=prerequisites, unlocks=unlocks, associates=associates,
        meta=MetaInfo(created_by="migration_auto", version=1),
    )


# ── 核心迁移逻辑 ──


def migrate_user(
    user_id: str = DEFAULT_USER_ID,
    dry_run: bool = False,
    clean_first: bool = False,
) -> dict:
    """
    将指定用户的旧数据迁移至 CognitiveNode。

    Args:
        user_id: 用户 ID
        dry_run: 仅预览不写入
        clean_first: 迁移前清除该用户的 CognitiveNode (重迁用)

    Returns:
        统计摘要 dict
    """
    from app.db.database import get_db
    from app.cognitive.storage import (  # type: ignore
        upsert_node,
        append_event,
    )
    from app.cognitive.models import (
        CognitiveNode, Activation, Belief, Scheduling,
        PracticeSummary, Trend, PracticeEvent,
        Prerequisite, Unlock, Associate, MetaInfo,
        CognitiveEvent,
    )

    stats = {
        "total_kgs_nodes": 0,
        "total_pg_knowledge": 0,
        "nodes_created": 0,
        "nodes_skipped": 0,
        "events_migrated": 0,
        "errors": 0,
    }

    # ── 1. 加载数据 ──

    logger.info(f"[migrate] 加载用户数据: user_id={user_id}")
    user_data = _load_user_data(user_id)
    pg_knowledge = _load_pg_knowledge_states(user_id)
    pg_attempts = _load_pg_practice_attempts(user_id)

    knowledge_graphs = user_data.get("knowledge_graphs", {})
    has_kg = bool(knowledge_graphs)

    # 题库技能
    from app.db.database import get_db as _get_db
    _db = _get_db()
    skill_rows = _db.fetchall("SELECT DISTINCT skill_id FROM questions WHERE skill_id != '' ORDER BY skill_id")
    question_skills = [r["skill_id"] for r in skill_rows]

    # attempts 按 skill 聚合
    attempt_skills = _db.fetchall("""
        SELECT COALESCE(q.skill_id, '') as skill_id,
               COUNT(*) as cnt,
               SUM(CASE WHEN a.is_correct THEN 1 ELSE 0 END) as correct,
               ROUND(EXTRACT(EPOCH FROM MAX(a.submitted_at))) as last_practiced_ts
        FROM attempts a
        LEFT JOIN questions q ON a.question_id = q.question_id
        WHERE a.user_id = %s
        GROUP BY q.skill_id
    """, (user_id,))

    attempt_map = {r["skill_id"]: r for r in attempt_skills}

    logger.info(
        f"[migrate] 数据概览: KG分区={len(knowledge_graphs)}, "
        f"题库技能={len(question_skills)}, "
        f"attempts技能={len([r for r in attempt_skills if r['skill_id']])}, "
        f"PG BKT={len(pg_knowledge)}, "
        f"PG attempts总数={len(pg_attempts)}"
    )

    # ── 2. 构建 BKT 索引 ──

    bkt_index: dict[str, dict] = {}
    for ks in pg_knowledge:
        sid = ks.get("skill_id", "")
        bkt_index[sid] = ks
    stats["total_pg_knowledge"] = len(bkt_index)

    # ── 3. 收集练习事件 ──

    events_by_skill = _collect_all_practice_events(user_data, user_id, pg_attempts)

    # ── 4. 构建知识层级 ──

    # 从 userData.partitions, domains, topics 读取已知层级
    known_levels: dict[str, str] = {}
    for pid in user_data.get("partitions", {}):
        known_levels[pid] = "partition"
    for did in user_data.get("domains", {}):
        known_levels[did] = "domain"
    for tid in user_data.get("topics", {}):
        known_levels[tid] = "topic"

    # ── 5. 遍历图谱/技能创建 CognitiveNodes ──

    if clean_first and not dry_run:
        logger.info("[migrate] 清除已有 CognitiveNode (user_id=%s)", user_id)
        db = get_db()
        db.execute("DELETE FROM cognitive_nodes WHERE user_id = %s", (user_id,))
        db.execute("DELETE FROM cognitive_events WHERE user_id = %s", (user_id,))

    db = get_db()
    processed_nodes: set[str] = set()

    if has_kg:
        # 有知识图谱 → 从图谱创建
        for pid, kg in knowledge_graphs.items():
            partition_id = pid
            graph_nodes = kg.get("nodes", {})
            graph_edges = kg.get("edges", [])

            stats["total_kgs_nodes"] += len(graph_nodes)

            # Partition 级节点
            partition_label = user_data.get("partitions", {}).get(partition_id, {}).get("name", partition_id)
            if not dry_run:
                try:
                    upsert_node(CognitiveNode(
                        id=partition_id, label=partition_label, level="partition",
                        path_id=partition_id, is_visible=True,
                        activation=Activation(base_level=0.1, recency=0.0, spread_targets=[]),
                        meta=MetaInfo(created_by="migration", version=1),
                    ))
                    stats["nodes_created"] += 1
                    processed_nodes.add(partition_id)
                except Exception as e:
                    logger.error(f"[migrate] partition 创建失败: {partition_id} — {e}")
                    stats["errors"] += 1

            # 遍历 KGNode
            for node_id, kg_node in graph_nodes.items():
                try:
                    label = kg_node.get("label", node_id)
                    level = _estimate_level_from_graph(node_id, kg, known_levels)
                    parent = partition_id if level == "atom" else None

                    ks = bkt_index.get(node_id, {})
                    p_known = ks.get("p_known", kg_node.get("mastery", 0.0) / 100.0 if kg_node.get("mastery") else 0.1)
                    n_obs = ks.get("attempt_count", 0)
                    beta_data = _bkt_to_beta(p_known, n_obs)

                    skill_events = events_by_skill.get(node_id, [])
                    practice_summary = _build_practice_summary(skill_events)

                    if dry_run:
                        stats["nodes_skipped"] += 1
                        continue

                    cn = _build_cognitive_node(node_id, label, level, parent, kg_node.get("is_core", False),
                                               p_known, n_obs, beta_data, practice_summary,
                                               graph_edges, graph_nodes)
                    upsert_node(cn)
                    stats["nodes_created"] += 1
                    processed_nodes.add(node_id)
                except Exception as e:
                    logger.error(f"[migrate] KG节点迁移失败: {node_id} — {e}")
                    stats["errors"] += 1
    else:
        # 无知识图谱 → 从容备考题技能创建
        partition_id = f"__auto_{user_id}__"

        # 创建默认分区节点
        if not dry_run:
            try:
                from app.cognitive.storage import list_all_nodes
                existing = list_all_nodes(user_id)
                if not existing:
                    upsert_node(CognitiveNode(
                        id=partition_id, label="题库技能", level="partition",
                        path_id=partition_id, is_visible=True,
                        activation=Activation(base_level=0.1, recency=0.0, spread_targets=[]),
                        meta=MetaInfo(created_by="migration_auto", version=1),
                    ))
                    stats["nodes_created"] += 1
                    processed_nodes.add(partition_id)
            except Exception as e:
                logger.error(f"[migrate] 分区创建失败: {e}")
                stats["errors"] += 1

        for skill_id in question_skills:
            try:
                label = skill_id.replace("_", " ").title()
                am = attempt_map.get(skill_id, {})
                n_obs = am.get("cnt", 0)
                correct = am.get("correct", 0)
                p_known = (correct / n_obs) if n_obs > 0 else 0.3

                beta_data = _bkt_to_beta(p_known, n_obs)
                practice_summary = {
                    "total_attempts": n_obs,
                    "correct_attempts": correct,
                    "total_time_spent": 0.0,
                    "recent_success_rate_7d": p_known,
                    "last_practiced": am.get("last_practiced_ts"),
                    "decayed_event_count": n_obs,
                }

                if dry_run:
                    stats["nodes_skipped"] += 1
                    continue

                cn = _build_cognitive_node(skill_id, label, "topic", partition_id, False,
                                           p_known, n_obs, beta_data, practice_summary,
                                           [], {})
                upsert_node(cn)
                stats["nodes_created"] += 1
                processed_nodes.add(skill_id)

            except Exception as e:
                logger.error(f"[migrate] 题库技能迁移失败: {skill_id} — {e}")
                stats["errors"] += 1

    # ── 6. 迁移练习事件 → cognitive_events ──

    if not dry_run:
        for skill_id, events in events_by_skill.items():
            if skill_id not in processed_nodes:
                continue
            for ev in events[:50]:  # 最多 50 条
                try:
                    append_event(CognitiveEvent(
                        event_id=f"mig_{skill_id}_{ev['timestamp']}_{ev.get('correct', False)}",
                        event_type="practice_response",
                        node_id=skill_id,
                        user_id=user_id,
                        timestamp=ev.get("timestamp", time.time()),
                        payload={
                            "correct": ev.get("correct", False),
                            "time_spent": ev.get("time_spent", 0),
                            "migrated": True,
                        },
                        processed=False,
                    ))
                    stats["events_migrated"] += 1
                except Exception as e:
                    logger.error(f"[migrate] 事件迁移失败: {skill_id} — {e}")
                    stats["errors"] += 1

    logger.info(
        f"[migrate] 完成: 图谱节点={stats['total_kgs_nodes']}, "
        f"BKT状态={stats['total_pg_knowledge']}, "
        f"创建={stats['nodes_created']}, "
        f"跳过={stats['nodes_skipped']}, "
        f"事件={stats['events_migrated']}, "
        f"错误={stats['errors']}"
    )

    return stats


# ──────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description="旧 BKT + 知识图谱 → CognitiveNode 迁移")
    parser.add_argument("--user", default=DEFAULT_USER_ID, help="用户 ID")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入数据库")
    parser.add_argument("--clean-first", action="store_true", help="迁移前清除该用户的 CognitiveNode")
    args = parser.parse_args()

    logger.info(f"=== 迁移开始 ===")
    logger.info(f"  用户: {args.user}")
    logger.info(f"  dry-run: {args.dry_run}")
    logger.info(f"  clean-first: {args.clean_first}")

    stats = migrate_user(
        user_id=args.user,
        dry_run=args.dry_run,
        clean_first=args.clean_first,
    )

    logger.info(f"=== 迁移摘要 ===")
    for k, v in stats.items():
        logger.info(f"  {k}: {v}")

    if stats.get("errors", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()

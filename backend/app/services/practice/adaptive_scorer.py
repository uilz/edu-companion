"""
AdaptiveScorer — 精通度/掌握度计算（纯函数）

不依赖 DB/I/O，可独立单元测试。
"""

from __future__ import annotations

import logging
import random
from typing import Optional

from shared.utils import safe_json

logger = logging.getLogger(__name__)


def compute_node_mastery(
    questions: list[dict],
    stats_map: dict[str, dict],
) -> dict[str, float]:
    """
    统计每个知识点的掌握度（0~1）。

    从关联题目的正确率加权平均计算：
    - 正确率 = max(0, 1 - wrongs/total)
    - 无数据的题目不影响掌握度
    """
    node_accum: dict[str, dict] = {}

    for q in questions:
        node_ids = q.get("cognitive_node_ids") or []
        stat = stats_map.get(q["id"], {})
        total = stat.get("total", 0) or 0
        wrongs = stat.get("wrongs", 0) or 0

        if total == 0:
            continue

        accuracy = max(0.0, 1.0 - wrongs / total)

        for nid in node_ids:
            if not nid:
                continue
            if nid not in node_accum:
                node_accum[nid] = {"sum": 0.0, "count": 0, "label": ""}
            node_accum[nid]["sum"] += accuracy
            node_accum[nid]["count"] += 1

    result = {}
    for nid, data in node_accum.items():
        if data["count"] > 0:
            result[nid] = round(data["sum"] / data["count"], 3)
    return result


def has_mastery_data(q: dict, node_mastery: dict[str, float]) -> bool:
    """检查题目关联的知识点是否有掌握度数据"""
    node_ids = q.get("cognitive_node_ids") or []
    return any(nid in node_mastery for nid in node_ids)


def filter_by_mastery(
    questions: list[dict],
    node_mastery: dict[str, float],
    min_mastery: float = 0.0,
    max_mastery: float = 1.0,
) -> list[dict]:
    """
    按掌握度范围筛选题目。

    如果题目关联多个知识点，取平均掌握度。
    如果知识点无掌握度数据 → 视作 0。
    """
    result = []
    for q in questions:
        node_ids = q.get("cognitive_node_ids") or []
        if not node_ids:
            # 无知识点的题目按最低掌握度处理
            result.append(q)
            continue
        scores = [node_mastery.get(nid, 0.0) for nid in node_ids if nid]
        if not scores:
            result.append(q)
            continue
        avg_mastery = sum(scores) / len(scores)
        if min_mastery <= avg_mastery < max_mastery:
            result.append(q)
    return result


def pick_from_pool(
    pool: list[dict],
    stats_map: dict[str, dict],
    count: int,
    min_attempts: int = 1,
    max_attempts: int = None,
    max_mastery: float = None,
    min_mastery: float = None,
    node_mastery: dict[str, float] = None,
) -> list[dict]:
    """
    从候选题池中按"错误次数优先"策略选题。
    """
    if not pool or count <= 0:
        return []

    # 按错误次数排序（倒序）
    scored = []
    for q in pool:
        stat = stats_map.get(q["id"], {})
        total = stat.get("total", 0) or 0
        wrongs = stat.get("wrongs", 0) or 0

        # 筛选条件
        if min_attempts is not None and total < min_attempts:
            continue
        if max_attempts is not None and total > max_attempts:
            continue

        if max_mastery is not None and node_mastery:
            q_mastery = _avg_mastery(q, node_mastery)
            if q_mastery is not None and q_mastery >= max_mastery:
                continue
        if min_mastery is not None and node_mastery:
            q_mastery = _avg_mastery(q, node_mastery)
            if q_mastery is not None and q_mastery < min_mastery:
                continue

        scored.append((q, wrongs))

    scored.sort(key=lambda x: -x[1])

    selected = []
    for q, _ in scored:
        if len(selected) >= count:
            break
        selected.append(q)

    return selected


def cold_start_select(
    pool: list[dict],
    stats_map: dict[str, dict],
    count: int,
) -> list[dict]:
    """
    冷启动选题（无掌握度数据时使用）。

    策略：
    1. 从未做过的题目中随机选 60%
    2. 从错误次数最多的题目中选 40%
    3. 保证 Bloom 层次覆盖（如果可能）
    """
    if not pool:
        return []

    # 从未做过的题目中随机选
    new_questions = [q for q in pool if not stats_map.get(q["id"], {}).get("total", 0)]
    random.shuffle(new_questions)

    new_count = min(int(count * 0.6), len(new_questions))
    selected = new_questions[:new_count]

    # 从错误次数最多的题目中选
    remaining_count = count - new_count
    if remaining_count > 0:
        # 排除已选
        used_ids = {q["id"] for q in selected}
        remaining = [q for q in pool if q["id"] not in used_ids]
        # 按错误次数排序
        scored = [(q, stats_map.get(q["id"], {}).get("wrongs", 0) or 0) for q in remaining]
        scored.sort(key=lambda x: -x[1])
        for q, _ in scored:
            if len(selected) >= count:
                break
            if q["id"] not in used_ids:
                selected.append(q)
                used_ids.add(q["id"])

    return selected[:count]


def pick_difficult_questions(pool: list[dict], count: int) -> list[dict]:
    """从高难度题目中选择（challenge 模式）"""
    sorted_pool = sorted(pool, key=lambda q: -(q.get("difficulty", 3) or 3))
    return sorted_pool[:count]


def ensure_bloom_coverage(
    questions: list[dict],
    distribution: Optional[dict[str, int]] = None,
    full_pool: Optional[list[dict]] = None,
) -> list[dict]:
    """
    保证 Bloom 层次覆盖。

    distribution: {"remember": 2, "understand": 2, "apply": 3, ...}
    如果未指定，默认分布偏重"应用"和"理解"
    """
    if not distribution:
        distribution = {"remember": 1, "understand": 2, "apply": 3, "analyze": 2, "evaluate": 1, "create": 1}

    from collections import Counter
    meta_counts = Counter()
    bloom_map = {}
    for q in questions:
        meta = safe_json(q.get("metadata"), {})
        bl = meta.get("bloom_level", "apply")
        meta_counts[bl] += 1
        bloom_map[q["id"]] = bl

    needs = {}
    for bl, target in distribution.items():
        have = meta_counts.get(bl, 0)
        if have < target:
            needs[bl] = target - have

    if not needs:
        return questions

    if not full_pool:
        logger.info("Bloom覆盖缺口: %s（无可替换候选题）", dict(needs))
        return questions

    surplus = {}
    for bl, target in distribution.items():
        have = meta_counts.get(bl, 0)
        if have > target:
            surplus[bl] = have - target

    if not surplus:
        logger.info("Bloom覆盖缺口: %s（无冗余层次可替换）", dict(needs))
        return questions

    candidates_by_bloom = {}
    for q in full_pool:
        meta = safe_json(q.get("metadata"), {})
        bl = meta.get("bloom_level", "apply")
        if bl not in candidates_by_bloom:
            candidates_by_bloom[bl] = []
        candidates_by_bloom[bl].append(q)

    redundant_ids = set()
    for q in questions:
        bl = bloom_map.get(q["id"], "apply")
        if bl in surplus and surplus[bl] > 0:
            redundant_ids.add(q["id"])
            surplus[bl] -= 1

    if not redundant_ids:
        logger.info("Bloom覆盖缺口: %s（无法定位可替换题目）", dict(needs))
        return questions

    import random
    result = [q for q in questions if q["id"] not in redundant_ids]
    for bl, needed in needs.items():
        available = candidates_by_bloom.get(bl, [])
        available = [q for q in available if q["id"] not in {r["id"] for r in result}]
        random.shuffle(available)
        for q in available[:needed]:
            result.append(q)

    if len(result) < len(questions):
        for bl in surplus:
            available = candidates_by_bloom.get(bl, [])
            available = [q for q in available if q["id"] not in {r["id"] for r in result}]
            random.shuffle(available)
            for q in available[:len(questions) - len(result)]:
                result.append(q)

    logger.info("Bloom重平衡: 缺口=%s, 替换前=%d, 替换后=%d",
                dict(needs), len(questions), len(result))
    return result[:len(questions)]


def select_by_mastery_layers(
    pool: list[dict],
    stats_map: dict[str, dict],
    node_mastery: dict[str, float],
    count: int,
    mode: str = "adaptive",
    epsilon: float = 0.1,
) -> list[dict]:
    """
    按掌握度分层选题（纯逻辑，无 I/O）。

    adaptive 模式: 6:3:1 分层
    review 模式: 全从薄弱选
    challenge 模式: 高难度
    new 模式: 全新题
    """
    import random

    if mode == "new":
        return pick_from_pool(pool, stats_map, count, min_attempts=0, max_attempts=0)

    if mode == "review":
        return pick_from_pool(pool, stats_map, count, max_mastery=0.4, node_mastery=node_mastery)

    if mode == "challenge":
        return pick_difficult_questions(pool, count)

    # adaptive 模式：6:3:1 分层
    weak_pool = filter_by_mastery(pool, node_mastery, max_mastery=0.4)
    medium_pool = filter_by_mastery(pool, node_mastery, min_mastery=0.4, max_mastery=0.7)
    strong_pool = filter_by_mastery(pool, node_mastery, min_mastery=0.7)
    unknown_pool = [q for q in pool if not has_mastery_data(q, node_mastery)]

    weak_count = max(1, int(count * 0.6))
    medium_count = max(1, int(count * 0.3))
    strong_count = count - weak_count - medium_count

    if len(unknown_pool) > len(pool) * 0.5:
        logger.info("冷启动模式: 无掌握度数据比例过高")
        return cold_start_select(pool, stats_map, count)

    selected = []
    selected.extend(pick_from_pool(weak_pool, stats_map, weak_count, max_mastery=0.4, node_mastery=node_mastery))
    selected.extend(pick_from_pool(medium_pool, stats_map, medium_count, min_mastery=0.4, max_mastery=0.7, node_mastery=node_mastery))
    selected.extend(pick_from_pool(strong_pool, stats_map, strong_count, min_mastery=0.7, node_mastery=node_mastery))

    used_ids = {q["id"] for q in selected}
    remaining = [q for q in pool if q["id"] not in used_ids]
    if len(selected) < count and remaining:
        random.shuffle(remaining)
        for q in remaining:
            if len(selected) >= count:
                break
            selected.append(q)

    return selected


# ── 内部辅助 ──


def _avg_mastery(q: dict, node_mastery: dict[str, float]) -> Optional[float]:
    """计算题目关联知识点的平均掌握度"""
    node_ids = q.get("cognitive_node_ids") or []
    scores = [node_mastery.get(nid, 0.0) for nid in node_ids if nid]
    if not scores:
        return None
    return sum(scores) / len(scores)



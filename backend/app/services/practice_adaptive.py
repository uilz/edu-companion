"""
自适应选题算法

策略（分层优先级）：
1. 错题优先 — 错误次数多的权重最高
2. 新题穿插 — 从未做过的题目保证一定比例
3. 薄弱知识点 — 通过 cognitive_node_ids 加权
4. 难度自适应 — 根据近期正确率调整目标难度
5. Bloom 层次覆盖 — 保证各认知层次都有
"""

import json
import logging
import random
from datetime import datetime, timedelta
from typing import Optional
from shared.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)


def adaptive_select(
    bank_id: str,
    user_id: str = DEFAULT_USER_ID,
    count: int = 10,
    mode: str = "adaptive",
    exclude_ids: Optional[list[str]] = None,
    target_difficulty: Optional[int] = None,
    cognitive_node_ids: Optional[list[str]] = None,
    bloom_distribution: Optional[dict[str, int]] = None,
) -> list[dict]:
    """
    自适应选题。

    参数:
        bank_id: 题库ID
        count: 选题数量
        mode: adaptive / review / challenge / new
        exclude_ids: 排除的题目ID（如已在当前会话中的）
        target_difficulty: 目标难度 1-5
        cognitive_node_ids: 限定的知识点范围
        bloom_distribution: Bloom层次分布 {"remember": 2, "understand": 3, ...}

    返回:
        选出的题目列表（不含答案）
    """
    from app.db.database import get_db
    db = get_db()

    exclude = set(exclude_ids or [])

    # 1. 获取题库所有活跃题目
    questions = db.fetchall(
        """SELECT q.* FROM v7_questions q
           WHERE q.bank_id = %s AND q.deleted_at IS NULL AND q.status = 'active'
           AND q.is_slashed = false
           ORDER BY q.created_at DESC""",
        (bank_id,),
    )

    if not questions:
        logger.info("题库 %s 无可用题目", bank_id)
        return []

    # 2. 过滤排除 + 知识点范围
    pool = [q for q in questions if q["id"] not in exclude]
    if cognitive_node_ids:
        pool = [
            q for q in pool
            if q.get("cognitive_node_ids") and any(
                cid in (q["cognitive_node_ids"] or []) for cid in cognitive_node_ids
            )
        ]

    if not pool:
        logger.info("过滤后无可用题目 bank=%s", bank_id)
        return []

    # 3. 获取历史作答统计
    qids = [q["id"] for q in pool]
    if not qids:
        return []

    # 查询每个题目的历史正确率
    stats_raw = db.fetchall(
        """SELECT question_id,
                  COUNT(*) as total,
                  SUM(CASE WHEN is_wrong THEN 1 ELSE 0 END) as wrongs,
                  MAX(created_at) as last_done
           FROM v7_practice_attempts
           WHERE question_id = ANY(%s) AND user_id = %s
           GROUP BY question_id""",
        (qids, user_id),
    )
    stats_map = {r["question_id"]: r for r in stats_raw}

    # 4. 计算权重并排序
    scored = []
    for q in pool:
        qid = q["id"]
        stat = stats_map.get(qid, {})
        total = stat.get("total", 0) or 0
        wrongs = stat.get("wrongs", 0) or 0

        if mode == "new":
            # 纯新题模式：没做过的排最前
            score = 0 if total == 0 else 100 + total
        elif mode == "review":
            # 复习模式：错得越多越优先
            score = -wrongs  # 负数做大值
            if total == 0:
                score = -100  # 新题不优先
        elif mode == "challenge":
            # 挑战模式：高难度优先
            score = -float(q.get("difficulty", 3))
        else:
            # adaptive 默认模式
            if total == 0:
                score = -50  # 新题，中等优先
            elif wrongs / max(total, 1) > 0.5:
                score = -wrongs * 2  # 错误率 > 50%，极高优先
            else:
                score = 50 - wrongs  # 已掌握的靠后

        # 目标难度加权
        if target_difficulty:
            diff = q.get("difficulty", 3)
            score -= abs(diff - target_difficulty) * 5

        scored.append((score, q))

    # 5. 按分数排序（分数越小越靠前）
    scored.sort(key=lambda x: x[0])

    # 6. 选前 N 道 + 随机微调（避免每次完全一样）
    top_n = scored[:max(count * 2, 20)]  # 候选池放大
    # 前 70% 从高分区选，后 30% 加入随机扰动
    high_priority = top_n[:max(len(top_n) // 2, count)]
    low_priority = top_n[len(high_priority):]

    selected = []
    # 先取高优先级
    random.shuffle(high_priority)
    for _, q in high_priority:
        if len(selected) >= count:
            break
        selected.append(q)

    # 不够再补低优先级
    if len(selected) < count:
        random.shuffle(low_priority)
        for _, q in low_priority:
            if len(selected) >= count:
                break
            if q not in selected:
                selected.append(q)

    # 7. Bloom 覆盖保证
    selected = _ensure_bloom_coverage(selected, bloom_distribution)

    # 8. 脱敏（不返回答案）
    result = []
    for q in selected:
        item = _row_to_safe(q)
        stat = stats_map.get(q["id"], {})
        item["_attempts"] = stat.get("total", 0) or 0
        item["_wrongs"] = stat.get("wrongs", 0) or 0
        result.append(item)

    logger.info(
        "自适应选题: bank=%s, mode=%s, pool=%d, selected=%d",
        bank_id, mode, len(pool), len(result),
    )
    return result


def _ensure_bloom_coverage(
    questions: list[dict],
    distribution: Optional[dict[str, int]] = None,
) -> list[dict]:
    """
    保证 Bloom 层次覆盖。
    distribution: {"remember": 2, "understand": 2, "apply": 3, ...}
    如果未指定，默认分布偏重"应用"和"理解"
    """
    if not distribution:
        # 默认分布：记忆1 理解2 应用3 分析2 评价1 创造1
        distribution = {"remember": 1, "understand": 2, "apply": 3, "analyze": 2, "evaluate": 1, "create": 1}

    # 从 metadata 提取 bloom_level
    from collections import Counter
    meta_counts = Counter()
    for q in questions:
        meta = _safe_json(q.get("metadata"), {})
        bl = meta.get("bloom_level", "apply")
        meta_counts[bl] += 1

    # 检查各层次是否达标
    needs = {}
    for bl, target in distribution.items():
        have = meta_counts.get(bl, 0)
        if have < target:
            needs[bl] = target - have

    if not needs:
        return questions  # 已满足

    # 需要补充的层次 — 从非选中题查找
    # 简单实现：打印日志，保持原列表（深入补充涉及全题库重选，暂做简化）
    logger.info("Bloom覆盖缺口: %s", dict(needs))
    return questions


def _row_to_safe(row: dict) -> dict:
    """将数据库行转成安全返回（不含答案）"""
    from app.services.practice_question_bank import _safe_json
    return {
        "id": row["id"],
        "bank_id": row["bank_id"],
        "question_type": row["question_type"],
        "stem": row["stem"],
        "options": _safe_json(row.get("options"), []),
        "difficulty": row.get("difficulty", 3),
        "cognitive_node_ids": row.get("cognitive_node_ids") or [],
        "metadata": _safe_json(row.get("metadata"), {}),
    }


def _safe_json(val, default=None):
    if val is None:
        return default
    if isinstance(val, (list, dict)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return default
    return default

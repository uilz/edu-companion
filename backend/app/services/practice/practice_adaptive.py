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

logger = logging.getLogger(__name__)


def adaptive_select(
    bank_id: str,
    user_id: str,
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
        """SELECT q.* FROM questions q
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
           FROM practice_attempts
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

    # 7. Bloom 覆盖保证（主动重平衡）
    selected = _ensure_bloom_coverage(selected, bloom_distribution, full_pool=pool)

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
    full_pool: Optional[list[dict]] = None,
) -> list[dict]:
    """
    保证 Bloom 层次覆盖。

    改进点:
    - 从被动记录缺口 → 主动从候选池(full_pool)中替换题目以补齐缺口
    - 如果 full_pool 为空，则退化为日志模式

    distribution: {"remember": 2, "understand": 2, "apply": 3, ...}
    如果未指定，默认分布偏重"应用"和"理解"
    """
    if not distribution:
        # 默认分布：记忆1 理解2 应用3 分析2 评价1 创造1
        distribution = {"remember": 1, "understand": 2, "apply": 3, "analyze": 2, "evaluate": 1, "create": 1}

    # 从 metadata 提取 bloom_level
    from collections import Counter
    meta_counts = Counter()
    bloom_map = {}  # question_id → bloom_level
    for q in questions:
        meta = _safe_json(q.get("metadata"), {})
        bl = meta.get("bloom_level", "apply")
        meta_counts[bl] += 1
        bloom_map[q["id"]] = bl

    # 检查各层次是否达标
    needs = {}
    for bl, target in distribution.items():
        have = meta_counts.get(bl, 0)
        if have < target:
            needs[bl] = target - have

    if not needs:
        return questions  # 已满足

    if not full_pool:
        # 无候选池，仅记录日志（旧行为）
        logger.info("Bloom覆盖缺口: %s（无可替换候选题）", dict(needs))
        return questions

    # 主动重平衡：从 full_pool 中查找缺失层次的题目替换已有重复层次的题目
    # 找出有冗余的层次
    surplus = {}
    for bl, target in distribution.items():
        have = meta_counts.get(bl, 0)
        if have > target:
            surplus[bl] = have - target

    if not surplus:
        # 没有冗余层次可以替换，记录日志
        logger.info("Bloom覆盖缺口: %s（无冗余层次可替换）", dict(needs))
        return questions

    # 构建 candidate 池 (按 bloom 层次分组)
    candidates_by_bloom = {}
    for q in full_pool:
        meta = _safe_json(q.get("metadata"), {})
        bl = meta.get("bloom_level", "apply")
        if bl not in candidates_by_bloom:
            candidates_by_bloom[bl] = []
        candidates_by_bloom[bl].append(q)

    # 替换：从冗余层次的题目中替换为缺失层次的题目
    # 先找出当前选中题中属于冗余层次的
    redundant_ids = set()
    for q in questions:
        bl = bloom_map.get(q["id"], "apply")
        if bl in surplus and surplus[bl] > 0:
            redundant_ids.add(q["id"])
            surplus[bl] -= 1

    if not redundant_ids:
        logger.info("Bloom覆盖缺口: %s（无法定位可替换题目）", dict(needs))
        return questions

    # 从候选池中找缺失层次的题目替换
    result = [q for q in questions if q["id"] not in redundant_ids]
    for bl, needed in needs.items():
        available = candidates_by_bloom.get(bl, [])
        # 排除已在结果中的
        available = [q for q in available if q["id"] not in {r["id"] for r in result}]
        random.shuffle(available)
        for q in available[:needed]:
            result.append(q)

    # 用冗余层次中多出来的题补回数量
    if len(result) < len(questions):
        for bl in surplus:
            available = candidates_by_bloom.get(bl, [])
            available = [q for q in available if q["id"] not in {r["id"] for r in result}]
            random.shuffle(available)
            for q in available[:len(questions) - len(result)]:
                result.append(q)

    logger.info(
        "Bloom重平衡: 缺口=%s, 替换前=%d, 替换后=%d",
        dict(needs), len(questions), len(result),
    )
    return result[:len(questions)]  # 保持数量不变


# ══════════════════════════════════════════════════════════════
# v2 自适应算法 — 6:3:1 分层 + AI fallback
# ══════════════════════════════════════════════════════════════


def adaptive_select_v2(
    bank_id: str,
    user_id: str,
    count: int = 10,
    mode: str = "adaptive",
    exclude_ids: Optional[list[str]] = None,
    cognitive_node_ids: Optional[list[str]] = None,
    enable_ai_fallback: bool = True,
    subject_hint: Optional[str] = None,
) -> list[dict]:
    """
    增强版自适应选题。

    相比 v1 的改进：
    1. 6:3:1 分层 — 通过 practice_attempts 统计各知识点掌握度
       → 薄弱 (mastery<0.4) 60% / 巩固 (0.4-0.7) 30% / 保持 (>=0.7) 10%
    2. ε-greedy 探索 — 10% 概率随机选题，避免纯贪心
    3. AI fallback — 题目不足时自动 AI 生成补足
    4. 冷启动 — 无历史数据时退化为 v1 算法

    参数:
        subject_hint: AI fallback 时使用的学科提示，从对话上下文推断
    """
    from app.db.database import get_db
    db = get_db()

    exclude = set(exclude_ids or [])

    # 1. 获取题库所有活跃题目
    questions = db.fetchall(
        """SELECT q.* FROM questions q
           WHERE q.bank_id = %s AND q.deleted_at IS NULL AND q.status = 'active'
           AND q.is_slashed = false
           ORDER BY q.created_at DESC""",
        (bank_id,),
    )

    if not questions:
        logger.info("题库 %s 无可用题目，尝试 AI fallback", bank_id)
        return _ai_fallback(bank_id, user_id, count, cognitive_node_ids, subject_hint=subject_hint) if enable_ai_fallback else []

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
        logger.info("过滤后无可用题目 bank=%s, 尝试 AI fallback", bank_id)
        return _ai_fallback(bank_id, user_id, count, cognitive_node_ids, subject_hint=subject_hint) if enable_ai_fallback else []

    # 3. 获取历史作答统计 + 按知识点计算掌握度
    qids = [q["id"] for q in pool]
    stats_raw = db.fetchall(
        """SELECT question_id,
                  COUNT(*) as total,
                  SUM(CASE WHEN is_wrong THEN 1 ELSE 0 END) as wrongs,
                  MAX(created_at) as last_done
           FROM practice_attempts
           WHERE question_id = ANY(%s) AND user_id = %s
           GROUP BY question_id""",
        (qids, user_id),
    )
    stats_map = {r["question_id"]: r for r in stats_raw}

    # 4. 计算每个知识点的掌握度（从所有题目的统计推算）
    node_mastery = _compute_node_mastery(pool, stats_map)

    # 5. 6:3:1 分层选题
    selected = _select_by_mastery_layers(
        pool=pool,
        stats_map=stats_map,
        node_mastery=node_mastery,
        count=count,
        mode=mode,
    )

    # 6. Bloom 覆盖（主动重平衡）
    selected = _ensure_bloom_coverage(selected, full_pool=pool)

    # 7. 脱敏
    result = []
    for q in selected:
        item = _row_to_safe(q)
        stat = stats_map.get(q["id"], {})
        item["_attempts"] = stat.get("total", 0) or 0
        item["_wrongs"] = stat.get("wrongs", 0) or 0
        result.append(item)

    # 8. AI fallback 补足（如果选的还不够）
    if len(result) < count and enable_ai_fallback:
        shortage = count - len(result)
        logger.info("AI fallback 补题: %d 道不足", shortage)
        ai_questions = _ai_fallback(bank_id, user_id, shortage, cognitive_node_ids, subject_hint=subject_hint)
        if ai_questions:
            result.extend(ai_questions)

    logger.info(
        "adaptive_v2: bank=%s, mode=%s, pool=%d, selected=%d%s",
        bank_id, mode, len(pool), len(result),
        " (with AI fallback)" if len(result) > len(selected) else "",
    )
    return result


def _compute_node_mastery(
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
            # 新题不计入掌握度计算
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


def _select_by_mastery_layers(
    pool: list[dict],
    stats_map: dict[str, dict],
    node_mastery: dict[str, float],
    count: int,
    mode: str = "adaptive",
    epsilon: float = 0.1,  # 探索率：10% 的概率随机选题
) -> list[dict]:
    """
    按掌握度分层选题。

    核心比例（adaptive 模式）:
    - 薄弱 (mastery < 0.4): 60%
    - 巩固 (0.4 <= mastery < 0.7): 30%
    - 保持 (mastery >= 0.7): 10%

    ε-greedy 探索:
    - 以 epsilon 概率从各层随机选题而非按错误次数排序
    - 避免系统永远选"当前最优"，错过潜在能力发现

    其他模式:
    - review: 全从薄弱选
    - challenge: 全从巩固/保持选（高难度）
    - new: 全从新题选
    """
    if mode == "new":
        return _pick_from_pool(pool, stats_map, count, min_attempts=0, max_attempts=0)

    if mode == "review":
        return _pick_from_pool(pool, stats_map, count, max_mastery=0.4, node_mastery=node_mastery)

    if mode == "challenge":
        # 挑战模式：高难度 + 较高掌握度题目
        return _pick_difficult_questions(pool, count)

    # adaptive 模式：6:3:1 分层
    weak_pool = _filter_by_mastery(pool, node_mastery, max_mastery=0.4)
    medium_pool = _filter_by_mastery(pool, node_mastery, min_mastery=0.4, max_mastery=0.7)
    strong_pool = _filter_by_mastery(pool, node_mastery, min_mastery=0.7)

    # 无掌握度数据（冷启动）
    unknown_pool = [q for q in pool if not _has_mastery_data(q, node_mastery)]

    weak_count = max(1, int(count * 0.6))
    medium_count = max(1, int(count * 0.3))
    strong_count = count - weak_count - medium_count

    # 冷启动：如果大部分题目无掌握度，退化为 v1 算法
    if len(unknown_pool) > len(pool) * 0.5:
        logger.info("冷启动模式: 无掌握度数据比例过高")
        return _cold_start_select(pool, stats_map, count)

    selected = []
    selected.extend(_pick_from_pool(weak_pool, stats_map, weak_count, max_mastery=0.4, node_mastery=node_mastery))
    selected.extend(_pick_from_pool(medium_pool, stats_map, medium_count, min_mastery=0.4, max_mastery=0.7, node_mastery=node_mastery))
    selected.extend(_pick_from_pool(strong_pool, stats_map, strong_count, min_mastery=0.7, node_mastery=node_mastery))

    # 补不足
    used_ids = {q["id"] for q in selected}
    remaining = [q for q in pool if q["id"] not in used_ids]
    if len(selected) < count and remaining:
        random.shuffle(remaining)
        for q in remaining:
            if len(selected) >= count:
                break
            selected.append(q)

    return selected


def _filter_by_mastery(
    questions: list[dict],
    node_mastery: dict[str, float],
    min_mastery: float = 0.0,
    max_mastery: float = 1.0,
) -> list[dict]:
    """按掌握度范围过滤题目"""
    result = []
    for q in questions:
        node_ids = q.get("cognitive_node_ids") or []
        if not node_ids:
            # 无关联知识点的题放中间层
            if min_mastery <= 0.4 and max_mastery >= 0.4:
                result.append(q)
            continue
        # 取该题关联节点的平均掌握度
        mastery_vals = [node_mastery.get(nid, 0.5) for nid in node_ids if nid]
        if not mastery_vals:
            continue
        avg_mastery = sum(mastery_vals) / len(mastery_vals)
        if min_mastery <= avg_mastery < max_mastery:
            result.append(q)
    return result


def _has_mastery_data(q: dict, node_mastery: dict[str, float]) -> bool:
    """检查题目是否有掌握度数据"""
    for nid in (q.get("cognitive_node_ids") or []):
        if nid and nid in node_mastery:
            return True
    return False


def _pick_from_pool(
    pool: list[dict],
    stats_map: dict[str, dict],
    count: int,
    min_attempts: int = 0,
    max_attempts: int = 999,
    min_mastery: float = 0.0,
    max_mastery: float = 1.0,
    node_mastery: Optional[dict[str, float]] = None,
    epsilon: float = 0.1,  # ε-greedy 探索率
) -> list[dict]:
    """从候选池中按条件选题。

    支持 ε-greedy 探索：
    - 以 epsilon 概率纯随机选取（探索未知能力）
    - 以 1-epsilon 概率按错误次数排序选取（利用已知弱点）
    """
    candidates = []
    for q in pool:
        stat = stats_map.get(q["id"], {})
        total = stat.get("total", 0) or 0
        if total < min_attempts or total > max_attempts:
            continue
        # 掌握度过滤
        if node_mastery is not None:
            node_ids = q.get("cognitive_node_ids") or []
            if node_ids:
                mastery_vals = [node_mastery.get(nid, 0.5) for nid in node_ids if nid]
                if mastery_vals:
                    avg = sum(mastery_vals) / len(mastery_vals)
                    if avg < min_mastery or avg >= max_mastery:
                        continue
        candidates.append(q)

    if not candidates:
        return []

    # ε-greedy: 以 epsilon 概率随机探索
    if random.random() < epsilon and len(candidates) > count:
        random.shuffle(candidates)
        return candidates[:count]

    # 按错误次数排序（错得多优先）
    candidates.sort(key=lambda q: -(stats_map.get(q["id"], {}).get("wrongs", 0) or 0))
    random.shuffle(candidates[:max(count * 2, 10)])
    return candidates[:count]


def _pick_difficult_questions(pool: list[dict], count: int) -> list[dict]:
    """挑战模式：选高难度题"""
    sorted_pool = sorted(pool, key=lambda q: -(q.get("difficulty", 3)))
    return sorted_pool[:count]


def _cold_start_select(pool: list[dict], stats_map: dict[str, dict], count: int) -> list[dict]:
    """冷启动选题：v1 逻辑 — 新题优先 + 随机"""
    scored = []
    for q in pool:
        stat = stats_map.get(q["id"], {})
        total = stat.get("total", 0) or 0
        wrongs = stat.get("wrongs", 0) or 0
        if total == 0:
            score = -50  # 新题优先
        elif wrongs / max(total, 1) > 0.5:
            score = -wrongs * 2
        else:
            score = 50 - wrongs
        scored.append((score, q))

    scored.sort(key=lambda x: x[0])
    random.shuffle(scored[:max(count * 2, 10)])
    return [q for _, q in scored[:count]]


def _ai_fallback(
    bank_id: str,
    user_id: str,
    count: int,
    cognitive_node_ids: Optional[list[str]] = None,
    subject_hint: Optional[str] = None,
) -> list[dict]:
    """AI 补题：当题库不够时自动生成"""
    try:
        from app.services.practice.practice_question_gen import generate_and_save

        skill_id = cognitive_node_ids[0] if cognitive_node_ids else ""

        # 推断学科：优先使用外部提示，其次从 cognitive_node_ids 推断，最后回退
        subject = subject_hint or ""
        if not subject and cognitive_node_ids:
            # 尝试从认知节点查找学科信息
            try:
                from app.cognitive import get_repo
                for nid in cognitive_node_ids:
                    node = get_repo().get_node(nid, user_id)
                    if node and hasattr(node, 'subject') and node.subject:
                        subject = node.subject
                        break
            except Exception:
                pass
        if not subject:
            # 从题库元数据推测
            try:
                from app.db.database import get_db
                db = get_db()
                bank = db.fetchone(
                    "SELECT metadata FROM question_banks WHERE id = %s",
                    (bank_id,),
                )
                if bank:
                    meta = _safe_json(bank.get("metadata"), {})
                    subject = meta.get("subject", "") or meta.get("topic", "") or ""
            except Exception:
                pass
        if not subject:
            subject = "数学"  # 最终回退

        saved = generate_and_save(
            bank_id=bank_id,
            user_id=user_id,
            subject=subject,
            skill_id=skill_id,
            count=min(count, 5),
            content_type="choice",
        )
        # 转成 safe 格式
        result = []
        for q in saved:
            result.append({
                "id": q["id"],
                "bank_id": bank_id,
                "question_type": q.get("question_type", "single"),
                "stem": q.get("stem", ""),
                "options": q.get("options", []),
                "difficulty": q.get("difficulty", 3),
                "cognitive_node_ids": q.get("cognitive_node_ids") or [],
                "metadata": q.get("metadata", {}),
            })
        logger.info("AI fallback 生成了 %d 道题", len(result))
        return result
    except Exception as e:
        logger.warning("AI fallback 失败: %s", e)
        return []


def _row_to_safe(row: dict) -> dict:
    """将数据库行转成安全返回（不含答案）"""
    from app.services.practice.practice_question_bank import _safe_json
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

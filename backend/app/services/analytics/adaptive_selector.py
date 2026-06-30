"""
AdaptiveSelector — 自适应练习队列生成器

基于 CognitiveNode 信念 + Scheduling 状态，为每个用户生成
个性化练习队列，自动平衡：
  1. 复习紧迫度 (urgency)
  2. 最近发展区 (ZPD) — 掌握度 0.3-0.7 之间的"甜点"
  3. 探索覆盖率 — 还没练过的知识点

算法：三级优先级排序 + 前 N 截断
"""

from __future__ import annotations
import logging
import time
from app.domain.cognitive.models import CognitiveNode
from app.domain.cognitive import get_repo
from app.services.analytics.spaced_repetition import ReviewResult

logger = logging.getLogger(__name__)

# ─── 默认参数 ───
DEFAULT_QUEUE_SIZE = 8
REVIEW_WEIGHT = 2.0       # 复习优先级权重
ZPD_WEIGHT = 1.5          # ZPD 区域权重
EXPLORE_WEIGHT = 0.5      # 新知识点权重
MASTERY_LOWER = 0.3       # ZPD 下界
MASTERY_UPPER = 0.7       # ZPD 上界
MAX_ATTEMPTS_NORMALIZE = 15  # 练习次数归一化上限


class AdaptiveSelector:
    """自适应练习选择器"""

    def get_queue(
        self,
        user_id: str,
        count: int = DEFAULT_QUEUE_SIZE,
        dir_id: str | None = None,
        mode: str = "adaptive",  # adaptive | review | explore | challenge
    ) -> list[ReviewResult]:
        """
        生成练习队列

        参数：
            user_id: 用户
            count: 返回数量
            dir_id: 可选，限定在某个分区
            mode: 队列模式
                adaptive (默认) — 平衡复习 + ZPD + 探索
                review — 仅复习 (urgency > 0.5)
                explore — 仅新知识点
                challenge — 挑战高难度 (proficiency > 0.7)

        返回：
            按优先级降序排列的 ReviewResult 列表
        """
        # 1. 获取候选节点
        nodes = self._get_candidates(user_id, dir_id)
        if not nodes:
            logger.info("No candidate nodes found for user=%s", user_id)
            return []

        # 2. 计算打分
        scored = self._score_nodes(nodes, mode)

        # 3. 排序 + 截断
        scored.sort(key=lambda x: x["total_score"], reverse=True)

        # 4. 转成 ReviewResult
        results = []
        seen_labels: set[str] = set()
        for item in scored:
            node = item["node"]
            # 去重（相同 label 不重复出现）
            if node.label in seen_labels:
                continue
            seen_labels.add(node.label)
            results.append(self._to_review_result(node, item))
            if len(results) >= count:
                break

        return results

    def _get_candidates(
        self, user_id: str, dir_id: str | None = None,
    ) -> list[CognitiveNode]:
        """获取候选节点：atom + concept 级别，非删除"""
        nodes = get_repo().list_all_nodes(user_id)
        # 过滤
        candidates = []
        for n in nodes:
            if n.level not in ("atom", "concept"):
                continue
            # 检查未删除 — deleted_at 不存储在 CognitiveNode 模型中
            # 由 SQL 过滤，此处信任 get_repo().list_all_nodes
            if dir_id and n.path_id and not n.path_id.startswith(dir_id):
                continue
            candidates.append(n)
        return candidates

    def _score_nodes(
        self, nodes: list[CognitiveNode], mode: str,
    ) -> list[dict]:
        """为每个节点计算三级综合得分"""
        now = time.time()
        results = []

        for node in nodes:
            mu = node.belief.proficiency_mean if node.belief else 0.5
            attempts = node.practice_summary.total_attempts if node.practice_summary else 0
            last_ts = node.practice_summary.last_practiced if node.practice_summary else None
            days_since = (now - last_ts) / 86400.0 if last_ts else 0.0
            urgency = node.scheduling.urgency if node.scheduling else 0.0
            node.trend.stagnation_days if node.trend else 0.0

            # ── 三级得分 ──
            if mode == "review":
                review_score = urgency
                zpd_score = 0.0
                explore_score = 0.0
            elif mode == "explore":
                review_score = 0.0
                zpd_score = 0.0
                explore_score = 1.0 - min(attempts / MAX_ATTEMPTS_NORMALIZE, 1.0)
            elif mode == "challenge":
                review_score = 0.0
                zpd_score = max(0.0, mu - 0.7) * 3.0  # >0.7 的优先
                explore_score = 0.0
            else:
                # adaptive 模式：平衡三方面
                # 复习：urgency 越高越该复习
                review_score = urgency
                # ZPD：0.3-0.7 之间的"甜点区"
                if mu < MASTERY_LOWER:
                    zpd_score = 0.0  # 还太弱，不适合练习
                elif mu > MASTERY_UPPER:
                    zpd_score = 0.0  # 已掌握，留给复习
                else:
                    # 越接近 0.5 越高
                    zpd_score = 1.0 - abs(mu - 0.5) * 5.0
                # 探索：没练过的优先
                explore_score = 1.0 - min(attempts / MAX_ATTEMPTS_NORMALIZE, 1.0)

            # ── 综合得分 ──
            total = (
                review_score * REVIEW_WEIGHT
                + zpd_score * ZPD_WEIGHT
                + explore_score * EXPLORE_WEIGHT
            )

            results.append({
                "node": node,
                "review_score": round(review_score, 3),
                "zpd_score": round(zpd_score, 3),
                "explore_score": round(explore_score, 3),
                "total_score": round(total, 3),
                "days_since": round(days_since, 1),
            })

        return results

    @staticmethod
    def _to_review_result(node: CognitiveNode, item: dict) -> ReviewResult:
        """评分项 → ReviewResult"""
        mu = node.belief.proficiency_mean if node.belief else 0.5
        urgency = node.scheduling.urgency if node.scheduling else 0.0
        stagnation = node.trend.stagnation_days if node.trend else 0.0
        direction = node.trend.direction if node.trend else "stable"
        attempts = node.practice_summary.total_attempts if node.practice_summary else 0

        # 生成可读 reason
        reasons = []
        if item["review_score"] > 0.3:
            reasons.append(f"复习紧迫度 {item['review_score']:.2f}")
        if item["zpd_score"] > 0.3:
            reasons.append("处于学习甜点区")
        if attempts == 0:
            reasons.append("未练习过")
        elif item["explore_score"] > 0.3:
            reasons.append(f"仅练习 {attempts} 次")

        # next_action_type
        if urgency > 0.7:
            action_type = "review"
        elif mu < 0.5:
            action_type = "practice"
        else:
            action_type = "challenge"

        next_review = node.scheduling.next_review if node.scheduling else 0.0
        interval_days = max((next_review - (node.practice_summary.last_practiced or 0)) / 86400.0, 1.0) if next_review > 0 and node.practice_summary.last_practiced else 1.0

        return ReviewResult(
            node_id=node.id,
            label=node.label,
            level=node.level,
            proficiency_mean=mu,
            urgency=urgency,
            next_review=next_review,
            interval_days=round(interval_days, 1),
            ease_factor=2.5,
            stagnation_days=stagnation,
            direction=direction,
            action_type=action_type,
            reason="; ".join(reasons) if reasons else "常规练习",
        )


# 全局实例
adaptive_selector = AdaptiveSelector()

"""分析洞察层 — 18 个教育分析函数

所有函数遵循统一签名:
    analyze_xxx(user_id, scope=None, options=None) -> AnalysisResult

设计原则:
1. SQL 层优先过滤 → 内存一次遍历聚合 → 无 N+1
2. 归一化评分 (norm_urgency) 使策略引擎可跨类型比较
3. 空数据/冷启动返回 data_quality="cold_start"，不抛异常
4. 所有函数直接调 cognitive/storage.py，无中间抽象层
"""

from __future__ import annotations

from app.shared.constants import DEFAULT_USER_ID
import logging
import time
from collections import defaultdict

from app.cognitive.storage import (
    get_subtree,
    list_all_nodes,
)
from app.cognitive.models import CognitiveNode
from .models import (
    AnalysisMeta,
    AnalysisResult,
    AnalyzeOptions,
    ScoredInsight,
    ScopeSpec,
    compute_priority,
    normalize_value,
)

logger = logging.getLogger(__name__)

_USER_ID_DEFAULT = DEFAULT_USER_ID


# ════════════════════════════════════════════
# 内部辅助
# ════════════════════════════════════════════


def _resolve_scope(
    scope: ScopeSpec | None,
    user_id: str,
) -> tuple[list[CognitiveNode], list[CognitiveNode], AnalysisMeta]:
    """解析 scope，返回 (atom_nodes, parent_nodes, meta)"""
    sc = scope or ScopeSpec(level="user")

    if sc.level == "user":
        all_nodes = list_all_nodes(user_id)
        atoms = [n for n in all_nodes if n.level == "atom"]
        parents = [n for n in all_nodes if n.level in ("concept", "topic", "domain")]
        meta = AnalysisMeta(scope=sc, source_nodes=len(all_nodes))
        return atoms, parents, meta

    # 指定 scope：查子树
    subtree = get_subtree(sc.node_id, user_id)
    if not subtree:
        return [], [], AnalysisMeta(
            scope=sc, source_nodes=0, data_quality="cold_start"
        )
    atoms = [n for n in subtree.values() if n.level == "atom"]
    parents = [n for n in subtree.values() if n.level in ("concept", "topic", "domain")]
    meta = AnalysisMeta(scope=sc, source_nodes=len(subtree))
    return atoms, parents, meta


def _get_nodes(
    user_id: str,
    scope: ScopeSpec | None = None,
) -> list[CognitiveNode]:
    """获取指定范围内的所有 CognitiveNode"""
    sc = scope or ScopeSpec(level="user")
    if sc.level == "user":
        return list_all_nodes(user_id)
    subtree = get_subtree(sc.node_id, user_id)
    return list(subtree.values()) if subtree else []


def _build_insight(
    node: CognitiveNode,
    primary_value: float,
    primary_label: str,
    value_type: str,
    extra: dict | None = None,
) -> ScoredInsight:
    """从 CognitiveNode 构建 ScoredInsight"""
    # 提取趋势
    trend = "stable"
    if node.trend:
        trend = node.trend.direction or "stable"

    # 提取错误模式
    top_error = ""
    if node.error_clusters:
        sorted_errors = sorted(
            node.error_clusters,
            key=lambda e: getattr(e, "count", 0),
            reverse=True,
        )
        if sorted_errors:
            top_error = str(sorted_errors[0].cluster_id if hasattr(sorted_errors[0], 'cluster_id') else sorted_errors[0])

    # 置信度
    confidence = 1.0
    data_points = 0
    if node.belief:
        precision = node.belief.alpha + node.belief.beta
        confidence = min(precision / 20.0, 1.0)
        data_points = int(precision - 2) if precision > 2 else 0
    if node.practice_summary:
        data_points = max(data_points, node.practice_summary.total_attempts)

    norm_urg = normalize_value(primary_value, value_type)

    return ScoredInsight(
        node_id=node.id,
        label=node.label or node.id,
        level=node.level,
        parent_path=_build_parent_path(node),
        primary_value=primary_value,
        primary_label=primary_label,
        norm_urgency=norm_urg,
        norm_priority=compute_priority(norm_urg, confidence, data_points),
        confidence=confidence,
        data_points=data_points,
        trend=trend,
        top_error_pattern=top_error,
        extra=extra or {},
    )


def _build_parent_path(node: CognitiveNode) -> list[str]:
    """构建层级路径"""
    # 通过 parent 字段构建（需要额外查询才能拿到 label，这里先用 id）
    path = []
    if node.parent:
        path.append(node.parent)
    # 无法递归获取更上层（避免 N+1），caller 需要时自行 enrich
    return path


def _cold_result(analysis_type: str) -> AnalysisResult:
    """冷启动空结果"""
    return AnalysisResult(
        analysis_type=analysis_type,
        meta=AnalysisMeta(
            scope=ScopeSpec(level="user"),
            source_nodes=0,
            data_quality="cold_start",
        ),
        summary="数据不足，尚无法生成分析",
    )


# ════════════════════════════════════════════
# 1. 薄弱诊断类
# ════════════════════════════════════════════


def find_weakness_clusters(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """发现薄弱知识点簇 — 按父节点分组的薄弱 atom 聚合"""
    opts = options or AnalyzeOptions()
    atoms, parents, meta = _resolve_scope(scope, user_id)
    if not atoms:
        return _cold_result("find_weakness_clusters")

    # SQL 层已查全量，内存过滤
    weak = [
        n for n in atoms
        if n.belief and n.belief.proficiency_mean < opts.threshold
    ]
    if not weak:
        return AnalysisResult(
            analysis_type="find_weakness_clusters",
            meta=meta,
            summary="未发现低于阈值的薄弱知识点",
        )

    # 按 parent 聚类
    clusters: dict[str, list[CognitiveNode]] = defaultdict(list)
    for node in weak:
        parent_key = node.parent or "_orphan"
        clusters[parent_key].append(node)

    items: list[ScoredInsight] = []
    for parent_id, nodes in clusters.items():
        avg_prof = sum(n.belief.proficiency_mean for n in nodes) / len(nodes)
        # 合并错误模式
        error_counter: dict[str, int] = defaultdict(int)
        for n in nodes:
            for ec in (n.error_clusters or []):
                eid = str(ec.cluster_id if hasattr(ec, 'cluster_id') else ec)
                if eid:
                    error_counter[eid] += 1
        top_error = max(error_counter, key=error_counter.get) if error_counter else ""

        # 多数决趋势
        trends = [n.trend.direction if n.trend else "stable" for n in nodes]
        majority_trend = max(set(trends), key=trends.count)

        items.append(ScoredInsight(
            node_id=parent_id,
            label=parent_id,
            level="concept",
            parent_path=[],
            primary_value=avg_prof,
            primary_label="平均掌握度",
            norm_urgency=normalize_value(avg_prof, "proficiency"),
            norm_priority=compute_priority(
                normalize_value(avg_prof, "proficiency"),
                min(len(nodes) / 10, 1.0),
                len(nodes),
            ),
            confidence=min(len(nodes) / 5, 1.0),
            data_points=sum(n.belief.alpha + n.belief.beta - 2 if n.belief else 0 for n in nodes),
            trend=majority_trend,
            top_error_pattern=top_error,
            extra={"weak_atom_count": len(nodes)},
        ))

    items.sort(key=lambda x: x.norm_priority, reverse=True)
    items = items[:opts.max_items]

    return AnalysisResult(
        analysis_type="find_weakness_clusters",
        meta=AnalysisMeta(
            scope=meta.scope,
            source_nodes=len(weak),
            data_quality="high" if len(weak) > 5 else "low",
            computed_at=time.time(),
        ),
        items=items,
        summary=f"发现 {len(items)} 个薄弱概念簇，共 {len(weak)} 个薄弱原子知识点",
        top_priority=items[0].label if items else None,
    )


def detect_stagnant_topics(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """检测停滞知识点 — trend.stagnation_days > 阈值"""
    opts = options or AnalyzeOptions()
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("detect_stagnant_topics")

    stagnant = []
    for n in nodes:
        if n.trend and n.trend.stagnation_days >= 3:
            stagnant.append(_build_insight(
                n,
                primary_value=n.trend.stagnation_days,
                primary_label="停滞天数",
                value_type="stagnation_days",
                extra={"stagnation_days": n.trend.stagnation_days},
            ))

    stagnant.sort(key=lambda x: x.norm_urgency, reverse=True)
    stagnant = stagnant[:opts.max_items]

    return AnalysisResult(
        analysis_type="detect_stagnant_topics",
        meta=AnalysisMeta(
            scope=scope or ScopeSpec(level="user"),
            source_nodes=len(stagnant),
        ),
        items=stagnant,
        summary=f"发现 {len(stagnant)} 个停滞知识点",
        top_priority=stagnant[0].label if stagnant else None,
    )


def trace_proficiency_regression(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """掌握度退步追踪 — trend.velocity_ewma < 0 且下降幅度显著"""
    opts = options or AnalyzeOptions()
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("trace_proficiency_regression")

    regressed = []
    for n in nodes:
        if n.trend and n.activation:
            velocity = n.trend.velocity_ewma
            retrieval = n.activation.retrieval_prob
            if velocity < -0.05 or (velocity < 0 and retrieval < 0.3):
                regressed.append(_build_insight(
                    n,
                    primary_value=velocity,
                    primary_label="变化速度",
                    value_type="proficiency",
                    extra={
                        "velocity": velocity,
                        "retrieval_prob": retrieval,
                    },
                ))

    regressed.sort(key=lambda x: x.primary_value)
    regressed = regressed[:opts.max_items]

    return AnalysisResult(
        analysis_type="trace_proficiency_regression",
        meta=AnalysisMeta(
            scope=scope or ScopeSpec(level="user"),
            source_nodes=len(regressed),
        ),
        items=regressed,
        summary=f"追踪到 {len(regressed)} 个退步知识点",
        top_priority=regressed[0].label if regressed else None,
    )


# ════════════════════════════════════════════
# 2. 认知评估
# ════════════════════════════════════════════


def assess_current_burden(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """评估当前认知负荷 — 综合 cognitive_load + 最近练习成功率"""
    opts = options or AnalyzeOptions()
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("assess_current_burden")

    loaded = []
    for n in nodes:
        if n.cognitive_load:
            intrinsic = n.cognitive_load.intrinsic
            effective = intrinsic + (n.cognitive_load.dynamic or 0.0)

            # 结合最近成功率修正
            success_rate = 0.5
            if n.practice_summary:
                sr = n.practice_summary.recent_success_rate_7d
                if sr > 0:
                    success_rate = sr
                    # 低成功率 + 高负荷 = 更严重
                    if success_rate < 0.5:
                        effective = min(1.0, effective * 1.3)

            if effective > 0.4:
                loaded.append(_build_insight(
                    n,
                    primary_value=effective,
                    primary_label="认知负荷",
                    value_type="cognitive_load",
                    extra={"success_rate": success_rate},
                ))

    if not loaded:
        return AnalysisResult(
            analysis_type="assess_current_burden",
            meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=0),
            summary="当前认知负荷正常",
        )

    loaded.sort(key=lambda x: x.norm_urgency, reverse=True)
    max_burden = loaded[0].norm_urgency if loaded else 0

    return AnalysisResult(
        analysis_type="assess_current_burden",
        meta=AnalysisMeta(
            scope=scope or ScopeSpec(level="user"),
            source_nodes=len(loaded),
            data_quality="high" if len(loaded) > 3 else "low",
        ),
        items=loaded[:opts.max_items],
        summary=f"认知负荷水平: {max_burden:.0%}",
        top_priority=f"负荷最高: {loaded[0].label}" if loaded else None,
    )


def predict_fatigue_risk(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """疲劳风险预测 — 基于 cognitive_load + engagement.effort_estimate"""
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("predict_fatigue_risk")

    fatigue_nodes = []
    for n in nodes:
        load = n.cognitive_load
        eng = n.engagement
        if load and eng:
            combined = (load.intrinsic + load.dynamic) * (eng.effort_estimate or 0.5)
            if combined > 0.5:
                fatigue_nodes.append(_build_insight(
                    n,
                    primary_value=combined,
                    primary_label="疲劳风险",
                    value_type="cognitive_load",
                    extra={"effort": eng.effort_estimate, "load_intrinsic": load.intrinsic},
                ))

    fatigue_nodes.sort(key=lambda x: x.norm_urgency, reverse=True)
    return AnalysisResult(
        analysis_type="predict_fatigue_risk",
        meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=len(fatigue_nodes)),
        items=fatigue_nodes[:5],
        summary=f"发现 {len(fatigue_nodes)} 个高疲劳风险节点" if fatigue_nodes else "未检测到疲劳风险",
        top_priority=fatigue_nodes[0].label if fatigue_nodes else None,
    )


# ════════════════════════════════════════════
# 3. 遗忘风险
# ════════════════════════════════════════════


def rank_forgetting_risk(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """遗忘概率排序 — 基于 activation.retrieval_prob + scheduling.urgency"""
    opts = options or AnalyzeOptions()
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("rank_forgetting_risk")

    forgetting = []
    for n in nodes:
        if not (n.activation and n.scheduling):
            continue

        retrieval = n.activation.retrieval_prob or 0.0
        urgency = n.scheduling.urgency or 0.0

        # 遗忘风险 = (1 - retrieval) * (1 + urgency) 的加权
        risk = (1.0 - retrieval) * (1.0 + urgency * 0.5)

        if risk > 0.3:
            forgetting.append(_build_insight(
                n,
                primary_value=risk,
                primary_label="遗忘风险",
                value_type="forgetting_risk",
                extra={
                    "retrieval_prob": retrieval,
                    "urgency": urgency,
                    "next_review": n.scheduling.next_review if n.scheduling else 0,
                },
            ))

    forgetting.sort(key=lambda x: x.norm_urgency, reverse=True)
    forgetting = forgetting[:opts.max_items]

    return AnalysisResult(
        analysis_type="rank_forgetting_risk",
        meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=len(forgetting)),
        items=forgetting,
        summary=f"高遗忘风险: {len(forgetting)} 个知识点",
        top_priority=forgetting[0].label if forgetting else None,
    )


def predict_optimal_review(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """最优复习时机预测 — 基于 scheduling.next_review 接近当前时间"""
    opts = options or AnalyzeOptions()
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("predict_optimal_review")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).timestamp()

    review_items = []
    for n in nodes:
        if n.scheduling and n.scheduling.next_review:
            due = n.scheduling.next_review
            delta_hours = (due - now) / 3600
            # 越接近 due，紧急度越高（到期前后 48h 窗口）
            if -24 <= delta_hours <= 48:
                urgency = 1.0 - abs(delta_hours) / 48.0
                review_items.append(_build_insight(
                    n,
                    primary_value=delta_hours,
                    primary_label="到期剩余小时",
                    value_type="forgetting_risk",
                    extra={"delta_hours": delta_hours, "next_review": due},
                ))
                # override norm_urgency with our computed value
                review_items[-1].norm_urgency = urgency

    review_items.sort(key=lambda x: x.norm_urgency, reverse=True)
    review_items = review_items[:opts.max_items]

    return AnalysisResult(
        analysis_type="predict_optimal_review",
        meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=len(review_items)),
        items=review_items,
        summary=f"即将到期: {len(review_items)} 个知识点",
        top_priority=review_items[0].label if review_items else None,
    )


def find_overdue_reviews(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """过期复习项 — scheduling.next_review < now"""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).timestamp()

    opts = options or AnalyzeOptions()
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("find_overdue_reviews")

    overdue = []
    for n in nodes:
        if n.scheduling and n.scheduling.next_review:
            if n.scheduling.next_review < now:
                overdue.append(_build_insight(
                    n,
                    primary_value=now - n.scheduling.next_review,
                    primary_label="过期时长(秒)",
                    value_type="stagnation_days",
                    extra={"next_review": n.scheduling.next_review},
                ))

    overdue.sort(key=lambda x: x.norm_urgency, reverse=True)
    overdue = overdue[:opts.max_items]

    return AnalysisResult(
        analysis_type="find_overdue_reviews",
        meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=len(overdue)),
        items=overdue,
        summary=f"过期未复习: {len(overdue)} 个知识点",
        top_priority=overdue[0].label if overdue else None,
    )


# ════════════════════════════════════════════
# 4. 错误分析
# ════════════════════════════════════════════


def analyze_error_patterns(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """错误模式聚类分析 — 聚合所有节点的 error_clusters"""
    opts = options or AnalyzeOptions()
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("analyze_error_patterns")

    # 按错误类型聚合
    pattern_nodes: dict[str, list[CognitiveNode]] = defaultdict(list)
    for n in nodes:
        for ec in (n.error_clusters or []):
            eid = str(ec.cluster_id if hasattr(ec, 'cluster_id') else ec)
            if eid:
                pattern_nodes[eid].append(n)

    items = []
    for pattern, involved in pattern_nodes.items():
        # 涉及该错误的总次数
        total_count = sum(
            ec.count if hasattr(ec, 'count') else 1
            for n in involved
            for ec in (n.error_clusters or [])
        )
        avg_belief = sum(
            n.belief.proficiency_mean for n in involved if n.belief
        ) / len(involved) if involved else 0.5

        items.append(ScoredInsight(
            node_id=f"error:{pattern}",
            label=pattern,
            level="concept",
            primary_value=total_count,
            primary_label="错误次数",
            norm_urgency=normalize_value(total_count / 50.0, "error_frequency"),
            norm_priority=compute_priority(
                normalize_value(total_count / 50.0, "error_frequency"),
                min(len(involved) / 5, 1.0),
                total_count,
            ),
            confidence=min(total_count / 10, 1.0),
            data_points=total_count,
            extra={"involved_nodes": len(involved), "avg_proficiency": avg_belief},
        ))

    items.sort(key=lambda x: x.norm_priority, reverse=True)
    items = items[:opts.max_items]

    return AnalysisResult(
        analysis_type="analyze_error_patterns",
        meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=len(nodes)),
        items=items,
        summary=f"发现 {len(items)} 种主要错误模式",
        top_priority=items[0].label if items else None,
    )


# ════════════════════════════════════════════
# 5. 进展画像
# ════════════════════════════════════════════


def compute_progress_delta(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """进步量化 — 掌握度变化 + 练习量 + streak"""
    opts = options or AnalyzeOptions()
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("compute_progress_delta")

    improved = []
    for n in nodes:
        if n.belief and n.trend:
            velocity = n.trend.velocity_ewma
            if velocity > 0.05:
                improved.append(_build_insight(
                    n,
                    primary_value=velocity,
                    primary_label="进步速度",
                    value_type="proficiency",
                    extra={"current_prof": n.belief.proficiency_mean},
                ))
                # 进步越大 norm_urgency 越低（好事），用反向
                improved[-1].norm_urgency = 1.0 - min(velocity, 1.0)

    improved.sort(key=lambda x: x.norm_urgency)  # 最低 = 进步最大
    improved = improved[:opts.max_items]

    # 全局 streak
    streak = 0
    xp = 0.0
    for n in nodes:
        if n.engagement:
            streak = max(streak, n.engagement.streak_current or 0)
            xp += n.engagement.xp or 0.0

    return AnalysisResult(
        analysis_type="compute_progress_delta",
        meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=len(improved)),
        items=improved,
        summary=f"进步知识点: {len(improved)}, 连续学习: {streak}天, 总XP: {xp:.0f}",
        top_priority=f"最大进步: {improved[0].label}" if improved else "稳步进行中",
    )


def profile_learning_rhythm(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """学习节奏画像 — 基于 engagement + 元认知"""
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("profile_learning_rhythm")

    total_streak = 0
    total_effort = 0.0
    overconfident = 0
    underconfident = 0

    for n in nodes:
        if n.engagement:
            total_streak = max(total_streak, n.engagement.streak_current or 0)
            total_effort += n.engagement.effort_estimate or 0.0
        if n.metacognition:
            if n.metacognition.direction == "overconfident":
                overconfident += 1
            elif n.metacognition.direction == "underconfident":
                underconfident += 1

    avg_effort = total_effort / len(nodes) if nodes else 0.5
    cal_status = "accurate"
    if overconfident > underconfident * 2:
        cal_status = "overconfident"
    elif underconfident > overconfident * 2:
        cal_status = "underconfident"

    return AnalysisResult(
        analysis_type="profile_learning_rhythm",
        meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=len(nodes)),
        items=[
            ScoredInsight(
                node_id="rhythm:streak",
                label="学习连续性",
                level="user",
                primary_value=total_streak,
                primary_label="连续天数",
                norm_urgency=0.0,
                norm_priority=0.0,
                extra={"streak": total_streak},
            ),
            ScoredInsight(
                node_id="rhythm:calibration",
                label=f"元认知校准: {cal_status}",
                level="user",
                primary_value=1.0 if cal_status == "accurate" else 0.5,
                primary_label="校准状态",
                norm_urgency=0.0,
                norm_priority=0.0,
                extra={"overconfident": overconfident, "underconfident": underconfident},
            ),
            ScoredInsight(
                node_id="rhythm:effort",
                label="平均努力程度",
                level="user",
                primary_value=avg_effort,
                primary_label="努力系数",
                norm_urgency=0.0,
                norm_priority=0.0,
                extra={"avg_effort": avg_effort},
            ),
        ],
        summary=f"学习节奏: 连续{total_streak}天, 校准{cal_status}",
    )


# ════════════════════════════════════════════
# 6. 跨域关联
# ════════════════════════════════════════════


def find_cross_domain_bridges(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """薄弱→优势跨域连接 — 基于 deep_links"""
    opts = options or AnalyzeOptions()
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("find_cross_domain_bridges")

    bridges = []
    for n in nodes:
        if n.deep_links:
            for link in n.deep_links:
                if link.strength > 0.3 and link.domain:
                    bridges.append(ScoredInsight(
                        node_id=n.id,
                        label=n.label or n.id,
                        level=n.level,
                        primary_value=link.strength,
                        primary_label="连接强度",
                        norm_urgency=0.0,  # 跨域连接不产生紧迫
                        norm_priority=0.0,
                        extra={
                            "target": link.target,
                            "target_domain": link.domain,
                            "link_type": link.type,
                        },
                    ))

    bridges.sort(key=lambda x: x.primary_value, reverse=True)
    return AnalysisResult(
        analysis_type="find_cross_domain_bridges",
        meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=len(bridges)),
        items=bridges[:opts.max_items],
        summary=f"发现 {len(bridges)} 条跨域连接",
    )


# ════════════════════════════════════════════
# 7. 元认知 & 目标
# ════════════════════════════════════════════


def detect_calibration_mismatch(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """过度自信/不足检测 — metacognition.calibration_error"""
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("detect_calibration_mismatch")

    mismatched = []
    for n in nodes:
        if n.metacognition:
            err = n.metacognition.calibration_error
            direction = n.metacognition.direction
            if abs(err) > 0.2 or direction != "accurate":
                mismatched.append(_build_insight(
                    n,
                    primary_value=err,
                    primary_label=f"校准偏差({direction})",
                    value_type="proficiency",
                    extra={"calibration_direction": direction},
                ))

    mismatched.sort(key=lambda x: abs(x.primary_value), reverse=True)
    return AnalysisResult(
        analysis_type="detect_calibration_mismatch",
        meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=len(mismatched)),
        items=mismatched[:opts.max_items] if opts else mismatched[:10],
        summary=f"偏差: {len(mismatched)} 个知识点",
    )


def assess_goal_distance(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """目标差距评估 — goal_alignment"""
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("assess_goal_distance")

    goals = []
    for n in nodes:
        if n.goal_alignment and n.goal_alignment.toward_goal:
            goals.append(ScoredInsight(
                node_id=n.id,
                label=f"{n.label or n.id} → {n.goal_alignment.toward_goal}",
                level=n.level,
                primary_value=n.goal_alignment.distance,
                primary_label=f"距目标距离 ({n.goal_alignment.toward_goal})",
                norm_urgency=min(n.goal_alignment.distance, 1.0),
                norm_priority=compute_priority(
                    min(n.goal_alignment.distance, 1.0),
                    0.7,
                    1,
                ),
                extra={"goal": n.goal_alignment.toward_goal, "on_critical_path": n.goal_alignment.on_critical_path},
            ))

    goals.sort(key=lambda x: x.norm_priority, reverse=True)
    return AnalysisResult(
        analysis_type="assess_goal_distance",
        meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=len(goals)),
        items=goals[:opts.max_items] if opts else goals[:10],
        summary=f"关联目标: {len(goals)} 个知识点",
    )


# ════════════════════════════════════════════
# 8. 预测偏差 & 路径 & 上下文
# ════════════════════════════════════════════


def detect_prediction_divergence(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """预期vs实际偏差 — prediction.prediction_error"""
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("detect_prediction_divergence")

    divergent = []
    for n in nodes:
        if n.prediction and n.prediction.error_flag:
            divergent.append(_build_insight(
                n,
                primary_value=n.prediction.prediction_error,
                primary_label="预测误差",
                value_type="proficiency",
                extra={"expected": n.prediction.top_down_mean},
            ))

    divergent.sort(key=lambda x: abs(x.primary_value), reverse=True)
    return AnalysisResult(
        analysis_type="detect_prediction_divergence",
        meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=len(divergent)),
        items=divergent[:opts.max_items] if opts else divergent[:10],
        summary=f"预测偏差: {len(divergent)} 个知识点",
    )


def suggest_learning_path_step(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """下一步最优路径 — 基于 prerequisites + unlocks + 掌握度"""
    opts = options or AnalyzeOptions()
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("suggest_learning_path_step")

    # 找"已满足前置条件但未掌握"的知识点
    node_map = {n.id: n for n in nodes}
    candidates = []
    for n in nodes:
        if not n.prerequisites:
            continue
        prereq_ids = [str(p.id) if hasattr(p, 'id') else str(p) for p in n.prerequisites]
        if not prereq_ids:
            continue

        # 检查前置条件是否都已掌握
        all_met = True
        for pid in prereq_ids:
            prereq = node_map.get(pid)
            if prereq and prereq.belief:
                if prereq.belief.proficiency_mean < 0.7:
                    all_met = False
                    break

        if all_met and n.belief:
            mastery_gap = 1.0 - n.belief.proficiency_mean
            if mastery_gap > 0.2:
                candidates.append(_build_insight(
                    n,
                    primary_value=mastery_gap,
                    primary_label="掌握度缺口",
                    value_type="proficiency",
                ))

    candidates.sort(key=lambda x: x.norm_urgency, reverse=True)
    candidates = candidates[:opts.max_items]

    return AnalysisResult(
        analysis_type="suggest_learning_path_step",
        meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=len(candidates)),
        items=candidates,
        summary=f"推荐 {len(candidates)} 个下一步知识点" if candidates else "未找到适合的下一步",
        top_priority=candidates[0].label if candidates else None,
    )


def extract_recent_context(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """近期讨论摘要 — dialogue_contexts"""
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("extract_recent_context")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).timestamp()

    recent = []
    for n in nodes:
        if n.dialogue_contexts:
            for dc in n.dialogue_contexts:
                if dc.last_discussed and (now - dc.last_discussed) < 86400 * 7:  # 7天内
                    recent.append(ScoredInsight(
                        node_id=n.id,
                        label=n.label or n.id,
                        level=n.level,
                        primary_value=dc.relevance_score or 0.5,
                        primary_label="相关度",
                        norm_urgency=0.0,
                        norm_priority=0.0,
                        extra={
                            "last_discussed": dc.last_discussed,
                            "summary": dc.summary_text or "",
                            "session_id": dc.session_id,
                        },
                    ))
                    break  # 每节点只取一个

    return AnalysisResult(
        analysis_type="extract_recent_context",
        meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=len(recent)),
        items=recent[:10],
        summary=f"近期讨论: {len(recent)} 个知识点" if recent else "最近无讨论",
    )


# ════════════════════════════════════════════
# 9. 推荐排序（多因素融合）
# ════════════════════════════════════════════


def rank_recommendations(
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """多因素融合推荐 — 综合遗忘风险 + 薄弱 + 停滞 + 过期复习"""
    opts = options or AnalyzeOptions()
    nodes = _get_nodes(user_id, scope)
    if not nodes:
        return _cold_result("rank_recommendations")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).timestamp()

    scored: list[ScoredInsight] = []
    for n in nodes:
        urgency = 0.0

        # 因素1: 掌握度低
        if n.belief:
            mastery_urg = 1.0 - n.belief.proficiency_mean
            urgency += mastery_urg * 0.3

        # 因素2: 遗忘风险
        if n.activation:
            forgetting = 1.0 - (n.activation.retrieval_prob or 0.5)
            urgency += forgetting * 0.25

        # 因素3: 过期复习
        if n.scheduling and n.scheduling.next_review:
            if n.scheduling.next_review < now:
                overdue = (now - n.scheduling.next_review) / 86400  # 天
                urgency += min(overdue * 0.1, 0.25)

        # 因素4: 停滞
        if n.trend and n.trend.stagnation_days > 3:
            urgency += min(n.trend.stagnation_days * 0.02, 0.2)

        if urgency > 0.2:
            scored.append(_build_insight(
                n,
                primary_value=urgency,
                primary_label="综合推荐分",
                value_type="proficiency",
            ))
            # 直接用 urgency 作为 norm_urgency
            scored[-1].norm_urgency = min(urgency, 1.0)

    scored.sort(key=lambda x: x.norm_urgency, reverse=True)
    scored = scored[:opts.max_items]

    return AnalysisResult(
        analysis_type="rank_recommendations",
        meta=AnalysisMeta(scope=scope or ScopeSpec(level="user"), source_nodes=len(scored)),
        items=scored,
        summary=f"推荐 {len(scored)} 个优先处理项",
        top_priority=scored[0].label if scored else None,
    )


# ════════════════════════════════════════════
# 分析函数注册表（便于反射调用）
# ════════════════════════════════════════════

ANALYSIS_REGISTRY: dict[str, callable] = {
    "find_weakness_clusters": find_weakness_clusters,
    "detect_stagnant_topics": detect_stagnant_topics,
    "trace_proficiency_regression": trace_proficiency_regression,
    "assess_current_burden": assess_current_burden,
    "predict_fatigue_risk": predict_fatigue_risk,
    "rank_forgetting_risk": rank_forgetting_risk,
    "predict_optimal_review": predict_optimal_review,
    "find_overdue_reviews": find_overdue_reviews,
    "analyze_error_patterns": analyze_error_patterns,
    "compute_progress_delta": compute_progress_delta,
    "profile_learning_rhythm": profile_learning_rhythm,
    "find_cross_domain_bridges": find_cross_domain_bridges,
    "detect_calibration_mismatch": detect_calibration_mismatch,
    "assess_goal_distance": assess_goal_distance,
    "detect_prediction_divergence": detect_prediction_divergence,
    "suggest_learning_path_step": suggest_learning_path_step,
    "extract_recent_context": extract_recent_context,
    "rank_recommendations": rank_recommendations,
}


def run_analysis(
    analysis_name: str,
    user_id: str = _USER_ID_DEFAULT,
    scope: ScopeSpec | None = None,
    options: AnalyzeOptions | None = None,
) -> AnalysisResult:
    """通过名称运行指定的分析函数"""
    fn = ANALYSIS_REGISTRY.get(analysis_name)
    if fn is None:
        raise ValueError(f"未知分析函数: {analysis_name}")
    return fn(user_id=user_id, scope=scope, options=options)

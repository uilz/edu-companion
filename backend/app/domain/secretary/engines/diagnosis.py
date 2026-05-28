"""诊断引擎 — 基于分析层多函数结果融合的综合诊断

工作流程:
  1. 调用 6 个分析函数获取多维度洞察
  2. 去重 + 归一化排序（使用 norm_urgency）
  3. LLM 生成 highlight 和 summary
  4. 组装 DiagnosisReport
"""

from __future__ import annotations

import logging
from typing import Any

from app.shared.constants import DEFAULT_USER_ID
from ..models import (
    DiagnosisReport,
    ScopeSpec,
    WeakPoint,
)
from ..analysis import (
    find_weakness_clusters,
    detect_stagnant_topics,
    trace_proficiency_regression,
    assess_current_burden,
    detect_calibration_mismatch,
    detect_prediction_divergence,
    compute_progress_delta,
)

logger = logging.getLogger(__name__)

_USER_ID_DEFAULT = DEFAULT_USER_ID


class DiagnosisEngine:
    """诊断引擎 — 综合分析层产出，生成诊断报告"""

    async def diagnose(
        self,
        user_id: str = _USER_ID_DEFAULT,
        scope: ScopeSpec | None = None,
    ) -> DiagnosisReport:
        """执行全量诊断"""
        # 并行收集各项洞察
        weakness = find_weakness_clusters(user_id=user_id, scope=scope)
        stagnant = detect_stagnant_topics(user_id=user_id, scope=scope)
        regression = trace_proficiency_regression(user_id=user_id, scope=scope)
        burden = assess_current_burden(user_id=user_id, scope=scope)
        calibration = detect_calibration_mismatch(user_id=user_id, scope=scope)
        divergence = detect_prediction_divergence(user_id=user_id, scope=scope)
        progress = compute_progress_delta(user_id=user_id, scope=scope)

        # 融合 weak points
        seen_ids: set[str] = set()
        all_weak: list[WeakPoint] = []
        for insight in weakness.items:
            if insight.node_id not in seen_ids:
                seen_ids.add(insight.node_id)
                all_weak.append(WeakPoint.from_insight(insight))
        for insight in stagnant.items:
            if insight.node_id not in seen_ids:
                seen_ids.add(insight.node_id)
                all_weak.append(WeakPoint.from_insight(insight))
        for insight in regression.items:
            if insight.node_id not in seen_ids:
                seen_ids.add(insight.node_id)
                all_weak.append(WeakPoint.from_insight(insight))

        # 按 norm_urgency 排序
        all_sorted = sorted(
            weakness.items + stagnant.items + regression.items,
            key=lambda x: x.norm_urgency,
            reverse=True,
        )

        # 认知负荷
        cognitive_load = 0.0
        if burden.items:
            cognitive_load = burden.items[0].primary_value

        # 收集诊断来源
        source_findings = []
        if weakness.items:
            source_findings.append(f"weakness({len(weakness.items)}簇)")
        if stagnant.items:
            source_findings.append(f"stagnant({len(stagnant.items)}个)")
        if regression.items:
            source_findings.append(f"regression({len(regression.items)}个)")
        if calibration.items:
            source_findings.append(f"calibration偏差({len(calibration.items)}个)")
        if divergence.items:
            source_findings.append(f"预测偏差({len(divergence.items)}个)")

        # LLM 生成 highlight 和 summary（模板版，后续可升级为 LLM）
        highlight = self._generate_highlight(progress, all_weak)
        summary = self._generate_summary(all_weak, cognitive_load, calibration)

        return DiagnosisReport(
            user_id=user_id,
            weak_points=all_weak[:20],  # 最多 20 个
            cognitive_load=cognitive_load,
            highlight=highlight,
            summary=summary,
            source_findings=source_findings,
        )

    def _generate_highlight(self, progress_result, weak_list) -> str:
        """生成进步亮点（基于 compute_progress_delta）"""
        if progress_result.items:
            top = progress_result.items[0]
            if top.primary_value > 0:
                return f"🎉 {top.label} 进步明显，继续保持！"
        if not weak_list:
            return "✅ 当前未发现薄弱知识点，保持节奏即可"
        if len(weak_list) <= 3:
            return f"📈 薄弱知识点数量较少({len(weak_list)}个)，针对性练习即可攻克"
        return f"📊 检测到 {len(weak_list)} 个知识点有待加强，按优先级逐个突破"

    def _generate_summary(self, weak_list, cognitive_load, calibration) -> str:
        """生成诊断摘要"""
        parts = [f"当前检测到 {len(weak_list)} 个薄弱知识点"]
        if cognitive_load > 0.7:
            parts.append("，认知负荷偏高，建议适当休息")
        elif cognitive_load < 0.3:
            parts.append("，认知负荷正常，适合学习")

        if calibration.items:
            cal = calibration.items[0]
            if "overconfident" in cal.label:
                parts.append("，部分知识点存在过度自信倾向，建议多做练习验证")
            elif "underconfident" in cal.label:
                parts.append("，部分知识点信心不足，实际上已掌握，大胆尝试")

        return "。".join(parts) + "。"

    async def quick_assess(
        self,
        user_id: str = _USER_ID_DEFAULT,
    ) -> dict[str, Any]:
        """快速评估 — 轻量版，只返回最关键的指标"""
        burden = assess_current_burden(user_id=user_id)
        progress = compute_progress_delta(user_id=user_id)

        return {
            "cognitive_load": burden.items[0].primary_value if burden.items else 0.0,
            "weak_count": len(find_weakness_clusters(user_id=user_id).items),
            "stagnant_count": len(detect_stagnant_topics(user_id=user_id).items),
            "streak_days": int(progress.items[0].primary_value) if progress.items else 0,
            "summary": progress.summary,
        }

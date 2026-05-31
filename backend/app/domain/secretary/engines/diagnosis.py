"""诊断引擎 — 基于分析层多函数结果融合的综合诊断

工作流程:
  1. 一次加载 nodes 缓存
  2. 调用 7 个分析函数（共享缓存）
  3. 去重 + 归一化排序
  4. 组装 DiagnosisReport
"""

from __future__ import annotations

import logging
from typing import Any

from shared.constants import DEFAULT_USER_ID
from ..models import (
    DiagnosisReport,
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
    _get_nodes,
)

logger = logging.getLogger(__name__)


class DiagnosisEngine:
    """诊断引擎 — 综合分析层产出，生成诊断报告"""

    async def diagnose(
        self,
        user_id: str = DEFAULT_USER_ID,
    ) -> DiagnosisReport:
        """执行全量诊断 — 一次加载 nodes，共享给所有分析函数"""
        # 一次加载，避免 7 次重复查询
        nodes = _get_nodes(user_id)

        # 并行收集各项洞察（共享 nodes 缓存）
        weakness = find_weakness_clusters(user_id, nodes=nodes)
        stagnant = detect_stagnant_topics(user_id, nodes=nodes)
        regression = trace_proficiency_regression(user_id, nodes=nodes)
        burden = assess_current_burden(user_id, nodes=nodes)
        calibration = detect_calibration_mismatch(user_id, nodes=nodes)
        divergence = detect_prediction_divergence(user_id, nodes=nodes)
        progress = compute_progress_delta(user_id, nodes=nodes)

        # 融合 weak points
        seen_ids: set[str] = set()
        all_weak: list[WeakPoint] = []
        for item in weakness:
            if item["node_id"] not in seen_ids:
                seen_ids.add(item["node_id"])
                all_weak.append(WeakPoint(
                    node_id=item["node_id"],
                    label=item["label"],
                    mastery=item["mastery"],
                    source="weakness",
                ))
        for item in stagnant:
            if item["node_id"] not in seen_ids:
                seen_ids.add(item["node_id"])
                all_weak.append(WeakPoint(
                    node_id=item["node_id"],
                    label=item["label"],
                    mastery=0,
                    source="stagnant",
                    days_since=item.get("days_since", 0),
                ))
        for item in regression:
            if item["node_id"] not in seen_ids:
                seen_ids.add(item["node_id"])
                all_weak.append(WeakPoint(
                    node_id=item["node_id"],
                    label=item["label"],
                    mastery=0,
                    source="regression",
                ))

        # 按 mastery 排序（低→高 = 紧急→不紧急）
        all_weak.sort(key=lambda w: w.mastery)

        # 认知负荷
        burden_level = burden.get("burden_level", "low")
        cognitive_load = {"high": 0.8, "medium": 0.5, "low": 0.2}.get(burden_level, 0.2)

        # 收集诊断来源
        source_findings = []
        if weakness:
            source_findings.append(f"weakness({len(weakness)}簇)")
        if stagnant:
            source_findings.append(f"stagnant({len(stagnant)}个)")
        if regression:
            source_findings.append(f"regression({len(regression)}个)")
        if calibration:
            source_findings.append(f"calibration偏差({len(calibration)}个)")
        if divergence:
            source_findings.append(f"预测偏差({len(divergence)}个)")

        highlight = self._generate_highlight(progress, all_weak)
        summary = self._generate_summary(all_weak, cognitive_load, calibration)

        return DiagnosisReport(
            user_id=user_id,
            weak_points=all_weak[:20],
            cognitive_load=cognitive_load,
            highlight=highlight,
            summary=summary,
            source_findings=source_findings,
        )

    def _generate_highlight(self, progress: dict, weak_list: list) -> str:
        """生成进步亮点"""
        nodes_practiced = progress.get("nodes_practiced", 0)
        if nodes_practiced > 0:
            return f"🎉 最近 {progress.get('period_days', 7)} 天练习了 {nodes_practiced} 个知识点"
        if not weak_list:
            return "✅ 当前未发现薄弱知识点，保持节奏即可"
        if len(weak_list) <= 3:
            return f"📈 薄弱知识点数量较少({len(weak_list)}个)，针对性练习即可攻克"
        return f"📊 检测到 {len(weak_list)} 个知识点有待加强，按优先级逐个突破"

    def _generate_summary(self, weak_list: list, cognitive_load: float, calibration: list) -> str:
        """生成诊断摘要"""
        parts = [f"当前检测到 {len(weak_list)} 个薄弱知识点"]
        if cognitive_load > 0.7:
            parts.append("，认知负荷偏高，建议适当休息")
        elif cognitive_load < 0.3:
            parts.append("，认知负荷正常，适合学习")

        if calibration:
            cal = calibration[0]
            if cal.get("issue") == "high_mastery_low_confidence":
                parts.append("，部分知识点存在信心不足，建议多做练习巩固")

        return "。".join(parts) + "。"

    async def quick_assess(
        self,
        user_id: str = DEFAULT_USER_ID,
    ) -> dict[str, Any]:
        """快速评估 — 轻量版，只返回最关键的指标"""
        nodes = _get_nodes(user_id)
        burden = assess_current_burden(user_id, nodes=nodes)
        progress = compute_progress_delta(user_id, nodes=nodes)
        weakness = find_weakness_clusters(user_id, nodes=nodes)
        stagnant = detect_stagnant_topics(user_id, nodes=nodes)

        return {
            "cognitive_load": {"high": 0.8, "medium": 0.5, "low": 0.2}.get(burden.get("burden_level", "low"), 0.2),
            "weak_count": len(weakness),
            "stagnant_count": len(stagnant),
            "streak_days": progress.get("nodes_practiced", 0),
            "summary": f"薄弱{len(weakness)}个，停滞{len(stagnant)}个",
        }

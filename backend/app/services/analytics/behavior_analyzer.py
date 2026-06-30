"""
学习行为分析器

基于统计数据提取学习行为模式：
- 最佳学习时段
- 连续学习天数 (streak)
- 学习规律性
- 疲劳曲线
- 个性化建议
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any


class BehaviorReport:
    """行为分析报告"""

    def __init__(
        self,
        current_streak: int = 0,
        longest_streak: int = 0,
        best_study_hours: list[int] | None = None,
        regularity_score: float = 0.0,
        fatigue_drop_minute: int | None = None,
        total_sessions: int = 0,
        avg_session_minutes: float = 0.0,
        recommendations: list[str] | None = None,
    ):
        self.current_streak = current_streak
        self.longest_streak = longest_streak
        self.best_study_hours = best_study_hours or []
        self.regularity_score = regularity_score
        self.fatigue_drop_minute = fatigue_drop_minute
        self.total_sessions = total_sessions
        self.avg_session_minutes = avg_session_minutes
        self.recommendations = recommendations or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_streak": self.current_streak,
            "longest_streak": self.longest_streak,
            "best_study_hours": self.best_study_hours,
            "regularity_score": round(self.regularity_score, 2),
            "fatigue_drop_minute": self.fatigue_drop_minute,
            "total_sessions": self.total_sessions,
            "avg_session_minutes": round(self.avg_session_minutes, 1),
            "recommendations": self.recommendations,
        }


class LearningBehaviorAnalyzer:
    """
    学习行为分析引擎

    输入: daily_trend + hourly_heatmap + mastery_bars（来自 /stats 端点）
    输出: BehaviorReport
    """

    def analyze(
        self,
        daily_trend: list[dict[str, Any]],
        hourly_heatmap: list[dict[str, Any]],
        mastery_bars: list[dict[str, Any]],
        total_sessions: int = 0,
        total_minutes: float = 0.0,
    ) -> BehaviorReport:
        # 1. 连续学习天数
        current_streak, longest_streak = self._compute_streak(daily_trend)

        # 2. 最佳学习时段
        best_hours = self._find_best_hours(hourly_heatmap)

        # 3. 学习规律性
        regularity = self._compute_regularity(daily_trend)

        # 4. 疲劳曲线
        fatigue_drop = self._estimate_fatigue(hourly_heatmap)

        # 5. 平均会话
        avg_min = total_minutes / max(total_sessions, 1)

        # 6. 生成建议
        recs = self._generate_recommendations(
            current_streak=current_streak,
            best_hours=best_hours,
            regularity=regularity,
            fatigue_drop=fatigue_drop,
            mastery_bars=mastery_bars,
        )

        return BehaviorReport(
            current_streak=current_streak,
            longest_streak=longest_streak,
            best_study_hours=best_hours,
            regularity_score=regularity,
            fatigue_drop_minute=fatigue_drop,
            total_sessions=total_sessions,
            avg_session_minutes=avg_min,
            recommendations=recs,
        )

    # ── 连续天数 ──

    def _compute_streak(self, daily_trend: list[dict]) -> tuple[int, int]:
        """计算当前连续天数和历史最长连续天数"""
        if not daily_trend:
            return 0, 0

        # 只看有练习的天
        active_dates: set[str] = set()
        for d in daily_trend:
            if d.get("questions", 0) > 0:
                active_dates.add(d.get("date", ""))

        if not active_dates:
            return 0, 0

        today = datetime.now().strftime("%m-%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%m-%d")

        # 当前 streak：从今天往前数连续几天
        current = 0
        check = today
        while check in active_dates:
            current += 1
            dt = datetime.strptime(f"2026-{check}", "%Y-%m-%d") - timedelta(days=1)
            check = dt.strftime("%m-%d")
        # 如果今天没练但从昨天开始算，也算当前 streak
        if current == 0:
            check = yesterday
            while check in active_dates:
                current += 1
                dt = datetime.strptime(f"2026-{check}", "%Y-%m-%d") - timedelta(days=1)
                check = dt.strftime("%m-%d")

        # 最长 streak：扫描所有活跃日期找最长连续段
        sorted_dates = sorted(active_dates)
        longest = 1
        run = 1
        prev_dt = datetime.strptime(f"2026-{sorted_dates[0]}", "%Y-%m-%d")
        for date_str in sorted_dates[1:]:
            curr_dt = datetime.strptime(f"2026-{date_str}", "%Y-%m-%d")
            if (curr_dt - prev_dt).days == 1:
                run += 1
                longest = max(longest, run)
            else:
                run = 1
            prev_dt = curr_dt

        return current, longest

    # ── 最佳时段 ──

    def _find_best_hours(self, hourly_heatmap: list[dict]) -> list[int]:
        """找出做题量最多的 3 个时段"""
        if not hourly_heatmap:
            return []

        hour_counts: dict[int, int] = defaultdict(int)
        for cell in hourly_heatmap:
            h = cell.get("hour", 0)
            q = cell.get("questions", 0)
            if q > 0:
                hour_counts[h] += q

        sorted_hours = sorted(hour_counts.items(), key=lambda x: -x[1])
        return [h for h, _ in sorted_hours[:3]]

    # ── 规律性评分 ──

    def _compute_regularity(self, daily_trend: list[dict]) -> float:
        """
        学习规律性：标准差越小越规律
        0 = 完全不规律，1 = 每天固定时间固定量
        """
        active = [d for d in daily_trend if d.get("questions", 0) > 0]
        if len(active) < 3:
            return 0.0

        counts = [d.get("questions", 0) for d in active]
        mean = sum(counts) / len(counts)
        if mean == 0:
            return 0.0

        variance = sum((c - mean) ** 2 for c in counts) / len(counts)
        std = variance ** 0.5
        cv = std / mean  # 变异系数

        # cv < 0.3 → 很规律, cv > 1.0 → 很不规律
        score = max(0.0, 1.0 - cv)
        return min(1.0, score)

    # ── 疲劳估计 ──

    def _estimate_fatigue(self, hourly_heatmap: list[dict]) -> int | None:
        """
        估算疲劳开始时间：找到连续 2 个时段做题量下降的转折点
        返回大约分钟数（从第一个活跃时段开始算），没有明显疲劳返回 None
        """
        hours = sorted(set(c["hour"] for c in hourly_heatmap))
        if len(hours) < 3:
            return None

        # 聚合每个时段的总题量
        hour_q: dict[int, int] = defaultdict(int)
        for c in hourly_heatmap:
            hour_q[c["hour"]] += c.get("questions", 0)

        # 找下降点
        sorted_hr = sorted(hour_q.keys())
        for i in range(1, len(sorted_hr) - 1):
            prev = hour_q[sorted_hr[i - 1]]
            curr = hour_q[sorted_hr[i]]
            next_q = hour_q[sorted_hr[i + 1]]
            if curr > 0 and prev > 0 and curr < prev * 0.6 and next_q < curr:
                # 从这个时段对应的分钟估算
                return sorted_hr[i] * 60 + 30  # 取中值

        return None

    # ── 建议生成 ──

    def _generate_recommendations(
        self,
        current_streak: int,
        best_hours: list[int],
        regularity: float,
        fatigue_drop: int | None,
        mastery_bars: list[dict],
    ) -> list[str]:
        recs: list[str] = []

        # 最佳时段建议
        if best_hours:
            best_h = best_hours[0]
            label = f"上午{best_h}" if best_h < 12 else f"下午{best_h - 12}" if best_h < 18 else f"晚上{best_h - 12}"
            recs.append(f"你在{label}点左右效率最高，建议把重难点安排在这个时段 💡")

        # 连续天数
        if current_streak >= 7:
            recs.append(f"已连续学习{current_streak}天！你正在养成稳定的学习习惯 🔥")
        elif current_streak >= 3:
            recs.append(f"连续{current_streak}天学习了，坚持住！再坚持几天就会变成习惯 💪")
        elif current_streak < 3:
            recs.append("试着每天固定时间学习10分钟，养成习惯比一次学很久更重要 🌱")

        # 规律性
        if regularity < 0.3:
            recs.append("学习时间不太规律，试试固定一个时段（比如每天晚上8点）效果会更好 📅")
        elif regularity > 0.7:
            recs.append("你的学习节奏很规律，这是高效学习者的重要特质 ✨")

        # 疲劳
        if fatigue_drop and fatigue_drop < 40:
            recs.append(f"专注力大约在{fatigue_drop}分钟左右下降，建议用番茄钟：学25分钟休息5分钟 🍅")
        elif fatigue_drop and fatigue_drop < 90:
            recs.append(f"你的专注力可以持续约{fatigue_drop}分钟，状态不错！注意适时休息 🎯")

        # 知识掌握
        if mastery_bars:
            weak_count = sum(1 for m in mastery_bars if m.get("p_known", 0) < 0.5)
            mastered_count = sum(1 for m in mastery_bars if m.get("p_known", 0) >= 0.8)
            if weak_count > 0:
                recs.append(f"还有{weak_count}个知识点需要加强，今天可以选1个重点突破 🎯")
            if mastered_count > 0 and current_streak > 0:
                recs.append(f"已掌握{mastered_count}个知识点，每一点进步都值得庆祝 🎉")

        # 去重 + 限制
        seen: set[str] = set()
        unique: list[str] = []
        for r in recs:
            key = r[:20]
            if key not in seen:
                seen.add(key)
                unique.append(r)

        return unique[:6]


# 全局实例
behavior_analyzer = LearningBehaviorAnalyzer()

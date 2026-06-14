"""
题目质量分析引擎

基于 IRT (Item Response Theory) 和心理测量学:
- 难度 (Difficulty): 答对率 → 太易/太难
- 区分度 (Discrimination): 高分群 vs 低分群 答对率差
- 干扰项质量 (Distractor Quality): 各错误选项的吸引力分布
- 猜测检测 (Guess Detection): 正确率≈随机概率
- 时间分析 (Time): 过快/过慢

质量分公式:
  quality = discrimination × 0.45 + distractor_q × 0.30
          + difficulty_appropriateness × 0.15 + guess_penalty × 0.10
"""
from __future__ import annotations

import math
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from app.infrastructure.db.database import get_db

logger = logging.getLogger("quality.analyzer")


# ═══════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════

@dataclass
class DistractorStats:
    """单个干扰项的统计"""
    option_letter: str
    option_text: str
    selection_count: int        # 被选次数
    selection_rate: float       # 占所有错误答案的比例
    quality: str                # excellent / good / marginal / dead
    is_correct: bool = False

    def to_dict(self) -> dict:
        return {
            "letter": self.option_letter,
            "text": self.option_text[:60],
            "count": self.selection_count,
            "rate": round(self.selection_rate, 3),
            "quality": self.quality,
            "is_correct": self.is_correct,
        }


@dataclass
class QuestionQuality:
    """单题质量报告"""
    question_id: str
    text: str = ""
    skill_id: str = ""
    subject: str = ""

    # 基础统计
    total_attempts: int = 0
    correct_count: int = 0
    correct_rate: float = 0.0
    avg_time_seconds: float = 0.0

    # IRT 指标
    difficulty: float = 0.5           # 难度 (b) — 高=难
    discrimination: float = 0.0       # 区分度 (a) — 高=好
    guess_rate: float = 0.0           # 猜测率 (c) — 高=有问题

    # 质量判定
    quality_score: float = 0.5        # 综合质量分 (0-1)
    quality_grade: str = "marginal"   # excellent/good/marginal/poor
    flags: list[str] = field(default_factory=list)  # 标记: too_easy/too_hard/low_disc/ambiguous/dead_distractor

    # 干扰项
    distractors: list[DistractorStats] = field(default_factory=list)

    # 时间分布
    time_fast_ratio: float = 0.0      # <5秒答对的比例（秒答）
    time_slow_ratio: float = 0.0      # >60秒的比例（纠结）

    # 当前状态
    current_status: str = "active"
    status_action: str = ""           # keep / flag / retire

    def to_dict(self) -> dict:
        return {
            "question_id": self.question_id,
            "text": self.text[:120],
            "skill_id": self.skill_id,
            "subject": self.subject,
            "total_attempts": self.total_attempts,
            "correct_count": self.correct_count,
            "correct_rate": round(self.correct_rate, 3),
            "avg_time_seconds": round(self.avg_time_seconds, 1),
            "difficulty": round(self.difficulty, 3),
            "discrimination": round(self.discrimination, 3),
            "guess_rate": round(self.guess_rate, 3),
            "quality_score": round(self.quality_score, 3),
            "quality_grade": self.quality_grade,
            "flags": self.flags,
            "distractors": [d.to_dict() for d in self.distractors],
            "time_fast_ratio": round(self.time_fast_ratio, 3),
            "time_slow_ratio": round(self.time_slow_ratio, 3),
            "current_status": self.current_status,
            "status_action": self.status_action,
        }


@dataclass
class QualitySummary:
    """全局质量摘要"""
    total_questions: int
    analyzed: int
    excellent: int
    good: int
    marginal: int
    poor: int
    flagged: int
    retired: int
    avg_quality: float
    worst_questions: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_questions": self.total_questions,
            "analyzed": self.analyzed,
            "excellent": self.excellent,
            "good": self.good,
            "marginal": self.marginal,
            "poor": self.poor,
            "flagged": self.flagged,
            "retired": self.retired,
            "avg_quality": round(self.avg_quality, 3),
            "worst_questions": self.worst_questions,
        }


# ═══════════════════════════════════════════════════════════
# 分析引擎
# ═══════════════════════════════════════════════════════════

class QualityAnalyzer:
    """题目质量分析引擎"""

    MIN_ATTEMPTS = 5   # 最少需要多少次答题才分析

    def analyze_question(self, question_id: str) -> Optional[QuestionQuality]:
        """分析单题质量"""
        db = get_db()

        # 获取题目信息
        q = db.fetchone(
            "SELECT * FROM questions WHERE question_id = %s",
            (question_id,)
        )
        if not q:
            return None

        # 获取所有答题记录
        attempts = db.fetchall(
            "SELECT * FROM practice_attempts WHERE question_id = %s ORDER BY created_at",
            (question_id,)
        )

        if len(attempts) < self.MIN_ATTEMPTS:
            return QuestionQuality(
                question_id=question_id,
                text=q.get("text", ""),
                skill_id=q.get("skill_id", ""),
                subject=q.get("subject", ""),
                total_attempts=len(attempts),
                quality_grade="insufficient_data",
                flags=["insufficient_data"],
                current_status=q.get("status", "active"),
                status_action="keep",
            )

        # ── 1. 基础统计 ──
        att_list = [dict(a) for a in attempts]
        total = len(att_list)
        correct = sum(1 for a in att_list if a.get("is_correct"))
        correct_rate = correct / total
        times = [a.get("time_spent_seconds", 0) or 0 for a in att_list]
        avg_time = sum(times) / total

        # ── 2. 难度 (b) ──
        # IRT: b = ln((1-p)/p), 标准化到 [0,1]
        if correct_rate > 0 and correct_rate < 1:
            b_raw = math.log((1 - correct_rate) / correct_rate)
            difficulty = 1 / (1 + math.exp(-b_raw / 2))  # sigmoid 标准化
        elif correct_rate == 0:
            difficulty = 1.0
        else:
            difficulty = 0.0

        # ── 3. 区分度 (a) ──
        # 按用户总正确率分两组: 高分组(上50%) vs 低分组(下50%)
        user_stats = self._compute_user_ability(att_list)
        median_ability = self._median(list(user_stats.values()))
        high_group = [a for a in att_list if user_stats.get(a.get("user_id", ""), 0) >= median_ability]
        low_group = [a for a in att_list if user_stats.get(a.get("user_id", ""), 0) < median_ability]

        high_correct = sum(1 for a in high_group if a.get("is_correct")) / max(len(high_group), 1)
        low_correct = sum(1 for a in low_group if a.get("is_correct")) / max(len(low_group), 1)
        discrimination = abs(high_correct - low_correct)

        # ── 4. 干扰项分析 ──
        options = q.get("options_json", [])
        if isinstance(options, str):
            import json
            options = json.loads(options)
        if not isinstance(options, list):
            options = []

        distractors = self._analyze_distractors(att_list, options, q.get("correct_answer", ""))

        # 干扰项质量分
        distractor_q = self._compute_distractor_quality(distractors)

        # ── 5. 猜测率 ──
        num_options = max(len(options), 2)
        random_rate = 1.0 / num_options
        # 如果 correct_rate 接近随机概率 → 可能在猜
        guess_deviation = abs(correct_rate - random_rate)
        guess_rate = max(0, 1 - guess_deviation / random_rate)  # 偏离越小越可疑

        # ── 6. 时间分析 ──
        fast_answers = sum(1 for a in att_list if (a.get("time_spent_seconds") or 0) < 5)
        slow_answers = sum(1 for a in att_list if (a.get("time_spent_seconds") or 0) > 60)
        time_fast_ratio = fast_answers / total
        time_slow_ratio = slow_answers / total

        # ── 7. 综合质量分 ──
        difficulty_appropriate = 1.0 - abs(correct_rate - 0.5) * 2  # 50%答对率最优
        guess_penalty = 1.0 - guess_rate

        quality_score = (
            discrimination * 0.45 +
            distractor_q * 0.30 +
            difficulty_appropriate * 0.15 +
            guess_penalty * 0.10
        )

        # ── 8. 标记 ──
        flags = []
        if correct_rate > 0.90:
            flags.append("too_easy")
        if correct_rate < 0.10:
            flags.append("too_hard")
        if discrimination < 0.15:
            flags.append("low_discrimination")
        if guess_rate > 0.5:
            flags.append("high_guess")
        if any(d.quality == "dead" for d in distractors):
            flags.append("dead_distractor")
        if time_fast_ratio > 0.5:
            flags.append("too_fast")
        if time_slow_ratio > 0.4:
            flags.append("ambiguous")

        # ── 9. 等级 ──
        if quality_score >= 0.8:
            grade = "excellent"
        elif quality_score >= 0.6:
            grade = "good"
        elif quality_score >= 0.35:
            grade = "marginal"
        else:
            grade = "poor"

        # ── 10. 建议动作 ──
        if grade == "poor":
            action = "retire"
        elif grade == "marginal" and len(flags) >= 2:
            action = "flag"
        else:
            action = "keep"

        return QuestionQuality(
            question_id=question_id,
            text=q.get("text", ""),
            skill_id=q.get("skill_id", ""),
            subject=q.get("subject", ""),
            total_attempts=total,
            correct_count=correct,
            correct_rate=correct_rate,
            avg_time_seconds=avg_time,
            difficulty=difficulty,
            discrimination=discrimination,
            guess_rate=guess_rate,
            quality_score=quality_score,
            quality_grade=grade,
            flags=flags,
            distractors=distractors,
            time_fast_ratio=time_fast_ratio,
            time_slow_ratio=time_slow_ratio,
            current_status=q.get("status", "active"),
            status_action=action,
        )

    def analyze_all(self, min_attempts: int = 5) -> QualitySummary:
        """全量分析所有题目"""
        db = get_db()
        rows = db.fetchall("SELECT question_id FROM questions WHERE status != 'retired'")
        all_qids = [r["question_id"] for r in rows]

        results = []
        grades = {"excellent": 0, "good": 0, "marginal": 0, "poor": 0,
                  "insufficient_data": 0}
        flagged = 0
        retired = 0

        for qid in all_qids:
            q = self.analyze_question(qid)
            if q is None:
                continue
            results.append(q)

            grade = q.quality_grade
            if grade in grades:
                grades[grade] += 1
            if "flag" in q.flags or q.status_action == "flag":
                flagged += 1
            if q.status_action == "retire":
                retired += 1

        total_analyzed = len(results)
        avg_q = sum(r.quality_score for r in results) / max(total_analyzed, 1)

        # 最差的5题
        worst = sorted(results, key=lambda r: r.quality_score)[:5]
        worst_list = [{
            "question_id": r.question_id,
            "text": r.text[:80],
            "quality_score": r.quality_score,
            "flags": r.flags,
            "status_action": r.status_action,
        } for r in worst]

        return QualitySummary(
            total_questions=len(all_qids),
            analyzed=total_analyzed,
            excellent=grades["excellent"],
            good=grades["good"],
            marginal=grades["marginal"],
            poor=grades["poor"],
            flagged=flagged,
            retired=retired,
            avg_quality=avg_q,
            worst_questions=worst_list,
        )

    def apply_actions(self, dry_run: bool = False) -> dict:
        """执行质量分析建议的动作（标记/淘汰）"""
        db = get_db()
        summary = self.analyze_all()
        actions_taken = {"flagged": 0, "retired": 0, "kept": 0}
        details = []

        for qid in [r["question_id"] for r in db.fetchall(
            "SELECT question_id FROM questions WHERE status != 'retired'"
        )]:
            result = self.analyze_question(qid)
            if result is None:
                continue

            action = result.status_action
            actions_taken[{"flag": "flagged", "retire": "retired", "keep": "kept"}[action]] += 1

            if action != "keep" and not dry_run:
                new_status = "retired" if action == "retire" else "flagged"
                db.execute(
                    "UPDATE questions SET status = %s, quality_score = %s WHERE question_id = %s",
                    (new_status, result.quality_score, qid)
                )
                details.append({
                    "question_id": qid,
                    "action": action,
                    "grade": result.quality_grade,
                    "reasons": result.flags,
                })

        return {
            "dry_run": dry_run,
            "summary": summary.to_dict(),
            "actions": actions_taken,
            "details": details[:20],
        }

    # ── 内部方法 ──

    def _compute_user_ability(self, attempts: list[dict]) -> dict[str, float]:
        """估计用户能力: 用户在所有题上的正确率"""
        user_correct: dict[str, list[bool]] = defaultdict(list)
        for a in attempts:
            uid = a.get("user_id", "anon")
            user_correct[uid].append(a.get("is_correct", False))
        return {
            uid: sum(cs) / len(cs)
            for uid, cs in user_correct.items()
        }

    def _median(self, values: list[float]) -> float:
        if not values:
            return 0.5
        sorted_v = sorted(values)
        n = len(sorted_v)
        if n % 2 == 0:
            return (sorted_v[n // 2 - 1] + sorted_v[n // 2]) / 2
        return sorted_v[n // 2]

    def _analyze_distractors(
        self, attempts: list[dict], options: list[dict], correct_answer: str
    ) -> list[DistractorStats]:
        """分析干扰项"""
        wrong_answers = [a for a in attempts if not a.get("is_correct")]
        total_wrong = len(wrong_answers)

        stats = []
        for opt in options:
            letter = opt.get("letter", "?")
            text = opt.get("text", "")
            is_correct = letter.upper() == correct_answer.strip().upper()

            if is_correct:
                # 正确选项：统计被正确选择的次数
                correct_picks = sum(1 for a in attempts if a.get("is_correct"))
                stats.append(DistractorStats(
                    option_letter=letter, option_text=text,
                    selection_count=correct_picks,
                    selection_rate=1.0,  # correct_rate
                    quality="correct",
                    is_correct=True,
                ))
            else:
                picks = sum(
                    1 for a in wrong_answers
                    if a.get("user_answer", "").strip().upper() == letter.upper()
                )
                rate = picks / max(total_wrong, 1)

                # 干扰项质量判定
                if rate >= 0.25 and rate <= 0.75:
                    quality = "excellent"   # 吸引合理比例的错误
                elif rate >= 0.10:
                    quality = "good"
                elif rate >= 0.02:
                    quality = "marginal"
                else:
                    quality = "dead"        # 没人选 — 无效干扰项

                stats.append(DistractorStats(
                    option_letter=letter, option_text=text,
                    selection_count=picks,
                    selection_rate=rate,
                    quality=quality,
                    is_correct=False,
                ))

        return stats

    def _compute_distractor_quality(self, distractors: list[DistractorStats]) -> float:
        """计算干扰项整体质量分"""
        wrong_distractors = [d for d in distractors if not d.is_correct]
        if not wrong_distractors:
            return 0.5

        quality_scores = {
            "excellent": 1.0,
            "good": 0.7,
            "marginal": 0.3,
            "dead": 0.0,
        }
        scores = [quality_scores.get(d.quality, 0) for d in wrong_distractors]
        return sum(scores) / len(scores)


# ── 全局实例 ──
quality_analyzer = QualityAnalyzer()

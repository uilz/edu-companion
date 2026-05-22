"""
ZPD自适应调度器
基于最近发展区(Zone of Proximal Development)的题目调度
"""

from __future__ import annotations

import math
import logging
from typing import Optional

from app.schemas.practice import (
    BloomLevel,
    KnowledgeState,
    PracticeSessionPlan,
    Question,
    ReviewTask,
)

logger = logging.getLogger(__name__)


class ZPDScheduler:
    """
    基于Vygotsky最近发展区的自适应调度
    
    核心思想：每道题都应该在"刚好够挑战"的甜蜜点
    
    |θ - b| ∈ [0.3, 1.2] → ZPD甜蜜点
    |θ - b| < 0.3 → 太简单
    |θ - b| > 1.2 → 太难
    
    其中 θ = 学生能力, b = 题目难度
    """

    # ZPD窗口参数
    ZPD_MIN_GAP = 0.3   # 最小难度差（避免太简单）
    ZPD_MAX_GAP = 1.0   # 最大难度差（避免太难）
    ZPD_OPTIMAL = 0.6   # 最优难度差

    def select_questions(
        self,
        question_pool: list[Question],
        student_ability: float,
        count: int = 3,
        target_bloom: Optional[BloomLevel] = None,
        blocked_skills: list[str] | None = None,
    ) -> list[Question]:
        """
        从候选池中选择最适合的题目

        参数:
            question_pool: 候选题目
            student_ability: 学生当前能力估计 θ (0-1)
            count: 选择数量
            target_bloom: 目标Bloom层次
            blocked_skills: 前置知识卡控 — 被阻塞的技能列表，其题目直接过滤
        """
        if not question_pool:
            return []

        # 过滤Bloom层次
        candidates = question_pool
        if target_bloom:
            candidates = [q for q in candidates if q.bloom_level == target_bloom]

        if not candidates:
            return []

        # 前置知识卡控: 过滤被阻塞的技能
        if blocked_skills:
            candidates = [q for q in candidates if q.skill_id not in blocked_skills]
        if not candidates:
            return []

        # 计算每道题的ZPD得分
        scored = []
        for q in candidates:
            difficulty_gap = abs(student_ability - q.difficulty)
            
            # ZPD得分：越接近最优差距，得分越高
            if difficulty_gap < self.ZPD_MIN_GAP:
                zpd_score = 1.0 - difficulty_gap / self.ZPD_MIN_GAP * 0.5
            elif difficulty_gap <= self.ZPD_MAX_GAP:
                # 在ZPD区间内，越接近最优越好
                zpd_score = 1.0 - abs(difficulty_gap - self.ZPD_OPTIMAL) / self.ZPD_MAX_GAP
            else:
                zpd_score = max(0.1, 1.0 - difficulty_gap / 2.0)

            # 质量加成
            quality_bonus = q.quality_score * 0.3
            
            # 新颖性加成（没用过的题优先）
            novelty = 1.0 if q.usage_count == 0 else max(0.3, 1.0 / math.log(q.usage_count + 2))
            novelty_bonus = novelty * 0.2

            scored.append((q, zpd_score + quality_bonus + novelty_bonus))

        # 排序并选择top N
        scored.sort(key=lambda x: x[1], reverse=True)
        selected = [q for q, _ in scored[:count]]

        # 更新使用计数
        for q in selected:
            q.usage_count += 1

        return selected

    def estimate_student_ability(
        self,
        knowledge_states: dict[str, KnowledgeState],
        skill_id: str,
        user_id: str = "default_user",
    ) -> float:
        """
        估计学生在某知识点的能力θ
        
        Phase 6: 优先读 CognitiveNode，备降旧 knowledge_states
        """
        # Phase 6: CognitiveNode 主源
        try:
            from app.cognitive.storage import get_node
            node = get_node(skill_id, user_id)
            if node and node.belief:
                mu = node.belief.proficiency_mean
                return mu * 0.6 + mu * 0.4  # simplified: θ = proficiency_mean
        except Exception:
            pass

        # 备降: 旧 knowledge_states
        state = knowledge_states.get(skill_id)
        if not state:
            return 0.3  # 默认：低能力
        
        p_known = state.p_known
        avg_dim = state.avg_dimension_p
        
        # 能力估计
        ability = p_known * 0.6 + avg_dim * 0.4
        
        # 置信度调整：尝试次数少 → 能力估计保守
        if state.attempt_count < 3:
            ability = max(0.1, ability - 0.1)
        
        return ability

    def plan_session(
        self,
        knowledge_states: dict[str, KnowledgeState],
        question_pool: dict[str, list[Question]],
        target_skills: list[str],
        duration_minutes: int = 30,
    ) -> PracticeSessionPlan:
        """
        规划一次练习session
        
        策略：
        1. 每个知识点选3-5道题
        2. 按ZPD难度选择
        3. 交错排列不同知识点的题目
        """
        all_questions = []
        questions_per_skill = max(2, duration_minutes // (len(target_skills) * 5))

        for skill_id in target_skills:
            pool = question_pool.get(skill_id, [])
            if not pool:
                continue
            
            ability = self.estimate_student_ability(knowledge_states, skill_id)
            selected = self.select_questions(pool, ability, count=questions_per_skill)
            all_questions.extend(selected)

        # 简单交错排列
        if len(target_skills) > 1:
            all_questions.sort(key=lambda q: target_skills.index(q.skill_id))
            # 轮询交错
            interleaved = []
            per_skill = {s: [] for s in target_skills}
            for q in all_questions:
                per_skill[q.skill_id].append(q)
            
            max_len = max(len(v) for v in per_skill.values())
            for i in range(max_len):
                for s in target_skills:
                    if i < len(per_skill[s]):
                        interleaved.append(per_skill[s][i])
            all_questions = interleaved

        return PracticeSessionPlan(
            skills=target_skills,
            questions=all_questions,
            estimated_minutes=len(all_questions) * 3,  # 每题约3分钟
        )

    def fatigue_adjusted_ability(
        self,
        base_ability: float,
        session_elapsed_minutes: float,
        consecutive_wrong: int,
    ) -> float:
        """
        疲劳感知的能力调整
        
        规则：
        - 每30分钟降低0.1能力
        - 连续错题降低0.05/题
        """
        # 时间衰减
        time_decay = session_elapsed_minutes / 300  # 5小时归零
        
        # 错误惩罚
        error_penalty = consecutive_wrong * 0.05
        
        adjusted = max(0.05, base_ability * (1.0 - time_decay) - error_penalty)
        
        return adjusted


class SpacedRepetitionScheduler:
    """SM-2间隔重复调度"""
    
    # SM-2间隔表（天数）
    INTERVALS = [1, 3, 7, 14, 30, 60, 120, 240]
    
    def compute_next_review(
        self,
        state: KnowledgeState,
        is_correct: bool,
    ) -> int:
        """
        计算下次复习的天数间隔
        
        SM-2算法简化版：
        - 答对：间隔递增
        - 答错：重置到1天
        """
        if not is_correct:
            return 1  # 答错：明天复习
        
        # 答对：根据当前稳定性决定间隔
        stability = 1.0
        if state.explanation_state:
            stability = state.explanation_state.stability
        
        base_interval = int(1.0 / (1.0 - state.p_known + 0.1))
        adjusted = int(base_interval * stability)
        
        return min(adjusted, 60)  # 最长60天
    
    def get_review_tasks(
        self,
        knowledge_states: dict[str, KnowledgeState],
        now: float,
    ) -> list[ReviewTask]:
        """获取所有需要复习的知识点"""
        tasks = []
        
        for skill_id, state in knowledge_states.items():
            if state.attempt_count == 0:
                continue
            
            days_since = 0  # 简化：假设刚练习
            forgetting_prob = math.exp(-days_since / max(state.p_known + 0.1, 0.1))
            
            if forgetting_prob > 0.3 and state.p_known < 0.8:
                tasks.append(ReviewTask(
                    type="knowledge_review",
                    skill_id=skill_id,
                    priority=forgetting_prob,
                    instruction=f"复习{skill_id}",
                ))
        
        tasks.sort(key=lambda t: t.priority, reverse=True)
        return tasks[:10]


# 全局实例
zpd_scheduler = ZPDScheduler()
spacing_scheduler = SpacedRepetitionScheduler()

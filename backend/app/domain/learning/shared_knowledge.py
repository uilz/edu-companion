"""
⚠️  DEPRECATED — SharedKnowledgeState 已由 CognitiveNode 替代。

本模块仅作为 knowledge_bridge.py 的遗留 fallback 保留。
新代码应直接使用 app.cognitive.storage + CognitiveNode。

SharedKnowledgeState — 对话与练习统一知识状态

核心设计：
- 单一真相源：每个 skill 只有一个 SharedSkillState
- 双向流入：练习 BKT 写入 + 对话证据写入
- 加权融合：unified_mastery = BKT × α + conversation_evidence × (1-α)
- 置信度感知：证据越多，置信度越高

使用方式：
    state = SharedKnowledgeState()
    
    # Practice writes
    state.update_from_practice("derivative", bkt_state)
    
    # Conversation writes
    state.add_conversation_evidence("derivative", 
        evidence_type="correct_explanation",
        confidence=0.7)
    
    # Read unified view
    mastery = state.get_unified_mastery("derivative")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ── 对话证据类型 ──

class EvidenceType(str, Enum):
    """对话中观察到的证据类型"""
    CORRECT_EXPLANATION = "correct_explanation"      # 正确解释概念
    PARTIAL_EXPLANATION = "partial_explanation"      # 部分正确
    INCORRECT_EXPLANATION = "incorrect_explanation"   # 错误理解
    ASKED_CLARIFICATION = "asked_clarification"       # 主动提问澄清
    DEMONSTRATED_APPLICATION = "demonstrated_application"  # 展示应用
    EXPRESSED_CONFUSION = "expressed_confusion"       # 表达困惑
    REQUESTED_DEEPER = "requested_deeper"             # 请求深入讲解
    SELF_CORRECTED = "self_corrected"                 # 自我纠正


# ── 证据记录 ──

@dataclass
class ConversationEvidence:
    """单条对话证据"""
    timestamp: datetime
    evidence_type: EvidenceType
    confidence: float         # 0.0 ~ 1.0，证据强度
    skill_id: str
    source_text: str = ""     # 触发证据的对话片段（截断）
    branch_id: str = ""
    
    @property
    def weight(self) -> float:
        """证据权重（类型 × 置信度）"""
        type_weights = {
            EvidenceType.CORRECT_EXPLANATION: 0.8,
            EvidenceType.DEMONSTRATED_APPLICATION: 0.9,
            EvidenceType.SELF_CORRECTED: 0.7,
            EvidenceType.REQUESTED_DEEPER: 0.3,
            EvidenceType.PARTIAL_EXPLANATION: 0.4,
            EvidenceType.ASKED_CLARIFICATION: 0.2,
            EvidenceType.EXPRESSED_CONFUSION: -0.3,
            EvidenceType.INCORRECT_EXPLANATION: -0.5,
        }
        return type_weights.get(self.evidence_type, 0.0) * self.confidence


# ── 统一技能状态 ──

@dataclass
class SharedSkillState:
    """统一技能掌握状态"""
    skill_id: str
    
    # Practice side (BKT)
    bkt_p_known: float = 0.0          # BKT 估计的掌握概率
    bkt_confidence: float = 0.0       # BKT 数据量决定的置信度
    bkt_attempt_count: int = 0
    bkt_last_updated: Optional[datetime] = None
    
    # Conversation side
    conversation_evidences: list[ConversationEvidence] = field(default_factory=list)
    conversation_mastery_score: float = 0.0  # 对话侧掌握评分
    conversation_last_updated: Optional[datetime] = None
    
    # Unified
    unified_mastery: float = 0.0      # 融合后的掌握度 (0-1)
    overall_confidence: float = 0.0   # 综合置信度
    last_updated: datetime = field(default_factory=datetime.now)
    
    # Meta
    evidence_count: int = 0           # 总证据数
    last_conversation_mention: Optional[datetime] = None
    is_stale: bool = False            # 数据是否过期
    
    # ── Properties ──
    
    @property
    def is_mastered(self) -> bool:
        return self.unified_mastery >= 0.8 and self.overall_confidence >= 0.4
    
    @property
    def is_learning(self) -> bool:
        return 0.3 <= self.unified_mastery < 0.8
    
    @property
    def is_novice(self) -> bool:
        return self.unified_mastery < 0.3
    
    @property
    def bkt_weight(self) -> float:
        """BKT 在融合中的权重"""
        return self._compute_bkt_weight()
    
    @property
    def conversation_weight(self) -> float:
        return 1.0 - self.bkt_weight
    
    # ── Methods ──
    
    def _compute_bkt_weight(self) -> float:
        """BKT权重：数据越多，权越高（上限 0.7）"""
        if self.bkt_attempt_count == 0:
            return 0.0
        return min(0.7, 0.3 + 0.04 * self.bkt_attempt_count)
    
    def update_from_bkt(self, p_known: float, confidence: float, attempt_count: int):
        """练习侧更新"""
        self.bkt_p_known = p_known
        self.bkt_confidence = confidence
        self.bkt_attempt_count = attempt_count
        self.bkt_last_updated = datetime.now()
        self._recompute_unified()
    
    def add_evidence(self, evidence: ConversationEvidence):
        """添加对话证据"""
        self.conversation_evidences.append(evidence)
        self.evidence_count = len(self.conversation_evidences)
        self.conversation_last_updated = evidence.timestamp
        self.last_conversation_mention = evidence.timestamp
        
        # 保持最近50条（避免无限增长）
        if len(self.conversation_evidences) > 50:
            self.conversation_evidences = self.conversation_evidences[-50:]
        
        # 重新计算对话侧评分
        self._recompute_conversation_score()
        self._recompute_unified()
    
    def _recompute_conversation_score(self):
        """根据证据重新计算对话侧掌握评分"""
        if not self.conversation_evidences:
            self.conversation_mastery_score = 0.0
            return
        
        # 时间衰减：最近证据权重更高
        now = datetime.now()
        total_weight = 0.0
        weighted_sum = 0.0
        
        for ev in self.conversation_evidences:
            # 时间衰减因子（半衰期 7 天）
            age_days = (now - ev.timestamp).total_seconds() / 86400
            time_decay = 0.5 ** (age_days / 7)
            
            w = ev.weight * time_decay
            weighted_sum += w
            total_weight += abs(ev.weight)  # 用于归一化
        
        if total_weight == 0:
            self.conversation_mastery_score = 0.5  # 中性默认
        else:
            # 映射到 [0, 1]
            raw = max(0.0, min(1.0, (weighted_sum / total_weight + 1) / 2))
            self.conversation_mastery_score = raw
    
    def _recompute_unified(self):
        """融合 BKT + 对话证据 → unified_mastery"""
        bkt_w = self.bkt_weight
        conv_w = 1.0 - bkt_w
        
        if bkt_w == 0:
            # 只有对话证据
            self.unified_mastery = self.conversation_mastery_score
            self.overall_confidence = min(0.6, self.evidence_count * 0.05)
        elif self.conversation_evidences:
            # 双向融合
            self.unified_mastery = self.bkt_p_known * bkt_w + self.conversation_mastery_score * conv_w
            # 置信度 = BKT置信度 × 权重 + 证据量 × 因子
            self.overall_confidence = min(0.9, self.bkt_confidence * 0.5 + min(0.4, self.evidence_count * 0.03))
        else:
            # 只有 BKT，没有对话证据
            self.unified_mastery = self.bkt_p_known
            self.overall_confidence = self.bkt_confidence * 0.7  # 单独BKT打折
        
        self.last_updated = datetime.now()
        self.is_stale = (datetime.now() - self.last_updated) > timedelta(days=14)
    
    def to_dict(self) -> dict:
        return {
            "skill_id": self.skill_id,
            "unified_mastery": round(self.unified_mastery, 3),
            "overall_confidence": round(self.overall_confidence, 3),
            "bkt_p_known": round(self.bkt_p_known, 3),
            "bkt_confidence": round(self.bkt_confidence, 3),
            "bkt_attempt_count": self.bkt_attempt_count,
            "conversation_score": round(self.conversation_mastery_score, 3),
            "evidence_count": self.evidence_count,
            "is_mastered": self.is_mastered,
            "is_stale": self.is_stale,
            "last_updated": self.last_updated.isoformat(),
        }


# ── 全局状态管理器 ──

@dataclass
class SharedKnowledgeState:
    """全局统一知识状态"""
    
    skills: dict[str, SharedSkillState] = field(default_factory=dict)
    
    # ── BKT 写入 ──
    
    def update_from_practice(
        self,
        skill_id: str,
        p_known: float,
        confidence: float = 0.5,
        attempt_count: int = 1,
    ):
        """练习侧写入"""
        if skill_id not in self.skills:
            self.skills[skill_id] = SharedSkillState(skill_id=skill_id)
        
        state = self.skills[skill_id]
        state.update_from_bkt(p_known, confidence, attempt_count)
        logger.debug(f"BKT → SharedState: {skill_id} = {p_known:.2f}")
    
    # ── 对话证据写入 ──
    
    def add_conversation_evidence(
        self,
        skill_id: str,
        evidence_type: EvidenceType,
        confidence: float = 0.5,
        source_text: str = "",
        branch_id: str = "",
    ):
        """对话侧写入证据"""
        if skill_id not in self.skills:
            self.skills[skill_id] = SharedSkillState(skill_id=skill_id)
        
        evidence = ConversationEvidence(
            timestamp=datetime.now(),
            evidence_type=evidence_type,
            confidence=confidence,
            skill_id=skill_id,
            source_text=source_text[:200],
            branch_id=branch_id,
        )
        
        self.skills[skill_id].add_evidence(evidence)
        logger.debug(f"Conversation → SharedState: {skill_id} {evidence_type.value}")
    
    # ── 批量写入（从BKT全量同步） ──
    
    def bulk_update_from_bkt(self, bkt_states: dict[str, dict]):
        """批量从 BKT 引擎同步"""
        for skill_id, bkt in bkt_states.items():
            self.update_from_practice(
                skill_id=skill_id,
                p_known=bkt.get("p_known", 0.0),
                confidence=bkt.get("confidence", 0.5),
                attempt_count=bkt.get("attempt_count", 1),
            )
    
    # ── 读取 ──
    
    def get_skill(self, skill_id: str) -> Optional[SharedSkillState]:
        return self.skills.get(skill_id)
    
    def get_unified_mastery(self, skill_id: str) -> float:
        state = self.skills.get(skill_id)
        return state.unified_mastery if state else 0.0
    
    def get_all_mastered(self, threshold: float = 0.8) -> list[str]:
        """获取所有已掌握的 skill"""
        return [
            sid for sid, s in self.skills.items()
            if s.unified_mastery >= threshold
        ]
    
    def get_all_weak(self, threshold: float = 0.4) -> list[str]:
        """获取所有薄弱的 skill"""
        return [
            sid for sid, s in self.skills.items()
            if s.unified_mastery < threshold and s.evidence_count > 0
        ]
    
    # ── 导出 ──
    
    def to_dict(self) -> dict:
        return {
            "skills": {sid: s.to_dict() for sid, s in self.skills.items()},
            "total_skills": len(self.skills),
            "mastered_count": len(self.get_all_mastered()),
            "weak_count": len(self.get_all_weak()),
        }
    
    def to_context_string(self) -> str:
        """导出为对话上下文字符串（注入 system prompt）"""
        if not self.skills:
            return ""
        
        lines = ["[统一知识状态]"]
        mastered = self.get_all_mastered()
        weak = self.get_all_weak()
        learning = [
            sid for sid, s in self.skills.items()
            if sid not in mastered and sid not in weak
        ]
        
        if mastered:
            lines.append(f"✅ 已掌握({len(mastered)}): {', '.join(mastered[:5])}")
        if learning:
            lines.append(f"📖 学习中({len(learning)}): {', '.join(learning[:5])}")
        if weak:
            lines.append(f"⚠️ 薄弱({len(weak)}): {', '.join(weak[:5])}")
        
        return "\n".join(lines)


# ── 全局单例 ──

shared_knowledge = SharedKnowledgeState()

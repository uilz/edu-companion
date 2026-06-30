"""
前置知识卡控引擎

核心职责:
1. 检查用户是否满足某个技能的前置条件
2. 导出所有未满足的前置技能
3. 推荐该技能的最优学习路径

数据源优先级:
  1. UserData.knowledge_graphs[dir_id].edges  ← 用户知识树边（动态）
  2. ALL_PREREQUISITES                            ← 硬编码回退（兼容旧逻辑）
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.domain.knowledge.prerequisites import (
    ALL_PREREQUISITES,
    SKILL_TO_SUBJECT,
)

if TYPE_CHECKING:
    from shared.protocols import PracticeService

logger = logging.getLogger("domain.prerequisites")

# ── 卡控阈值 ──
MASTERY_THRESHOLD = 0.70   # 前置知识点 p_known ≥ 0.7 才算"掌握"


class PrerequisiteCheckResult:
    """前置检查结果"""

    def __init__(self, blocked: list[str], satisfied: list[str],
                 missing_count: int, reason: str = ""):
        self.blocked = blocked        # 未满足的前置技能
        self.satisfied = satisfied    # 已满足的前置技能
        self.missing_count = missing_count
        self.reason = reason

    @property
    def can_practice(self) -> bool:
        return self.missing_count == 0

    def to_dict(self) -> dict:
        return {
            "can_practice": self.can_practice,
            "blocked_by": self.blocked,
            "satisfied": self.satisfied,
            "reason": self.reason,
        }


class PrerequisiteChecker:
    """
    前置知识检查器

    数据源:
      - 优先从 UserData.knowledge_graphs 读取动态前置关系
      - 回退到 ALL_PREREQUISITES 硬编码数据

    使用方式:
      checker = PrerequisiteChecker(practice_service)
      # 动态加载用户知识树前置
      checker.load_from_knowledge_tree(user_id, dir_id)
      result = await checker.can_practice(user_id, "node_abc")
      if not result.can_practice:
          print(f"需要先学: {result.blocked_by}")
    """

    def __init__(self, practice: PracticeService):
        self._practice = practice
        self._prerequisites = dict(ALL_PREREQUISITES)  # 默认硬编码（可被覆盖）
        self._node_labels: dict[str, str] = {}          # skill_id → 显示名称
        self._subject_map: dict[str, str] = {}          # skill_id → 学科

    # ═══════════════════════════════════════════════════════════
    # 动态加载：从知识树边读取前置关系
    # ═══════════════════════════════════════════════════════════

    def load_from_knowledge_tree(self, user_id: str, dir_id: str) -> bool:
        """
        从 UserData.knowledge_graphs[dir_id] 加载前置关系。

        返回 True 表示成功加载了知识树数据，False 表示回退到硬编码。
        """
        try:
            from app.services.common import get_data_repo
            data = get_data_repo().load(user_id)
            graph = data.knowledge_graphs.get(dir_id)
            if not graph or not graph.nodes:
                logger.info(f"[checker] 分区 {dir_id} 无知识树，使用硬编码回退")
                return False

            # 从知识树边构建前置关系
            dynamic_prereqs: dict[str, list[str]] = {}
            node_labels: dict[str, str] = {}
            partition = data.directory_nodes.get(dir_id)
            subject = partition.name if partition else ""

            for nid, node in graph.nodes.items():
                dynamic_prereqs.setdefault(nid, [])
                node_labels[nid] = node.label
                self._subject_map[nid] = subject

            for edge in graph.edges:
                dynamic_prereqs.setdefault(edge.to_id, [])
                if edge.from_id not in dynamic_prereqs[edge.to_id]:
                    dynamic_prereqs[edge.to_id].append(edge.from_id)

            self._prerequisites = dynamic_prereqs
            self._node_labels = node_labels

            logger.info(
                f"[checker] 从知识树加载前置关系: {len(dynamic_prereqs)} 节点, "
                f"{len(graph.edges)} 边, 分区={dir_id}"
            )
            return True
        except Exception as e:
            logger.warning(f"[checker] 加载知识树失败，使用硬编码回退: {e}")
            return False

    def reset(self) -> None:
        """重置为硬编码数据"""
        self._prerequisites = dict(ALL_PREREQUISITES)
        self._node_labels = {}
        self._subject_map = {}

    # ═══════════════════════════════════════════════════════════
    # 公共接口
    # ═══════════════════════════════════════════════════════════

    async def can_practice(self, user_id: str, skill_id: str) -> PrerequisiteCheckResult:
        """
        检查用户是否可以练习指定技能

        返回 PrerequisiteCheckResult，其中:
        - can_practice: True 表示可以练习
        - blocked_by: 未满足的前置技能列表
        - reason: 人类可读的阻塞原因
        """
        prerequisites = self._prerequisites.get(skill_id)

        # 无前置依赖 → 直接通过
        if not prerequisites:
            return PrerequisiteCheckResult(
                blocked=[], satisfied=[], missing_count=0,
                reason="",
            )

        blocked: list[str] = []
        satisfied: list[str] = []

        for prereq_id in prerequisites:
            state = await self._practice.get_knowledge_state(user_id, prereq_id)
            p_known = state.get("p_known", 0.0) if state else 0.0

            if p_known < MASTERY_THRESHOLD:
                blocked.append(prereq_id)
            else:
                satisfied.append(prereq_id)

        if blocked:
            reason = self._build_reason(skill_id, blocked)
        else:
            reason = ""

        return PrerequisiteCheckResult(
            blocked=blocked,
            satisfied=satisfied,
            missing_count=len(blocked),
            reason=reason,
        )

    async def check_batch(
        self, user_id: str, skill_ids: list[str],
    ) -> dict[str, PrerequisiteCheckResult]:
        """批量检查多个技能"""
        results = {}
        for sid in skill_ids:
            results[sid] = await self.can_practice(user_id, sid)
        return results

    async def get_prerequisites(self, skill_id: str) -> dict:
        """获取技能的前置依赖图（含用户状态）"""
        prereqs = self._prerequisites.get(skill_id, [])
        subject = self._subject_map.get(skill_id) or SKILL_TO_SUBJECT.get(skill_id, "未知")
        return {
            "skill_id": skill_id,
            "subject": subject,
            "prerequisites": prereqs,
            "total": len(prereqs),
            "depth": self._compute_depth(skill_id),
        }

    async def get_blocked_skills(self, user_id: str) -> list[dict]:
        """
        获取用户被卡控的所有技能清单
        用于前端展示"当前还无法练习"的技能
        """
        blocked_list = []
        for skill_id in self._prerequisites:
            result = await self.can_practice(user_id, skill_id)
            if not result.can_practice:
                blocked_list.append({
                    "skill_id": skill_id,
                    "blocked_by": result.blocked,
                    "subject": self._subject_map.get(skill_id) or SKILL_TO_SUBJECT.get(skill_id, "未知"),
                })
        return blocked_list

    async def find_ready_skills(self, user_id: str, subject: str | None = None) -> list[str]:
        """
        找出当前用户可以练习的所有技能
        用于 ZPD 调度时过滤候选技能
        """
        ready = []
        for skill_id in self._prerequisites:
            s = self._subject_map.get(skill_id) or SKILL_TO_SUBJECT.get(skill_id)
            if subject and s != subject:
                continue
            result = await self.can_practice(user_id, skill_id)
            if result.can_practice:
                ready.append(skill_id)
        return ready

    @property
    def skill_ids(self) -> list[str]:
        """返回所有已注册的技能 ID"""
        return list(self._prerequisites.keys())

    # ── 内部方法 ──

    def _build_reason(self, skill_id: str, blocked: list[str]) -> str:
        """构造人类可读的阻塞原因"""
        skill_name = self._skill_display_name(skill_id)
        blocked_names = [self._skill_display_name(b) for b in blocked]
        if len(blocked_names) == 1:
            return f"建议先掌握「{blocked_names[0]}」再学「{skill_name}」"
        else:
            return f"建议先掌握 {', '.join(blocked_names)} 再学「{skill_name}」"

    def _skill_display_name(self, skill_id: str) -> str:
        """skill_id → 可读名称（知识树节点 label 优先，回退到硬编码映射）"""
        if skill_id in self._node_labels:
            return self._node_labels[skill_id]
        names = {
            "calculus_limit": "极限与连续",
            "calculus_derivative": "导数与微分",
            "calculus_derivative_app": "导数应用",
            "calculus_integral": "积分学",
            "calculus_integral_tech": "积分技巧",
            "calculus_multivariable": "多元微积分",
            "calculus_series": "无穷级数",
            "calculus_diff_eq": "微分方程",
            "linalg_matrix": "矩阵运算",
            "linalg_determinant": "行列式",
            "linalg_vector_space": "向量空间",
            "linalg_eigenvalue": "特征值与特征向量",
            "linalg_quadratic": "二次型",
            "prob_basic": "概率基础",
            "prob_distribution": "概率分布",
            "prob_expectation": "期望与方差",
            "prob_law_large_numbers": "大数定律",
            "prob_estimation": "参数估计",
            "prob_hypothesis_test": "假设检验",
            "physics_mechanics": "经典力学",
            "physics_energy": "能量与动量",
            "physics_rotation": "刚体转动",
            "physics_em_static": "静电场",
            "physics_em_magnetic": "磁场",
            "physics_em_induction": "电磁感应",
            "physics_em_maxwell": "麦克斯韦方程组",
            "physics_wave": "波动学",
            "physics_optics": "光学",
            "physics_quantum": "量子力学基础",
            "cs_programming_basic": "编程基础",
            "cs_data_structure": "数据结构",
            "cs_algorithm": "算法设计",
            "cs_algorithm_advanced": "高级算法",
            "cs_os": "操作系统",
            "cs_network": "计算机网络",
            "cs_db": "数据库系统",
            "cs_ai_ml": "机器学习",
            "cs_ai_dl": "深度学习",
        }
        return names.get(skill_id, skill_id)

    def _compute_depth(self, skill_id: str, visited: set | None = None) -> int:
        """递归计算前置深度"""
        if visited is None:
            visited = set()
        if skill_id in visited:
            return 0
        visited.add(skill_id)
        prereqs = self._prerequisites.get(skill_id, [])
        if not prereqs:
            return 0
        return 1 + max(self._compute_depth(p, visited) for p in prereqs)
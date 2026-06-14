"""
前置知识依赖图 — 学科知识点前置关系定义

每行: 目标知识点 → 需要先掌握的前置知识点列表
格式: skill_id: [prereq_skill_ids]
"""
from __future__ import annotations

# ═══════════════════════════════════════════════════════════
# 机器学习 — 前置依赖链
# ═══════════════════════════════════════════════════════════

MATH_PREREQUISITES: dict[str, list[str]] = {
    # 微积分链
    "calculus_limit":           [],                                  # 极限 — 入口，无前置
    "calculus_derivative":      ["calculus_limit"],                  # 导数 ← 极限
    "calculus_derivative_app":  ["calculus_derivative"],             # 导数应用 ← 导数
    "calculus_integral":        ["calculus_derivative"],             # 积分 ← 导数
    "calculus_integral_tech":   ["calculus_integral"],               # 积分技巧 ← 积分
    "calculus_multivariable":   ["calculus_derivative", "calculus_integral"],  # 多元 ← 导数+积分
    "calculus_series":          ["calculus_limit", "calculus_derivative"],     # 级数 ← 极限+导数
    "calculus_diff_eq":         ["calculus_derivative", "calculus_integral"],  # 微分方程 ← 导数+积分

    # 线性代数链
    "linalg_matrix":            [],                                  # 矩阵 — 入口
    "linalg_determinant":       ["linalg_matrix"],                   # 行列式 ← 矩阵
    "linalg_vector_space":      ["linalg_matrix"],                   # 向量空间 ← 矩阵
    "linalg_eigenvalue":        ["linalg_determinant", "linalg_vector_space"],  # 特征值 ← 行列式+向量空间
    "linalg_quadratic":         ["linalg_eigenvalue"],               # 二次型 ← 特征值

    # 概率论链
    "prob_basic":               [],                                  # 概率基础 — 入口
    "prob_distribution":        ["prob_basic"],                      # 分布 ← 基础
    "prob_expectation":         ["prob_distribution"],               # 期望方差 ← 分布
    "prob_law_large_numbers":   ["prob_expectation"],                # 大数定律 ← 期望
    "prob_estimation":          ["prob_distribution", "prob_expectation"],  # 估计 ← 分布+期望
    "prob_hypothesis_test":     ["prob_estimation"],                 # 假设检验 ← 估计
}

# ═══════════════════════════════════════════════════════════
# 数据科学
# ═══════════════════════════════════════════════════════════

PHYSICS_PREREQUISITES: dict[str, list[str]] = {
    "physics_mechanics":        [],                                       # 力学 — 入口
    "physics_energy":           ["physics_mechanics"],                    # 能量 ← 力学
    "physics_rotation":         ["physics_mechanics"],                    # 转动 ← 力学
    "physics_em_static":        ["physics_mechanics", "calculus_integral"],  # 静电场 ← 力学+积分
    "physics_em_magnetic":      ["physics_em_static"],                    # 磁场 ← 静电场
    "physics_em_induction":     ["physics_em_magnetic"],                  # 电磁感应 ← 磁场
    "physics_em_maxwell":       ["physics_em_induction"],                 # 麦克斯韦 ← 电磁感应
    "physics_wave":             ["physics_mechanics"],                    # 波动 ← 力学
    "physics_optics":           ["physics_wave"],                         # 光学 ← 波动
    "physics_quantum":          ["physics_wave", "linalg_eigenvalue"],    # 量子 ← 波动+特征值
}

# ═══════════════════════════════════════════════════════════
# 计算机
# ═══════════════════════════════════════════════════════════

CS_PREREQUISITES: dict[str, list[str]] = {
    "cs_programming_basic":     [],                                  # 编程基础 — 入口
    "cs_data_structure":        ["cs_programming_basic"],            # 数据结构 ← 编程基础
    "cs_algorithm":             ["cs_data_structure", "prob_basic"], # 算法 ← 数据结构+概率
    "cs_algorithm_advanced":    ["cs_algorithm", "linalg_matrix"],   # 高级算法 ← 算法+矩阵
    "cs_os":                    ["cs_data_structure"],               # 操作系统 ← 数据结构
    "cs_network":               ["cs_os"],                           # 网络 ← 操作系统
    "cs_db":                    ["cs_data_structure"],               # 数据库 ← 数据结构
    "cs_ai_ml":                 ["cs_algorithm", "prob_estimation", "linalg_matrix"],  # AI/ML ← 算法+估计+矩阵
    "cs_ai_dl":                 ["cs_ai_ml", "linalg_eigenvalue"],   # 深度学习 ← ML+特征值
}

# ═══════════════════════════════════════════════════════════
# 合并全量
# ═══════════════════════════════════════════════════════════

ALL_PREREQUISITES: dict[str, list[str]] = {
    **MATH_PREREQUISITES,
    **PHYSICS_PREREQUISITES,
    **CS_PREREQUISITES,
}

# ── 辅助: 按学科分组 ──

SUBJECT_SKILLS: dict[str, list[str]] = {
    "机器学习": list(MATH_PREREQUISITES.keys()),
    "数据科学": list(PHYSICS_PREREQUISITES.keys()),
    "Web开发":   list(CS_PREREQUISITES.keys()),
}

# ── 辅助: 技能→所属学科 ──

SKILL_TO_SUBJECT: dict[str, str] = {}
for subj, skills in SUBJECT_SKILLS.items():
    for s in skills:
        SKILL_TO_SUBJECT[s] = subj

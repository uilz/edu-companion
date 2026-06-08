# 练习系统

> 智能题库系统 — 练习、考试、错题本、AI 出题、Bloom 分类、多维知识状态、自适应出题、用户资料索引。
>
> 源码：[backend/app/schemas/practice.py](../../../backend/app/schemas/practice.py)

---

## 核心流程

```
选题（按知识点/题库/Bloom层次/模式）
  → 答题（选择/填空/自由/计算）
    → 判题（AI 辅助或自动判题 + 错因分析）
      → 记录（多维 KnowledgeState 更新 + CognitiveNode belief 更新 + 错题本）
        → 复习（间隔重复 + 自适应出题 + BKT 掌握度追踪）
```

## 功能总览

| 功能 | 说明 | 状态 |
|------|------|------|
| 题库 CRUD | 创建/编辑/删除题库 | ✅ 已实现 |
| AI 出题 | 对话中自动生成题目 | ✅ 已实现 |
| Bloom 分类 | 题目按认知层次分类（remember→create） | ✅ 已实现 |
| 多维知识状态 | concept/procedure/application/transfer 四维追踪 | ✅ 已实现 |
| 知识点自动匹配 | 题目自动关联 CognitiveNode | ✅ 已实现 |
| 错题本 | 错因分类 + 深度分析 + 追踪复习 | ✅ 已实现 |
| 考试模式 | 限时/随机组卷 | ✅ 已实现 |
| 文档导入出题 | PDF/文档导入 → AI 生成题目 | ✅ 已实现 |
| AI 核对答案 | 主观题 AI 批改 | ✅ 已实现 |
| BKT 自适应出题 | 基于知识掌握度动态出题 | ✅ 已实现 |
| 用户资料索引 | 上传资料 → 分块 → 向量化 → 出题 | ✅ 已实现 |
| 解释卡片 | 知识点解释能力评估 | ✅ 已实现 |
| 参考资料 | 知识点关联资料推荐 | ✅ 已实现 |

## 练习模式

| 模式 | 说明 |
|------|------|
| `adaptive` | 自适应出题（默认） |
| `targeted` | 针对性练习 |
| `review` | 复习模式 |
| `challenge` | 挑战模式 |
| `contextual` | 情境化练习 |

## 实现文档

| 文档 | 说明 |
|------|------|
| [backend-api.md](backend-api.md) | 题库 CRUD、组题、判题接口 |
| [import-ai-features.md](import-ai-features.md) | 文档导入、AI 核对、节点自动匹配 |
| [adaptive-engine.md](adaptive-engine.md) | BKT 自适应出题算法 |

## 设计决策

1. **不双轨** → 直接合并重构，`/api/practice/*` 全部替换
2. **对话 AI 出题** → 自动存入当前专题题库，用户可指定
3. **知识点→题库** → `bnk_{node_id}` 命名规则，自动创建
4. **旧数据** → 一次性迁移脚本

详见 [roadmaps/v7.0-practice-revamp.md](../../roadmaps/v7.0-practice-revamp.md)。

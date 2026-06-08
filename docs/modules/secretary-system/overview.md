# 秘书系统

> 诊断引擎 + 提案生成器 + 模块注册表 — 持续监听事件总线，分析学习数据，生成针对性建议。
>
> 源码：[backend/app/domain/secretary/](../../../backend/app/domain/secretary/)

---

## 核心架构

```
事件总线 → 事件消费者(SecretaryEventHandler)
               ↓
         诊断引擎(DiagnosisEngine) + 上下文引擎(ContextEngine) + 策略引擎(PolicyEngine)
               ↓
         提案生成器(ProposalGenerator) → 提案操作处理器(ProposalActionHandler)
               ↓
         模块注册表(SecretaryModuleRegistry) → 内置模块
               ↓
         前端秘书面板
```

## 功能总览

| 功能 | 说明 | 状态 |
|------|------|------|
| 诊断引擎 | 分析 CognitiveNode 状态 | ✅ 已实现 |
| 上下文引擎 | 构建用户情境快照 | ✅ 已实现 |
| 策略引擎 | 决策提案生成策略 | ✅ 已实现 |
| 提案生成 | 生成学习建议 | ✅ 已实现 |
| 提案操作处理器 | 执行已采纳提案的图谱操作 | ✅ 已实现 |
| 复习提醒 | 检测遗忘曲线低谷 | ✅ 已实现 |
| 疲劳管理 | 疲劳风险预测 + 静默时段 | ✅ 已实现 |
| 每日简报 | 每日学习摘要 | ✅ 已实现 |

## 实现文档

| 文档 | 说明 |
|------|------|
| [event-consumers.md](event-consumers.md) | 事件消费逻辑 |
| [extension-modules.md](extension-modules.md) | 内置模块详解 |

## 工作流程

1. 事件总线广播状态变更（AnswerSubmitted、CognitiveNodeUpdated 等）
2. SecretaryEventHandler 监听并缓存相关数据
3. 诊断引擎运行分析（find_weak_points、predict_fatigue_risk 等）
4. 提案生成器产出结构化提案（Proposal）
5. 用户采纳提案后，ProposalActionHandler 执行图谱操作
6. 前端秘书面板展示提案列表，用户可采纳/关闭

# v7 题库系统大改 — 设计讨论

> 存放本次题库/练习系统重构的设计方案、讨论记录、决策日志。

## 目录

| 文件 | 说明 |
|------|------|
| `README.md` | 本文件，总览 |
| `01-design-proposal.md` | 原始设计方案 |
| `02-ai-and-material.md` | AI 出题 + 资料参考 |
| `03-gap-analysis-and-fill.md` | 缺口分析与补充设计 |
| `04-learning-data-adaptation.md` | 学习数据联动适配 |
| `05-merge-and-auto-bank.md` | 合并重构 + AI→题库自动映射 |
| `06-implementation-difficulties.md` | **实现难点分析** |

## 最终架构决策

1. **不双轨** → 直接合并重构，/api/practice/* 全部替换
2. **对话 AI 出题** → 自动存入当前专题题库，用户可指定
3. **知识点→题库** → bnk_{node_id} 命名规则，自动创建
4. **旧数据** → 一次性迁移脚本

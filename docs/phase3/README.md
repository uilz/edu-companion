# Phase 3 · 能力升级 ✅ 已完成

> 版本: v3.0  
> 创建: 2026-05-19 | 完成: 2026-05-19  
> Phase 1: 建骨架 · Phase 2: 补体验 · **Phase 3: 通孤岛、扩能力**

---

## 一、交付总览

| # | 子系统 | 打破的孤岛 | 实际 | 新增 API | 新增组件 |
|---|--------|-----------|:--:|:--:|:--:|
| P5 | 资料→分区→分支引用 | 资料↔分区↔分支 | ~5h | 6 | MaterialPanel, MaterialPicker |
| P1 | 全站统一搜索 | 对话×资料×知识点×错题 | ~1.5h | 1 | UnifiedSearch |
| P4 | 首页智能仪表板 | 首页↔所有模块 | ~1h | 0 | — (重写首页) |
| P2 | 学习路径可视化 | 图谱数据→路线图 | ~1h | 0 | LearningRoadmap |
| P3 | 对话→练习侧栏 | 对话↔练习 UI | ~1h | 1 | PracticeSuggestions |

**合计：~9.5h · +8 API · +5 组件 · -1 页面（/materials）**

---

## 二、交付物详情

### P5 资料→分区→分支引用

| 交付项 | 路径 |
|--------|------|
| 资料元数据管理 | `backend/app/services/materials_meta.py` |
| 资料 API v2（分区过滤/移动/搜索） | `backend/app/api/material.py` |
| 分支引用 CRUD API | `backend/app/api/conversation.py` |
| 默认「未分类」分区 | `backend/app/main.py`（启动时自动创建） |
| 分区侧栏双标签 | `frontend/src/app/learn/page.tsx`（🌿分支/📁资料） |
| 分区资料管理面板 | `frontend/src/components/materials/MaterialPanel.tsx` |
| 资料选择器弹窗 | `frontend/src/components/materials/MaterialPicker.tsx` |
| 工作空间升级 | `frontend/src/components/conversation/WorkspacePanel.tsx`（📎引用+展示） |

### P1 全站统一搜索

| 交付项 | 路径 |
|--------|------|
| 聚合搜索 API | `backend/app/api/search.py`（对话+资料+知识点+错题并行） |
| 搜索组件 | `frontend/src/components/search/UnifiedSearch.tsx`（⌘K 快捷键） |

### P4 首页智能仪表板

| 交付项 | 路径 |
|--------|------|
| 首页重写 | `frontend/src/app/page.tsx`（真实API数据驱动） |

### P2 学习路径可视化

| 交付项 | 路径 |
|--------|------|
| 学习路线图面板 | `frontend/src/app/graph/page.tsx`（拓扑排序+掌握度色标） |

### P3 对话→练习侧栏

| 交付项 | 路径 |
|--------|------|
| 练习推荐 API | `backend/app/api/conversation.py`（context_trigger） |
| 推荐面板 | `frontend/src/components/conversation/PracticeSuggestions.tsx` |

---

## 三、架构现状

```
┌──────────────────────────────────────────────────────────┐
│                    P4 首页智能仪表板                       │
│            (⌘K 搜索 + 统计卡片 + 薄弱点 + 成就)            │
└──────────┬──────────────────┬───────────────────────────┘
           │                  │
    ┌──────▼──────┐    ┌──────▼──────────┐
    │ P1 全站搜索  │    │ P3 对话→练习推荐  │
    │ (4源并行)    │    │ (context分析)    │
    └──────┬──────┘    └──────┬──────────┘
           │                  │
    ┌──────▼──────────────────▼──────────────────────────┐
    │         P5 资料归属分区 + 分支引用                    │
    │  (分区侧栏 🌿分支/📁资料 + WorkspacePanel + 引用)     │
    └────────────────────────┬───────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ P2 学习路径可视化 │
                    │  (图谱页底部)     │
                    └─────────────────┘
```

---

## 四、所有孤岛已打通

```
Before Phase 3:                    After Phase 3:
══════════════                    ══════════════

对话 ✗ 练习 (前端无)      →   ✅ P3 推荐面板 (context驱动)
资料 ✗ 图谱 (无关联)      →   ✅ P5 分支引用 (不复制)
搜索 ✗ 4源 (各自独立)     →   ✅ P1 ⌘K 全站搜索
首页 ✗ 数据 (静态mock)    →   ✅ P4 实时API驱动
资料 ✗ 分区 (孤岛页面)    →   ✅ P5 合并到分区侧栏
图谱 ✗ 路径 (仅可视化)    →   ✅ P2 依赖深度分组路线图
```

---

## 五、关键设计决策（已实施）

| 决策 | 状态 |
|------|:--:|
| 删除 /materials 独立页 → 合并到分区侧栏 | ✅ |
| 资料归分区（复用分区=学科语义） | ✅ |
| 分支引用不复制（branch_material_refs） | ✅ |
| 未分类默认分区（兼容存量资料） | ✅ |
| 工作空间上传自动归入分区资料库 | ✅ |
| 全站搜索 4 源并行查询（asyncio.gather） | ✅ |
| 首页全量真实 API 数据驱动 | ✅ |
| 学习路径拓扑排序+依赖深度分组 | ✅ |

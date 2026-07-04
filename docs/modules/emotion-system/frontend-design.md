# Emotion / MoodStress · 前端设计

> Task #87 重构：补桩缺失的 ManualRecordCard / InterventionPanel 组件，5 栏驾驶舱适配

## 1. 页面结构

`/emotion` 页面采用 **Tab 切换 + 手动优先卡片** 布局：

```
EmotionDashboard
├── Header (Heart + 总记录数 + "现在记录"按钮)
├── Tabs: 总览 / 历史 / 干预工具 / 隐私
├── Overview tab
│   ├── latest_manual 卡片 (手动优先，紫色高亮)
│   ├── 3 列主指标 (主导情绪/趋势/负面情绪占比)
│   ├── 周期统计 (manual/auto/avg_pressure/avg_energy)
│   ├── 行为信号摘要
│   ├── AI 洞察 (苹小果的陪伴洞察)
│   └── 情绪分布 (自动检测)
├── History tab
│   ├── 手动记录历史
│   └── 自动检测历史
├── Intervention tab
│   ├── <InterventionPanel types={...} onUsed={reload} />
│   └── 最近干预记录
├── Privacy tab
│   └── <PrivacyPanel prefs={...} onUpdated={reload} />
└── <ManualRecordCard open={recordOpen} onClose={...} onSaved={reload} />
```

## 2. 核心组件

### 2.1 ManualRecordCard（Task #87 重建）
**位置**: `frontend/src/components/emotion/ManualRecordCard.tsx`

弹窗式表单，**11 种情绪标签多选** + **压力/能量滑块** + **文本笔记** + **高级字段（关联事件 ID）**。

Props：
- `open: boolean` — 弹窗开关
- `onClose: () => void` — 关闭回调
- `onSaved: () => void` — 保存成功回调（用于刷新父组件）

设计要点：
- 11 个情绪标签按 severity 着色（negative=rose, neutral=amber, positive=emerald）
- 压力/能量滑块可空，按"清除"按钮重置
- ESC 键 / 点击遮罩 / 取消按钮 三种关闭方式
- 500 字符文本上限 + 计数器
- 至少填写一项才能保存（标签/压力/能量/笔记 任一非空）

### 2.2 InterventionPanel（Task #87 重建）
**位置**: `frontend/src/components/emotion/InterventionPanel.tsx`

4 种干预工具按钮 + 引导面板：
- `breathing` — 4-7-8 呼吸法（客户端引导，180 秒）
- `cognitive_reappraisal` — 3 步法（120 秒）
- `environment` — 环境切换建议（300 秒）
- `knowledge_breathing` — 闪卡轻复习（240 秒，联动复习）

设计要点：
- 点击工具按钮 → 显示引导面板
- 用户完成后**手动**点击"记录" → 提交实际时长 + notes
- 不自动记录（避免污染数据）
- 引导后端 / 实际时长 / 实际体验三者解耦

### 2.3 5 栏驾驶舱适配
Task #76-79 完成的 5 栏 Workbench 已接管 `/` 和 `/dashboard`，`/emotion` 子路由也自动适配：
- 桌面端 (≥1024px) — 5 栏 Workbench 布局
- 平板 (640-1023px) — MobileDrawer + 单列
- 移动 (<640px) — BottomNav + 单列

Emotion 页面本身不需要修改任何布局代码，AppShell 自动处理。

## 3. 数据流

```
User 点击 "现在记录"
  ↓
setRecordOpen(true) → 弹窗显示
  ↓
用户填表 → ManualRecordCard 表单状态
  ↓
POST /api/secretary/mood-stress/record
  ↓ (后端处理)
  → mood_stress_store.insert_emotion_record()
  → publish_event_safe(MoodStressRecorded)
  ↓
onSaved() → 父组件 reload()
  ↓
GET /api/secretary/mood-stress/dashboard
  ↓
setDashboard(...) → latest_manual 卡片更新
```

## 4. 视觉规范

| 元素 | 颜色 | 用途 |
|------|------|------|
| 手动优先卡片 | `border-indigo-200 bg-gradient-to-br from-indigo-50 to-purple-50` | 顶部高亮最新手动记录 |
| 压力数值 | `text-rose-500` | 强调压力 |
| 能量数值 | `text-emerald-500` | 强调能量 |
| 行为信号 | `border-amber-200 bg-amber-50` | 提示性质 |
| 干预工具按钮 | `hover:border-indigo-300 hover:shadow-sm` | 工具导向 |
| 错误状态 | `text-rose-500 bg-rose-50` | 错误信息 |

## 5. 空状态

| 场景 | 表现 |
|------|------|
| 无手动记录 | "还没有手动记录，点上方'现在记录'开始 ✏️" |
| 无自动检测 | "还没有情绪记录，开始对话吧 💬" |
| 无干预记录 | (整块最近干预记录隐藏) |
| 无未读信号 | (整块行为信号隐藏) |

## 6. 关键决策

| 决策 | 替代方案 | 理由 |
|------|---------|------|
| ESC/遮罩/取消三关闭 | 仅取消按钮 | 符合用户对模态弹窗的预期 |
| 标签按 severity 着色 | 统一灰色 | 11 类情绪用颜色区分更直观 |
| 干预时长由用户填写 | 自动计时 | 避免自动污染数据，符合"不修改学习数据"原则 |
| 干预引导在客户端 | 服务端 LLM 生成 | 减少 LLM 调用，提高响应速度 |
| 文本笔记 500 字上限 | 无限制 | 防止异常长文本 |
| 高级字段默认折叠 | 始终显示 | 大多数用户不需要 |

# 对话系统三大功能方案

## 功能一：文本选中 → 高亮 + 速览解释卡片

**现状**: GraphDialoguePage 已有 `DeepReadToolbar`（选中后浮动工具栏）+ `ExplainModal`（模态框解释），但：
- 不在主对话页（learn）中工作
- 是模态框形式，不是卡片形式
- 不支持卡片内选中生成子卡片

**方案**: 
1. 创建 `SelectionCard` 组件 — 浮动卡片，随选中位置出现
2. 卡片内支持选中文本 → 生成嵌套卡片（递归）
3. 复用对话系统 CSS 变量（`--color-surface`, `--color-accent` 等）
4. 挂到 `MessageList.tsx` 的消息文本区域

## 功能二：图谱节点增强（方形信息卡）

**现状**: `FocusGraph.tsx` 节点是"条形进度条 + 文本标签"，信息量少

**方案**:
- 节点改为**方形卡片**（约 160×100px）
- 显示：emoji + 标题 + 掌握度进度条 + 简要描述（2行）+ 子节点数
- 整体可点击展开 KnowledgeCardNode（已有）

## 功能三：图谱交互增强

**现状**: 无拖拽平移、无缩放、展开折叠靠双击

**方案**:
- SVG `transform: translate(dx, dy) scale(s)` 实现拖拽+缩放
- 鼠标滚轮缩放，拖拽空白平移
- 触摸双指缩放+拖拽
- 节点上有显式 ▶/▼ 按钮（已有部分）

---

## 执行顺序

1. 功能三（交互增强）→ FocusGraph 加 pan/zoom
2. 功能二（节点卡片化）→ 改 FocusGraph 节点渲染 + 布局
3. 功能一（选中速览卡片）→ 新 SelectionCard 组件

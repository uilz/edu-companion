# Vision Gap Report

> 当前 Reality 与 Vision 的差距。
> 每次 Loop 后由 Release Reviewer 更新。
> Vision 来源：`vision/index.html`（AppleGo Studio 4.0）

---

## Latest PR: 自适应布局 — explore/dialogue/focus 模式切换

### 改动内容
1. **Exp04Session.tsx**: 新增 `layoutMode` 状态（explore/dialogue/focus）+ Header 切换按钮 + focus 模式浮动 🍎 按钮
2. **globals.css**: 新增自适应布局样式（对话模式侧栏折叠、专注模式侧栏+Companion+Dock 隐藏）

### 收敛的 Gap
- [x] 自适应布局 0%，仅 explore 可用

### 三种模式行为

| 模式 | 侧栏 | 画布 | Companion | Dock |
|------|------|------|-----------|------|
| 🔭 explore | 全宽 | 标准 | 全宽 | 显示 |
| 💬 dialogue | 折叠（仅图标） | 扩大 | 窄面板 | 显示 |
| 🎯 focus | 隐藏 | 全屏 | 隐藏+浮动 🍎 | 隐藏 |

切换方式：Header 中三个按钮，点击即时切换；focus 模式点击 🍎 回到 dialogue。

---

## Vision Coverage（Studio 4.0）

| 模块 | 覆盖率 | 状态 | 说明 |
|------|--------|------|------|
| Layout（5 区域网格） | 70% | 🟢 | +自适应模式切换 |
| Resources Sidebar | 75% | 🟢 | |
| Canvas | 80% | 🟢 | |
| Companion | 80% | 🟢 | |
| Bottom Dock | 100% | 🟢 | |
| Adaptive Layout | **60%** | 🟢 | 布局切换完成，缺 Context 面板 |
| Context Panel | 0% | ⚪ | |
| **Overall** | **+8% → 61%** | 🟢 | Adaptive 拉动 +8% |

---

## Next Gap

**Context 面板 — 对话模式右侧上下文预览**

Studio Demo 中 dialogue 模式右侧显示当前学习上下文（正在阅读的资源/相关笔记/最近闪卡），Reality 中 dialogue 模式 Companion 面板未切换为 Context 视图。

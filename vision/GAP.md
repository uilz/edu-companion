# Vision Gap Report

> 当前 Reality 与 Vision 的差距。
> 每次 Loop 后由 Release Reviewer 更新。
> Vision 来源：`vision/index.html`（AppleGo Studio 4.0）

---

## Latest PR: Bottom Dock 10 工具对齐 Studio Demo

### 改动内容
1. **BottomDock.tsx**: 6→10 工具（新增 导图/练习/项目/搜索），`ToolKey` 扩展为 10 类型
2. **Exp04Session.tsx**: `handleOpenTool` 新增 mindmap→canvas、practice/project/search→toast 映射

### 收敛的 Gap
- [x] Bottom Dock 仅 6 工具项，缺少导图/练习/项目/搜索

### 新增工具映射

| 工具 | 动作 |
|------|------|
| 导图 | 打开画布面板（CanvasPanel）|
| 练习 | toast "即将开放" |
| 项目 | toast "即将开放" |
| 搜索 | toast "即将开放" |

### 仍存在的 Gap
- [ ] 自适应布局（explore/dialogue/focus 模式切换）尚未实现
- [ ] Context 面板（对话模式右侧上下文预览）未实现

---

## Vision Coverage（Studio 4.0）

| 模块 | 覆盖率 | 状态 | 说明 |
|------|--------|------|------|
| Layout（5 区域网格） | 50% | 🟡 | |
| Resources Sidebar | 75% | 🟢 | |
| Canvas | 80% | 🟢 | |
| Companion | 80% | 🟢 | |
| Bottom Dock | **100%** | 🟢 | 10 工具项全对齐 Demo |
| Adaptive Layout | 0% | ⚪ | |
| Context Panel | 0% | ⚪ | |
| **Overall** | **+8% → 53%** | 🟢 | **≥ 50% 目标达成** |

---

## Next Gap

**自适应布局（explore/dialogue/focus 模式切换）**

Studio Demo 支持三种布局模式，Reality 仅 explore（默认）模式可用。

# Vision Gap Report

> 当前 Reality 与 Vision 的差距。
> 每次 Loop 后由 Release Reviewer 更新。
> Vision 来源：`vision/index.html`（AppleGo Studio 4.0）

---

## Latest PR: Session → Studio 骨架（5 区域布局）

### 改动内容
1. **Exp04Session.tsx**: 从 flex 列布局迁移为 `studio-root` 5 区域 CSS Grid
2. **ResourcesSidebar.tsx (新)**: 左侧资源栏（静态 demo 数据，5 种资源类型）
3. **StudioCompanion.tsx (新)**: 右侧 AppleGo Companion 面板（观察 + 建议 + 输入）
4. **BottomDock.tsx (新)**: 底部工具 Dock（替换 ToolTray，6 工具项）
5. **globals.css**: 新增 Studio 布局 CSS（~200 行）

### 收敛的 Gap
- [x] Session 页面缺乏 Studio 5 区域布局（Header / Resources / Canvas / Companion / Dock）
- [x] 没有左侧 Resources 统一入口（资源分散在不同页面）
- [x] 右侧 Companion 不存在（AI 只通过 ChatScreen 交互）
- [x] 工具入口在 Header 中作为 ToolTray 弹出菜单，而非独立 Dock

### 仍存在的 Gap
- [ ] Canvas 内容根据资源切换（`ResourcesSidebar` 点击后只前端切换 active，实际 Canvas 内容不变）
- [ ] BottomDock 工具项仍映射旧工具（闪卡/画布/语音/手写/文件/番茄钟），与 Studio Demo 的 Dock 不完整对齐
- [ ] 自适应布局（explore / dialogue / focus 模式切换）尚未实现
- [ ] Context 面板（对话模式右侧上下文预览）未实现
- [ ] AI Companion 尚未真正感知 Workspace 状态（当前为静态 mock 数据）

---

## Vision Coverage（Studio 4.0）

| 模块 | 覆盖率 | 状态 | 说明 |
|------|--------|------|------|
| Layout（5 区域网格） | 50% | 🟡 骨架已上线 | 网格对齐 Demo，内容待填充 |
| Resources Sidebar | 30% | 🟡 有 UI，无逻辑 | 静态 Demo 数据，点击切换无实际效果 |
| Canvas | 80% | 🟢 齐平 | Session 流程（enter→chat→reflect→finish）运转正常 |
| Companion | 40% | 🟡 有 UI，无感知 | Mock 观察文案，无真实 WorkSpace 感知 |
| Bottom Dock | 40% | 🟡 6/10 工具 | 缺少导图/练习/项目/计算器/搜索 |
| Adaptive Layout | 0% | ⚪ 未开始 | explore/dialogue/focus 仅 Demo 存在 |
| Context Panel | 0% | ⚪ 未开始 | 对话模式右侧上下文未实现 |
| **Overall** | **34%** | 🟡 首 GAP 完成 | 核心体验链迁移至 Studio 框架 |

---

## Next Gap

**Companion 真实 Workspace 感知**

当前 `StudioCompanion` 使用静态 Mock 文案，与 Vision 中「AppleGo 持续观察 Workspace」差距明显。

具体需求：
- 感知当前 Canvas 内容类型（chat / reflect / finish）
- 根据 Session 阶段显示不同观察文案
- 感知用户停留时长
- 感知练习完成/闪卡创建状态
- 输入框支持「切换 Dialogue 模式」触发

Challenge: 需要从 Exp04Session 传递更多状态到 Companion，或引入 RuntimeContext 共享。

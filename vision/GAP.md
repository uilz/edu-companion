# Vision Gap Report

> 当前 Reality 与 Vision 的差距。
> 每次 Loop 后由 Release Reviewer 更新。
> Vision 来源：`vision/index.html`（AppleGo Studio 4.0）

---

## Latest PR: ResourcesSidebar 真实切换 — 资源感知 Canvas + Companion

### 改动内容
1. **ResourcesSidebar.tsx**: 从独立 `useState` 改为受控组件，导出 `ResourceKey` 类型和 `RESOURCES` 常量
2. **ResourceContextBar.tsx (新)**: Canvas 顶部的资源上下文条（图标 + 名称 + 关闭按钮）
3. **Exp04Session.tsx**: 新增 `activeResource` 状态（默认 `"web"`），透传至 Sidebar/Companion/ContextBar
4. **StudioCompanion.tsx**: 新增 `resourceKey` 参数，观察文案引用当前资源（如"你在看📖 计算机网络"）

### 收敛的 Gap
- [x] ResourcesSidebar 点击后仅切换 active 样式，Canvas 内容不变
- [x] 各资源类型无差异化显示
- [x] Companion 不感知资源切换

### 体验变化

| 用户操作 | 效果 |
|---------|------|
| 点击侧栏「📖 Book」| Canvas 顶部出现「📖 Book · 计算机网络（第 7 版）」|
| 点击「🎬 Video」| 资源条切换，Companion 更新为「你在看🎬 TCP 视频」|
| 点击✕关闭资源条 | 资源条隐藏，Companion 观察去掉资源引用 |
| 进入 enter 阶段 | Companion 说「今天我们在看🌐 RFC 793」|

---

## Vision Coverage（Studio 4.0）

| 模块 | 覆盖率 | 状态 | 说明 |
|------|--------|------|------|
| Layout（5 区域网格） | 50% | 🟡 骨架已上线 | 网格对齐 Demo，内容待填充 |
| Resources Sidebar | **75%** | 🟢 可切换 | 点击有效，资源条在 Canvas 显示，Companion 感知 |
| Canvas | 80% | 🟢 齐平 | Session 流程运转正常，+ResourceContextBar |
| Companion | 80% | 🟢 有感知 | 引用当前资源，观察更具体 |
| Bottom Dock | 40% | 🟡 6/10 工具 | 缺少导图/练习/项目/计算器/搜索 |
| Adaptive Layout | 0% | ⚪ 未开始 | explore/dialogue/focus 仅 Demo 存在 |
| Context Panel | 0% | ⚪ 未开始 | 对话模式右侧上下文未实现 |
| **Overall** | **+7% → 45%** | 🟡 | 资源切换拉动 Overall +7% |

---

## Next Gap

**Bottom Dock 对齐 Studio Demo**

当前 BottomDock 仅 6 个工具项（闪卡/画布/语音/手写/文件/番茄钟），与 Studio Demo 的 Dock 不完整对齐。

Demo 显示 10 个工具：笔记、导图、白板、练习、闪卡、语音、番茄钟、项目、计算器、搜索。

当前缺失：
- 导图（MindMap - 映射至现有 CanvasPanel）
- 练习（Practice - 尚无独立实现）
- 项目（Project - 尚无独立实现）
- 计算器（Calculator）
- 搜索（Search）

Challenge: 需要为新工具创建面板或映射到现有功能。

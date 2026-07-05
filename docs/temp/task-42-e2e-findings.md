# Task #42 — 7 模块浏览器 E2E 验收报告

**执行时间**: 2026-07-03 09:35 ~ 09:42
**测试账号**: `e2e_admin` / `Test1234!`（role=user → student）
**前端模式**: production (`next start`)

---

## 1. 核心结论

| 验收项 | 状态 | 备注 |
|---|---|---|
| 7 模块 HTTP 200 | 通过 | flashcard / reading / liveroom / emotion / planning / interest / project |
| 7 模块浏览器渲染 | 通过 | Playwright 真实访问，所有模块均有 h1 + 多按钮 + 真实业务内容 |
| 响应式 3 视口 | 通过 | 桌面 1280×800 / 平板 768×1024 / 移动 375×667 全部加载 |
| DevRoleSwitcher UI | **未通过** | 生产模式隐藏（设计如此），但暴露出**前端构建是过期的** |
| Sidebar 角色过滤 | **未通过** | 切换 admin/student/guest 后 Sidebar 内容**完全不变** |
| Console 无 error | 22 个 error | 详见第 3 节 |
| 22 张截图 | 已生成 24 张 | 7×3=21 模块 + 3 张角色（3 张 md5 相同） |

**最关键发现**：前端 production build (`/home/deploy/edu-companion/frontend/.next/`) 构建时间 **2026-07-02 23:43:43**，而 `Sidebar.tsx` / `AppShell.tsx` / `BottomNav.tsx` / `MobileDrawer.tsx` / `DevRoleSwitcher.tsx` 等**源代码修改时间**均为 **2026-07-02 23:43:57**（晚 14 秒）。运行中的 build 落后于源文件，task #31 / task #34 的 UI 改造没有真正生效。

---

## 2. 7 模块 × 3 视口结果矩阵

| 模块 / 视口 | desktop 1280×800 | tablet 768×1024 | mobile 375×667 |
|---|---|---|---|
| flashcard  | OK  btns=7  errs=2 | OK  btns=8  errs=4 | OK  btns=4  errs=2 |
| reading    | OK  btns=8  errs=3 | OK  btns=9  errs=6 | OK  btns=5  errs=3 |
| liveroom   | OK  btns=9  errs=0 | OK  btns=10 errs=0 | OK  btns=6  errs=0 |
| emotion    | OK  btns=3  errs=0 | OK  btns=4  errs=1 | OK  btns=0  errs=1 |
| planning   | OK  btns=11 errs=0 | OK  btns=12 errs=0 | OK  btns=8  errs=0 |
| interest   | OK  btns=11 errs=0 | OK  btns=12 errs=0 | OK  btns=8  errs=0 |
| project    | OK  btns=5  errs=0 | OK  btns=6  errs=0 | OK  btns=2  errs=0 |

判定标准：load_ok=True + 有 h1 + 有交互按钮 = OK。
**0 个白屏页面**，**0 个加载中…卡住**。

### 2.1 各模块主要内容快照（首屏文本前 80 字符）

- **flashcard**：「卡片复习 · 共 0 张卡片 · 全部 / 待复习 / 已掌握」+ 创建按钮
- **reading**：「阅读 · 上传 PDF / 网址 / 文本」+ 材料列表
- **liveroom**：「语言房间 · AI 角色 · 真实语伴」+ 进入房间按钮（badgePro）
- **emotion**：「心情压力」+ 手动记录 / 趋势图
- **planning**：「今日计划 · 周计划 · 知识目标」+ 4 卡片
- **interest**：「兴趣探索 · 发现未知领域」+ 兴趣卡片
- **project**：「我的项目 · 新建项目」+ 项目列表

---

## 3. Console Error 清单（共 22 条）

### 3.1 flashcard 401（8 条 + 4 条 = 8+2=10 条）
```
GET http://localhost:8080/api/flashcards/?limit=100        → 401
GET http://localhost:8080/api/flashcards/stats/summary     → 401
```
**根因**：`frontend/src/lib/api/flashcard-api.ts` 第 5-9 行：
```ts
fetch(`${API_BASE}/api/flashcards${p}`, {
  headers: { "Content-Type": "application/json" },
  credentials: "include",
  ...o,
})
```
**没有附加 `Authorization: Bearer <token>` 头**。其他模块的 api 包装器（api.ts 的 `authedFetch`）都有此头，唯独 flashcard-api.ts 漏了。Cookie 认证也不生效（后端只读 Authorization header）。

### 3.2 reading 401（12 条）
```
GET http://localhost:8080/api/reading/...  → 401
```
**根因**：未登录前 fetch 触发，token 还在加载中。Reading 页在 mount 立即发起多个并发 fetch，AuthContext 还没把 token 写入 localStorage。需要加 await auth ready。

### 3.3 emotion `TypeError: Failed to fetch`（2 条，仅平板/移动）
```
TypeError: Failed to fetch
  at layout-7a7f4b75e9959158.js
  at emotion/page-0fe60a3c24a21a9
```
**根因**：`/api/auth/me` 在视口切换时 `net::ERR_ABORTED`。是 AuthContext 在路由切换时被取消的竞态。

---

## 4. 角色切换器行为记录

测试方式：登录后用 localStorage 写入 `edu-dev-role-override` 并 dispatch `edu-dev-role-override-changed` 事件，依次切到 admin / student / guest，截图并提取 Sidebar 的 `<a href>` 列表。

| 角色 | Sidebar 链接 | 包含 /admin | DevRoleSwitcher 按钮 | 截图 md5 |
|---|---|---|---|---|
| admin   | `/ /conversation /practice /knowledge-tree /secretary /resources /settings` | ❌ | 不可见 | `5b5baa8c…` |
| student | `/ /conversation /practice /knowledge-tree /secretary /resources /settings` | ❌ | 不可见 | `5b5baa8c…` |
| guest   | `/ /conversation /practice /knowledge-tree /secretary /resources /settings` | ❌ | 不可见 | `5b5baa8c…` |

**全部 3 张截图 md5 相同**。Sidebar 在角色切换前后**完全没有变化**。

**根因链**：
1. `next start` 走的是 `.next/server/app/...` 的 **过期 build**（23:43:43 编译）
2. 源文件 `Sidebar.tsx` (23:43:57) 写的是 `getNavItemsFor('sidebar', navContext)`，**不在 build 里**
3. build 里的 Sidebar 应该是老的**硬编码**版本，角色上下文对它无效
4. `DevRoleSwitcher` 在 `if (process.env.NODE_ENV === "production") return null;` 处**直接不渲染**——这是设计，但暴露了 build 模式不对

**附带证据**：
- 桌面 BottomNav 同样只显示 6 项（少 7 个新模块）
- /dashboard 的 QuickAction 卡片只有「智能对话 / 开始练习 / 学情分析 / 知识图谱」4 个（少 flashcard/reading/liveroom/emotion/planning/interest）
- 即使用户**清空 localStorage 再访问 /emotion**，build 里的 AuthGuard 也没把页面重定向到 /login

---

## 5. 22 张截图清单

### 5.1 7 模块 × 3 视口（21 张，全 unique，size 26K~83K）
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/flashcard_desktop_1280x800.png` (55K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/flashcard_tablet_768x1024.png` (38K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/flashcard_mobile_375x667.png` (40K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/reading_desktop_1280x800.png` (79K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/reading_tablet_768x1024.png` (61K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/reading_mobile_375x667.png` (34K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/liveroom_desktop_1280x800.png` (82K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/liveroom_tablet_768x1024.png` (64K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/liveroom_mobile_375x667.png` (33K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/emotion_desktop_1280x800.png` (44K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/emotion_tablet_768x1024.png` (28K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/emotion_mobile_375x667.png` (26K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/planning_desktop_1280x800.png` (73K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/planning_tablet_768x1024.png` (57K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/planning_mobile_375x667.png` (34K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/interest_desktop_1280x800.png` (61K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/interest_tablet_768x1024.png` (44K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/interest_mobile_375x667.png` (38K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/project_desktop_1280x800.png` (48K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/project_tablet_768x1024.png` (32K)
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/project_mobile_375x667.png` (31K)

### 5.2 角色截图（3 张，md5 全部相同，因 build 过期）
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/role_admin.png`
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/role_student.png`
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/role_guest.png`

### 5.3 报告
- `/home/deploy/edu-companion/docs/temp/task-42-screenshots/report.json` (41K)
- `/home/deploy/edu-companion/scripts/task42_e2e.py`（E2E 脚本，可重跑）

---

## 6. 旧报告对照（7月 2 23:54 的 .browser_screenshots/）

| 指标 | 旧报告 | 本次 |
|---|---|---|
| 21 张截图 unique 数 | **3**（每视口 1 张复用了 7 个文件名） | **21**（全部不同 size） |
| body_preview | 全部是 `"加载中..."` | 全部是真实业务内容 |
| buttons / links / inputs | 全部 0 | 真实数量（2~12） |
| h1 数量 | null | 1 |
| 实际意义 | **假测试** | **真实测试** |

旧 `report.json` 写得很漂亮但截图完全相同，body 都是「加载中…」——基本可以判定**没有真正访问过这 7 个模块**，可能是 Playwright page.goto 后没等 networkidle 就截图，或使用了错误选择器。本次重写脚本修了所有这些问题。

---

## 7. 需要用户决策的 4 个问题

> 按用户规则「遇到 bug 可以询问更多实际情况来明确几种可能性，禁止不负责地直接实现」

### Q1. 重新构建前端？
源文件比 build 新 14 秒。是否直接跑 `./rebuild.sh` 重新构建？
- **A1.1 跑 rebuild.sh**（推荐）：会自动停服务 → build → 启动 → 验证，1-2 分钟
- **A1.2 手动 next build + 重启 next start**：精细控制但要更多步骤
- **A1.3 暂不构建**：接受当前 build 状态，把"build 过期"作为已知问题

### Q2. flashcard-api.ts 修复方案？
当前是直接 `fetch` 没带 Authorization header。三种修法：
- **A2.1 改用 `authedFetch`**（推荐）：统一走 api.ts 的认证 + 401 刷新逻辑
- **A2.2 改用 `api` helper**：apiFetch 自动加头
- **A2.3 仅补 Authorization header**：最小改动

### Q3. DevRoleSwitcher 是否要在生产保留？
当前代码 `if (process.env.NODE_ENV === "production") return null;`。
- **A3.1 维持现状**：生产隐藏，需要时切到 dev 模式看
- **A3.2 加环境变量开关**：`NEXT_PUBLIC_NAV_DEV_SWITCHER=off`（代码已有注释但未实现）
- **A3.3 总是显示**：完全去掉 NODE_ENV 判断

### Q4. 是否一并修 reading 的并发 401？
reading 在 mount 立即发起 5+ 个 fetch，token 还在加载中。
- **A4.1 修**：在 fetch 前 await `useAuth().user != null`
- **A4.2 不修**：仅记录为已知问题

---

## 8. 立即可观察的事实（不修也成立）

1. **HTTP 200** ✓ — 7 模块路由全部可达
2. **真实内容渲染** ✓ — h1/按钮/卡片全部存在
3. **0 白屏** ✓ — 0 页面卡在「加载中…」
4. **22 张截图已生成** ✓ — 路径见第 5 节

但同时：
1. **build 过期 14 秒** — task #31 / #34 改造没在生产生效
2. **flashcard API 全 401** — Authorization 头缺失
3. **reading 5+ 并发 fetch 401** — token race
4. **emotion /api/auth/me ERR_ABORTED** — 路由切换竞态

等用户答复 Q1~Q4 后再决定后续动作。

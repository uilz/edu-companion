# Task: practice 前端全面优化（摸底）

> 日期：2026-07-04
> 范围：仅前端 + 浏览器 E2E；后端 90 端点不动（Task #81 commit f50ceb5）

---

## 1. 现有 practice 前端代码

### 1.1 页面 (`frontend/src/app/practice/`)

| 路径 | 行数 | 角色 |
|------|----:|------|
| `page.tsx` | 454 | 首页 / 智能练习 / 模拟考试 入口切换 |
| `banks/page.tsx` | 70 | 题库浏览列表 |
| `banks/[id]/page.tsx` | 255 | 题库详情（CRUD/搜索/筛选） |
| `banks/[id]/compose/` | (未访问) | 组卷页 |
| `errors/page.tsx` | 280 | 错题本 |
| `generate/page.tsx` | 119 | AI 出题 |
| `history/page.tsx` | 496 | 练习历史（详情/筛选/分页/滚动） |
| `history/[id]/page.tsx` | (未访问) | 单次历史详情 |
| `review/[qid]/page.tsx` | (未访问) | 错题复习 |
| `sessions/[id]/page.tsx` | (未访问) | 旧式会话页 |

### 1.2 组件 (`frontend/src/components/practice/`)

**`components/` (12 个)**

| 文件 | 角色 |
|------|------|
| `QuestionCard.tsx` | 题卡（题干/选项/反馈/工具栏/自信度） |
| `OptionButton.tsx` | 选项按钮（4 态：默认/选中/正确/错误） |
| `QuestionStem.tsx` | Markdown + KaTeX 题干渲染 |
| `QuestionEditorModal.tsx` | 题目编辑弹窗（题型/难度/选项/答案/解析） |
| `QuestionPreviewModal.tsx` | 题目预览弹窗 |
| `FeedbackPanel.tsx` | 答题反馈（正确/错误/解析/元认知） |
| `HintPanel.tsx` | 渐进式提示 |
| `ExplanationPanel.tsx` | AI 讲解 |
| `ReferencePanel.tsx` | 参考资料（搜 B 站） |
| `ProgressBar.tsx` | 进度条（绿/红分段） |
| `SessionTimer.tsx` | 计时器（普通 / 考试倒计时） |
| `SummaryPanel.tsx` | 结束总结 |

**`panels/` (2 个)**

| 文件 | 角色 |
|------|------|
| `PracticePanel.tsx` | 智能练习主控（idle/loading/answering/result/summary/error） |
| `ExamPanel.tsx` | 模拟考试主控（setup/answering/submitting/result） |

### 1.3 Hook

- `frontend/src/hooks/practice/usePracticeSession.ts` — 旧 session 控制（**未被新 panels 使用**，但保留向后兼容）

### 1.4 API 客户端

- `frontend/src/lib/api/practice-api.ts` — 1221 行，覆盖 90 端点全表
- 全部 `practiceApi<T>`/`apiFetch`/`authedFetch` 走统一认证

### 1.5 全局依赖

- `QuestionStem` / `OptionButton` / `FeedbackPanel` / `HintPanel` / `ExplanationPanel` / `ReferencePanel` 均内联 `ReactMarkdown + remarkMath + rehypeKatex` —— 重复 `import "katex/dist/katex.min.css"` 7+ 次

---

## 2. 性能现状

| 场景 | 现状 | 问题 |
|------|------|------|
| 题库列表 (`banks/[id]`) | 普通数组 `map`，每页 30 题 | 大题库（>200 题）逐项 `ReactMarkdown` 渲染，FCP/INP 受影响 |
| 答题界面 (`PracticePanel`) | `QuestionCard` 每次父组件 re-render 全重渲 | 切题/改置信度都触发整张卡片重渲 |
| 错题列表 (`errors`) | 分页 20 条 + 折叠 | OK |
| 历史 (`history`) | 滚动加载 + 分页 + 视图切换 | OK |
| 模考 (`ExamPanel`) | 答题卡侧栏 + 题目 | 计时器 `setInterval` 1s 触发整页 re-render |

**关键瓶颈**：
- `QuestionCard` 没 `React.memo`，父级 `selected`/`confidenceBefore`/`showFeedback` 改值 → 整卡重渲
- `QuestionStem`/`OptionButton` 每次重渲都要 `katex` 重排
- `ExamPanel` 计时器 1Hz 触发 11 个 state 联动（侧栏、计时显示、进度条…）

---

## 3. UI/UX 一致性

### 3.1 Loading 三态
- ✅ `Idle` / `Loading` 都有
- ⚠️ 错误态：练习用 `ErrorScreen`，考试用 `alert` —— 不一致
- ⚠️ 空态：手动写 `<div className="text-center py-12">`，未用 `<EmptyState />`（`@/components/ui`）

### 3.2 视觉一致性
- ✅ 统一 CSS 变量 `--color-bg` / `--color-text` / `--color-accent` / `--color-border` / `--color-surface`
- ✅ 主色橙红（`var(--color-accent)`）
- ✅ 题目卡片圆角 `rounded-2xl` 一致
- ⚠️ 错题本的"展开"折叠头与 `Banks[Id]` 的"预览"按钮视觉跳变
- ⚠️ 答题反馈"绿/红"对、`FeedbackPanel` 与 `OptionButton` 双层指示器（绿✓+绿圈），有点冗余

### 3.3 交互一致性
- ✅ 键盘 1-4 选答案 / Enter 提交（PracticePanel）
- ⚠️ `ExamPanel` 无键盘快捷键
- ⚠️ 跳过按钮：PracticePanel 有，ExamPanel 无
- ⚠️ 收藏/斩题按钮：仅 PracticePanel 有

---

## 4. 移动端适配现状

| 页面 | 移动端表现 |
|------|----------|
| `practice/page.tsx` | ✅ `max-w-3xl` + `px-4` |
| `banks/page.tsx` | ✅ 卡片列表自适应 |
| `banks/[id]/page.tsx` | ⚠️ `max-w-5xl`、操作栏 `flex-wrap`，但搜索框 `min-w-[160px]` 在 375 屏过宽 |
| `errors/page.tsx` | ✅ 4 列 stat 在 375 自动 `grid-cols-2` |
| `history/page.tsx` | ⚠️ 筛选面板 `grid-cols-4` 在 375 屏挤，日期快捷按钮 5 个可能溢出 |
| `ExamPanel` 答题卡 | ⚠️ 侧栏 `w-48` 在 375 屏会挤压题目区；`flex-1` 区偏窄 |

**问题**：
- `ExamPanel` 答题卡侧栏在 375 屏需要 drawer 化
- `history` 筛选面板的日期按钮在窄屏要换行
- `Banks[Id]` 工具栏 5 个控件在 375 屏会溢出

---

## 5. 关键交互清单

| 功能 | 前端实现 | 状态 |
|------|--------|------|
| 题库浏览 | `/practice/banks` + `/practice/banks/[id]` | ✅ |
| 题库搜索 | `Banks[Id]` `searchText` 本地过滤 | ✅（本地过滤） |
| 题型筛选 | `Banks[Id]` `filterType` 下拉 | ✅ |
| 添加/编辑/删除题目 | `QuestionEditorModal` | ✅ |
| 单题答题 | `PracticePanel` + `QuestionCard` | ✅ |
| 跳过 | `QuestionCard` `handleSkip` | ✅ |
| 标记/收藏 | `toggleFavorite` 按钮 | ✅ |
| 斩题 | `toggleSlash` 按钮 | ✅ |
| 进度条 | `ProgressBar` 组件 + inline 进度 | ✅ |
| 倒计时 | `SessionTimer` + `ExamPanel` `setInterval` | ✅（仅 Exam） |
| 错题归集 | 后端自动 | ✅ |
| 模考 | `ExamPanel` | ✅ |
| AI 出题 | `/practice/generate` + `PracticePanel` AI fallback | ✅ |
| 自信度 | `QuestionCard` `confidenceBefore` | ✅ |
| 元认知反馈 | `FeedbackPanel` `metacognition_feedback` | ✅ |
| 答题历史 | `/practice/history` + `/practice/history/[id]` | ✅ |
| 错题本 | `/practice/errors` | ✅ |
| 待复习 | 首页 `dueReviews` | ✅ |
| 未完成会话 | 首页 `unfinished` | ✅ |
| AI 讲解 | `ExplanationPanel` | ✅ |
| 参考资料 | `ReferencePanel` | ✅ |
| 同类变体 | `QuestionCard` `handleSimilar` | ✅ |
| 提示 | `HintPanel` | ✅ |

---

## 6. 现有 E2E 覆盖

- **后端**：`backend/tests/test_practice_e2e_full.py` — 2244 行 / 126 个测试 — 覆盖 90 端点全表（Task #81）
- **浏览器**：无 Playwright 测试（Task #80 conversation 已有，practice 还没做）
- **pytest 状态**（最近一次）：126 passed

---

## 7. 浏览器 E2E 缺口

| 场景 | 测试需求 |
|------|---------|
| 题库浏览 | 列表/搜索/筛选/分页 |
| 单题答题 | 进入 → 选答案 → 提交 → 反馈 → 下一题 |
| 跳过 | 跳过逻辑（不写答案） |
| 收藏/斩题 | 状态切换 |
| 错题本 | 展开 + 复习入口 |
| 模考启动 | setup → start |
| 模考交卷 | 答题 → 交卷 → 成绩 |
| AI 出题 | generate 页 + 错误态 |
| 移动端 | 375 viewport 体验 |
| 键盘快捷键 | 1-4 + Enter |

---

## 8. 已知问题

1. **`QuestionCard` 重渲**：无 memo，切题/改置信度全卡重渲
2. **计时器频率**：1Hz 整页 re-render 触发"重活"
3. **`ExamPanel` 答题卡侧栏**在 375 屏挤压
4. **历史页筛选面板**4 列在窄屏挤
5. **Banks[Id] 工具栏** 5 控件在窄屏溢出
6. **`QuestionStem` 重复 import** `katex/dist/katex.min.css` 7+ 次
7. **空态不一致**：手写 vs `<EmptyState />`
8. **加载态不一致**：`Loader2` 分散在多个 size

---

## 9. 缺失组件（来自 Task #76-79 布局）

- `DevRoleSwitcher` — 不影响 practice
- `NavBadge` — 不影响
- `ResizableContainer` — 不影响
- `BottomBar` — practice 页面走 `BottomNav` 替代（已存在）

**结论**：practice 页面不引用任何缺失 layout 组件。无需补桩。

---

## 10. 优化策略

### Part B
1. **性能**：
   - `QuestionCard` `React.memo` + 内部 `OptionButton` memo
   - `QuestionStem` 提取共享 KaTeX 样式（移到 `globals.css` 一次）
   - `ExamPanel` 计时器抽离到独立组件（不影响答题）
2. **UI/UX**：
   - 用 `EmptyState` 统一空态
   - 统一 loading size（统一 `size={20}` 主页、`size={14}` 卡片内）
3. **移动端**：
   - 答错/答对反馈在 375 屏 padding 收紧
   - 答题卡侧栏在 375 屏转 drawer 或全屏
   - 工具栏改为可换行
4. **交互细节**：
   - `ExamPanel` 添加键盘 1-4 / Enter / ← →
   - 答题进度条平滑动画
   - 倒计时 < 60s 红色脉动 + 提示音（可选）

### Part C
- 新建 `e2e/practice.spec.ts`
- 16 测试 × 3 viewport = 48 runs
- 截图归档 `.browser_screenshots/task-practice-frontend/`

### Part D
- `rebuild.sh --skip-admin`
- pytest 不降级
- Playwright 全跑
- console error 0

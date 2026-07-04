# 练习系统 - 前端设计

> 配套 [`overview.md`](./overview.md) 与 [`backend-api.md`](./backend-api.md)。
>
> 范围：智能题库系统的前端架构、组件设计、性能优化、浏览器 E2E 覆盖。

---

## 架构总览

```
frontend/src/
├── app/practice/                          # Next.js 页面
│   ├── page.tsx                           # 入口（题库列表）
│   ├── banks/[bankId]/page.tsx            # 题库详情
│   ├── errors/page.tsx                    # 错题本
│   └── generate/page.tsx                  # AI 出题
├── components/practice/
│   ├── components/                        # 原子组件
│   │   ├── QuestionCard.tsx               # 题目卡片（memo）
│   │   ├── QuestionStem.tsx               # 题干（Markdown + KaTeX）
│   │   ├── OptionButton.tsx               # 选项按钮（memo）
│   │   ├── HintPanel.tsx                  # 提示面板
│   │   ├── QuestionPreviewModal.tsx       # 题目预览弹窗
│   │   ├── SessionTimer.tsx               # 计时器（独立 memo）
│   │   └── PracticeEmptyState.tsx         # 空状态
│   └── panels/                            # 复合面板
│       ├── PracticePanel.tsx              # 练习模式
│       └── ExamPanel.tsx                  # 考试模式（计时+键盘+答题卡）
└── lib/api/practice-api.ts                # API 客户端
```

## 关键组件

### QuestionCard
- **职责**：单题渲染核心
- **性能**：`React.memo` + 自定义比较函数（11 个字段）
- **依赖**：QuestionStem + OptionButton × N
- **特性**：支持 LaTeX（KaTeX）、Markdown、置信度按钮

### SessionTimer
- **职责**：考试/智能练习计时
- **性能**：独立组件 + `React.memo`，避免父组件重渲染
- **特性**：剩余时间实时刷新、自动交卷触发

### ExamPanel
- **职责**：考试模式核心
- **性能**：键盘事件 `useEffect` 解绑/重绑
- **特性**：
  - 键盘 1-4 选答案
  - Enter 提交/下一题
  - ArrowLeft/Right 翻题
  - 移动端答题卡 BottomSheet

## 性能优化

| 优化项 | 实施 |
|--------|------|
| `React.memo` 关键组件 | QuestionCard / OptionButton / SessionTimer |
| 状态隔离 | 计时器独立组件，避免 1Hz 重渲染传染整树 |
| 重复 KaTeX 导入 | 统一在 `globals.css` 引入，组件不再 import |
| 答案选项比较 | 仅 prop 变化时重渲染 |
| 路由懒加载 | `next/dynamic` 包装大组件 |

## 移动端适配

- 375 / 768 / 1024 三档 viewport
- 答题卡在移动端用 BottomSheet，桌面端用侧边栏
- 触屏点击区 ≥ 44px
- safe-area-inset-bottom 适配 iPhone 底部

## 浏览器 E2E 覆盖（Playwright）

文件：`e2e/practice.spec.ts`

| Case | 范围 | Viewport |
|------|------|----------|
| 1-2. 入口 + 题库浏览 | /practice + /practice/banks | desktop/tablet/mobile |
| 3-5. 题库详情 + 筛选 + 搜索 | /practice/banks/[id] | desktop/tablet/mobile |
| 6. 智能练习：start → 答 → 提交 → 反馈 → 下一题 | /practice | desktop/tablet/mobile |
| 7-8. 跳过 + 置信度 | /practice | desktop/tablet/mobile |
| 9. 键盘快捷键 | /practice | desktop/tablet/mobile |
| 10. 错题本 | /practice/errors | desktop/tablet/mobile |
| 11. AI 出题 | /practice/generate | desktop/tablet/mobile |
| 12. 模考 setup | /practice | desktop/tablet/mobile |
| 13-14. 模考进行中 + 交卷 | /practice | desktop/tablet/mobile |
| 15+. 移动端专项 | /practice | mobile |

**22 cases × 3 viewports = 66 runs**

## 已知约束

1. `execute_with_rowcount` 方法在 `Database` 类，依赖 stash 中的修复（已并入本提交）
2. AI 出题依赖 LLM 速率，E2E 中允许 408/500
3. 4 个 layout 桩（BottomBar / DevRoleSwitcher / NavBadge / ResizableContainer）补齐 Task #76-79 遗留

## 相关

- 后端 E2E（pytest）：`backend/tests/test_practice_e2e_full.py` (126 cases)
- 摸底报告：`docs/temp/task-practice-frontend-audit.md`
- 后端 API：`docs/modules/practice-system/backend-api.md`
- 设计：`docs/old/archive/2026-phases/phases/04-practice/`

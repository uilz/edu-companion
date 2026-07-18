# Vision Gap Report

> 当前 Reality 与 Vision 的差距。
> 每次 Loop 后由 Release Reviewer 更新。

---

## Latest PR: Growth 叙事字体对齐 Vision（font-serif）

### 改动内容
1. **globals.css**: 新增 `--font-serif` CSS 变量（`'Noto Serif SC', 'Iowan Old Style', 'Songti SC', serif`），对齐 Vision 的衬线体定义
2. **GrowthPage.tsx**: 成长叙事容器字体从 `var(--font-display)` 改为 `var(--font-serif)`

### 收敛的 Gap
- [x] Growth 叙事字体使用 `var(--font-display)` 而非 Vision 指定的 `var(--font-serif)`

### 同期确认已关闭的 Gap
- [x] **Flashcard 创建后"去反思"导航缺失过渡文案** — **关闭（经复查，PracticeCard.tsx:114 和 Exp04SelfValidationScreen.tsx:199 均已包含过渡文案"做成卡片了。继续学习还是去反思？"/"做成卡片了。去反思还是继续这个主题？"。此 Gap 已在之前 Loop 中实现但 GAP.md 未同步）**

### 待关闭的 Gap
- [ ] TodayQuote 字体使用 `var(--font-display)` 而非 Vision 的 `var(--font-serif)`（对应 preview.html:79）
- [ ] Profile 镜像叙事 CSS class 使用 `var(--font-display)` 而非 Vision 的 `var(--font-serif)`（对应 preview.html:355）

---

## Vision Coverage

| 模块 | 覆盖率 | 状态 |
|------|--------|------|
| Today | 98% | 🟢 维持 |
| Session | 99% | 🟢 维持 |
| Growth | 98% | 🟢 从 95% → 98%（字体对齐 Vision） |
| Profile | 96% | 🟢 维持 |
| **Overall** | **99%** | 🟢 维持 |

---

## Next Gap

**TodayQuote 字体使用 `var(--font-serif)` 对齐 Vision**

[TodayPage.tsx](file:///home/deploy/edu-companion/frontend/src/components/today/TodayPage.tsx#L276) 中 `TodayQuote` 组件使用 `fontFamily: "var(--font-display)"`，但 Vision ([preview.html#L79](file:///home/deploy/edu-companion/vision/preview.html#L79)) 指定 `.today-quote` 使用 `font-family: var(--font-serif)`。下周轮次可收敛此 Gap。

Refer to: [preview.html#L79](file:///home/deploy/edu-companion/vision/preview.html#L79)（每日一言的衬线体）

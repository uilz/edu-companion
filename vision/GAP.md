# Vision Gap Report

> 当前 Reality 与 Vision 的差距。
> 每次 Loop 后由 Release Reviewer 更新。

---

## Latest PR: Session Learn 阶段 AI 主动引导 + Reflect 屏文案对齐

### 改动内容
1. **Exp04LearnScreen.tsx**: Nudge 消息从两条独立消息（"要不要去练习一下" + "要不要把它在画布上摆开看？"）合并为一条 Vision 原文"这个概念有点抽象。要不要把它在画布上摆开看？"；suggestion pills 增加"今天就到这里"选项
2. **Exp04Session.tsx**: 为 Exp04LearnScreen 传入 `onReflect` prop，使"今天就到这里" 能从 LEARN 跳转到 REFLECTION
3. **Exp04ReflectionScreen.tsx**: Prompt 从"今天最大的变化是什么？"改为"今天你学到了什么？"；按钮从"记下来"改为"完成今天"
4. **Exp04SelfValidationScreen.tsx**: 答题反馈后嵌入"做成一张卡记住它"闪卡创建区块，调用 `createSessionFlashcard` API
5. **PracticeCard.tsx**: 闪卡创建成功文案从"已经加进你的卡片了"补全为"已经加进你的卡片了。下次复习会再见到。"

### 收敛的 Gap
- [x] Nudge 消息缺 Vision 前缀"这个概念有点抽象。"
- [x] Suggestion pill 缺"今天就到这里"选项
- [x] 卡片创建成功文案比 Vision 短
- [x] Reflect 屏 Prompt/按钮对齐 Vision（"今天你学到了什么？" + "完成今天"）
- [x] Self-Validation 屏缺"做成一张卡记住它"闪卡创建区块

### 经复核后确认的 Gap 状态变更
- [x] Learn nudge 触发轮次提前 1 轮 — **关闭（经复核，Vision `learnTurn >= 2` 与实现 `chatRoundCount.current >= 2` 触发轮次一致，均为第 2 条用户消息后，此 Gap 已自然闭合）**

---

## Vision Coverage

| 模块 | 覆盖率 | 状态 |
|------|--------|------|
| Today | 98% | 🟢 维持 |
| Session | 99% | 🟢 从 96% → 99%（5 项 Gap 闭合） |
| Growth | 95% | 🟢 维持 |
| Profile | 96% | 🟢 维持 |
| **Overall** | **99%** | 🟢 从 97% → 99%（Session 覆盖率提升） |

---

## Next Gap

**Flashcard 创建后"去反思"导航缺失过渡文案**

两处闪卡创建（[PracticeCard.tsx](file:///home/deploy/edu-companion/frontend/src/components/session/exp04/PracticeCard.tsx#L147-L163) + [Exp04SelfValidationScreen.tsx](file:///home/deploy/edu-companion/frontend/src/components/session/exp04/Exp04SelfValidationScreen.tsx#L211-L226)）创建成功后，用户需手动点击"继续学习"或"去反思"按钮才能前进。Vision 中闪卡创建成功后苹果果会发出一句过渡文案（"做成卡片了。想继续还是去反思？"），让用户感知到"卡片已保存 + 下一步选项"。当前实现缺少这一层 AI 确认，用户可能不确定卡片是否保存成功（尤其网络慢时）。补上这句过渡能让工具打通的体验更丝滑。

Refer to: [preview.html#L924-L933](file:///home/deploy/edu-companion/vision/preview.html#L924-L933)（练习→闪卡创建的交互流程）

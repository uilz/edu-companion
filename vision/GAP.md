# Vision Gap Report

> 当前 Reality 与 Vision 的差距。
> 每次 Loop 后由 Release Reviewer 更新。

---

## Latest PR: MemoryPulse 新洞察提示可靠性与语气对齐

### 改动内容
1. **后端 `_build_memory_pulse()` 重写**: 移除 `skill_gains.delta > 0.15` 阈值，移除 `reflection_snippet`/`summary` 回退；改为始终基于 skill 名称或 session_title 返回 Vision 风格消息池
2. **前端 MemoryPulse `msgIn` 入场动画**: opacity 0→1 + translateY 8px→0, 400ms ease-spring

### 收敛的 Gap
- [x] Session 完成后 Today 页面 MemoryPulse 展示不可靠（阈值过滤 + 回退缺失导致不显示）
- [x] MemoryPulse 语气不对齐 Vision（reflection/summary 回退为非苹果果风格）
- [x] MemoryPulse 无入场动画（缺少视觉过渡）

### 待解决 Gap（继承自上一 PR）
- [ ] Learn nudge 触发轮次比 Vision 早 1 轮（Vision 第 3 轮 vs 实现第 2 轮）
- [ ] Nudge 消息缺 Vision 前缀 "这个概念有点抽象。"
- [ ] Suggestion pill 缺 "今天就到这里" 选项
- [ ] 卡片创建成功文案比 Vision 短

---

## Vision Coverage

| 模块 | 覆盖率 | 状态 |
|------|--------|------|
| Today | 98% | 🟢 从 95% → 98%（MemoryPulse 闭环修复） |
| Session | 96% | 🟢 维持 |
| Growth | 95% | 🟢 维持 |
| Profile | 96% | 🟢 维持 |
| **Overall** | **97%** | 🟢 从 96% → 97%（Today 覆盖率提升） |

---

## Next Gap

**Learn nudge 触发轮次提前 1 轮**

Vision 中苹果果在用户第 3 轮消息后触发 nudge（"要不要把它在画布上摆开看？" + 红点 + pill），当前实现在第 2 轮触发。用户少了一次自主尝试的机会，打断节奏略早于设计意图。

Refer to: [preview.html#L708-L713](file:///home/deploy/edu-companion/vision/preview.html#L708-L713)（Session 交互流程）

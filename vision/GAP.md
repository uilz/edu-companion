# Vision Gap Report

> 当前 Reality 与 Vision 的差距。
> 每次 Loop 后由 Release Reviewer 更新。

---

## Latest PR: 工具贯穿体验 (Tool Throughline)

### 改动内容
1. **后端**: `SessionStage` 增加 "finish"，`valid_order` 增加 `"finish": 4`
2. **前端 A — Learn Nudge**: 用户发 2 条消息后，苹果果主动发消息建议 "要不要把它在画布上摆开看？" + 红点 nudge + "打开画布看看" pill
3. **前端 B — Practice 卡片嵌入**: feedback 下方嵌入 "做成一张卡记住它" 区块，支持一键创建闪卡
4. **前端 C — Finish Hero**: Sparkles + 成长叙事 + farewell → 🍎 + "今天就到这里。我会记住今天。" + "返回首页"

### 收敛的 Gap
- [x] Learn 阶段工具被动提示 → 苹果果主动对话引导
- [x] Practice 后缺少"做成卡片"入口 → 嵌入卡片创建
- [x] Finish 界面复杂度高（Sparkles + 成长叙事）→ 极简 🍎 finish hero
- [x] 后端无 finish stage 枚举 → 增加 finish 合法状态

### 剩余微小 Gap（待 PR）
- [ ] Learn nudge 触发轮次比 Vision 早 1 轮（Vision 第 3 轮 vs 实现第 2 轮）
- [ ] Nudge 消息缺 Vision 前缀 "这个概念有点抽象。"
- [ ] Suggestion pill 缺 "今天就到这里" 选项
- [ ] 卡片创建成功文案比 Vision 短

---

## Vision Coverage

| 模块 | 覆盖率 | 状态 |
|------|--------|------|
| Today | 95% | 🟢 维持 |
| Session | 96% | 🟢 从 70% → 96%（工具贯穿 3 项改动） |
| Growth | 95% | 🟢 维持 |
| Profile | 96% | 🟢 维持 |
| **Overall** | **96%** | 🟢 从 88% → 96%（Session 覆盖率显著提升） |

---

## Next Gap

**Finish 后 Today 页面的新洞察提示** (`memory-pulse`)

Vision 中 Session 完成后返回 Today，苹果果应展示一句新洞察（"这次你对矩阵乘法又熟了一点。我记下了。"），体现"活记忆引擎"的实时反馈。当前实现缺少完成 Session 后 Today 页面的洞察展示闭环。

Refer to: [preview.html#L708-L713](file:///home/deploy/edu-companion/vision/preview.html#L708-L713)

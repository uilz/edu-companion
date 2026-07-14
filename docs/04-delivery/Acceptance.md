# Template: Feature Acceptance

> **功能验收标准模板。**
>
> 它不是"代码能跑"，而是"产品体验完成"。
>
> 以后 Agent 开始任何 Feature 开发前，先看 Acceptance。不是先看 PRD。

---

## Feature：XXX

### Definition of Done

**产品层面**

- [ ] 用户能完成完整的体验流程（遵循 Product Blueprint 中的 Happy Path）
- [ ] AI 行为符合 AI Constitution（用户主权、先理解再建议、鼓励不施压）
- [ ] 用户感受到的是体验，不是系统（没有暴露后台术语）
- [ ] 体验一致：与其他页面的交互模式、AI 语调、信息结构一致

**能力层面**

- [ ] 该 Feature 的所有 Capability 已完成
- [ ] Capability Tree 中对应能力的成熟度已更新

**验收场景**

```
<!-- 描述一个用户从开始到结束的完整场景 -->
用户：XXX
操作：XXX
期望结果：XXX
```

**边界情况**

- [ ] 用户中断后返回
- [ ] 用户连续使用
- [ ] 用户长时间未使用后回来
- [ ] 用户数据为空

**不可验收的情况（违反即不通过）**

- ❌ 用户看到技术术语（Knowledge Graph、Learner Model 等）
- ❌ AI 命令用户（"今天你必须完成"）
- ❌ AI 假装理解用户（在没有足够上下文时做武断推荐）
- ❌ 页面上出现系统内部概念（Event Bus、Aggregate 等）

---

### 示例：Profile — "苹果果眼中的你"

| 字段 | 内容 |
|------|------|
| Feature | Profile — 苹果果眼中的你 |
| 产品层面 | ✅ 苹果果用一段叙事描述用户，不是数据库字段，不是 Persona |
| 能力层面 | ✅ Profile/苹果果眼中的你 成熟度更新 |
| 场景 | 用户使用一个月后打开 Profile，看到 AI 对自己的描述 |
| 边界 | 数据为空时显示"苹果果还在了解你" |
| 不通过 | ❌ 显示"Learner Model: confidence=0.85" |

### 示例：Growth — 成长事件

| 字段 | 内容 |
|------|------|
| Feature | Growth — 成长叙事 |
| 产品层面 | ✅ 用户看完以后，知道自己发生了什么变化，不是"Knowledge +5" |
| 能力层面 | ✅ Growth/成长叙事 成熟度更新 |
| 场景 | 完成 Session 后查看 Growth，看到"你今天学会了矩阵乘法" |
| 不通过 | ❌ 显示"XP +200"、"Knowledge +5"、"等级提升" |

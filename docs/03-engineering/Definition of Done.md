# Template: Definition of Done

> **统一完成定义。** 任何 PR 必须通过以下全部检查才能 Merge。
>
> 它不是"代码能跑"，而是"产品完成"。

---

## 产品检查

- [ ] **Product Bible 一致** — 实现是否符合 Product Bible 定义的产品体验？
- [ ] **不新增产品概念** — 没有引入 Product Vocabulary 之外的新概念？
- [ ] **不破坏主流程** — Today → Session → Growth → Profile 闭环完整？
- [ ] **Acceptance 通过** — 对应功能的验收标准全部满足？

## 领域检查

- [ ] **Domain 正确** — 聚合根、实体、值对象符合 Strategic DDD？
- [ ] **Event 正确** — 领域事件完整，事件名符合规范？
- [ ] **Aggregate 边界正确** — 没有跨 Aggregate 的直接数据访问？

## 工程检查

- [ ] **API 签名一致** — 没有破坏现有 API 兼容性？
- [ ] **Tests 通过** — 单元测试 + 集成测试全部通过？
- [ ] **Logging** — 关键路径有日志？
- [ ] **Error Handling** — 所有错误路径有处理？

## UI 检查

- [ ] **Loading 状态** — 数据加载中有展示？
- [ ] **Empty 状态** — 数据为空时有引导？
- [ ] **Error 状态** — 出错时有提示和恢复路径？
- [ ] **Mobile 适配** — 在小屏幕下可用？

## 体验检查

- [ ] **Demo 能讲** — 能向别人演示这个功能并讲清楚价值？
- [ ] **用户能理解** — 用户不需要技术背景就能理解这是什么？
- [ ] **AI 有温度** — AI 的行为符合 AI Constitution（不命令、不施压、不假装理解）？

## 文档检查

- [ ] **ADR** — 如果有架构变更，已记录 ADR？
- [ ] **Changelog** — 更新了 CHANGELOG.md？
- [ ] **Capability 更新** — Capability Roadmap 中对应能力的成熟度已更新？

---

> **任何一项不通过，PR 打回。**

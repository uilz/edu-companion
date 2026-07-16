# Founder Workflow

> 你（橙子）只需要发一句话：`LOOP`
> 其余一切由 Agent 按 Vision-Driven 流程自动推进。

---

## 一句话启动

```
LOOP
```

Agent 会读取 `/prompts/LOOP.md`，自动进入：

```
Vision Guardian → 选 Gap → Architecture Planner → 等你批准 → Implementation Lead → Release Reviewer → 更新 GAP.md → 回到起点
```

---

## 你的参与点

| 环节 | 你要做什么 |
|------|-----------|
| **启动** | 说 `LOOP` |
| **选 Gap 后** | 听 Agent 汇报 Architecture Plan，说 `批准` 或 `换另一个 Gap` |
| **实现后** | 体验 Reality，确认是否更接近 Vision |
| **争议时** | 你说了算 |

---

## 你不需要做的事

- 写 Prompt
- 写 Story
- Review 代码
- 管 Release
- 维护 Dashboard
- 追进度

Agent 会自动读取 `/prompts/` 下的四个角色 Prompt，并更新 `/vision/GAP.md`。

---

## 如果 Agent 跑歪了

直接说：

> "你重新读 /vision/preview.html，现在偏离 Vision 了。"

或：

> "STOP，这个方向不对。"

---

## 关键文件

| 文件 | 作用 |
|------|------|
| `/vision/preview.html` | 最终产品原型，唯一真相源 |
| `/vision/VISION.md` | 产品理念 |
| `/vision/GAP.md` | 当前 Reality 与 Vision 的差距 |
| `/vision/ROADMAP.md` | 按 Gap 排序的长期计划 |
| `/prompts/LOOP.md` | 你给 Agent 的唯一指令 |
| `/prompts/01-vision-guardian.md` | 角色 1 |
| `/prompts/02-architecture-planner.md` | 角色 2 |
| `/prompts/03-implementation-lead.md` | 角色 3 |
| `/prompts/04-release-reviewer.md` | 角色 4 |

---

> **核心原则：Vision 永远不变，Reality 持续靠近。**

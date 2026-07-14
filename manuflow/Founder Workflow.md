# Founder Workflow

> 你只需要关心这三件事。
> 其他所有事情由我和 CPO 自动处理。

---

## 三方角色

| 角色 | 是谁 | 负责什么 |
|------|------|----------|
| **Founder** | **你（橙子）** | 选方向、验收成果、做最终决定 |
| **Agent（我）** | Trae IDE Agent | 写 Story、写 Spec、编码、测试 |
| **CPO** | GPT | Review Story、Review Interaction |

---

## 工作流全景（你的视角）

你只出现在以下 **4 个环节**：

```
[你] 选下一条 Experience
     ↓
[我] 写 Story Plan
     ↓
[CPO] Review Story ──→ 不通过 → [我] 修改 → 再 Review
     ↓ 通过
[我] 写 Interaction Spec
     ↓
[CPO] Review Interaction ──→ 不通过 → [我] 修改 → 再 Review
     ↓ 通过
[我] 编码 + 测试
     ↓
[你] 产品验收 ←── 你现在在这里
     ↓ 不通过 → [我] 修改 → 再验收
     ↓ 通过
[我] Merge + 更新 Dashboard
     ↓
回到顶部，等你的下一个方向
```

**你的参与点只有 4 个：**
1. **选方向** — 告诉我下一条想做的 Experience
2. **回答我的问题** — 当我拿不准时，我会用 `AskUserQuestion` 问你
3. **产品验收** — 编码完成后，你体验一下，说 OK 我就 Merge
4. **最终决策** — 任何争议，你说"不"就是不

---

## 你不需要做的事

| ❌ 不需要 | ✅ 交给谁 |
|-----------|----------|
| 写 Story 文档 | 我 |
| 写 Interaction Spec | 我 |
| Review Story 细节 | CPO |
| Review Interaction 细节 | CPO |
| 管 Sprint / 管进度 | 我 |
| 管 Release 计划 | 我 |
| 维护 Dashboard | 我 |
| 决定技术方案 | 我（我会问你确认） |
| 追着问进度 | 我会主动汇报 |

---

## 什么时候你会收到我的消息

| 场景 | 你会看到什么 | 你需要做什么 |
|------|-------------|-------------|
| 开始新 Story | 我发 Story Plan | 等待 CPO Review 即可 |
| 我有疑问 | `AskUserQuestion` 弹窗 | 选一个选项或回答 |
| CPO Review 不通过 | 我汇报修改方案 | 通常不需要你介入 |
| 编码完成 | 我通知你验收 | 体验一下，告诉我 OK 或哪里不对 |
| 你主动给我方向 | 你直接告诉我 | 告诉我就好 |

---

## 快速参考：如何启动一次开发

1. 告诉我：**接下来做 X**
2. 我会出 Story Plan → 发给 CPO Review
3. CPO 通过 → 我编码 → 通知你验收
4. 你验收通过 → 我 Merge

全程你只说两句话：
- 「接下来做 X」
- 「OK，验收通过」或「这里不对，改一下」

---

## 当前状态速查

打开 [Project Dashboard](Project%20Dashboard.md) 就能看到当前进度。

---

> **一句话概括：** 你选方向、验成果，中间的一切我来跑。

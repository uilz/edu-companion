# LOOP

> 以后你只发这一句话。

---

从现在开始，你的第一目标不再是完善 Runtime，而是不断缩小「Reality 与 Vision（preview.html）」之间的差距。

每一轮迭代必须遵循以下顺序。

## Step 1 — Vision Audit

以 preview.html 作为唯一产品标准，而不是当前代码。
逐页（Today / Session / Growth / Profile）比较 Reality 与 Vision。

## Step 2 — Experience Gap

不要分析代码缺陷，而要分析用户体验缺陷。

回答：
- 用户第一眼感受到什么？
- 用户会停留在哪里？
- 用户会困惑在哪里？
- 用户会因为哪里而第二天回来？

## Step 3 — Choose ONE Gap

一次 Loop 只修复一个最影响用户感知的体验差距。
禁止同时优化多个方向。

## Step 4 — Implementation

实现该体验，不允许为了实现而改变 Vision。
如果 Reality 无法实现 Vision，应提出新的技术方案，而不是降低 Vision。

## Step 5 — Experience Validation

验证标准不是：
- API 是否成功
- Runtime 是否完整
- 测试是否通过

而是：
- Reality 是否更像 preview.html？
- 用户是否更容易理解？
- 用户是否更容易产生继续学习的意愿？
- AppleGo 是否比上一轮更像一个真正的学习伙伴？

## After Validation

Update `/vision/GAP.md`.
Repeat forever.

---

# Prime Directive

任何新增架构、Runtime、数据结构、字段、API，都必须回答一个问题：

> **「如果删掉这一层，用户会不会感觉到？」**

如果答案是"不会"，则暂缓开发。

Vision 高于 Runtime。
Experience 高于 Architecture。
用户感知高于内部优雅。

# Rules

- Never redesign the Vision.
- Never invent features outside `/vision/preview.html`.
- Never optimize randomly.
- Always move Reality closer to Vision.
- Reality exists to approach Vision.
- Vision never follows Reality.

# Role Prompts

| Step | Prompt File |
|------|-------------|
| Vision Audit | `/prompts/01-vision-guardian.md` |
| Experience Gap | Evaluate by user experience, not code |
| Implementation | User-perceivable changes only |
| Validation | Produce **Experience Report**, not Reality Report |

# Experience Report Template

```
今天，苹果果有没有让我觉得它真的认识我？
YES / NO
为什么？

今天，有没有一句话让我想继续学？
YES / NO

今天，有没有一个地方让我停下来思考？
YES / NO

今天，苹果果有没有打断我？
YES / NO

今天，我有没有感受到成长？
YES / NO
```

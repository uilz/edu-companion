# Session Interaction Spec

> **苹果果 Session 的完整交互规范。Agent 编码的唯一依据。**
>
> 行为驱动，不是页面驱动。一个页面并不等于一个交互。相同的 UI 可能服务不同的用户意图。
>
> **设计来源**：[Learning Session Design](../Learning%20Session%20Design.md) | **约束来源**：[Learning Principles](../../00-foundation/Learning%20Principles.md) + [Interaction Laws](Interaction%20Laws.md) | **文案来源**：[AI Companion Spec](../../03-engineering/specifications/AI%20Companion.md) + [Copywriting Guide](../../03-engineering/Copywriting%20Guide.md)

---

## Part A：User Intent（用户意图）

用户打开 Today，可能处于完全不同的心理状态。苹果果需要先识别意图，再决定交互。

### Intent 1：我要继续昨天

用户知道昨天做了什么，今天想接着做。

```
打开 Today
    ↓
苹果果：昨天我们停在矩阵乘法。今天继续吗？
    ↓
［继续昨天］→ 进入 Session（恢复之前进度）
```

### Intent 2：今天换个方向

用户昨天学的东西今天不想继续了。

```
打开 Today
    ↓
苹果果：昨天我们停在矩阵乘法。
    ↓
［今天换个主题］ → 输入框 → 输入新主题 → 进入 Session
```

### Intent 3：今天不知道学什么

用户打开苹果果但没有明确目标。

```
打开 Today
    ↓
苹果果：如果没有想法，可以从昨天留下的问题开始，或者看看你最近感兴趣的方向。
    ↓
［从昨天继续］ / ［看看最近］
```

### Intent 4：我只是来看看

用户打开 Today 想查看状态，不打算学习。

```
打开 Today
    ↓
Today 展示昨天的总结 + 简单的状态描述。
    ↓
不做任何引导学习的行为。
```

### Intent 5：我是新用户

第一次来，没有历史记录。

```
打开 Today
    ↓
Today 显示欢迎页。
    ↓
苹果果：你想从什么开始？
    ↓
输入主题（可选）→ ［开始学习］
```

---

## Part B：Interaction（交互规范）

每个交互使用 **Observation → Reasoning → Response** 结构。Agent 需理解：苹果果说的话不是固定文案，而是从观察推导出来的。

---

### Intent 1：继续昨天

#### Observation（观察到）

```
昨天 Session 停在矩阵乘法。
Reflection 内容：理解了矩阵乘法的定义（行×列），但第二道练习题没做对。
已完成 Practice 的 3/5 题。
```

#### Reasoning（因此）

```
用户已经理解核心概念，今天最自然的进入方式是继续昨天的进度。
不需要从头开始，不需要重新介绍。
需要给用户选择空间（Learning Principles §1：学习属于用户）。
```

#### Response（所以说）

```
"昨天我们停在矩阵乘法。今天继续吗？"
```

| 元素 | 内容 |
|------|------|
| 主要行动 | ［继续昨天］→ stage 切换到 learn，从上次断点继续 |
| 次要行动 | ［今天换个主题］→ 见 Intent 2 |
| 禁止出现 | 第三个按钮、"建议"列表、昨天时长、正确率 |

#### 交互细节

| 状态 | UI |
|------|-----|
| idle | ［继续昨天］可点击 |
| loading | 按钮 disabled + "正在准备今天……" |
| success | 跳转 Session learn 阶段 |
| error | 按钮恢复 + "今天没能顺利开始，我们再试一次。" |

---

### Intent 2：今天换个主题

#### Observation（观察到）

```
用户选择了"换个主题"。
```

#### Reasoning（因此）

```
用户对自己的学习方向有明确想法。苹果果直接询问，不推荐、不猜测。
设新主题为 Mission（属性化——不提"请输入 Mission"，只问"今天想学什么？"）。
```

#### Response（所以说）

```
"今天想学什么？"
```

| 元素 | 内容 |
|------|------|
| 输入框 | placeholder: "输入你想学的……" |
| 主要行动 | ［开始学习］→ 以输入内容为 Mission → 进入 learn 阶段 |
| 次要行动 | 不输入直接开始（自由模式） |
| 禁止出现 | Mission 表单、目标持续时间、预期完成日期 |

#### Mission 是属性，不是步骤

用户输入"矩阵乘法" → Session 的 `mission` 字段自动设为"理解矩阵乘法"。

用户在所有阶段都可以修改 Mission——在 Learn 中说"不，我想学梯度下降"即可切换方向。不需要回到 Intro 重新设置。

---

### Intent 3：今天不知道学什么

#### Observation（观察到）

```
昨天有未完成的 Session / 有历史学习主题 / 有 Growth 数据。
```

#### Reasoning（因此）

```
用户需要温和引导但不需要被教育。给 1-2 个自然选项。
不要用"推荐系统"做 Heavy Recommendation。
选项来自已有数据（昨天 + 历史），不是随机推荐。
```

#### Response（所以说）

```
"如果没有想法，可以从昨天留下的问题开始，或者看看你最近感兴趣的方向。"
```

| 元素 | 内容 |
|------|------|
| 选项 1 | ［从昨天继续］ |
| 选项 2 | ［看看最近］→ 展示最近 3 个学习主题 → 用户选一个进入 |
| 禁止出现 | "根据你的学习画像，我们推荐……"、算法标签、置信度分数 |

---

### Intent 4：我只是来看看

#### Observation（观察到）

```
用户打开了 Today。浏览了一段时间但没有点击任何 CTA。
```

#### Reasoning（因此）

```
用户此刻的意图是观察，不是行动。苹果果不应该催促。
给一个温和的入口但不引导。
```

#### Response（所以说）

```
Today 展示昨天的总结 + "昨天我们学了矩阵乘法。"
只有 CTAs 但无引导性文字层。
```

#### 交互决策

| 做什么 | 不做什么 |
|--------|---------|
| Today 底部保留 ［开始今天］ | 不弹出"要不要继续学习？" |
| 顶部显示最近的 Summary | 不闪动按钮 |
| — | 不推送通知 |

---

### Intent 5：新用户

#### Observation（观察到）

```
用户首次登录。无任何历史数据。
```

#### Reasoning（因此）

```
不知道用户想学什么。最简单的方式：直接问。
不给推荐列表——还没了解用户（Learning Principles §1）。
不强迫设定 Mission（Learning Principles §1）。
```

#### Response（所以说）

```
"你想从什么开始？"
```

| 元素 | 内容 |
|------|------|
| 输入框 | placeholder: "输入你想学的……" |
| 主要行动 | ［开始学习］（有输入→设为 Mission；无输入→自由模式） |
| 禁止出现 | 3 个推荐主题、"新手引导 1/3"、"开始前请设定目标" |

---

## Part C：State Machine

Agent 编码必须遵循的状态机。已定义在 [Session State Machine](../../02-domain/Session%20State%20Machine.md)，本 Spec 只补充交互层面的约束。

### 状态 ≠ 页面

一个状态不等于一个页面。例如 Intro 和 Learn 可以在同一个对话界面中完成——用户感知不到"阶段切换"，苹果果的对话自然推进。

### 不可跳过的阶段

| 阶段 | 可否跳过 | 原因 |
|------|:--:|------|
| Intro | 否 | 苹果果必须能建立学习意图 |
| Learn | 否 | 核心学习阶段 |
| Practice | 否 | 输出型学习 |
| Reflection | 否 | Learning Principles §4 |

### 阶段转移检测

苹果果通过对话内容判断是否进入下一阶段，而不是等用户点击"下一步"。

| 用户说 | 苹果果判断 |
|--------|----------|
| "我明白了" / "继续" | 可能可以进入 Practice |
| "再练一道" | 留在 Practice |
| "今天就到这里吧" | 引导进入 Reflection |

---

> **版本：v2.0 | 重构：行为驱动（User Intent → Interaction → State），引入 Observation→Reasoning→Response 模式**
>
> **关联文档**：
> - [Learning Principles](../../00-foundation/Learning%20Principles.md)
> - [Interaction Laws](Interaction%20Laws.md)
> - [AI Companion Spec](../../03-engineering/specifications/AI%20Companion.md)
> - [Copywriting Guide](../../03-engineering/Copywriting%20Guide.md)
> - [Session State Machine](../../02-domain/Session%20State%20Machine.md)

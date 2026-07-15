# AppleGo V1 Master Backlog

> **唯一开发清单。Agent 只能从这里取任务。**
>
> 开发单位不是页面，不是 API，是**用户体验**。
>
> 结构：Experience（体验）→ Capability（能力）→ Epic → Story
>
> 状态标注：✅ 已完成 | 🔨 进行中 | ⏳ 待开始

---

## 总览

```
EXP-01 第一次学习           ■■■■■■■■■■ 100% ← Sprint 1 全链路已跑通
EXP-02 第二次回来继续         ■■■■■■■■□□ 80%  ← S2.1 ~ S2.4 已跑通
EXP-03 回来时苹果果还记得我     ■■■■■■□□□□ 67%  ← S3.1 ~ S3.2 Core 已跑通
EXP-04 苹果果真的记得我        ■■■■□□□□□□ 40%
EXP-05 完成长期目标           □□□□□□□□□□ 0%
EXP-06 导入内容              □□□□□□□□□□ 0%
EXP-07 Demo 演示路径         ■■■□□□□□□□ 30%
```

---

## EXP-01：第一次学习（First Learning Journey）⭐⭐⭐⭐⭐

**验收：一个新用户，15 分钟内完成第一次学习。不用任何设置。第二天回来，苹果果主动从昨天继续。**

> 涉及能力：Session Lifecycle / Memory / Growth / Profile / Recommendation

---

### Capability 1-A：Session Lifecycle（学习会话闭环）■■■■■■■■■■ 100%

#### Epic 1.1：Today → Session 启动流 ✅

| Story | 描述 | 后端状态 | 前端状态 |
|-------|------|----------|----------|
| **S1.1** 从推荐创建 Session | Today 点击"开始今天"→ `POST /api/session` → `/session/[id]` | ✅ | ✅ |
| **S1.2** 从 Today 继续上次 Session | 显示未完成 Session → 点击"继续" | ✅ | ✅ |
| **S1.3** Today 状态展示 | 无任务 → AI 推荐。有进行中 → 继续选项 | - | ✅ |

#### Epic 1.2：Session 学习四阶段 ✅

| Story | 描述 | 后端状态 | 前端状态 |
|-------|------|----------|----------|
| **S1.4** Session 基本布局 | 左侧对话区，右侧进度条，stage 状态栏 | ✅ | ✅ |
| **S1.5** Intro → 设定 Mission | Arrival 已简化为无输入；Mission 由后端基于 Learner Model 自动生成，进入 learn 后在 MissionBar 展示 | ✅ | ✅ |
| **S1.6** Learn → 对话学习 | 复用现有 conversation 组件 + SSE | ✅ | ✅ |
| **S1.7** Practice → 练习验证 | 阶段切换 → `PATCH /api/session/{id}/stage` | ✅ | ✅ |
| **S1.8** Reflection → 反思总结 | 用户输入反思 → `POST /api/session/{id}/complete` | ✅ | ✅ |

#### Epic 1.3：Session 完成流 ✅

| Story | 描述 | 后端状态 | 前端状态 |
|-------|------|----------|----------|
| **S1.9** 完成后导航 | 完成 → Today，显示"今天完成了 [标题]" | ✅ | ✅ |
| **S1.10** 取消流程 | 取消 → Today | ✅ | ✅ |

---

### Capability 1-B：Growth 第一条记录 ■■■■■■■■■■ 100%

#### Epic 1.4：Session → Growth 事件链路 ✅

| Story | 描述 | 后端状态 | 前端状态 |
|-------|------|----------|----------|
| **S1.11** Session 完成后自动生成 GrowthRecord | GrowthEngine 监听 `LearningSessionCompleted` | ✅ | - |
| **S1.12** Reflection 补充到 GrowthRecord | GrowthEngine 监听 `ReflectionGenerated` | ✅ | - |
| **S1.13** Growth 页面展示第一条记录 | `GET /api/growth/records` → 叙事化展示 | ✅ | ✅ |
| **S1.14** Growth 记录不用数字 | 禁止 XP/积分/等级/百分比 | - | ✅ |

---

### Capability 1-C：Profile 初始画像 ■■■■■■■■■■ 100%

#### Epic 1.5：首次 Profile ✅

| Story | 描述 | 后端状态 | 前端状态 |
|-------|------|----------|----------|
| **S1.15** 数据为空时的引导 | "完成一次学习后这里会更新" | - | ✅ |
| **S1.16** 第一次学习后 Profile 更新 | 学习偏好 + 学习统计首次展示 | ✅ | ✅ |

---

## EXP-02：第二次回来继续学习 ⭐⭐⭐⭐⭐

**验收：用户第二天打开苹果果，不用回忆昨天学到哪。Today 直接说：你昨天在做矩阵乘法，今天从这里继续。**

> 涉及能力：Memory / Session Resume / Recommendation

---

### Capability 2-A：跨 Session 记忆 ■■■■■■■■ 80%

| Story | 描述 | 后端状态 | 前端状态 |
|-------|------|----------|----------|
| **S2.1** Today 显示"继续昨天" | 基于活跃 Session + Growth 摘要，Today 优先展示昨日进度 | ✅ | ✅ |
| **S2.2** Session 创建时关联 Learner Model | 影响 Mission 建议 | ✅ | ✅ |
| **S2.3** 今天推荐不随机 | Secretary 引擎根据历史推荐 | ✅ | ✅ |
| **S2.4** 学习路径连续性 | 从「继续昨天」创建的 Session 自动承接昨日主题/goal，Mission 围绕同一主题生成 | ✅ | ✅ |

---

## EXP-03：回来时，苹果果还记得我 ⭐⭐⭐⭐

**验收：用户回来时，苹果果还记得他。不是"7天没学习"的内疚感，而是"我一直在这里"的安定感。**

> 涉及能力：Memory / AI Companion

---

### Capability 3-A：长时间间隔恢复 ■■■□ 67%

| Story | 描述 | 后端 | 前端 |
|-------|------|------|------|
| **S3.1** 欢迎回来 | "欢迎回来。上次我们聊到了……"（不计数、不批评） | ✅ | ✅ |
| **S3.2** 从这里继续 | Mission 引用上次 key_takeaways / reflection，体现成长连续 | ✅ | ✅ |
| **S3.3** Growth 时间线间隔展示 | ~~中间缺失的时间段友好展示~~ → 移入 Enhancement Backlog | — | — |

> EXP-03 Core 已完成。S3.3 由 CPO 决策降级为 Enhancement，不在 EXP-03 范围内。

---

## EXP-04："苹果果真的记得我" ⭐⭐⭐⭐⭐

**验收：用户打开 Profile 时，看到的不是统计，而是一段让他觉得被理解的话。**

> 涉及能力：Profile（AI 叙事化）/ Growth 长期积累 / Persona

---

### Capability 4-A：AI 叙事化 Profile ■■■■ 40%

| Story | 描述 | 后端状态 | 前端状态 |
|-------|------|----------|----------|
| **S4.1** Profile 加载画像数据 | `GET /api/profile` | ✅ | ⏳ |
| **S4.2** "苹果果眼中的你" | 基于 GrowthRecord 生成自然 AI 叙事 | ✅ | ⏳ |
| **S4.3** 学习偏好展示 | Persona 偏好 → 可视化 | ✅ | ⏳ |
| **S4.4** 学习统计（叙事化） | 连续学习天数 / 本周时长 / 不显示原始数字 | ✅ | ⏳ |

### Capability 4-B：Growth 长期叙事 ■■■■ 40%

| Story | 描述 | 后端状态 | 前端状态 |
|-------|------|----------|----------|
| **S4.5** Growth 时间轴 | 按时间展示记录卡片（日期 + 标题 + 一句话总结） | ✅ | ⏳ |
| **S4.6** 禁止暴露后台术语 | Learner Model / Knowledge Graph / BKT 不进 UI | - | ⏳ |

---

## EXP-05：完成一个长期目标 ⭐⭐⭐

⏳ 未拆解。当 EXP-01 ~ 04 完成后启动。

---

## EXP-06：从任意地方导入内容 ⭐⭐⭐

⏳ 未拆解。后端已有多媒体 import API。

---

## EXP-07：Demo 演示路径 ⭐⭐⭐⭐⭐

**验收：5 分钟演示，不中断，不解释技术。观众看完说：我想用。**

> EXP-01 + EXP-02 + Profile 叙事化 + Growth 叙事化 全部完成后启动。

| Story | 描述 | 状态 |
|-------|------|------|
| **S7.1** Demo 预填数据脚本 | 预置学习资料 + 历史学习记录 + Growth + Profile | ⏳ |
| **S7.2** 5 分钟演示链路 | Today → Session → Growth → Profile 无缝衔接 | ⏳ |
| **S7.3** Demo 中不暴露任何后台术语 | - | ⏳ |

---

## Agent 工作流程

```
1. 从 Backlog 中取当前 Experience 的最高优先级 Story
2. 使用 Development Package 模板创建开发包
3. 完成后通过 DoD + Story Acceptance 全部检查
4. 提交 PR → Review → Merge
5. 更新 Experience Backlog 进度
```

### 当前优先级

```
🟢 EXP-01 — 第一次学习：Sprint 1 全链路已闭合（S1.1 ~ S1.16）

🟢 EXP-02 — 第二次回来继续学习：S2.1 ~ S2.4 已闭合
    ▸ 待确认：是否进入 EXP-03 / 继续补 EXP-02 剩余 20%（如 Demo 数据、文案打磨）
```

### Agent 不能做的事

- ❌ 自选 Experience 之外的开发目标
- ❌ 优化"看起来重要"的后台模块
- ❌ 新建 API 除非当前 Story 明确要求
- ❌ 重构旧页面除非阻塞了当前 Story

---

> **维护者：Founder。更新条件：每完成一个 Story 后由 Agent 更新状态。每完成一条 Experience 后由 Founder 验收。**
>
> **相关文档：[V1 Experience Backlog](V1%20Experience%20Backlog.md)（体验定义与验收）**

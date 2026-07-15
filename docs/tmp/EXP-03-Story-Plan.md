# EXP-03 Story Plan：回来时，苹果果还记得我

> **状态：CPO Review 通过，待 Interaction Spec Review**
>
> **关联文档**：
> - [Trust Journey](../02-domain/Trust%20Journey.md) 节点 4（第一周，模式建立）
> - [Learning Principles](../00-foundation/Learning%20Principles.md) §5 §10
> - [AI Constitution](../00-foundation/AI%20Constitution.md) 第三条
> - [Interaction Laws](../00-foundation/Interaction%20Laws.md) §1 §2 §6
> - [Experience Backlog](../01-product/Experience%20Backlog.md) EXP-03

---

## 一、Experience 定义

**名称**：EXP-03：回来时，苹果果还记得我

**核心假设**：当用户离开一段时间后回来，苹果果能否降低重新开始的心理成本？

**验收标准**（来自 Experience Backlog）：
> 用户回来时，苹果果还记得他。不是"7天没学习"的内疚感，而是"我一直在这里"的安定感。

**Trust Journey 映射**：节点 4（第一周，模式建立）

**与 EXP-02 的边界**：
- EXP-02：用户第二天回来 → "继续昨天"（时间间隔 = 1 天）
- EXP-03：用户离开多天后回来 → "欢迎回来"（时间间隔 ≥ 3 天）

**核心产品方向**（CPO Review 确认）：
1. 不是恢复任务，是恢复关系
2. 不恢复"上次任务做到哪里"，恢复"上次那个正在成长的你"
3. 从"知识连续"走向"成长方式连续"
4. AI 用行为表达"我记得你"，而非用称呼表达
5. 文案方向：从"你学到了"转向"我们聊到了"

---

## 二、Story 拆解

### S3.1：欢迎回来

**User Story**：
作为离开了一段时间的学习者，当我重新打开苹果果时，我希望看到"欢迎回来"和上次我们一起探索的内容，这样我能感受到苹果果记得这段关系，而不是在催促我继续任务。

**Why**：
Learning Principle 10（暂停不是放弃）：回来的第一句话是"好久不见" + 上次学到哪，不提"你停了多久"。
Trust Journey 节点 4：用户中断三天后回来，苹果果不提中断——它记得学习内容，但不评价行为。
AI Constitution 第三条：不制造内疚感，营造"随时可以继续"的安全感。

**当前问题**：
`/api/session/continue` 在 `days_ago >= 3` 时仍返回 `type: "yesterday"`，前端显示"继续昨天"。时间间隔长短不影响 UX，缺少"欢迎回来"的关系恢复体验。

**Flow**：
```
用户打开 Today
  ↓
GET /api/session/continue
  ↓
days_ago >= 3 → type: "welcome_back"
  ↓
Today 展示"欢迎回来"卡片：
  - 苹果果说："欢迎回来。上次我们聊到了 {title}。"
  - 引用上次学习的标题（不提离开天数）
  - CTA：[从这里继续]（primary）+ [换个方向]（secondary, 文字链接）
  ↓
用户点击 [从这里继续]
  ↓
创建新 Session，继承上次主题与上下文
```

**Acceptance Criteria**：
1. `days_ago >= 3` 时，`/api/session/continue` 返回 `type: "welcome_back"`
2. Today 页面展示"欢迎回来"卡片，不出现"X天前"计数
3. 卡片引用上次学习的标题和关键收获，不提离开时长
4. 苹果果说一句话："欢迎回来。上次我们聊到了……"（Interaction Law 1 & 2）
5. 主 CTA 是"从这里继续"，次要是"换个方向"（文字链接样式，视觉弱于 primary）
6. 如果用户无历史学习记录，不展示此卡片
7. 如果用户只有一次 Session 且无 key_takeaways / reflection，不强行展示"记得你"——回退到新用户 EmptyState

**Out of Scope**：
- 不做推送通知
- 不做回归用户检测逻辑（已有后台模块）
- 不在 Session 内重复"欢迎回来"
- 不做 30 天+ 分层体验（未来能力）

**Trust 行为检查**：
- 行为：引用上次学习内容，不提离开时长
- 删掉文案，信任是否成立：是。用户看到上次学习标题就知道苹果果记得他。
- 文案职责：用"我们聊到了"强调关系，不用"你学到了"强调成绩

---

### S3.2：从这里继续

**User Story**：
作为选择"从这里继续"的学习者，当我进入新 Session 时，我希望 Mission 能体现苹果果对我学习方式的理解，这样我不用自己回忆"上次学到哪了"，也能感到苹果果真的在参与我的成长。

**Why**：
Product Principles §5（Never Start Over）：苹果果永远记得昨天。
Trust Journey 节点 4：推荐内容基于之前练习中的表现，Session 中引用过去的困难。
CPO Review：从"知识连续"转向"成长方式连续"——记住用户如何成长，不只是学了什么。

**当前问题**：
S2.4 已实现"继续昨天"创建 Session 时继承主题，但 Mission 生成仅基于 topic 字符串匹配，不引用上次的 key_takeaways 和 reflection。长间隔后用户需要更多上下文才能恢复学习状态。且当前 Mission 侧重知识内容，不体现对用户学习方式的理解。

**Flow**：
```
用户点击 [从这里继续]
  ↓
POST /api/session（携带 source: "welcome_back"）
  ↓
后端读取上次 GrowthRecord：
  - session_title
  - key_takeaways
  - reflection_snippet
  ↓
_build_mission_from_learner_model 增强：
  - Mission 标题：引用上次主题
  - 第一步：引用上次的 key_takeaway，用"我们发现/我们聊到了"而非"你学到了"
  - review 步骤：如果 reflection 中有学习方式发现，引用它
  ↓
Session Learn 阶段展示 MissionBar
  ↓
用户看到：上次我们聊到了什么 → 今天从这里继续
```

**Mission 文案方向**（CPO Review 约束）：

| ❌ 不推荐（知识复盘） | ✅ 推荐（成长方式连续） |
|----------------------|----------------------|
| "上次你的问题是递归树遍历的空间复杂度" | "上次我们发现用画图理解递归会更容易" |
| "上次你学到了矩阵乘法的定义" | "上次我们聊到了矩阵乘法，你从几何角度切入" |
| "上次你错了 3 题，今天继续练习" | "上次你尝试了用例子来理解，今天继续这个方向" |

**Acceptance Criteria**：
1. 从"welcome_back"卡片创建的 Session，Mission 第一步引用上次学习的 key_takeaway
2. Mission 文案使用"我们"而非"你"，强调伙伴关系而非考核
3. 如果上次 reflection 中有学习方式线索（如"画图""举例""类比"），Mission review 步骤引用它
4. Mission 不出现"你离开了 X 天"或任何计数语言
5. 如果上次学习无 key_takeaways，回退到当前行为（基于 topic 生成 Mission）
6. Learner Model 的 struggling_skills 仍然参与 Mission 生成（S2.2 逻辑不丢失）

**Out of Scope**：
- 不做知识图谱级断点恢复
- 不做 skill_id 级精确连续
- 不修改 Session 状态机
- 不在 Learn 阶段开头加"好久不见"（Today 已完成关系恢复）

**Trust 行为检查**：
- 行为：Mission 内容引用上次学习的具体收获和学习方式，不泛泛说"继续"
- 删掉文案，信任是否成立：部分成立。Mission 结构展示了连续性。引用 key_takeaway 是行为信号。
- 文案职责：让引用自然，不变成学习档案复盘

---

## 三、Story 依赖与顺序

```
EXP-03 Core：

S3.1 欢迎回来（后端 + 前端）
  ↓
S3.2 从这里继续（后端 Mission 增强）
```

S3.1 是入口，S3.2 依赖 S3.1 的"从这里继续"流程。

---

## 四、Enhancement Backlog（移出 EXP-03 Core）

### S3.3（Enhancement）：Growth 时间线间隔友好展示

**状态**：移入 Growth Enhancement Backlog，不在 EXP-03 范围内。

**原因**（CPO Review）：
- Growth 是回顾，不是重新建立关系
- 用户回来第一分钟不会先打开 Growth
- EXP-03 最大价值是验证长期陪伴关系，不是页面完善

**未来方向**：
- 两条记录间隔 ≥ 3 天时插入自然时间标记（"上周"/"6月中旬"）
- 不出现"无学习"/"空白"/"中断"等负面语言
- 不计数间隔天数

---

## 五、技术方案概要

### 后端变更

| 文件 | 变更 |
|------|------|
| `backend/app/api/session/session.py` | `/api/session/continue` 增加 `welcome_back` type（`days_ago >= 3`） |
| `backend/app/domain/session/service.py` | `_build_mission_from_learner_model` 增强读取上次 GrowthRecord 的 key_takeaways / reflection |

### 前端变更

| 文件 | 变更 |
|------|------|
| `frontend/src/components/today/TodayPage.tsx` | 新增 `WelcomeBackCard` 组件，处理 `type: "welcome_back"` |

### 不新增

- 不新增 API 端点（复用 `/api/session/continue`）
- 不新增数据库表
- 不新增后端模块
- 不新增页面

---

## 六、产品原则检查

| 原则 | 检查结果 |
|------|---------|
| Learning Principle 5（记忆帮助陪伴，不监督） | ✅ 记住学习内容，不提离开时长 |
| Learning Principle 7（不给压力） | ✅ 无 streak、无计数、无评价 |
| Learning Principle 10（暂停不是放弃） | ✅ 回来第一句话是"欢迎回来" + 上次内容 |
| AI Constitution 第三条（鼓励不施压） | ✅ 不制造内疚感 |
| AI Constitution 第五条（承认不确定性） | ✅ 只有一次 Session 无有效记忆时不伪造熟悉感 |
| Interaction Law 1（一个页面最多主动说一次） | ✅ Today 只展示一张卡片 |
| Interaction Law 2（不超过两句话） | ✅ "欢迎回来。上次我们聊到了……" |
| Interaction Law 4（一个主要 CTA） | ✅ [从这里继续] primary + [换个方向] secondary |
| Interaction Law 6（用户可跳过 AI 建议） | ✅ 有"换个方向"出口 |
| Product Principles §5（Never Start Over） | ✅ 从上次继续，不重新开始 |

---

## 七、CPO Review 确认项

| 问题 | CPO 回答 | 状态 |
|------|---------|------|
| "好久不见"触发阈值？ | ≥3 天，不暴露"3天"给用户 | ✅ 已采纳 |
| 时间标记格式？ | 自然语言，但 S3.3 降级为 Enhancement | ✅ 已采纳 |
| Session 内是否增加"好久不见"？ | ❌ 不增加，Today 已完成关系恢复 | ✅ 已采纳 |

---

## 八、异常流程

### 情况 1：用户离开 30 天以上回来

V1 不做分层。`days_ago >= 3` 统一返回 `welcome_back`。

未来能力：30 天+ 展示"重新认识一下最近状态"。

### 情况 2：用户只有一次 Session 且无有效记忆

如果用户只完成过一次 Session，且该 Session 无 key_takeaways 和 reflection：
- 不展示"欢迎回来"卡片
- 回退到新用户 EmptyState
- 原则：宁愿少说，也不要伪造熟悉感（AI Constitution 第五条）

---

> **版本：v2.0 | CPO Review 通过 | 下一步：Interaction Spec**

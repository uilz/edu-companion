# AppleGo Demo3.0 Product Spec

> **Phase A 输出：逐页拆解 preview.html 为产品规格。**
>
> 对应 LOOP.md Phase A 全部 15 项。每一项均可映射回 Demo 的具体 UI 或交互。
>
> 版本：v1.0 | 基准：preview.html | 冻结日期：2026-07-18

---

## 1. 信息架构总览

### 1.1 页面拓扑

```
App Root
├── BottomNav（固定底栏，4 Tab）
│   ├── Today（默认首页）
│   ├── Growth
│   ├── Profile
│   └── More（工具箱入口）
├── Session（全屏覆盖层，从 Today 进入）
├── ToolPage（全屏工具页，全屏覆盖层）
│   ├── Flashcards
│   ├── Reader
│   ├── Voice
│   ├── Canvas
│   ├── Handwrite
│   ├── Files
│   ├── Pomodoro
│   └── Preferences
├── ToolTrayMenu（浮层菜单，从 Session 内打开）
└── DemoBar（演示控制条，仅在开发/演示环境显示）
    ├── 学科切换（线代 / 递归）
    ├── 时间维度（第一周 / 一个月 / 三个月）
    └── 情景（继续昨天 / 中断回来）
```

### 1.2 导航规则

| 规则 | 说明 |
|------|------|
| 底部导航 | 4 Tab 固定显示，active 高亮，点击切换页面 |
| Session 内导航 | 顶部可返回 Today，不可切换 BottomNav |
| ToolPage 内导航 | 顶部"返回"关闭工具页，不切换页面 |
| Session + Tool 共存 | Session 内可打开 ToolPage（全屏覆盖），关闭后回到 Session |

### 1.3 页面层级

```
Layer 0: Today / Growth / Profile / More（主内容层）
Layer 1: Session Overlay（全屏覆盖主内容）
Layer 2: ToolPage（全屏覆盖 Session 或主内容）
Layer 3: ToolTrayMenu（浮层，在 Session 之上）
Layer 100: BottomNav（始终在底层之上）
```

---

## 2. Today 页面规格

### 2.1 信息架构

```
Today Page
├── [Quote] 可选一言（受偏好控制）
├── Greeting（🍎 + 时间问候）
├── Date（格式化日期）
├── Observation（苹果果基于记忆的观察文案）
├── [MemoryPulse] 学后新洞察（仅在学完 Session 返回后显示）
├── LastSessionCard（上次学习摘要）
│   ├── Label（"昨天" / "上次"）
│   ├── Title（上次学习标题）
│   └── SkillStatus（苹果果对你的理解状态）
├── TodayTools（快捷工具建议，横向滚动）
│   ├── 复习卡片（卡片数 + 待复习数）
│   ├── 继续阅读（剩余阅读时间）
│   └── 练口语（10 分钟房间）
├── CTA（主要行动按钮）
│   ├── [NewUser] "开始第一次学习"
│   ├── [Return] "从这里继续"
│   └── [Continue] "继续昨天"
└── [SwitchLink] "今天想学点别的"
```

### 2.2 页面状态

| 状态 | 触发条件 | UI 表现 |
|------|----------|---------|
| **新用户** | scene='new' 或 sessionsDone=0 | 大 Welcome Hero（苹果图标 + 欢迎文案 + 开始按钮），无 LastSessionCard |
| **继续昨天** | scene='continue' 且有学习记录 | 完整页面，LastSessionCard 显示"昨天的学习" |
| **中断回来** | scene='return' 且有过学习记录 | 完整页面，Greeting="好久不见"，LastSessionCard 显示"上次的学习" |
| **学后返回** | state.newInsight 不为 null | 在 Observation 下方显示 MemoryPulse 卡片（渐变色背景 + 蓝色左边框） |
| **Loading** | 数据加载中 | （Demo 未实现，留扩展） |
| **Empty** | 无任何数据 | 等同新用户 |
| **Error** | 数据加载失败 | （Demo 未实现，留扩展） |

### 2.3 组件树

```
TodayPage
├── QuoteBanner（条件渲染）
│   └── props: text: string
├── GreetingSection
│   └── props: greeting: string, date: string, observation: string
├── MemoryPulse（条件渲染）
│   └── props: text: string（苹果果的新洞察）
├── LastSessionCard
│   └── props: label: string, title: string, status: string
├── TodayTools（水平滚动容器）
│   └── ToolQuickButton[]（可复用组件）
│       └── props: icon: string, color: string, title: string, subtitle: string, onClick: () => void
├── CTAButton
│   └── props: label: string, onClick: () => void, variant: 'primary' | 'welcome'
└── SwitchLink
    └── props: label: string, onClick: () => void
```

### 2.4 交互事件

| 事件 | 触发元素 | 行为 |
|------|---------|------|
| 开始学习 | CTA Button | 调用 startSession('intro')，打开 Session Overlay |
| 换学科 | N/A（DemoBar 控制） | 切换 subject，重置记忆，重新渲染 |
| 切换情景 | N/A（DemoBar 控制） | 设置 scene，重新渲染 |
| 打开工具 | ToolQuickButton | 调用 openToolPage(type) |
| 今天想学点别的 | text-link | 调用 startSession('intro', true) |
| 切换偏好 | 偏好的 toggle | 更新 state.prefs，控制 Quote 显示 |

### 2.5 AI 行为

苹果果的 Observation 文案基于记忆深度动态生成：

| 记忆深度 | 文案类型 | 示例 |
|----------|---------|------|
| sessionsDone=0 | 新人引导 | "你想从什么开始？我还不太了解你，学几次就熟了。" |
| scene='return' | 中断欢迎 | "好久不见。上次我们在学[lastTopic]。我一直在这里。" |
| sessionsDone≤2 | 初期陪伴 | "昨天我们刚一起接触了[topic]。今天从这里继续吗？" |
| mastery<0.4 | 鼓励巩固 | "这是个新朋友，慢慢来。" |
| mastery<0.7 | 鼓励推进 | "昨天你在[topic]上又近了一步。今天继续巩固吗？" |
| mastery≥0.7 | 鼓励深入 | "昨天你又练了[topic]，已经很稳了。今天往深走一步？" |

### 2.6 Demo 中的变量数据

| 变量 | 来源 | 用途 |
|------|------|------|
| greeting | SCENE_GREETING 映射 | 下午好 / 好久不见 |
| dateStr | new Date() | 格式化中文日期 |
| quote | QUOTES 随机 | 每日一言 |
| observation | Narrative.todayObservation() | 动态观察文案 |
| lastTitle | 基于 subject + scene | 上次学习的标题 |
| topic.status | mem.topics[topic].status | 苹果果对你的理解状态 |

---

## 3. Session 规格

### 3.1 信息架构

Session 是一个 **全屏覆盖层**，包含 5 个顺序阶段：

```
Session Overlay
├── Topbar
│   ├── Back Button（返回 Today，退出 Session）
│   ├── Title（当前 Mission 标题）
│   ├── Tools Trigger（打开工具托盘，可显示红点提示 + 番茄钟运行指示）
│   └── Stages（5 段式进度指示器）
├── Progress Bar（线性进度条，0% → 100%）
└── Body（每个阶段不同内容）
    ├── Stage: Intro（设置/确认今天学什么）
    ├── Stage: Learn（对话学习）
    ├── Stage: Practice（练习）
    ├── Stage: Reflect（反思）
    └── Stage: Finish（结束）
```

### 3.2 阶段流转

```
Intro → Learn → Practice → Reflect → Finish
  ↑         ↑          ↑          ↑
  |--- 可中途去 Practice --| 可跳过 Reflect
  |--------- 可"今天就到这里"直接到 Finish
```

| 阶段 | 用户感知 | 持续时间 | 是否必选 |
|------|---------|---------|---------|
| Intro | "今天学什么？" | 短（确认即过） | ✅ |
| Learn | "和苹果果一起学" | 可变（3+ 轮对话） | ✅ |
| Practice | "练一练" | 可变（1+ 题） | ✅ |
| Reflect | "今天学到了什么？" | 可变（可选填写） | ⚡ 可跳过 |
| Finish | "今天就到这里" | 短 | ✅ |

### 3.3 各阶段规格

#### 3.3.1 Intro

**状态**：无 loading/empty/error 状态，立即显示。

**UI**：
```
StageCenter
├── AIQuote（苹果果的第一句话）
│   ├── 新用户: "你想从什么开始？"
│   ├── 中断回来: "好久不见。上次我们在学[lastTopic]。我一直在这里。"
│   ├── 继续昨天 sessionsDone≤2: "昨天我们刚接触了[topic]。今天从这里继续吗？"
│   └── 继续昨天 sessionsDone>2: "昨天你在[topic]上又近了一步（[status]）。今天继续吗？"
└── CTA
    ├── "继续" Button → goStage('learn')
    └── "今天想学点别的" Link → renderIntroSwitch()
```

**IntroSwitch 子状态**：
```
StageCenter
├── AIQuote: "今天想学什么？"
├── InputField: placeholder="输入你想学的……（不填也行）"
└── CTA
    ├── "开始学习" Button → goStage('learn')
    └── "还是继续昨天" Link → renderIntro()
```

#### 3.3.2 Learn

**状态**：

| 子状态 | 触发 | UI |
|--------|------|-----|
| AI 说话中 | 初始 | msg-list 中显示 AI 消息 + typing cursor 动画 |
| 等待用户回复 | AI 说完 | suggestion-row 显示推荐追问 pill |
| 用户发送消息 | 用户输入 | appendUserMsg + 苹果果回复 + typing animation |
| 工具推荐时机 | learnTurn≥2 | 苹果果主动建议："这个概念有点抽象。要不要把它在画布上摆开看？" + tool-nudge 红点 |
| 准备进入下一阶段 | 任意时刻 | suggestion-row 显示"去练习""今天就到这里" |

**组件树**：
```
LearnView
├── Conversation
│   ├── MessageList
│   │   ├── MessageAI（左对齐，🍎 头像，ai-msg 气泡）
│   │   │   └── props: text: string, typing?: boolean
│   │   └── MessageUser（右对齐，"你"头像，user-msg 气泡）
│   │       └── props: text: string
│   ├── SuggestionRow（推荐追问按钮组）
│   │   └── props: pills: string[], onSelect: (text) => void
│   └── InputBar
│       ├── InputField（placeholder="问苹果果……"）
│       └── SendButton
├── ToolNudge（红点提示，6 秒延迟后显示）
└── EmbedToolCard（条件渲染，苹果果推荐工具时）
    └── props: icon, title, description, buttonLabel, onClick
```

**AI 行为**：
- 初始发送 learnConversation 中的预置消息（打字机效果，每句 400ms 间隔）
- AI 回复基于 learnReply 映射（固定回复 + default fallback）
- 第 3 轮对话后主动递工具（toolNudge 红点）
- 支持 typing cursor 动画模拟实时输入

#### 3.3.3 Practice

**UI**：
```
PracticeView
├── PracticeQuestion（卡片式）
│   ├── Label: "练一练"
│   ├── QuestionText
│   ├── [CodeBlock]（条件渲染，等宽字体 pre）
│   └── Options（选项按钮列表）
│       └── 状态: unselected / correct / wrong / locked
├── [FeedbackArea]（作答后显示）
│   ├── FeedbackBubble（AI 反馈，带 verdict）
│   │   └── 状态: ok（绿色）/ nope（橙色）
│   ├── [EmbedToolCard]（"做成一张卡记住它"，点击创建闪卡）
│   └── SuggestionRow
│       ├── "再来一道"
│       └── "去反思"
└── [CreateCardResult]（创建后显示 ✓ 确认）
```

**状态**：

| 状态 | 触发 | UI |
|------|------|-----|
| 未作答 | 刚进入 | 所有 option 可选 |
| 已作答（正确） | 用户选对 | 正确项标绿 + okFeedback + 嵌入卡片创建 |
| 已作答（错误） | 用户选错 | 正确项标绿，错误项标红 + nopeFeedback + 嵌入卡片创建 |
| 锁定 | 已作答 | 所有 option 添加 locked class，不可再选 |

**记忆更新**：
- 答对：topic.mastery +0.08
- 答错：topic.mastery +0.02, pressure +0.05
- 状态文本更新：mastery<0.3→"新朋友", <0.6→"正在巩固", <0.85→"比较熟了", else→"很稳"

#### 3.3.4 Reflect

**UI**：
```
ReflectView
├── Prompt: "今天你学到了什么？"
├── SubPrompt: "写下你自己的理解。不写也行。"
├── Textarea（placeholder="今天我对……有了新的理解……"）
│   └── 可复用 ReflectDraftButton（"苹果果帮你整理"）
│       └── 点击后填充 draft 文本（打字机效果）
└── Actions
    ├── "跳过"（回到 Finish）
    └── "完成今天"（保存反思 → 进入 Finish）
```

**状态**：
- 空状态：textarea 为空，显示 placeholder
- 已填充 draft：打字机效果逐字填入
- 已提交：保存到 state.session.reflectionText

#### 3.3.5 Finish

**UI**：
```
FinishView
├── 🍎 大图标
├── AIQuote: "今天就到这里。我会记住今天。"
└── CTA: "返回首页" Button
```

**完成行为**：
1. 调用 updateMemoryFromSession() 更新记忆
2. 生成 newInsight（随机从 pool 选取）
3. 退出 Session 覆盖层
4. 跳转回 Today 页面
5. Today 页面显示 MemoryPulse 新洞察

### 3.4 Session 内工具交互

| 事件 | 触发 | 行为 |
|------|------|------|
| 打开工具托盘 | 点击顶部工具按钮 | 显示 ToolTrayMenu 浮层（Pomodoro、Canvas、Handwrite、Files） |
| 工具红点提示 | Learn 阶段 6 秒后 | tool-nudge 显示红点 |
| 番茄钟状态 | Pomodoro 运行中 | pomo-badge 显示小红点脉冲动画 |
| 练习→创建卡片 | 点击"＋ 创建" | 向 state.customCards 添加卡片，更新闪卡列表 |
| 阅读→划线做卡 | 点击高亮文本 | 向 state.customCards 添加卡片 |

---

## 4. Growth 页面规格

### 4.1 信息架构

```
Growth Page
├── PageTitle: "你的成长"
├── GrowthNarrative（苹果果的叙事总结）
│   └── 基于记忆深度动态生成
└── Timeline（时间线列表）
    └── TimelineItem[]
        ├── Time（相对时间：如"3 天前""昨天""刚才"）
        ├── Title（事件标题）
        └── Summary（事件描述）
```

### 4.2 页面状态

| 状态 | 触发 | UI |
|------|------|-----|
| 有历史 | sessionsDone>0 | 显示完整 Narrative + Timeline |
| 新用户 | sessionsDone=0 | Narrative="这是我们刚开始的样子" + 空 Timeline（Demo 未渲染空态，留扩展） |

### 4.3 组件树

```
GrowthPage
├── PageTitle（h1）
└── GrowthNarrative
    └── props: text: string（基于记忆的叙事）
└── Timeline
    └── TimelineItem[]
        ├── props: time: string, title: string, summary: string, isNew?: boolean
        └── 新项（time="刚才"）显示 new-item 高亮边框
```

### 4.4 AI 行为

Narrative 基于 sessionsDone 深度：

| 深度 | 文案 |
|------|------|
| sessionsDone≤2 | "这是我们刚开始的样子。每一次学习，我都会更了解你一点。" |
| sessionsDone<15 | "这一个月，你对[topic]的感觉在变。从觉得难，到慢慢上手。" |
| sessionsDone≥15 | "三个月。你对[topic]的感觉完全不一样了。这不是分数能说的，是你真真切切走过来的。" |

---

## 5. Profile 页面规格

### 5.1 信息架构

```
Profile Page
├── PageTitle: "苹果果眼中的你"
├── ProfileMirror（苹果果的叙事画像）
│   └── 基于记忆深度 + 学科动态生成
└── LearningInfo
    ├── SectionTitle: "关于你的学习"
    └── PrefGrid（键值对列表）
        ├── 学习方式（基于学科: "先实践，再看理论" / "先看例子，再看定义"）
        ├── 学习节奏（本周 X 天左右）
        ├── 最近在学（学科名称）
        └── 已经一起走过（X 次学习）
```

### 5.2 页面状态

| 状态 | 触发 | UI |
|------|------|-----|
| 刚开始 | sessionsDone≤2 | Mirror 简短短语："我们刚开始。你最近在学[topic]……" |
| 一个月 | sessionsDone<15 | Mirror 对比叙事 + 学习风格洞察 |
| 三个月 | sessionsDone≥15 | Mirror 强烈对比叙事 + 详细学习习惯洞察 |

### 5.3 组件树

```
ProfilePage
├── PageTitle
├── ProfileMirror
│   └── props: html: string（可直接包含 <span class="highlight"> 标签）
└── ProfileSection
    ├── SectionTitle
    └── PrefGrid
        └── PrefRow[]
            ├── props: label: string, value: string
            └── 左对齐 label，右对齐 value
```

### 5.4 AI 行为

Mirror 文案三段式结构：

1. **起点对比**：基于 sessionsDone 对比用户最初和现在的状态
2. **学习风格**：基于学科提取的学习偏好洞察
3. **状态提醒**：如果 pressure>0.5 提醒放松，否则鼓励深入

---

## 6. More（工具箱）规格

### 6.1 信息架构

```
More Page
├── PageTitle: "我的学习工具箱"
└── MoreGrid（2 列网格）
    ├── MoreCard: 阅读（📖）
    ├── MoreCard: 语音房间（🗣️）
    ├── MoreCard: 卡片（🧠）
    ├── MoreCard: 画布（🧩）
    ├── MoreCard: 手写（✏️）
    ├── MoreCard: 文件（📄）
    ├── MoreCard: 番茄钟（⏱️）
    └── MoreCard: 偏好（⚙️）
```

### 6.2 组件树

```
MorePage
├── PageTitle
└── MoreGrid
    └── MoreCard[]
        ├── props: icon: string, iconBg: string, title: string, desc: string, onClick: () => void
        └── 点击 → openToolPage(type)
```

### 6.3 工具页规格

所有工具页共享同一容器：

```
ToolPage（全屏覆盖层）
├── ToolTopbar
│   ├── Back Button（关闭工具页）
│   └── Title（工具名称）
└── ToolBody（每个工具不同内容）
```

#### 6.3.1 Flashcard（闪卡）

| 状态 | UI |
|------|-----|
| 有卡片可复习 | 卡片正面 → 点击翻转 → 四级评分（忘了/模糊/记得/很熟） |
| 全部复习完毕 | 完成页面：🍎 + "今天的卡片复习完了" + 返回按钮 |
| 空 | （Demo 总有一组合集，未实现空态） |

**组件**：
```
FlashcardView
├── Counter: "第 X / Y 张"
├── Flashcard（点击翻转）
│   ├── Front: label "正面" + content
│   └── Back: label "记得吗" + content
├── GradeActions（翻转后显示）
│   ├── Again（忘了）
│   ├── Hard（模糊）
│   ├── Good（记得）
│   └── Easy（很熟）
└── Hint: "点卡片翻面"
```

#### 6.3.2 Reader（阅读）

| 状态 | UI |
|------|-----|
| 有内容 | 阅读正文 + 高亮标记 + AI 笔记 |
| 划线 | 点击高亮文本 → 创建卡片 → toast 提示 |

**组件**：
```
ReaderView
├── Meta: "还剩 X 分钟的阅读量"
├── Title
├── Body（等宽字体文章）
│   └── HighlightedSpan（可点击高亮文本）
│       └── 点击 → 创建卡片
└── AINote（苹果果的阅读注解）
    ├── Head: 🍎 苹果果注意到你划了这段
    └── Text: 个性化注解
```

#### 6.3.3 Voice（语音房间）

| 状态 | UI |
|------|-----|
| 未开始 | 静态 orb + "点下面开始对话" |
| 正在说 | orb 脉冲动画 + wave 动画 + 语音转文字气泡 |
| 暂停 | orb 恢复静态 + "暂停了" |

**组件**：
```
VoiceView
├── VoiceOrb（脉冲动画）
│   └── 状态: idle / speaking
├── StatusLabel + Hint
├── VoiceWave（声波动画）
│   └── 状态: idle（静态）/ active（动画）
├── Transcript（对话记录）
│   └── VtLine[]（ai / user 标签）
├── Controls
│   ├── Toggle Button（开始/暂停/继续）
│   └── End Button
└── QuickReplies（快捷回复 pill）
```

#### 6.3.4 Canvas（概念画布）

| 状态 | UI |
|------|-----|
| 初始 | 3 个预设节点（学科相关）+ 1 个"昨天学习"链接节点 + SVG 连线 |
| 交互 | 节点可拖拽、点击"＋"新增节点 |
| 新节点 | 添加后播放 nodePop 动画 |

**组件**：
```
CanvasView
├── Hint: "拖动节点重新摆 · 点 ＋ 添加"
├── CanvasSVG（节点间连线）
├── CanvasNode[]（可拖拽）
│   └── props: icon, color, title, subtitle, linked?: boolean
├── CanvasAddButton（FAB "+"）
└── 新节点自动带有 new-node 动画
```

#### 6.3.5 Handwrite（手写）

| 状态 | UI |
|------|-----|
| 使用中 | 可书写画布 + 颜色选择 + 清除 |
| 空 | 空白画布 |

**组件**：
```
HandwriteView
├── HandwriteCanvas（原生 canvas）
├── ToolBar（底部悬浮）
│   ├── ColorPicker（3 色：黑/蓝/红）
│   └── ClearButton
```

#### 6.3.6 Files（知识文件）

文件列表，固定数据（Demo 级），每一项含图标、名称、元信息。

#### 6.3.7 Pomodoro（番茄钟）

| 状态 | UI |
|------|-----|
| 准备 | 25:00 显示 + "准备专注" |
| 专注中 | 倒计时 + 环形进度 + "专注中" + 顶部 badge 脉冲 |
| 暂停 | 暂停倒计时 + "暂停" |
| 完成 | 回到准备状态 |

**组件**：
```
PomodoroView
├── Clock
│   ├── 环形进度（SVG circle stroke-dashoffset）
│   ├── 时间（MM:SS）
│   └── Label（准备专注 / 专注中）
├── Controls（开始/暂停 + 重置）
└── TaskList
    └── TaskItem[]
        ├── checkbox（done/undone）
        ├── text
        └── tag
```

#### 6.3.8 Preferences（偏好）

| 组 | 项目 |
|----|------|
| 氛围 | 首页一言 toggle、信息源推送 toggle |
| 已订阅信息源 | 每日数学（启用）、编程灵感（未启用） |

---

## 7. BottomNav 规格

### 7.1 信息架构

```
BottomNav（固定底部，高度 68px）
├── Tab: Today（首页 icon + "Today"）
├── Tab: Growth（趋势图 icon + "Growth"）
├── Tab: Profile（人头 icon + "Profile"）
└── Tab: More（三点 icon + "更多"）
```

### 7.2 状态

| 状态 | UI |
|------|-----|
| active | accent 蓝色 + 粗体 |
| inactive | muted 灰色 |
| hover | slightly darker muted |
| Session 活跃时 | BottomNav 仍在底层可见，但被 Session Overlay 覆盖 |
| safe-area | padding-bottom 适配 notch |

---

## 8. DemoBar 规格（演示专用）

### 8.1 信息架构

```
DemoBar（固定顶部，仅在演示环境显示）
├── Toggle（展开/折叠）
├── 学科切换
│   ├── "线代"（active）
│   └── "递归"
├── 时间维度
│   ├── "第一周"（active）
│   ├── "一个月"
│   └── "三个月"
└── 情景
    ├── "继续昨天"（active）
    └── "中断回来"
```

### 8.2 交互

| 事件 | 行为 |
|------|------|
| 切换学科 | 更新 state.subject，重置记忆到当前 era，重置 customCards，重新渲染所有页面 |
| 切换时间维度 | 更新 state.era，重新加载对应深度记忆，重置 customCards，重新渲染 |
| 切换情景 | 更新 state.scene，重新渲染 Today |

### 8.3 记忆数据模型

```javascript
// 时间维度记忆模板
ERA_MEMORY = {
  week1:  { sessionsDone: 2,  streakWeeks: 1, topics: {...}, insights: [], growthHistory: [...] },
  month1: { sessionsDone: 9,  streakWeeks: 4, topics: {...}, insights: [...], growthHistory: [...] },
  month3: { sessionsDone: 28, streakWeeks: 11, topics: {...}, insights: [...], growthHistory: [...] }
}

// Topic 模型
topic = {
  mastery: number (0-1),    // 掌握度
  visits: number,           // 学习次数
  status: string            // 状态文本: "新朋友"|"正在巩固"|"比较熟了"|"很稳"
}

// Growth History 条目
growthHistoryItem = {
  time: string,       // 相对时间
  title: string,      // 事件标题
  summary: string     // 事件描述
}

// 全局状态
state = {
  page: 'today' | 'growth' | 'profile' | 'more',
  subject: 'linear' | 'recursion',
  scene: 'continue' | 'return',
  era: 'week1' | 'month1' | 'month3',
  session: { active, stage, practiceAnswered, reflectionText, learnTurn, toolNudged, cardCreatedThisSession, stuckSignal },
  flashcards: { idx },
  voice: { speaking },
  pomo: { running, seconds },
  tasks: [{ text, tag, done }],
  prefs: { quote, serif, source },
  customCards: [],
  newInsight: null
}
```

---

## 9. 数据流

### 9.1 主数据流

```
用户操作 → state 更新 → renderPage() → DOM 重渲染
                                      ↓
Session 完成 → updateMemoryFromSession() → 更新 mem
                                       ↓
                                  newInsight 生成
                                       ↓
                                  Today 页显示 MemoryPulse
```

### 9.2 Session 数据流

```
startSession()
  ↓
renderSession() → 根据 stage 渲染对应视图
  ↓
goStage(next) → 更新 state.session.stage → rerender
  ↓
finishSession()
  ├→ updateMemoryFromSession()
  │   ├→ topic.visits++
  │   ├→ sessionsDone++
  │   └→ growthHistory.unshift(newRecord)
  ├→ state.newInsight = Narrative.newInsightAfterSession()
  └→ exitSession() → renderPage() → Today 显示新洞察
```

### 9.3 记忆更新流

```
Practice 完成
  ↓
updateMemoryFromPractice(correct)
  ├→ topic.mastery += correct ? 0.08 : 0.02
  ├→ topic.visits++
  ├→ topic.status = recalc(mastery)
  └→ pressure += correct ? 0 : 0.05

Session 完成
  ↓
updateMemoryFromSession()
  ├→ topic.visits++
  ├→ sessionsDone++
  └→ growthHistory.unshift({ time:'刚才', title, summary })
```

### 9.4 工具数据流

```
Tool 创建卡片
  ↓
state.customCards.push(card)
  ↓
下次打开 Flashcard → getAllCards() → 合并预设卡片 + 自建卡片
  ↓
复习 → gradeFlashcard() → 更新 idx → 下一张 / 完成
```

---

## 10. API 映射

Demo3.0 是纯前端演示，无后端 API。以下为未来实现时的 API 映射建议：

| 功能 | 数据类型 | 建议 API | 当前数据来源 |
|------|---------|---------|-------------|
| Today Observation | 字符串 | GET /api/today/observation | Narrative.todayObservation() |
| Today MemoryPulse | 字符串 | GET /api/today/insight | state.newInsight |
| LastSession | Object | GET /api/sessions/latest | mem.growthHistory[0] |
| Session Learn | 对话数组 | GET /api/sessions/{id}/conversation | DATA[subject].learnConversation |
| Practice Question | Object | GET /api/practice/next | DATA[subject].practice |
| Profile Mirror | 字符串 | GET /api/profile/mirror | Narrative.profileMirror() |
| Profile Prefs | 键值对数组 | GET /api/profile/preferences | Narrative.profilePrefs() |
| Growth Timeline | 数组 | GET /api/growth/timeline | mem.growthHistory |
| Growth Narrative | 字符串 | GET /api/growth/narrative | Narrative.growthNarrative() |
| Flashcard Set | 数组 | GET /api/flashcards | getAllCards() |
| Reader Content | Object | GET /api/reader/{id} | DATA[subject].readerTitle + 内联内容 |
| Tools List | 数组 | GET /api/tools | 硬编码在 renderMore() |
| Preferences | Object | GET /api/user/preferences | state.prefs |
| Narration Update | - | POST /api/sessions/{id}/complete | finishSession() 的副作用 |
| Card Create | - | POST /api/flashcards | createCardFromPractice() |

---

## 11. 数据库映射

Demo3.0 无后端数据库。以下为域模型建议：

| 域 | 实体 | 关键字段 |
|----|------|---------|
| **Memory** | UserMemory | userId, sessionsDone, streakWeeks, topics:{topicId: {mastery, visits, status}}, insights[], pressure |
| **Growth** | GrowthRecord | userId, time, title, summary, sessionId |
| **Session** | Session | id, userId, subject, missionTitle, stages, startedAt, completedAt |
| **Conversation** | Message | id, sessionId, role(ai/user), content, timestamp |
| **Flashcard** | Flashcard | id, userId, front, back, source(system/custom), nextReview, interval |
| **Practice** | PracticeAttempt | id, sessionId, questionId, correct, answeredAt |
| **Reflection** | Reflection | id, sessionId, content, createdAt |
| **Pomodoro** | PomodoroSession | id, userId, duration, completed, taskIds[] |
| **Preferences** | UserPrefs | userId, showQuote, serifFont, sources[] |

---

## 12. 动画行为

| 动画 | 触发 | 实现 | 时长 |
|------|------|------|------|
| sessionEnter | Session Overlay 出现 | translateY(20px) → 0, opacity 0→1 | 300ms ease-out |
| msgIn | 新消息出现 | translateY(8px) → 0, opacity 0→1 | 300ms ease-out |
| typing cursor | AI 打字中 | opacity blink | 0.8s infinite |
| thinking dots | AI 消息加载中 | 三点 bounce | 1.2s infinite |
| voice ring | 语音房间 orb | scale(1)→(1.5), opacity 递减 | 1.8s infinite |
| waveBar | 语音声波动画 | height 6→28→6 | 0.9s infinite ease-out |
| nodePop | 画布新节点 | scale(0.7)→(1), opacity 0→1 | 400ms ease-spring |
| pulse | 红点/番茄 badge | opacity 1→0.4→1 | 1.5s infinite |
| fadeIn | 页面切换/元素出现 | opacity 0→1 | 400ms ease-out |
| blink | typing cursor | opacity 1→0 | 0.8s infinite |
| toggle switch | 偏好 toggle | translateX(0)→(18px) | 200ms ease-spring |
| flashcard flip | 卡片翻转 | rotateY(0)→(180deg) | 600ms ease-out |
| pomo ring | 番茄钟进度 | stroke-dashoffset 线性变化 | 1s linear |

---

## 13. Loading / Empty / Error 状态

### 13.1 Demo3.0 已实现的状态

| 页面 | Loading | Empty | Error | 备注 |
|------|---------|-------|-------|------|
| Today | ❌ 未实现 | ✅ 新用户等同 Empty | ❌ 未实现 | 演示中无网络请求 |
| Session - Learn | ✅ typing cursor + thinking dots | ❌ 始终有内容 | ❌ 未实现 | 对话固定内容 |
| Session - Practice | ❌ 无 loading | ❌ 始终有题目 | ❌ 未实现 | 固定题库 |
| Growth | ❌ 无 loading | ⚡ 新用户应显示空态但未实现 | ❌ 未实现 | Timeline 可能为空 |
| Profile | ❌ 无 loading | ❌ 始终有 Mirror | ❌ 未实现 | 基于记忆总有内容 |
| More | ❌ 无 loading | ❌ 始终有 8 个工具 | ❌ 未实现 | 固定工具列表 |
| Flashcard | ❌ 无 loading | ✅ 全部复习完有完成态 | ❌ 未实现 | |
| Pomodoro | ❌ 无 loading | ✅ 无任务时显示空列表 | ❌ 未实现 | |

### 13.2 未来实现需补充的状态

- **Today**：数据加载中 skeleton、网络错误提示
- **Session**：API 调用失败提示、重试机制
- **Growth**：新用户空时间线引导文案
- **Profile**：数据加载失败 fallback
- **各工具页**：API 初始化失败处理

---

## 14. 权限

Demo3.0 为纯前端演示，无权限系统。

| 权限 | 当前处理 | 未来建议 |
|------|---------|---------|
| 用户认证 | 无 | 登录后确定 userId |
| 数据隔离 | 无（全局 mem） | 按 userId 加载记忆数据 |
| 学科访问 | 无限制 | 按用户学习记录动态展示 |
| 工具访问 | 全部开放 | 按学习状态/场景智能建议 |

---

## 15. 未来扩展点

| 扩展点 | 当前状态 | 建议 |
|--------|---------|------|
| **多学科动态数据** | 硬编码 DATA[linear|recursion] | 从数据库动态加载学科内容 |
| **FSRS 调度** | gradeFlashcard 仅移动 idx | 实现完整 FSRS 间隔重复算法 |
| **语音识别** | voice 仅模拟 | 集成 Web Speech API 或第三方 |
| **手写识别** | canvas 仅保存位图 | 集成手写识别引擎 |
| **Canvas 概念图** | 固定 SVG 连线 + 拖拽 | 实现完整图形数据模型 |
| **阅读内容源** | 内联固定文本 | 从数据库/Markdown 动态加载 |
| **学习推荐** | 基于固定记忆阈值 | 实现协同+内容混合推荐 |
| **社交/协作** | 无 | 共享画布、学习小组 |
| **离线支持** | 无 | Service Worker + IndexedDB 缓存 |
| **多端适配** | 仅 Mobile Web | 桌面版自适应布局 |
| **数据分析** | 仅 Timeline | 学习行为分析仪表盘 |
| **AI 对话深度** | 固定回复映射 | 接入 LLM 实现开放对话 |

---

## 完成检查

| LOOP.md Phase A 步骤 | 对应章节 | 状态 |
|----------------------|---------|------|
| 1. 逐页分析 Demo 的每个可用页面 | §1.1 页面拓扑 | ✅ |
| 2. 拆解每页的信息架构 | §2.1, §3.1, §4.1, §5.1, §6.1, §7.1 | ✅ |
| 3. 拆解每页的状态 | §2.2, §3.3, §4.2, §5.2, §6.3, §13 | ✅ |
| 4. 拆解页面级组件树 | §2.3, §3.3, §4.3, §5.3, §6.2, §7 | ✅ |
| 5. 提取组件职责 | 各组件 props 定义 | ✅ |
| 6. 定义交互事件 | §2.4, §3.4 | ✅ |
| 7. 定义 AI 行为 | §2.5, §3.3.2, §4.4, §5.4 | ✅ |
| 8. 定义 Runtime 行为 | §9 数据流, §8.3 状态模型 | ✅ |
| 9. 绘制数据流 | §9 数据流图 | ✅ |
| 10. 映射 API | §10 API 映射表 | ✅ |
| 11. 映射数据库 | §11 数据库映射表 | ✅ |
| 12. 定义动画行为 | §12 动画表 | ✅ |
| 13. 定义 loading/empty/error 状态 | §13 状态清单 | ✅ |
| 14. 定义权限 | §14 权限表 | ✅ |
| 15. 定义未来扩展点 | §15 扩展点清单 | ✅ |

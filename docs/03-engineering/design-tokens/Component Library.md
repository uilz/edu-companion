# AppleGo Component Library

> **Phase C 输出：可复用组件清单 + Props + 状态 + 组合关系。**
>
> 基准：Demo3.0 (preview.html) | 纪律：任何页面只能拼组件，不得重复开发

---

## 1. 组件分类

| 分类 | 数量 | 覆盖范围 |
|------|------|---------|
| 布局组件 | 6 | BottomNav, TopBar, Overlay, 页面容器等 |
| 通用组件 | 9 | Button, Input, Card, Toggle, 状态层等 |
| 内容组件 | 9 | PageTitle, Quote, Narrative, Timeline, 偏好等 |
| Session 组件 | 12 | 消息气泡、输入栏、练习、反思、完成等 |
| 工具组件 | 14 | 闪卡、阅读、语音、画布、手写、番茄钟等 |

---

## 2. 布局组件

### AppleBottomNav

固定底部导航栏，4 Tab。

**Props**:
```
interface AppleBottomNavProps {
  activeTab: 'today' | 'growth' | 'profile' | 'more';
  onTabSelect: (tab: string) => void;
}
```

**状态**：无状态（由 activeTab 控制高亮）

**组合**：App 根布局

**需要 Storybook**：✅

### ApplePageContainer

主内容容器，居中单列布局（max-width: 560px）。

**Props**:
```
interface ApplePageContainerProps {
  children: ReactNode;
  padding?: 'default' | 'compact';  // default: var(--space-4), compact: var(--space-3)
}
```

**状态**：无状态

**组合**：所有页面

**需要 Storybook**：否（纯布局 Wrapper）

### AppleTopBar

页面顶部栏，含返回按钮 + 标题 + 可选右侧操作。

**Props**:
```
interface AppleTopBarProps {
  title: string;
  onBack?: () => void;
  rightAction?: ReactNode;
  variant?: 'session' | 'tool';
}
```

**状态**：无状态

**组合**：Session Overlay, ToolPage

**需要 Storybook**：✅

### AppleSessionOverlay

Session 全屏覆盖层容器。

**Props**:
```
interface AppleSessionOverlayProps {
  active: boolean;
  onClose: () => void;
  title: string;
  progress: number;        // 0-100
  stages: StageIndicator[];
  onToolTrigger: () => void;
  toolNudgeVisible: boolean;
  pomoBadgeVisible: boolean;
  children: ReactNode;
}
interface StageIndicator {
  done: boolean;
  active: boolean;
}
```

**状态**：active / inactive

**组合**：AppleTopBar, AppleProgressBar, AppleStageDots

**需要 Storybook**：✅

### AppleToolPage

工具页全屏覆盖层容器。

**Props**:
```
interface AppleToolPageProps {
  title: string;
  onClose: () => void;
  children: ReactNode;
}
```

**状态**：active / inactive

**组合**：所有工具页内容

**需要 Storybook**：否

### AppleDemoBar

演示控制条（仅开发/演示环境）。

**Props**:
```
interface AppleDemoBarProps {
  subject: string;
  era: string;
  scene: string;
  onSubjectChange: (s: string) => void;
  onEraChange: (e: string) => void;
  onSceneChange: (s: string) => void;
}
```

**状态**：collapsed / expanded

**需要 Storybook**：否（仅演示用）

---

## 3. 通用组件

### AppleButton

**变体**：
| 变体 | CSS | 用途 |
|------|-----|------|
| primary | btn btn-primary | 主行动按钮（开始学习、继续） |
| outline | btn btn-outline | 次要操作（跳过、返回） |
| link | text-link | 文字链接（今天想学点别的） |
| pill | suggestion-pill | 建议/快捷回复 |
| grade | fc-grade | 闪卡评分（again/hard/good/easy） |

**Props**:
```
interface AppleButtonProps {
  variant: 'primary' | 'outline' | 'link' | 'pill' | 'grade';
  size?: 'default' | 'lg';
  color?: 'accent' | 'success' | 'warning' | 'danger';  // grade variant
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
  icon?: ReactNode;
}
```

**状态**：default / hover / active / disabled

**组合**：所有页面

**需要 Storybook**：✅

### AppleInput

**变体**：input-field（文本输入）、learn-input-bar 内的输入框

**Props**:
```
interface AppleInputProps {
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  onEnter?: () => void;
  variant?: 'default' | 'chat';
  multiline?: boolean;
}
```

**状态**：default / focus / disabled / placeholder

**组合**：Session InputBar, IntroSwitch

**需要 Storybook**：✅

### AppleToggle

开关组件。

**Props**:
```
interface AppleToggleProps {
  on: boolean;
  onChange: () => void;
}
```

**状态**：on / off

**组合**：Preferences

**需要 Storybook**：✅

### AppleCard

通用卡片容器。

**Props**:
```
interface AppleCardProps {
  children: ReactNode;
  variant?: 'default' | 'highlight' | 'insight';
  padding?: 'default' | 'compact';
  onClick?: () => void;
}
```

**状态**：default / hover / highlight（new-item 蓝色边框）

**组合**：所有卡片内容

**需要 Storybook**：✅

### AppleToast

Toast 提示。

**Props**:
```
interface AppleToastProps {
  message: string;
  duration?: number;  // default 2200ms
}
```

**状态**：visible → fading → hidden（自动清除）

**需要 Storybook**：否（全局工具）

### AppleSkeleton

骨架屏（Demo3.0 未实现，留扩展）。

**状态**：loading

**需要 Storybook**：✅

### AppleEmptyState

空状态引导（Demo3.0 部分实现）。

**Props**:
```
interface AppleEmptyStateProps {
  icon?: string;
  title: string;
  description: string;
  action?: { label: string; onClick: () => void };
}
```

**需要 Storybook**：✅

### AppleErrorState

错误状态（Demo 未实现，留扩展）。

**需要 Storybook**：✅

---

## 4. 内容组件

### ApplePageTitle

页面标题。

**Props**: `{ title: string }`

**使用**：Growth, Profile, More 页面

**需要 Storybook**：否

### AppleQuoteBanner

每日一言横幅。

**Props**: `{ text: string; visible: boolean }`

**状态**：visible / hidden

**组合**：Today 页面

**需要 Storybook**：否

### AppleGreetingSection

Today 页问候区。

**Props**:
```
interface AppleGreetingSectionProps {
  greeting: string;
  date: string;
  observation: string;
}
```

**组合**：Today 页面

**需要 Storybook**：✅

### AppleLastSessionCard

上次学习摘要卡片。

**Props**:
```
interface AppleLastSessionCardProps {
  label: string;       // "昨天" / "上次"
  title: string;
  status: string;      // 苹果果对你的理解状态
}
```

**状态**：continue / return / hidden（新用户）

**组合**：Today 页面

**需要 Storybook**：✅

### AppleMemoryPulse

学后新洞察提示。

**Props**: `{ text: string; onClose?: () => void }`

**状态**：visible / hidden

**组合**：Today 页面（学后返回时显示）

**需要 Storybook**：✅

### AppleGrowthNarrative

Growth 页叙事总结。

**Props**: `{ text: string }`

**组合**：Growth 页面

**需要 Storybook**：否

### AppleProfileMirror

Profile 页苹果果画像。

**Props**: `{ html: string }` — 可包含 `<span class="highlight">` 标签

**组合**：Profile 页面

**需要 Storybook**：✅

### AppleTimeline

时间线组件。

**Props**:
```
interface AppleTimelineProps {
  items: AppleTimelineItem[];
}
interface AppleTimelineItem {
  time: string;
  title: string;
  summary: string;
  isNew?: boolean;
}
```

**状态**：有历史 / 空

**组合**：Growth 页面

**需要 Storybook**：✅

### ApplePrefGrid

偏好键值对网格。

**Props**: `{ items: { label: string; value: string }[] }`

**组合**：Profile 页面

**需要 Storybook**：否

---

## 5. Session 组件

### AppleAIQuote

苹果果引言（大号，居中）。

**Props**: `{ text: string }`

**使用**：Session Intro, Finish

**需要 Storybook**：否

### AppleMessage

对话消息气泡。

**Props**:
```
interface AppleMessageProps {
  role: 'ai' | 'user';
  text: string;
  typing?: boolean;     // AI 打字中
  thinking?: boolean;   // AI 思考中
  feedback?: { variant: 'ok' | 'nope'; text: string };
}
```

**状态**：
| 状态 | 说明 |
|------|------|
| default | 完整消息显示 |
| typing | AI 正在打字（typing cursor） |
| thinking | AI 正在思考（三点动画） |
| feedback | 练习反馈气泡（ok/nope） |

**组合**：Conversation

**需要 Storybook**：✅

### AppleConversation

对话容器，含消息列表 + suggestion row + input bar。

**Props**:
```
interface AppleConversationProps {
  messages: AppleMessage[];
  suggestions: string[];
  onSuggestion: (text: string) => void;
  onSend: (text: string) => void;
  inputPlaceholder: string;
}
```

**组合**：Session Learn 阶段

**需要 Storybook**：✅

### AppleSuggestionRow

推荐追问/操作按钮行。

**Props**: `{ pills: AppleSuggestionPill[] }`
```
interface AppleSuggestionPill {
  label: string;
  variant?: 'default' | 'accent';
  onClick: () => void;
}
```

**需要 Storybook**：否

### AppleEmbedToolCard

内联工具推荐卡片（嵌入对话）。

**Props**:
```
interface AppleEmbedToolCardProps {
  icon: string;
  iconBg: string;
  title: string;
  description: string;
  buttonLabel: string;
  onAction: () => void;
}
```

**状态**：default / done（点击后显示 ✓ 确认）

**需要 Storybook**：✅

### AppleToolNudge

工具推荐红点提示。

**Props**: `{ visible: boolean }`

**状态**：show / hidden

**需要 Storybook**：否

### ApplePracticeQuestion

练习题目卡片。

**Props**:
```
interface ApplePracticeQuestionProps {
  label: string;     // "练一练"
  question: string;
  code?: string;     // 可选代码块
  options: { text: string; index: number }[];
  correctIndex: number;
  onAnswer: (index: number) => void;
}
```

**状态**：unanswered / correct / wrong / locked

**组合**：Session Practice 阶段

**需要 Storybook**：✅

### AppleFeedbackBubble

作答反馈气泡。

**Props**:
```
interface AppleFeedbackBubbleProps {
  verdict: string;
  text: string;
  variant: 'ok' | 'nope';
}
```

**需要 Storybook**：否

### AppleReflectView

反思区。

**Props**:
```
interface AppleReflectViewProps {
  prompt: string;
  subPrompt: string;
  placeholder: string;
  value: string;
  onChange: (v: string) => void;
  draftText?: string;       // "苹果果帮你整理"的草稿
  onDraft: () => void;
  onSkip: () => void;
  onSubmit: () => void;
}
```

**状态**：empty / draft-filling / filled / submitted

**需要 Storybook**：✅

### AppleFinishHero

Session 完成页。

**Props**: `{ onBackToHome: () => void }`

**需要 Storybook**：否

### AppleProgressBar

线性进度条。

**Props**: `{ progress: number }` — 0-100

**需要 Storybook**：否

### AppleStageDots

阶段进度指示器。

**Props**: `{ stages: { done: boolean; active: boolean }[] }`

**需要 Storybook**：否

---

## 6. 工具组件

### AppleMoreCard

工具箱网格卡片。

**Props**:
```
interface AppleMoreCardProps {
  icon: string;
  iconBg: string;
  title: string;
  description: string;
  onClick: () => void;
}
```

**状态**：default / hover

**组合**：More 页面

**需要 Storybook**：✅

### AppleToolQuickButton

Today 页快捷工具入口。

**Props**:
```
interface AppleToolQuickButtonProps {
  icon: string;
  iconBg: string;
  title: string;
  subtitle: string;
  onClick: () => void;
}
```

**组合**：Today 页面

**需要 Storybook**：✅

### AppleFlashcard

闪卡（翻转卡片）。

**Props**:
```
interface AppleFlashcardProps {
  front: string;
  back: string;
  flipped: boolean;
  onFlip: () => void;
}
```

**状态**：front / flipped

**组合**：FlashcardView

**需要 Storybook**：✅

### AppleFlashcardGrade

闪卡四级评分按钮组。

**Props**:
```
interface AppleFlashcardGradeProps {
  visible: boolean;
  onGrade: (grade: 'again' | 'hard' | 'good' | 'easy') => void;
}
```

**状态**：hidden / visible

**需要 Storybook**：否

### AppleFlashcardDone

闪卡完成页。

**Props**: `{ cardCount: number; onReturn: () => void }`

**需要 Storybook**：否

### AppleReaderView

阅读视图。

**Props**:
```
interface AppleReaderViewProps {
  meta: string;
  title: string;
  paragraphs: string[];
  highlightedIndices: number[];      // 可划线的段落索引
  onHighlightClick: (index: number) => void;
  aiNote?: { text: string };
  cardCreatedIndices: number[];      // 已创建卡片的索引
}
```

**状态**：content / creating-card（划线动画）

**需要 Storybook**：✅

### AppleReaderAINote

阅读 AI 注解。

**Props**: `{ text: string }`

**需要 Storybook**：否

### AppleVoiceRoom

语音房间。

**Props**:
```
interface AppleVoiceRoomProps {
  speaking: boolean;
  transcript: { role: 'ai' | 'user'; text: string }[];
  quickReplies: string[];
  onToggle: () => void;
  onEnd: () => void;
  onQuickReply: (text: string) => void;
}
```

**状态**：idle / speaking / paused

**需要 Storybook**：✅

### AppleVoiceOrb

语音 Orb（脉冲动画）。

**Props**: `{ state: 'idle' | 'speaking' }`

**需要 Storybook**：✅

### AppleCanvasView

概念画布。

**Props**:
```
interface AppleCanvasViewProps {
  nodes: CanvasNode[];
  svgPaths: string;  // SVG path data for connections
  onAddNode: () => void;
  onNodeDrag: (id: string, x: number, y: number) => void;
}
interface CanvasNode {
  id: string;
  icon: string;
  iconBg: string;
  title: string;
  subtitle: string;
  x: number;
  y: number;
  linked?: boolean;
  isNew?: boolean;
}
```

**需要 Storybook**：✅

### AppleHandwritePad

手写画布。

**Props**:
```
interface AppleHandwritePadProps {
  onSave?: (canvas: HTMLCanvasElement) => void;
}
```

**需要 Storybook**：否

### AppleFileItem

文件列表项。

**Props**:
```
interface AppleFileItemProps {
  icon: string;
  iconBg: string;
  name: string;
  meta: string;
}
```

**需要 Storybook**：否

### ApplePomodoroClock

番茄钟。

**Props**:
```
interface ApplePomodoroClockProps {
  seconds: number;   // 剩余秒数
  running: boolean;
  onToggle: () => void;
  onReset: () => void;
}
```

**状态**：ready / running / paused

**需要 Storybook**：✅

### AppleTaskItem

任务项。

**Props**:
```
interface AppleTaskItemProps {
  text: string;
  tag: string;
  done: boolean;
  onToggle: () => void;
}
```

**状态**：undone / done

**组合**：PomodoroView

**需要 Storybook**：否

### ApplePreferencesView

偏好设置页。

**Props**:
```
interface ApplePreferencesViewProps {
  prefs: { quote: boolean; source: boolean };
  onToggle: (key: string) => void;
  sources: { name: string; desc: string; active: boolean }[];
  onSourceToggle: (index: number) => void;
}
```

**需要 Storybook**：✅

---

## 7. 组件组合关系

### 页面 → 组件映射

```
TodayPage
├── AppleQuoteBanner (条件)
├── AppleGreetingSection
│   └── AppleMemoryPulse (条件)
├── AppleLastSessionCard
├── AppleToolQuickButton[]
├── AppleButton (CTA)
└── AppleButton (link variant)

SessionOverlay
├── AppleTopBar (session variant)
│   ├── AppleStageDots
│   └── AppleToolNudge
├── AppleProgressBar
└── Session Body
    ├── [Intro] AppleAIQuote + AppleButton
    ├── [Learn] AppleConversation
    │               ├── AppleMessage[]
    │               ├── AppleSuggestionRow
    │               ├── AppleInput
    │               └── AppleEmbedToolCard (条件)
    ├── [Practice] ApplePracticeQuestion
    │               ├── AppleFeedbackBubble
    │               └── AppleEmbedToolCard
    ├── [Reflect] AppleReflectView
    └── [Finish] AppleFinishHero

GrowthPage
├── ApplePageTitle
├── AppleGrowthNarrative
└── AppleTimeline
    └── AppleTimelineItem[]

ProfilePage
├── ApplePageTitle
├── AppleProfileMirror
└── ApplePrefGrid
    └── ApplePrefRow[]

MorePage
├── ApplePageTitle
└── AppleMoreCardGrid (2 col)
    └── AppleMoreCard[]

ToolPage (通用)
├── AppleTopBar (tool variant)
└── Tool-specific content
    ├── [Flashcard] AppleFlashcard + AppleFlashcardGrade
    ├── [Reader] AppleReaderView + AppleReaderAINote
    ├── [Voice] AppleVoiceRoom + AppleVoiceOrb
    ├── [Canvas] AppleCanvasView
    ├── [Pomodoro] ApplePomodoroClock + AppleTaskItem[]
    └── [Preferences] ApplePreferencesView
```

### 跨页面复用关系

| 组件 | 使用页面 |
|------|---------|
| AppleButton | 全部页面 |
| AppleCard | Today, Session, Growth, Profile |
| AppleInput | Session, IntroSwitch |
| AppleToggle | Preferences |
| AppleToast | Reader（划线成功提示） |
| ApplePageTitle | Growth, Profile, More |
| AppleTopBar | Session, ToolPage |

---

## 8. 需要 Storybook 的组件清单

| 组件 | 优先级 | 原因 |
|------|--------|------|
| AppleBottomNav | P0 | 全局导航，必须视觉准确 |
| AppleTopBar | P0 | 多页面复用 |
| AppleButton (所有变体) | P0 | 最高频交互元素 |
| AppleInput | P0 | 高频表单元素 |
| AppleToggle | P0 | 偏好控制 |
| AppleCard | P0 | 基础容器 |
| AppleMessage | P0 | Session 核心交互 |
| AppleConversation | P0 | Session Learn 核心 |
| ApplePracticeQuestion | P0 | 练习核心 |
| AppleReflectView | P0 | 反思核心 |
| AppleFlashcard | P0 | 闪卡核心 |
| ApplePomodoroClock | P0 | 番茄钟核心 |
| AppleGreetingSection | P1 | Today 核心区 |
| AppleLastSessionCard | P1 | Today 核心区 |
| AppleMemoryPulse | P1 | 学后反馈关键 |
| AppleProfileMirror | P1 | Profile 核心 |
| AppleTimeline | P1 | Growth 核心 |
| AppleMoreCard | P1 | More 页面核心 |
| AppleToolQuickButton | P1 | Today 快捷入口 |
| AppleEmbedToolCard | P1 | Session 工具打通 |
| AppleReaderView | P1 | 阅读核心 |
| AppleVoiceRoom | P1 | 语音核心 |
| AppleCanvasView | P1 | 画布核心 |
| AppleSkeleton | P2 | 未来扩展 |
| AppleEmptyState | P2 | 未来扩展 |
| AppleErrorState | P2 | 未来扩展 |

---

## 9. 纪律

1. **任何页面只能拼组件，不得重复开发** — 如果发现重复 UI 模式，先检查是否已有对应组件
2. **所有组件必须引用 Design Token** — 不得在组件文件内硬编码颜色/字号/间距/圆角
3. **Props 命名遵循以上定义** — 不随意扩展 Props，如需新增 review with Founder
4. **状态命名统一** — default / hover / active / disabled / loading / empty / error
5. **组件文件命名** — 使用 PascalCase，如 `AppleBottomNav.tsx`

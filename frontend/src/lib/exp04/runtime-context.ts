// Learning Runtime Type Definitions
// Runtime Context

/**
 * ============================================================
 * Learning Runtime Types
 *
 * This file defines the core data model for AppleGo's
 * Learning Runtime. All LI modules read/write through
 * RuntimeContext — the single mutable source for a Session.
 *
 * Principles:
 *   P4 — Shared Context, Isolated Capability
 *   P8 — RuntimeContext is the single mutable source
 *
 * ============================================================
 */


// ────────────────────────────────────────────────────────────
// 1. RuntimeContext — Session 内唯一可变对象
// ────────────────────────────────────────────────────────────

export interface RuntimeContext {
  sessionId: string;
  userId: string;

  /** LI-01: Mission Intelligence 输出 */
  mission: MissionContext;
  /** 当前 Learner State（读时组装，LI-03 写回持久层） */
  learner: LearnerContext;
  /** Session 流程状态 */
  flow: FlowContext;
  /** LI-02: Understanding Intelligence 输出 */
  understanding: UnderstandingContext;
  /** REFLECTION 阶段输入 */
  reflection: ReflectionContext;
  /** LI-04: 对话状态（关闭即清除） */
  conversation: ConversationContext;
}

// ────────────────────────────────────────────────────────────
// 2. Mission Context
// ────────────────────────────────────────────────────────────

export interface MissionContext {
  /** 用户输入的学习目标标题 */
  title: string;
  /** Mission 来源 */
  source: MissionSource;
  /** LI-01 输出 */
  analysis: MissionAnalysis | null;
}

export type MissionSource =
  | "user_topic"
  | "welcome_back"
  | "system_recommend";

/**
 * LI-01 输出的结构化 Mission 理解。
 * 不是 Prompt 产物，是整个 Runtime 的 Mission 数据模型。
 */
export interface MissionAnalysis {
  /** 核心概念（name / importance / description） */
  concepts: ConceptItem[];
  /** 前置知识 */
  dependencies: DependencyItem[];
  /** 用户角度的学习目标 */
  learningObjectives: string[];
  /** 潜在难点 + 常见误区 */
  difficultySpots: DifficultySpot[];
  /** 练习策略（LI-05 消费） */
  practiceStrategy: PracticeStrategy | null;
  /** 反思引导方向 */
  reflectionFocus: string[];
  /** 成长观察方向（LI-03 消费） */
  growthSignals: GrowthSignals;
}

export interface ConceptItem {
  name: string;
  importance: "high" | "medium" | "low";
  description: string;
  /** P7: 不确定标注 */
  confidence?: number;
}

export interface DependencyItem {
  concept: string;
  importance: "required" | "recommended";
}

export interface DifficultySpot {
  point: string;
  commonMisconception: string;
  difficultyLevel: number; // 1-5
  confidence?: number;
}

export interface PracticeStrategy {
  type: "explanation" | "comparison" | "correction";
  focus: string;
}

export interface GrowthSignals {
  expectedGains: string[];
  observationPoints: string[];
}

// ────────────────────────────────────────────────────────────
// 3. Learner Context
// ────────────────────────────────────────────────────────────

export interface LearnerContext {
  /** 知识掌握度（从 BKT CognitiveNode 读取） */
  knowledge: Record<string, SkillState>;
  /** 学习者画像 */
  profile: LearnerProfile;
  /** 最近成长记录 */
  recentGrowth: GrowthRecord | null;
  /** 推理模式（跨 Session 累积） */
  patterns: ReasoningPattern | null;
}

export interface SkillState {
  proficiency: number;  // 0-1, BKT proficiency_mean
  precision: number;    // BKT proficiency_precision
  trend: "ascending" | "stable" | "declining";
  lastActive: string | null; // ISO date
}

export interface LearnerProfile {
  subjects: string[];
  gradeLevel: string;
  learningStyle: "visual" | "reading" | "kinesthetic" | null;
}

export interface GrowthRecord {
  sessionId: string;
  skillGains: string[];
  summary: string;
  keyTakeaways: string[];
  reflectionSnippet: string | null;
  createdAt: string; // ISO date
}

export interface ReasoningPattern {
  prefersAnalogy: boolean | null;
  needsVisualization: boolean | null;
  tendsToOvergeneralize: boolean | null;
  catchesEdgeCases: boolean | null;
}

// ────────────────────────────────────────────────────────────
// 4. Flow Context
// ────────────────────────────────────────────────────────────

export interface FlowContext {
  currentStage: Exp04Stage;
  cognitiveSearchTriggered: boolean;
  cognitiveSearchDurationMs: number | null;
}

export type Exp04Stage =
  | "ENTER"
  | "LEARN"
  | "COGNITIVE_SEARCH"
  | "SELF_VALIDATION"
  | "REFLECTION"
  | "END";

// ────────────────────────────────────────────────────────────
// 5. Understanding Context
// ────────────────────────────────────────────────────────────

export interface UnderstandingContext {
  /** 用户在 SELF_VALIDATION 写的理解 */
  userText: string;
  /** 原文参考 */
  referenceText: string;
  /** LI-02 分析输出 */
  analysis: UnderstandingAnalysis | null;
  /** 生成的引导问题 */
  guidanceGiven: string | null;
}

/**
 * LI-02 输出。分析用户写的理解，形成 Observation。
 *
 * 采用 Observation / Evidence / Hypothesis 三元组 —— 不是标签。
 * 所有 Hypothesis 必须标注 confidence（P7）。
 */
export interface UnderstandingAnalysis {
  /** 概念观察（O-E-H） */
  conceptObservations: ConceptObservation[];
  /** 推理迹象 */
  reasoningEvidence: ReasoningEvidence;
  /** 理解差距 */
  gaps: UnderstandingGap[];
  /** 元认知信号 */
  metacognitiveSignals: MetacognitiveSignals;
  /** → LI-03 更新指令 */
  learnerDelta: LearnerDelta;
}

export interface ConceptObservation {
  concept: string;
  observation: string;   // 用户表达了什么 / 没表达什么
  evidence: string;      // 原文引用
  hypothesis: string;    // 苹果果的假设
  confidence: number;    // 0.0 ~ 1.0，< 0.5 时不触发引导
}

export interface ReasoningEvidence {
  usesOwnWords: boolean;
  makesConnections: string[];
  asksQuestions: string[];
}

export interface UnderstandingGap {
  concept: string;
  observation: string;
  evidence: string;
  hypothesis: string;
  severity: 1 | 2 | 3;
  confidence: number;
}

export interface MetacognitiveSignals {
  awareOfGap: boolean;
  overconfidentOn: string[];
}

export interface LearnerDelta {
  knowledgeUpdates: KnowledgeUpdate[];
  reasoningInsights: string[];
  growthInsights: string[];
}

export interface KnowledgeUpdate {
  skillId: string;
  confidenceShift: number; // -1 到 +1
  evidence: string;
}

// ────────────────────────────────────────────────────────────
// 6. Reflection Context
// ────────────────────────────────────────────────────────────

export interface ReflectionContext {
  content: string | null;
  wasSkipped: boolean;
}

// ────────────────────────────────────────────────────────────
// 7. Conversation Context
// ────────────────────────────────────────────────────────────

export interface ConversationContext {
  isOpen: boolean;
  roundCount: number;
  messages: ChatMessage[];
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: string; // ISO date
}

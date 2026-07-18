"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, Clock, Loader2, Play } from "lucide-react";
import { useSecretaryDashboard } from "@/hooks/useSecretaryDashboard";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/Skeleton";
import ErrorState from "@/components/ui/ErrorState";
import { authedFetch } from "@/lib/api/api";
import type {
  DashboardFocus,
  DashboardRecommendations,
  DashboardActivity,
} from "@/lib/api/secretary-dashboard-api";

// ── 视图模型（叙事驱动） ──────────────────────────────────

interface ActiveSession {
  id: string;
  title: string;
  stage: string;
  status: string;
  started_at: number;
}

interface ContinueContext {
  type: "active_session" | "yesterday" | "welcome_back" | "none";
  session_id?: string;
  title?: string;
  stage?: string;
  key_takeaways?: string[];
  reflection_snippet?: string;
  skills?: string[];
  topic_status?: string;
  date_label?: string;
  started_at?: number;
}

interface TodayViewModel {
  greeting: string;
  date: string;
  /** 苹果果的观察：一段完整的第一人称叙事 */
  observation: string;
  /** 聚焦卡片 */
  focusCard: {
    title: string;
    description: string;
    estimatedMinutes: number;
  } | null;
  /** 做完之后的预期 */
  afterPlan: string;
  /** 焦点标题（用于创建 Session） */
  focusTitle: string;
  /** 今日名言 */
  quote: string;
  /** 是否显示名言 */
  quoteEnabled: boolean;
  /** 记忆脉冲（最新成长摘要） */
  memoryPulse: string | null;
}

const TODAY_QUOTES = [
  "理解一个概念，比记住一百个更重要。",
  "学习的节奏，是你自己的节奏。",
  "今天少做一点，也是向前。",
  "困惑是理解的开始。",
];

function pickDailyQuote(seedDate: string): string {
  let hash = 0;
  for (let i = 0; i < seedDate.length; i++) {
    hash = seedDate.charCodeAt(i) + ((hash << 5) - hash);
  }
  const idx = Math.abs(hash) % TODAY_QUOTES.length;
  return TODAY_QUOTES[idx];
}

function buildViewModel(
  data: {
    greeting: string;
    date: string;
    focus: DashboardFocus | null;
    recommendations: DashboardRecommendations;
    activities: { items: DashboardActivity[] };
    today: { quote_enabled: boolean; memory_pulse: string | null };
  },
  continueContext: ContinueContext | null,
): TodayViewModel {
  const { greeting, date, focus, recommendations, activities, today } = data;
  const { suggestion, urgent, building, new_topic } = recommendations;

  // ── Observation：一段叙事（对齐 Vision preview.html Narrative.todayObservation） ──
  const observation = buildObservation(
    activities.items,
    urgent,
    building,
    suggestion,
    continueContext,
  );

  // ── Focus Card ──
  const focusCard = buildFocusCard(focus, urgent, building, new_topic);

  // ── After Plan ──
  const topItem = urgent[0] ?? building[0] ?? new_topic[0];
  const afterPlan = buildAfterPlan(topItem);

  return {
    greeting,
    date,
    observation,
    focusCard,
    afterPlan,
    focusTitle: focus?.title || topItem?.label || "",
    quote: pickDailyQuote(date),
    quoteEnabled: today.quote_enabled,
    memoryPulse: today.memory_pulse,
  };
}

/**
 * 构建「苹果果的观察」叙事文本。
 *
 * 对齐 Vision preview.html (行 515-537) Narrative.todayObservation：
 *   - return (welcome_back)：好久不见 + 上次在学 X
 *   - 新朋友 / sessionsDone≤2：刚接触，从这里继续吗？
 *   - 刚开始 (mastery<0.4)：新朋友，慢慢来
 *   - 正在巩固 / 比较熟了 (mastery<0.7)：又近一步，继续巩固吗？
 *   - 很稳 (mastery≥0.7)：很稳了，往深走一步？
 *
 * 后端 topic_status 5 档：新朋友 / 刚开始 / 正在巩固 / 比较熟了 / 很稳。
 */
function buildObservation(
  activities: DashboardActivity[],
  urgent: { label: string }[],
  building: { label: string }[],
  suggestion: string,
  continueContext: ContinueContext | null,
): string {
  const parts: string[] = [];

  // ── 1. return（welcome_back）专用叙事：好久不见 ──
  // Vision 行 520-522：`好久不见。上次我们在学 X。我一直在这里。`
  if (continueContext?.type === "welcome_back") {
    const lastTitle = continueContext.title || "上次的内容";
    parts.push(`好久不见。上次我们在学「${lastTitle}」。我一直在这里。`);
    return parts.join("");
  }

  // ── 2. 昨天回顾（若能说人话） ──
  const completed = activities.filter((a) => a.status === "completed").slice(0, 3);
  if (completed.length === 1) {
    parts.push(`昨天我们一起完成了「${completed[0].title}」。`);
  } else if (completed.length === 2) {
    parts.push(`昨天我们一起完成了「${completed[0].title}」和「${completed[1].title}」。`);
  } else if (completed.length >= 3) {
    parts.push(
      `昨天我们一起完成了三件事：「${completed[0].title}」、「${completed[1].title}」和「${completed[2].title}」。`,
    );
  }

  // ── 3. 按 topic_status 分档生成「苹果果的发现」（对齐 Vision mastery 分档） ──
  const topicTitle =
    continueContext?.type === "yesterday"
      ? continueContext.title
      : (urgent[0]?.label ?? building[0]?.label);

  const topicStatus = continueContext?.topic_status;
  const discovery = buildDiscoveryByMastery(topicStatus, topicTitle, urgent, building, suggestion);

  if (discovery) {
    parts.push(discovery);
  }

  // ── 4. 如果什么都没有，给一个温和的开场 ──
  if (parts.length === 0) {
    parts.push("我还在慢慢了解你的学习节奏。完成几次学习后，我会更清楚你适合什么。");
  }

  return parts.join("");
}

/**
 * 按 mastery 分档生成「苹果果的发现」叙事。
 * 对齐 Vision preview.html (行 527-536)。
 */
function buildDiscoveryByMastery(
  topicStatus: string | undefined,
  topicTitle: string | undefined,
  urgent: { label: string }[],
  building: { label: string }[],
  suggestion: string,
): string | null {
  const topic = topicTitle || "";

  // 有 topic_status：按 Vision 5 档分档
  if (topicStatus && topic) {
    switch (topicStatus) {
      // Vision 行 527-528：sessionsDone≤2 → 刚接触
      case "新朋友":
        return `昨天我们刚一起接触了「${topic}」。今天从这里继续吗？`;
      // Vision 行 530-531：mastery<0.4 → 新朋友，慢慢来
      case "刚开始":
        return `昨天我们一起开始了「${topic}」。这是个新朋友，慢慢来。`;
      // Vision 行 533-534：mastery<0.7 → 又近一步，继续巩固？
      case "正在巩固":
      case "比较熟了":
        return `昨天你在「${topic}」上又近了一步。今天继续巩固吗？`;
      // Vision 行 536：mastery≥0.7 → 很稳了，往深走？
      case "很稳":
        return `昨天你又练了「${topic}」，已经很稳了。今天往深走一步？`;
      default:
        break;
    }
  }

  // 无 topic_status 兜底：用 urgent/building 维度
  if (urgent.length > 0 && building.length > 0) {
    return `我注意到你在「${building[0].label}」上进步很快，「${urgent[0].label}」还需要再巩固一下。`;
  }
  if (urgent.length > 0) {
    return `我注意到「${urgent[0].label}」是你当前最值得突破的方向。`;
  }
  if (building.length > 0) {
    return `我注意到你在「${building[0].label}」上正在稳步前进。`;
  }
  if (suggestion) {
    return suggestion;
  }
  return null;
}

/** 构建聚焦卡片 */
function buildFocusCard(
  focus: DashboardFocus | null,
  urgent: { label: string; subject?: string; p_known?: number }[],
  building: { label: string; subject?: string; p_known?: number }[],
  new_topic: { label: string; subject?: string; p_known?: number }[],
): TodayViewModel["focusCard"] {
  if (focus && focus.title) {
    return {
      title: focus.title,
      description: focus.description || "",
      estimatedMinutes: focus.estimated_minutes || 25,
    };
  }

  const item = urgent[0] ?? building[0] ?? new_topic[0];
  if (!item) return null;

  const subjectHint = item.subject ? `（${item.subject}）` : "";
  return {
    title: `${item.label}${subjectHint}`,
    description: "",
    estimatedMinutes: 25,
  };
}

/** 构建「做完以后」叙事 */
function buildAfterPlan(item: { label: string; p_known?: number } | undefined): string {
  if (!item) return "完成今天的练习后，我对你的了解会更准确。";
  const pKnown = item.p_known ?? 0;
  if (pKnown > 0.6) {
    return `做完以后，你对「${item.label}」的理解会更深入，距离熟练掌握就更近一步了。`;
  }
  return `做完以后，你对「${item.label}」的理解会比现在更扎实。`;
}

// ── 今日名言 ─────────────────────────────────────────────

function TodayQuote({ text }: { text: string }) {
  return (
    <p
      className="text-center text-sm italic text-ink-muted mb-4 leading-relaxed"
      style={{ fontFamily: "var(--font-display)" }}
    >
      「{text}」
    </p>
  );
}

// ── 记忆脉冲：又懂你一点 ─────────────────────────────────

function MemoryPulse({ text }: { text: string }) {
  return (
    <div
      className="mb-5 p-3 rounded-lg bg-accent-soft border-l-2 border-accent flex items-start gap-3"
      style={{ animation: 'msgIn .4s cubic-bezier(0.34, 1.56, 0.64, 1)' }}
    >
      <div className="text-lg leading-none mt-0.5">🍎</div>
      <p className="text-sm text-ink-secondary leading-relaxed">{text}</p>
    </div>
  );
}

// ── 快捷工具托盘 ─────────────────────────────────────────

function TodayTools() {
  const router = useRouter();
  const tools = [
    {
      icon: "🧠",
      label: "复习卡片",
      desc: "3 张待复习",
      bg: "bg-violet-500/15",
      onClick: () => router.push("/flashcard/review"),
    },
    {
      icon: "📖",
      label: "继续阅读",
      desc: "继续上次阅读",
      bg: "bg-teal-500/15",
      onClick: () => router.push("/reading"),
    },
    {
      icon: "🗣️",
      label: "练口语",
      desc: "10 分钟房间",
      bg: "bg-pink-500/15",
      onClick: () => router.push("/liveroom"),
    },
  ];

  return (
    <div className="flex gap-3 overflow-x-auto pb-2 mb-6 -mx-1 px-1">
      {tools.map((tool) => (
        <button
          key={tool.label}
          onClick={tool.onClick}
          className="flex items-center gap-2.5 bg-surface border border-divider rounded-xl px-3 py-2.5 flex-shrink-0 transition-colors hover:bg-surface-hover"
        >
          <div
            className={`w-9 h-9 rounded-lg ${tool.bg} flex items-center justify-center text-base`}
          >
            {tool.icon}
          </div>
          <div className="text-left">
            <strong className="block text-xs font-semibold text-ink-primary">
              {tool.label}
            </strong>
            <span className="text-[10px] text-ink-muted">{tool.desc}</span>
          </div>
        </button>
      ))}
    </div>
  );
}

// ── 新用户欢迎页 ─────────────────────────────────────────

function WelcomeHero({
  quote,
  quoteEnabled,
  onStart,
  creating,
}: {
  quote: string;
  quoteEnabled: boolean;
  onStart: () => void;
  creating: boolean;
}) {
  return (
    <div className="max-w-lg mx-auto px-4 py-12 sm:py-16 text-center animate-fadeIn">
      {quoteEnabled && <TodayQuote text={quote} />}
      <span className="text-5xl mb-5 block">🍎</span>
      <h1 className="text-2xl font-bold text-ink-primary mb-3">
        欢迎来到苹果果
      </h1>
      <p className="text-sm text-ink-secondary max-w-xs mx-auto mb-8 leading-relaxed">
        我是你的 AI 学习伙伴。开始第一次学习后，我会越来越了解你。
      </p>
      <Button
        variant="primary"
        size="lg"
        disabled={creating}
        onClick={onStart}
        className="text-base px-10 py-3 rounded-full shadow-md"
      >
        {creating ? (
          <>
            <Loader2 size={18} className="animate-spin" />
            正在准备...
          </>
        ) : (
          <>
            开始第一次学习
            <ArrowRight size={18} />
          </>
        )}
      </Button>
    </div>
  );
}

// ── 加载骨架屏 ────────────────────────────────────────────

function TodaySkeleton() {
  return (
    <div className="max-w-lg mx-auto space-y-5 px-4 py-10">
      <Skeleton variant="title" className="w-40 mb-2" />
      <Skeleton variant="text" className="w-24" />
      <div className="pt-2 space-y-2">
        <Skeleton variant="text" className="w-full" />
        <Skeleton variant="text" className="w-3/4" />
      </div>
      <Skeleton variant="card" className="h-28 mt-4" />
      <Skeleton variant="text" className="w-2/3 mt-2" />
      <div className="flex justify-center pt-4">
        <Skeleton variant="button" className="w-40 h-12" />
      </div>
    </div>
  );
}

// ── 主组件 ────────────────────────────────────────────────

export default function TodayPage() {
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [activeSession, setActiveSession] = useState<ActiveSession | null>(null);
  const [checkingActive, setCheckingActive] = useState(true);
  const [continueContext, setContinueContext] = useState<ContinueContext | null>(null);
  const [continueDismissed, setContinueDismissed] = useState(false);
  const [checkingContinue, setCheckingContinue] = useState(true);
  const { data, loading, error, refetch } = useSecretaryDashboard();

  // ── 拉取进行中的 Session（S1.2 / S1.3） ──
  useEffect(() => {
    let mounted = true;
    authedFetch("/api/session/active")
      .then(async (res) => {
        if (!res.ok) return;
        const list: ActiveSession[] = await res.json();
        const active = list.find(
          (s) => s.status !== "completed" && s.status !== "cancelled",
        );
        if (mounted) setActiveSession(active || null);
      })
      .catch(() => {})
      .finally(() => {
        if (mounted) setCheckingActive(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  // ── 拉取「继续昨天」上下文（S2.1） ──
  useEffect(() => {
    let mounted = true;
    authedFetch("/api/session/continue")
      .then(async (res) => {
        if (!res.ok) return;
        const ctx: ContinueContext = await res.json();
        if (mounted) setContinueContext(ctx.type !== "none" ? ctx : null);
      })
      .catch(() => {})
      .finally(() => {
        if (mounted) setCheckingContinue(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  // ── 创建 Session 的通用 handler ──
  const handleCreateSession = useCallback(
    async (params: { title: string; focus: string; goal: string; estimatedMinutes: number; source?: string }) => {
      setCreateError(null);
      setCreating(true);
      try {
        const res = await authedFetch("/api/session", {
          method: "POST",
          body: JSON.stringify({
            title: params.title,
            focus: params.focus,
            goal: params.goal,
            estimated_minutes: params.estimatedMinutes,
            source: params.source || "",
          }),
        });
        if (!res.ok) {
          const text = await res.text().catch(() => "");
          setCreateError("今天没能顺利开始，我们再试一次。");
          console.error("Create session failed:", res.status, text);
          return;
        }
        const json = await res.json();
        router.push(`/session/${json.session_id}`);
      } catch (e) {
        setCreateError("好像网络不太好，我们再试一次。");
        console.error("Create session error:", e);
      } finally {
        setCreating(false);
      }
    },
    [router],
  );

  // ── Loading ──
  if (loading || checkingActive || checkingContinue) return <TodaySkeleton />;

  // ── Error ──
  if (error) {
    return (
      <div className="max-w-lg mx-auto px-4 py-10">
        <ErrorState
          title="加载失败"
          message="无法获取今日学习建议，请稍后重试。"
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const todayDateStr = new Date().toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });

  // ── 新用户：没有学习历史且无进行/回归上下文 ──
  const hasHistory = data ? data.activities.items.length > 0 : false;
  const isNewUser = !hasHistory && !activeSession && !continueContext;
  if (isNewUser) {
    return (
      <WelcomeHero
        quote={pickDailyQuote(todayDateStr)}
        quoteEnabled={data?.today.quote_enabled ?? true}
        onStart={() =>
          handleCreateSession({
            title: "",
            focus: "",
            goal: "",
            estimatedMinutes: 25,
          })
        }
        creating={creating}
      />
    );
  }

  if (!data) {
    return (
      <div className="max-w-lg mx-auto px-4 py-10">
        <ErrorState
          title="加载失败"
          message="无法获取今日学习建议，请稍后重试。"
          onRetry={() => refetch()}
        />
      </div>
    );
  }

  const vm = buildViewModel(data, continueContext);
  const hasFocus = vm.focusCard !== null;

  return (
    <div className="max-w-lg mx-auto px-4 py-8 sm:py-10">

      {/* ── 今日名言 ── */}
      {vm.quoteEnabled && <TodayQuote text={vm.quote} />}

      {/* ── 问候 ── */}
      <div className="mb-6">
        <h1 className="text-3xl sm:text-4xl font-bold text-ink-primary mb-1">
          🍎 {vm.greeting}
        </h1>
        <p className="text-sm text-ink-muted">{vm.date}</p>
      </div>

      {/* ── 苹果果的观察（一段叙事） ── */}
      <p className="text-sm leading-relaxed text-ink-secondary mb-6">
        {vm.observation}
      </p>

      {/* ── 记忆脉冲（仅在非 activeSession 时展示，学完后才出现） ── */}
      {vm.memoryPulse && !activeSession && <MemoryPulse text={vm.memoryPulse} />}

      {activeSession ? (
        /* ── 有未完成的 Session：主 CTA 为继续（S1.2 / S1.3） ── */
        <>
          <div className="mb-6 p-5 rounded-xl bg-surface border border-border/60">
            <p className="text-xs text-ink-muted mb-2">进行中的学习</p>
            <h2 className="text-lg font-semibold text-ink-primary mb-4">
              {activeSession.title || "学习 Session"}
            </h2>

            <div className="flex flex-col items-start gap-3">
              <Button
                variant="primary"
                size="lg"
                onClick={() => router.push(`/session/${activeSession.id}`)}
                className="text-base px-6 py-3 rounded-full shadow-md"
              >
                <Play size={18} />
                继续学习
              </Button>
              <button
                onClick={() => {
                  const c = continueContext;
                  const title = c?.type === "yesterday" && c.title ? `继续：${c.title}` : vm.focusTitle || "";
                  handleCreateSession({
                    title,
                    focus: vm.focusTitle || "",
                    goal: c?.type === "yesterday" ? (c as any).reflection_snippet || c?.key_takeaways?.join("\n") || "" : vm.focusCard?.description || "",
                    estimatedMinutes: vm.focusCard?.estimatedMinutes || 25,
                  });
                }}
                className="text-xs text-ink-muted hover:text-ink-secondary transition-colors"
              >
                今天想学点别的
              </button>
              {createError && (
                <p className="text-xs text-red-500">{createError}</p>
              )}
            </div>
          </div>

          {/* 工具托盘在页面级别（对齐 Vision preview.html） */}
          <TodayTools />
        </>
      ) : continueContext?.type === "welcome_back" && !continueDismissed ? (
        /* ── 欢迎回来（≥3天未学）：三段式布局 ── */
        <>
          <div className="mb-6 p-5 rounded-xl bg-surface border border-border/60 relative">
            <button
              onClick={() => setContinueDismissed(true)}
              className="absolute top-4 right-4 text-xs text-ink-muted hover:text-ink-secondary transition-colors"
              aria-label="关闭"
            >
              ✕
            </button>
            <p className="text-xs text-ink-muted mb-1.5">上次的学习</p>
            <h2 className="text-lg font-semibold text-ink-primary mb-2">
              {continueContext.title || "一次学习"}
            </h2>
            {continueContext.key_takeaways?.[0] && (
              <p className="text-xs text-ink-muted mb-1">{continueContext.key_takeaways[0]}</p>
            )}
            {continueContext.topic_status && (
              <p className="text-xs text-ink-muted">
                苹果果对你的理解：{continueContext.topic_status}
              </p>
            )}
          </div>
          <div className="mb-6">
            <TodayTools />
          </div>
          <div className="flex flex-col items-center gap-2 mb-6">
            <Button
              variant="primary"
              size="lg"
              disabled={creating}
              onClick={() =>
                handleCreateSession({
                  title: `继续：${continueContext.title || ""}`,
                  focus: continueContext.title || "",
                  goal: continueContext.key_takeaways?.join("\n") || continueContext.reflection_snippet || "",
                  estimatedMinutes: 25,
                  source: "welcome_back",
                })
              }
              className="text-base px-10 py-3 rounded-full shadow-md"
            >
              {creating ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  正在准备...
                </>
              ) : (
                <>
                  <Play size={18} />
                  从这里继续
                </>
              )}
            </Button>
            <button
              onClick={() =>
                handleCreateSession({
                  title: "",
                  focus: "",
                  goal: "",
                  estimatedMinutes: 25,
                })
              }
              className="text-xs text-ink-muted hover:text-ink-secondary transition-colors"
            >
              换个方向
            </button>
            {createError && (
              <p className="text-xs text-red-500 mt-1">{createError}</p>
            )}
          </div>
        </>
      ) : continueContext?.type === "yesterday" && !continueDismissed ? (
        /* ── 昨日学习：三段式布局（对齐 Vision） ── */
        <>
          {/* 段1: 昨日卡片 — 严格三行 label / title / 理解 */}
          <div className="mb-6 p-5 rounded-xl bg-surface border border-border/60 relative">
            <button
              onClick={() => setContinueDismissed(true)}
              className="absolute top-4 right-4 text-xs text-ink-muted hover:text-ink-secondary transition-colors"
              aria-label="关闭"
            >
              ✕
            </button>
            <p className="text-xs text-ink-muted mb-1.5">
              {continueContext.date_label}的学习
            </p>
            <h2 className="text-lg font-semibold text-ink-primary mb-2">
              {continueContext.title || "一次学习"}
            </h2>
            {continueContext.topic_status && (
              <p className="text-xs text-ink-muted">
                苹果果对你的理解：{continueContext.topic_status}
              </p>
            )}
          </div>

          {/* 段2: 工具托盘 */}
          <div className="mb-6">
            <TodayTools />
          </div>

          {/* 段3: CTA */}
          <div className="flex flex-col items-center gap-2 mb-6">
            <Button
              variant="primary"
              size="lg"
              disabled={creating}
              onClick={() =>
                handleCreateSession({
                  title: `继续：${continueContext.title || ""}`,
                  focus: continueContext.title || "",
                  goal:
                    continueContext.key_takeaways?.join("\n") ||
                    continueContext.reflection_snippet ||
                    "",
                  estimatedMinutes: 25,
                })
              }
              className="text-base px-10 py-3 rounded-full shadow-md"
            >
              {creating ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  正在准备...
                </>
              ) : (
                <>
                  <Play size={18} />
                  继续昨天
                </>
              )}
            </Button>
            <button
              onClick={() =>
                handleCreateSession({
                  title: vm.focusTitle || "",
                  focus: vm.focusTitle || "",
                  goal: vm.focusCard?.description || "",
                  estimatedMinutes: vm.focusCard?.estimatedMinutes || 25,
                })
              }
              className="text-xs text-ink-muted hover:text-ink-secondary transition-colors"
            >
              今天想学点别的
            </button>
            {createError && (
              <p className="text-xs text-red-500 mt-1">{createError}</p>
            )}
          </div>
        </>
      ) : hasFocus ? (
        <>
          {/* ── 今天想带你做的 ── */}
          <p className="text-sm text-ink-secondary mb-3">
            今天我想带你一起：
          </p>

          <div className="mb-6 p-5 rounded-xl bg-surface border border-border/60">
            <h2 className="text-lg font-semibold text-ink-primary mb-1">
              {vm.focusCard!.title}
            </h2>
            {vm.focusCard!.description && (
              <p className="text-sm text-ink-secondary mb-3">
                {vm.focusCard!.description}
              </p>
            )}
            {vm.focusCard!.estimatedMinutes > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-ink-muted">
                <Clock size={13} />
                <span>大概需要 {vm.focusCard!.estimatedMinutes} 分钟</span>
              </div>
            )}
          </div>

          {/* ── 做完以后 ── */}
          {vm.afterPlan && (
            <p className="text-sm text-ink-secondary mb-8">
              {vm.afterPlan}
            </p>
          )}

          <TodayTools />

          {/* ── CTA ── */}
          <div className="flex flex-col items-center gap-2">
            <Button
              variant="primary"
              size="lg"
              disabled={creating}
              onClick={() =>
                handleCreateSession({
                  title: vm.focusTitle || "",
                  focus: vm.focusTitle || "",
                  goal: vm.focusCard?.description || "",
                  estimatedMinutes: vm.focusCard?.estimatedMinutes || 25,
                })
              }
              className="text-base px-10 py-3 rounded-full shadow-md"
            >
              {creating ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  正在准备今天...
                </>
              ) : (
                <>
                  开始今天
                  <ArrowRight size={18} />
                </>
              )}
            </Button>
            {vm.focusCard && vm.focusCard.estimatedMinutes > 0 && (
              <p className="text-xs text-ink-muted">
                不用一次学完
              </p>
            )}
            {createError && (
              <p className="text-xs text-red-500 mt-1">{createError}</p>
            )}
          </div>
        </>
      ) : (
        /* ── 无焦点卡片时：简单提示 ── */
        <div className="text-center pt-8">
          <p className="text-sm text-ink-secondary mb-6">
            我还在准备今天的学习计划。先开始一次自由学习吧。
          </p>
          <Button
            variant="primary"
            size="lg"
            disabled={creating}
            onClick={() =>
              handleCreateSession({
                title: "",
                focus: "",
                goal: "",
                estimatedMinutes: 25,
              })
            }
            className="text-base px-10 py-3 rounded-full shadow-md"
          >
            {creating ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                正在准备今天...
              </>
            ) : (
              <>
                开始学习
                <ArrowRight size={18} />
              </>
            )}
          </Button>
          {createError && (
            <p className="text-xs text-red-500 mt-3">{createError}</p>
          )}
        </div>
      )}
    </div>
  );
}

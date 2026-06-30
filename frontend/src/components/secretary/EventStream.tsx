"use client";

import {
  MessageSquare, Target, Brain, Bell, Settings, Activity,
  RefreshCw, ChevronDown, ChevronRight,
  Clock, Search, Filter, X, BarChart3, Layers, List,
  AlertCircle, Loader2,
} from "lucide-react";
import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useCurrentUserId } from "@/hooks/useCurrentUserId";
import { authedFetch } from "@/lib/api/api";

// ══════════════════════════════════════════════════════════════
//  Types
// ══════════════════════════════════════════════════════════════

interface EventItem {
  id: string;
  user_id: string;
  event_type: string;
  stream_type: string;
  stream_id: string;
  source_type: string;
  source_id: string;
  parent_event_id: string;
  correlation_id: string;
  status: string;
  status_msg: string;
  payload: Record<string, unknown>;
  summary: string;
  importance: number;
  child_count?: number;
  embedding: number[] | null;
  created_at: number | string;
  updated_ats: number[];
}

interface EventSummary {
  total_events: number;
  counts: Record<string, number>;
  last_active: number;
  recent_24h: number;
}

// ══════════════════════════════════════════════════════════════
//  Constants
// ══════════════════════════════════════════════════════════════

const STREAM_TYPE_CONFIG: Record<string, { label: string; icon: typeof Activity; color: string }> = {
  conversation: { label: "对话", icon: MessageSquare, color: "text-blue-500 bg-blue-500/10" },
  practice:    { label: "练习", icon: Target,          color: "text-emerald-500 bg-emerald-500/10" },
  knowledge:   { label: "知识树", icon: Brain,          color: "text-purple-500 bg-purple-500/10" },
  secretary:   { label: "秘书", icon: Bell,            color: "text-amber-500 bg-amber-500/10" },
  system:      { label: "系统", icon: Settings,        color: "text-slate-500 bg-slate-500/10" },
  aggregate:   { label: "聚合", icon: Layers,          color: "text-rose-500 bg-rose-500/10" },
};

const EVENT_TYPE_CONFIG: Record<string, { label: string; color: string; bg: string; ring: string }> = {
  AssistantReplied:        { label: "AI 回复",   color: "text-blue-500",     bg: "bg-blue-500/10",     ring: "ring-blue-500/30" },
  AnswerSubmitted:         { label: "答题",       color: "text-emerald-500",  bg: "bg-emerald-500/10",  ring: "ring-emerald-500/30" },
  SessionCompleted:        { label: "会话完成",   color: "text-purple-500",   bg: "bg-purple-500/10",   ring: "ring-purple-500/30" },
  CognitiveNodeUpdated:    { label: "知识更新",   color: "text-orange-500",   bg: "bg-orange-500/10",   ring: "ring-orange-500/30" },
  NodeCreated:             { label: "节点创建",   color: "text-teal-500",     bg: "bg-teal-500/10",     ring: "ring-teal-500/30" },
  EpisodeDigest:           { label: "学习片段",   color: "text-indigo-500",   bg: "bg-indigo-500/10",   ring: "ring-indigo-500/30" },
  TopicDigest:             { label: "主题摘要",   color: "text-violet-500",   bg: "bg-violet-500/10",   ring: "ring-violet-500/30" },
  TypeDigest:              { label: "类型摘要",   color: "text-sky-500",      bg: "bg-sky-500/10",      ring: "ring-sky-500/30" },
  PracticeSessionSummary:  { label: "练习总结",   color: "text-pink-500",     bg: "bg-pink-500/10",     ring: "ring-pink-500/30" },
  DailyDigest:             { label: "日报",       color: "text-amber-500",    bg: "bg-amber-500/10",    ring: "ring-amber-500/30" },
  ErrorRecorded:           { label: "错题记录",   color: "text-red-500",      bg: "bg-red-500/10",      ring: "ring-red-500/30" },
  MessageClassified:       { label: "消息分类",   color: "text-cyan-500",     bg: "bg-cyan-500/10",     ring: "ring-cyan-500/30" },
  ProposalAccepted:        { label: "提案采纳",   color: "text-lime-500",     bg: "bg-lime-500/10",     ring: "ring-lime-500/30" },
};

const STREAM_TYPE_OPTIONS = [
  { value: "", label: "全部类型" },
  ...Object.entries(STREAM_TYPE_CONFIG).map(([k, v]) => ({ value: k, label: v.label })),
];

const EVENT_TYPE_OPTIONS = [
  { value: "", label: "全部事件" },
  ...Object.entries(EVENT_TYPE_CONFIG).map(([k, v]) => ({ value: k, label: v.label })),
];

const TIME_RANGE_OPTIONS = [
  { value: 0, label: "全部时间" },
  { value: 3600, label: "最近 1 小时" },
  { value: 86400, label: "最近 24 小时" },
  { value: 604800, label: "最近 7 天" },
];

const DIMENSION_OPTIONS = [
  { value: "", label: "全部维度" },
  { value: "mixed", label: "时间线" },
  { value: "topic", label: "按主题" },
  { value: "type", label: "按类型" },
];

type ViewMode = "raw" | "aggregated";

// ══════════════════════════════════════════════════════════════
//  Helpers
// ══════════════════════════════════════════════════════════════

function parseTimestamp(ts: number | string): number {
  if (typeof ts === "number") return ts * 1000;
  // ISO string or other
  const d = new Date(ts);
  return isNaN(d.getTime()) ? 0 : d.getTime();
}

function formatTime(ts: number | string): string {
  const ms = parseTimestamp(ts);
  if (!ms) return "";
  const now = Date.now();
  const diffMs = now - ms;
  const diffMin = Math.floor(diffMs / 60000);
  const diffH = Math.floor(diffMs / 3600000);

  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin} 分钟前`;
  if (diffH < 24) return `${diffH} 小时前`;

  const d = new Date(ms);
  const pad = (n: number) => String(n).padStart(2, "0");
  const mm = pad(d.getMonth() + 1);
  const dd = pad(d.getDate());
  const hh = pad(d.getHours());
  const mi = pad(d.getMinutes());
  if (d.getFullYear() === new Date().getFullYear()) {
    return `${mm}-${dd} ${hh}:${mi}`;
  }
  return `${d.getFullYear()}-${mm}-${dd} ${hh}:${mi}`;
}

function getEventBrief(event: EventItem): string {
  if (event.summary) return event.summary;
  const p = event.payload;
  switch (event.event_type) {
    case "AnswerSubmitted":
      return `答题${p.is_correct ? "\u2713" : "\u2717"} ${(p.skill_id as string) || ""}`;
    case "AssistantReplied": {
      const c = (p.content as string) || "";
      return c.length > 80 ? c.slice(0, 80) + "..." : c;
    }
    case "SessionCompleted":
      return `练习完成 准确率 ${typeof p.accuracy === "number" ? Math.round(p.accuracy * 100) + "%" : "\u2014"}`;
    case "CognitiveNodeUpdated":
      return `知识更新 ${(p.label as string) || ""}`;
    case "NodeCreated":
      return `创建节点 ${(p.label as string) || ""}`;
    case "EpisodeDigest":
    case "TopicDigest":
    case "TypeDigest": {
      const childCount = (p.child_count as number) || 0;
      const dim = (p.dimension as string) || "";
      const topic = (p.topic_label as string) || (p.type_label as string) || "";
      return `${dim === "topic" ? topic : dim === "type" ? topic : "学习片段"} ${childCount}条`;
    }
    case "PracticeSessionSummary":
      return `${(p.total_questions as number) || 0}题 正确${(p.correct_count as number) || 0}`;
    case "DailyDigest":
      return `日报 ${(p.date as string) || ""}`;
    case "ErrorRecorded":
      return `错题 ${(p.skill_id as string) || ""}`;
    default:
      return event.event_type;
  }
}

// ══════════════════════════════════════════════════════════════
//  Skeleton
// ══════════════════════════════════════════════════════════════

function Skeleton({ count = 5 }: { count?: number }) {
  return (
    <div className="relative pl-6 border-l-2 border-[var(--color-border)] ml-2 space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="relative pb-1 animate-pulse">
          <div className="absolute -left-[25px] top-1.5 w-3 h-3 rounded-full bg-[var(--color-border)]" />
          <div className="p-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] space-y-2">
            <div className="flex items-center gap-2">
              <div className="w-5 h-5 rounded bg-[var(--color-bg-tertiary)]" />
              <div className="h-3 w-16 rounded bg-[var(--color-bg-tertiary)]" />
              <div className="h-3 w-12 rounded bg-[var(--color-bg-tertiary)]" />
            </div>
            <div className="h-4 w-3/4 rounded bg-[var(--color-bg-tertiary)]" />
            <div className="h-3 w-24 rounded bg-[var(--color-bg-tertiary)]" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
//  StatCard
// ══════════════════════════════════════════════════════════════

function StatCard({ icon: Icon, value, label, color }: {
  icon: typeof Activity; value: string | number; label: string; color: string;
}) {
  return (
    <div className="p-3 rounded-lg bg-[var(--color-bg-tertiary)]">
      <Icon size={14} className={color} />
      <div className="text-lg font-semibold text-[var(--color-text)] mt-1">{value}</div>
      <div className="text-[10px] text-[var(--color-text-muted)]">{label}</div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
//  EventTimelineItem
// ══════════════════════════════════════════════════════════════

function EventTimelineItem({
  event,
  viewMode,
  isExpanded,
  childEvents,
  isLoadingChildren,
  onToggleExpand,
}: {
  event: EventItem;
  viewMode: ViewMode;
  isExpanded: boolean;
  childEvents: EventItem[];
  isLoadingChildren: boolean;
  onToggleExpand: () => void;
}) {
  const streamCfg = STREAM_TYPE_CONFIG[event.stream_type] || STREAM_TYPE_CONFIG.system;
  const eventCfg = EVENT_TYPE_CONFIG[event.event_type];
  const StreamIcon = streamCfg.icon;
  const brief = getEventBrief(event);
  const childCount = event.child_count ?? (event.payload?.child_count as number) ?? 0;
  const hasChildren = childCount > 0;

  return (
    <div className="relative pb-1 group">
      {/* 时间线圆点 */}
      <div
        className={`absolute -left-[25px] top-1.5 w-3 h-3 rounded-full border-2 border-[var(--color-bg)] ${
          eventCfg?.bg || "bg-slate-500/10"
        } ring-2 ${eventCfg?.ring || "ring-slate-500/30"}`}
      />

      {/* 事件卡片 */}
      <div className="p-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] hover:border-[var(--color-border-hover)] transition-colors mb-1">
        <div className="flex items-start gap-2">
          {/* 图标 */}
          <div className={`p-1 rounded ${streamCfg.color} flex-shrink-0`}>
            <StreamIcon size={12} />
          </div>

          <div className="flex-1 min-w-0">
            {/* 标签行 */}
            <div className="flex items-center gap-1.5 flex-wrap mb-1">
              {eventCfg ? (
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${eventCfg.bg} ${eventCfg.color}`}>
                  {eventCfg.label}
                </span>
              ) : (
                <span className="text-[10px] px-1.5 py-0.5 rounded font-medium bg-slate-500/10 text-slate-500">
                  {event.event_type}
                </span>
              )}

              <span className="text-[10px] text-[var(--color-text-tertiary)]">
                {streamCfg.label}
              </span>

              {viewMode === "aggregated" && hasChildren && (
                <span className="text-[10px] px-1 rounded bg-[var(--color-bg-tertiary)] text-[var(--color-text-muted)]">
                  {childCount}条
                </span>
              )}

              {event.importance > 0.5 && (
                <span className="text-[10px] px-1 rounded bg-amber-500/10 text-amber-500">
                  {"\u2605"} {Math.round(event.importance * 100)}%
                </span>
              )}
            </div>

            {/* 摘要内容 */}
            <button
              onClick={onToggleExpand}
              className="text-xs text-[var(--color-text-secondary)] text-left hover:text-[var(--color-text)] transition-colors line-clamp-2 w-full"
            >
              {brief}
            </button>

            {/* 时间 */}
            <div className="flex items-center gap-1 mt-1.5 text-[10px] text-[var(--color-text-tertiary)]">
              <Clock size={10} />
              {formatTime(event.created_at)}
            </div>
          </div>

          {/* 展开按钮 */}
          {(hasChildren || viewMode === "raw") && (
            <button
              onClick={onToggleExpand}
              className="flex-shrink-0 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-muted)] transition-colors mt-0.5"
            >
              {isLoadingChildren ? (
                <Loader2 size={14} className="animate-spin" />
              ) : isExpanded ? (
                <ChevronDown size={14} />
              ) : (
                <ChevronRight size={14} />
              )}
            </button>
          )}
        </div>

        {/* 展开子节点 */}
        {isExpanded && (
          <>
            {viewMode === "aggregated" && childEvents.length > 0 && (
              <div className="mt-3 pt-3 border-t border-[var(--color-border)] space-y-1.5 ml-2">
                {childEvents.map((child) => (
                  <div
                    key={child.id}
                    className="flex items-start gap-2 p-2 rounded bg-[var(--color-bg-tertiary)] text-xs"
                  >
                    <span
                      className={`text-[10px] px-1 py-0.5 rounded font-medium flex-shrink-0 ${
                        (EVENT_TYPE_CONFIG[child.event_type]?.bg || "bg-slate-500/10")
                      } ${EVENT_TYPE_CONFIG[child.event_type]?.color || "text-slate-500"}`}
                    >
                      {EVENT_TYPE_CONFIG[child.event_type]?.label || child.event_type}
                    </span>
                    <span className="text-[var(--color-text-secondary)] line-clamp-2">
                      {getEventBrief(child)}
                    </span>
                    <span className="text-[10px] text-[var(--color-text-tertiary)] flex-shrink-0 ml-auto">
                      {formatTime(child.created_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {viewMode === "aggregated" && isLoadingChildren && (
              <div className="mt-3 pt-3 border-t border-[var(--color-border)] flex items-center justify-center py-2">
                <Loader2 size={14} className="animate-spin text-[var(--color-text-tertiary)]" />
              </div>
            )}

            {viewMode === "raw" && (
              <div className="mt-3 pt-3 border-t border-[var(--color-border)] space-y-2 text-xs">
                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[var(--color-text-tertiary)]">
                  <div>
                    <span className="text-[var(--color-text-muted)]">事件ID:</span>{" "}
                    <code className="text-[10px]">{event.id}</code>
                  </div>
                  <div>
                    <span className="text-[var(--color-text-muted)]">流ID:</span>{" "}
                    <code className="text-[10px]">{event.stream_id}</code>
                  </div>
                  {event.parent_event_id && (
                    <div className="col-span-2">
                      <span className="text-[var(--color-text-muted)]">父事件:</span>{" "}
                      <code className="text-[10px]">{event.parent_event_id}</code>
                    </div>
                  )}
                  {event.correlation_id && (
                    <div className="col-span-2">
                      <span className="text-[var(--color-text-muted)]">关联ID:</span>{" "}
                      <code className="text-[10px]">{event.correlation_id}</code>
                    </div>
                  )}
                </div>
                <details className="group">
                  <summary className="text-[var(--color-text-muted)] cursor-pointer hover:text-[var(--color-text)]">
                    Payload ({Object.keys(event.payload).length} 字段)
                  </summary>
                  <pre className="mt-1 p-2 rounded bg-[var(--color-bg-tertiary)] text-[10px] text-[var(--color-text-secondary)] overflow-x-auto max-h-40 overflow-y-auto">
                    {JSON.stringify(event.payload, null, 2)}
                  </pre>
                </details>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
//  Main Component
// ══════════════════════════════════════════════════════════════

export default function EventStream() {
  const userId = useCurrentUserId();

  // ── 状态 ──
  const [events, setEvents] = useState<EventItem[]>([]);
  const [summary, setSummary] = useState<EventSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 视图模式 (延迟读取 localStorage 避免 hydration mismatch)
  const [viewMode, setViewMode] = useState<ViewMode>("aggregated");
  const [dimension, setDimension] = useState("");
  const [hydrated, setHydrated] = useState(false);

  // 筛选
  const [filterStreamType, setFilterStreamType] = useState("");
  const [filterEventType, setFilterEventType] = useState("");
  const [filterTimeRange, setFilterTimeRange] = useState(0);
  const [searchText, setSearchText] = useState("");
  const [showFilters, setShowFilters] = useState(false);

  // 展开/折叠
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());
  const childrenMapRef = useRef<Record<string, EventItem[]>>({});
  const [childrenMap, setChildrenMap] = useState<Record<string, EventItem[]>>({});
  const [loadingChildren, setLoadingChildren] = useState<Set<string>>(new Set());

  // ── 客户端 hydration: 从 localStorage 恢复偏好 ──
  useEffect(() => {
    const saved = localStorage.getItem("event_stream_view");
    if (saved === "raw" || saved === "aggregated") setViewMode(saved);
    const savedDim = localStorage.getItem("event_stream_dimension");
    if (savedDim) setDimension(savedDim);
    setHydrated(true);
  }, []);

  // ── 持久化偏好 ──
  useEffect(() => {
    if (hydrated) localStorage.setItem("event_stream_view", viewMode);
  }, [viewMode, hydrated]);
  useEffect(() => {
    if (hydrated) localStorage.setItem("event_stream_dimension", dimension);
  }, [dimension, hydrated]);

  // ── 数据加载 ──
  const loadEvents = useCallback(async () => {
    if (!userId) return;
    setError(null);
    try {
      let evtRes: Response;

      if (viewMode === "aggregated") {
        const params = new URLSearchParams();
        params.set("user_id", userId);
        params.set("limit", "100");
        params.set("stream_type", "aggregate");
        if (dimension) params.set("dimension", dimension);
        evtRes = await authedFetch(`/api/secretary/events/top-level?${params.toString()}`);
      } else {
        const params = new URLSearchParams();
        params.set("user_id", userId);
        params.set("limit", "100");
        if (filterStreamType) params.set("stream_type", filterStreamType);
        if (filterEventType) params.set("event_type", filterEventType);
        if (filterTimeRange > 0) {
          params.set("since", String(Date.now() / 1000 - filterTimeRange));
        }
        evtRes = await authedFetch(`/api/secretary/events/stream?${params.toString()}`);
      }

      const sumRes = await authedFetch(`/api/secretary/events/summary?user_id=${userId}`);

      if (evtRes.ok) {
        const data: EventItem[] = await evtRes.json();
        setEvents(data);
      } else {
        setError("加载事件失败");
      }
      if (sumRes.ok) {
        const data: EventSummary = await sumRes.json();
        setSummary(data);
      }
    } catch (err) {
      setError("网络错误，请检查连接后重试");
      console.error("EventStream load failed:", err);
    }
  }, [userId, viewMode, dimension, filterStreamType, filterEventType, filterTimeRange]);

  useEffect(() => {
    if (!userId) return;
    setLoading(true);
    setExpandedIds(new Set());
    childrenMapRef.current = {};
    setChildrenMap({});
    loadEvents().finally(() => setLoading(false));
  }, [loadEvents, userId]);

  // 自动刷新 (30s)
  useEffect(() => {
    if (!userId) return;
    const interval = setInterval(() => {
      setRefreshing(true);
      loadEvents().finally(() => setRefreshing(false));
    }, 30000);
    return () => clearInterval(interval);
  }, [loadEvents, userId]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadEvents();
    setRefreshing(false);
  };

  // ── 加载子节点 (使用 ref 避免闭包陈旧) ──
  const loadChildren = useCallback(async (eventId: string) => {
    if (childrenMapRef.current[eventId]) return;
    setLoadingChildren((prev) => new Set(prev).add(eventId));
    try {
      const res = await authedFetch(`/api/secretary/events/${eventId}/children`);
      if (res.ok) {
        const data: EventItem[] = await res.json();
        childrenMapRef.current = { ...childrenMapRef.current, [eventId]: data };
        setChildrenMap((prev) => ({ ...prev, [eventId]: data }));
      }
    } catch (err) {
      console.error("Load children failed:", err);
    } finally {
      setLoadingChildren((prev) => {
        const next = new Set(prev);
        next.delete(eventId);
        return next;
      });
    }
  }, []);

  // ── 展开/折叠 ──
  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
        if (viewMode === "aggregated") {
          loadChildren(id);
        }
      }
      return next;
    });
  };

  // ── 筛选后的事件 ──
  const filteredEvents = useMemo(() => {
    if (!searchText) return events;
    const q = searchText.toLowerCase();
    return events.filter((e) => {
      const brief = getEventBrief(e).toLowerCase();
      return brief.includes(q) || e.event_type.toLowerCase().includes(q);
    });
  }, [events, searchText]);

  // ── 按流类型统计 ──
  const stats = useMemo(() => {
    const streamCounts: Record<string, number> = {};
    for (const e of filteredEvents) {
      streamCounts[e.stream_type] = (streamCounts[e.stream_type] || 0) + 1;
    }
    return streamCounts;
  }, [filteredEvents]);

  const hasFilters = filterStreamType || filterEventType || filterTimeRange > 0 || dimension;
  const hasResults = filteredEvents.length > 0;

  return (
    <div className="space-y-4">
      {/* ── 错误提示 ── */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg border border-red-500/20 bg-red-500/5 text-xs text-red-500">
          <AlertCircle size={14} />
          <span className="flex-1">{error}</span>
          <button
            onClick={handleRefresh}
            className="px-2 py-0.5 rounded border border-red-500/30 hover:bg-red-500/10 transition-colors"
          >
            重试
          </button>
        </div>
      )}

      {/* ── 摘要统计栏 ── */}
      {summary && !loading && (
        <div className="grid grid-cols-4 gap-3">
          <StatCard icon={Activity} value={summary.total_events} label="总事件数" color="text-blue-500" />
          <StatCard icon={BarChart3} value={summary.recent_24h} label="24h 事件" color="text-emerald-500" />
          <StatCard
            icon={MessageSquare}
            value={(summary.counts?.AssistantReplied || 0) + (summary.counts?.EpisodeDigest || 0)}
            label="对话事件"
            color="text-purple-500"
          />
          <StatCard
            icon={Target}
            value={(summary.counts?.AnswerSubmitted || 0) + (summary.counts?.SessionCompleted || 0)}
            label="练习事件"
            color="text-amber-500"
          />
        </div>
      )}

      {/* ── 工具栏 ── */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* 视图模式切换 */}
        <div className="flex items-center rounded border border-[var(--color-border)] overflow-hidden">
          <button
            onClick={() => setViewMode("raw")}
            className={`inline-flex items-center gap-1 px-2.5 py-1.5 text-xs transition-colors ${
              viewMode === "raw"
                ? "bg-[var(--color-accent)] text-white"
                : "bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            <List size={12} />
            原始流
          </button>
          <button
            onClick={() => setViewMode("aggregated")}
            className={`inline-flex items-center gap-1 px-2.5 py-1.5 text-xs transition-colors ${
              viewMode === "aggregated"
                ? "bg-[var(--color-accent)] text-white"
                : "bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            <Layers size={12} />
            聚合流
          </button>
        </div>

        {/* 维度切换 (仅聚合流) */}
        {viewMode === "aggregated" && (
          <select
            value={dimension}
            onChange={(e) => setDimension(e.target.value)}
            className="text-xs px-2 py-1.5 rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
          >
            {DIMENSION_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        )}

        {/* 筛选切换 (原始流) */}
        {viewMode === "raw" && (
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded border transition-colors ${
              showFilters || hasFilters
                ? "border-[var(--color-accent)] text-[var(--color-accent)] bg-[var(--color-accent)]/5"
                : "border-[var(--color-border)] text-[var(--color-text-muted)] bg-[var(--color-surface)]"
            }`}
          >
            <Filter size={12} />
            筛选{hasFilters ? ` (${filteredEvents.length})` : ""}
          </button>
        )}

        {/* 搜索 */}
        <div className="relative flex-1 min-w-[140px] max-w-[240px]">
          <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
          <input
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="搜索事件…"
            className="w-full text-xs pl-7 pr-2 py-1.5 rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] outline-none focus:border-[var(--color-accent)]"
          />
        </div>

        {/* 刷新 */}
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs text-[var(--color-text-muted)] bg-[var(--color-surface)] rounded border border-[var(--color-border)] hover:text-[var(--color-text)] transition-colors disabled:opacity-50"
        >
          <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
          刷新
        </button>

        {hasFilters && (
          <button
            onClick={() => {
              setFilterStreamType("");
              setFilterEventType("");
              setFilterTimeRange(0);
              setDimension("");
              setSearchText("");
            }}
            className="inline-flex items-center gap-1 px-2 py-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-error)] transition-colors"
          >
            <X size={12} />
            清除
          </button>
        )}
      </div>

      {/* ── 筛选面板 (仅原始流) ── */}
      {showFilters && viewMode === "raw" && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] flex-wrap">
          <select
            value={filterStreamType}
            onChange={(e) => setFilterStreamType(e.target.value)}
            className="text-xs px-2 py-1 rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
          >
            {STREAM_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          <select
            value={filterEventType}
            onChange={(e) => setFilterEventType(e.target.value)}
            className="text-xs px-2 py-1 rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
          >
            {EVENT_TYPE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>

          <select
            value={filterTimeRange}
            onChange={(e) => setFilterTimeRange(Number(e.target.value))}
            className="text-xs px-2 py-1 rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
          >
            {TIME_RANGE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      )}

      {/* ── 流类型快速统计 ── */}
      {hasResults && Object.keys(stats).length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          {Object.entries(stats).map(([key, count]) => {
            const cfg = STREAM_TYPE_CONFIG[key];
            if (!cfg) return null;
            const Icon = cfg.icon;
            return (
              <span
                key={key}
                className={`inline-flex items-center gap-1 px-2 py-0.5 text-[10px] rounded-full ${cfg.color}`}
              >
                <Icon size={10} />
                {cfg.label} {count}
              </span>
            );
          })}
        </div>
      )}

      {/* ── 事件列表 ── */}
      {loading ? (
        <Skeleton count={5} />
      ) : !hasResults ? (
        <div className="p-8 rounded-lg border border-dashed border-[var(--color-border)] text-center">
          <div className="text-sm text-[var(--color-text-muted)] mb-1">
            {hasFilters
              ? "没有匹配的事件，请调整筛选条件"
              : viewMode === "aggregated"
                ? "暂未生成聚合事件"
                : "暂未记录事件"}
          </div>
          <div className="text-xs text-[var(--color-text-tertiary)]">
            {hasFilters
              ? ""
              : "开始学习后，系统会自动记录和聚合事件"}
          </div>
        </div>
      ) : (
        <div className="relative pl-6 border-l-2 border-[var(--color-border)] space-y-0 ml-2">
          {filteredEvents.map((event) => (
            <EventTimelineItem
              key={event.id}
              event={event}
              viewMode={viewMode}
              isExpanded={expandedIds.has(event.id)}
              childEvents={childrenMap[event.id] || []}
              isLoadingChildren={loadingChildren.has(event.id)}
              onToggleExpand={() => toggleExpand(event.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
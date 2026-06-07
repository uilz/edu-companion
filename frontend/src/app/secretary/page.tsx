"use client";

import {
  Bell, Check, X, Clock, AlertTriangle, TrendingUp, Settings,
  MessageSquare, Search, ChevronDown, ChevronRight,
  RotateCcw, EyeOff, Timer,
} from "lucide-react";
import { useState, useEffect, useCallback, useMemo } from "react";
import { useNotificationStore } from "@/store/notification/notification-store";
import {
  snoozeNotification,
  dismissNotification,
} from "@/store/notification/notification-service";
import { navigateToProposal } from "@/store/notification/proposal-navigator";
import type {
  SecretaryNotification, PageType, ActionType, NotificationSource,
} from "@/store/notification/types";

// ══════════════════════════════════════════════════════════════
//  Constants
// ══════════════════════════════════════════════════════════════

const SOURCE_OPTIONS: { value: NotificationSource | ""; label: string }[] = [
  { value: "", label: "全部来源" },
  { value: "secretary", label: "秘书引擎" },
  { value: "context_switch", label: "上下文切换" },
  { value: "tree_recommendation", label: "知识树推荐" },
  { value: "temp_recommendation", label: "会话推荐" },
  { value: "job_update", label: "后台任务" },
];

const ACTION_TYPE_OPTIONS: { value: ActionType | ""; label: string }[] = [
  { value: "", label: "全部类型" },
  { value: "review", label: "复习" },
  { value: "practice", label: "练习" },
  { value: "rest", label: "休息" },
  { value: "explore", label: "探索" },
  { value: "exam_prep", label: "备考" },
];

const ACTION_TYPE_LABELS: Record<string, string> = {
  review: "复习",
  practice: "练习",
  rest: "休息",
  explore: "探索",
  exam_prep: "备考",
};

const SNOOZE_PRESETS = [
  { label: "1 小时", ms: 60 * 60 * 1000 },
  { label: "4 小时", ms: 4 * 60 * 60 * 1000 },
  { label: "明天", ms: 24 * 60 * 60 * 1000 },
];

const PRIORITY_LABELS: Record<number, string> = {
  1: "低",
  2: "较低",
  3: "中",
  4: "高",
  5: "紧急",
};

type TabKey = "pending" | "snoozed" | "history";
type ViewMode = "flat" | "grouped";

// ══════════════════════════════════════════════════════════════
//  Helper: convert API item to SecretaryNotification
// ══════════════════════════════════════════════════════════════

interface ProposalItem {
  id: string;
  emoji: string;
  title: string;
  description: string;
  action_type: string;
  priority: number;
  status: string;
  created_at?: string;
}

function toNotification(p: ProposalItem): SecretaryNotification {
  return {
    id: p.id,
    emoji: p.emoji,
    title: p.title,
    description: p.description,
    priority: p.priority,
    target: { pages: ["learn" as PageType] },
    source: "secretary",
    actionType: (p.action_type || undefined) as ActionType | undefined,
    sourceModule: "secretary",
    read: false,
    status: "pending",
    created_at: p.created_at ? new Date(p.created_at).getTime() : Date.now(),
  };
}

// ══════════════════════════════════════════════════════════════
//  Snapshot types
// ══════════════════════════════════════════════════════════════

interface SnapshotData {
  cognitive_load: number;
  weak_count: number;
  stagnant_count: number;
  streak_days: number;
  summary: string;
}

// ══════════════════════════════════════════════════════════════
//  Page Component
// ══════════════════════════════════════════════════════════════

export default function SecretaryPage() {
  // ── 基础状态 ──
  const [activeTab, setActiveTab] = useState<TabKey>("pending");
  const [snapshot, setSnapshot] = useState<SnapshotData | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [checking, setChecking] = useState(false);
  const [checkerResult, setCheckerResult] = useState<{ proposals: number; modules: number; reasons: string[] } | null>(null);

  // ── 筛选状态 ──
  const [filterSource, setFilterSource] = useState<NotificationSource | "">("");
  const [filterActionType, setFilterActionType] = useState<ActionType | "">("");
  const [priorityMin, setPriorityMin] = useState(1);
  const [searchText, setSearchText] = useState("");

  // ── 视图状态 ──
  const [viewMode, setViewMode] = useState<ViewMode>("flat");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [batchMode, setBatchMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  // ── 动作反馈 ──
  const [localFeedback, setLocalFeedback] = useState<{
    id: string; message: string; success: boolean;
  } | null>(null);

  // ── 初始化 ──
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [snapRes, propRes] = await Promise.all([
        fetch("/api/secretary/snapshot?user_id=default_user"),
        fetch("/api/secretary/proposals/pending?user_id=default_user"),
      ]);
      if (snapRes.ok) setSnapshot(await snapRes.json());
      if (propRes.ok) {
        const data: ProposalItem[] = await propRes.json();
        const store = useNotificationStore.getState();
        const existingIds = new Set(store.notifications.map((n) => n.id));
        for (const p of data) {
          const notif = toNotification(p);
          if (existingIds.has(p.id)) {
            store.updateNotification(p.id, notif);
          } else {
            store.addNotification(notif);
          }
        }
      }
    } finally {
      setLoading(false);
    }
  };

  // ── Read from store (individual selectors for stable references) ──
  const notifications = useNotificationStore((s) => s.notifications);
  const actionFeedbacks = useNotificationStore((s) => s.actionFeedbacks);
  const acceptNotification = useNotificationStore((s) => s.acceptNotification);
  const dismissNotificationAct = useNotificationStore((s) => s.dismissNotification);
  const hideNotification = useNotificationStore((s) => s.hideNotification);
  const snoozeNotificationAct = useNotificationStore((s) => s.snoozeNotification);
  const restoreNotification = useNotificationStore((s) => s.restoreNotification);
  const addActionFeedback = useNotificationStore((s) => s.addActionFeedback);
  const clearActionFeedback = useNotificationStore((s) => s.clearActionFeedback);
  const batchAccept = useNotificationStore((s) => s.batchAccept);
  const batchDismiss = useNotificationStore((s) => s.batchDismiss);

  // ── 筛选构建 ──
  const activeFilter = useMemo(() => {
    const f: any = {};
    if (filterSource) f.source = filterSource;
    if (filterActionType) f.actionType = filterActionType;
    if (priorityMin > 1) f.priorityMin = priorityMin;
    if (searchText) f.search = searchText;
    return Object.keys(f).length ? f : undefined;
  }, [filterSource, filterActionType, priorityMin, searchText]);

  // ── 根据 tab 获取数据 ──
  const { items, countLabel } = useMemo(() => {
    const store = useNotificationStore.getState();
    let list: SecretaryNotification[];
    let label = "";

    switch (activeTab) {
      case "pending": {
        list = store.getActiveNotifications(activeFilter);
        // further filter: exclude "secretary" source ones with non-pending status (already handled by getActiveNotifications)
        label = `待处理 (${list.length})`;
        break;
      }
      case "snoozed": {
        list = store.getSnoozedNotifications(activeFilter);
        label = `已延后 (${list.length})`;
        break;
      }
      case "history": {
        list = store.getHistoryNotifications(activeFilter);
        label = `历史 (${list.length})`;
        break;
      }
      default:
        list = [];
    }

    return { items: list, countLabel: label };
  }, [activeTab, activeFilter, notifications]);

  // ── 处理函数 ──
  const handleAccept = useCallback(async (id: string, options?: { navigate?: boolean }) => {
    try {
      const res = await fetch(`/api/secretary/proposals/${id}/accept?user_id=default_user`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        const msg = data.action_result?.message || "已采纳！";
        setLocalFeedback({ id, message: msg, success: true });
        setTimeout(() => setLocalFeedback(null), 4000);

        // 如果有 action_result，同步到 ActionFeedback
        if (data.action_result) {
          const notif = notifications.find((n) => n.id === id);
          addActionFeedback({
            id: `accept_${id}_${Date.now()}`,
            proposalId: id,
            actionType: (notif?.actionType || "review") as ActionType,
            title: notif?.title || "建议已采纳",
            result: data.action_result,
            planAdjustment: null,
            timestamp: Date.now(),
          });

          // 自动导航到目标页面（单个采纳时，批量采纳不跳转）
          const shouldNavigate = options?.navigate !== false;
          if (shouldNavigate && notif) {
            navigateToProposal({
              actionType: notif.actionType || "",
              payload: data.action_result?.payload || {},
              title: notif.title,
              description: notif.description,
              targetActionPath: notif.target?.actionPath,
            });
          }
        }
      }
      acceptNotification(id);
    } catch {
      // 即使 API 失败也更新本地状态
      acceptNotification(id);
    }
  }, [notifications, acceptNotification, addActionFeedback]);

  const handleDismiss = useCallback((id: string) => {
    dismissNotification(id);
  }, []);

  const handleSnooze = useCallback((id: string, ms: number) => {
    const until = Date.now() + ms;
    snoozeNotificationAct(id, until);
    snoozeNotification(id, until);
  }, [snoozeNotificationAct, snoozeNotification]);

  const handleHide = useCallback((id: string) => {
    hideNotification(id);
  }, [hideNotification]);

  const handleRestore = useCallback((id: string) => {
    restoreNotification(id);
    // also call backend if needed
    fetch(`/api/secretary/proposals/${id}/restore?user_id=default_user`, { method: "POST" }).catch(() => {});
  }, [restoreNotification]);

  // ── 生成提案 ──
  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await fetch("/api/secretary/generate-llm-proposals?user_id=default_user", {
        method: "POST",
      });
      if (res.ok) {
        const data: ProposalItem[] = await res.json();
        const store = useNotificationStore.getState();
        const existingIds = new Set(store.notifications.map((n) => n.id));
        for (const p of data) {
          const notif = toNotification(p);
          if (!existingIds.has(p.id)) {
            store.addNotification(notif);
          }
        }
      }
    } finally {
      setGenerating(false);
    }
  };

  // ── 手动主动检查 ──
  const handleRunCheck = async () => {
    setChecking(true);
    setCheckerResult(null);
    try {
      const res = await fetch("/api/secretary/checker/run?user_id=default_user", {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setCheckerResult({
          proposals: data.proposals_generated || 0,
          modules: data.modules_run || 0,
          reasons: data.reasons || [],
        });
        // 刷新当前视图
        await loadData();
      }
    } finally {
      setChecking(false);
    }
  };

  // ── 批量操作 ──
  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleBatchAccept = useCallback(() => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    ids.forEach((id) => handleAccept(id, { navigate: false }));
    setSelectedIds(new Set());
  }, [selectedIds, handleAccept]);

  const handleBatchDismiss = useCallback(() => {
    const ids = Array.from(selectedIds);
    if (ids.length === 0) return;
    ids.forEach((id) => handleDismiss(id));
    setSelectedIds(new Set());
  }, [selectedIds, handleDismiss]);

  // ── 分组数据 ──
  const grouped = useMemo(() => {
    if (viewMode !== "grouped") return null;
    const groups: Record<string, SecretaryNotification[]> = {};
    for (const item of items) {
      const key = item.actionType || "other";
      if (!groups[key]) groups[key] = [];
      groups[key].push(item);
    }
    return groups;
  }, [viewMode, items]);

  const groupOrder = ["review", "practice", "rest", "explore", "exam_prep", "other"];

  // ── 冷启动 ──
  const isColdStart = snapshot && snapshot.weak_count === 0 && snapshot.summary?.includes("数据不足");

  return (
    <div className="max-w-4xl mx-auto space-y-5">
      {/* ── 页面标题 ── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-text)]">秘书系统</h1>
          <p className="text-sm text-[var(--color-text-muted)] mt-0.5">智能学习助理 · 通知管理中心</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--color-accent)] text-white rounded-md hover:opacity-90 active:scale-[0.97] transition-opacity disabled:opacity-50"
          >
            {generating ? "生成中…" : "生成建议"}
            <Bell size={12} />
          </button>
          <button
            onClick={handleRunCheck}
            disabled={checking}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--color-surface)] text-[var(--color-text)] rounded-md border border-[var(--color-border)] hover:bg-[var(--color-bg-tertiary)] transition-colors disabled:opacity-50"
          >
            {checking ? "检查中…" : "立即检查"}
            <Timer size={12} />
          </button>
          <a
            href="/secretary/settings"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--color-surface)] text-[var(--color-text-muted)] rounded-md border border-[var(--color-border)] hover:text-[var(--color-text)] transition-colors"
          >
            <Settings size={12} />
            设置
          </a>
        </div>
      </div>

      {/* ── 状态卡片 ── */}
      {loading ? (
        <div className="p-8 text-center text-sm text-[var(--color-text-muted)]">加载中…</div>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-3">
            {[
              { label: "薄弱点", value: snapshot?.weak_count ?? 0, icon: AlertTriangle, color: "text-[var(--color-error)]", bg: "bg-[var(--color-error)]/5" },
              { label: "停滞项", value: snapshot?.stagnant_count ?? 0, icon: Clock, color: "text-[var(--color-warning)]", bg: "bg-yellow-500/5" },
              { label: "学习天数", value: snapshot?.streak_days ?? 0, icon: TrendingUp, color: "text-[var(--color-success)]", bg: "bg-[var(--color-success)]/5" },
              { label: "认知负荷", value: snapshot?.cognitive_load != null ? `${Math.round(snapshot.cognitive_load * 100)}%` : "—", icon: Bell, color: "text-[var(--color-info)]", bg: "bg-[var(--color-accent)]/5" },
            ].map((stat) => {
              const Icon = stat.icon;
              return (
                <div key={stat.label} className={`p-3 rounded-lg ${stat.bg}`}>
                  <Icon size={14} className={stat.color} />
                  <div className="text-lg font-semibold text-[var(--color-text)] mt-1">{stat.value}</div>
                  <div className="text-[10px] text-[var(--color-text-muted)]">{stat.label}</div>
                </div>
              );
            })}
          </div>

          {isColdStart && (
            <div className="p-4 rounded-lg border border-[var(--color-warning)]/20 bg-yellow-500/5">
              <p className="text-sm text-[var(--color-warning)]">📊 学习数据不足，建议先进行一些练习，秘书系统才能提供个性化建议</p>
            </div>
          )}

          {/* ── 主动检查结果 ── */}
          {checkerResult && (
            <div className={`p-3 rounded-lg flex items-start gap-2 ${
              checkerResult.proposals > 0
                ? "border border-[var(--color-success)]/20 bg-[var(--color-success)]/5"
                : "border border-[var(--color-border)] bg-[var(--color-surface)]"
            }`}>
              <Bell size={14} className={checkerResult.proposals > 0 ? "text-[var(--color-success)]" : "text-[var(--color-text-muted)]"} />
              <div className="flex-1 min-w-0">
                <p className="text-xs text-[var(--color-text)]">
                  检查完成：运行 {checkerResult.modules} 个模块，生成 {checkerResult.proposals} 条提案
                </p>
                {checkerResult.reasons.length > 0 && (
                  <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5 truncate">
                    {checkerResult.reasons.slice(0, 3).join("；")}
                  </p>
                )}
              </div>
              <button
                onClick={() => setCheckerResult(null)}
                className="text-[var(--color-text-tertiary)] hover:text-[var(--color-text)]"
              >
                <X size={12} />
              </button>
            </div>
          )}

          {/* ── 动作反馈 Toast ── */}
          {localFeedback && localFeedback.success && (
            <div className="p-3 rounded-lg border border-[var(--color-success)]/20 bg-[var(--color-success)]/5 flex items-center gap-2">
              <Check size={14} className="text-[var(--color-success)] flex-shrink-0" />
              <span className="text-sm text-[var(--color-success)]">{localFeedback.message}</span>
            </div>
          )}
        </>
      )}

      {/* ── Tab 栏 ── */}
      <div className="flex items-center border-b border-[var(--color-border)] gap-0">
        {([
          { key: "pending" as TabKey, label: "待处理", icon: Bell },
          { key: "snoozed" as TabKey, label: "已延后", icon: Timer },
          { key: "history" as TabKey, label: "历史", icon: Clock },
        ]).map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => { setActiveTab(key); setSelectedIds(new Set()); }}
            className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
              activeTab === key
                ? "border-[var(--color-accent)] text-[var(--color-text)]"
                : "border-transparent text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}
          >
            <Icon size={12} />
            {label}
          </button>
        ))}
      </div>

      {/* ── 筛选栏 ── */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* 来源 */}
        <select
          value={filterSource}
          onChange={(e) => setFilterSource(e.target.value as NotificationSource | "")}
          className="text-xs px-2 py-1 rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
        >
          {SOURCE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        {/* 动作类型 */}
        <select
          value={filterActionType}
          onChange={(e) => setFilterActionType(e.target.value as ActionType | "")}
          className="text-xs px-2 py-1 rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
        >
          {ACTION_TYPE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>

        {/* 优先级 */}
        <select
          value={priorityMin}
          onChange={(e) => setPriorityMin(Number(e.target.value))}
          className="text-xs px-2 py-1 rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)]"
        >
          <option value={1}>优先级 ≥ 1</option>
          <option value={2}>优先级 ≥ 2</option>
          <option value={3}>优先级 ≥ 3</option>
          <option value={4}>优先级 ≥ 4</option>
          <option value={5}>优先级 = 5</option>
        </select>

        {/* 搜索 */}
        <div className="relative flex-1 min-w-[120px] max-w-[200px]">
          <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
          <input
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            placeholder="搜索标题/描述…"
            className="w-full text-xs pl-7 pr-2 py-1 rounded border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] outline-none focus:border-[var(--color-accent)]"
          />
        </div>

        {/* 分组切换 */}
        <button
          onClick={() => setViewMode(viewMode === "flat" ? "grouped" : "flat")}
          className={`text-xs px-2 py-1 rounded border transition-colors ${
            viewMode === "grouped"
              ? "border-[var(--color-accent)] text-[var(--color-accent)] bg-[var(--color-accent)]/5"
              : "border-[var(--color-border)] text-[var(--color-text-muted)] bg-[var(--color-surface)]"
          }`}
        >
          按类型{viewMode === "grouped" ? " ✓" : ""}
        </button>

        {/* 批量模式 */}
        {activeTab === "pending" && (
          <button
            onClick={() => { setBatchMode(!batchMode); setSelectedIds(new Set()); }}
            className={`text-xs px-2 py-1 rounded border transition-colors ${
              batchMode
                ? "border-[var(--color-accent)] text-[var(--color-accent)] bg-[var(--color-accent)]/5"
                : "border-[var(--color-border)] text-[var(--color-text-muted)] bg-[var(--color-surface)]"
            }`}
          >
            批量{batchMode ? " ✓" : ""}
          </button>
        )}

        {/* 如果有筛选，显示清理 */}
        {(filterSource || filterActionType || priorityMin > 1 || searchText) && (
          <button
            onClick={() => {
              setFilterSource("");
              setFilterActionType("");
              setPriorityMin(1);
              setSearchText("");
            }}
            className="text-xs px-2 py-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-error)] transition-colors"
          >
            清除筛选
          </button>
        )}
      </div>

      {/* ── 批量操作栏 ── */}
      {batchMode && selectedIds.size > 0 && (
        <div className="flex items-center gap-2 p-2 rounded-lg bg-[var(--color-accent)]/5 border border-[var(--color-accent)]/20">
          <span className="text-xs text-[var(--color-text-muted)]">已选 {selectedIds.size} 项</span>
          <button
            onClick={handleBatchAccept}
            className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-medium bg-[var(--color-success)] text-white rounded hover:opacity-90"
          >
            <Check size={10} />批量采纳
          </button>
          <button
            onClick={handleBatchDismiss}
            className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-[var(--color-text-muted)] bg-[var(--color-surface)] rounded border border-[var(--color-border)] hover:text-[var(--color-text)]"
          >
            <X size={10} />批量忽略
          </button>
          <button
            onClick={() => setSelectedIds(new Set())}
            className="text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] ml-auto"
          >
            取消选择
          </button>
        </div>
      )}

      {/* ── 列表标题 ── */}
      {!loading && (
        <div className="text-xs text-[var(--color-text-muted)]">{countLabel}</div>
      )}

      {/* ── 列表 / 分组视图 ── */}
      {!loading && items.length === 0 ? (
        <div className="p-6 rounded-lg border border-dashed border-[var(--color-border)] text-center text-sm text-[var(--color-text-muted)]">
          {activeTab === "pending" && "🎉 没有待处理的通知"}
          {activeTab === "snoozed" && "没有已延后的通知"}
          {activeTab === "history" && "暂无历史记录"}
        </div>
      ) : (
        <>
          {/* Flat 模式 */}
          {viewMode === "flat" && items.map((item) => (
            <ProposalCard
              key={item.id}
              item={item}
              tab={activeTab}
              expanded={expandedId === item.id}
              batchMode={batchMode && activeTab === "pending"}
              selected={selectedIds.has(item.id)}
              onToggleExpand={() => setExpandedId(expandedId === item.id ? null : item.id)}
              onToggleSelect={() => toggleSelect(item.id)}
              onAccept={() => handleAccept(item.id)}
              onDismiss={() => handleDismiss(item.id)}
              onSnooze={(ms) => handleSnooze(item.id, ms)}
              onHide={() => handleHide(item.id)}
              onRestore={() => handleRestore(item.id)}
            />
          ))}

          {/* 分组模式 */}
          {viewMode === "grouped" && grouped && groupOrder.map((key) => {
            const group = grouped[key];
            if (!group || group.length === 0) return null;
            return (
              <div key={key} className="space-y-1.5">
                <h3 className="text-xs font-medium text-[var(--color-text-muted)] flex items-center gap-1.5 px-1">
                  {ACTION_TYPE_LABELS[key] || key === "other" ? "其他" : key}
                  <span className="text-[10px] px-1 rounded bg-[var(--color-bg-tertiary)]">{group.length}</span>
                </h3>
                {group.map((item) => (
                  <ProposalCard
                    key={item.id}
                    item={item}
                    tab={activeTab}
                    expanded={expandedId === item.id}
                    batchMode={batchMode && activeTab === "pending"}
                    selected={selectedIds.has(item.id)}
                    onToggleExpand={() => setExpandedId(expandedId === item.id ? null : item.id)}
                    onToggleSelect={() => toggleSelect(item.id)}
                    onAccept={() => handleAccept(item.id)}
                    onDismiss={() => handleDismiss(item.id)}
                    onSnooze={(ms) => handleSnooze(item.id, ms)}
                    onHide={() => handleHide(item.id)}
                    onRestore={() => handleRestore(item.id)}
                  />
                ))}
              </div>
            );
          })}
        </>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
//  ProposalCard
// ══════════════════════════════════════════════════════════════

interface ProposalCardProps {
  item: SecretaryNotification;
  tab: TabKey;
  expanded: boolean;
  batchMode: boolean;
  selected: boolean;
  onToggleExpand: () => void;
  onToggleSelect: () => void;
  onAccept: () => void;
  onDismiss: () => void;
  onSnooze: (ms: number) => void;
  onHide: () => void;
  onRestore: () => void;
}

function ProposalCard({
  item,
  tab,
  expanded,
  batchMode,
  selected,
  onToggleExpand,
  onToggleSelect,
  onAccept,
  onDismiss,
  onSnooze,
  onHide,
  onRestore,
}: ProposalCardProps) {
  const borderColor =
    item.priority >= 4
      ? "border-l-red-500"
      : item.priority >= 3
        ? "border-l-yellow-400"
        : "border-l-blue-400";

  const sourceLabel: Record<string, string> = {
    secretary: "秘书引擎",
    context_switch: "上下文切换",
    tree_recommendation: "知识树推荐",
    temp_recommendation: "会话推荐",
    job_update: "后台任务",
  };

  return (
    <div
      className={`p-3 rounded-lg border border-[var(--color-border)] border-l-4 ${borderColor} ${
        selected ? "ring-1 ring-[var(--color-accent)]" : ""
      } transition-shadow`}
    >
      <div className="flex items-start gap-2">
        {/* 批量模式复选框 */}
        {batchMode && (
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggleSelect}
            className="mt-1 accent-[var(--color-accent)]"
          />
        )}

        <span className="text-base leading-none mt-0.5">{item.emoji}</span>

        {/* 主内容 */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <button
              onClick={onToggleExpand}
              className="text-sm font-medium text-[var(--color-text)] hover:text-[var(--color-accent)] transition-colors text-left"
            >
              {item.title}
            </button>
            {item.actionType && (
              <span className="text-[10px] px-1 rounded bg-[var(--color-bg-tertiary)] text-[var(--color-text-tertiary)] flex-shrink-0">
                {ACTION_TYPE_LABELS[item.actionType] || item.actionType}
              </span>
            )}
            {item.priority >= 4 && (
              <span className="text-[10px] px-1 rounded bg-red-500/10 text-red-500 flex-shrink-0">高优</span>
            )}
          </div>

          {!expanded && (
            <div className="text-xs text-[var(--color-text-muted)] mt-0.5 line-clamp-2">
              {item.description}
            </div>
          )}

          {/* 展开详情 */}
          {expanded && (
            <div className="mt-2 space-y-2 text-xs">
              <p className="text-[var(--color-text-secondary)]">{item.description}</p>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-[var(--color-text-tertiary)]">
                <span>来源: {sourceLabel[item.source] || item.source}</span>
                {item.actionType && <span>类型: {ACTION_TYPE_LABELS[item.actionType] || item.actionType}</span>}
                <span>优先级: {PRIORITY_LABELS[item.priority] || item.priority}</span>
                <span>创建: {new Date(item.created_at).toLocaleString("zh-CN")}</span>
                {item.snoozedUntil && (
                  <span>延后至: {new Date(item.snoozedUntil).toLocaleString("zh-CN")}</span>
                )}
              </div>
              {item.target.actionPath && (
                <a
                  href={item.target.actionPath}
                  className="inline-flex items-center gap-1 text-[var(--color-info)] hover:underline"
                >
                  <MessageSquare size={10} />前往 {item.target.actionPath}
                </a>
              )}
            </div>
          )}

          {/* 操作按钮 */}
          <div className="flex gap-1.5 mt-2 flex-wrap">
            {tab === "pending" && (
              <>
                <button
                  onClick={onAccept}
                  className="inline-flex items-center gap-1 px-2 py-1 text-[10px] font-medium bg-[var(--color-success)] text-white rounded hover:opacity-90 active:scale-[0.97] transition-all"
                >
                  <Check size={10} />采纳
                </button>
                <button
                  onClick={onDismiss}
                  className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] bg-[var(--color-surface)] rounded border border-[var(--color-border)] hover:border-[var(--color-text-muted)] transition-colors"
                >
                  <X size={10} />忽略
                </button>

                {/* 延后 */}
                <div className="relative group">
                  <button
                    className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] bg-[var(--color-surface)] rounded border border-[var(--color-border)] hover:border-[var(--color-text-muted)] transition-colors"
                  >
                    <Clock size={10} />延后
                  </button>
                  <div className="absolute top-full left-0 mt-1 z-10 hidden group-hover:flex flex-col gap-0.5 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded shadow-lg p-1 min-w-[80px]">
                    {SNOOZE_PRESETS.map((preset) => (
                      <button
                        key={preset.label}
                        onClick={onSnooze.bind(null, preset.ms)}
                        className="text-[10px] px-2 py-1 text-left text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-bg-tertiary)] rounded transition-colors"
                      >
                        {preset.label}
                      </button>
                    ))}
                  </div>
                </div>

                <button
                  onClick={onHide}
                  className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] bg-[var(--color-surface)] rounded border border-[var(--color-border)] hover:border-[var(--color-text-muted)] transition-colors"
                >
                  <EyeOff size={10} />隐藏
                </button>
              </>
            )}

            {tab === "history" && (
              <button
                onClick={onRestore}
                className="inline-flex items-center gap-1 px-2 py-1 text-[10px] text-[var(--color-info)] bg-[var(--color-surface)] rounded border border-blue-400/30 hover:border-blue-400/60 transition-colors"
              >
                <RotateCcw size={10} />恢复
              </button>
            )}
          </div>
        </div>

        {/* 展开/折叠图标 */}
        <button
          onClick={onToggleExpand}
          className="flex-shrink-0 mt-0.5 text-[var(--color-text-tertiary)] hover:text-[var(--color-text-muted)] transition-colors"
        >
          {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        </button>
      </div>
    </div>
  );
}
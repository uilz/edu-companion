"use client";

import {
  Bell, Check, X, Clock, AlertTriangle, TrendingUp, Settings,
  Timer, Activity,
} from "lucide-react";
import { useState, useEffect, useCallback, useMemo } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useNotificationStore } from "@/store/notification/notification-store";
import { authedFetch } from "@/lib/api/api";
import {
  snoozeNotification,
  dismissNotification,
} from "@/store/notification/notification-service";
import { navigateToProposal } from "@/store/notification/proposal-navigator";
import type {
  SecretaryNotification, PageType, ActionType, NotificationSource,
} from "@/store/notification/types";
import EventStream from "@/components/secretary/EventStream";
import {
  ACTION_TYPE_LABELS, TabKey, ViewMode, ProposalItem, SnapshotData, toNotification,
} from "@/components/secretary/shared";
import ProposalCard from "@/components/secretary/ProposalCard";
import FilterBar from "@/components/secretary/FilterBar";
import BatchActions from "@/components/secretary/BatchActions";
import StatsCards from "@/components/secretary/StatsCards";

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

  const { user, loading: authLoading } = useAuth();

  // ── 初始化 ──
  useEffect(() => {
    if (authLoading || !user) return;
    loadData();
  }, [authLoading, user]);

  const loadData = async () => {
    if (authLoading || !user) return;
    setLoading(true);
    try {
      const userId = user.id;
      const [snapRes, propRes] = await Promise.all([
        authedFetch(`/api/secretary/snapshot?user_id=${userId}`),
        authedFetch(`/api/secretary/proposals/pending?user_id=${userId}`),
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
      case "events": {
        list = [];
        label = "事件流";
        break;
      }
      default:
        list = [];
    }

    return { items: list, countLabel: label };
  }, [activeTab, activeFilter, notifications]);

  // ── 处理函数 ──
  const handleAccept = useCallback(async (id: string, options?: { navigate?: boolean }) => {
    if (!user) return;
    try {
      const userId = user.id;
      const res = await authedFetch(`/api/secretary/proposals/${id}/accept?user_id=${userId}`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        const msg = data.action_result?.message || "已采纳！";
        setLocalFeedback({ id, message: msg, success: true });
        setTimeout(() => setLocalFeedback(null), 4000);

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
      acceptNotification(id);
    }
  }, [user, notifications, acceptNotification, addActionFeedback]);

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
    if (!user) return;
    restoreNotification(id);
    authedFetch(`/api/secretary/proposals/${id}/restore?user_id=${user.id}`, { method: "POST" }).catch(() => {});
  }, [user, restoreNotification]);

  // ── 生成提案 ──
  const handleGenerate = async () => {
    if (!user) return;
    setGenerating(true);
    try {
      const res = await authedFetch(`/api/secretary/generate-llm-proposals?user_id=${user.id}`, {
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
    if (!user) return;
    setChecking(true);
    setCheckerResult(null);
    try {
      const res = await authedFetch(`/api/secretary/checker/run?user_id=${user.id}`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setCheckerResult({
          proposals: data.proposals_generated || 0,
          modules: data.modules_run || 0,
          reasons: data.reasons || [],
        });
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

  const handleClearFilters = useCallback(() => {
    setFilterSource("");
    setFilterActionType("");
    setPriorityMin(1);
    setSearchText("");
  }, []);

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
          <h1 className="text-xl font-semibold text">秘书系统</h1>
          <p className="text-sm text-muted mt-0.5">智能学习助理 · 通知管理中心</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-accent text-white rounded-md hover:opacity-90 active:scale-[0.97] transition-opacity disabled:opacity-50"
          >
            {generating ? "生成中…" : "生成建议"}
            <Bell size={12} />
          </button>
          <button
            onClick={handleRunCheck}
            disabled={checking}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface text rounded-md border border hover:bg-surface-hover transition-colors disabled:opacity-50"
          >
            {checking ? "检查中…" : "立即检查"}
            <Timer size={12} />
          </button>
          <a
            href="/secretary/settings"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-surface text-muted rounded-md border border hover:text transition-colors"
          >
            <Settings size={12} />
            设置
          </a>
        </div>
      </div>

      {/* ── 状态卡片 ── */}
      {loading ? (
        <div className="p-8 text-center text-sm text-muted">加载中…</div>
      ) : (
        <>
          <StatsCards snapshot={snapshot} />

          {isColdStart && (
            <div className="p-4 rounded-lg border border-warning/20 bg-warning/5">
              <p className="text-sm text-warning">📊 学习数据不足，建议先进行一些练习，秘书系统才能提供个性化建议</p>
            </div>
          )}

          {/* ── 主动检查结果 ── */}
          {checkerResult && (
            <div className={`p-3 rounded-lg flex items-start gap-2 ${
              checkerResult.proposals > 0
                ? "border border-success/20 bg-success/5"
                : "border border bg-surface"
            }`}>
              <Bell size={14} className={checkerResult.proposals > 0 ? "text-success" : "text-muted"} />
              <div className="flex-1 min-w-0">
                <p className="text-xs text">
                  检查完成：运行 {checkerResult.modules} 个模块，生成 {checkerResult.proposals} 条提案
                </p>
                {checkerResult.reasons.length > 0 && (
                  <p className="text-[10px] text-muted mt-0.5 truncate">
                    {checkerResult.reasons.slice(0, 3).join("；")}
                  </p>
                )}
              </div>
              <button
                onClick={() => setCheckerResult(null)}
                className="text-muted hover:text"
              >
                <X size={12} />
              </button>
            </div>
          )}

          {/* ── 动作反馈 Toast ── */}
          {localFeedback && localFeedback.success && (
            <div className="p-3 rounded-lg border border-success/20 bg-success/5 flex items-center gap-2">
              <Check size={14} className="text-success flex-shrink-0" />
              <span className="text-sm text-success">{localFeedback.message}</span>
            </div>
          )}
        </>
      )}

      {/* ── Tab 栏 ── */}
      <div className="flex items-center border-b border gap-0">
        {([
          { key: "pending" as TabKey, label: "待处理", icon: Bell },
          { key: "snoozed" as TabKey, label: "已延后", icon: Timer },
          { key: "history" as TabKey, label: "历史", icon: Clock },
          { key: "events" as TabKey, label: "事件流", icon: Activity },
        ]).map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => { setActiveTab(key); setSelectedIds(new Set()); }}
            className={`flex items-center gap-1.5 px-4 py-2 text-xs font-medium border-b-2 transition-colors ${
              activeTab === key
                ? "border-accent text"
                : "border-transparent text-muted hover:text"
            }`}
          >
            <Icon size={12} />
            {label}
          </button>
        ))}
      </div>

      {/* ── 筛选栏 ── */}
      <FilterBar
        activeTab={activeTab}
        filterSource={filterSource}
        filterActionType={filterActionType}
        priorityMin={priorityMin}
        searchText={searchText}
        viewMode={viewMode}
        batchMode={batchMode}
        onFilterSourceChange={setFilterSource}
        onFilterActionTypeChange={setFilterActionType}
        onPriorityMinChange={setPriorityMin}
        onSearchTextChange={setSearchText}
        onViewModeToggle={() => setViewMode(viewMode === "flat" ? "grouped" : "flat")}
        onBatchModeToggle={() => { setBatchMode(!batchMode); setSelectedIds(new Set()); }}
        onClearFilters={handleClearFilters}
      />

      {/* ── 批量操作栏 ── */}
      {batchMode && selectedIds.size > 0 && (
        <BatchActions
          selectedCount={selectedIds.size}
          onBatchAccept={handleBatchAccept}
          onBatchDismiss={handleBatchDismiss}
          onCancelSelection={() => setSelectedIds(new Set())}
        />
      )}

      {/* ── 列表标题 ── */}
      {!loading && activeTab !== "events" && (
        <div className="text-xs text-muted">{countLabel}</div>
      )}

      {/* ── 列表 / 分组视图 ── */}
      {/* 事件流 tab — 独立渲染 */}
      {activeTab === "events" && <EventStream />}

      {/* 通知 tabs */}
      {activeTab !== "events" && !loading && items.length === 0 ? (
        <div className="p-6 rounded-lg border border-dashed border text-center text-sm text-muted">
          {activeTab === "pending" && "🎉 没有待处理的通知"}
          {activeTab === "snoozed" && "没有已延后的通知"}
          {activeTab === "history" && "暂无历史记录"}
        </div>
      ) : activeTab !== "events" ? (
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
                <h3 className="text-xs font-medium text-muted flex items-center gap-1.5 px-1">
                  {ACTION_TYPE_LABELS[key] || key === "other" ? "其他" : key}
                  <span className="text-[10px] px-1 rounded bg-surface-hover">{group.length}</span>
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
      ) : null}
    </div>
  );
}
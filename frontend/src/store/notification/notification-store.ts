// ══════════════════════════════════════════════════════════════
//  NotificationStore — 统一通知状态管理
//
//  基于 Zustand，管理所有通知的增删改查和页面感知路由。
//  不直接依赖 React，可在任何模块中使用。
// ══════════════════════════════════════════════════════════════

import { create } from "zustand";
import type {
  SecretaryNotification,
  PageType,
  NotificationFilter,
  ActionFeedback,
} from "./types";

// ══════════════════════════════════════════════════════════════
//  辅助: 根据筛选条件过滤通知列表
// ══════════════════════════════════════════════════════════════

function applyFilter(
  list: SecretaryNotification[],
  filter?: NotificationFilter,
): SecretaryNotification[] {
  if (!filter) return list;
  return list.filter((n) => {
    if (filter.source && n.source !== filter.source) return false;
    if (filter.sourceModule && n.sourceModule !== filter.sourceModule) return false;
    if (filter.actionType && n.actionType !== filter.actionType) return false;
    if (filter.priorityMin !== undefined && (n.priority ?? 3) < filter.priorityMin) return false;
    if (filter.priorityMax !== undefined && (n.priority ?? 3) > filter.priorityMax) return false;
    if (filter.page && !n.target.pages.includes(filter.page)) return false;
    if (filter.search) {
      const q = filter.search.toLowerCase();
      if (
        !n.title.toLowerCase().includes(q) &&
        !n.description.toLowerCase().includes(q)
      )
        return false;
    }
    return true;
  });
}

// ══════════════════════════════════════════════════════════════
//  State
// ══════════════════════════════════════════════════════════════

export interface NotificationState {
  notifications: SecretaryNotification[];

  // ── 动作反馈 ──
  actionFeedbacks: ActionFeedback[];

  // ── 基础查询 ──
  getNotifications: () => SecretaryNotification[];
  getNotificationsByPage: (page: PageType) => SecretaryNotification[];
  getInlineNotifications: (conversationId: string) => SecretaryNotification[];
  unreadCount: () => number;

  // ── 高级筛选查询 ──
  getFilteredNotifications: (filter?: NotificationFilter) => SecretaryNotification[];

  // ── 活跃/历史/隐式 分组查询 ──
  /** 当前应展示的活跃通知（pending + 非 snoozed + 非 hidden） */
  getActiveNotifications: (filter?: NotificationFilter) => SecretaryNotification[];
  /** 已延后的通知 */
  getSnoozedNotifications: (filter?: NotificationFilter) => SecretaryNotification[];
  /** 已隐藏的通知（用户可手动恢复） */
  getHiddenNotifications: (filter?: NotificationFilter) => SecretaryNotification[];
  /** 已处理的历史通知（accepted / dismissed / deleted） */
  getHistoryNotifications: (filter?: NotificationFilter) => SecretaryNotification[];

  // ── 命令 ──
  addNotification: (n: SecretaryNotification) => void;
  updateNotification: (id: string, patch: Partial<SecretaryNotification>) => void;
  markRead: (id: string) => void;
  acceptNotification: (id: string) => void;
  dismissNotification: (id: string) => void;
  /** 删除通知（从 store 中移除） */
  removeNotification: (id: string) => void;
  /** 延后通知到指定时间 */
  snoozeNotification: (id: string, untilTimestamp: number) => void;
  /** 隐藏通知（保留在 store，可通过历史恢复） */
  hideNotification: (id: string) => void;
  /** 恢复隐藏/已处理/已延后的通知 */
  restoreNotification: (id: string) => void;
  clearAll: () => void;

  // ── 动作反馈 ──
  addActionFeedback: (feedback: ActionFeedback) => void;
  clearActionFeedback: (id: string) => void;
  clearAllFeedbacks: () => void;

  // ── 批量操作 ──
  batchAccept: (filter?: NotificationFilter) => string[];
  batchDismiss: (filter?: NotificationFilter) => string[];
}

// ══════════════════════════════════════════════════════════════
//  Store
// ══════════════════════════════════════════════════════════════

export const useNotificationStore = create<NotificationState>()((set, get) => ({
  notifications: [],
  actionFeedbacks: [],

  // ── 基础查询 ──

  getNotifications: () => get().notifications,

  getNotificationsByPage: (page: PageType) =>
    get().notifications.filter((n) => n.target.pages.includes(page)),

  getInlineNotifications: (conversationId: string) =>
    get().notifications.filter(
      (n) =>
        n.target.inlineConversationId === conversationId &&
        n.status === "pending" &&
        !n.hidden &&
        (!n.snoozedUntil || Date.now() >= n.snoozedUntil),
    ),

  unreadCount: () =>
    get().notifications.filter(
      (n) => !n.read && n.status === "pending" && !n.hidden &&
        (!n.snoozedUntil || Date.now() >= n.snoozedUntil),
    ).length,

  // ── 高级筛选 ──

  getFilteredNotifications: (filter) =>
    applyFilter(get().notifications, filter),

  // ── 分组查询 ──

  getActiveNotifications: (filter) =>
    applyFilter(
      get().notifications.filter(
        (n) =>
          n.status === "pending" &&
          !n.hidden &&
          (!n.snoozedUntil || Date.now() >= n.snoozedUntil),
      ),
      filter,
    ),

  getSnoozedNotifications: (filter) =>
    applyFilter(
      get().notifications.filter(
        (n) =>
          n.status === "pending" &&
          n.snoozedUntil &&
          Date.now() < n.snoozedUntil,
      ),
      filter,
    ),

  getHiddenNotifications: (filter) =>
    applyFilter(
      get().notifications.filter((n) => n.hidden),
      filter,
    ),

  getHistoryNotifications: (filter) =>
    applyFilter(
      get().notifications.filter(
        (n) =>
          n.status === "accepted" ||
          n.status === "dismissed" ||
          n.status === "deleted",
      ),
      filter,
    ),

  // ── 命令 ──

  addNotification: (n) =>
    set((s) => ({ notifications: [...s.notifications, n] })),

  updateNotification: (id, patch) =>
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === id ? { ...n, ...patch } : n,
      ),
    })),

  markRead: (id) =>
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === id ? { ...n, read: true } : n
      ),
    })),

  acceptNotification: (id) =>
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === id ? { ...n, status: "accepted" as const, read: true } : n
      ),
    })),

  dismissNotification: (id) =>
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === id ? { ...n, status: "dismissed" as const } : n
      ),
    })),

  removeNotification: (id) =>
    set((s) => ({
      notifications: s.notifications.filter((n) => n.id !== id),
    })),

  snoozeNotification: (id, untilTimestamp) =>
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === id ? { ...n, snoozedUntil: untilTimestamp } : n
      ),
    })),

  hideNotification: (id) =>
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === id ? { ...n, hidden: true } : n
      ),
    })),

  restoreNotification: (id) =>
    set((s) => ({
      notifications: s.notifications.map((n) =>
        n.id === id
          ? { ...n, hidden: false, snoozedUntil: undefined, status: "pending" as const }
          : n
      ),
    })),

  clearAll: () => set({ notifications: [] }),

  // ── 动作反馈 ──

  addActionFeedback: (feedback) =>
    set((s) => ({ actionFeedbacks: [...s.actionFeedbacks, feedback] })),

  clearActionFeedback: (id) =>
    set((s) => ({
      actionFeedbacks: s.actionFeedbacks.filter((f) => f.id !== id),
    })),

  clearAllFeedbacks: () => set({ actionFeedbacks: [] }),

  // ── 批量操作 ──

  batchAccept: (filter) => {
    const ids = get()
      .getActiveNotifications(filter)
      .map((n) => n.id);
    set((s) => ({
      notifications: s.notifications.map((n) =>
        ids.includes(n.id) ? { ...n, status: "accepted" as const, read: true } : n
      ),
    }));
    return ids;
  },

  batchDismiss: (filter) => {
    const ids = get()
      .getActiveNotifications(filter)
      .map((n) => n.id);
    set((s) => ({
      notifications: s.notifications.map((n) =>
        ids.includes(n.id) ? { ...n, status: "dismissed" as const } : n
      ),
    }));
    return ids;
  },
}));

// ══════════════════════════════════════════════════════════════
//  Imperative API（测试和非 React 场景）
// ══════════════════════════════════════════════════════════════

export function createNotificationStore() {
  const store = useNotificationStore;
  return {
    // 基础
    addNotification: (n: SecretaryNotification) => store.getState().addNotification(n),
    getNotifications: () => store.getState().getNotifications(),
    getNotificationsByPage: (page: PageType) => store.getState().getNotificationsByPage(page),
    getInlineNotifications: (cid: string) => store.getState().getInlineNotifications(cid),
    unreadCount: () => store.getState().unreadCount(),
    markRead: (id: string) => store.getState().markRead(id),
    acceptNotification: (id: string) => store.getState().acceptNotification(id),
    dismissNotification: (id: string) => store.getState().dismissNotification(id),
    removeNotification: (id: string) => store.getState().removeNotification(id),
    clearAll: () => store.getState().clearAll(),

    // 高级筛选
    getFilteredNotifications: (filter?: NotificationFilter) =>
      store.getState().getFilteredNotifications(filter),

    // 分组
    getActiveNotifications: (filter?: NotificationFilter) =>
      store.getState().getActiveNotifications(filter),
    getSnoozedNotifications: (filter?: NotificationFilter) =>
      store.getState().getSnoozedNotifications(filter),
    getHiddenNotifications: (filter?: NotificationFilter) =>
      store.getState().getHiddenNotifications(filter),
    getHistoryNotifications: (filter?: NotificationFilter) =>
      store.getState().getHistoryNotifications(filter),

    // 新操作
    snoozeNotification: (id: string, until: number) =>
      store.getState().snoozeNotification(id, until),
    hideNotification: (id: string) =>
      store.getState().hideNotification(id),
    restoreNotification: (id: string) =>
      store.getState().restoreNotification(id),
    updateNotification: (id: string, patch: Partial<SecretaryNotification>) =>
      store.getState().updateNotification(id, patch),
    batchAccept: (filter?: NotificationFilter) =>
      store.getState().batchAccept(filter),
    batchDismiss: (filter?: NotificationFilter) =>
      store.getState().batchDismiss(filter),

    // 动作反馈
    addActionFeedback: (feedback: ActionFeedback) =>
      store.getState().addActionFeedback(feedback),
    clearActionFeedback: (id: string) =>
      store.getState().clearActionFeedback(id),
    clearAllFeedbacks: () =>
      store.getState().clearAllFeedbacks(),
    getActionFeedbacks: () =>
      store.getState().actionFeedbacks,
  };
}
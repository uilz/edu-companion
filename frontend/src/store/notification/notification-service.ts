// ══════════════════════════════════════════════════════════════
//  NotificationService — WS 事件消费 + API 对接
//
//  将 WS 事件转为 NotificationStore 的操作。
// ══════════════════════════════════════════════════════════════

import type {
  SecretaryNotification,
  SecretaryUpdatePayload,
  NotificationHistoryItem,
  NotificationFilter,
  ActionType,
} from "./types";
import { useNotificationStore } from "./notification-store";
import { navigateToProposal } from "./proposal-navigator";
import { api } from "@/lib/api/api";

/**
 * 处理 secretary_update WS 事件：
 * 收到有新提案的通知时，从 API 拉取最新提案列表并入 store。
 */
export async function handleSecretaryUpdate(
  _payload: SecretaryUpdatePayload,
): Promise<void> {
  try {
    const proposals: SecretaryNotification[] = await api("/api/secretary/proposals/pending");
    const store = useNotificationStore.getState();
    proposals.forEach((p) => store.addNotification(p));
  } catch {
    // 静默失败，下次更新会重试
  }
}

/**
 * 处理 secretary_inline WS 事件：
 * 后端主动推送完整通知数据，直接入 store。
 */
export function handleSecretaryInline(proposal: SecretaryNotification): void {
  useNotificationStore.getState().addNotification(proposal);
}

/**
 * 处理 secretary_proposal_update WS 事件：
 * 后端推送提案状态变更，同步更新本地 store。
 */
export function handleSecretaryProposalUpdate(
  data: { id: string; status: string; until?: number | null },
): void {
  const store = useNotificationStore.getState();
  const { id, status, until } = data;

  switch (status) {
    case "accepted":
      store.acceptNotification(id);
      break;
    case "dismissed":
      store.dismissNotification(id);
      break;
    case "snoozed":
      if (until) {
        store.snoozeNotification(id, until);
      }
      break;
    case "deleted":
      store.removeNotification(id);
      break;
    case "restored":
      store.restoreNotification(id);
      break;
    default:
      // 未知状态，尝试用 updateNotification 回退
      store.updateNotification(id, { status: status as SecretaryNotification["status"] });
      break;
  }
}

// ══════════════════════════════════════════════════════════════
//  单条操作（同步本地 + 后端）
// ══════════════════════════════════════════════════════════════

/**
 * 标记通知为已读
 */
export async function markNotificationRead(id: string): Promise<void> {
  useNotificationStore.getState().markRead(id);
  try {
    await api(`/api/secretary/proposals/${id}/dismiss`, { method: "POST" });
  } catch {
    // 静默失败
  }
}

/**
 * 接受通知（同步到后端，并捕获执行结果作为反馈）
 * @param navigate 是否自动导航到目标页面（默认 true）
 */
export async function acceptNotification(
  id: string,
  options?: { navigate?: boolean },
): Promise<void> {
  const store = useNotificationStore.getState();
  const notif = store.notifications.find((n) => n.id === id);

  store.acceptNotification(id);
  try {
    const body: any = await api(`/api/secretary/proposals/${id}/accept`, { method: "POST" });
    // 将执行结果存入 feedback，方便 UI 展示
    if (body.action_result || body.plan_adjustment) {
      store.addActionFeedback({
        id: `feedback_${id}`,
        proposalId: id,
        actionType: (notif?.actionType || "") as ActionType,
        title: notif?.title || "提案已执行",
        result: body.action_result || null,
        planAdjustment: body.plan_adjustment || null,
        timestamp: Date.now(),
      });
    }

    // 自动导航到目标页面
    const shouldNavigate = options?.navigate !== false;
    if (shouldNavigate && notif) {
      navigateToProposal({
        actionType: notif.actionType || "",
        payload: body.action_result?.payload || {},
        title: notif.title,
        description: notif.description,
        targetActionPath: notif.target?.actionPath,
      });
    }
  } catch {
    // 静默失败
  }
}

/**
 * 忽略通知（同步到后端）
 */
export async function dismissNotification(id: string): Promise<void> {
  useNotificationStore.getState().dismissNotification(id);
  try {
    await api(`/api/secretary/proposals/${id}/dismiss`, { method: "POST" });
  } catch {
    // 静默失败
  }
}

/**
 * 删除通知（从 store 移除 + 后端标记 deleted）
 */
export async function deleteNotification(id: string): Promise<void> {
  useNotificationStore.getState().removeNotification(id);
  try {
    await api(`/api/secretary/proposals/${id}/delete`, { method: "POST" });
  } catch {
    // 静默失败
  }
}

/**
 * 延后通知（本地 + 后端）
 * @param untilTimestamp 何时重新提醒（毫秒时间戳）
 */
export async function snoozeNotification(
  id: string,
  untilTimestamp: number,
): Promise<void> {
  useNotificationStore.getState().snoozeNotification(id, untilTimestamp);
  try {
    await api(`/api/secretary/proposals/${id}/snooze`, {
      method: "POST",
      body: JSON.stringify({ until: untilTimestamp }),
    });
  } catch {
    // 静默失败
  }
}

/**
 * 恢复通知（本地 + 后端）
 */
export async function restoreNotification(id: string): Promise<void> {
  useNotificationStore.getState().restoreNotification(id);
  try {
    await api(`/api/secretary/proposals/${id}/restore`, { method: "POST" });
  } catch {
    // 静默失败
  }
}

// ══════════════════════════════════════════════════════════════
//  批量操作
// ══════════════════════════════════════════════════════════════

/**
 * 批量接受通知
 */
export async function batchAcceptNotifications(
  ids: string[],
): Promise<void> {
  const store = useNotificationStore.getState();
  ids.forEach((id) => store.acceptNotification(id));
  try {
    await api("/api/secretary/proposals/batch-accept", {
      method: "POST",
      body: JSON.stringify({ ids }),
    });
  } catch {
    // 静默失败
  }
}

/**
 * 批量忽略通知
 */
export async function batchDismissNotifications(
  ids: string[],
): Promise<void> {
  const store = useNotificationStore.getState();
  ids.forEach((id) => store.dismissNotification(id));
  try {
    await api("/api/secretary/proposals/batch-dismiss", {
      method: "POST",
      body: JSON.stringify({ ids }),
    });
  } catch {
    // 静默失败
  }
}

// ══════════════════════════════════════════════════════════════
//  历史记录
// ══════════════════════════════════════════════════════════════

/**
 * 从后端拉取历史记录
 */
export async function fetchHistory(
  days: number = 7,
  filter?: NotificationFilter,
): Promise<NotificationHistoryItem[]> {
  const params = new URLSearchParams({ days: String(days) });
  if (filter?.sourceModule) params.set("source_module", filter.sourceModule);
  if (filter?.actionType) params.set("action_type", filter.actionType);
  try {
    return await api<NotificationHistoryItem[]>(`/api/secretary/proposals/history?${params}`);
  } catch {
    return [];
  }
}

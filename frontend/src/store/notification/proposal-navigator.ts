// ══════════════════════════════════════════════════════════════
//  ProposalNavigator — 提案采纳后自动导航与执行闭环
//
//  根据提案的动作类型和载荷，自动跳转到目标页面，
//  并在执行完成后回传结果到秘书系统。
// ══════════════════════════════════════════════════════════════

import type { ActionType } from "./types";
import { api } from "@/lib/api/api";

// ══════════════════════════════════════════════════════════════
//  Types
// ══════════════════════════════════════════════════════════════

export interface NavigationTarget {
  /** 目标 URL 路径 */
  path: string;
  /** 页面类型（用于通知路由） */
  page: string;
  /** 执行上下文，用于结果回传时识别 */
  context?: string;
}

export interface ProposalNavigationInput {
  actionType: ActionType | string;
  payload?: Record<string, unknown>;
  title?: string;
  description?: string;
  targetActionPath?: string;
}

export interface ExecutionResult {
  success: boolean;
  message: string;
  details?: string;
  completedAt?: number;
}

// ══════════════════════════════════════════════════════════════
//  Route mapping
// ══════════════════════════════════════════════════════════════

const ACTION_ROUTES: Record<string, (payload?: Record<string, unknown>) => NavigationTarget> = {
  review: (payload) => {
    const kpId = payload?.kp_id as string || "";
    const topic = payload?.topic as string || "";
    const params = new URLSearchParams();
    if (kpId) params.set("node_id", kpId);
    if (topic) params.set("negotiate", topic);
    const qs = params.toString();
    return {
      path: `/learn${qs ? `?${qs}` : ""}`,
      page: "learn",
      context: kpId || topic || "review",
    };
  },

  practice: (payload) => {
    const kpId = payload?.kp_id as string || "";
    const topic = payload?.topic as string || "";
    const params = new URLSearchParams();
    if (kpId) params.set("node_id", kpId);
    if (topic) params.set("topic", topic);
    const qs = params.toString();
    return {
      path: `/practice${qs ? `?${qs}` : ""}`,
      page: "practice",
      context: kpId || topic || "practice",
    };
  },

  explore: (payload) => {
    const kpId = payload?.kp_id as string || "";
    const topic = payload?.topic as string || "";
    const params = new URLSearchParams();
    if (kpId) params.set("node_id", kpId);
    if (topic) params.set("q", topic);
    const qs = params.toString();
    return {
      path: `/knowledge-tree${qs ? `?${qs}` : ""}`,
      page: "knowledge-tree",
      context: kpId || topic || "explore",
    };
  },

  exam_prep: (payload) => {
    const exam = payload?.exam as string || "";
    const params = new URLSearchParams();
    if (exam) params.set("exam", exam);
    params.set("mode", "exam_prep");
    const qs = params.toString();
    return {
      path: `/practice${qs ? `?${qs}` : ""}`,
      page: "practice",
      context: exam || "exam_prep",
    };
  },

  rest: () => ({
    path: "/dashboard",
    page: "dashboard",
    context: "rest",
  }),
};

// ══════════════════════════════════════════════════════════════
//  Navigator API
// ══════════════════════════════════════════════════════════════

/**
 * 根据提案信息计算出导航目标
 */
export function getNavigationTarget(input: ProposalNavigationInput): NavigationTarget | null {
  // 优先使用预设的 actionPath
  if (input.targetActionPath) {
    return {
      path: input.targetActionPath,
      page: "learn",
      context: input.title || "proposal",
    };
  }

  const mapper = ACTION_ROUTES[input.actionType];
  if (mapper) {
    return mapper(input.payload);
  }

  // 兜底：如果有 payload.route 字段
  if (input.payload?.route) {
    return {
      path: input.payload.route as string,
      page: "learn",
      context: input.title || "proposal",
    };
  }

  return null;
}

/**
 * 执行导航跳转
 * @returns true 如果跳转已触发
 */
export function navigateToProposal(input: ProposalNavigationInput): boolean {
  const target = getNavigationTarget(input);
  if (!target) return false;

  // 记录执行上下文（供后续回传使用）
  try {
    const ctx = {
      actionType: input.actionType,
      context: target.context,
      path: target.path,
      page: target.page,
      title: input.title,
      startedAt: Date.now(),
    };
    sessionStorage.setItem("proposal_navigation", JSON.stringify(ctx));
  } catch {
    // sessionStorage not available
  }

  // 执行跳转
  window.location.href = target.path;
  return true;
}

/**
 * 检查是否有未完成的提案导航（用于目标页面启动时检测）
 */
export function checkPendingProposalNavigation(): {
  actionType: string;
  context: string;
  path: string;
  page: string;
  title?: string;
  startedAt: number;
} | null {
  try {
    const raw = sessionStorage.getItem("proposal_navigation");
    if (!raw) return null;
    const ctx = JSON.parse(raw);
    // 只保留最近 30 秒内的导航
    if (Date.now() - ctx.startedAt > 30_000) {
      sessionStorage.removeItem("proposal_navigation");
      return null;
    }
    return ctx;
  } catch {
    return null;
  }
}

/**
 * 清除待处理的提案导航记录
 */
export function clearPendingProposalNavigation(): void {
  try {
    sessionStorage.removeItem("proposal_navigation");
  } catch {
    // ignore
  }
}

/**
 * 回传执行结果到秘书系统
 */
export async function reportProposalExecution(
  proposalId: string,
  result: ExecutionResult,
): Promise<void> {
  try {
    await api(`/api/secretary/proposals/${proposalId}/execution-result`, {
      method: "POST",
      body: JSON.stringify({
        success: result.success,
        message: result.message,
        details: result.details,
        completed_at: result.completedAt || Date.now(),
      }),
    });
  } catch {
    // 静默失败
  }
}
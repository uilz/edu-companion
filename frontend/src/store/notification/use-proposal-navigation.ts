// ══════════════════════════════════════════════════════════════
//  useProposalNavigation — 检测并处理提案导航
//
//  在目标页面（learn / practice / knowledge-tree）加载时调用，
//  检测是否有来自秘书系统的提案导航，显示执行上下文。
// ══════════════════════════════════════════════════════════════

"use client";

import { useEffect, useState } from "react";
import { checkPendingProposalNavigation, clearPendingProposalNavigation, reportProposalExecution } from "./proposal-navigator";

interface PendingContext {
  actionType: string;
  context: string;
  path: string;
  page: string;
  title?: string;
  startedAt: number;
  executed?: boolean;
}

/**
 * 检测并消费来自秘书系统提案导航的上下文
 *
 * 在目标页面组件中调用，例如：
 * ```tsx
 * const context = useProposalNavigation();
 * if (context) { showBanner(context.title); }
 * ```
 */
export function useProposalNavigation(): PendingContext | null {
  const [context, setContext] = useState<PendingContext | null>(null);

  useEffect(() => {
    const pending = checkPendingProposalNavigation();
    if (pending) {
      // 标记已消费
      clearPendingProposalNavigation();
      setContext({ ...pending, executed: true });
    }
  }, []);

  return context;
}

/**
 * 手动回传执行结果（在目标页面完成动作后调用）
 *
 * 示例：用户完成练习后回传结果
 * ```tsx
 * import { useReportExecution } from "./use-proposal-navigation";
 * const { report, reporting } = useReportExecution();
 * await report({ success: true, message: "练习完成，正确率80%", details: "8/10" });
 * ```
 */
export function useReportExecution() {
  const [reporting, setReporting] = useState(false);

  const report = async (result: { success: boolean; message: string; details?: string }) => {
    setReporting(true);
    try {
      const pending = checkPendingProposalNavigation();
      if (pending) {
        // 如果有待处理的导航，用通用 ID 回传
        await reportProposalExecution("proposal_from_navigation", {
          ...result,
          completedAt: Date.now(),
        });
      }
      // 也尝试从 URL 参数获取 proposal_id
      const params = new URLSearchParams(window.location.search);
      const proposalId = params.get("proposal_id");
      if (proposalId) {
        await reportProposalExecution(proposalId, {
          ...result,
          completedAt: Date.now(),
        });
      }
    } finally {
      setReporting(false);
    }
  };

  return { report, reporting };
}
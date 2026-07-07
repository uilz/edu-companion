"use client";

/**
 * Toast — 通用轻量操作反馈提示
 *
 * 用于：复制成功、删除成功、重命名成功、保存成功等用户级操作反馈。
 * 区别于 ActionFeedbackToast（那是 Secretary 提案执行结果专用）。
 *
 * 设计原则：
 * - 独立 store，避免污染 Secretary 通知流
 * - 自动消失（默认 2.5s）
 * - 4 种类型：success / info / warning / error
 * - 多条堆叠显示，最多 5 条
 */

import { create } from "zustand";
import { CheckCircle2, Info, AlertTriangle, XCircle, X } from "lucide-react";
import { useEffect, useState } from "react";

export type ToastType = "success" | "info" | "warning" | "error";

export interface Toast {
  id: string;
  type: ToastType;
  title: string;
  description?: string;
  /** 自动消失时间（ms），0 表示手动关闭 */
  duration?: number;
}

interface ToastState {
  toasts: Toast[];
  push: (toast: Omit<Toast, "id">) => string;
  remove: (id: string) => void;
  clear: () => void;
}

const MAX_TOASTS = 5;
const DEFAULT_DURATION = 2500;

export const useToastStore = create<ToastState>((set, get) => ({
  toasts: [],
  push: (toast) => {
    const id = `toast-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
    const t: Toast = { duration: DEFAULT_DURATION, ...toast, id };
    set((s) => {
      const next = [...s.toasts, t];
      // 限制最多 MAX_TOASTS 条
      return { toasts: next.length > MAX_TOASTS ? next.slice(-MAX_TOASTS) : next };
    });
    return id;
  },
  remove: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  clear: () => set({ toasts: [] }),
}));

/** 便捷调用方法（在非 React 上下文或 hooks 内使用） */
export const toast = {
  success: (title: string, description?: string) =>
    useToastStore.getState().push({ type: "success", title, description }),
  info: (title: string, description?: string) =>
    useToastStore.getState().push({ type: "info", title, description }),
  warning: (title: string, description?: string) =>
    useToastStore.getState().push({ type: "warning", title, description }),
  error: (title: string, description?: string) =>
    useToastStore.getState().push({ type: "error", title, description }),
};

/** 单条 Toast 视觉 */
function ToastItem({ t }: { t: Toast }) {
  const remove = useToastStore((s) => s.remove);
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    if (!t.duration || t.duration <= 0) return;
    const exitTimer = setTimeout(() => setExiting(true), t.duration - 200);
    const removeTimer = setTimeout(() => remove(t.id), t.duration);
    return () => {
      clearTimeout(exitTimer);
      clearTimeout(removeTimer);
    };
  }, [t.id, t.duration, remove]);

  const colors: Record<ToastType, { bg: string; border: string; text: string; icon: React.ReactNode }> = {
    success: {
      bg: "bg-success/10",
      border: "border-success/30",
      text: "text-success",
      icon: <CheckCircle2 size={16} />,
    },
    info: {
      bg: "bg-accent/10",
      border: "border-accent/30",
      text: "text-accent",
      icon: <Info size={16} />,
    },
    warning: {
      bg: "bg-warning/10",
      border: "border-warning/30",
      text: "text-warning",
      icon: <AlertTriangle size={16} />,
    },
    error: {
      bg: "bg-danger/10",
      border: "border-danger/30",
      text: "text-danger",
      icon: <XCircle size={16} />,
    },
  };
  const c = colors[t.type];

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid={`toast-${t.type}`}
      className={`
        flex items-start gap-2 rounded-lg border ${c.border} ${c.bg}
        px-3 py-2 shadow-md min-w-[240px] max-w-sm
        transition-all duration-200
        ${exiting ? "opacity-0 translate-x-2" : "opacity-100 translate-x-0"}
      `}
    >
      <span className={`flex-shrink-0 ${c.text} mt-0.5`}>{c.icon}</span>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium text leading-snug">{t.title}</div>
        {t.description && (
          <div className="mt-0.5 text-xs text-secondary leading-relaxed">
            {t.description}
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={() => remove(t.id)}
        className="flex-shrink-0 p-0.5 text-muted hover:text rounded"
        aria-label="关闭"
        style={{ minWidth: 28, minHeight: 28 }}
      >
        <X size={12} />
      </button>
    </div>
  );
}

/** Toast 容器 — 放在 AppShell 顶部即可全站可见 */
export function ToastHost() {
  const toasts = useToastStore((s) => s.toasts);
  if (toasts.length === 0) return null;
  return (
    <div
      data-testid="toast-host"
      className="fixed bottom-4 right-4 z-[60] flex flex-col gap-2 pointer-events-none"
    >
      {toasts.map((t) => (
        <div key={t.id} className="pointer-events-auto">
          <ToastItem t={t} />
        </div>
      ))}
    </div>
  );
}

export default ToastHost;

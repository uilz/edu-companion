'use client';

import { type ReactNode } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  action?: ReactNode;
}

/**
 * ErrorState — 统一错误状态展示组件
 * 用于页面级或区域级的错误展示，支持重试回调
 */
export default function ErrorState({
  title = '加载失败',
  message,
  onRetry,
  action,
}: ErrorStateProps) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[300px] p-8 text-center">
      <div className="w-14 h-14 rounded-full bg-error/10 flex items-center justify-center mb-4">
        <AlertCircle size={28} className="text-error" />
      </div>
      <h3 className="text-base font-semibold text-ink-primary mb-2">{title}</h3>
      {message && (
        <p className="text-sm text-ink-muted mb-6 max-w-sm">{message}</p>
      )}
      <div className="flex items-center gap-2">
        {onRetry && (
          <button
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm border border rounded-md hover:bg-surface transition-colors"
          >
            <RefreshCw size={14} />
            重试
          </button>
        )}
        {action}
      </div>
    </div>
  );
}
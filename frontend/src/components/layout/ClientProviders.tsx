'use client';
// 引入主题上下文 Provider，用于全局主题管理
import { ThemeProvider } from '@/contexts/ThemeContext';
// 引入错误边界组件，用于捕获子组件渲染时的异常
import ErrorBoundary from '@/components/ui/ErrorBoundary';

/**
 * ClientProviders — 客户端全局 Providers 封装组件
 * 将应用中需要的全局上下文 Provider 聚合在一起，包裹整个应用内容。
 * 当前聚合：
 *   1. ThemeProvider — 主题支持（亮色/暗色模式）
 *   2. ErrorBoundary — 全局错误边界，防止白屏崩溃
 */
export default function ClientProviders({ children }: { children: React.ReactNode }) {
  return (
    // 主题上下文 — 提供亮/暗主题切换能力
    <ThemeProvider>
      {/* 错误边界 — 捕获子组件中的未捕获异常，展示降级 UI */}
      <ErrorBoundary>
        {children}
      </ErrorBoundary>
    </ThemeProvider>
  );
}

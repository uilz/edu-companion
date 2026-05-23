'use client';

import { Component, type ReactNode } from 'react';

// ── 错误边界 Props 接口：子组件和可选的自定义 fallback ──
interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

// ── 错误边界 State 接口：记录是否出错以及错误详情 ──
interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

// ── ErrorBoundary 组件：捕获子组件渲染异常，防止白屏 ──
export default class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  // ── 构造函数：初始化状态为无错误 ──
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  // ── 静态生命周期方法：子组件抛出异常时更新状态，触发降级 UI ──
  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  // ── 渲染方法：有错误时展示 fallback 或默认错误 UI，无错误时正常渲染子组件 ──
  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center">
          <div className="text-5xl mb-4">😵</div>
          <h2 className="text-xl font-semibold text-red-500 mb-2">
            出了点问题
          </h2>
          <p className="text-gray-500 dark:text-gray-400 mb-4 max-w-md">
            {this.state.error?.message || '页面加载时发生错误'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            重试
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

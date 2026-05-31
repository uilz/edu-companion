'use client';
// 客户端组件标识 — 此组件只能在客户端渲染，因为它使用了客户端特有的交互和样式

import { type ReactNode } from 'react';

// EmptyState 组件的属性接口
interface EmptyStateProps {
  icon?: string;         // 可选：空状态展示的图标（默认值：📭）
  title: string;         // 必填：空状态的主标题
  description?: string;  // 可选：空状态的补充描述文字
  action?: ReactNode;    // 可选：用户可执行的操作按钮或链接
}

/**
 * EmptyState — 空状态展示组件
 * 用于列表无数据、搜索无结果、页面内容为空等场景，
 * 向用户提供友好的视觉反馈和可能的操作指引。
 */
export default function EmptyState({ icon = '📭', title, description, action }: EmptyStateProps) {
  return (
    // 外层容器：flex 居中布局，最小高度 300px，内边距 32px
    <div className="flex flex-col items-center justify-center min-h-[300px] p-8 text-center">
      {/* 图标区域：5xl 字号，降低不透明度以弱化视觉权重 */}
      <div className="text-5xl mb-4 opacity-60">{icon}</div>
      {/* 标题区域：lg 字号、半粗体，适配深色模式 */}
      <h3 className="text-lg font-semibold text-[var(--color-text)] dark:text-[var(--color-text)] mb-2">
        {title}
      </h3>
      {/* 描述区域：仅当 description 存在时渲染，限制最大宽度 */}
      {description && (
        <p className="text-sm text-[var(--color-text-muted)] dark:text-[var(--color-text-muted)] mb-6 max-w-sm">
          {description}
        </p>
      )}
      {/* 操作区域：仅当 action 存在时渲染 */}
      {action && <div>{action}</div>}
    </div>
  );
}

"use client";

import { ReactNode } from "react";
import { useDroppable } from "@dnd-kit/core";

export interface DroppableColumnProps {
  id: string;
  children: ReactNode;
  className?: string;
  activeClassName?: string;
}

/**
 * 通用可放置容器 (Task #89)
 *
 * 用于看板列、文件上传区等接收拖拽的场景。
 * 拖拽进入时合并 activeClassName 提供视觉反馈。
 */
export function DroppableColumn({
  id,
  children,
  className = "",
  activeClassName = "ring-2 ring-[var(--color-accent)] ring-offset-2 ring-offset-page",
}: DroppableColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <div
      ref={setNodeRef}
      className={`${className} ${isOver ? activeClassName : ""}`}
    >
      {children}
    </div>
  );
}

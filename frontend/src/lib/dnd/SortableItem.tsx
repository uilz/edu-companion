"use client";

import { ReactNode } from "react";
import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

export interface SortableItemProps {
  id: string;
  children: (handleProps: {
    listeners: ReturnType<typeof useSortable>["listeners"];
    attributes: ReturnType<typeof useSortable>["attributes"];
    setActivatorNodeRef: ReturnType<typeof useSortable>["setActivatorNodeRef"];
  }) => ReactNode;
  className?: string;
  disabled?: boolean;
}

/**
 * 通用可排序项 (Task #89)
 *
 * 用法：children 接收 handleProps，调用方把 listeners/attributes 绑到拖拽 handle。
 * 这样可以精确控制"哪个元素可拖"，避免整行可拖导致误操作。
 */
export function SortableItem({ id, children, className, disabled = false }: SortableItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id, disabled });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className={className}>
      {children({ listeners, attributes, setActivatorNodeRef })}
    </div>
  );
}

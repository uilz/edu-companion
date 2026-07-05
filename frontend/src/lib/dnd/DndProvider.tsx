"use client";

import { ReactNode, useState } from "react";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  DragStartEvent,
  DragOverlay,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  arrayMove,
} from "@dnd-kit/sortable";

export interface DndProviderProps<T extends { id: string }> {
  items: T[];
  onReorder: (newOrder: T[]) => void | Promise<void>;
  renderItem: (item: T, index: number) => ReactNode;
  renderOverlay?: (item: T) => ReactNode;
  className?: string;
  children?: ReactNode;
}

/**
 * 通用单列表 Sortable 容器 (Task #89)
 *
 * 包装 DndContext + SortableContext，简化同父级节点的重排。
 * - onReorder 在拖拽结束时调用，参数是重排后的数组
 * - renderItem 由调用方提供单条渲染函数（应使用 useSortable）
 * - DragOverlay 提供拖拽时的视觉反馈
 */
export function DndProvider<T extends { id: string }>({
  items,
  onReorder,
  renderItem,
  renderOverlay,
  className,
  children,
}: DndProviderProps<T>) {
  const [activeId, setActiveId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragStart = (e: DragStartEvent) => {
    setActiveId(String(e.active.id));
  };

  const handleDragEnd = (e: DragEndEvent) => {
    setActiveId(null);
    const { active, over } = e;
    if (!over || active.id === over.id) return;
    const oldIndex = items.findIndex((i) => i.id === active.id);
    const newIndex = items.findIndex((i) => i.id === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    const newOrder = arrayMove(items, oldIndex, newIndex);
    void onReorder(newOrder);
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={items.map((i) => i.id)}
        strategy={verticalListSortingStrategy}
      >
        <div className={className}>
          {items.map((item, idx) => renderItem(item, idx))}
          {children}
        </div>
      </SortableContext>
      <DragOverlay>
        {activeId && renderOverlay
          ? renderOverlay(items.find((i) => i.id === activeId)!)
          : null}
      </DragOverlay>
    </DndContext>
  );
}

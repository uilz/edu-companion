"use client";

// ============================================================
//  KanbanView — 4 列看板 (Task #89 新)
// ============================================================

import { Plus, GripVertical } from "lucide-react";
import {
  DndContext,
  closestCorners,
  PointerSensor,
  TouchSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  DragEndEvent,
  DragOverlay,
  useDroppable,
  useDraggable,
  type DraggableSyntheticListeners,
  type DraggableAttributes,
} from "@dnd-kit/core";
import { useState } from "react";
import {
  ProjectViewProps,
  ProjectNode,
  NODE_STATUS_COLUMNS,
  NodeStatusValue,
  NODE_TYPE_LABELS,
} from "../types";

export interface KanbanViewProps extends ProjectViewProps {
  onSetStatus: (nodeId: string, status: string) => void | Promise<void>;
}

interface ColumnData {
  status: NodeStatusValue;
  nodes: ProjectNode[];
}

export function KanbanView(props: KanbanViewProps) {
  const { nodes, onOpenNode, onAddNode, onSetStatus } = props;
  const [activeId, setActiveId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 150, tolerance: 5 } }),
    useSensor(KeyboardSensor),
  );

  // 按 status 分组
  const columns: ColumnData[] = NODE_STATUS_COLUMNS.map((col) => ({
    status: col.value,
    nodes: nodes
      .filter((n) => (n.status || "pending") === col.value)
      .sort((a, b) => a.order_in_parent - b.order_in_parent),
  }));

  const handleDragEnd = (e: DragEndEvent) => {
    setActiveId(null);
    const { active, over } = e;
    if (!over) return;
    const nodeId = String(active.id);
    const overId = String(over.id);
    // 拖到 column (overId = status value) 或拖到另一张卡片 (overId = node id)
    let targetStatus: NodeStatusValue | null = null;
    if ((NODE_STATUS_COLUMNS.map((c) => c.value) as string[]).includes(overId)) {
      targetStatus = overId as NodeStatusValue;
    } else {
      const overNode = nodes.find((n) => n.id === overId);
      if (overNode) targetStatus = (overNode.status || "pending") as NodeStatusValue;
    }
    if (!targetStatus) return;
    const node = nodes.find((n) => n.id === nodeId);
    if (!node || (node.status || "pending") === targetStatus) return;
    void onSetStatus(nodeId, targetStatus);
  };

  const activeNode = activeId ? nodes.find((n) => n.id === activeId) : null;

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-ink-secondary uppercase tracking-wider">
          看板视图
        </h3>
        <span className="text-xs text-ink-secondary">
          拖拽卡片跨列移动以更新状态
        </span>
      </div>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={(e) => setActiveId(String(e.active.id))}
        onDragEnd={handleDragEnd}
        onDragCancel={() => setActiveId(null)}
      >
        <div className="flex gap-3 overflow-x-auto pb-2">
          {columns.map((col) => (
            <KanbanColumn
              key={col.status}
              column={col}
              onOpenNode={onOpenNode}
              onAddNode={onAddNode}
            />
          ))}
        </div>
        <DragOverlay>
          {activeNode ? <KanbanCard node={activeNode} isOverlay /> : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}

function KanbanColumn({
  column,
  onOpenNode,
  onAddNode,
}: {
  column: ColumnData;
  onOpenNode: (n: ProjectNode) => void;
  onAddNode: (parentId: string | null, type: number) => void;
}) {
  const meta = NODE_STATUS_COLUMNS.find((c) => c.value === column.status)!;
  const { setNodeRef, isOver } = useDroppable({ id: column.status });
  return (
    <div
      ref={setNodeRef}
      className={`flex-shrink-0 w-72 border-l-4 ${meta.color} bg-surface border border-divider border-l-4 rounded-lg p-3 ${
        isOver ? "ring-2 ring-[var(--color-accent)]" : ""
      }`}
    >
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm font-semibold text-ink-primary">
          {meta.label} <span className="text-ink-secondary font-normal">({column.nodes.length})</span>
        </div>
        <button
          onClick={() => onAddNode(null, 1)}
          className="text-ink-secondary hover:text-[var(--color-accent)]"
          title="添加节点到此列"
        >
          <Plus size={14} />
        </button>
      </div>
      <div className="space-y-2 min-h-[80px]">
        {column.nodes.length === 0 ? (
          <div className="text-center text-ink-secondary text-xs py-4 opacity-50">
            拖入或新建
          </div>
        ) : (
          column.nodes.map((n) => <DraggableCard key={n.id} node={n} onOpen={onOpenNode} />)
        )}
      </div>
    </div>
  );
}

function DraggableCard({ node, onOpen }: { node: ProjectNode; onOpen: (n: ProjectNode) => void }) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, isDragging } = useDraggable({
    id: node.id,
  });
  return (
    <div
      ref={setNodeRef}
      style={{ opacity: isDragging ? 0.4 : 1 }}
      className="touch-none"
    >
      <KanbanCard
        node={node}
        onOpen={onOpen}
        dragHandle={{ setActivatorNodeRef, listeners, attributes }}
      />
    </div>
  );
}

function KanbanCard({
  node,
  onOpen,
  isOverlay = false,
  dragHandle,
}: {
  node: ProjectNode;
  onOpen?: (n: ProjectNode) => void;
  isOverlay?: boolean;
  dragHandle?: {
    setActivatorNodeRef: (el: HTMLElement | null) => void;
    listeners: DraggableSyntheticListeners;
    attributes: DraggableAttributes;
  };
}) {
  const typeInfo = NODE_TYPE_LABELS[node.type] || NODE_TYPE_LABELS[1];
  return (
    <div
      className={`rounded-lg bg-page border border-divider p-2.5 ${
        isOverlay ? "shadow-xl rotate-1" : "hover:border-[var(--color-accent)]"
      } transition`}
    >
      <div className="flex items-start gap-2">
        {dragHandle && (
          <button
            ref={dragHandle.setActivatorNodeRef}
            {...dragHandle.listeners}
            {...dragHandle.attributes}
            className="text-ink-secondary cursor-grab active:cursor-grabbing touch-none mt-0.5"
            title="拖拽"
          >
            <GripVertical size={12} />
          </button>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 text-[10px] text-ink-secondary mb-1">
            {typeInfo.icon}
            <span>{typeInfo.label}</span>
            <span>·</span>
            <span>v{node.version}</span>
          </div>
          <button
            onClick={() => onOpen?.(node)}
            className="text-sm text-ink-primary hover:text-[var(--color-accent)] text-left w-full line-clamp-2 font-medium"
          >
            {node.title || "(无标题)"}
          </button>
          {node.description && (
            <div className="text-[11px] text-ink-secondary mt-1 line-clamp-2">
              {node.description}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

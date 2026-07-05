"use client";

// ============================================================
//  DocumentView — 手稿/文档视图 (Task #89 新 + @引用跳转/高亮/Badge)
// ============================================================

import { useCallback, useMemo, useRef, useState } from "react";
import { Plus, FileText, CheckCircle2, Circle, Link2 } from "lucide-react";
import { ProjectViewProps, FlatNode, flattenTree, NODE_TYPE_LABELS, formatDate } from "../types";
import { SortableItem } from "@/lib/dnd/SortableItem";
import { DndProvider } from "@/lib/dnd/DndProvider";
import { parseNodeRefs, makeTitleResolver } from "@/lib/parseNodeRefs";
import type { DraggableSyntheticListeners, DraggableAttributes } from "@dnd-kit/core";

const HIGHLIGHT_DURATION_MS = 1500;

export function DocumentView(props: ProjectViewProps) {
  const { nodes, onOpenNode, onAddNode, onCompleteNode, onReorder } = props;
  const flat: FlatNode[] = flattenTree(nodes);
  const titleResolver = useMemo(() => makeTitleResolver(nodes), [nodes]);

  // 节点 DOM 引用表（用于跳转高亮）
  const nodeRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const setNodeRef = useCallback((id: string, el: HTMLDivElement | null) => {
    if (el) nodeRefs.current.set(id, el);
    else nodeRefs.current.delete(id);
  }, []);

  // 高亮目标 id（用于触发 1.5s 后清除）
  const [highlightedId, setHighlightedId] = useState<string | null>(null);
  const handleJumpToNode = useCallback(
    (nodeId: string) => {
      const el = nodeRefs.current.get(nodeId);
      if (!el) return;
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      setHighlightedId(nodeId);
      window.setTimeout(() => {
        setHighlightedId((prev) => (prev === nodeId ? null : prev));
      }, HIGHLIGHT_DURATION_MS);
    },
    [],
  );

  if (flat.length === 0) {
    return (
      <div>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-ink-secondary uppercase tracking-wider">
            手稿视图
          </h3>
          <button
            onClick={() => onAddNode(null, 1)}
            className="text-sm text-[var(--color-accent)] hover:opacity-80 flex items-center gap-1 whitespace-nowrap flex-shrink-0"
          >
            <Plus size={14} /> 根节点
          </button>
        </div>
        <div className="text-center text-ink-secondary py-20 border border-dashed border-divider rounded-lg">
          <FileText size={40} className="mx-auto mb-3 opacity-50" />
          <p>暂无节点。点击"根节点"开始书写你的研究手稿。</p>
          <p className="text-xs mt-2 text-ink-secondary">
            描述中可用 @[节点标题] 引用其他节点,点击跳转并高亮。
          </p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-ink-secondary uppercase tracking-wider">
          手稿视图
        </h3>
        <button
          onClick={() => onAddNode(null, 1)}
          className="text-sm text-[var(--color-accent)] hover:opacity-80 flex items-center gap-1 whitespace-nowrap flex-shrink-0"
        >
          <Plus size={14} /> 根节点
        </button>
      </div>
      <div className="max-w-3xl mx-auto">
        <DndProvider
          items={flat}
          onReorder={(newOrder) => {
            const byParent = new Map<string | null, FlatNode[]>();
            for (const n of newOrder) {
              const list = byParent.get(n.parent_id) || [];
              list.push(n);
              byParent.set(n.parent_id, list);
            }
            // 串行调用各父级的 reorder
            void (async () => {
              for (const [parentId, group] of Array.from(byParent)) {
                await onReorder(parentId, group);
              }
            })();
          }}
          renderItem={(node) => (
            <SortableItem id={node.id}>
              {({ listeners, attributes, setActivatorNodeRef }) => (
                <BlockRow
                  node={node}
                  allNodes={flat}
                  resolve={titleResolver}
                  onJumpRef={handleJumpToNode}
                  onEdit={onOpenNode}
                  onComplete={onCompleteNode}
                  isHighlighted={highlightedId === node.id}
                  registerRef={setNodeRef}
                  dragHandle={{ listeners, attributes, setActivatorNodeRef }}
                />
              )}
            </SortableItem>
          )}
          className="space-y-3"
        />
      </div>
    </div>
  );
}

interface BlockRowProps {
  node: FlatNode;
  allNodes: FlatNode[];
  resolve: (title: string) => string | undefined;
  onJumpRef: (nodeId: string) => void;
  onEdit: (n: FlatNode) => void;
  onComplete: (n: FlatNode) => void;
  isHighlighted: boolean;
  registerRef: (id: string, el: HTMLDivElement | null) => void;
  dragHandle: {
    listeners?: DraggableSyntheticListeners;
    attributes?: DraggableAttributes;
    setActivatorNodeRef?: (el: HTMLElement | null) => void;
  };
}

function BlockRow({
  node,
  allNodes,
  resolve,
  onJumpRef,
  onEdit,
  onComplete,
  isHighlighted,
  registerRef,
  dragHandle,
}: BlockRowProps) {
  const typeInfo = NODE_TYPE_LABELS[node.type] || NODE_TYPE_LABELS[1];
  const tokens = node.description ? parseNodeRefs(node.description, resolve) : [];
  const reverseCount = allNodes.filter(
    (x) => x.id !== node.id && (x.linked_node_ids || []).includes(node.id),
  ).length;

  return (
    <div
      ref={(el) => registerRef(node.id, el)}
      className={`rounded-lg border bg-surface hover:border-[var(--color-accent)] transition group p-4 ${
        isHighlighted
          ? "border-[var(--color-accent)] ring-2 ring-[var(--color-accent)]"
          : "border-divider"
      }`}
      style={{ marginLeft: `${node.depth * 24}px` }}
    >
      <div className="flex items-start gap-2">
        <button
          ref={dragHandle.setActivatorNodeRef}
          {...(dragHandle.listeners || {})}
          {...(dragHandle.attributes || {})}
          className="text-ink-secondary cursor-grab active:cursor-grabbing touch-none mt-1"
          title="拖拽重排"
        >
          <span className="text-xs">⋮⋮</span>
        </button>
        <span className="text-ink-secondary mt-0.5">{typeInfo.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <button
              onClick={() => onEdit(node)}
              className="text-ink-primary font-semibold hover:text-[var(--color-accent)] text-left flex-1 truncate"
              title="点击编辑节点"
            >
              {node.title || "(无标题)"}
            </button>
            <span className="text-xs text-ink-secondary flex-shrink-0">
              {typeInfo.label} · v{node.version} · {formatDate(node.updated_at)}
            </span>
            {reverseCount > 0 && (
              <span
                className="flex items-center gap-1 text-[10px] text-blue-500 whitespace-nowrap flex-shrink-0"
                title={`被 ${reverseCount} 个其他节点引用`}
              >
                <Link2 size={10} /> 被 {reverseCount} 引用
              </span>
            )}
            <button
              onClick={() => onComplete(node)}
              className="p-1 rounded text-ink-secondary hover:text-green-500 flex-shrink-0"
              title={node.completed_at ? "已完成" : "标记完成"}
            >
              {node.completed_at ? (
                <CheckCircle2 size={14} className="text-green-500" />
              ) : (
                <Circle size={14} />
              )}
            </button>
          </div>
          {node.description && (
            <div className="text-sm text-ink-secondary mt-2 whitespace-pre-wrap break-words">
              {tokens.map((t, i) =>
                t.type === "ref" && t.nodeId ? (
                  <button
                    key={i}
                    onClick={() => onJumpRef(t.nodeId!)}
                    className="text-[var(--color-accent)] hover:underline mx-0.5"
                    title="跳转到该节点"
                  >
                    {t.value}
                  </button>
                ) : (
                  <span key={i}>{t.value}</span>
                ),
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

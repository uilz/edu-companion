"use client";

// ============================================================
//  OutlineView — 大纲视图 (Task #89 增强: @引用 + 反向引用)
// ============================================================

import { useState } from "react";
import { Plus, Link2 } from "lucide-react";
import type { DraggableSyntheticListeners, DraggableAttributes } from "@dnd-kit/core";
import { ProjectViewProps, ProjectNode, getChildren, NODE_TYPE_LABELS } from "../types";
import { NodeRow } from "../components/NodeRow";
import { SortableItem } from "@/lib/dnd/SortableItem";
import { DndProvider } from "@/lib/dnd/DndProvider";
import { parseNodeRefs, makeTitleResolver } from "@/lib/parseNodeRefs";
import { useProjectData } from "../hooks/useProjectData";

export function OutlineView(props: ProjectViewProps & { projectId: string }) {
  const { nodes, onOpenNode, onAddNode, onCompleteNode, onReorder, projectId } = props;
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const { reorderNodes } = useProjectData(projectId);
  void reorderNodes; // 用作类型占位（不直接在此处用）

  const toggle = (id: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const titleResolver = makeTitleResolver(nodes);

  const renderNode = (node: ProjectNode, depth: number) => {
    const children = getChildren(nodes, node.id);
    const hasChildren = children.length > 0;
    const isExpanded = expanded.has(node.id);

    return (
      <div key={node.id}>
        <NodeRow
          node={node}
          depth={depth}
          hasChildren={hasChildren}
          isExpanded={isExpanded}
          onToggle={() => toggle(node.id)}
          onOpen={() => onOpenNode(node)}
          onAddChild={() => onAddNode(node.id, 2)}
          onComplete={() => onCompleteNode(node)}
          showDescription={false}
        />
        {/* 描述 + @引用渲染 + 反向引用 badge */}
        {node.description && (
          <div
            className="ml-12 mr-4 text-xs text-ink-secondary mb-1"
            style={{ paddingLeft: `${depth * 16}px` }}
          >
            <DescriptionWithRefs text={node.description} resolve={titleResolver} onJump={onOpenNode} nodes={nodes} />
          </div>
        )}
        {isExpanded && children.map((c) => renderNode(c, depth + 1))}
      </div>
    );
  };

  const rootNodes = getChildren(nodes, null);
  // 用 dnd-kit 包装根节点重排
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-ink-secondary uppercase tracking-wider">
          大纲视图
        </h3>
        <button
          onClick={() => onAddNode(null, 1)}
          className="text-sm text-accent hover:opacity-80 flex items-center gap-1 whitespace-nowrap flex-shrink-0"
        >
          <Plus size={14} /> 根节点
        </button>
      </div>
      {rootNodes.length === 0 ? (
        <div className="text-center text-ink-secondary py-12 border border-divider rounded-lg bg-surface">
          暂无节点。点击"根节点"开始构建大纲。
        </div>
      ) : (
        <DndProvider
          items={rootNodes}
          onReorder={(newOrder) => onReorder(null, newOrder)}
          renderItem={(node) => (
            <SortableItem id={node.id}>
              {({ listeners, attributes, setActivatorNodeRef }) => (
                <div>{renderNodeWithHandle(node, 0, listeners, attributes, setActivatorNodeRef)}</div>
              )}
            </SortableItem>
          )}
          className="border border-divider rounded-lg bg-surface p-2 min-h-[400px]"
        />
      )}
    </div>
  );

  function renderNodeWithHandle(
    node: ProjectNode,
    depth: number,
    listeners: DraggableSyntheticListeners,
    attributes: DraggableAttributes,
    setActivatorNodeRef: (el: HTMLElement | null) => void,
  ) {
    const children = getChildren(nodes, node.id);
    const hasChildren = children.length > 0;
    const isExpanded = expanded.has(node.id);
    return (
      <div>
        <NodeRow
          node={node}
          depth={depth}
          hasChildren={hasChildren}
          isExpanded={isExpanded}
          onToggle={() => toggle(node.id)}
          onOpen={() => onOpenNode(node)}
          onAddChild={() => onAddNode(node.id, 2)}
          onComplete={() => onCompleteNode(node)}
          showDescription={false}
          dragHandleProps={{ listeners, attributes, setActivatorNodeRef }}
        />
        {node.description && (
          <div
            className="ml-12 mr-4 text-xs text-ink-secondary mb-1"
            style={{ paddingLeft: `${depth * 16}px` }}
          >
            <DescriptionWithRefs
              text={node.description}
              resolve={titleResolver}
              onJump={onOpenNode}
              nodes={nodes}
              currentId={node.id}
            />
          </div>
        )}
        {isExpanded && children.map((c) => renderNode(c, depth + 1))}
      </div>
    );
  }
}

// ── 描述渲染：@引用 + 反向引用 ──

function DescriptionWithRefs({
  text,
  resolve,
  onJump,
  nodes,
  currentId,
}: {
  text: string;
  resolve: (title: string) => string | undefined;
  onJump: (n: ProjectNode) => void;
  nodes: ProjectNode[];
  currentId?: string;
}) {
  const tokens = parseNodeRefs(text, resolve);
  // 反向引用：哪些节点引用了 currentId？
  const reverseCount = currentId
    ? nodes.filter((n) => (n.linked_node_ids || []).includes(currentId)).length
    : 0;
  return (
    <div className="flex items-start gap-2">
      <div className="flex-1 whitespace-pre-wrap break-words">
        {tokens.map((t, i) =>
          t.type === "ref" && t.nodeId ? (
            <button
              key={i}
              onClick={() => {
                const target = nodes.find((n) => n.id === t.nodeId);
                if (target) onJump(target);
              }}
              className="text-accent hover:underline mx-0.5"
            >
              {t.value}
            </button>
          ) : (
            <span key={i}>{t.value}</span>
          ),
        )}
      </div>
      {reverseCount > 0 && (
        <span className="flex items-center gap-1 text-[10px] text-info whitespace-nowrap flex-shrink-0">
          <Link2 size={10} /> 被 {reverseCount} 节点引用
        </span>
      )}
    </div>
  );
}

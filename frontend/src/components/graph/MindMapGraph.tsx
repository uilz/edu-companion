"use client";

import React, { useRef, useEffect, useState } from "react";
import type { GraphData, GraphNode } from "@/lib/graph-types";
import { getMasteryColor } from "@/lib/graph-types";
import { ChevronRight, ChevronDown } from "lucide-react";

interface MindMapGraphProps {
  data: GraphData;
  selectedNodeId?: string;
  onNodeSelect?: (node: GraphNode) => void;
  width: number;
  height: number;
}

// Build tree from flat graph data (parent-child)
function buildTree(nodes: GraphNode[], edges: GraphData["edges"]) {
  const childrenMap = new Map<string, GraphNode[]>();
  const rootNodes: GraphNode[] = [];

  for (const node of nodes) {
    if (node.parent && nodes.find((n) => n.id === node.parent)) {
      const siblings = childrenMap.get(node.parent) || [];
      siblings.push(node);
      childrenMap.set(node.parent, siblings);
    } else {
      rootNodes.push(node);
    }
  }

  return { rootNodes, childrenMap };
}

interface TreeNode extends GraphNode {
  depth: number;
  x: number;
  y: number;
  collapsed: boolean;
}

export default function MindMapGraph({
  data,
  selectedNodeId,
  onNodeSelect,
}: MindMapGraphProps) {
  const { rootNodes, childrenMap } = buildTree(data.nodes, data.edges);
  const [treeNodes, setTreeNodes] = useState<TreeNode[]>([]);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const toggleCollapse = useRef((id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  });

  // Flatten tree with layout
  useEffect(() => {
    const flat: TreeNode[] = [];
    const xStep = 220;
    const yStep = 40;
    const startY = 60;

    function walk(node: GraphNode, depth: number, y: number) {
      const isCollapsed = collapsed.has(node.id);
      flat.push({ ...node, depth, x: depth * xStep + 20, y, collapsed: isCollapsed });

      if (!isCollapsed) {
        const children = childrenMap.get(node.id) || [];
        let cy = y - ((children.length - 1) * yStep) / 2;
        for (const child of children) {
          walk(child, depth + 1, cy);
          cy += yStep;
        }
      }
    }

    for (const root of rootNodes) {
      walk(root, 0, startY + flat.length * yStep);
    }

    setTreeNodes(flat);
  }, [data, collapsed, rootNodes, childrenMap]);

  return (
    <svg width="100%" height="100%" className="overflow-visible">
      {/* Edges */}
      {treeNodes.map((node) => {
        if (!node.parent) return null;
        const parent = treeNodes.find((n) => n.id === node.parent);
        if (!parent) return null;
        return (
          <line
            key={`edge-${node.id}`}
            x1={parent.x}
            y1={parent.y}
            x2={node.x}
            y2={node.y}
            stroke="var(--color-border)"
            strokeWidth={1.5}
            strokeOpacity={0.5}
          />
        );
      })}

      {/* Nodes */}
      {treeNodes.map((node) => {
        const isSelected = node.id === selectedNodeId;
        const hasChildren = (childrenMap.get(node.id) || []).length > 0;
        const isCollapsed = collapsed.has(node.id);

        return (
          <g
            key={node.id}
            onClick={() => onNodeSelect?.(node)}
            style={{ cursor: "pointer" }}
          >
            {/* Horizontal connector line */}
            {node.parent && (
              <line
                x1={node.x - 10}
                y1={node.y}
                x2={node.x}
                y2={node.y}
                stroke="var(--color-border)"
                strokeWidth={1}
              />
            )}

            {/* Mastery bar */}
            <rect
              x={node.x}
              y={node.y - 6}
              width={80}
              height={12}
              rx={6}
              fill="var(--color-surface-hover)"
            />
            <rect
              x={node.x}
              y={node.y - 6}
              width={Math.max(node.mastery * 80, 4)}
              height={12}
              rx={6}
              fill={getMasteryColor(node.mastery)}
              opacity={0.8}
            />

            {/* Label */}
            <text
              x={node.x + 88}
              y={node.y + 1}
              fontSize={12}
              fill={isSelected ? "var(--color-accent)" : "var(--color-text)"}
              fontWeight={isSelected ? 600 : 400}
              dominantBaseline="middle"
            >
              {node.emoji} {node.label}
            </text>

            {/* Trend indicator */}
            <text
              x={node.x + 84}
              y={node.y - 12}
              fontSize={9}
              fill="var(--color-text-muted)"
              textAnchor="end"
            >
              {node.trend === "ascending" ? "↑" : node.trend === "descending" ? "↓" : ""}
              {Math.round(node.mastery * 100)}%
            </text>

            {/* Collapse toggle */}
            {hasChildren && (
              <text
                x={node.x - 4}
                y={node.y - 12}
                fontSize={10}
                fill="var(--color-text-muted)"
                textAnchor="end"
                style={{ cursor: "pointer" }}
                onClick={(e) => {
                  e.stopPropagation();
                  toggleCollapse.current(node.id);
                }}
              >
                {isCollapsed ? "▶" : "▼"}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

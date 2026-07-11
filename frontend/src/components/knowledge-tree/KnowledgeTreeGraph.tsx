"use client";

import React, { useEffect, useRef } from "react";
import { Graph, CommonEvent, NodeEvent } from "@antv/g6";
import type { GraphData, NodeData, EdgeData } from "@antv/g6";
import type { TreeNode, TreeEdge } from "@/lib/api/knowledge-trees-api";

export type TreeViewMode = "tree" | "graph" | "mindmap" | "force" | "dag";

export interface TreeGraphData {
  nodes: TreeNode[];
  edges: TreeEdge[];
}

export interface KnowledgeTreeGraphProps {
  data: TreeGraphData;
  viewMode: TreeViewMode;
  selectedNodeId?: string | null;
  width: number;
  height: number;
  onNodeClick?: (node: TreeNode) => void;
  onNodeDoubleClick?: (node: TreeNode) => void;
  onNodeContextMenu?: (node: TreeNode, e: MouseEvent) => void;
  onCanvasClick?: () => void;
}

const DEFAULT_NODE_FILL = "#64748b";
const DEFAULT_NODE_SIZE = 24;
const SELECTED_STROKE = "#6366f1";

function getNodeStyle(node: TreeNode, isSelected: boolean) {
  const cv = node.cognitive_view;
  const fill = cv?.display_color ?? node.color ?? DEFAULT_NODE_FILL;
  const baseSize = cv?.display_size ?? 1;
  const size = Math.max(18, Math.round(DEFAULT_NODE_SIZE * baseSize));
  const glow = cv?.display_glow ?? false;

  return {
    fill,
    size,
    stroke: isSelected ? SELECTED_STROKE : "#1e293b",
    lineWidth: isSelected ? 3 : 1.5,
    labelFill: "#e2e8f0",
    labelFontSize: 12,
    labelFontWeight: 500,
    labelOffsetY: size / 2 + 10,
    halo: glow,
    haloLineWidth: glow ? 4 : 0,
    haloStroke: fill,
    haloOpacity: glow ? 0.35 : 0,
    cursor: "pointer",
  };
}

function getEdgeStyle(edge: TreeEdge) {
  const isPrereq = edge.edge_type === "prerequisite";
  const isRelated = edge.edge_type === "related";
  return {
    stroke: isPrereq ? "#f59e0b" : isRelated ? "#64748b" : "#475569",
    lineWidth: 1 + (edge.strength ?? 1) * 1.5,
    lineDash: isRelated ? [4, 4] : undefined,
    endArrow: true,
    endArrowSize: 6,
    labelFill: "#94a3b8",
    labelFontSize: 10,
  };
}

function buildG6Data(data: TreeGraphData, selectedNodeId?: string | null): GraphData {
  const nodes: NodeData[] = data.nodes.map((node) => ({
    id: node.id,
    data: {
      ...node,
      label: node.label || node.id.slice(-6),
    },
    style: getNodeStyle(node, node.id === selectedNodeId) as unknown as NodeData["style"],
  }));

  const edges: EdgeData[] = data.edges.map((edge) => ({
    id: edge.id,
    source: edge.source_node_id,
    target: edge.target_node_id,
    data: {
      ...edge,
      label: edge.edge_type,
    },
    style: getEdgeStyle(edge) as unknown as EdgeData["style"],
  }));

  return { nodes, edges };
}

function getLayoutSpec(viewMode: TreeViewMode) {
  if (viewMode === "tree") {
    return {
      type: "mindmap",
      direction: "H",
      getWidth: () => 160,
      getHeight: () => 50,
      getVGap: () => 30,
      getHGap: () => 80,
    } as const;
  }
  return {
    type: "force",
    preventOverlap: true,
    linkDistance: 120,
    nodeSize: 40,
  } as const;
}

export default function KnowledgeTreeGraph({
  data,
  viewMode,
  selectedNodeId,
  width,
  height,
  onNodeClick,
  onNodeDoubleClick,
  onNodeContextMenu,
  onCanvasClick,
}: KnowledgeTreeGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<Graph | null>(null);

  // Initialize graph once
  useEffect(() => {
    if (!containerRef.current || graphRef.current) return;

    const graph = new Graph({
      container: containerRef.current,
      width,
      height,
      background: "transparent",
      autoResize: true,
      data: { nodes: [], edges: [] },
      node: {
        type: "circle",
        style: {
          labelText: (d: any) => d.data.label,
        },
      },
      edge: {
        type: "line",
        style: {
          endArrow: true,
        },
      },
      layout: getLayoutSpec(viewMode),
      behaviors: ["drag-canvas", "zoom-canvas", "drag-element", "click-select"],
      plugins: [
        {
          type: "tooltip",
          getContent: (_e: any, items: any) => {
            const node = items?.[0]?.data as TreeNode | undefined;
            if (!node) return "";
            const cv = node.cognitive_view;
            return `
              <div style="padding:8px 10px;font-size:12px;color:#e2e8f0;background:#0f172a;border:1px solid #334155;border-radius:6px;max-width:240px;">
                <div style="font-weight:600;margin-bottom:4px;">${node.label}</div>
                ${cv ? `
                  <div>掌握度: ${Math.round(cv.proficiency * 100)}%</div>
                  <div>紧迫度: ${Math.round(cv.urgency * 100)}%</div>
                  <div>不确定性: ${Math.round(cv.uncertainty * 100)}%</div>
                ` : "<div style=\"color:#94a3b8\">未关联认知节点</div>"}
              </div>
            `;
          },
        },
      ],
    });

    graph.on(NodeEvent.CLICK, (evt: any) => {
      const node = evt?.target?.data?.data as TreeNode | undefined;
      if (node) onNodeClick?.(node);
    });

    graph.on(NodeEvent.DBLCLICK, (evt: any) => {
      const node = evt?.target?.data?.data as TreeNode | undefined;
      if (node) onNodeDoubleClick?.(node);
    });

    graph.on(NodeEvent.CONTEXT_MENU, (evt: any) => {
      const originalEvent = evt?.originalEvent as MouseEvent | undefined;
      const node = evt?.target?.data?.data as TreeNode | undefined;
      if (node && originalEvent) {
        originalEvent.preventDefault();
        onNodeContextMenu?.(node, originalEvent);
      }
    });

    graph.on(CommonEvent.CLICK, (evt: any) => {
      if (evt?.target?.type === "canvas") {
        onCanvasClick?.();
      }
    });

    graphRef.current = graph;
    graph.render();

    return () => {
      graph.destroy();
      graphRef.current = null;
    };
  }, []);

  // Update size
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.setSize(width, height);
  }, [width, height]);

  // Update data / selection
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.setData(buildG6Data(data, selectedNodeId));
    graph.render();
  }, [data, selectedNodeId]);

  // Update layout on view mode change
  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.setLayout(getLayoutSpec(viewMode));
    graph.render();
  }, [viewMode]);

  return <div ref={containerRef} className="w-full h-full" />;
}

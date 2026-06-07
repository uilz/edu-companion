"use client";

import React, { useMemo, useState, useCallback, useRef, useEffect } from "react";
import type { GraphData, GraphNode, GraphEdge } from "@/lib/types/graph-types";
import {
  getMasteryColor, getEdgeColor, getEdgeDash,
} from "@/lib/types/graph-types";
import { ZoomIn, ZoomOut, Maximize2 } from "lucide-react";

interface DAGGraphProps {
  data: GraphData;
  selectedNodeId?: string;
  onNodeSelect?: (node: GraphNode) => void;
  onNodeContextMenu?: (node: GraphNode, e: React.MouseEvent) => void;
  width: number;
  height: number;
  activePath?: string[];
  searchQuery?: string;
  matchedNodeIds?: string[];
}

interface DAGLayoutNode extends GraphNode {
  x: number;
  y: number;
  layer: number;
}

// ── 拓扑分层布局 ──
function computeDAGLayout(data: GraphData, width: number, height: number): {
  nodes: DAGLayoutNode[];
  edges: GraphEdge[];
} {
  if (!data.nodes.length) return { nodes: [], edges: [] };

  // 只使用 prerequisite 边进行拓扑排序
  const prereqEdges = data.edges.filter(e => e.relation === "prerequisite" || !e.relation);
  const inDegree = new Map<string, number>();
  const outEdges = new Map<string, string[]>();
  data.nodes.forEach(n => { inDegree.set(n.id, 0); outEdges.set(n.id, []); });
  prereqEdges.forEach(e => {
    inDegree.set(e.target, (inDegree.get(e.target) || 0) + 1);
    outEdges.get(e.source)?.push(e.target);
  });

  // 拓扑排序
  const layers: string[][] = [];
  const visited = new Set<string>();
  let queue = data.nodes.filter(n => (inDegree.get(n.id) || 0) === 0).map(n => n.id);
  while (queue.length > 0) {
    layers.push([...queue]);
    const next: string[] = [];
    for (const id of queue) {
      visited.add(id);
      for (const child of outEdges.get(id) || []) {
        const deg = (inDegree.get(child) || 1) - 1;
        inDegree.set(child, deg);
        if (deg === 0 && !visited.has(child)) next.push(child);
      }
    }
    queue = next;
  }

  // 未拓扑到的（环形依赖）放到最后一层
  const remaining = data.nodes.filter(n => !visited.has(n.id));
  if (remaining.length > 0) layers.push(remaining.map(n => n.id));

  if (layers.length === 0) return { nodes: [], edges: [] };

  // 计算每层最大宽度
  const maxInLayer = Math.max(...layers.map(l => l.length));
  const layerH = Math.max(120, Math.min(200, (height - 80) / Math.max(layers.length, 1)));
  const nodeW = 160;
  const nodeH = 64;
  const hGap = Math.min(40, (width - nodeW - 40) / Math.max(maxInLayer, 1));

  const result: DAGLayoutNode[] = [];
  layers.forEach((layerIds, li) => {
    const totalW = layerIds.length * (nodeW + hGap) - hGap;
    const startX = Math.max(20, (width - totalW) / 2);
    layerIds.forEach((id, ni) => {
      const node = data.nodes.find(n => n.id === id);
      if (!node) return;
      result.push({
        ...node,
        x: startX + ni * (nodeW + hGap),
        y: 40 + li * layerH,
        layer: li,
      });
    });
  });

  return { nodes: result, edges: data.edges };
}

export default function DAGGraph({
  data, selectedNodeId, onNodeSelect, onNodeContextMenu, width, height,
  activePath = [], searchQuery, matchedNodeIds,
}: DAGGraphProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);

  const nodeW = 160;
  const nodeH = 64;

  const { nodes: layout, edges } = useMemo(
    () => computeDAGLayout(data, width, height),
    [data, width, height],
  );

  const matchedSet = useMemo(() => matchedNodeIds ? new Set(matchedNodeIds) : null, [matchedNodeIds]);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setZoom(z => Math.min(3, Math.max(0.3, z * delta)));
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if ((e.target as Element).closest("[data-node-id]")) return;
    setIsPanning(true);
    panStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    e.preventDefault();
  }, [pan]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isPanning) return;
      setPan({ x: e.clientX - panStart.current.x, y: e.clientY - panStart.current.y });
    };
    const onUp = () => setIsPanning(false);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, [isPanning]);

  const resetView = useCallback(() => { setZoom(1); setPan({ x: 0, y: 0 }); }, []);

  return (
    <div className="relative w-full h-full select-none">
      {/* Controls */}
      <div className="absolute top-3 right-3 z-10 flex gap-1">
        <button onClick={() => setZoom(z => Math.min(3, z * 1.2))}
          className="w-7 h-7 flex items-center justify-center rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
          <ZoomIn size={13} />
        </button>
        <button onClick={() => setZoom(z => Math.max(0.3, z / 1.2))}
          className="w-7 h-7 flex items-center justify-center rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
          <ZoomOut size={13} />
        </button>
        <button onClick={resetView}
          className="w-7 h-7 flex items-center justify-center rounded bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
          <Maximize2 size={13} />
        </button>
      </div>

      <svg
        ref={svgRef}
        className="w-full h-full cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onWheel={handleWheel}
      >
        <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
          {/* Edges */}
          {edges.map((edge) => {
            const src = layout.find(n => n.id === edge.source);
            const tgt = layout.find(n => n.id === edge.target);
            if (!src || !tgt) return null;
            const color = getEdgeColor(edge.relation || "prerequisite");
            const dash = getEdgeDash(edge.relation || "prerequisite");
            const onPath = activePath.includes(edge.source) && activePath.includes(edge.target);
            return (
              <g key={edge.id}>
                <defs>
                  <marker id={`dag-arr-${edge.id}`} viewBox="0 -5 10 10" refX={nodeW} refY={0}
                    markerWidth={6} markerHeight={6} orient="auto">
                    <path d="M0,-5L10,0L0,5" fill={color} opacity={0.6} />
                  </marker>
                </defs>
                <line
                  x1={src.x + nodeW} y1={src.y + nodeH / 2}
                  x2={tgt.x} y2={tgt.y + nodeH / 2}
                  stroke={color} strokeWidth={onPath ? 2.5 : 1.5}
                  strokeOpacity={onPath ? 0.9 : 0.5}
                  strokeDasharray={dash || undefined}
                  markerEnd={`url(#dag-arr-${edge.id})`}
                  className="pointer-events-none"
                />
                {edge.label && (
                  <text x={(src.x + nodeW + tgt.x) / 2} y={(src.y + tgt.y) / 2 - 8}
                    textAnchor="middle" fill={color} fontSize={8} opacity={0.6}
                    className="pointer-events-none">
                    {edge.label}
                  </text>
                )}
              </g>
            );
          })}

          {/* Nodes */}
          {layout.map((n) => {
            const isSel = n.id === selectedNodeId;
            const isOnPath = activePath.includes(n.id);
            const isHovered = n.id === hoveredId;
            const isMatched = matchedSet?.has(n.id);
            const mColor = getMasteryColor(n.mastery);

            return (
              <g key={n.id} data-node-id={n.id}
                onClick={() => onNodeSelect?.(n)}
                onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); onNodeContextMenu?.(n, e); }}
                onMouseEnter={() => setHoveredId(n.id)}
                onMouseLeave={() => setHoveredId(null)}
                style={{ cursor: "pointer" }}
                opacity={isSel || isOnPath || isHovered || isMatched ? 1 : 0.55}
                className="transition-opacity"
              >
                {/* Search glow */}
                {isMatched && (
                  <rect x={n.x - 3} y={n.y - 3} width={nodeW + 6} height={nodeH + 6} rx={8}
                    fill="var(--color-accent)" opacity={0.08} className="animate-pulse" />
                )}

                {/* Card */}
                <rect x={n.x} y={n.y} width={nodeW} height={nodeH} rx={8}
                  fill={isSel ? "var(--color-accent)" : "var(--color-surface)"}
                  stroke={isSel ? "var(--color-accent)" : isOnPath ? "var(--color-accent)" : "var(--color-border)"}
                  strokeWidth={isSel ? 2 : isOnPath ? 1.5 : 1}
                  filter={isHovered && !isSel ? "drop-shadow(0 2px 4px rgba(0,0,0,0.08))" : undefined}
                />

                {/* Mastery dot */}
                <circle cx={n.x + 10} cy={n.y + 14} r={4} fill={mColor} />

                {/* Priority badge */}
                <text x={n.x + nodeW - 8} y={n.y + 14} fontSize={8}
                  fill={isSel ? "rgba(255,255,255,0.6)" : "var(--color-text-muted)"}
                  textAnchor="end">P{n.priority || "-"}</text>

                {/* Label */}
                <text x={n.x + 8} y={n.y + 32} fontSize={10}
                  fill={isSel ? "#fff" : "var(--color-text)"} fontWeight={600}
                  textLength={nodeW - 20} lengthAdjust="spacingAndGlyphs">
                  {n.label}
                </text>

                {/* Tags */}
                {n.tags?.length > 0 && (
                  <text x={n.x + 8} y={n.y + 50} fontSize={7}
                    fill={isSel ? "rgba(255,255,255,0.5)" : "var(--color-text-muted)"}
                    textLength={nodeW - 20} lengthAdjust="spacingAndGlyphs">
                    {n.tags.slice(0, 2).join(" · ")}
                  </text>
                )}

                {/* Layer indicator */}
                <text x={n.x + nodeW - 8} y={n.y + nodeH - 6} fontSize={7}
                  fill={isSel ? "rgba(255,255,255,0.4)" : "var(--color-text-muted)"}
                  textAnchor="end">L{n.layer}</text>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}

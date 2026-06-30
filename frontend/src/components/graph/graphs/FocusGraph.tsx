"use client";

import React, { useMemo, useState, useCallback, useRef, useEffect } from "react";
import type { GraphData, GraphNode } from "@/lib/types/graph-types";
import { getMasteryColor } from "@/lib/types/graph-types";
import { ChevronRight, ChevronDown, ChevronUp } from "lucide-react";

interface FocusGraphProps {
  data: GraphData;
  selectedNodeId?: string;
  onNodeSelect?: (node: GraphNode, pos?: { x: number; y: number }) => void;
  onFocusNode?: (nodeId: string) => void;
  onNodeContextMenu?: (node: GraphNode, e: React.MouseEvent) => void;
  activePath: string[];
  width: number;
  height: number;
  searchQuery?: string;
  matchedNodeIds?: string[];
  /** 在正确位置渲染节点弹出层，位置会随视图变化自动更新 */
  renderNodePopup?: (pos: { x: number; y: number }) => React.ReactNode;
}

// ── Tree builder ──
function buildTree(nodes: GraphNode[]) {
  const children = new Map<string, GraphNode[]>();
  const roots: GraphNode[] = [];
  const levels = new Set(["partition", "domain", "topic", "concept", "atom"]);
  const tree = nodes.filter((n) => levels.has(n.level));
  for (const n of tree) {
    if (n.parent && tree.some((t) => t.id === n.parent)) {
      const sib = children.get(n.parent) || [];
      sib.push(n);
      children.set(n.parent, sib);
    } else roots.push(n);
  }
  return { children, roots, treeSet: new Set(tree.map((t) => t.id)) };
}

interface LNode extends GraphNode {
  x: number; y: number; depth: number; isLeaf: boolean; childrenCount: number;
}

const CARD_W = 175;
const CARD_H = 118;
const H_GAP = 56;
const V_GAP = 20;

interface ViewTransform { x: number; y: number; scale: number; }

export default function FocusGraph({
  data, selectedNodeId, onNodeSelect, onFocusNode, onNodeContextMenu, activePath, width, height, searchQuery, matchedNodeIds, renderNodePopup,
}: FocusGraphProps) {
  const { children, roots, treeSet } = useMemo(() => buildTree(data.nodes), [data.nodes]);
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  // ── Pan / Zoom ──
  const [view, setView] = useState<ViewTransform>({ x: 0, y: 0, scale: 1 });
  const viewRef = useRef(view);
  viewRef.current = view;
  const isDragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const viewStart = useRef({ x: 0, y: 0 });

  // ── Collapse ──
  const [collapsed, setCollapsed] = useState<Set<string>>(() => {
    const s = new Set<string>();
    const expandUpTo = 2;
    const walk = (id: string, depth: number) => {
      s.delete(id);
      if (depth >= expandUpTo && !activePath.includes(id)) return;
      for (const c of children.get(id) || []) walk(c.id, depth + 1);
    };
    for (const r of roots) walk(r.id, 0);
    for (const r of roots) {
      if (activePath.includes(r.id)) {
        const walkFull = (id: string) => {
          s.delete(id);
          for (const c of children.get(id) || []) if (activePath.includes(c.id)) walkFull(c.id);
        };
        walkFull(r.id);
      }
    }
    return s;
  });

  const toggle = useCallback((id: string) => {
    setCollapsed((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  }, []);

  const handleExpandAll = useCallback(() => setCollapsed(new Set()), []);
  const handleCollapseAll = useCallback(() => {
    const s = new Set<string>();
    data.nodes.forEach((n) => s.add(n.id));
    roots.forEach((r) => s.delete(r.id));
    setCollapsed(s);
  }, [data.nodes, roots]);

  // ── Search match ──
  const matchedSet = useMemo(() => matchedNodeIds ? new Set(matchedNodeIds) : null, [matchedNodeIds]);

  // ── Click logic ──
  const clickTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastClickTime = useRef(0);
  const lastClickId = useRef<string | null>(null);
  const handleNodeClick = useCallback((n: LNode) => {
    const now = Date.now();
    const isDoubleClick = lastClickId.current === n.id && (now - lastClickTime.current) < 400;
    lastClickId.current = n.id;
    lastClickTime.current = now;
    if (clickTimer.current) clearTimeout(clickTimer.current);
    if (isDoubleClick) {
      if (n.childrenCount > 0) toggle(n.id);
    } else {
      // 传入 view 调整后的坐标（适配 scaled-div 坐标系）
      const v = viewRef.current;
      clickTimer.current = setTimeout(() => onNodeSelect?.(n, {
        x: n.x * v.scale + v.x,
        y: n.y * v.scale + v.y,
      }), 250);
    }
  }, [onNodeSelect, toggle]);

  // ── Mouse pan ──
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    const target = e.target as SVGElement;
    if (target.closest("[data-node-id],.graph-btn,.graph-slider")) return;
    isDragging.current = true;
    dragStart.current = { x: e.clientX, y: e.clientY };
    const v = viewRef.current;
    viewStart.current = { x: v.x, y: v.y };
    e.preventDefault();
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      setView((v) => ({ ...v, x: viewStart.current.x + e.clientX - dragStart.current.x, y: viewStart.current.y + e.clientY - dragStart.current.y }));
    };
    const onUp = () => { isDragging.current = false; };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, []);

  // ── Wheel zoom ──
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setView((v) => {
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      const newScale = Math.min(Math.max(v.scale * delta, 0.3), 3);
      const rect = svgRef.current?.getBoundingClientRect();
      if (!rect) return { ...v, scale: newScale };
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      return { x: mx - (mx - v.x) / v.scale * newScale, y: my - (my - v.y) / v.scale * newScale, scale: newScale };
    });
  }, []);

  // ── Touch ──
  const lastTouch = useRef<{ x: number; y: number; dist?: number } | null>(null);

  // 用原生 addEventListener 注册 touch 事件（passive: false），避免 React passive 限制
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;

    const onTouchStart = (e: TouchEvent) => {
      const v = viewRef.current;
      if (e.touches.length === 1) {
        lastTouch.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        viewStart.current = { x: v.x, y: v.y };
      } else if (e.touches.length === 2) {
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        lastTouch.current = { x: (e.touches[0].clientX + e.touches[1].clientX) / 2, y: (e.touches[0].clientY + e.touches[1].clientY) / 2, dist: Math.sqrt(dx * dx + dy * dy) };
        viewStart.current = { x: v.x, y: v.y };
      }
    };

    const onTouchMove = (e: TouchEvent) => {
      e.preventDefault();
      if (e.touches.length === 1 && lastTouch.current) {
        setView((v) => ({ ...v, x: viewStart.current.x + e.touches[0].clientX - lastTouch.current!.x, y: viewStart.current.y + e.touches[0].clientY - lastTouch.current!.y }));
      } else if (e.touches.length === 2 && lastTouch.current?.dist) {
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        const newDist = Math.sqrt(dx * dx + dy * dy);
        setView((v) => {
          const newScale = Math.min(Math.max(v.scale * (newDist / lastTouch.current!.dist!), 0.3), 3);
          return { x: e.touches[0].clientX - (e.touches[0].clientX - viewStart.current.x) / v.scale * newScale, y: e.touches[0].clientY - (e.touches[0].clientY - viewStart.current.y) / v.scale * newScale, scale: newScale };
        });
      }
    };

    const onTouchEnd = () => { lastTouch.current = null; };

    el.addEventListener("touchstart", onTouchStart, { passive: false });
    el.addEventListener("touchmove", onTouchMove, { passive: false });
    el.addEventListener("touchend", onTouchEnd);
    return () => {
      el.removeEventListener("touchstart", onTouchStart);
      el.removeEventListener("touchmove", onTouchMove);
      el.removeEventListener("touchend", onTouchEnd);
    };
  }, []);

  // ── Search auto-expand ──
  useEffect(() => {
    if (!matchedSet || matchedSet.size === 0) return;
    setCollapsed((prev) => {
      const next = new Set(prev);
      Array.from(matchedSet).forEach((mid) => {
        next.delete(mid);
        let current = data.nodes.find((n) => n.id === mid);
        while (current?.parent) { next.delete(current.parent); current = data.nodes.find((n) => n.id === current!.parent); }
      });
      return next;
    });
  }, [matchedSet, data.nodes]);

  // ── Layout: bottom-up height prep + top-down positioning ──
  const layout = useMemo(() => {
    const flat: LNode[] = [];
    const cardH = CARD_H + V_GAP;

    // Phase 1: 自底向上计算子树总高度（后序遍历）
    const subH = new Map<string, number>();
    function calcH(id: string): number {
      if (collapsed.has(id)) return cardH;
      const kids = children.get(id);
      if (!kids || kids.length === 0) return cardH;
      let total = 0;
      for (const k of kids) total += calcH(k.id);
      subH.set(id, total);
      return total;
    }
    for (const r of roots) calcH(r.id);

    // Phase 2: 自上而下定位节点，父节点居中于子节点中点
    function place(id: string, depth: number, yCenter: number) {
      const node = data.nodes.find((n) => n.id === id);
      if (!node) return;
      const kids = children.get(id) || [];
      const isColl = collapsed.has(id);
      const showKids = !isColl && kids.length > 0;

      flat.push({
        ...node,
        x: depth * (CARD_W + H_GAP) + 24,
        y: yCenter - CARD_H / 2,
        depth,
        isLeaf: kids.length === 0,
        childrenCount: kids.length,
      });

      if (!showKids) return;

      const totalH = subH.get(id) || (kids.length * cardH);
      let offset = -totalH / 2;
      for (const k of kids) {
        const kh = subH.get(k.id) || cardH;
        place(k.id, depth + 1, yCenter + offset + kh / 2);
        offset += kh;
      }
    }

    let yAcc = 60;
    for (const r of roots) {
      const rh = subH.get(r.id) || cardH;
      place(r.id, 0, yAcc + rh / 2);
      yAcc += rh;
    }

    return flat;
  }, [data.nodes, children, roots, collapsed]);

  // ── Edge style ──
  const getEdgeStyle = (sourceId: string, targetId: string) => {
    const onPath = activePath.includes(sourceId) && activePath.includes(targetId);
    return onPath
      ? { stroke: "var(--color-accent)", strokeWidth: 2.5, strokeOpacity: 0.8 }
      : { stroke: "var(--color-border)", strokeWidth: 1.5, strokeOpacity: 0.4 };
  };

  // ── Status tag helper ──
  const statusConfig = (n: GraphNode) => {
    const m = n.mastery ?? 0;
    const unlearned = n.node_type === "implicit" || m < 0.05;
    if (unlearned) return { text: "待学习", color: "var(--color-text-muted)", bg: "var(--color-surface-hover)" };
    if (m >= 0.8) return { text: "已掌握", color: "var(--color-success)", bg: "rgba(34,197,94,0.12)" };
    if (m >= 0.4) return { text: "学习中", color: "var(--color-warning)", bg: "rgba(234,179,8,0.12)" };
    return { text: "初学", color: "var(--color-accent)", bg: "rgba(99,102,241,0.1)" };
  };

  const statusWidth = (t: string) => t.length * 7 + 10;

  // ── 选中的节点在 SVG viewport 中的位置（实时计算，跟随视图变化） ──
  const selectedScreenPos = useMemo(() => {
    if (!selectedNodeId) return null;
    const n = layout.find(l => l.id === selectedNodeId);
    if (!n) return null;
    return { x: n.x * view.scale + view.x, y: n.y * view.scale + view.y };
  }, [selectedNodeId, layout, view]);

  return (
    <div className="relative w-full h-full select-none" onContextMenu={(e) => e.preventDefault()}>

      {/* ═══ SVG CANVAS ═══ */}
      <svg
        ref={svgRef}
        className="w-full h-full cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onWheel={handleWheel}
      >
        <defs>
          <filter id="card-shadow">
            <feDropShadow dx={0} dy={2} stdDeviation={3} floodOpacity={0.1} />
          </filter>
        </defs>
        <g transform={`translate(${view.x},${view.y}) scale(${view.scale})`}>
          {/* Edges */}
          {layout.map((n) => {
            if (!n.parent || !treeSet.has(n.parent)) return null;
            const p = layout.find((l) => l.id === n.parent);
            if (!p) return null;
            const es = getEdgeStyle(n.parent, n.id);
            return (
              <line key={`e-${n.id}`}
                x1={p.x + CARD_W} y1={p.y + CARD_H / 2}
                x2={n.x} y2={n.y + CARD_H / 2}
                stroke={es.stroke} strokeWidth={es.strokeWidth} strokeOpacity={es.strokeOpacity}
                className="pointer-events-none"
              />
            );
          })}

          {/* Nodes */}
          {layout.map((n) => {
            const isSel = n.id === selectedNodeId;
            const isOnPath = activePath.includes(n.id);
            const isColl = collapsed.has(n.id);
            const hasChildren = n.childrenCount > 0;
            const isHovered = n.id === hoveredId;
            const isMatched = matchedSet?.has(n.id);
            const isPartner = isSel || isOnPath;
            const st = statusConfig(n);
            const sw = statusWidth(st.text);

            return (
              <g key={n.id}
                data-node-id={n.id}
                onClick={() => handleNodeClick(n)}
                onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); onNodeContextMenu?.(n, e); }}
                onMouseEnter={() => setHoveredId(n.id)}
                onMouseLeave={() => setHoveredId(null)}
                style={{ cursor: "pointer" }}
                opacity={isPartner || isHovered || isMatched ? 1 : 0.5}
              >
                {/* Search glow */}
                {isMatched && (
                  <rect x={n.x - 2} y={n.y - 2} width={CARD_W + 4} height={CARD_H + 4} rx={10}
                    fill="var(--color-accent)" opacity={0.08} className="animate-pulse" />
                )}

                {/* Card */}
                <rect x={n.x} y={n.y} width={CARD_W} height={CARD_H} rx={10}
                  fill={isSel ? "var(--color-accent)" : "var(--color-surface)"}
                  stroke={isSel ? "var(--color-accent)" : isOnPath ? "var(--color-accent)" : "var(--color-border)"}
                  strokeWidth={isSel ? 2 : isOnPath ? 1.5 : 1}
                  strokeOpacity={isSel ? 1 : isOnPath ? 0.6 : 0.5}
                  filter={isHovered && !isSel ? "url(#card-shadow)" : undefined}
                />

                {/* Status tag */}
                <rect x={n.x + 8} y={n.y + 7} width={sw} height={16} rx={3}
                  fill={isSel ? "rgba(255,255,255,0.15)" : st.bg} />
                <text x={n.x + 12} y={n.y + 17} fontSize={7.5}
                  fill={isSel ? "rgba(255,255,255,0.9)" : st.color} fontWeight={600}>{st.text}</text>

                {/* Emoji */}
                <text x={n.x + CARD_W - 10} y={n.y + 22} fontSize={14} textAnchor="end"
                  fill={isSel ? "rgba(255,255,255,0.8)" : "var(--color-text-muted)"}
                >{n.emoji || "📘"}</text>

                {/* Title */}
                <text x={n.x + 8} y={n.y + 38} fontSize={11}
                  fill={isSel ? "#fff" : "var(--color-text)"} fontWeight={700}
                >{n.label.replace(n.emoji || "", "").trim()}</text>

                {/* 简介 */}
                <foreignObject x={n.x + 8} y={n.y + 48} width={CARD_W - 16} height={32}>
                  <div className="text-[7.5px] leading-[10px] overflow-hidden"
                    style={{ color: isSel ? "rgba(255,255,255,0.7)" : "var(--color-text-muted)" }}>
                    {n.brief || `${n.level} · ${n.childrenCount || 0} 子节点`}
                  </div>
                </foreignObject>

                {/* Divider */}
                <line x1={n.x + 8} y1={n.y + CARD_H - 30} x2={n.x + CARD_W - 8} y2={n.y + CARD_H - 30}
                  stroke={isSel ? "rgba(255,255,255,0.12)" : "var(--color-border)"} strokeOpacity={0.4} strokeWidth={0.5} />

                {/* Action: 深入（聚焦到该节点） */}
                <g className="graph-btn" style={{ cursor: "pointer" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    const v = viewRef.current;
                    onNodeSelect?.(n, { x: n.x * v.scale + v.x, y: n.y * v.scale + v.y });
                    onFocusNode?.(n.id);
                  }}>
                  <rect x={n.x + 8} y={n.y + CARD_H - 24} width={52} height={18} rx={3}
                    fill={isSel ? "rgba(255,255,255,0.12)" : "var(--color-surface-hover)"} />
                  <text x={n.x + 18} y={n.y + CARD_H - 12} fontSize={8}
                    fill={isSel ? "rgba(255,255,255,0.8)" : "var(--color-accent)"} fontWeight={600}>深入</text>
                </g>

                {/* Action: 展开/收起 */}
                {hasChildren && (
                  <g className="graph-btn" style={{ cursor: "pointer" }}
                    onClick={(e) => { e.stopPropagation(); toggle(n.id); }}>
                    <rect x={n.x + 66} y={n.y + CARD_H - 24} width={52} height={18} rx={3}
                      fill={isSel ? "rgba(255,255,255,0.12)" : "var(--color-surface-hover)"} />
                    <text x={n.x + 76} y={n.y + CARD_H - 12} fontSize={8}
                      fill={isSel ? "rgba(255,255,255,0.8)" : "var(--color-text-muted)"} fontWeight={500}>{isColl ? "展开" : "收起"}</text>
                  </g>
                )}

                {/* Mastery % */}
                <text x={n.x + CARD_W - 10} y={n.y + CARD_H - 12} fontSize={8}
                  fill={isSel ? "rgba(255,255,255,0.5)" : "var(--color-text-muted)"} textAnchor="end"
                >{Math.round((n.mastery ?? 0) * 100)}%</text>
              </g>
            );
          })}
        </g>
      </svg>

      {/* ═══ 节点弹出层（在 SVG 之上，位置实时跟随视图） ═══ */}
      {renderNodePopup && selectedScreenPos && renderNodePopup(selectedScreenPos)}
    </div>
  );
}
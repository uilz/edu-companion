"use client";

import React, { useMemo, useState, useCallback, useRef, useEffect } from "react";
import type { GraphData, GraphNode } from "@/lib/graph-types";
import { getMasteryColor } from "@/lib/graph-types";
import { ChevronRight, ZoomIn, ZoomOut, RefreshCw, ChevronDown, ChevronUp } from "lucide-react";

interface FocusGraphProps {
  data: GraphData;
  selectedNodeId?: string;
  onNodeSelect?: (node: GraphNode) => void;
  activePath: string[];
  width: number;
  height: number;
  searchQuery?: string;
  matchedNodeIds?: string[];
}

// ── Tree builder ──
function buildTree(nodes: GraphNode[]) {
  const children = new Map<string, GraphNode[]>();
  const roots: GraphNode[] = [];
  const levels = new Set(["partition", "domain", "topic", "concept"]);
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
const H_GAP = 40;
const V_GAP = 14;

interface ViewTransform { x: number; y: number; scale: number; }

export default function FocusGraph({
  data, selectedNodeId, onNodeSelect, activePath, width, height, searchQuery, matchedNodeIds,
}: FocusGraphProps) {
  const { children, roots, treeSet } = useMemo(() => buildTree(data.nodes), [data.nodes]);
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  // ── Pan / Zoom ──
  const [view, setView] = useState<ViewTransform>({ x: 0, y: 0, scale: 1 });
  const isDragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const viewStart = useRef({ x: 0, y: 0 });

  const zoomPercent = useMemo(() => Math.round(view.scale * 100), [view.scale]);
  const handleSliderZoom = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setView((v) => ({ ...v, scale: parseInt(e.target.value, 10) / 100 }));
  }, []);
  const handleZoomIn = useCallback(() => setView((v) => ({ ...v, scale: Math.min(v.scale * 1.15, 3) })), []);
  const handleZoomOut = useCallback(() => setView((v) => ({ ...v, scale: Math.max(v.scale / 1.15, 0.3) })), []);

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
      clickTimer.current = setTimeout(() => onNodeSelect?.(n), 250);
    }
  }, [onNodeSelect, toggle]);

  // ── Click breadcrumb to navigate ──
  const handleBreadcrumbClick = useCallback((node: GraphNode) => {
    onNodeSelect?.(node);
  }, [onNodeSelect]);

  // ── Mouse pan ──
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    const target = e.target as SVGElement;
    if (target.closest("[data-node-id],.graph-btn,.graph-slider")) return;
    isDragging.current = true;
    dragStart.current = { x: e.clientX, y: e.clientY };
    viewStart.current = { x: view.x, y: view.y };
  }, [view]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging.current) return;
    setView((v) => ({ ...v, x: viewStart.current.x + e.clientX - dragStart.current.x, y: viewStart.current.y + e.clientY - dragStart.current.y }));
  }, []);

  const handleMouseUp = useCallback(() => { isDragging.current = false; }, []);

  // ── Wheel zoom ──
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
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
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (e.touches.length === 1) {
      lastTouch.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      viewStart.current = { x: view.x, y: view.y };
    } else if (e.touches.length === 2) {
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      lastTouch.current = { x: (e.touches[0].clientX + e.touches[1].clientX) / 2, y: (e.touches[0].clientY + e.touches[1].clientY) / 2, dist: Math.sqrt(dx * dx + dy * dy) };
      viewStart.current = { x: view.x, y: view.y };
    }
  }, [view]);

  const handleTouchMove = useCallback((e: React.TouchEvent) => {
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
  }, []);

  const handleTouchEnd = useCallback(() => { lastTouch.current = null; }, []);

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

      // 定位本节点（yCenter 是卡片垂直中点）
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

  // ── Breadcrumbs ──
  const breadcrumbs = useMemo(() => {
    return activePath.map((id) => data.nodes.find((n) => n.id === id)).filter(Boolean) as GraphNode[];
  }, [activePath, data.nodes]);

  // ── Edge style ──
  const getEdgeStyle = (sourceId: string, targetId: string) => {
    const onPath = activePath.includes(sourceId) && activePath.includes(targetId);
    return onPath
      ? { stroke: "var(--color-accent)", strokeWidth: 2.5, strokeOpacity: 0.8 }
      : { stroke: "var(--color-border)", strokeWidth: 1.5, strokeOpacity: 0.4 };
  };

  // ── SVG size ──
  const svgW = Math.max(width, layout.length > 0 ? (layout.reduce((m, n) => Math.max(m, n.x + CARD_W + 60), 0)) : width);
  const svgH = Math.max(height - 88, layout.length > 0 ? (layout.reduce((m, n) => Math.max(m, n.y + CARD_H + 40), 0)) : height - 88);

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

  return (
    <div className="relative w-full h-full select-none flex flex-col" onContextMenu={(e) => e.preventDefault()}>

      {/* ═══ TOP BAR ═══ */}
      <div className="flex-shrink-0 flex items-center justify-between px-4 py-1.5 border-b border-[var(--color-border)] bg-[var(--color-surface)] min-h-[36px]">
        <div className="flex items-center gap-1 text-[11px] min-w-0 mr-2">
          {breadcrumbs.length > 0 ? (
            breadcrumbs.map((b, i) => (
              <React.Fragment key={b.id}>
                {i > 0 && <ChevronRight size={10} className="text-[var(--color-text-muted)] flex-shrink-0" />}
                <button
                  onClick={() => handleBreadcrumbClick(b)}
                  className="truncate max-w-[100px] px-1 py-0.5 rounded hover:bg-[var(--color-surface-hover)] transition-colors cursor-pointer"
                  style={{
                    color: i === breadcrumbs.length - 1 ? "var(--color-text)" : "var(--color-text-muted)",
                    fontWeight: i === breadcrumbs.length - 1 ? 600 : 400,
                  }}
                >
                  {b.label}
                </button>
              </React.Fragment>
            ))
          ) : (
            <span className="text-[var(--color-text-muted)]">知识点图谱</span>
          )}
        </div>
        <div className="flex items-center gap-0.5 flex-shrink-0">
          <button onClick={handleExpandAll}
            className="graph-btn flex items-center gap-0.5 px-1.5 py-1 rounded text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors">
            <ChevronDown size={10} />展开
          </button>
          <button onClick={handleCollapseAll}
            className="graph-btn flex items-center gap-0.5 px-1.5 py-1 rounded text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors">
            <ChevronUp size={10} />收起
          </button>
        </div>
      </div>

      {/* ═══ SVG CANVAS ═══ */}
      <svg
        ref={svgRef}
        width={svgW}
        height={svgH}
        className="flex-1 cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
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

                {/* Title — 去掉 emoji 前缀防止重复 */}
                <text x={n.x + 8} y={n.y + 38} fontSize={11}
                  fill={isSel ? "#fff" : "var(--color-text)"} fontWeight={700}
                  textLength={CARD_W - 20} lengthAdjust="spacingAndGlyphs"
                >{n.label.replace(n.emoji || "", "").trim()}</text>

                {/* 简介（节点的内容说明） */}
                <foreignObject x={n.x + 8} y={n.y + 48} width={CARD_W - 16} height={32}>
                  <div className="text-[7.5px] leading-[10px] overflow-hidden"
                    style={{ color: isSel ? "rgba(255,255,255,0.7)" : "var(--color-text-muted)" }}>
                    {n.brief || `${n.level} · ${n.childrenCount || 0} 子节点`}
                  </div>
                </foreignObject>

                {/* Divider */}
                <line x1={n.x + 8} y1={n.y + CARD_H - 30} x2={n.x + CARD_W - 8} y2={n.y + CARD_H - 30}
                  stroke={isSel ? "rgba(255,255,255,0.12)" : "var(--color-border)"} strokeOpacity={0.4} strokeWidth={0.5} />

                {/* Action: 深入 */}
                <g className="graph-btn" style={{ cursor: "pointer" }}
                  onClick={(e) => { e.stopPropagation(); onNodeSelect?.(n); }}>
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

      {/* ═══ BOTTOM BAR ═══ */}
      <div className="flex-shrink-0 flex items-center justify-between px-3 py-1.5 border-t border-[var(--color-border)] bg-[var(--color-surface)] min-h-[34px]">
        <div className="flex items-center gap-1.5">
          <button onClick={handleZoomOut}
            className="graph-btn graph-slider w-6 h-6 flex items-center justify-center rounded text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]">
            <ZoomOut size={12} />
          </button>
          <input
            type="range" min={30} max={300} value={zoomPercent}
            onChange={handleSliderZoom}
            className="graph-slider w-20 h-1 appearance-none cursor-pointer rounded-full"
            style={{
              background: `linear-gradient(to right, var(--color-accent) 0%, var(--color-accent) ${zoomPercent}%, var(--color-border) ${zoomPercent}%, var(--color-border) 100%)`,
            }}
          />
          <button onClick={handleZoomIn}
            className="graph-btn graph-slider w-6 h-6 flex items-center justify-center rounded text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]">
            <ZoomIn size={12} />
          </button>
          <span className="text-[9px] text-[var(--color-text-muted)] min-w-[2.5em] text-center font-mono">{zoomPercent}%</span>
        </div>
        <button onClick={() => setView({ x: 0, y: 0, scale: 1 })}
          className="graph-btn flex items-center gap-0.5 px-1.5 py-1 rounded text-[9px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]">
          <RefreshCw size={10} />重置
        </button>
      </div>
    </div>
  );
}

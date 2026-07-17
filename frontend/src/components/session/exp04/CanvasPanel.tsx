"use client";

import { useState, useRef, useCallback } from "react";
import { Plus, X } from "lucide-react";

// ── Types ──────────────────────────────────────────────────

interface CanvasNode {
  id: string;
  icon: string;
  bg: string;
  title: string;
  sub: string;
  x: number;
  y: number;
  linkedIds: string[];
}

interface Props {
  sessionTitle?: string;
  open: boolean;
  onClose: () => void;
}

// ── Helpers ────────────────────────────────────────────────

const ICON_POOL = [
  { icon: "📐", bg: "var(--color-accent-soft, #fef3c7)" },
  { icon: "🔢", bg: "var(--color-teal-soft, #ccfbf1)" },
  { icon: "🧠", bg: "var(--color-purple-soft, #ede9fe)" },
  { icon: "📝", bg: "var(--color-blue-soft, #dbeafe)" },
  { icon: "💡", bg: "var(--color-amber-soft, #fef3c7)" },
  { icon: "🌟", bg: "var(--color-pink-soft, #fce7f3)" },
];

function titleToKeywords(title: string): string[] {
  // Split by common delimiters: ：: , ， 、 spaces
  const parts = title.split(/[：:，,、\s]+/).filter(Boolean);
  // Remove common noise words
  const noise = /^(从|到|与|的|和|及|之|入门|基础|进阶|初探|详解)$/;
  return parts.filter((p) => !noise.test(p) && p.length >= 2).slice(0, 4);
}

function createStarterNodes(sessionTitle?: string): CanvasNode[] {
  const keywords = sessionTitle ? titleToKeywords(sessionTitle) : [];
  const nodes: CanvasNode[] = [];
  let count = 0;

  // Add keyword nodes
  for (const kw of keywords.slice(0, 3)) {
    const pool = ICON_POOL[count % ICON_POOL.length];
    nodes.push({
      id: `n${count}`,
      icon: pool.icon,
      bg: pool.bg,
      title: kw,
      sub: `核心概念`,
      x: 30 + count * 150,
      y: 50 + (count % 2) * 100,
      linkedIds: count > 0 ? [`n${count - 1}`] : [],
    });
    count++;
  }

  // Add a "昨天的学习" bridge node
  nodes.push({
    id: `n${count}`,
    icon: "🔗",
    bg: "var(--color-teal-soft, #ccfbf1)",
    title: "昨天的学习",
    sub: "链接到上次内容",
    x: 40,
    y: 260,
    linkedIds: nodes.length > 0 ? [nodes[0].id] : [],
  });

  // Link first node to bridge
  if (nodes.length > 0 && nodes[0].linkedIds.length === 0) {
    nodes[0].linkedIds.push(`n${count}`);
  }

  return nodes;
}

// ── Node Component ─────────────────────────────────────────

function NodeCard({
  node,
  onDrag,
}: {
  node: CanvasNode;
  onDrag: (id: string, x: number, y: number) => void;
}) {
  const dragRef = useRef<{ sx: number; sy: number; ox: number; oy: number } | null>(null);

  const handleDown = useCallback(
    (e: React.MouseEvent | React.TouchEvent) => {
      const pt = "touches" in e ? e.touches[0] : e;
      dragRef.current = { sx: pt.clientX, sy: pt.clientY, ox: node.x, oy: node.y };
      e.preventDefault();

      const handleMove = (ev: MouseEvent | TouchEvent) => {
        if (!dragRef.current) return;
        const p = "touches" in ev ? ev.touches[0] : ev;
        onDrag(node.id, dragRef.current.ox + p.clientX - dragRef.current.sx, dragRef.current.oy + p.clientY - dragRef.current.sy);
      };
      const handleUp = () => {
        dragRef.current = null;
        document.removeEventListener("mousemove", handleMove);
        document.removeEventListener("mouseup", handleUp);
        document.removeEventListener("touchmove", handleMove);
        document.removeEventListener("touchend", handleUp);
      };

      document.addEventListener("mousemove", handleMove);
      document.addEventListener("mouseup", handleUp);
      document.addEventListener("touchmove", handleMove, { passive: false });
      document.addEventListener("touchend", handleUp);
    },
    [node.id, node.x, node.y, onDrag],
  );

  return (
    <div
      className="absolute cursor-grab active:cursor-grabbing select-none"
      style={{ left: node.x, top: node.y }}
      onMouseDown={handleDown}
      onTouchStart={handleDown}
    >
      <div className="bg-surface rounded-xl border border-border/60 shadow-sm p-3 min-w-[120px] hover:shadow-md transition-shadow">
        <div className="flex items-center gap-2 mb-1">
          <span
            className="w-7 h-7 rounded-lg grid place-items-center text-sm"
            style={{ background: node.bg }}
          >
            {node.icon}
          </span>
          <span className="text-sm font-medium text-ink-primary">
            {node.title}
          </span>
        </div>
        <p className="text-[11px] text-ink-muted">{node.sub}</p>
      </div>
    </div>
  );
}

// ── SVG Connections ────────────────────────────────────────

function Connections({ nodes }: { nodes: CanvasNode[] }) {
  const lines: { x1: number; y1: number; x2: number; y2: number; key: string }[] = [];

  for (const n of nodes) {
    for (const lid of n.linkedIds) {
      const other = nodes.find((o) => o.id === lid);
      if (!other) continue;
      lines.push({
        x1: n.x + 60,
        y1: n.y + 30,
        x2: other.x + 60,
        y2: other.y + 30,
        key: `${n.id}-${lid}`,
      });
    }
  }

  if (lines.length === 0) return null;

  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none">
      {lines.map((l) => (
        <path
          key={l.key}
          d={`M${l.x1},${l.y1} C${(l.x1 + l.x2) / 2},${l.y1} ${(l.x1 + l.x2) / 2},${l.y2} ${l.x2},${l.y2}`}
          fill="none"
          stroke="var(--color-border, #e2e8f0)"
          strokeWidth="2"
          strokeDasharray="6 4"
        />
      ))}
    </svg>
  );
}

// ── Main Component ─────────────────────────────────────────

export default function CanvasPanel({ sessionTitle, open, onClose }: Props) {
  const [nodes, setNodes] = useState<CanvasNode[]>(() =>
    createStarterNodes(sessionTitle),
  );
  const nextId = useRef(nodes.length);

  const handleDrag = useCallback((id: string, x: number, y: number) => {
    setNodes((prev) => prev.map((n) => (n.id === id ? { ...n, x, y } : n)));
  }, []);

  const addNode = useCallback(() => {
    const id = `n${nextId.current++}`;
    const pool = ICON_POOL[nextId.current % ICON_POOL.length];
    const node: CanvasNode = {
      id,
      icon: pool.icon,
      bg: pool.bg,
      title: "新概念",
      sub: "拖动我 · 双击编辑",
      x: 60 + Math.random() * 180,
      y: 60 + Math.random() * 180,
      linkedIds: [],
    };
    setNodes((prev) => [...prev, node]);
  }, []);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] bg-black/30 backdrop-blur-sm flex flex-col animate-in fade-in duration-200">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-surface/90 backdrop-blur border-b border-border/50">
        <span className="text-sm font-semibold text-ink-primary">概念画布</span>
        <button
          onClick={onClose}
          className="text-ink-muted hover:text-ink-secondary transition-colors"
          aria-label="关闭画布"
        >
          <X size={20} />
        </button>
      </div>

      {/* Hint */}
      <div className="absolute top-14 left-1/2 -translate-x-1/2 z-10 px-4 py-1.5 rounded-full bg-surface/80 backdrop-blur border border-border/40 text-xs text-ink-muted shadow-sm pointer-events-none">
        拖动节点重新摆 · 点 ＋ 添加
      </div>

      {/* Canvas area */}
      <div className="flex-1 relative overflow-hidden bg-page">
        {/* Connections */}
        <Connections nodes={nodes} />

        {/* Nodes */}
        {nodes.map((node) => (
          <NodeCard key={node.id} node={node} onDrag={handleDrag} />
        ))}

        {/* Add button */}
        <button
          onClick={addNode}
          className="absolute bottom-6 right-6 w-12 h-12 rounded-full bg-accent text-white shadow-lg grid place-items-center hover:opacity-90 transition-opacity z-10"
          aria-label="添加节点"
        >
          <Plus size={24} />
        </button>
      </div>
    </div>
  );
}

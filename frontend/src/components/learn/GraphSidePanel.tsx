'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { Loader2, AlertTriangle, Filter, Info, ZoomIn, ZoomOut, Maximize2, Network, ExternalLink } from 'lucide-react';
import Link from 'next/link';

// ── 类型定义 ──
/** 知识图谱节点 */
interface GraphNode {
  id: string;
  label: string;
  subject: string;
  mastery: number;
  mastery_level: string;
  can_practice: boolean;
  blocked_by: string[];
  attempt_count: number;
  x?: number;
  y?: number;
}

/** 知识图谱边（节点间的关系） */
interface GraphEdge {
  from: string;
  to: string;
  label: string;
}

/** 知识图谱数据（节点 + 边 + 元信息） */
interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
  subjects: string[];
  layout?: Record<string, [number, number]>;
}

// ── 布局计算 ──
/**
 * 基于拓扑排序计算节点布局坐标
 * - 按依赖关系分层（入度为 0 的节点放在最上层）
 * - 同层节点水平均匀分布
 * - 层间垂直等距排列
 */
function computeLayout(nodes: GraphNode[], edges: GraphEdge[]): GraphNode[] {
  if (nodes.length === 0) return nodes;
  const inDegree = new Map<string, number>();
  const outEdges = new Map<string, string[]>();
  nodes.forEach((n) => { inDegree.set(n.id, 0); outEdges.set(n.id, []); });
  edges.forEach((e) => {
    inDegree.set(e.to, (inDegree.get(e.to) || 0) + 1);
    outEdges.get(e.from)?.push(e.to);
  });
  const layers: string[][] = [];
  const visited = new Set<string>();
  let queue = nodes.filter((n) => (inDegree.get(n.id) || 0) === 0).map((n) => n.id);
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
  const remaining = nodes.filter((n) => !visited.has(n.id));
  if (remaining.length > 0) layers.push(remaining.map((n) => n.id));

  const layerHeight = 100, nodeSpacing = 110, marginX = 50, marginY = 40;
  const result = nodes.map((n) => ({ ...n }));
  layers.forEach((layer, li) => {
    const totalWidth = (layer.length - 1) * nodeSpacing;
    const startX = marginX + Math.max(0, (500 - totalWidth) / 2);
    layer.forEach((id, ni) => {
      const node = result.find((n) => n.id === id);
      if (node) {
        node.x = startX + ni * nodeSpacing;
        node.y = marginY + li * layerHeight;
      }
    });
  });
  return result;
}

/**
 * 根据掌握度返回颜色
 * - ≥95%: 绿色（精通）
 * - ≥70%: 黄绿色（良好）
 * - ≥40%: 橙色（一般）
 * - >0%:  橙色（偏低）
 * - 0%:   灰色（未学习）
 */
function masteryColor(mastery: number): string {
  if (mastery >= 95) return '#22c55e';
  if (mastery >= 70) return '#84cc16';
  if (mastery >= 40) return '#f59e0b';
  if (mastery > 0) return '#f97316';
  return '#525252';
}

// ── 组件 Props ──
interface GraphSidePanelProps {
  onClose: () => void;
}

/**
 * 知识图谱侧边面板组件
 * - 展示知识点之间的依赖关系图
 * - 支持缩放、拖拽平移
 * - 可点击节点查看详情并跳转练习/学习页
 * - 支持按学科筛选
 */
export default function GraphSidePanel({ onClose }: GraphSidePanelProps) {
  // ── 状态定义 ──
  const [data, setData] = useState<GraphData | null>(null);          // 图谱数据
  const [loading, setLoading] = useState(true);                       // 加载中
  const [error, setError] = useState('');                             // 错误信息
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);  // 当前选中的节点
  const [selectedSubject, setSelectedSubject] = useState('');         // 选中的学科筛选
  const [zoom, setZoom] = useState(1);                                // 缩放比例
  const [pan, setPan] = useState({ x: 0, y: 0 });                    // 平移偏移
  const [isPanning, setIsPanning] = useState(false);                  // 是否正在拖拽
  const panStart = useRef({ x: 0, y: 0 });                           // 拖拽起始位置
  const svgRef = useRef<SVGSVGElement>(null);                         // SVG 引用

  // ── 数据获取 ──
  /** 从后端 API 拉取知识图谱数据，可选按学科筛选 */
  const fetchGraph = useCallback(async (subject?: string) => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ user_id: 'default_user' });
      if (subject) params.set('subject', subject);
      const res = await fetch(`/api/knowledge/graph?${params}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json: GraphData = await res.json();
      // 优先使用后端已保存的布局，否则前端计算
      if (json.layout) {
        json.nodes = json.nodes.map((n) => ({ ...n, x: json.layout![n.id]?.[0], y: json.layout![n.id]?.[1] }));
      } else {
        json.nodes = computeLayout(json.nodes, json.edges);
      }
      setData(json);
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  // 学科筛选变化时重新拉取数据
  useEffect(() => { fetchGraph(selectedSubject || undefined); }, [fetchGraph, selectedSubject]);

  // ── 拖拽与缩放事件处理 ──
  /** 鼠标按下：开始拖拽（仅在背景或空白区域触发） */
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.target === svgRef.current || (e.target as Element).tagName === 'rect') {
      setIsPanning(true);
      panStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    }
  };
  /** 鼠标移动：更新平移位置 */
  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning) return;
    setPan({ x: e.clientX - panStart.current.x, y: e.clientY - panStart.current.y });
  };
  /** 鼠标松开/离开：结束拖拽 */
  const handleMouseUp = () => setIsPanning(false);
  /** 滚轮缩放（限制范围 0.3x ~ 2x） */
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    setZoom((z) => Math.min(2, Math.max(0.3, z + (e.deltaY > 0 ? -0.1 : 0.1))));
  };

  // ── 加载状态 ──
  if (loading) {
    return <div className="flex items-center justify-center py-20"><Loader2 size={24} className="animate-spin text-[var(--color-accent)]" /></div>;
  }
  // ── 错误状态 ──
  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-20 px-4 text-center">
        <AlertTriangle size={24} className="text-[#f59e0b]" />
        <span className="text-xs text-[var(--color-text-muted)]">{error}</span>
        <button onClick={() => fetchGraph()} className="px-3 py-1.5 text-xs border border-[var(--color-border)] hover:bg-[var(--color-surface)]">
          重试
        </button>
      </div>
    );
  }

  // ── 计算视图尺寸与统计指标 ──
  const nodes = data?.nodes || [];
  const maxX = Math.max(600, ...nodes.map((n) => (n.x || 0) + 80));
  const maxY = Math.max(500, ...nodes.map((n) => (n.y || 0) + 80));
  const avgMastery = nodes.length > 0 ? Math.round(nodes.reduce((s, n) => s + n.mastery, 0) / nodes.length) : 0;

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 49px)' }}>
      {/* ── 顶部统计栏：节点数 / 平均掌握度 / 学科筛选 / 全屏入口 ── */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-[var(--color-border)] text-xs text-[var(--color-text-muted)]">
        <span>{data?.total_nodes} 知识点</span>
        <span>·</span>
        <span>平均掌握 {avgMastery}%</span>
        {data?.subjects && data.subjects.length > 0 && (
          <>
            <span>·</span>
            <select
              value={selectedSubject}
              onChange={(e) => { setSelectedSubject(e.target.value); setSelectedNode(null); }}
              className="text-xs bg-transparent border-none text-[var(--color-accent)] outline-none cursor-pointer"
            >
              <option value="">全部学科</option>
              {data.subjects.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </>
        )}
        <Link href="/dashboard?tab=graph" className="ml-auto text-[var(--color-accent)] hover:underline flex items-center gap-1">
          <ExternalLink size={12} /> 全屏
        </Link>
      </div>

      {/* ── SVG 图谱画布 ── */}
      <div className="flex-1 overflow-hidden relative bg-[var(--color-surface)]" style={{ cursor: isPanning ? 'grabbing' : 'grab' }}>
        {/* 缩放与重置控件 */}
        <div className="absolute top-2 right-2 z-10 flex gap-1">
          <button onClick={() => setZoom((z) => Math.min(2, z + 0.2))} className="w-7 h-7 flex items-center justify-center bg-[var(--color-card)] border border-[var(--color-border)] text-xs">+</button>
          <button onClick={() => setZoom((z) => Math.max(0.3, z - 0.2))} className="w-7 h-7 flex items-center justify-center bg-[var(--color-card)] border border-[var(--color-border)] text-xs">−</button>
          <button onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }} className="w-7 h-7 flex items-center justify-center bg-[var(--color-card)] border border-[var(--color-border)] text-xs">⌂</button>
        </div>

        <svg
          ref={svgRef}
          viewBox={`0 0 ${maxX} ${maxY}`}
          className="w-full h-full"
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
        >
          {/* 画布背景 */}
          <rect width={maxX} height={maxY} fill="var(--color-surface)" />
          {/* 变换容器：应用平移 + 缩放 */}
          <g transform={`translate(${pan.x},${pan.y}) scale(${zoom})`}>
            {/* ── 渲染边（依赖关系线 + 关系标签） ── */}
            {data?.edges.map((edge, i) => {
              const from = nodes.find((n) => n.id === edge.from);
              const to = nodes.find((n) => n.id === edge.to);
              if (!from || !to || from.x === undefined || from.y === undefined || to.x === undefined || to.y === undefined) return null;
              return (
                <g key={`e${i}`}>
                  <line x1={from.x + 40} y1={from.y + 20} x2={to.x + 40} y2={to.y + 20}
                    stroke="var(--color-border)" strokeWidth={1.5} markerEnd="url(#arrow)" />
                  <text x={(from.x + to.x) / 2 + 42} y={(from.y + to.y) / 2 + 14}
                    fontSize={9} fill="var(--color-text-muted)" textAnchor="middle">{edge.label}</text>
                </g>
              );
            })}
            {/* 箭头定义 */}
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX={9} refY={5} markerWidth={6} markerHeight={6} orient="auto">
                <path d="M0,0 L10,5 L0,10 Z" fill="var(--color-border)" />
              </marker>
            </defs>
            {/* ── 渲染节点（知识点卡片） ── */}
            {nodes.map((node) => {
              if (node.x === undefined || node.y === undefined) return null;
              const isSelected = selectedNode?.id === node.id;
              const color = masteryColor(node.mastery);
              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x},${node.y})`}
                  onClick={() => setSelectedNode(isSelected ? null : node)}
                  style={{ cursor: 'pointer' }}
                >
                  {/* 节点背景（选中时高亮边框） */}
                  <rect
                    width={80} height={36} rx={4}
                    fill={isSelected ? `${color}20` : 'var(--color-card)'}
                    stroke={isSelected ? color : 'var(--color-border)'}
                    strokeWidth={isSelected ? 2 : 1}
                  />
                  {/* 学科名称 */}
                  <text x={40} y={14} fontSize={9} fill="var(--color-text-muted)" textAnchor="middle">
                    {node.subject}
                  </text>
                  {/* 知识点名称 */}
                  <text x={40} y={28} fontSize={10} fill="var(--color-text)" textAnchor="middle" fontWeight={500}>
                    {node.label}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {/* ── 节点详情面板（选中节点时显示） ── */}
      {selectedNode && (
        <div className="border-t border-[var(--color-border)] p-3 bg-[var(--color-card)]">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-sm font-semibold text-[var(--color-text)]">{selectedNode.label}</h3>
            <span className="text-xs px-2 py-0.5 rounded" style={{
              background: `${masteryColor(selectedNode.mastery)}20`,
              color: masteryColor(selectedNode.mastery),
            }}>
              {selectedNode.mastery_level} ({selectedNode.mastery}%)
            </span>
          </div>
          <div className="text-xs text-[var(--color-text-muted)] mb-2">
            {selectedNode.subject} · 练习 {selectedNode.attempt_count} 次
          </div>
          <div className="flex gap-2">
            {/* 可练习时显示"去练习"按钮 */}
            {selectedNode.can_practice && (
              <Link
                href={`/practice?skill=${encodeURIComponent(selectedNode.id)}`}
                className="flex-1 text-center text-xs px-3 py-1.5 bg-[var(--color-accent)] text-white hover:opacity-90 transition-opacity"
              >
                去练习
              </Link>
            )}
            {/* "去提问"按钮，点击同时关闭侧边面板 */}
            <Link
              href={`/learn?skill=${encodeURIComponent(selectedNode.id)}`}
              onClick={onClose}
              className="flex-1 text-center text-xs px-3 py-1.5 border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-surface)]"
            >
              去提问
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

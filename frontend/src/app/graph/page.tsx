"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { ZoomIn, ZoomOut, Maximize2, Info, Filter, Loader2, AlertTriangle, RefreshCw } from "lucide-react";
import Card from "@/components/ui/Card";

// ── Types (from API) ──
interface GraphNode {
  id: string;
  label: string;
  subject: string;
  mastery: number;        // 0-100
  mastery_level: string;  // 未接触/初学/发展中/接近掌握/已掌握
  can_practice: boolean;
  blocked_by: string[];
  attempt_count: number;
  // 布局后注入
  x?: number;
  y?: number;
}

interface GraphEdge {
  from: string;
  to: string;
  label: string;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
  subjects: string[];
  layout?: Record<string, [number, number]>;  // API-provided force-directed coords
}

// ── Subject colors ──
const subjectColors: Record<string, string> = {
  "高等数学": "#0066FF",
  "大学物理": "#f59e0b",
  "计算机": "#22c55e",
  "线性代数": "#a855f7",
  "概率论": "#ec4899",
};
const fallbackColor = "#737373";

// ── Auto-layout: layered DAG ──
function computeLayout(nodes: GraphNode[], edges: GraphEdge[]): GraphNode[] {
  if (nodes.length === 0) return nodes;

  // Build adjacency
  const inDegree = new Map<string, number>();
  const outEdges = new Map<string, string[]>();
  nodes.forEach((n) => {
    inDegree.set(n.id, 0);
    outEdges.set(n.id, []);
  });
  edges.forEach((e) => {
    inDegree.set(e.to, (inDegree.get(e.to) || 0) + 1);
    outEdges.get(e.from)?.push(e.to);
  });

  // Topological sort into layers
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
        if (deg === 0 && !visited.has(child)) {
          next.push(child);
        }
      }
    }
    queue = next;
  }

  // Any unvisited (cycles) → append
  const remaining = nodes.filter((n) => !visited.has(n.id));
  if (remaining.length > 0) layers.push(remaining.map((n) => n.id));

  // Assign coordinates
  const n_nodes = nodes.length;
  const layerHeight = Math.max(160, 800 / Math.max(layers.length, 1));
  const nodeSpacing = Math.max(200, 1000 / Math.max(Math.max(...layers.map(l => l.length)), 1));
  const marginX = 120;
  const marginY = 100;

  const nodeMap = new Map(nodes.map((n) => [n.id, n]));
  const result = nodes.map((n) => ({ ...n }));

  layers.forEach((layer, li) => {
    const totalWidth = (layer.length - 1) * nodeSpacing;
    const startX = marginX + Math.max(0, (600 - totalWidth) / 2);
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

// ── Mastery color ──
function masteryColor(mastery: number): string {
  if (mastery >= 95) return "#22c55e";
  if (mastery >= 70) return "#84cc16";
  if (mastery >= 40) return "#f59e0b";
  if (mastery > 0) return "#f97316";
  return "#525252";
}

// ── Main page ──
export default function GraphPage() {
  const [data, setData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [partitionId, setPartitionId] = useState<string>("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [generating, setGenerating] = useState(false);
  const panStart = useRef({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);

  // ── Parse partition_id from URL ──
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const pid = params.get("partition_id") || "";
    setPartitionId(pid);
    setReady(true);
    if (!pid) setLoading(false);
  }, []);

  // ── Fetch graph data ──
  const fetchGraph = useCallback(async () => {
    if (!partitionId) {
      setLoading(false);
      setData(null);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`/api/knowledge/graph/${partitionId}`);
      const json = await res.json();

      if (!json.generated) {
        setData({ nodes: [], edges: [], total_nodes: 0, total_edges: 0, subjects: [] } as any);
        setLoading(false);
        return;
      }

      // Convert to existing format
      const nodes: GraphNode[] = (json.nodes || []).map((n: any) => ({
        id: n.id,
        label: n.label,
        subject: partitionId,
        mastery: n.mastery || 0,
        mastery_level: n.mastery_level || "未接触",
        can_practice: true,
        blocked_by: [] as string[],
        attempt_count: 0,
      }));

      const edges: GraphEdge[] = (json.edges || []).map((e: any) => ({
        from: e.from_id,
        to: e.to_id,
        label: e.relation || e.label || "",
      }));

      const graphData: GraphData = {
        nodes: computeLayout(nodes, edges),
        edges,
        total_nodes: json.total_nodes,
        total_edges: json.total_edges,
        subjects: [],
      };
      setData(graphData);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [partitionId]);

  useEffect(() => {
    if (partitionId) fetchGraph();
  }, [partitionId, fetchGraph]);

  // ── AI 生成图谱 ──
  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const res = await fetch(`/api/knowledge/graph/${partitionId}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ depth: 3 }),
      });
      if (res.ok) {
        await fetchGraph();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setGenerating(false);
    }
  };

  // ── Interaction handlers ──
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.target === svgRef.current || (e.target as Element).tagName === "rect") {
      setIsPanning(true);
      panStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    }
  };

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isPanning) return;
      setPan({ x: e.clientX - panStart.current.x, y: e.clientY - panStart.current.y });
    },
    [isPanning]
  );

  const handleMouseUp = () => setIsPanning(false);

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setZoom((z) => Math.min(2, Math.max(0.3, z + delta)));
  };

  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  // ── Compute SVG viewBox ──
  const nodes = data?.nodes || [];
  const maxX = Math.max(700, ...nodes.map((n) => (n.x || 0) + 100));
  const maxY = Math.max(600, ...nodes.map((n) => (n.y || 0) + 100));

  // ── Sidebar stats ──
  const avgMastery = nodes.length > 0
    ? Math.round(nodes.reduce((s, n) => s + n.mastery, 0) / nodes.length)
    : 0;
  const readyCount = nodes.filter((n) => n.can_practice).length;
  const blockedCount = nodes.filter((n) => !n.can_practice).length;

  // ── Loading state ──
  if (loading) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <Loader2 size={32} className="animate-spin text-[var(--color-accent)]" />
          <span className="text-sm text-[var(--color-text-muted)]">加载知识图谱…</span>
        </div>
      </main>
    );
  }

  // ── Error state ──
  if (error) {
    return (
      <main className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 max-w-sm text-center">
          <AlertTriangle size={32} className="text-[#f59e0b]" />
          <span className="text-sm text-[var(--color-text-muted)]">{error}</span>
          <button
            onClick={() => fetchGraph()}
            className="px-4 py-2 text-xs border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-colors"
          >
            重试
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-8 sm:py-16">
        {/* Header */}
        <div className="flex items-center justify-between mb-8 flex-wrap gap-4">
          <div>
            <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-[var(--color-text)]">
              知识图谱
            </h1>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">
              {partitionId ? `${data?.total_nodes || 0} 个知识点 · ${data?.total_edges || 0} 条前置依赖` : "请从会话进入分区"}
            </p>
          </div>

          {partitionId && (
            <div className="flex items-center gap-2">
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
              >
                {generating ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <RefreshCw size={14} />
                )}
                AI 生成图谱
              </button>
            </div>
          )}
        </div>

        {!partitionId && !loading && (
          <div className="text-center py-16">
            <p className="text-sm text-[var(--color-text-muted)]">
              请从侧栏会话分区的「📊 知识图谱」入口进入
            </p>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Graph area */}
          <div className="lg:col-span-3">
            <div className="border border-[var(--color-border)] bg-[var(--color-card)] overflow-hidden relative">
              {/* Controls */}
              <div className="absolute top-4 right-4 z-10 flex gap-1">
                <button onClick={() => setZoom((z) => Math.min(2, z + 0.2))}
                  className="w-8 h-8 flex items-center justify-center bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors">
                  <ZoomIn size={14} />
                </button>
                <button onClick={() => setZoom((z) => Math.max(0.3, z - 0.2))}
                  className="w-8 h-8 flex items-center justify-center bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors">
                  <ZoomOut size={14} />
                </button>
                <button onClick={resetView}
                  className="w-8 h-8 flex items-center justify-center bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors">
                  <Maximize2 size={14} />
                </button>
              </div>

              {nodes.length === 0 ? (
                <div className="flex items-center justify-center h-96 text-sm text-[var(--color-text-muted)]">
                  暂无图谱数据
                </div>
              ) : (
                <svg
                  ref={svgRef}
                  className="w-full"
                  viewBox={`0 0 ${maxX} ${maxY}`}
                  onMouseDown={handleMouseDown}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                  onMouseLeave={handleMouseUp}
                  onWheel={handleWheel}
                  style={{ cursor: isPanning ? "grabbing" : "grab", userSelect: "none", WebkitUserSelect: "none" as any }}
                >
                  <g transform={`translate(${pan.x / 2},${pan.y / 2}) scale(${zoom})`}>
                    {/* Edges — quadratic bezier curves */}
                    {(data?.edges || []).map((edge) => {
                      const fromNode = nodes.find((n) => n.id === edge.from);
                      const toNode = nodes.find((n) => n.id === edge.to);
                      if (!fromNode?.x || !toNode?.x) return null;
                      const dx = toNode.x - fromNode.x;
                      const dy = (toNode.y || 0) - (fromNode.y || 0);
                      const cx = fromNode.x + dx * 0.6;
                      const cy = (fromNode.y || 0) + dy * 0.3;
                      const midX = fromNode.x + dx * 0.45;
                      const midY = (fromNode.y || 0) + dy * 0.35;
                      return (
                        <g key={`${edge.from}-${edge.to}`}>
                          <defs>
                            <marker id={`arrow-${edge.from}-${edge.to}`} viewBox="0 0 10 10"
                              refX={dx > 0 ? 10 : 0} refY={5}
                              markerWidth={5} markerHeight={5}
                              orient={dx > 0 ? "auto" : "auto-start-reverse"}>
                              <path d="M 0 2 L 6 5 L 0 8 z" fill="#404040" opacity="0.6" />
                            </marker>
                          </defs>
                          <path
                            d={`M ${fromNode.x} ${fromNode.y} Q ${cx} ${cy} ${toNode.x} ${toNode.y}`}
                            fill="none"
                            stroke="#333"
                            strokeWidth={1}
                            opacity={0.35}
                            markerEnd={`url(#arrow-${edge.from}-${edge.to})`}
                          />
                          {edge.label && (
                            <text x={midX} y={midY - 6} textAnchor="middle"
                              fill="#525252" fontSize={9} opacity={0.6}>{edge.label}</text>
                          )}
                        </g>
                      );
                    })}

                    {/* Nodes */}
                    {nodes.map((node) => {
                      if (!node.x || !node.y) return null;
                      const isSelected = selectedNode?.id === node.id;
                      const color = subjectColors[node.subject] || fallbackColor;
                      const mColor = masteryColor(node.mastery);
                      const radius = isSelected ? 28 : 23;

                      return (
                        <g key={node.id}
                          onClick={(e) => { e.stopPropagation(); setSelectedNode(isSelected ? null : node); }}
                          style={{ cursor: "pointer" }}
                        >
                          {/* Mastery ring */}
                          <circle cx={node.x} cy={node.y} r={radius + 4}
                            fill="none" stroke={mColor} strokeWidth={2}
                            strokeDasharray={`${(node.mastery / 100) * Math.PI * 2 * (radius + 4)} ${Math.PI * 2 * (radius + 4)}`}
                            strokeDashoffset={0}
                            opacity={node.mastery > 0 ? 0.6 : 0.15}
                            style={{ transition: "all 0.3s" }}
                          />

                          {/* Node circle */}
                          <circle cx={node.x} cy={node.y} r={radius}
                            fill={isSelected ? color : node.can_practice ? "#0d0d0d" : "#1a1a1a"}
                            stroke={node.can_practice ? color : "#404040"}
                            strokeWidth={isSelected ? 2.5 : 1.5}
                            opacity={node.can_practice ? 1 : 0.5}
                            style={{ transition: "all 0.2s" }}
                          />

                          {/* Blocked indicator */}
                          {!node.can_practice && (
                            <text x={node.x} y={node.y - radius - 8}
                              textAnchor="middle" fill="#525252" fontSize={8}>🔒</text>
                          )}

                          {/* Label */}
                          <text x={node.x} y={node.y + 1}
                            textAnchor="middle" dominantBaseline="middle"
                            fill={isSelected ? "#ffffff" : node.can_practice ? color : "#525252"}
                            fontSize={9} fontWeight={600}>
                            {node.label.length > 5 ? node.label.slice(0, 4) + "…" : node.label}
                          </text>

                          {/* Full label tooltip on hover */}
                          <title>{node.label} — {node.mastery_level} ({node.mastery}%){node.can_practice ? "" : " 🔒前置未满足"}</title>
                        </g>
                      );
                    })}
                  </g>
                </svg>
              )}
            </div>
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Legend */}
            <Card title="图例">
              <div className="space-y-2">
                {(data?.subjects || Object.keys(subjectColors)).map((subject) => (
                  <div key={subject} className="flex items-center gap-2.5 text-sm">
                    <div className="w-3 h-3 flex-shrink-0" style={{ backgroundColor: subjectColors[subject] || fallbackColor }} />
                    <span className="text-[var(--color-text-secondary)]">{subject}</span>
                  </div>
                ))}
              </div>
              <div className="mt-3 pt-3 border-t border-[var(--color-surface)] space-y-1 text-[10px] text-[var(--color-text-muted)]">
                <div>🔒 = 前置知识未满足，暂不可练</div>
                <div>圆环 = 掌握进度 (0-100%)</div>
              </div>
            </Card>

            {/* Stats */}
            <Card title="统计">
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">知识点</span>
                  <span className="text-[var(--color-text)] font-medium">{nodes.length}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">可练习</span>
                  <span className="text-[#22c55e] font-medium">{readyCount}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">被卡控</span>
                  <span className="text-[#f97316] font-medium">{blockedCount}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">关联边</span>
                  <span className="text-[var(--color-text)] font-medium">{data?.total_edges || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">平均掌握</span>
                  <span className="text-[var(--color-text)] font-medium">{avgMastery}%</span>
                </div>
              </div>
            </Card>

            {/* Node detail */}
            {selectedNode ? (
              <Card title="知识点详情">
                <div className="space-y-3">
                  <div>
                    <div className="text-lg font-bold text-[var(--color-text)]">{selectedNode.label}</div>
                    <div className="text-xs text-[var(--color-text-muted)] mt-0.5">
                      {selectedNode.subject} · {selectedNode.id}
                    </div>
                  </div>

                  {/* Mastery bar */}
                  <div>
                    <div className="text-xs text-[var(--color-text-muted)] mb-1">
                      掌握度 · {selectedNode.mastery_level}
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-[var(--color-surface)] h-2">
                        <div className="h-full transition-all duration-500"
                          style={{
                            width: `${selectedNode.mastery}%`,
                            backgroundColor: masteryColor(selectedNode.mastery),
                          }} />
                      </div>
                      <span className="text-sm text-[var(--color-text)] font-medium">
                        {selectedNode.mastery}%
                      </span>
                    </div>
                  </div>

                  {/* Can practice? */}
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[var(--color-text-muted)]">状态:</span>
                    {selectedNode.can_practice ? (
                      <span className="text-xs px-2 py-0.5 border border-[#22c55e] text-[#22c55e]">可练习</span>
                    ) : (
                      <span className="text-xs px-2 py-0.5 border border-[#f97316] text-[#f97316]">前置未满足</span>
                    )}
                  </div>

                  {/* Blocked by */}
                  {!selectedNode.can_practice && selectedNode.blocked_by.length > 0 && (
                    <div>
                      <div className="text-xs text-[var(--color-text-muted)] mb-1">需要先掌握</div>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedNode.blocked_by.map((bid) => {
                          const blockedNode = nodes.find((n) => n.id === bid);
                          return (
                            <span key={bid}
                              onClick={() => blockedNode && setSelectedNode(blockedNode)}
                              className="text-xs px-2 py-1 border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)] cursor-pointer transition-colors"
                            >
                              {blockedNode?.label || bid}
                            </span>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Prerequisites */}
                  <div>
                    <div className="text-xs text-[var(--color-text-muted)] mb-1">前置知识</div>
                    <div className="flex flex-wrap gap-1.5">
                      {((data?.edges || []).filter((e) => e.to === selectedNode.id).map((e) => {
                        const fromNode = nodes.find((n) => n.id === e.from);
                        return (
                          <span key={e.from}
                            onClick={() => fromNode && setSelectedNode(fromNode)}
                            className="text-xs px-2 py-1 border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)] cursor-pointer transition-colors"
                          >
                            {fromNode?.label || e.from}
                          </span>
                        );
                      })).length === 0 && (
                        <span className="text-xs text-[var(--color-text-muted)]">无（入口知识点）</span>
                      )}
                    </div>
                  </div>

                  {/* Stats */}
                  <div className="text-[10px] text-[var(--color-text-muted)]">
                    练习 {selectedNode.attempt_count} 次
                  </div>
                </div>
              </Card>
            ) : (
              <Card>
                <div className="text-center py-4">
                  <Info size={20} className="text-[var(--color-text-muted)] mx-auto mb-2" />
                  <div className="text-sm text-[var(--color-text-muted)]">点击节点查看详情</div>
                </div>
              </Card>
            )}
          </div>

          {/* ── P2: Learning Roadmap ── */}
          <div className="lg:col-span-2">
            <Card title="📋 推荐学习路径">
              {loading ? (
                <div className="py-8 text-center">
                  <Loader2 size={16} className="animate-spin mx-auto" />
                </div>
              ) : (
                <LearningRoadmap nodes={nodes} edges={data?.edges || []} />
              )}
            </Card>
          </div>
        </div>
      </div>
    </main>
  );
}

// ── P2: Learning Roadmap Component ──

function LearningRoadmap({
  nodes,
  edges,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
}) {
  // Topological sort by dependency depth
  const depDepth = new Map<string, number>();

  function getDepth(skillId: string, visited = new Set<string>()): number {
    if (depDepth.has(skillId)) return depDepth.get(skillId)!;
    if (visited.has(skillId)) return 0;
    visited.add(skillId);

    const prereqs = edges.filter((e) => e.to === skillId).map((e) => e.from);
    if (prereqs.length === 0) {
      depDepth.set(skillId, 0);
      return 0;
    }

    const maxDepth = Math.max(...prereqs.map((p) => getDepth(p, visited)));
    const depth = maxDepth + 1;
    depDepth.set(skillId, depth);
    return depth;
  }

  nodes.forEach((n) => getDepth(n.id));

  // Sort by depth, then by mastery (low mastery first within same depth)
  const sorted = [...nodes].sort((a, b) => {
    const da = depDepth.get(a.id) || 0;
    const db = depDepth.get(b.id) || 0;
    if (da !== db) return da - db;
    return a.mastery - b.mastery;
  });

  // Group by depth level
  const levels: Map<number, GraphNode[]> = new Map();
  sorted.forEach((n) => {
    const d = depDepth.get(n.id) || 0;
    if (!levels.has(d)) levels.set(d, []);
    levels.get(d)!.push(n);
  });

  const masteryColor = (level: string) => {
    switch (level) {
      case "已掌握": return "bg-green-500";
      case "接近掌握": return "bg-emerald-400";
      case "发展中": return "bg-yellow-400";
      case "初学": return "bg-orange-400";
      default: return "bg-gray-400";
    }
  };

  const masteryBg = (level: string) => {
    switch (level) {
      case "已掌握": return "bg-green-500/10 border-green-500/30";
      case "接近掌握": return "bg-emerald-400/10 border-emerald-400/30";
      case "发展中": return "bg-yellow-400/10 border-yellow-400/30";
      case "初学": return "bg-orange-400/10 border-orange-400/30";
      default: return "bg-gray-400/10 border-gray-400/30";
    }
  };

  return (
    <div className="space-y-4">
      {Array.from(levels.entries()).map(([depth, skills]) => (
        <div key={depth}>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[10px] font-semibold text-[var(--color-text-muted)] uppercase">
              阶段 {depth + 1}
            </span>
            <div className="flex-1 h-px bg-[var(--color-border)]" />
          </div>
          <div className="flex flex-wrap gap-2">
            {skills.map((skill) => (
              <div
                key={skill.id}
                className={`flex items-center gap-2 px-3 py-2 border text-xs transition-all ${masteryBg(skill.mastery_level)}`}
              >
                <div
                  className={`w-2 h-2 flex-shrink-0 ${masteryColor(skill.mastery_level)}`}
                  style={{ borderRadius: "50%" }}
                />
                <span className="text-[var(--color-text-secondary)]">
                  {skill.label}
                </span>
                <span className="text-[10px] text-[var(--color-text-muted)]">
                  {skill.mastery}%
                </span>
                {!skill.can_practice && skill.blocked_by.length > 0 && (
                  <span className="text-[10px] text-orange-400" title={`前置未完成: ${skill.blocked_by.join(", ")}`}>
                    🔒
                  </span>
                )}
                {skill.can_practice && skill.mastery < 80 && (
                  <span className="text-[10px] text-green-400">✓</span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

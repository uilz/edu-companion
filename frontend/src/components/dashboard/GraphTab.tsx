'use client';

import { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { ZoomIn, ZoomOut, Maximize2, Info, Loader2, RefreshCw, ChevronDown, GitGraph } from "lucide-react";
import Card from "@/components/ui/Card";

// ── Types ──
interface GraphNode {
  id: string; label: string; subject: string;
  mastery: number; mastery_level: string;
  can_practice: boolean; blocked_by: string[]; attempt_count: number;
  x?: number; y?: number;
}
interface GraphEdge { from: string; to: string; label: string; }

// ── Colors ──
const subjectColors: Record<string, string> = {
  "高等数学": "#0066FF", "大学物理": "#f59e0b",
  "计算机": "#22c55e", "线性代数": "#a855f7", "概率论": "#ec4899",
};
const fallbackColor = "#737373";

// ── Layout ──
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
  const layerHeight = Math.max(140, 700 / Math.max(layers.length, 1));
  const nodeSpacing = Math.max(180, 900 / Math.max(Math.max(...layers.map(l => l.length)), 1));
  const marginX = 100, marginY = 80;
  const result = nodes.map((n) => ({ ...n }));
  layers.forEach((layer, li) => {
    const totalWidth = (layer.length - 1) * nodeSpacing;
    const startX = marginX + Math.max(0, (600 - totalWidth) / 2);
    layer.forEach((id, ni) => {
      const node = result.find((n) => n.id === id);
      if (node) { node.x = startX + ni * nodeSpacing; node.y = marginY + li * layerHeight; }
    });
  });
  return result;
}

function masteryColor(m: number) {
  if (m >= 95) return "#22c55e"; if (m >= 70) return "#84cc16";
  if (m >= 40) return "#f59e0b"; if (m > 0) return "#f97316";
  return "#525252";
}

// ── Main component ──
export function GraphTab() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const partitionIdFromUrl = searchParams.get("partition_id") || "";

  const [partitionId, setPartitionId] = useState(partitionIdFromUrl);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [totalNodes, setTotalNodes] = useState(0);
  const [totalEdges, setTotalEdges] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState("");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);

  // ── Partition picker ──
  const [partitions, setPartitions] = useState<{ id: string; name: string; emoji: string }[]>([]);
  const [showPicker, setShowPicker] = useState(false);
  const [loadingParts, setLoadingParts] = useState(false);
  const loadPartitions = useCallback(async () => {
    setLoadingParts(true);
    try {
      const res = await fetch("/api/conversations/partitions");
      const data = await res.json();
      setPartitions(data.partitions || []);
    } catch { /* noop */ }
    finally { setLoadingParts(false); }
  }, []);

  // ── Sync partitionId from URL ──
  useEffect(() => {
    if (partitionIdFromUrl && partitionIdFromUrl !== partitionId) {
      setPartitionId(partitionIdFromUrl);
    }
  }, [partitionIdFromUrl]);

  // ── Fetch graph ──
  const fetchGraph = useCallback(async () => {
    if (!partitionId) { setNodes([]); setEdges([]); return; }
    setLoading(true); setError("");
    try {
      const res = await fetch(`/api/knowledge/graph/${partitionId}`);
      const json = await res.json();
      if (!json.generated) {
        setNodes([]); setEdges([]);
        setLoading(false); return;
      }
      const rawNodes: GraphNode[] = (json.nodes || []).map((n: any) => ({
        id: n.id, label: n.label, subject: partitionId,
        mastery: n.mastery || 0, mastery_level: n.mastery_level || "未接触",
        can_practice: true, blocked_by: [] as string[], attempt_count: 0,
      }));
      const rawEdges: GraphEdge[] = (json.edges || []).map((e: any) => ({
        from: e.from_id, to: e.to_id, label: e.relation || e.label || "",
      }));
      setNodes(computeLayout(rawNodes, rawEdges));
      setEdges(rawEdges);
      setTotalNodes(json.total_nodes);
      setTotalEdges(json.total_edges);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally { setLoading(false); }
  }, [partitionId]);

  useEffect(() => { fetchGraph(); }, [fetchGraph]);

  // ── AI Generate ──
  const handleGenerate = async () => {
    setGenerating(true); setGenerateError("");
    try {
      const res = await fetch(`/api/knowledge/graph/${partitionId}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ depth: 3 }),
      });
      const json = await res.json();
      if (res.ok && json.ok) { await fetchGraph(); }
      else { setGenerateError(json?.detail || json?.error || `生成失败 (HTTP ${res.status})`); }
    } catch (e) {
      setGenerateError(e instanceof Error ? e.message : "网络异常");
    } finally { setGenerating(false); }
  };

  // ── Switch partition ──
  const switchPartition = (pid: string) => {
    setPartitionId(pid);
    setShowPicker(false);
    setSelectedNode(null);
    // Update URL without page reload
    const params = new URLSearchParams(searchParams.toString());
    params.set("partition_id", pid);
    router.replace(`/dashboard?${params.toString()}`, { scroll: false });
  };

  // ── Pan & zoom ──
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.target === svgRef.current || (e.target as Element).tagName === "rect") {
      setIsPanning(true);
      panStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
    }
  };
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning) return;
    setPan({ x: e.clientX - panStart.current.x, y: e.clientY - panStart.current.y });
  }, [isPanning]);
  const handleWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    const svg = svgRef.current; if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const mouseX = e.clientX - rect.left, mouseY = e.clientY - rect.top;
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    const oldZoom = zoom;
    const newZoom = Math.min(2, Math.max(0.3, oldZoom + delta));
    const svgX = (mouseX - pan.x) / oldZoom, svgY = (mouseY - pan.y) / oldZoom;
    setZoom(newZoom);
    setPan({ x: mouseX - svgX * newZoom, y: mouseY - svgY * newZoom });
  }, [zoom, pan]);
  useEffect(() => {
    const svg = svgRef.current; if (!svg) return;
    svg.addEventListener("wheel", handleWheel, { passive: false });
    return () => svg.removeEventListener("wheel", handleWheel);
  }, [handleWheel]);
  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  // ── Stats ──
  const avgMastery = nodes.length > 0 ? Math.round(nodes.reduce((s, n) => s + n.mastery, 0) / nodes.length) : 0;
  const readyCount = nodes.filter((n) => n.can_practice).length;
  const blockedCount = nodes.filter((n) => !n.can_practice).length;
  const actualSubjects = Array.from(new Set(nodes.map((n) => n.subject)));

  // ── ViewBox ──
  const maxX = Math.max(700, ...nodes.map((n) => (n.x || 0) + 100));
  const maxY = Math.max(500, ...nodes.map((n) => (n.y || 0) + 100));

  // ── Empty: no partition selected ──
  if (!partitionId) {
    return (
      <div className="text-center py-16">
        <GitGraph size={36} className="mx-auto mb-4 text-[var(--color-text-muted)] opacity-50" />
        <h2 className="text-lg font-bold text-[var(--color-text)] mb-2">选择分区查看知识图谱</h2>
        <p className="text-sm text-[var(--color-text-muted)] mb-6">
          从学习空间侧栏点击图谱图标，或在此选择分区
        </p>
        <button
          onClick={() => { setShowPicker(true); loadPartitions(); }}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-[var(--color-accent)] text-white text-sm hover:opacity-90 transition-opacity"
        >
          <GitGraph size={14} /> 选择分区
        </button>
        {showPicker && (
          <div className="relative inline-block">
            <div className="fixed inset-0 z-10" onClick={() => setShowPicker(false)} />
            <div className="absolute top-full mt-1 left-1/2 -translate-x-1/2 z-20 w-64 border border-[var(--color-border)] bg-[var(--color-bg)] shadow-lg text-left">
              {loadingParts ? (
                <div className="px-4 py-6 text-center"><Loader2 size={14} className="animate-spin mx-auto" /></div>
              ) : partitions.length === 0 ? (
                <div className="px-4 py-6 text-center text-xs text-[var(--color-text-muted)]">暂无分区</div>
              ) : (
                partitions.map((p) => (
                  <button key={p.id} onClick={() => switchPartition(p.id)}
                    className="block w-full text-left px-4 py-2.5 text-sm hover:bg-[var(--color-surface)] text-[var(--color-text-secondary)]"
                  ><span className="mr-2">{p.emoji || "📁"}</span>{p.name}</button>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── Loading ──
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 gap-4">
        <Loader2 size={24} className="animate-spin text-[var(--color-accent)]" />
        <span className="text-sm text-[var(--color-text-muted)]">加载知识图谱…</span>
      </div>
    );
  }

  // ── Error ──
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-4">
        <span className="text-sm text-[var(--color-text-muted)]">{error}</span>
        <button onClick={fetchGraph}
          className="px-4 py-2 text-xs border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-surface)]"
        >重试</button>
      </div>
    );
  }

  return (
    <div>
      {/* ── Top bar: partition selector + actions ── */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          {/* Partition selector */}
          <div className="relative">
            <button onClick={() => { setShowPicker(!showPicker); if (!showPicker) loadPartitions(); }}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-colors"
            >
              <GitGraph size={14} className="text-[var(--color-accent)]" />
              <span>{partitions.find(p => p.id === partitionId)?.emoji || "📁"} {partitions.find(p => p.id === partitionId)?.name || partitionId}</span>
              <ChevronDown size={12} className={`transition-transform ${showPicker ? "rotate-180" : ""}`} />
            </button>
            {showPicker && (
              <>
                <div className="fixed inset-0 z-10" onClick={() => setShowPicker(false)} />
                <div className="absolute top-full mt-1 left-0 z-20 w-64 max-h-64 overflow-y-auto border border-[var(--color-border)] bg-[var(--color-bg)] shadow-lg">
                  {loadingParts ? (
                    <div className="px-4 py-6 text-center"><Loader2 size={14} className="animate-spin mx-auto" /></div>
                  ) : (
                    partitions.map((p) => (
                      <button key={p.id} onClick={() => switchPartition(p.id)}
                        className={`block w-full text-left px-4 py-2.5 text-sm hover:bg-[var(--color-surface)] transition-colors ${
                          p.id === partitionId ? "text-[var(--color-accent)] bg-[var(--color-accent)]/5 font-medium" : "text-[var(--color-text-secondary)]"
                        }`}
                      ><span className="mr-2">{p.emoji || "📁"}</span>{p.name}</button>
                    ))
                  )}
                </div>
              </>
            )}
          </div>
          {/* Stats inline */}
          <span className="text-xs text-[var(--color-text-muted)]">
            {totalNodes} 知识点 · {totalEdges} 条关联 · 掌握度 {avgMastery}%
          </span>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button onClick={handleGenerate} disabled={generating}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 transition-opacity"
          >
            {generating ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            AI 生成
          </button>
        </div>
      </div>

      {/* ── Generate error ── */}
      {generateError && <p className="text-xs text-[#f97316] mb-4">{generateError}</p>}

      {/* ── Main: graph + sidebar ── */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Graph area */}
        <div className="lg:col-span-3">
          <div className="border border-[var(--color-border)] bg-[var(--color-card)] overflow-hidden relative" style={{ minHeight: 480 }}>
            {/* Zoom controls */}
            <div className="absolute top-3 right-3 z-10 flex gap-1">
              <button onClick={() => setZoom((z) => Math.min(2, z + 0.2))}
                className="w-8 h-8 flex items-center justify-center bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">
                <ZoomIn size={14} />
              </button>
              <button onClick={() => setZoom((z) => Math.max(0.3, z - 0.2))}
                className="w-8 h-8 flex items-center justify-center bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">
                <ZoomOut size={14} />
              </button>
              <button onClick={resetView}
                className="w-8 h-8 flex items-center justify-center bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]">
                <Maximize2 size={14} />
              </button>
            </div>

            {nodes.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-96 gap-3">
                <GitGraph size={28} className="text-[var(--color-text-muted)] opacity-40" />
                <span className="text-sm text-[var(--color-text-muted)]">暂无图谱数据</span>
                <button onClick={handleGenerate} disabled={generating}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 mt-2"
                >{generating ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} AI 生成图谱</button>
              </div>
            ) : (
              <svg ref={svgRef} className="w-full"
                viewBox={`0 0 ${maxX} ${maxY}`}
                onMouseDown={handleMouseDown} onMouseMove={handleMouseMove}
                onMouseUp={() => setIsPanning(false)} onMouseLeave={() => setIsPanning(false)}
                style={{ cursor: isPanning ? "grabbing" : "grab", userSelect: "none", WebkitUserSelect: "none" as any }}
              >
                <g transform={`translate(${pan.x / 2},${pan.y / 2}) scale(${zoom})`}>
                  {/* Edges */}
                  {edges.map((edge) => {
                    const fromNode = nodes.find((n) => n.id === edge.from);
                    const toNode = nodes.find((n) => n.id === edge.to);
                    if (!fromNode?.x || !toNode?.x) return null;
                    const dx = toNode.x - fromNode.x, dy = (toNode.y || 0) - (fromNode.y || 0);
                    const cx = fromNode.x + dx * 0.6, cy = (fromNode.y || 0) + dy * 0.3;
                    const midX = fromNode.x + dx * 0.45, midY = (fromNode.y || 0) + dy * 0.35;
                    return (
                      <g key={`${edge.from}-${edge.to}`}>
                        <defs>
                          <marker id={`arr-${edge.from}-${edge.to}`} viewBox="0 0 10 10"
                            refX={dx > 0 ? 10 : 0} refY={5} markerWidth={5} markerHeight={5}
                            orient={dx > 0 ? "auto" : "auto-start-reverse"}>
                            <path d="M 0 2 L 6 5 L 0 8 z" fill="#404040" opacity="0.6" />
                          </marker>
                        </defs>
                        <path d={`M ${fromNode.x} ${fromNode.y} Q ${cx} ${cy} ${toNode.x} ${toNode.y}`}
                          fill="none" stroke="#333" strokeWidth={1} opacity={0.35}
                          markerEnd={`url(#arr-${edge.from}-${edge.to})`} />
                        {edge.label && (
                          <text x={midX} y={midY - 6} textAnchor="middle" fill="#525252" fontSize={9} opacity={0.6}>{edge.label}</text>
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
                        style={{ cursor: "pointer" }}>
                        <circle cx={node.x} cy={node.y} r={radius + 4}
                          fill="none" stroke={mColor} strokeWidth={2}
                          strokeDasharray={`${(node.mastery / 100) * Math.PI * 2 * (radius + 4)} ${Math.PI * 2 * (radius + 4)}`}
                          opacity={node.mastery > 0 ? 0.6 : 0.15} />
                        <circle cx={node.x} cy={node.y} r={radius}
                          fill={isSelected ? color : node.can_practice ? "#0d0d0d" : "#1a1a1a"}
                          stroke={node.can_practice ? color : "#404040"}
                          strokeWidth={isSelected ? 2.5 : 1.5} opacity={node.can_practice ? 1 : 0.5} />
                        {!node.can_practice && (
                          <text x={node.x} y={node.y - radius - 8} textAnchor="middle" fill="#525252" fontSize={8}>🔒</text>
                        )}
                        <text x={node.x} y={node.y + 1} textAnchor="middle" dominantBaseline="middle"
                          fill={isSelected ? "#ffffff" : node.can_practice ? color : "#525252"}
                          fontSize={9} fontWeight={600}>
                          {node.label.length > 5 ? node.label.slice(0, 4) + "…" : node.label}
                        </text>
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
              {actualSubjects.map((subject) => (
                <div key={subject} className="flex items-center gap-2.5 text-sm">
                  <div className="w-3 h-3 flex-shrink-0" style={{ backgroundColor: subjectColors[subject] || fallbackColor }} />
                  <span className="text-[var(--color-text-secondary)]">{subject}</span>
                </div>
              ))}
              {actualSubjects.length === 0 && (
                <div className="text-xs text-[var(--color-text-muted)]">点击节点查看详情</div>
              )}
            </div>
            <div className="mt-3 pt-3 border-t border-[var(--color-surface)] space-y-1 text-[10px] text-[var(--color-text-muted)]">
              <div>🔒 = 前置知识未满足</div>
              <div>圆环 = 掌握进度 (0-100%)</div>
            </div>
          </Card>

          {/* Stats */}
          <Card title="统计">
            <div className="space-y-2 text-sm">
              {[["知识点", totalNodes], ["可练习", readyCount, "#22c55e"], ["被卡控", blockedCount, "#f97316"],
                ["关联边", totalEdges], ["平均掌握", `${avgMastery}%`]].map(([label, val, color]) => (
                <div key={label as string} className="flex justify-between">
                  <span className="text-[var(--color-text-muted)]">{label}</span>
                  <span className="font-medium" style={{ color: (color as string) || "var(--color-text)" }}>{val}</span>
                </div>
              ))}
            </div>
          </Card>

          {/* Node detail */}
          {selectedNode ? (
            <Card title="知识点详情">
              <div className="space-y-3">
                <div>
                  <div className="text-lg font-bold text-[var(--color-text)]">{selectedNode.label}</div>
                  <div className="text-xs text-[var(--color-text-muted)] mt-0.5">{selectedNode.subject}</div>
                </div>
                <div>
                  <div className="text-xs text-[var(--color-text-muted)] mb-1">掌握度 · {selectedNode.mastery_level}</div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 bg-[var(--color-surface)] h-2">
                      <div className="h-full transition-all duration-500"
                        style={{ width: `${selectedNode.mastery}%`, backgroundColor: masteryColor(selectedNode.mastery) }} />
                    </div>
                    <span className="text-sm text-[var(--color-text)] font-medium">{selectedNode.mastery}%</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-[var(--color-text-muted)]">状态:</span>
                  {selectedNode.can_practice ? (
                    <span className="text-xs px-2 py-0.5 border border-[#22c55e] text-[#22c55e]">可练习</span>
                  ) : (
                    <span className="text-xs px-2 py-0.5 border border-[#f97316] text-[#f97316]">前置未满足</span>
                  )}
                </div>
                {/* Prerequisites */}
                <div>
                  <div className="text-xs text-[var(--color-text-muted)] mb-1">前置知识</div>
                  <div className="flex flex-wrap gap-1.5">
                    {edges.filter((e) => e.to === selectedNode.id).map((e) => {
                      const fromNode = nodes.find((n) => n.id === e.from);
                      return (
                        <button key={e.from}
                          onClick={() => { const n = nodes.find(nn => nn.id === e.from); if (n) setSelectedNode(n); }}
                          className="text-xs px-2 py-1 border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)] cursor-pointer transition-colors"
                        >{fromNode?.label || e.from}</button>
                      );
                    })}
                    {edges.filter((e) => e.to === selectedNode.id).length === 0 && (
                      <span className="text-xs text-[var(--color-text-muted)]">无（入口知识点）</span>
                    )}
                  </div>
                </div>
              </div>
            </Card>
          ) : (
            <Card>
              <div className="text-center py-6">
                <Info size={20} className="text-[var(--color-text-muted)] mx-auto mb-2" />
                <div className="text-sm text-[var(--color-text-muted)]">点击节点查看详情</div>
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

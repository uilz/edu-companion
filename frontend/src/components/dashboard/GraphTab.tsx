// ── 客户端组件声明 ──
'use client';

import { useState, useEffect, useCallback, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { ZoomIn, ZoomOut, Maximize2, Info, Loader2, RefreshCw, ChevronDown, GitGraph, Plus, Trash2, Edit3, Link, X } from "lucide-react";
import Card from "@/components/ui/Card";
import NodeDetailCard from "./NodeDetailCard";
import type { GraphNode, GraphEdge, Coverage } from "./graph-layout";
import { computeLayout, masteryColor, subjectColors, fallbackColor } from "./graph-layout";
import type { KGNode, KGEdge } from "./graph-layout";

export function GraphTab() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const partitionIdFromUrl = searchParams.get("partition_id") || "";

  const [partitionId, setPartitionId] = useState(partitionIdFromUrl);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [rawGraph, setRawGraph] = useState<{ nodes: Record<string, KGNode>; edges: KGEdge[] }>({ nodes: {}, edges: [] });
  const [totalNodes, setTotalNodes] = useState(0);
  const [totalEdges, setTotalEdges] = useState(0);
  const [coverage, setCoverage] = useState<Coverage>({ total: 0, mastered: 0, learning: 0, weak: 0, untouched: 0 });
  const [anomalyCount, setAnomalyCount] = useState(0);
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
  const zoomRef = useRef(1);
  const panRef = useRef({ x: 0, y: 0 });
  useEffect(() => { zoomRef.current = zoom; }, [zoom]);
  useEffect(() => { panRef.current = pan; }, [pan]);

  const [editMode, setEditMode] = useState(false);
  const [addNodeOpen, setAddNodeOpen] = useState(false);
  const [newNodeLabel, setNewNodeLabel] = useState("");
  const [addEdgeFrom, setAddEdgeFrom] = useState<string | null>(null);
  const [editNodeId, setEditNodeId] = useState<string | null>(null);
  const [editNodeLabel, setEditNodeLabel] = useState("");

  const [partitions, setPartitions] = useState<{ id: string; name: string; emoji: string }[]>([]);
  const [showPicker, setShowPicker] = useState(false);
  const [loadingParts, setLoadingParts] = useState(false);
  const loadPartitions = useCallback(async () => {
    setLoadingParts(true);
    try {
      const res = await fetch("/api/conversations/tree/partition");
      const data = await res.json();
      setPartitions(data.partitions || []);
    } catch { /* ignore */ }
    finally { setLoadingParts(false); }
  }, []);

  useEffect(() => {
    if (partitionIdFromUrl && partitionIdFromUrl !== partitionId) setPartitionId(partitionIdFromUrl);
  }, [partitionIdFromUrl]);

  // ── 双数据源获取 ──
  const fetchGraph = useCallback(async () => {
    if (!partitionId) { setNodes([]); setEdges([]); return; }
    setLoading(true); setError("");
    try {
      const [kgRes, ppRes] = await Promise.all([
        fetch(`/api/knowledge/graph/${partitionId}`),
        fetch(`/api/partition-progress/${partitionId}`),
      ]);
      const kg = kgRes.ok ? await kgRes.json() : { nodes: {}, edges: [] };
      const pp = ppRes.ok ? await ppRes.json() : {};
      setRawGraph({ nodes: kg.nodes || {}, edges: kg.edges || [] });

      const skills = pp.skills || {};
      const anomalies = pp.anomalies || [];
      const anomalyMap = new Map<string, any>();
      anomalies.forEach((a: { skills?: string[]; [key: string]: unknown }) => (a.skills || []).forEach((sid: string) => anomalyMap.set(sid, a)));

      const nodeMap = new Map<string, GraphNode>();
      for (const [id, n] of Object.entries(kg.nodes || {}) as [string, KGNode][]) {
        const s = skills[id];
        nodeMap.set(id, {
          id, label: n.label || "", description: n.description || "", subject: partitionId,
          mastery: s?.mastery || 0, mastery_level: s?.mastery_level || "未接触",
          confidence: s?.confidence || 0, blocked: s?.blocked ?? false,
          blocked_by: s?.prerequisites_met ? [] : (s?.prerequisites || []),
          attempt_count: s?.attempt_count || 0, error_clusters: s?.error_clusters || [],
          trend: s?.trend || "stable", review_urgency: s?.review_urgency || 0,
          anomaly_type: anomalyMap.has(id) ? anomalyMap.get(id).type : null,
          anomaly_detail: anomalyMap.has(id) ? anomalyMap.get(id).detail : null,
        });
      }
      for (const [id, s] of Object.entries(skills as Record<string, any>)) {
        if (!nodeMap.has(id)) {
          nodeMap.set(id, {
            id, label: s.label || id, description: "", subject: partitionId,
            mastery: s.mastery || 0, mastery_level: s.mastery_level || "未接触",
            confidence: s.confidence || 0, blocked: s.blocked ?? false,
            blocked_by: s.prerequisites_met ? [] : (s.prerequisites || []),
            attempt_count: s.attempt_count || 0, error_clusters: s.error_clusters || [],
            trend: s.trend || "stable", review_urgency: s.review_urgency || 0,
            anomaly_type: anomalyMap.has(id) ? anomalyMap.get(id).type : null,
            anomaly_detail: anomalyMap.has(id) ? anomalyMap.get(id).detail : null,
          });
        }
      }

      const edgeList: GraphEdge[] = (kg.edges || []).map((e: KGEdge) => ({
        from: e.from_id, to: e.to_id, label: e.label || e.relation || "", satisfied: false, edgeId: e.id,
      }));
      for (const d of (pp.dependencies || [])) {
        const exists = edgeList.some(e => e.from === d.from_skill && e.to === d.to_skill);
        if (!exists) edgeList.push({ from: d.from_skill, to: d.to_skill, label: d.relation === "prerequisite" ? "前置" : (d.relation || ""), satisfied: d.satisfied ?? false });
      }

      const rawNodes = Array.from(nodeMap.values());
      setNodes(computeLayout(rawNodes, edgeList));
      setEdges(edgeList);
      setTotalNodes(rawNodes.length);
      setTotalEdges(edgeList.length);
      setCoverage(pp.coverage || { total: 0, mastered: 0, learning: 0, weak: 0, untouched: 0 });
      setAnomalyCount(anomalies.length);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally { setLoading(false); }
  }, [partitionId]);

  useEffect(() => { fetchGraph(); }, [fetchGraph]);

  // ── CRUD ──
  const api = (path: string, opts?: RequestInit) => fetch(`/api/knowledge/graph/${partitionId}${path}`, { headers: { "Content-Type": "application/json" }, ...opts });

  const handleAddNode = async () => {
    if (!newNodeLabel.trim()) return;
    await api("/node", { method: "POST", body: JSON.stringify({ label: newNodeLabel.trim() }) });
    setNewNodeLabel(""); setAddNodeOpen(false); await fetchGraph();
  };

  const handleDeleteNode = async (nodeId: string) => {
    if (!confirm("删除此节点及其关联边？")) return;
    await api(`/node/${nodeId}`, { method: "DELETE" });
    if (selectedNode?.id === nodeId) setSelectedNode(null);
    await fetchGraph();
  };

  const handleEditNode = async () => {
    if (!editNodeId || !editNodeLabel.trim()) return;
    await api(`/node/${editNodeId}`, { method: "PATCH", body: JSON.stringify({ label: editNodeLabel.trim() }) });
    setEditNodeId(null); setEditNodeLabel(""); await fetchGraph();
  };

  const handleAddEdge = async (toId: string) => {
    if (!addEdgeFrom || addEdgeFrom === toId) { setAddEdgeFrom(null); return; }
    await api("/edge", { method: "POST", body: JSON.stringify({ from_id: addEdgeFrom, to_id: toId, relation: "prerequisite" }) });
    setAddEdgeFrom(null); await fetchGraph();
  };

  const handleDeleteEdge = async (edgeId: string) => {
    await api(`/edge/${edgeId}`, { method: "DELETE" });
    await fetchGraph();
  };

  const handleGenerate = async () => {
    setGenerating(true); setGenerateError("");
    try {
      const res = await fetch(`/api/knowledge/graph/${partitionId}/generate`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ depth: 3 }) });
      const json = await res.json();
      if (res.ok && json.ok) await fetchGraph();
      else setGenerateError(json?.detail || json?.error || "生成失败");
    } catch (e) { setGenerateError(e instanceof Error ? e.message : "网络异常"); }
    finally { setGenerating(false); }
  };

  const switchPartition = (pid: string) => {
    setPartitionId(pid); setShowPicker(false); setSelectedNode(null);
    const params = new URLSearchParams(searchParams.toString());
    params.set("partition_id", pid);
    router.replace(`/dashboard?${params.toString()}`, { scroll: false });
  };

  // ── 交互事件 ──
  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.target === svgRef.current || (e.target as Element).tagName === "rect") {
      setIsPanning(true); panStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
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
    const oldZoom = zoomRef.current;
    const newZoom = Math.min(2, Math.max(0.3, oldZoom + delta));
    const svgX = (mouseX - panRef.current.x) / oldZoom, svgY = (mouseY - panRef.current.y) / oldZoom;
    panRef.current = { x: mouseX - svgX * newZoom, y: mouseY - svgY * newZoom };
    zoomRef.current = newZoom; setZoom(newZoom); setPan(panRef.current);
  }, []);
  useEffect(() => {
    const svg = svgRef.current; if (!svg) return;
    svg.addEventListener("wheel", handleWheel, { passive: false });
    return () => svg.removeEventListener("wheel", handleWheel);
  }, [handleWheel]);
  const resetView = () => { setZoom(1); setPan({ x: 0, y: 0 }); };

  const avgMastery = nodes.length > 0 ? Math.round(nodes.reduce((s, n) => s + n.mastery, 0) / nodes.length) : 0;
  const maxX = Math.max(700, ...nodes.map((n) => (n.x || 0) + 100));
  const maxY = Math.max(500, ...nodes.map((n) => (n.y || 0) + 100));

  // ── 条件渲染 ──
  if (!partitionId) {
    return (
      <div className="text-center py-16">
        <GitGraph size={36} className="mx-auto mb-4 text-[var(--color-text-muted)] opacity-50" />
        <h2 className="text-lg font-semibold text-[var(--color-text)] mb-2">选择分区查看知识图谱</h2>
        <p className="text-sm text-[var(--color-text-muted)] mb-6">从学习空间侧栏点击图谱图标，或在此选择分区</p>
        <button onClick={() => { setShowPicker(true); loadPartitions(); }}
          className="inline-flex items-center gap-2 px-5 py-2.5 bg-[var(--color-accent)] text-white text-sm hover:opacity-90 active:scale-[0.97] transition-transform">
          <GitGraph size={14} /> 选择分区
        </button>
        {showPicker && <PartitionPickerOverlay partitions={partitions} loading={loadingParts} onSelect={switchPartition} onClose={() => setShowPicker(false)} />}
      </div>
    );
  }
  if (loading) return <div className="flex items-center justify-center py-20 gap-4"><Loader2 size={24} className="animate-spin text-[var(--color-accent)]" /><span className="text-sm text-[var(--color-text-muted)]">加载知识图谱…</span></div>;
  if (error) return <div className="flex flex-col items-center justify-center py-20 gap-4"><span className="text-sm text-[var(--color-text-muted)]">{error}</span><button onClick={fetchGraph} className="px-4 py-2 text-xs border border-[var(--color-border)]">重试</button></div>;

  return (
    <div>
      {/* 顶栏 */}
      <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="relative">
            <button onClick={() => { setShowPicker(!showPicker); if (!showPicker) loadPartitions(); }}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm border border-[var(--color-border)] text-[var(--color-text)] hover:bg-[var(--color-surface)]">
              <GitGraph size={14} className="text-[var(--color-accent)]" />
              <span>{partitions.find(p => p.id === partitionId)?.emoji || "📁"} {partitions.find(p => p.id === partitionId)?.name || partitionId}</span>
              <ChevronDown size={12} className={`transition-transform ${showPicker ? "rotate-180" : ""}`} />
            </button>
            {showPicker && <PartitionPickerOverlay partitions={partitions} loading={loadingParts} onSelect={switchPartition} onClose={() => setShowPicker(false)} currentId={partitionId} />}
          </div>
          <span className="text-xs text-[var(--color-text-muted)]">
            {totalNodes} 知识点 · {totalEdges} 关联 · 掌握 {coverage.mastered} · 学习 {coverage.learning} · 薄弱 {coverage.weak} · 未接触 {coverage.untouched}
            {anomalyCount > 0 && <span className="text-[#f97316] ml-1">⚠️{anomalyCount}</span>}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setEditMode(!editMode)}
            className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium border transition-opacity ${editMode ? "border-[var(--color-accent)] text-[var(--color-accent)]" : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:opacity-80"}`}>
            <Edit3 size={14} /> {editMode ? "完成编辑" : "编辑图谱"}
          </button>
          <button onClick={handleGenerate} disabled={generating}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 active:scale-[0.97] transition-transform">
            {generating ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} AI 生成
          </button>
        </div>
      </div>

      {generateError && <p className="text-xs text-[#f97316] mb-4">{generateError}</p>}

      {/* 编辑工具栏 */}
      {editMode && (
        <div className="flex items-center gap-3 mb-4 p-3 border border-[var(--color-border)] bg-[var(--color-surface)] flex-wrap">
          <button onClick={() => setAddNodeOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white hover:opacity-90 active:scale-[0.97] transition-transform">
            <Plus size={12} /> 添加节点
          </button>
          <button onClick={() => setAddEdgeFrom(addEdgeFrom ? null : selectedNode?.id || null)}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs border ${addEdgeFrom ? "border-[#f97316] text-[#f97316]" : "border-[var(--color-border)] text-[var(--color-text-secondary)]"} hover:opacity-80`}>
            <Link size={12} /> {addEdgeFrom ? "点击目标节点完成连线" : "添加连线"}
          </button>
          {addEdgeFrom && <span className="text-xs text-[#f97316]">从「{nodes.find(n => n.id === addEdgeFrom)?.label}」出发 → 点击目标节点</span>}
        </div>
      )}

      {/* 添加节点弹窗 */}
      {addNodeOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-5 w-80 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-[var(--color-text)]">添加知识节点</h3>
              <button onClick={() => setAddNodeOpen(false)}><X size={14} className="text-[var(--color-text-muted)]" /></button>
            </div>
            <input value={newNodeLabel} onChange={e => setNewNodeLabel(e.target.value)} onKeyDown={e => e.key === "Enter" && handleAddNode()}
              placeholder="知识点名称" autoFocus
              className="w-full px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] outline-none" />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setAddNodeOpen(false)} className="px-3 py-1.5 text-xs border border-[var(--color-border)]">取消</button>
              <button onClick={handleAddNode} className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white active:scale-[0.97] transition-transform">添加</button>
            </div>
          </div>
        </div>
      )}

      {/* 编辑节点弹窗 */}
      {editNodeId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-[var(--color-card)] border border-[var(--color-border)] p-5 w-80 space-y-3">
            <h3 className="text-sm font-semibold text-[var(--color-text)]">编辑节点名称</h3>
            <input value={editNodeLabel} onChange={e => setEditNodeLabel(e.target.value)} onKeyDown={e => e.key === "Enter" && handleEditNode()}
              className="w-full px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] outline-none" />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setEditNodeId(null)} className="px-3 py-1.5 text-xs border border-[var(--color-border)]">取消</button>
              <button onClick={handleEditNode} className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white active:scale-[0.97] transition-transform">保存</button>
            </div>
          </div>
        </div>
      )}

      {/* 主区域 */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        <div className="lg:col-span-3">
          <div className="border border-[var(--color-border)] bg-[var(--color-card)] overflow-hidden relative" style={{ minHeight: 480, overflow: "auto" }}>
            <div className="absolute top-3 right-3 z-10 flex gap-1">
              <button onClick={() => setZoom(z => Math.min(2, z + 0.2))} className="w-8 h-8 flex items-center justify-center bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"><ZoomIn size={14} /></button>
              <button onClick={() => setZoom(z => Math.max(0.3, z - 0.2))} className="w-8 h-8 flex items-center justify-center bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"><ZoomOut size={14} /></button>
              <button onClick={resetView} className="w-8 h-8 flex items-center justify-center bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"><Maximize2 size={14} /></button>
            </div>

            {nodes.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-96 gap-3">
                <GitGraph size={28} className="text-[var(--color-text-muted)] opacity-40" />
                <span className="text-sm text-[var(--color-text-muted)]">暂无图谱数据</span>
                <div className="flex gap-2 mt-2">
                  <button onClick={() => { setEditMode(true); setAddNodeOpen(true); }}
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:opacity-80">
                    <Plus size={14} /> 手动添加
                  </button>
                  <button onClick={handleGenerate} disabled={generating}
                    className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 active:scale-[0.97] transition-transform">
                    {generating ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />} AI 生成
                  </button>
                </div>
              </div>
            ) : (
              <svg ref={svgRef} className="w-full" viewBox={`0 0 ${maxX} ${maxY}`}
                onMouseDown={handleMouseDown} onMouseMove={handleMouseMove}
                onMouseUp={() => setIsPanning(false)} onMouseLeave={() => setIsPanning(false)}
                style={{ cursor: isPanning ? "grabbing" : addEdgeFrom ? "crosshair" : "grab", userSelect: "none" as React.CSSProperties["userSelect"] }}>
                <g transform={`translate(${pan.x / 2},${pan.y / 2}) scale(${zoom})`}>
                  {/* Edges */}
                  {edges.map((edge) => {
                    const fromNode = nodes.find((n) => n.id === edge.from);
                    const toNode = nodes.find((n) => n.id === edge.to);
                    if (!fromNode?.x || !toNode?.x) return null;
                    const dx = toNode.x - fromNode.x, dy = (toNode.y || 0) - (fromNode.y || 0);
                    const cx = fromNode.x + dx * 0.6, cy = (fromNode.y || 0) + dy * 0.3;
                    const midX = fromNode.x + dx * 0.45, midY = (fromNode.y || 0) + dy * 0.35;
                    const edgeColor = edge.satisfied ? "#22c55e" : "#f97316";
                    const dashArray = edge.satisfied ? undefined : "6,3";
                    return (
                      <g key={`${edge.from}-${edge.to}`} className="group">
                        <defs>
                          <marker id={`arr-${edge.from}-${edge.to}`} viewBox="0 0 10 10" refX={dx > 0 ? 10 : 0} refY={5} markerWidth={5} markerHeight={5} orient={dx > 0 ? "auto" : "auto-start-reverse"}>
                            <path d="M 0 2 L 6 5 L 0 8 z" fill={edgeColor} opacity="0.7" />
                          </marker>
                        </defs>
                        <path d={`M ${fromNode.x} ${fromNode.y} Q ${cx} ${cy} ${toNode.x} ${toNode.y}`}
                          fill="none" stroke={edgeColor} strokeWidth={edge.satisfied ? 1.2 : 1}
                          strokeDasharray={dashArray} opacity={edge.satisfied ? 0.5 : 0.35}
                          markerEnd={`url(#arr-${edge.from}-${edge.to})`} />
                        {edge.label && <text x={midX} y={midY - 6} textAnchor="middle" fill="#525252" fontSize={9} opacity={0.6}>{edge.label}</text>}
                        {editMode && edge.edgeId && (
                          <g onClick={() => handleDeleteEdge(edge.edgeId!)} style={{ cursor: "pointer", opacity: 0 }} className="hover:opacity-100">
                            <rect x={midX - 8} y={midY - 18} width={16} height={16} rx={2} fill="var(--color-error)" opacity={0.8} />
                            <text x={midX} y={midY - 7} textAnchor="middle" fill="white" fontSize={10} fontWeight="bold">×</text>
                          </g>
                        )}
                      </g>
                    );
                  })}
                  {/* Nodes */}
                  {nodes.map((node) => {
                    if (!node.x || !node.y) return null;
                    const isSelected = selectedNode?.id === node.id;
                    const isEdgeTarget = addEdgeFrom && addEdgeFrom !== node.id;
                    const color = subjectColors[node.subject] || fallbackColor;
                    const mColor = masteryColor(node.mastery);
                    const radius = isSelected ? 28 : 23;
                    const hasAnomaly = !!node.anomaly_type;
                    return (
                      <g key={node.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          if (addEdgeFrom) { handleAddEdge(node.id); return; }
                          setSelectedNode(isSelected ? null : node);
                        }}
                        style={{ cursor: isEdgeTarget ? "crosshair" : "pointer" }}>
                        <circle cx={node.x} cy={node.y} r={radius + 4} fill="none" stroke={mColor} strokeWidth={2}
                          strokeDasharray={`${(node.mastery / 100) * Math.PI * 2 * (radius + 4)} ${Math.PI * 2 * (radius + 4)}`}
                          opacity={node.mastery > 0 ? 0.6 : 0.15} />
                        <circle cx={node.x} cy={node.y} r={radius}
                          fill={isSelected ? color : isEdgeTarget ? "#1a3a1a" : node.blocked ? "#1a1a1a" : "#0d0d0d"}
                          stroke={isEdgeTarget ? "#22c55e" : node.blocked ? "#404040" : color}
                          strokeWidth={isSelected || isEdgeTarget ? 2.5 : 1.5} opacity={node.blocked ? 0.5 : 1} />
                        {node.blocked && <text x={node.x} y={node.y - radius - 8} textAnchor="middle" fill="#525252" fontSize={8}>🔒</text>}
                        {hasAnomaly && !node.blocked && <text x={node.x + radius - 4} y={node.y - radius + 2} textAnchor="middle" fontSize={10}>⚠️</text>}
                        <text x={node.x} y={node.y + 1} textAnchor="middle" dominantBaseline="middle"
                          fill={isSelected ? "#ffffff" : node.blocked ? "#525252" : color} fontSize={9} fontWeight={600}>
                          {node.label.length > 5 ? node.label.slice(0, 4) + "…" : node.label}
                        </text>
                        <title>{node.label} — {node.mastery_level} ({node.mastery}%){node.blocked ? " 🔒前置未满足" : ""}{hasAnomaly ? " ⚠️" + node.anomaly_detail : ""}</title>
                        {editMode && (
                          <g>
                            <circle cx={node.x + radius + 6} cy={node.y - radius - 2} r={8} fill="var(--color-error)" opacity={0.7} style={{ cursor: "pointer" }}
                              onClick={(e) => { e.stopPropagation(); handleDeleteNode(node.id); }} />
                            <text x={node.x + radius + 6} y={node.y - radius + 1} textAnchor="middle" fill="white" fontSize={9} fontWeight="bold" style={{ pointerEvents: "none" }}>×</text>
                            <circle cx={node.x - radius - 6} cy={node.y - radius - 2} r={8} fill="var(--color-accent)" opacity={0.7} style={{ cursor: "pointer" }}
                              onClick={(e) => { e.stopPropagation(); setEditNodeId(node.id); setEditNodeLabel(node.label); }} />
                            <text x={node.x - radius - 6} y={node.y - radius + 1} textAnchor="middle" fill="white" fontSize={8} style={{ pointerEvents: "none" }}>✎</text>
                          </g>
                        )}
                      </g>
                    );
                  })}
                </g>
              </svg>
            )}
          </div>
        </div>

        {/* 侧边栏 */}
        <div className="space-y-4">
          <Card title="图例">
            <div className="space-y-2">
              <div className="flex items-center gap-2.5 text-sm"><div className="w-3 h-3 rounded-full" style={{ backgroundColor: "#22c55e" }} /><span className="text-[var(--color-text-secondary)]">已掌握 ≥80%</span></div>
              <div className="flex items-center gap-2.5 text-sm"><div className="w-3 h-3 rounded-full" style={{ backgroundColor: "#84cc16" }} /><span className="text-[var(--color-text-secondary)]">发展中 40-80%</span></div>
              <div className="flex items-center gap-2.5 text-sm"><div className="w-3 h-3 rounded-full" style={{ backgroundColor: "#f97316" }} /><span className="text-[var(--color-text-secondary)]">薄弱 &lt;40%</span></div>
            </div>
            <div className="mt-3 pt-3 border-t border-[var(--color-surface)] space-y-1 text-[10px] text-[var(--color-text-muted)]">
              <div>🔒 = 前置知识未满足</div>
              <div>⚠️ = 异常（停滞/跳跃/遗忘）</div>
              <div>圆环 = 掌握进度 (0-100%)</div>
            </div>
          </Card>

          <Card title="统计">
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">知识点</span><span className="font-medium">{totalNodes}</span></div>
              <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">已掌握</span><span className="font-medium text-[#22c55e]">{coverage.mastered}</span></div>
              <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">学习中</span><span className="font-medium text-[#84cc16]">{coverage.learning}</span></div>
              <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">薄弱</span><span className="font-medium text-[#f97316]">{coverage.weak}</span></div>
              <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">未接触</span><span className="font-medium text-[#525252]">{coverage.untouched}</span></div>
              <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">平均掌握</span><span className="font-medium">{avgMastery}%</span></div>
              {anomalyCount > 0 && <div className="flex justify-between"><span className="text-[var(--color-text-muted)]">⚠️异常</span><span className="font-medium text-[#f59e0b]">{anomalyCount}</span></div>}
            </div>
          </Card>

          {selectedNode ? (
            <NodeDetailCard selectedNode={selectedNode} edges={edges} nodes={nodes} onSelectNode={setSelectedNode} />
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

// ── 分区选择器浮层（内联小型组件） ──
function PartitionPickerOverlay({ partitions, loading, onSelect, onClose, currentId }: {
  partitions: { id: string; name: string; emoji: string }[];
  loading: boolean;
  onSelect: (pid: string) => void;
  onClose: () => void;
  currentId?: string;
}) {
  return (
    <>
      <div className="fixed inset-0 z-10" onClick={onClose} />
      <div className="absolute top-full mt-1 left-0 z-20 w-64 max-h-64 overflow-y-auto border border-[var(--color-border)] bg-[var(--color-bg)] shadow-lg">
        {loading
          ? <div className="px-4 py-6 text-center"><Loader2 size={14} className="animate-spin mx-auto" /></div>
          : partitions.length === 0
            ? <div className="px-4 py-6 text-center text-xs text-[var(--color-text-muted)]">暂无分区</div>
            : partitions.map((p) => (
                <button key={p.id} onClick={() => onSelect(p.id)}
                  className={`block w-full text-left px-4 py-2.5 text-sm hover:bg-[var(--color-surface)] ${p.id === currentId ? "text-[var(--color-accent)] bg-[var(--color-accent)]/5 font-medium" : "text-[var(--color-text-secondary)]"}`}>
                  <span className="mr-2">{p.emoji || "📁"}</span>{p.name}
                </button>
              ))
        }
      </div>
    </>
  );
}

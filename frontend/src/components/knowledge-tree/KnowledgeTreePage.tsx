"use client";

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Plus, X, Check, AlertCircle, Sparkles, Loader2, ZoomIn, ZoomOut,
  RefreshCw, Brain, Trash2,
} from "lucide-react";
import { useKnowledgeTree } from "@/hooks/knowledge-tree/useKnowledgeTree";
import KnowledgeTreeGraph from "./KnowledgeTreeGraph";
import LayerPanel from "./LayerPanel";
import ContextMenu, { getDefaultContextMenuItems } from "./ContextMenu";
import StatusBar from "./StatusBar";
import TreeNodeDetailPanel from "./TreeNodeDetailPanel";
import ResizeHandle from "@/components/ui/ResizeHandle";
import { useIsMobile } from "@/hooks/useMediaQuery";
import EmojiPicker from "@/components/ui/EmojiPicker";
import type { TreeNode, TreeEdge } from "@/lib/api/knowledge-trees-api";
import type { GraphData, GraphNode, GraphEdge } from "@/lib/types/graph-types";
import { cognitiveSearchApi } from "@/lib/api/knowledge-trees-api";

export type GraphMode = "tree" | "graph" | "mindmap" | "force" | "dag";

export interface DialogState {
  type: "normal" | "tree_exploration" | "temporary";
  conversationId: string;
  parentId: string;
  parentType: "dir";
  boundNode?: GraphNode | null;
}

// ═══════════════════════════════════════════════════════════════
// 适配：新 TreeNode/TreeEdge → 旧 GraphData（用于层级面板等）
// ═══════════════════════════════════════════════════════════════

function treeNodeToGraphNode(node: TreeNode): GraphNode {
  const cv = node.cognitive_view;
  return {
    id: node.id,
    label: node.label,
    description: node.brief || "",
    level: node.node_type === "topic" ? "domain" : node.node_type === "concept" ? "concept" : "atom",
    mastery: cv?.proficiency ?? 0,
    trend: "stable",
    priority: Math.round((cv?.urgency ?? 0) * 10),
    tags: node.tags || [],
    created_by: "user",
    children: node.children_order || node.children_ids || [],
    parent: node.parent_id || undefined,
    is_visible: node.status !== "deleted",
    node_type: node.node_type,
    path_id: node.tree_id,
    emoji: node.emoji,
    color: cv?.display_color || node.color,
    brief: node.brief,
    conv_ids: [],
  };
}

function treeEdgeToGraphEdge(edge: TreeEdge): GraphEdge {
  return {
    id: edge.id,
    source: edge.source_node_id,
    target: edge.target_node_id,
    label: edge.edge_type,
    relation: edge.edge_type,
    strength: edge.strength,
  };
}

function buildGraphData(nodes: TreeNode[], edges: TreeEdge[]): GraphData {
  return {
    nodes: nodes.map(treeNodeToGraphNode),
    edges: edges.map(treeEdgeToGraphEdge),
  };
}

function buildStats(nodes: TreeNode[]) {
  const total = nodes.length;
  if (total === 0) {
    return { total: 0, mastered: 0, learning: 0, untouched: 0, avgMastery: 0 };
  }
  let mastered = 0;
  let learning = 0;
  let untouched = 0;
  let sum = 0;
  nodes.forEach((n) => {
    const p = n.cognitive_view?.proficiency ?? 0;
    sum += p;
    if (p >= 0.8) mastered++;
    else if (p >= 0.05) learning++;
    else untouched++;
  });
  return {
    total,
    mastered,
    learning,
    untouched,
    avgMastery: sum / total,
  };
}

// ═══════════════════════════════════════════════════════════════
// 子组件
// ═══════════════════════════════════════════════════════════════

function LoadingSkeleton() {
  return (
    <div className="flex flex-col h-full min-h-[600px]">
      <div className="h-[48px] bg-surface border-b border flex-shrink-0" />
      <div className="flex flex-1 overflow-hidden">
        <div className="w-[320px] bg-surface border-r border animate-pulse" />
        <div className="flex-1 p-8 space-y-4 animate-pulse">
          <div className="h-6 bg-surface rounded w-1/3" />
          <div className="grid grid-cols-4 gap-4">
            {[1,2,3,4,5,6,7,8].map(i => (
              <div key={i} className="h-24 bg-surface rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyState({ onCreateTree }: { onCreateTree: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[500px] gap-6 px-4">
      <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-accent/10 to-accent/5 flex items-center justify-center shadow-sm border border">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-accent">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
        </svg>
      </div>
      <div className="text-center max-w-sm space-y-2">
        <h3 className="text-lg font-semibold text">暂无知识树</h3>
        <p className="text-sm text-muted leading-relaxed">创建一个知识树，开始结构化你的学习。</p>
      </div>
      <button onClick={onCreateTree}
        className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium bg-accent text-white rounded-xl hover:opacity-90 transition-all shadow-sm">
        <Plus size={14} /> 创建知识树
      </button>
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[400px] gap-4 px-4">
      <div className="w-20 h-20 rounded-2xl bg-danger/5 border border-danger/10 flex items-center justify-center">
        <AlertCircle className="text-danger" size={32} />
      </div>
      <div className="text-center max-w-sm space-y-1">
        <h3 className="text-sm font-semibold text">加载失败</h3>
        <p className="text-xs text-muted">{message}</p>
      </div>
      <button onClick={onRetry}
        className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium border border rounded-lg text-secondary hover:bg-surface transition-colors">
        <RefreshCw size={12} /> 重试
      </button>
    </div>
  );
}

function ZoomControls({ zoom, onZoomIn, onZoomOut, onReset }: {
  zoom: number; onZoomIn: () => void; onZoomOut: () => void; onReset: () => void;
}) {
  return (
    <div className="absolute bottom-4 right-4 flex items-center gap-0.5 p-1 rounded-xl z-20"
      style={{
        background: "rgba(15,15,22,0.75)",
        backdropFilter: "blur(16px) saturate(160%)",
        WebkitBackdropFilter: "blur(16px) saturate(160%)",
        border: "1px solid rgba(255,255,255,0.06)",
        boxShadow: "0 4px 24px rgba(0,0,0,0.3)",
      }}>
      <button onClick={onZoomOut} disabled={zoom <= 0.3}
        className="p-1.5 rounded-lg text-white/50 hover:text-white hover:bg-white/5 disabled:opacity-20 transition-all">
        <ZoomOut size={14} />
      </button>
      <button onClick={onReset}
        className="px-2 py-1 text-[10px] font-medium text-white/50 hover:text-white hover:bg-white/5 rounded-lg transition-all font-mono">
        {Math.round(zoom * 100)}%
      </button>
      <button onClick={onZoomIn} disabled={zoom >= 3}
        className="p-1.5 rounded-lg text-white/50 hover:text-white hover:bg-white/5 disabled:opacity-20 transition-all">
        <ZoomIn size={14} />
      </button>
    </div>
  );
}

function AddNodeDialog({
  open, onClose, onAdd, nodes, parentId, setParentId,
}: {
  open: boolean; onClose: () => void; onAdd: (label: string) => void;
  nodes: TreeNode[]; parentId: string | null; setParentId: (id: string | null) => void;
}) {
  const [label, setLabel] = useState("");
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="bg-surface border border rounded-xl p-5 w-80 space-y-4 shadow-xl">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text">{parentId ? "添加子节点" : "添加根节点"}</h3>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-surface-hover"><X size={14} className="text-muted" /></button>
        </div>
        <div className="space-y-3">
          <input value={label} onChange={e => setLabel(e.target.value)}
            placeholder="输入节点名称" autoFocus
            className="w-full px-3 py-2 text-sm bg-page border border text rounded-lg focus:outline-none focus:border-accent"
            onKeyDown={e => { if (e.key === "Enter" && label.trim()) { onAdd(label.trim()); setLabel(""); } if (e.key === "Escape") onClose(); }} />
          <select value={parentId ?? ""} onChange={e => setParentId(e.target.value || null)}
            className="w-full px-3 py-2 text-xs bg-page border border text rounded-lg focus:outline-none focus:border-accent">
            <option value="">无父节点（根节点）</option>
            {nodes.map(n => <option key={n.id} value={n.id}>{n.label}</option>)}
          </select>
        </div>
        <div className="flex gap-2 justify-end">
          <button onClick={onClose} className="px-3 py-1.5 text-xs border border rounded-lg text-muted hover:bg-surface-hover">取消</button>
          <button onClick={() => { onAdd(label.trim()); setLabel(""); }} disabled={!label.trim()}
            className="px-3 py-1.5 text-xs bg-accent text-white rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-1">
            <Check size={12} /> 确认
          </button>
        </div>
      </div>
    </div>
  );
}

function CognitiveLinkDialog({
  open, onClose, onLink,
}: {
  open: boolean; onClose: () => void; onLink: (cognitiveNodeId: string) => void;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<{ cognitive_node_id: string; label: string; level: string }[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setQ("");
    setResults([]);
  }, [open]);

  const search = useCallback(async () => {
    if (!q.trim()) return;
    setLoading(true);
    try {
      const res = await cognitiveSearchApi.search(q.trim(), 20);
      setResults(res.nodes || []);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }, [q]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="bg-surface border border rounded-xl p-5 w-96 space-y-4 shadow-xl">
        <h3 className="text-sm font-semibold text">关联认知节点</h3>
        <div className="flex gap-2">
          <input value={q} onChange={e => setQ(e.target.value)}
            placeholder="搜索认知节点…"
            className="flex-1 px-3 py-2 text-sm bg-page border border text rounded-lg focus:outline-none focus:border-accent"
            onKeyDown={e => e.key === "Enter" && search()} />
          <button onClick={search} disabled={loading}
            className="px-3 py-2 text-xs bg-accent text-white rounded-lg hover:opacity-90 disabled:opacity-50">
            {loading ? <Loader2 size={12} className="animate-spin" /> : "搜索"}
          </button>
        </div>
        <div className="max-h-[200px] overflow-y-auto space-y-1">
          {results.map(r => (
            <button key={r.cognitive_node_id} onClick={() => onLink(r.cognitive_node_id)}
              className="w-full text-left px-3 py-2 text-xs rounded-lg hover:bg-accent/10 text border border-transparent hover:border-accent/30">
              {r.label} <span className="text-muted ml-1">({r.level})</span>
            </button>
          ))}
          {results.length === 0 && !loading && <div className="text-xs text-muted text-center py-4">输入关键词搜索</div>}
        </div>
        <button onClick={onClose} className="w-full px-3 py-2 text-xs border border rounded-lg text-muted hover:bg-surface-hover">取消</button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// 主组件
// ═══════════════════════════════════════════════════════════════

export default function KnowledgeTreePage() {
  const kt = useKnowledgeTree();
  const isMobile = useIsMobile();

  const [showCreateTree, setShowCreateTree] = useState(false);
  const [newTreeName, setNewTreeName] = useState("");
  const [newTreeEmoji, setNewTreeEmoji] = useState("");

  const [addNodeOpen, setAddNodeOpen] = useState(false);
  const [newNodeParent, setNewNodeParent] = useState<string | null>(null);

  const [linkDialogOpen, setLinkDialogOpen] = useState(false);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; node: TreeNode } | null>(null);

  const [showDetailPanel, setShowDetailPanel] = useState(true);
  const [detailWidth, setDetailWidth] = useState(320);
  const [layerOpen, setLayerOpen] = useState(false);
  const [graphSearch, setGraphSearch] = useState("");

  const canvasRef = useRef<HTMLDivElement>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 800, height: 600 });

  useEffect(() => {
    if (!canvasRef.current) return;
    const el = canvasRef.current;
    const obs = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setCanvasSize({ width: entry.contentRect.width, height: entry.contentRect.height });
      }
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  const graphData = useMemo(() => buildGraphData(kt.nodes, kt.edges), [kt.nodes, kt.edges]);

  const stats = useMemo(() => buildStats(kt.nodes), [kt.nodes]);

  const matchedNodeIds = useMemo(() => {
    if (!graphSearch.trim()) return [];
    const q = graphSearch.trim().toLowerCase();
    return kt.nodes.filter(n => n.label.toLowerCase().includes(q)).map(n => n.id);
  }, [graphSearch, kt.nodes]);

  const handleCreateTree = useCallback(async () => {
    if (!newTreeName.trim()) return;
    await kt.createTree(newTreeName.trim(), "project");
    setNewTreeName("");
    setNewTreeEmoji("");
    setShowCreateTree(false);
  }, [kt, newTreeName]);

  const handleAddNode = useCallback(async (label: string) => {
    await kt.createNode(label, newNodeParent || null);
    setAddNodeOpen(false);
    setNewNodeParent(null);
  }, [kt, newNodeParent]);

  const handleNodeClick = useCallback((node: TreeNode) => {
    kt.selectNode(node.id);
    setShowDetailPanel(true);
  }, [kt]);

  const handleNodeDoubleClick = useCallback((node: TreeNode) => {
    // 双击可聚焦或展开，暂时占位
  }, []);

  const handleNodeContextMenu = useCallback((node: TreeNode, e: MouseEvent) => {
    setContextMenu({ x: e.clientX, y: e.clientY, node });
  }, []);

  const handleContextMenuAction = useCallback((action: string) => {
    const node = contextMenu?.node;
    if (!node) return;
    if (action === "add-child") {
      setNewNodeParent(node.id);
      setAddNodeOpen(true);
    } else if (action === "edit") {
      const label = window.prompt("编辑节点名称", node.label);
      if (label?.trim()) kt.updateNode(node.id, { label: label.trim() });
    } else if (action === "delete") {
      if (window.confirm(`确定删除节点 "${node.label}" 吗？`)) kt.deleteNode(node.id);
    } else if (action === "link-cognitive") {
      kt.selectNode(node.id);
      setLinkDialogOpen(true);
    }
    setContextMenu(null);
  }, [contextMenu, kt]);

  const handleLinkCognitive = useCallback(async (cognitiveNodeId: string) => {
    if (!kt.selectedNode) return;
    await kt.linkCognitive(kt.selectedNode.id, cognitiveNodeId);
    setLinkDialogOpen(false);
  }, [kt]);

  if (kt.loading && kt.nodes.length === 0) return <LoadingSkeleton />;
  if (kt.error && kt.nodes.length === 0) return <ErrorState message={kt.error} onRetry={kt.loadTreeData} />;
  if (kt.trees.length === 0) return <EmptyState onCreateTree={() => setShowCreateTree(true)} />;

  const filteredNodes = graphSearch.trim()
    ? kt.nodes.filter(n => matchedNodeIds.includes(n.id))
    : kt.nodes;

  return (
    <div className="flex flex-col h-full">
      {/* Top Bar */}
      <div className="flex items-center gap-3 h-[48px] px-4 border-b border bg-surface flex-shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-lg">{kt.selectedTree?.title ? "🌳" : "📚"}</span>
          <select value={kt.selectedTreeId ?? ""} onChange={e => kt.selectTree(e.target.value)}
            className="text-sm font-medium bg-transparent border-none focus:outline-none text max-w-[160px]">
            {kt.trees.map(t => <option key={t.id} value={t.id}>{t.title}</option>)}
          </select>
        </div>
        <div className="w-px h-5 bg-divider" />
        <button onClick={() => setAddNodeOpen(true)}
          className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-accent text-white hover:opacity-90">
          <Plus size={12} /> 节点
        </button>
        <button onClick={() => kt.setViewMode(kt.viewMode === "tree" ? "graph" : "tree")}
          className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-page-secondary border border text hover:border-accent">
          {kt.viewMode === "tree" ? "🌲 树视图" : "🕸️ 图视图"}
        </button>
        <button onClick={() => setLayerOpen(v => !v)}
          className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-all ${layerOpen ? "bg-accent/10 text-accent" : "text-muted hover:text"}`}>
          层级
        </button>
        <div className="relative flex-1 max-w-[200px]">
          <input value={graphSearch} onChange={e => setGraphSearch(e.target.value)}
            placeholder="搜索节点…"
            className="w-full pl-7 pr-2 py-1.5 text-[11px] rounded-md border border bg-page-secondary text placeholder:text-muted focus:outline-none focus:border-accent" />
          {matchedNodeIds.length > 0 && (
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[9px] text-accent font-medium bg-accent/10 px-1.5 py-0.5 rounded-full">
              {matchedNodeIds.length}
            </span>
          )}
        </div>
        <div className="ml-auto flex items-center gap-2">
          <button onClick={() => setShowDetailPanel(v => !v)}
            className={`text-[11px] px-2 py-1 rounded transition-all ${showDetailPanel ? "bg-accent/10 text-accent" : "text-muted hover:text"}`}>
            详情
          </button>
          <button onClick={() => setShowCreateTree(true)}
            className="text-[11px] px-2 py-1 rounded text-muted hover:text">
            新建树
          </button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Canvas */}
        <div ref={canvasRef} className="flex-1 relative overflow-hidden"
          style={{
            background: "linear-gradient(180deg, rgba(10,10,15,1) 0%, rgba(15,15,22,1) 100%)",
            backgroundImage: "radial-gradient(circle at 1px 1px, rgba(255,255,255,0.04) 0.5px, transparent 0)",
            backgroundSize: "24px 24px",
          }}>
          {layerOpen && (
            <LayerPanel
              graphData={graphData}
              searchQuery={graphSearch}
              onSearchChange={setGraphSearch}
              matchedNodeIds={matchedNodeIds}
              selectedNodeId={kt.selectedNodeId ?? undefined}
              onNodeSelect={(n) => handleNodeClick(kt.nodeMap.get(n.id)!)}
              onMaxLevelChange={() => {}}
              onClose={() => setLayerOpen(false)}
            />
          )}
          <KnowledgeTreeGraph
            data={{ nodes: filteredNodes, edges: kt.edges }}
            viewMode={kt.viewMode === "split" ? "tree" : kt.viewMode}
            selectedNodeId={kt.selectedNodeId}
            width={canvasSize.width}
            height={canvasSize.height}
            onNodeClick={handleNodeClick}
            onNodeDoubleClick={handleNodeDoubleClick}
            onNodeContextMenu={handleNodeContextMenu}
            onCanvasClick={() => kt.selectNode(null)}
          />
          <ZoomControls
            zoom={kt.zoom}
            onZoomIn={() => kt.setZoom(Math.min(3, kt.zoom + 0.15))}
            onZoomOut={() => kt.setZoom(Math.max(0.3, kt.zoom - 0.15))}
            onReset={() => kt.setZoom(1)}
          />
        </div>

        {/* Detail Panel */}
        {!isMobile && showDetailPanel && kt.selectedNode && (
          <>
            <ResizeHandle orientation="horizontal"
              onResizeStart={() => {}}
              onResize={(delta) => setDetailWidth(w => Math.max(240, Math.min(480, w - delta)))}
              onDoubleClick={() => setShowDetailPanel(false)} />
            <div style={{ width: detailWidth }} className="flex-shrink-0">
              <TreeNodeDetailPanel
                node={kt.selectedNode}
                onClose={() => kt.selectNode(null)}
                onDelete={() => kt.deleteNode(kt.selectedNode!.id)}
                onLinkCognitive={() => setLinkDialogOpen(true)}
              />
            </div>
          </>
        )}
        {isMobile && showDetailPanel && kt.selectedNode && (
          <div className="fixed inset-0 z-40 bg-black/30" onClick={() => kt.selectNode(null)}>
            <div className="absolute bottom-0 left-0 right-0 max-h-[70vh] bg-page rounded-t-xl overflow-y-auto"
              onClick={e => e.stopPropagation()}>
              <TreeNodeDetailPanel
                node={kt.selectedNode}
                onClose={() => kt.selectNode(null)}
                onDelete={() => kt.deleteNode(kt.selectedNode!.id)}
                onLinkCognitive={() => setLinkDialogOpen(true)}
              />
            </div>
          </div>
        )}
      </div>

      <StatusBar stats={stats} activeFilter="all" onStatClick={() => {}} />

      {/* Create Tree Dialog */}
      {showCreateTree && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
          <div className="bg-surface border border rounded-xl p-5 w-80 space-y-4 shadow-xl">
            <h3 className="text-sm font-semibold text">创建知识树</h3>
            <input value={newTreeName} onChange={e => setNewTreeName(e.target.value)}
              placeholder="知识树名称" autoFocus
              className="w-full px-3 py-2 text-sm bg-page border border text rounded-lg focus:outline-none focus:border-accent"
              onKeyDown={e => e.key === "Enter" && handleCreateTree()} />
            <EmojiPicker value={newTreeEmoji} onChange={setNewTreeEmoji} label="选择图标" />
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowCreateTree(false)} className="px-3 py-1.5 text-xs border border rounded-lg text-muted hover:bg-surface-hover">取消</button>
              <button onClick={handleCreateTree} disabled={!newTreeName.trim()}
                className="px-3 py-1.5 text-xs bg-accent text-white rounded-lg hover:opacity-90 disabled:opacity-50 flex items-center gap-1">
                {kt.loading ? <Loader2 size={12} className="animate-spin" /> : <Sparkles size={12} />} 创建
              </button>
            </div>
          </div>
        </div>
      )}

      <AddNodeDialog
        open={addNodeOpen}
        onClose={() => { setAddNodeOpen(false); setNewNodeParent(null); }}
        onAdd={handleAddNode}
        nodes={kt.nodes}
        parentId={newNodeParent}
        setParentId={setNewNodeParent}
      />

      <CognitiveLinkDialog
        open={linkDialogOpen}
        onClose={() => setLinkDialogOpen(false)}
        onLink={handleLinkCognitive}
      />

      {contextMenu && (
        <ContextMenu x={contextMenu.x} y={contextMenu.y}
          items={getDefaultContextMenuItems(contextMenu.node.label, contextMenu.node.id, {
            onEdit: () => handleContextMenuAction("edit"),
            onAddChild: () => handleContextMenuAction("add-child"),
            onAiExpand: () => { /* TODO */ setContextMenu(null); },
            onAiEdit: () => { /* TODO */ setContextMenu(null); },
            onLinkConversation: () => handleContextMenuAction("link-cognitive"),
            onExplain: () => { /* TODO */ setContextMenu(null); },
            onFocus: () => { /* TODO */ setContextMenu(null); },
            onDelete: () => handleContextMenuAction("delete"),
          })}
          onClose={() => setContextMenu(null)}
        />
      )}

      {kt.error && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50">
          <div className="flex items-center gap-2 px-4 py-2.5 rounded-lg shadow-lg text-xs font-medium bg-danger/90 text-white">
            <AlertCircle size={13} /> {kt.error}
          </div>
        </div>
      )}
    </div>
  );
}

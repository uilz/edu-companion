// ══════════════════════════════════════════════════════════════
//  useGraphCanvas — 知识图谱画布状态管理
//
//  封装所有图谱画布相关的状态、副作用、事件处理器。
//  包含数据加载、缩放、搜索、聚焦、筛选、键盘快捷键等。
// ══════════════════════════════════════════════════════════════

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { fetchGraphData, fetchPartitions } from "@/lib/api/graph-api";
import type { GraphData, GraphNode } from "@/lib/types/graph-types";
import { getNodeAncestors } from "@/lib/types/graph-types";
import { authedFetch } from "@/lib/api/api";
import { useGraphNodeActions } from "@/hooks/graph/useGraphNodeActions";
import type { GraphMode, DialogState } from "@/components/knowledge-tree/KnowledgeTreePage";
import type { LayoutPreference } from "./useTreeLayout";

// ── 内部类型 ──

export interface ContextMenuState {
  x: number;
  y: number;
  node: GraphNode;
}

export interface ToastState {
  message: string;
  type: "success" | "error" | "info";
}

export interface StatsInfo {
  total: number;
  mastered: number;
  learning: number;
  untouched: number;
  avgMastery: number;
}

export interface UseGraphCanvasReturn {
  // Data
  partitionId: string;
  setPartitionId: (id: string) => void;
  partitionList: { id: string; name: string; emoji?: string }[];
  graphData: GraphData | null;
  loading: boolean;
  error: string | null;
  selectedNode: GraphNode | null;
  loadGraph: () => void;

  // Canvas
  graphMode: GraphMode;
  zoomLevel: number;
  setZoomLevel: React.Dispatch<React.SetStateAction<number>>;
  graphFullscreen: boolean;
  graphSearch: string;
  matchedNodeIds: string[];
  maxDisplayLevel: string | undefined;

  // Filter / Focus
  focusRootId: string | undefined;
  focusBreadcrumb: GraphNode[];
  masteryFilter: Set<string>;
  setMasteryFilter: (f: Set<string>) => void;

  // UI modals
  contextMenu: ContextMenuState | null;
  toast: ToastState | null;
  dialogState: DialogState | null;
  inlineEditNode: GraphNode | null;
  addNodeOpen: boolean;

  // Add-node form state
  newNodeLabel: string;
  setNewNodeLabel: (v: string) => void;
  newNodeParent: string;
  setNewNodeParent: (v: string) => void;

  // Actions — canvas
  handleNodeSelect: (node: GraphNode) => void;
  handleNodeDoubleClick: (node: GraphNode) => void;
  handleNodeContextMenu: (node: GraphNode, e: { clientX: number; clientY: number; preventDefault?: () => void }) => void;
  handleSetFocus: (nodeId: string) => void;
  handleClearFocus: () => void;
  handleContextMenuAction: (action: string) => void;
  handleInlineEditSave: () => Promise<void>;
  handleAddNode: () => Promise<void>;
  handleStartTemporary: () => Promise<void>;

  // Actions — UI
  setDialogState: (s: DialogState | null) => void;
  setGraphSearch: (s: string) => void;
  setSelectedNode: (n: GraphNode | null) => void;
  setGraphFullscreen: (v: boolean) => void;
  setAddNodeOpen: (v: boolean) => void;
  setContextMenu: (m: ContextMenuState | null) => void;

  // Refs
  canvasRef: React.RefObject<HTMLDivElement | null>;
  graphContainerRef: React.RefObject<HTMLDivElement | null>;
  graphSize: { width: number; height: number };

  // Stats
  stats: StatsInfo;
}

// ── 常量 ──
const ZOOM_MIN = 0.3;
const ZOOM_MAX = 3;
const ZOOM_STEP = 0.15;

export function useGraphCanvas(
  layoutPref: LayoutPreference,
  setLayoutPref: React.Dispatch<React.SetStateAction<LayoutPreference>>,
): UseGraphCanvasReturn {
  const router = useRouter();
  const searchParams = useSearchParams();
  const urlPartition = searchParams.get("partition") || searchParams.get("node_id") || "";
  const urlNode = searchParams.get("node_id") || searchParams.get("node") || "";

  // ── Data ──
  const [partitionId, setPartitionId] = useState("");
  const [partitionList, setPartitionList] = useState<{ id: string; name: string; emoji?: string }[]>([]);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // ── Canvas / Interaction ──
  const [graphMode, setGraphMode] = useState<GraphMode>(layoutPref.graphMode);
  const [graphFullscreen, setGraphFullscreen] = useState(false);
  const [graphSearch, setGraphSearch] = useState("");
  const [matchedNodeIds, setMatchedNodeIds] = useState<string[]>([]);
  const [maxDisplayLevel, setMaxDisplayLevel] = useState<string | undefined>(layoutPref.maxDisplayLevel);

  // ── Modal UI ──
  const [addNodeOpen, setAddNodeOpen] = useState(false);
  const [newNodeLabel, setNewNodeLabel] = useState("");
  const [newNodeParent, setNewNodeParent] = useState("");
  const [addNodeLoading, setAddNodeLoading] = useState(false);
  const [layerOpen, setLayerOpen] = useState(layoutPref.layerOpen);
  const [inlineEditNode, setInlineEditNode] = useState<GraphNode | null>(null);
  const [inlineEditLabel, setInlineEditLabel] = useState("");
  const [inlineEditSaving, setInlineEditSaving] = useState(false);
  const [toast, setToast] = useState<ToastState | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [dialogState, setDialogState] = useState<DialogState | null>(null);

  // ── Zoom ──
  const [zoomLevel, setZoomLevel] = useState(1);

  // ── Filter / Focus ──
  const [masteryFilter, setMasteryFilter] = useState<Set<string>>(new Set(["mastered", "learning", "untouched"]));
  const [focusRootId, setFocusRootId] = useState<string | undefined>(undefined);

  // ── Refs ──
  const canvasRef = useRef<HTMLDivElement>(null);
  const graphContainerRef = useRef<HTMLDivElement>(null);
  const [graphSize, setGraphSize] = useState({ width: 600, height: 500 });

  // ════════════════════════════════════════
  //  Sync layoutPref → local state
  // ════════════════════════════════════════

  useEffect(() => { setGraphMode(layoutPref.graphMode); }, [layoutPref.graphMode]);
  useEffect(() => { setMaxDisplayLevel(layoutPref.maxDisplayLevel); }, [layoutPref.maxDisplayLevel]);
  useEffect(() => { setLayerOpen(layoutPref.layerOpen); }, [layoutPref.layerOpen]);

  // ════════════════════════════════════════
  //  Effects
  // ════════════════════════════════════════

  // Toast auto-dismiss
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 2500);
    return () => clearTimeout(timer);
  }, [toast]);

  // Canvas wheel prevention
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const preventScroll = (e: WheelEvent) => e.preventDefault();
    el.addEventListener("wheel", preventScroll, { passive: false });
    return () => el.removeEventListener("wheel", preventScroll);
  }, []);

  // Load partition list
  useEffect(() => {
    fetchPartitions().then(list => {
      const filtered = list.filter((p: { name: string }) => p.name !== "💬 临时");
      setPartitionList(filtered);
      if (!partitionId && filtered.length > 0) {
        const targetId = urlPartition && filtered.some((p: { id: string }) => p.id === urlPartition)
          ? urlPartition : filtered[0].id;
        setPartitionId(targetId);
      }
      if (filtered.length === 0) setLoading(false);
    });
  }, []); // eslint-disable-line

  // Load graph data
  const loadGraph = useCallback(() => {
    if (!partitionId) return;
    setLoading(true);
    fetchGraphData(partitionId)
      .then(data => { setGraphData(data); setError(null); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [partitionId]);

  useEffect(() => { loadGraph(); }, [loadGraph]);

  // URL anchor → selected node
  useEffect(() => {
    if (!urlNode || !graphData?.nodes) return;
    const node = graphData.nodes.find(n => n.id === urlNode);
    if (node) {
      setSelectedNode(node);
      setLayoutPref(p => ({ ...p, showDetailPanel: true }));
    }
  }, [urlNode, graphData, setLayoutPref]);

  // Search filter
  useEffect(() => {
    if (!graphSearch.trim() || !graphData?.nodes) {
      setMatchedNodeIds([]);
      return;
    }
    const q = graphSearch.toLowerCase();
    setMatchedNodeIds(graphData.nodes.filter(n => n.label.toLowerCase().includes(q)).map(n => n.id));
  }, [graphSearch, graphData]);

  // ResizeObserver
  useEffect(() => {
    const el = graphContainerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(entries => {
      for (const e of entries) {
        setGraphSize({ width: Math.max(300, e.contentRect.width), height: Math.max(300, e.contentRect.height) });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ════════════════════════════════════════
  //  Callbacks
  // ════════════════════════════════════════

  // Graph node actions (shared hook)
  const nodeActions = useGraphNodeActions(partitionId, {
    onNodeUpdated: loadGraph,
    onError: (msg) => setToast({ message: msg, type: "error" }),
  });

  // Focus
  const handleClearFocus = useCallback(() => setFocusRootId(undefined), []);
  const handleSetFocus = useCallback((nodeId: string) => setFocusRootId(nodeId), []);

  // Focus breadcrumb
  const focusBreadcrumb = useMemo(() => {
    if (!focusRootId || !graphData) return [];
    return getNodeAncestors(graphData, focusRootId);
  }, [focusRootId, graphData]);

  // Node selection
  const handleNodeSelect = useCallback((node: GraphNode) => {
    setSelectedNode(node);
    if (node && partitionId) {
      setDialogState({
        type: "tree_exploration",
        conversationId: "",
        parentId: partitionId,
        parentType: "dir",
        boundNode: node,
      });
    }
  }, [partitionId]);

  // Double-click → inline edit
  const handleNodeDoubleClick = useCallback((node: GraphNode) => {
    setInlineEditNode(node);
    setInlineEditLabel(node.label);
  }, []);

  // Context menu
  const handleNodeContextMenu = useCallback((
    node: GraphNode,
    e: { clientX: number; clientY: number; preventDefault?: () => void },
  ) => {
    e.preventDefault?.();
    setSelectedNode(node);
    setContextMenu({ x: e.clientX, y: e.clientY, node });
  }, []);

  const handleContextMenuAction = useCallback((action: string) => {
    const node = contextMenu?.node;
    if (!node) return;
    switch (action) {
      case "edit":
        setSelectedNode(node);
        break;
      case "add-child":
        setNewNodeParent(node.id);
        setAddNodeOpen(true);
        break;
      case "ai-expand":
        nodeActions.aiExpand(node.id);
        break;
      case "ai-edit":
        nodeActions.aiEdit(node.id);
        break;
      case "link":
        window.open(`/?link=conversation&node_id=${node.id}`, "_blank");
        break;
      case "explain":
        setSelectedNode(node);
        break;
      case "focus":
        handleSetFocus(node.id);
        break;
      case "delete":
        if (confirm(`确定删除节点「${node.label}」？此操作不可撤销。`)) {
          nodeActions.deleteNode(node.id, node.label).then((ok) => {
            if (ok) setSelectedNode(null);
          });
        }
        break;
    }
    setContextMenu(null);
  }, [contextMenu, nodeActions, handleSetFocus]);

  // Inline edit save
  const handleInlineEditSave = useCallback(async () => {
    if (!inlineEditNode || !inlineEditLabel.trim()) return;
    setInlineEditSaving(true);
    const ok = await nodeActions.editNode(inlineEditNode.id, { label: inlineEditLabel.trim() });
    if (ok) {
      setToast({ message: "节点已更新", type: "success" });
      setInlineEditNode(null);
    }
    setInlineEditSaving(false);
  }, [inlineEditNode, inlineEditLabel, nodeActions]);

  // Add node
  const handleAddNode = useCallback(async () => {
    if (!newNodeLabel.trim()) return;
    setAddNodeLoading(true);
    const ok = await nodeActions.createNode({
      label: newNodeLabel.trim(),
      parent_id: newNodeParent || undefined,
    });
    if (ok) {
      setAddNodeOpen(false);
      setNewNodeLabel("");
    }
    setAddNodeLoading(false);
  }, [newNodeLabel, newNodeParent, nodeActions]);

  // Temporary conversation
  const handleStartTemporary = useCallback(async () => {
    try {
      const res = await authedFetch(`/api/conversations/tree/conversation/temporary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await res.json();
      const conv = data.conversation;
      if (conv) {
        setDialogState({
          type: "temporary",
          conversationId: conv.id,
          parentId: conv.parent_id,
          parentType: "dir",
          boundNode: null,
        });
        const partitions = await fetchPartitions();
        setPartitionList(partitions);
        router.push(`/conversation?cid=${conv.id}&pid=${conv.parent_id}`);
      }
    } catch (e) {
      console.error("启动临时对话失败", e);
    }
  }, [router]);

  // ════════════════════════════════════════
  //  Keyboard shortcuts
  // ════════════════════════════════════════

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;

      if (e.key === "Escape") {
        if (inlineEditNode) { setInlineEditNode(null); return; }
        if (contextMenu) { setContextMenu(null); return; }
        if (graphFullscreen) { setGraphFullscreen(false); return; }
        if (addNodeOpen) { setAddNodeOpen(false); return; }
        if (selectedNode) { setSelectedNode(null); }
      }

      if (e.key === "F2" && selectedNode) {
        e.preventDefault();
        setInlineEditNode(selectedNode);
        setInlineEditLabel(selectedNode.label);
      }

      if ((e.key === "Delete" || e.key === "Backspace") && selectedNode && !inlineEditNode && !addNodeOpen) {
        e.preventDefault();
        if (confirm(`确定删除节点「${selectedNode.label}」？此操作不可撤销。`)) {
          nodeActions.deleteNode(selectedNode.id, selectedNode.label).then((ok) => {
            if (ok) setSelectedNode(null);
          });
        }
      }

      if ((e.ctrlKey || e.metaKey) && e.key === "n") {
        e.preventDefault();
        setNewNodeParent(e.shiftKey ? (selectedNode?.id || "") : "");
        setNewNodeLabel("");
        setAddNodeOpen(true);
      }

      if ((e.ctrlKey || e.metaKey) && e.key === "0") {
        e.preventDefault();
        setZoomLevel(1);
      }

      if ((e.ctrlKey || e.metaKey) && (e.key === "=" || e.key === "+")) {
        e.preventDefault();
        setZoomLevel(z => Math.min(ZOOM_MAX, z + ZOOM_STEP));
      }

      if ((e.ctrlKey || e.metaKey) && e.key === "-") {
        e.preventDefault();
        setZoomLevel(z => Math.max(ZOOM_MIN, z - ZOOM_STEP));
      }

      // Arrow key navigation
      if (selectedNode && graphData?.nodes && ["ArrowUp","ArrowDown","ArrowLeft","ArrowRight"].includes(e.key)) {
        e.preventDefault();
        const idx = graphData.nodes.findIndex(n => n.id === selectedNode.id);
        if (idx >= 0) {
          const delta = e.key === "ArrowUp" || e.key === "ArrowLeft" ? -1 : 1;
          const next = graphData.nodes[(idx + delta + graphData.nodes.length) % graphData.nodes.length];
          setSelectedNode(next);
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [graphFullscreen, addNodeOpen, selectedNode, graphData, inlineEditNode, contextMenu, partitionId, nodeActions]);

  // ════════════════════════════════════════
  //  Stats
  // ════════════════════════════════════════

  const stats = useMemo(() => {
    if (!graphData?.nodes?.length) return { total: 0, mastered: 0, learning: 0, untouched: 0, avgMastery: 0 };
    const nodes = graphData.nodes;
    return {
      total: nodes.length,
      mastered: nodes.filter(n => n.mastery >= 0.8).length,
      learning: nodes.filter(n => n.mastery >= 0.05 && n.mastery < 0.8).length,
      untouched: nodes.filter(n => n.mastery < 0.05).length,
      avgMastery: nodes.reduce((s, n) => s + (n.mastery || 0), 0) / nodes.length,
    };
  }, [graphData]);

  // ════════════════════════════════════════
  //  Return
  // ════════════════════════════════════════

  return {
    partitionId, setPartitionId, partitionList, graphData, loading, error, selectedNode, loadGraph,
    graphMode, zoomLevel, setZoomLevel, graphFullscreen, graphSearch, matchedNodeIds, maxDisplayLevel,
    focusRootId, focusBreadcrumb, masteryFilter, setMasteryFilter,
    contextMenu, toast, dialogState, inlineEditNode, addNodeOpen,
    newNodeLabel, setNewNodeLabel, newNodeParent, setNewNodeParent,
    handleNodeSelect, handleNodeDoubleClick, handleNodeContextMenu,
    handleSetFocus, handleClearFocus, handleContextMenuAction,
    handleInlineEditSave, handleAddNode, handleStartTemporary,
    setDialogState, setGraphSearch, setSelectedNode, setGraphFullscreen,
    setAddNodeOpen, setContextMenu,
    canvasRef, graphContainerRef, graphSize,
    stats,
  };
}

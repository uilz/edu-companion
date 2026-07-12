"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  knowledgeTreesApi,
  treeMaterialsApi,
  type KnowledgeTree,
  type TreeNode,
  type TreeEdge,
  type ViewportState,
  type TreeViewMode,
  type TreeLayout,
  type NodeMaterialsResponse,
  type SourceRef,
} from "@/lib/api/knowledge-trees-api";

export interface KnowledgeTreeState {
  // 树列表
  trees: KnowledgeTree[];
  selectedTreeId: string | null;
  selectedTree: KnowledgeTree | null;

  // 节点/边
  nodes: TreeNode[];
  edges: TreeEdge[];
  nodeMap: Map<string, TreeNode>;

  // 选中
  selectedNodeId: string | null;
  selectedNode: TreeNode | null;

  // 视图
  viewMode: TreeViewMode;
  layout: TreeLayout;
  zoom: number;
  viewport: ViewportState;

  // 跨壳材料聚合
  materials: NodeMaterialsResponse["materials"] | null;
  materialsLoading: boolean;
  materialsError: string | null;

  // UI
  loading: boolean;
  error: string | null;

  // Actions
  loadTrees: () => Promise<KnowledgeTree[]>;
  selectTree: (treeId: string) => void;
  createTree: (title: string, treeType?: KnowledgeTree["tree_type"]) => Promise<KnowledgeTree | null>;
  loadTreeData: () => Promise<void>;
  selectNode: (nodeId: string | null) => void;
  createNode: (label: string, parentId?: string | null, nodeType?: TreeNode["node_type"]) => Promise<TreeNode | null>;
  updateNode: (nodeId: string, data: Partial<TreeNode>) => Promise<boolean>;
  moveNode: (nodeId: string, newParentId?: string | null) => Promise<boolean>;
  deleteNode: (nodeId: string) => Promise<boolean>;
  createEdge: (sourceId: string, targetId: string, edgeType?: TreeEdge["edge_type"]) => Promise<TreeEdge | null>;
  deleteEdge: (edgeId: string) => Promise<boolean>;
  linkCognitive: (nodeId: string, cognitiveNodeId: string) => Promise<boolean>;
  unlinkCognitive: (nodeId: string, cognitiveNodeId: string) => Promise<boolean>;
  saveViewport: (patch: ViewportState) => Promise<void>;
  loadMaterials: (treeId: string, nodeId: string) => Promise<void>;
  addSourceRef: (treeId: string, nodeId: string, sourceRef: SourceRef) => Promise<boolean>;
  setViewMode: (mode: TreeViewMode) => void;
  setLayout: (layout: TreeLayout) => void;
  setZoom: (zoom: number) => void;
  setError: (error: string | null) => void;
}

const STORAGE_KEY = "knowledge-tree:last-tree-id";

export function useKnowledgeTree(): KnowledgeTreeState {
  const [trees, setTrees] = useState<KnowledgeTree[]>([]);
  const [selectedTreeId, setSelectedTreeId] = useState<string | null>(null);
  const [nodes, setNodes] = useState<TreeNode[]>([]);
  const [edges, setEdges] = useState<TreeEdge[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<TreeViewMode>("tree");
  const [layout, setLayout] = useState<TreeLayout>("layered");
  const [zoom, setZoom] = useState(1);
  const [viewport, setViewport] = useState<ViewportState>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 跨壳材料聚合
  const [materials, setMaterials] = useState<NodeMaterialsResponse["materials"] | null>(null);
  const [materialsLoading, setMaterialsLoading] = useState(false);
  const [materialsError, setMaterialsError] = useState<string | null>(null);

  const selectedTree = useMemo(
    () => trees.find((t) => t.id === selectedTreeId) || null,
    [trees, selectedTreeId]
  );

  const nodeMap = useMemo(() => {
    const map = new Map<string, TreeNode>();
    nodes.forEach((n) => map.set(n.id, n));
    return map;
  }, [nodes]);

  const selectedNode = useMemo(
    () => (selectedNodeId ? nodeMap.get(selectedNodeId) || null : null),
    [selectedNodeId, nodeMap]
  );

  const loadTrees = useCallback(async () => {
    try {
      const res = await knowledgeTreesApi.trees.list("active");
      setTrees(res.trees || []);
      return res.trees || [];
    } catch (e: any) {
      setError(e.message || "加载知识树列表失败");
      return [];
    }
  }, []);

  const restoreSelectedTree = useCallback((availableTrees: KnowledgeTree[]) => {
    if (availableTrees.length === 0) {
      setSelectedTreeId(null);
      return;
    }
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved && availableTrees.some((t) => t.id === saved)) {
        setSelectedTreeId(saved);
      } else {
        setSelectedTreeId(availableTrees[0].id);
      }
    } catch {
      setSelectedTreeId(availableTrees[0].id);
    }
  }, []);

  const selectTree = useCallback((treeId: string) => {
    setSelectedTreeId(treeId);
    setSelectedNodeId(null);
    try {
      localStorage.setItem(STORAGE_KEY, treeId);
    } catch { /* ignore */ }
  }, []);

  const loadTreeData = useCallback(async () => {
    if (!selectedTreeId) {
      setNodes([]);
      setEdges([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [treeRes, nodesRes, edgesRes, viewportRes] = await Promise.all([
        knowledgeTreesApi.trees.get(selectedTreeId),
        knowledgeTreesApi.nodes.list(selectedTreeId, true),
        knowledgeTreesApi.edges.list(selectedTreeId),
        knowledgeTreesApi.viewport.get(selectedTreeId),
      ]);

      const tree = treeRes.tree;
      setNodes(nodesRes.nodes || []);
      setEdges(edgesRes.edges || []);
      setViewport(viewportRes.viewport || {});
      setViewMode((tree.default_view_mode as TreeViewMode) || "tree");
      setLayout(tree.default_layout || "layered");
      setZoom(viewportRes.viewport?.zoom ?? 1);

      // 如果当前选中的节点已不存在，清除选中
      setSelectedNodeId((prev) => (prev && nodesRes.nodes?.some((n) => n.id === prev) ? prev : null));
    } catch (e: any) {
      setError(e.message || "加载知识树数据失败");
    } finally {
      setLoading(false);
    }
  }, [selectedTreeId]);

  const createTree = useCallback(async (title: string, treeType?: KnowledgeTree["tree_type"]) => {
    try {
      const res = await knowledgeTreesApi.trees.create({ title, tree_type: treeType || "project" });
      const tree = res.tree;
      setTrees((prev) => [...prev, tree]);
      setSelectedTreeId(tree.id);
      try {
        localStorage.setItem(STORAGE_KEY, tree.id);
      } catch { /* ignore */ }
      return tree;
    } catch (e: any) {
      setError(e.message || "创建知识树失败");
      return null;
    }
  }, []);

  const selectNode = useCallback((nodeId: string | null) => {
    setSelectedNodeId(nodeId);
    setMaterials(null);
    setMaterialsError(null);
  }, []);

  const createNode = useCallback(
    async (label: string, parentId?: string | null, nodeType?: TreeNode["node_type"]) => {
      if (!selectedTreeId) return null;
      try {
        const res = await knowledgeTreesApi.nodes.create(selectedTreeId, {
          label,
          parent_id: parentId ?? null,
          node_type: nodeType || "concept",
        });
        const node = res.node;
        setNodes((prev) => [...prev, node]);
        if (parentId) {
          setNodes((prev) =>
            prev.map((n) =>
              n.id === parentId
                ? { ...n, children_order: [...(n.children_order || []), node.id], children_ids: [...(n.children_ids || []), node.id] }
                : n
            )
          );
        }
        return node;
      } catch (e: any) {
        setError(e.message || "创建节点失败");
        return null;
      }
    },
    [selectedTreeId]
  );

  const updateNode = useCallback(
    async (nodeId: string, data: Partial<TreeNode>) => {
      if (!selectedTreeId) return false;
      try {
        const res = await knowledgeTreesApi.nodes.update(selectedTreeId, nodeId, {
          label: data.label,
          node_type: data.node_type,
          color: data.color,
          emoji: data.emoji,
          brief: data.brief,
          tags: data.tags,
          status: data.status,
          position: data.position,
          meta: data.metadata,
        });
        setNodes((prev) => prev.map((n) => (n.id === nodeId ? res.node : n)));
        return true;
      } catch (e: any) {
        setError(e.message || "更新节点失败");
        return false;
      }
    },
    [selectedTreeId]
  );

  const moveNode = useCallback(
    async (nodeId: string, newParentId?: string | null) => {
      if (!selectedTreeId) return false;
      try {
        const res = await knowledgeTreesApi.nodes.move(selectedTreeId, nodeId, {
          new_parent_id: newParentId ?? null,
        });
        setNodes((prev) => prev.map((n) => (n.id === nodeId ? res.node : n)));
        await loadTreeData();
        return true;
      } catch (e: any) {
        setError(e.message || "移动节点失败");
        return false;
      }
    },
    [selectedTreeId, loadTreeData]
  );

  const deleteNode = useCallback(
    async (nodeId: string) => {
      if (!selectedTreeId) return false;
      try {
        await knowledgeTreesApi.nodes.delete(selectedTreeId, nodeId);
        setNodes((prev) => prev.filter((n) => n.id !== nodeId));
        setEdges((prev) =>
          prev.filter((e) => e.source_node_id !== nodeId && e.target_node_id !== nodeId)
        );
        if (selectedNodeId === nodeId) setSelectedNodeId(null);
        return true;
      } catch (e: any) {
        setError(e.message || "删除节点失败");
        return false;
      }
    },
    [selectedTreeId, selectedNodeId]
  );

  const createEdge = useCallback(
    async (sourceId: string, targetId: string, edgeType?: TreeEdge["edge_type"]) => {
      if (!selectedTreeId) return null;
      try {
        const res = await knowledgeTreesApi.edges.create(selectedTreeId, {
          source_node_id: sourceId,
          target_node_id: targetId,
          edge_type: edgeType || "related",
        });
        const edge = res.edge;
        setEdges((prev) => [...prev, edge]);
        return edge;
      } catch (e: any) {
        setError(e.message || "创建边失败");
        return null;
      }
    },
    [selectedTreeId]
  );

  const deleteEdge = useCallback(
    async (edgeId: string) => {
      if (!selectedTreeId) return false;
      try {
        await knowledgeTreesApi.edges.delete(selectedTreeId, edgeId);
        setEdges((prev) => prev.filter((e) => e.id !== edgeId));
        return true;
      } catch (e: any) {
        setError(e.message || "删除边失败");
        return false;
      }
    },
    [selectedTreeId]
  );

  const linkCognitive = useCallback(
    async (nodeId: string, cognitiveNodeId: string) => {
      if (!selectedTreeId) return false;
      try {
        await knowledgeTreesApi.links.create(selectedTreeId, nodeId, {
          cognitive_node_id: cognitiveNodeId,
          link_role: "primary",
        });
        await loadTreeData();
        return true;
      } catch (e: any) {
        setError(e.message || "关联认知节点失败");
        return false;
      }
    },
    [selectedTreeId, loadTreeData]
  );

  const unlinkCognitive = useCallback(
    async (nodeId: string, cognitiveNodeId: string) => {
      if (!selectedTreeId) return false;
      try {
        await knowledgeTreesApi.links.delete(selectedTreeId, nodeId, cognitiveNodeId);
        await loadTreeData();
        return true;
      } catch (e: any) {
        setError(e.message || "解除关联失败");
        return false;
      }
    },
    [selectedTreeId, loadTreeData]
  );

  const loadMaterials = useCallback(async (treeId: string, nodeId: string) => {
    setMaterialsLoading(true);
    setMaterialsError(null);
    try {
      const res = await treeMaterialsApi.get(treeId, nodeId);
      setMaterials(res.materials);
    } catch (e: any) {
      setMaterialsError(e.message || "加载跨壳材料失败");
    } finally {
      setMaterialsLoading(false);
    }
  }, []);

  const addSourceRef = useCallback(
    async (treeId: string, nodeId: string, sourceRef: SourceRef) => {
      try {
        const res = await knowledgeTreesApi.nodes.addSourceRef(treeId, nodeId, sourceRef);
        setNodes((prev) => prev.map((n) => (n.id === nodeId ? res.node : n)));
        setMaterials((prev) =>
          prev
            ? { ...prev, source_refs: [...prev.source_refs, sourceRef] }
            : prev
        );
        return true;
      } catch (e: any) {
        setMaterialsError(e.message || "添加 source_ref 失败");
        return false;
      }
    },
    []
  );

  const saveViewport = useCallback(
    async (patch: ViewportState) => {
      if (!selectedTreeId) return;
      const next = { ...viewport, ...patch };
      setViewport(next);
      try {
        await knowledgeTreesApi.viewport.save(selectedTreeId, next);
      } catch (e: any) {
        setError(e.message || "保存视图状态失败");
      }
    },
    [selectedTreeId, viewport]
  );

  // Initial load
  useEffect(() => {
    let mounted = true;
    loadTrees().then((availableTrees) => {
      if (mounted) restoreSelectedTree(availableTrees);
    });
    return () => {
      mounted = false;
    };
  }, [loadTrees, restoreSelectedTree]);

  // Load tree data when selected tree changes
  useEffect(() => {
    if (selectedTreeId) {
      loadTreeData();
    }
  }, [selectedTreeId, loadTreeData]);

  return {
    trees,
    selectedTreeId,
    selectedTree,
    nodes,
    edges,
    nodeMap,
    selectedNodeId,
    selectedNode,
    viewMode,
    layout,
    zoom,
    viewport,
    loading,
    error,
    materials,
    materialsLoading,
    materialsError,
    loadTrees,
    selectTree,
    createTree,
    loadTreeData,
    selectNode,
    createNode,
    updateNode,
    moveNode,
    deleteNode,
    createEdge,
    deleteEdge,
    linkCognitive,
    unlinkCognitive,
    loadMaterials,
    addSourceRef,
    saveViewport,
    setViewMode,
    setLayout,
    setZoom,
    setError,
  };
}

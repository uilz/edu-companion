"use client";

import { useState, useCallback, useEffect, useRef, useMemo } from "react";
import type { GraphData, GraphNode, DialogueCardInfo } from "@/lib/types/graph-types";
import { fetchGraphData, fetchPartitions } from "@/lib/api/graph-api";
import { listNotes } from "@/lib/api/learning-api";
import type { Note } from "@/lib/api/learning-api";
import { api } from "@/lib/api/api";

// ── 导出类型 ──
export type LeftTab = "dialogue" | "practice" | "notes" | "resources" | "projects";
export type GraphMode = "mindmap" | "force" | "dag";
export type ReflectionTrigger = "practice_done" | "node_mastered" | "cognitive_conflict" | "weekly_review";

export interface ToolbarState {
  visible: boolean;
  position: { x: number; y: number };
  text: string;
  level: string;
}

// ── 工具函数 ──
async function fetchRelatedConversations(node: GraphNode): Promise<DialogueCardInfo[]> {
  try {
    const data: any = await api(`/api/conversations/tree/topic?parent_id=${encodeURIComponent(node.parent || "")}`);
    const convs: DialogueCardInfo[] = [];
    if (data.topics) {
      for (const t of Object.values(data.topics) as any[]) {
        if (t.name && t.id) {
          convs.push({
            id: t.id,
            question: t.name,
            summary: t.context_summary || "",
            knowledgeNodes: [node.label],
            timestamp: t.created_at || "",
          });
        }
      }
    }
    return convs.slice(0, 10);
  } catch {
    return [];
  }
}

export interface UseGraphDialogueReturn {
  graphData: GraphData | null;
  loading: boolean;
  error: string | null;
  selectedNode: GraphNode | null;
  graphMode: GraphMode;
  graphFullscreen: boolean;
  maxDisplayLevel: string | undefined;
  availableLevels: string[];
  relatedCards: DialogueCardInfo[];
  relatedNotes: Note[];
  cardLoading: boolean;
  childNodes: GraphNode[];
  leftTab: LeftTab;
  splitPercent: number;
  dragging: ReturnType<typeof useRef<boolean>>;
  containerRef: React.RefObject<HTMLDivElement>;

  reflectionOpen: boolean;
  reflectionTrigger: ReflectionTrigger;
  goalModalOpen: boolean;
  aggregateOpen: boolean;
  projectsOpen: boolean;
  noteSidebar: boolean;
  explainModal: boolean;
  selectedText: string;
  toolbar: ToolbarState;

  graphSearch: string;
  matchedNodeIds: string[];

  activePath: string[];
  practiceStats: { total: number; correct: number; accuracy: number; streak: number };

  // ── 分区相关 ──
  partitionId: string;
  partitionList: { id: string; name: string; emoji?: string }[];
  setPartitionId: (pid: string) => void;

  loadGraph: () => void;
  handleNodeSelect: (node: GraphNode) => void;
  handleStartPractice: (nodeId: string) => void;
  handleRequestExplain: (nodeId: string) => void;
  handleMarkMastered: (nodeId: string) => void;
  handleMarkQuestion: (nodeId: string, question: string) => void;
  handleReflectionSave: (reflection: any) => void;
  handleTextSelect: () => void;
  handleExplain: () => void;
  handleNote: () => void;
  handleExplainSave: (explanation: string) => void;
  setLeftTab: (t: LeftTab) => void;
  setGraphMode: (m: GraphMode) => void;
  setGraphSearch: (s: string) => void;
  setGraphFullscreen: (v: boolean) => void;
  setMaxDisplayLevel: (v: string | undefined) => void;
  setSelectedNode: (n: GraphNode | null) => void;
  setReflectionOpen: (v: boolean) => void;
  setReflectionTrigger: (v: ReflectionTrigger) => void;
  setGoalModalOpen: (v: boolean) => void;
  setAggregateOpen: (v: boolean) => void;
  setProjectsOpen: (v: boolean) => void;
  setNoteSidebar: (v: boolean) => void;
  setExplainModal: (v: boolean) => void;
  setToolbar: (v: ToolbarState) => void;
  setSplitPercent: (v: number) => void;
}

const LEVEL_ORDER: Record<string, number> = {
  partition: 0, domain: 1, topic: 2, conversation: 3, concept: 4, atom: 5,
};
const ALL_LEVELS = ["partition", "domain", "topic", "conversation", "concept", "atom"];

export function useGraphDialogue(initialPartitionId?: string): UseGraphDialogueReturn {
  // ── 分区 ──
  const [partitionId, setPartitionId] = useState(initialPartitionId || "");
  const [partitionList, setPartitionList] = useState<{ id: string; name: string; emoji?: string }[]>([]);

  // ── 图谱数据 ──
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [graphMode, setGraphMode] = useState<GraphMode>("mindmap");
  const [graphFullscreen, setGraphFullscreen] = useState(false);

  // ── 关联数据 ──
  const [relatedCards, setRelatedCards] = useState<DialogueCardInfo[]>([]);
  const [relatedNotes, setRelatedNotes] = useState<Note[]>([]);
  const [cardLoading, setCardLoading] = useState(false);
  const [childNodes, setChildNodes] = useState<GraphNode[]>([]);

  // ── 左侧面板 ──
  const [leftTab, setLeftTab] = useState<LeftTab>("dialogue");

  // ── 分栏 ──
  const [splitPercent, setSplitPercent] = useState(50);
  const dragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // ── 模态框 ──
  const [reflectionOpen, setReflectionOpen] = useState(false);
  const [reflectionTrigger, setReflectionTrigger] = useState<ReflectionTrigger>("node_mastered");
  const [goalModalOpen, setGoalModalOpen] = useState(false);
  const [aggregateOpen, setAggregateOpen] = useState(false);
  const [projectsOpen, setProjectsOpen] = useState(false);
  const [noteSidebar, setNoteSidebar] = useState(false);
  const [explainModal, setExplainModal] = useState(false);
  const [selectedText, setSelectedText] = useState("");
  const [toolbar, setToolbar] = useState<ToolbarState>({
    visible: false, position: { x: 0, y: 0 }, text: "", level: "sentence",
  });

  // ── 图谱搜索 ──
  const [graphSearch, setGraphSearch] = useState("");
  const [matchedNodeIds, setMatchedNodeIds] = useState<string[]>([]);

  // ── 层级筛选 ──
  const [maxDisplayLevel, setMaxDisplayLevel] = useState<string | undefined>(undefined);
  const availableLevels = useMemo(() => {
    if (!graphData?.nodes?.length) return ["partition","domain","topic","concept","atom"];
    const levels = new Set(graphData.nodes.map(n => n.level).filter(Boolean));
    return ALL_LEVELS.filter(l => levels.has(l));
  }, [graphData]);

  // ── 待对接数据 ──
  const practiceStats = { total: 24, correct: 16, accuracy: 67, streak: 3 };

  // ── 加载分区列表 ──
  useEffect(() => {
    fetchPartitions().then(list => {
      setPartitionList(list);
      if (!partitionId && list.length > 0) {
        setPartitionId(list[0].id);
      }
      if (list.length === 0) {
        // 没有分区时结束 loading，让 UI 显示空状态
        setLoading(false);
      }
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── 获取图谱数据 ──
  const loadGraph = useCallback(() => {
    if (!partitionId) return;
    setLoading(true);
    fetchGraphData(partitionId)
      .then((data) => {
        setGraphData(data);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [partitionId]);

  useEffect(() => { loadGraph(); }, [loadGraph]);

  // ── 切换分区时清空选中节点 ──
  useEffect(() => {
    setSelectedNode(null);
    setGraphSearch("");
  }, [partitionId]);

  // ── 选中节点时加载关联数据 ──
  useEffect(() => {
    if (!selectedNode || !graphData) {
      setRelatedCards([]);
      setRelatedNotes([]);
      setChildNodes([]);
      return;
    }

    setCardLoading(true);
    const children = graphData.nodes.filter((n) => n.parent === selectedNode.id);
    setChildNodes(children);
    listNotes({ node_id: selectedNode.id, limit: 20 })
      .then(setRelatedNotes)
      .catch(() => setRelatedNotes([]));
    fetchRelatedConversations(selectedNode).then(setRelatedCards);
    setCardLoading(false);

    if (selectedNode.mastery >= 0.8 && selectedNode.trend === "ascending") {
      setReflectionTrigger("node_mastered");
      setReflectionOpen(true);
    }
  }, [selectedNode, graphData]);

  // ── 搜索匹配更新 ──
  useEffect(() => {
    if (!graphSearch.trim() || !graphData) {
      setMatchedNodeIds([]);
      return;
    }
    const q = graphSearch.toLowerCase();
    setMatchedNodeIds(
      graphData.nodes.filter((n) => n.label.toLowerCase().includes(q)).map((n) => n.id),
    );
  }, [graphSearch, graphData]);

  // ── 选中节点处理 ──
  const handleNodeSelect = useCallback((node: GraphNode) => {
    setSelectedNode((prev) => (prev?.id === node.id ? null : node));
  }, []);

  // ── 操作回调 ──
  const handleStartPractice = useCallback((nodeId: string) => {
    console.log("Start practice for node:", nodeId);
    setLeftTab("practice");
  }, []);

  const handleRequestExplain = useCallback((nodeId: string) => {
    console.log("Request explain for node:", nodeId);
    setLeftTab("dialogue");
  }, []);

  const handleMarkMastered = useCallback((nodeId: string) => {
    console.log("Mark mastered:", nodeId);
    setReflectionTrigger("node_mastered");
    setReflectionOpen(true);
  }, []);

  const handleMarkQuestion = useCallback((nodeId: string, question: string) => {
    console.log("Mark question:", nodeId, question);
    setReflectionTrigger("cognitive_conflict");
    setReflectionOpen(true);
  }, []);

  const handleReflectionSave = useCallback((reflection: any) => {
    console.log("Reflection saved:", reflection);
  }, []);

  // ── 文本选择 ──
  const handleTextSelect = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.toString().trim()) {
      setToolbar((p) => ({ ...p, visible: false }));
      return;
    }
    const text = sel.toString().trim();
    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    const level = text.length < 50 ? "sentence" : text.length < 200 ? "paragraph" : "all";
    setToolbar({ visible: true, position: { x: rect.left + rect.width / 2, y: rect.top - 8 }, text, level });
    setSelectedText(text);
  }, []);

  const handleExplain = useCallback(() => setExplainModal(true), []);
  const handleNote = useCallback(() => setNoteSidebar(true), []);
  const handleExplainSave = useCallback((explanation: string) => {
    console.log("Save explanation:", explanation);
  }, []);

  // ── Active path for graph ──
  const activePath = useMemo(() => {
    if (selectedNode && graphData) {
      const path: string[] = [];
      let current: GraphNode | undefined = selectedNode;
      while (current) {
        path.unshift(current.id);
        current = current.parent ? graphData.nodes.find((n) => n.id === current!.parent) : undefined;
      }
      return path;
    }
    // Fallback: try from URL params
    if (!graphData) return [];
    const params = typeof window !== "undefined" ? new URLSearchParams(window.location.search) : null;
    if (!params) return [];
    const ids = [params.get("p"), params.get("d"), params.get("t"), params.get("c")].filter(Boolean);
    const validPath: string[] = [];
    for (const id of ids) {
      const node = graphData.nodes.find((n) => n.id === id);
      if (node) validPath.push(node.id);
    }
    return validPath;
  }, [selectedNode, graphData]);

  // ── 拖拽分隔线 ──
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      setSplitPercent(Math.max(15, Math.min(70, ((e.clientX - rect.left) / rect.width) * 100)));
    };
    const onUp = () => {
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, []);

  return {
    graphData, loading, error, selectedNode, graphMode, graphFullscreen,
    maxDisplayLevel, availableLevels,
    relatedCards, relatedNotes, cardLoading, childNodes, leftTab,
    splitPercent, dragging, containerRef,
    reflectionOpen, reflectionTrigger, goalModalOpen, aggregateOpen,
    projectsOpen, noteSidebar, explainModal, selectedText, toolbar,
    graphSearch, matchedNodeIds, activePath, practiceStats,

    // ── 分区 ──
    partitionId, partitionList, setPartitionId,

    loadGraph, handleNodeSelect, handleStartPractice, handleRequestExplain,
    handleMarkMastered, handleMarkQuestion, handleReflectionSave,
    handleTextSelect, handleExplain, handleNote, handleExplainSave,
    setLeftTab, setGraphMode, setGraphSearch, setGraphFullscreen,
    setMaxDisplayLevel,
    setSelectedNode, setReflectionOpen, setReflectionTrigger,
    setGoalModalOpen, setAggregateOpen, setProjectsOpen,
    setNoteSidebar, setExplainModal, setToolbar, setSplitPercent,
  };
}

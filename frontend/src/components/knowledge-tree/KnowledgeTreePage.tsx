"use client";

import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Plus, X, RefreshCw,
  Loader2, Sparkles, ZoomIn, ZoomOut, Maximize,
  Edit3, Check, AlertCircle,
  MessageCircle, Bot, Send,
} from "lucide-react";

import { fetchGraphData, fetchPartitions } from "@/lib/api/graph-api";
import type { GraphData, GraphNode } from "@/lib/types/graph-types";
import { getMasteryColor, filterByLevel, subtreeFilter, getNodeAncestors, findNodeById } from "@/lib/types/graph-types";
import FocusGraph from "@/components/graph/graphs/FocusGraph";
import ForceGraph from "@/components/graph/graphs/ForceGraph";
import DAGGraph from "@/components/graph/graphs/DAGGraph";
import NodeDetailPanel from "@/components/graph/panels/NodeDetailPanel";
import FloatingNodeCard from "@/components/graph/panels/FloatingNodeCard";
import LayerPanel from "./LayerPanel";
import DialogContainer from "./DialogContainer";
import ContextMenu, { getDefaultContextMenuItems } from "./ContextMenu";
import EmojiPicker from "@/components/ui/EmojiPicker";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

// ── 类型 ──
export type GraphMode = "mindmap" | "force" | "dag";

// ── 对话状态 ──
export interface DialogState {
  type: "normal" | "tree_exploration" | "temporary";
  conversationId: string;
  parentId: string;
  parentType: "partition" | "domain" | "topic";
  boundNode?: GraphNode | null;
}

interface LayoutPreference {
  showDialogPanel: boolean;
  showDetailPanel: boolean;
  dialogWidth: number;
  detailWidth: number;
  graphMode: GraphMode;
  layerOpen: boolean;
  maxDisplayLevel: string | undefined;
}

// ── 布局偏好持久化 ──
const STORAGE_KEY = "knowledge-tree-layout";

function loadLayout(): LayoutPreference {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return JSON.parse(saved);
  } catch {}
  return { showDialogPanel: true, showDetailPanel: false, dialogWidth: 320, detailWidth: 320, graphMode: "mindmap", layerOpen: true, maxDisplayLevel: undefined };
}

function saveLayout(pref: LayoutPreference) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(pref)); } catch {}
}

// ── Loading 骨架屏 ──
function LoadingSkeleton() {
  return (
    <div className="flex flex-col h-full min-h-[600px]">
      <div className="h-[48px] bg-[var(--color-surface)] border-b border-[var(--color-border)] flex-shrink-0" />
      <div className="flex flex-1 overflow-hidden">
        <div className="w-[320px] bg-[var(--color-surface)] border-r border-[var(--color-border)] animate-pulse" />
        <div className="flex-1 p-8 space-y-4 animate-pulse">
          <div className="h-6 bg-[var(--color-surface)] rounded w-1/3" />
          <div className="grid grid-cols-4 gap-4">
            {[1,2,3,4,5,6,7,8].map(i => (
              <div key={i} className="h-24 bg-[var(--color-surface)] rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── 空状态（有分区但无知识树） ──
function EmptyState({ partitionId, onLoad }: { partitionId: string; onLoad: () => void }) {
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const handleGenerate = async () => {
    setGenerating(true);
    setGenError(null);
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/graph/${partitionId}/generate`, { method: "POST" });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || `服务返回 ${res.status}`);
      }
      onLoad();
    } catch (e: any) {
      setGenError(e.message || "生成失败，请重试");
    }
    setGenerating(false);
  };
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[500px] gap-6 px-4">
      <div className="w-24 h-24 rounded-2xl bg-gradient-to-br from-[var(--color-accent)]/10 to-[var(--color-accent)]/5 flex items-center justify-center shadow-sm border border-[var(--color-border)]">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-[var(--color-accent)]">
          <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
        </svg>
      </div>
      <div className="text-center max-w-sm space-y-2">
        <h3 className="text-lg font-semibold text-[var(--color-text)]">该分区暂无知识树</h3>
        <p className="text-sm text-[var(--color-text-muted)] leading-relaxed">
          学习分区创建后，知识树需要手动或通过 AI 生成。点击下方按钮让 AI 自动构建初始结构，之后你可以在画布中自由编辑。
        </p>
      </div>

      {genError && (
        <div className="px-4 py-2.5 rounded-lg bg-red-500/5 border border-red-500/20 text-xs text-[var(--color-danger)] max-w-sm">
          {genError}
        </div>
      )}

      <div className="flex items-center gap-3">
        <button onClick={handleGenerate} disabled={generating}
          className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium bg-[var(--color-accent)] text-white rounded-xl hover:opacity-90 disabled:opacity-50 transition-all shadow-sm">
          {generating ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          AI 预生成知识树
        </button>
        <button onClick={onLoad}
          className="flex items-center gap-2 px-4 py-2.5 text-sm font-medium border border-[var(--color-border)] rounded-xl text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] transition-colors">
          <RefreshCw size={14} /> 刷新
        </button>
      </div>

      <div className="flex items-center gap-6 pt-2">
        <div className="flex items-center gap-2 text-[11px] text-[var(--color-text-muted)]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
          AI 根据分区名字和已有内容自动生成
        </div>
        <div className="flex items-center gap-2 text-[11px] text-[var(--color-text-muted)]">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg>
          生成后可手动增删改节点
        </div>
      </div>
    </div>
  );
}

// ── 无分区引导 — 引导创建分区直接探索知识树 ──
function NoPartitionState({ onPartitionCreated, onStartTemporary }: {
  onPartitionCreated: (id: string) => void;
  onStartTemporary?: () => void;
}) {
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newEmoji, setNewEmoji] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    setCreateError(null);
    try {
      const res = await fetch(`${API_BASE}/api/conversations/tree/partition`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim(), emoji: newEmoji }),
      });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(text || `创建失败（${res.status}）`);
      }
      const data = await res.json();
      const id = data.partition?.id;
      if (!id) throw new Error("创建分区成功但未返回分区 ID");
      onPartitionCreated(id);
    } catch (e: any) {
      setCreateError(e.message || "创建分区失败，请重试");
    }
    setCreating(false);
  };

  const quickPresets = [
    { name: "高等数学", emoji: "📐" },
    { name: "Python 编程", emoji: "🐍" },
    { name: "线性代数", emoji: "🔢" },
    { name: "数据结构", emoji: "🗃️" },
    { name: "大学物理", emoji: "⚛️" },
    { name: "英语单词", emoji: "📖" },
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[500px] gap-8 px-6">
      {/* ── 顶部插画 ── */}
      <div className="relative">
        <div className="w-32 h-32 rounded-3xl bg-gradient-to-br from-[var(--color-accent)]/15 to-[var(--color-accent)]/5 flex items-center justify-center shadow-sm border border-[var(--color-border)]">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" className="text-[var(--color-accent)]">
            <circle cx="12" cy="5" r="2.5" strokeWidth="1.5"/>
            <circle cx="5" cy="12" r="2.5" strokeWidth="1.5"/>
            <circle cx="19" cy="12" r="2.5" strokeWidth="1.5"/>
            <circle cx="8" cy="19" r="2.5" strokeWidth="1.5"/>
            <circle cx="16" cy="19" r="2.5" strokeWidth="1.5"/>
            <line x1="10" y1="7" x2="7" y2="10" strokeWidth="1.2"/>
            <line x1="14" y1="7" x2="17" y2="10" strokeWidth="1.2"/>
            <line x1="7" y1="14" x2="9" y2="17" strokeWidth="1.2"/>
            <line x1="17" y1="14" x2="15" y2="17" strokeWidth="1.2"/>
          </svg>
        </div>
        {/* 浮动装饰点 */}
        <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-[var(--color-success)]/30 animate-pulse" />
        <div className="absolute -bottom-1 -left-1 w-3 h-3 rounded-full bg-[var(--color-accent)]/20" />
      </div>

      {/* ── 介绍文字 ── */}
      <div className="text-center max-w-md space-y-2">
        <h3 className="text-xl font-semibold text-[var(--color-text)] tracking-tight">
          开始构建你的知识树
        </h3>
        <p className="text-sm text-[var(--color-text-muted)] leading-relaxed">
          知识树是学习的大脑地图 — 将学科知识结构化，让 AI 帮你梳理脉络、
          发现薄弱点、推荐学习路径。创建你的第一个学习分区即可开始。
        </p>
      </div>

      {/* ── 创建表单（展开状态） ── */}
      {showCreate ? (
        <div className="w-full max-w-sm bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-2xl shadow-md p-5 space-y-4">
          <div className="flex items-center gap-2">
            <div className="w-1 h-5 rounded-full bg-[var(--color-accent)]" />
            <span className="text-sm font-semibold text-[var(--color-text)]">新建学习分区</span>
          </div>
          <div className="space-y-3">
            {/* 名称 */}
            <div>
              <label className="text-[10px] font-medium text-[var(--color-text-muted)] uppercase tracking-wide">名称</label>
              <input value={newName} onChange={e => setNewName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleCreate()}
                className="mt-1 w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg bg-[var(--color-page-secondary)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)]"
                placeholder="例如：高等数学" autoFocus />
            </div>
            {/* Emoji 选择器 */}
            <EmojiPicker value={newEmoji} onChange={setNewEmoji} label="选择图标" />
          </div>
          {createError && (
            <div className="px-3 py-2 rounded-lg bg-red-500/5 border border-red-500/20 text-[10px] text-[var(--color-danger)]">
              {createError}
            </div>
          )}
          <div className="flex items-center gap-2 pt-1">
            <button onClick={handleCreate} disabled={creating || !newName.trim()}
              className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium bg-[var(--color-accent)] text-white rounded-xl hover:opacity-90 disabled:opacity-40 transition-all shadow-sm">
              {creating ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
              创建并生成知识树
            </button>
            <button onClick={() => setShowCreate(false)}
              className="px-4 py-2.5 text-sm font-medium border border-[var(--color-border)] rounded-xl text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors">
              取消
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-3">
          <button onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 px-6 py-3 text-sm font-medium bg-[var(--color-accent)] text-white rounded-xl hover:opacity-90 transition-all shadow-sm">
            <Plus size={16} /> 创建学习分区
          </button>
          {onStartTemporary && (
            <button onClick={onStartTemporary}
              className="inline-flex items-center gap-2 px-6 py-3 text-sm font-medium border border-[var(--color-border)] text-[var(--color-text-secondary)] rounded-xl hover:bg-[var(--color-surface)] transition-all">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
              临时对话
            </button>
          )}
        </div>
      )}

      {/* ── 快捷预设模板 ── */}
      <div className="w-full max-w-lg">
        <div className="flex items-center gap-2 mb-3">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[var(--color-text-muted)]">
            <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
          </svg>
          <span className="text-[11px] font-medium text-[var(--color-text-muted)]">快速开始模板</span>
        </div>
        <div className="grid grid-cols-3 gap-2">
          {quickPresets.map(p => (
            <button key={p.name} onClick={() => { setNewEmoji(p.emoji); setNewName(p.name); setShowCreate(true); }}
              className="flex items-center gap-2 px-3 py-2.5 rounded-xl border border-[var(--color-border)] bg-[var(--color-surface-elevated)] hover:border-[var(--color-accent)] hover:bg-[var(--color-accent)]/5 transition-all text-left">
              <span className="text-base">{p.emoji}</span>
              <span className="text-xs font-medium text-[var(--color-text)]">{p.name}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ── 底部功能预览 ── */}
      <div className="grid grid-cols-3 gap-4 max-w-md">
        {[
          { icon: "🧠", title: "AI 生成", desc: "输入学科名，AI 自动构建" },
          { icon: "✏️", title: "自由编辑", desc: "拖拽、增删、调整结构" },
          { icon: "💬", title: "对话探索", desc: "全局问答 + 节点讲解" },
        ].map(item => (
          <div key={item.title} className="text-center space-y-1">
            <div className="text-xl">{item.icon}</div>
            <div className="text-[10px] font-medium text-[var(--color-text)]">{item.title}</div>
            <div className="text-[9px] text-[var(--color-text-muted)]">{item.desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── 错误状态 ──
function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[400px] gap-4 px-4">
      <div className="w-20 h-20 rounded-2xl bg-red-500/5 border border-red-500/10 flex items-center justify-center">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-[var(--color-danger)]">
          <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>
        </svg>
      </div>
      <div className="text-center max-w-sm space-y-1">
        <h3 className="text-sm font-semibold text-[var(--color-text)]">加载失败</h3>
        <p className="text-xs text-[var(--color-text-muted)]">{message}</p>
      </div>
      <button onClick={onRetry}
        className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium border border-[var(--color-border)] rounded-lg text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] transition-colors">
        <RefreshCw size={12} />重试
      </button>
    </div>
  );
}

// ══════════════════════════════════════════
// 主组件
// ══════════════════════════════════════════

export default function KnowledgeTreePage() {
  const router = useRouter();
  // ── URL 参数（智能锚定） ──
  const searchParams = useSearchParams();
  const urlPartition = searchParams.get("partition");
  const urlNode = searchParams.get("node");

  // ── 布局偏好 ──
  const [layoutPref, setLayoutPref] = useState<LayoutPreference>(loadLayout);

  // ── 数据 ──
  const [partitionId, setPartitionId] = useState("");
  const [partitionList, setPartitionList] = useState<{ id: string; name: string; emoji?: string }[]>([]);
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  // ── 交互状态 ──
  const [graphMode, setGraphMode] = useState<GraphMode>(layoutPref.graphMode);
  const [graphFullscreen, setGraphFullscreen] = useState(false);
  const [graphSearch, setGraphSearch] = useState("");
  const [matchedNodeIds, setMatchedNodeIds] = useState<string[]>([]);
  const [maxDisplayLevel, setMaxDisplayLevel] = useState<string | undefined>(layoutPref.maxDisplayLevel);
  const [addNodeOpen, setAddNodeOpen] = useState(false);
  const [newNodeLabel, setNewNodeLabel] = useState("");
  const [newNodeParent, setNewNodeParent] = useState("");
  const [addNodeLoading, setAddNodeLoading] = useState(false);
  const [layerOpen, setLayerOpen] = useState(layoutPref.layerOpen);

  // ── 缩放控制 ──
  const [zoomLevel, setZoomLevel] = useState(1);
  const ZOOM_MIN = 0.3;
  const ZOOM_MAX = 3;
  const ZOOM_STEP = 0.15;

  // ── 掌握度筛选 ──
  const [masteryFilter, setMasteryFilter] = useState<Set<string>>(new Set(["mastered", "learning", "untouched"]));

  // ── 聚焦根节点：以某节点为根展示子树 ──
  const [focusRootId, setFocusRootId] = useState<string | undefined>(undefined);

  // 聚焦面包屑：当前聚焦节点的祖先链
  const focusBreadcrumb = useMemo(() => {
    if (!focusRootId || !graphData) return [];
    return getNodeAncestors(graphData, focusRootId);
  }, [focusRootId, graphData]);

  // 从聚焦模式回到全局视图
  const handleClearFocus = useCallback(() => {
    setFocusRootId(undefined);
  }, []);

  // 设置聚焦：双击节点或从菜单触发
  const handleSetFocus = useCallback((nodeId: string) => {
    setFocusRootId(nodeId);
  }, []);

  // ── 内联编辑 ──
  const [inlineEditNode, setInlineEditNode] = useState<GraphNode | null>(null);
  const [inlineEditLabel, setInlineEditLabel] = useState("");
  const [inlineEditSaving, setInlineEditSaving] = useState(false);

  // ── 操作反馈 ──
  const [toast, setToast] = useState<{ message: string; type: "success" | "error" | "info" } | null>(null);

  // Toast 自动消失
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 2500);
    return () => clearTimeout(timer);
  }, [toast]);

  // ── 右键菜单 ──
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; node: GraphNode } | null>(null);

  // ── 对话状态 ──
  const [dialogState, setDialogState] = useState<DialogState | null>(null);

  // ── refs ──
  const graphContainerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const [graphSize, setGraphSize] = useState({ width: 600, height: 500 });

  // ── 阻止图区域滚轮事件传播到页面 ──
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const preventScroll = (e: WheelEvent) => e.preventDefault();
    el.addEventListener("wheel", preventScroll, { passive: false });
    return () => el.removeEventListener("wheel", preventScroll);
  }, []);

  // ── 保存布局偏好 ──
  useEffect(() => { saveLayout(layoutPref); }, [layoutPref]);
  useEffect(() => { setGraphMode(layoutPref.graphMode); }, [layoutPref.graphMode]);

  // ── 加载分区列表（过滤临时分区） ──
  useEffect(() => {
    fetchPartitions().then(list => {
      const filtered = list.filter(p => p.name !== "💬 临时");
      setPartitionList(filtered);
      if (!partitionId && filtered.length > 0) {
        // 优先使用 URL 参数指定的分区
        const targetId = urlPartition && filtered.some(p => p.id === urlPartition) ? urlPartition : filtered[0].id;
        setPartitionId(targetId);
      }
      if (filtered.length === 0) setLoading(false);
    });
  }, []); // eslint-disable-line

  // ── 加载图谱 ──
  const loadGraph = useCallback(() => {
    if (!partitionId) return;
    setLoading(true);
    fetchGraphData(partitionId)
      .then(data => { setGraphData(data); setError(null); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [partitionId]);

  useEffect(() => { loadGraph(); }, [loadGraph]);

  // ── URL 参数智能锚定节点 ──
  useEffect(() => {
    if (!urlNode || !graphData?.nodes) return;
    const node = graphData.nodes.find(n => n.id === urlNode);
    if (node) {
      setSelectedNode(node);
      setLayoutPref(p => ({ ...p, showDetailPanel: true }));
    }
  }, [urlNode, graphData]);

  // ── 搜索过滤 ──
  useEffect(() => {
    if (!graphSearch.trim() || !graphData?.nodes) {
      setMatchedNodeIds([]);
      return;
    }
    const q = graphSearch.toLowerCase();
    const ids = graphData.nodes.filter(n => n.label.toLowerCase().includes(q)).map(n => n.id);
    setMatchedNodeIds(ids);
  }, [graphSearch, graphData]);

  // ── ResizeObserver ──
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

  // ── 键盘快捷键 ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // 忽略输入框中的按键
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;

      if (e.key === "Escape") {
        if (inlineEditNode) { setInlineEditNode(null); return; }
        if (contextMenu) { setContextMenu(null); return; }
        if (graphFullscreen) { setGraphFullscreen(false); return; }
        if (addNodeOpen) { setAddNodeOpen(false); return; }
        if (selectedNode) { setSelectedNode(null); }
      }

      // F2 — 编辑选中节点
      if (e.key === "F2" && selectedNode) {
        e.preventDefault();
        setInlineEditNode(selectedNode);
        setInlineEditLabel(selectedNode.label);
      }

      // Delete — 删除选中节点
      if ((e.key === "Delete" || e.key === "Backspace") && selectedNode && !inlineEditNode && !addNodeOpen) {
        e.preventDefault();
        if (confirm(`确定删除节点「${selectedNode.label}」？此操作不可撤销。`)) {
          fetch(`${API_BASE}/api/knowledge/graph/${partitionId}/node/${selectedNode.id}`, { method: "DELETE" })
            .then(() => { setSelectedNode(null); setToast({ message: `已删除「${selectedNode.label}」`, type: "success" }); loadGraph(); })
            .catch(() => setToast({ message: "删除失败", type: "error" }));
        }
      }

      // Ctrl/Cmd+N — 添加节点
      if ((e.ctrlKey || e.metaKey) && e.key === "n") {
        e.preventDefault();
        if (e.shiftKey) {
          // Ctrl+Shift+N — 添加当前节点的子节点
          setNewNodeParent(selectedNode?.id || "");
        } else {
          setNewNodeParent("");
        }
        setNewNodeLabel("");
        setAddNodeOpen(true);
      }

      // Ctrl/Cmd+0 — 重置缩放
      if ((e.ctrlKey || e.metaKey) && e.key === "0") {
        e.preventDefault();
        setZoomLevel(1);
      }

      // Ctrl/Cmd+= — 放大
      if ((e.ctrlKey || e.metaKey) && (e.key === "=" || e.key === "+")) {
        e.preventDefault();
        setZoomLevel(z => Math.min(ZOOM_MAX, z + ZOOM_STEP));
      }

      // Ctrl/Cmd+- — 缩小
      if ((e.ctrlKey || e.metaKey) && e.key === "-") {
        e.preventDefault();
        setZoomLevel(z => Math.max(ZOOM_MIN, z - ZOOM_STEP));
      }

      // 键盘导航
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
  }, [graphFullscreen, addNodeOpen, selectedNode, graphData, inlineEditNode, contextMenu, partitionId, loadGraph, zoomLevel]);

  // ── 统计 ──
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

  // ── 处理节点选择 ──
  const handleNodeSelect = useCallback((node: GraphNode) => {
    setSelectedNode(node);
    if (node && partitionId) {
      setDialogState({
        type: "tree_exploration",
        conversationId: "",
        parentId: partitionId,
        parentType: "partition",
        boundNode: node,
      });
    }
  }, [partitionId]);

  // ── 双击节点 → 内联编辑 ──
  const handleNodeDoubleClick = useCallback((node: GraphNode) => {
    setInlineEditNode(node);
    setInlineEditLabel(node.label);
  }, []);

  // ── 保存内联编辑 ──
  const handleInlineEditSave = useCallback(async () => {
    if (!inlineEditNode || !inlineEditLabel.trim()) return;
    setInlineEditSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/knowledge/graph/${partitionId}/node/${inlineEditNode.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: inlineEditLabel.trim() }),
      });
      if (!res.ok) throw new Error("保存失败");
      setToast({ message: "节点已更新", type: "success" });
      setInlineEditNode(null);
      loadGraph();
    } catch {
      setToast({ message: "保存失败", type: "error" });
    } finally {
      setInlineEditSaving(false);
    }
  }, [inlineEditNode, inlineEditLabel, partitionId, loadGraph]);

  // ── 处理右键菜单 ──
  const handleNodeContextMenu = useCallback((node: GraphNode, e: { clientX: number; clientY: number; preventDefault?: () => void }) => {
    e.preventDefault?.();
    setSelectedNode(node);
    setContextMenu({ x: e.clientX, y: e.clientY, node });
  }, []);

  // ── 启动临时对话 ──
  const handleStartTemporary = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/conversations/tree/conversation/temporary`, {
        method: "POST", headers: { "Content-Type": "application/json" },
      });
      const data = await res.json();
      const conv = data.conversation;
      if (conv) {
        setDialogState({
          type: "temporary",
          conversationId: conv.id,
          parentId: conv.parent_id,
          parentType: "partition",
          boundNode: null,
        });
        const partitions = await fetchPartitions();
        setPartitionList(partitions);
        // 跳转到对话页
        router.push(`/conversation?cid=${conv.id}&pid=${conv.parent_id}`);
      }
    } catch (e) {
      console.error("启动临时对话失败", e);
    }
  }, []);

  const handleContextMenuAction = useCallback((action: string) => {
    const node = contextMenu?.node;
    if (!node) return;
    switch (action) {
      case "edit":
        // 触发选中 + 内联编辑（通过选中节点让右侧面板/浮层出现）
        setSelectedNode(node);
        break;
      case "add-child":
        setNewNodeParent(node.id);
        setAddNodeOpen(true);
        break;
      case "ai-expand":
        fetch(`${API_BASE}/api/knowledge/graph/${partitionId}/ai-expand`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ node_id: node.id }),
        }).then(loadGraph);
        break;
      case "ai-edit":
        fetch(`${API_BASE}/api/knowledge/graph/${partitionId}/ai-edit`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ node_id: node.id }),
        }).then(loadGraph);
        break;
      case "link":
        window.open(`/?link=conversation&node_id=${node.id}`, "_blank");
        break;
      case "explain":
        // 触发讲解（交由现有机制处理）
        setSelectedNode(node);
        break;
      case "focus":
        handleSetFocus(node.id);
        break;
      case "delete":
        if (confirm(`确定删除节点「${node.label}」？此操作不可撤销。`)) {
          fetch(`${API_BASE}/api/knowledge/graph/${partitionId}/node/${node.id}`, { method: "DELETE" })
            .then(() => { setSelectedNode(null); loadGraph(); });
        }
        break;
    }
    setContextMenu(null);
  }, [contextMenu, partitionId, loadGraph]);

  // ── 添加节点 ──
  const handleAddNode = async () => {
    if (!newNodeLabel.trim()) return;
    setAddNodeLoading(true);
    try {
      await fetch(`${API_BASE}/api/knowledge/graph/${partitionId}/node`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label: newNodeLabel.trim(), parent_node_id: newNodeParent || null }),
      });
      setAddNodeOpen(false);
      setNewNodeLabel("");
      loadGraph();
    } catch {}
    setAddNodeLoading(false);
  };

  // ── 渲染 ──
  if (loading) return <LoadingSkeleton />;

  if (error) {
    return <ErrorState message={error} onRetry={loadGraph} />;
  }

  if (!graphData || graphData.nodes.length === 0) {
    if (!partitionId) return (
      <NoPartitionState
        onPartitionCreated={(id) => { setPartitionId(id); }}
        onStartTemporary={handleStartTemporary}
      />
    );
    return <EmptyState partitionId={partitionId} onLoad={loadGraph} />;
  }

  return (
    <div className="flex flex-col h-full">
      {/* ═══════ 顶部导航栏 ═══════ */}
      <TopBar
        partitionId={partitionId}
        partitionList={partitionList}
        onPartitionChange={setPartitionId}
        graphMode={graphMode}
        onGraphModeChange={setGraphMode}
        showDialogPanel={layoutPref.showDialogPanel}
        onToggleDialogPanel={() => setLayoutPref(p => ({ ...p, showDialogPanel: !p.showDialogPanel }))}
        showDetailPanel={layoutPref.showDetailPanel}
        onToggleDetailPanel={() => setLayoutPref(p => ({ ...p, showDetailPanel: !p.showDetailPanel }))}
        graphSearch={graphSearch}
        onGraphSearchChange={setGraphSearch}
        matchCount={matchedNodeIds.length}
        onAddNode={() => setAddNodeOpen(true)}
        onToggleFullscreen={() => setGraphFullscreen(!graphFullscreen)}
        graphFullscreen={graphFullscreen}
        layerOpen={layerOpen}
        onToggleLayer={() => { setLayerOpen(!layerOpen); setLayoutPref(p => ({ ...p, layerOpen: !layerOpen })); }}
      />

      {/* ═══════ 聚焦面包屑 ═══════ */}
      {focusRootId && (
        <div className="flex-shrink-0 flex items-center gap-1.5 px-4 py-1.5 border-b border-[var(--color-border)] bg-[var(--color-page-secondary)] text-[11px] text-[var(--color-text-muted)]">
          <button onClick={handleClearFocus}
            className="text-[var(--color-accent)] hover:underline font-medium">
            全局视图
          </button>
          <span className="text-[var(--color-text-muted)] mx-0.5">›</span>
          {focusBreadcrumb.map((ancestor) => (
            <span key={ancestor.id} className="flex items-center gap-1">
              <button onClick={() => handleSetFocus(ancestor.id)}
                className="hover:text-[var(--color-accent)] hover:underline transition-colors">
                {ancestor.label}
              </button>
              <span className="text-[var(--color-text-muted)] mx-0.5">›</span>
            </span>
          ))}
          <span className="text-[var(--color-text)] font-medium">
            {findNodeById(graphData!, focusRootId)?.label || "当前聚焦"}
          </span>
        </div>
      )}

      {/* ═══════ 主区域 ═══════ */}
      <div className="flex flex-1 overflow-hidden">
        {/* 对话面板 — 侧栏式 */}
        {layoutPref.showDialogPanel && (
          <>
            <AutoCollapsePanel
              side="left"
              width={layoutPref.dialogWidth}
              onCollapse={() => setLayoutPref(p => ({ ...p, showDialogPanel: false }))}
            >
              <DialogContainer
                dialogState={dialogState}
                onDialogStateChange={setDialogState}
                partitionId={partitionId}
                selectedNode={selectedNode}
                onNodeUpdated={loadGraph}
                width={layoutPref.dialogWidth}
                onWidthChange={(w: number) => setLayoutPref(p => ({ ...p, dialogWidth: w }))}
              />
            </AutoCollapsePanel>
            {/* 左侧拖拽分割线 */}
            <ResizeHandle side="left" onResize={(dx: number) => {
              setLayoutPref(p => ({ ...p, dialogWidth: Math.max(200, Math.min(600, p.dialogWidth + dx)) }));
            }} />
          </>
        )}

        {/* 图谱画布 */}
        <div ref={canvasRef} className="flex-1 min-w-0 relative overflow-hidden bg-[var(--color-bg)]"
             style={{ backgroundImage: "radial-gradient(circle at 1px 1px, var(--color-border) 1px, transparent 0)", backgroundSize: "24px 24px" }}>
          {/* 图层面板 */}
          {layerOpen && graphData && (
            <LayerPanel
              graphData={graphData}
              searchQuery={graphSearch}
              onSearchChange={setGraphSearch}
              matchedNodeIds={matchedNodeIds}
              selectedNodeId={selectedNode?.id}
              onNodeSelect={handleNodeSelect}
              maxDisplayLevel={maxDisplayLevel}
              onMaxLevelChange={(l) => { setMaxDisplayLevel(l); setLayoutPref(p => ({ ...p, maxDisplayLevel: l })); }}
              onClose={() => { setLayerOpen(false); setLayoutPref(p => ({ ...p, layerOpen: false })); }}
              masteryFilter={masteryFilter}
              onMasteryFilterChange={setMasteryFilter}
            />
          )}

          {/* 图谱视图 */}
          <div ref={graphContainerRef} className="absolute inset-0">
            <div className="w-full h-full transition-transform duration-200 ease-out origin-top-left"
              style={{ transform: `scale(${zoomLevel})`, transformOrigin: "top left" }}>
              {graphMode === "mindmap" && (
                <FocusGraph
                  data={filterByLevel(subtreeFilter(graphData, focusRootId), maxDisplayLevel)}
                  selectedNodeId={selectedNode?.id}
                  onNodeSelect={handleNodeSelect}
                  onFocusNode={handleSetFocus}
                  onNodeContextMenu={handleNodeContextMenu}
                  activePath={[]}
                  width={graphSize.width}
                  height={graphSize.height}
                  searchQuery={graphSearch}
                  matchedNodeIds={matchedNodeIds}
                />
              )}
              {graphMode === "force" && (
                <ForceGraph
                  data={filterByLevel(subtreeFilter(graphData, focusRootId), maxDisplayLevel)}
                  selectedNodeId={selectedNode?.id}
                  onNodeSelect={handleNodeSelect}
                  onNodeContextMenu={handleNodeContextMenu}
                  width={graphSize.width}
                  height={graphSize.height}
                />
              )}
              {graphMode === "dag" && (
                <DAGGraph
                  data={filterByLevel(subtreeFilter(graphData, focusRootId), maxDisplayLevel)}
                  selectedNodeId={selectedNode?.id}
                  onNodeSelect={handleNodeSelect}
                  onNodeContextMenu={handleNodeContextMenu}
                  activePath={[]}
                  width={graphSize.width}
                  height={graphSize.height}
                  searchQuery={graphSearch}
                  matchedNodeIds={matchedNodeIds}
                />
              )}
            </div>

            {/* ── 缩放控制 ── */}
            <div className="absolute bottom-4 right-4 flex items-center gap-0.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-md p-1 z-20">
              <button
                onClick={() => setZoomLevel(z => Math.max(ZOOM_MIN, z - ZOOM_STEP))}
                disabled={zoomLevel <= ZOOM_MIN}
                className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] disabled:opacity-30 transition-colors"
                title="缩小 (Ctrl+-)"
              >
                <ZoomOut size={14} />
              </button>
              <button
                onClick={() => setZoomLevel(1)}
                className="px-2 py-1 text-[10px] font-medium text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] rounded transition-colors"
                title="重置缩放 (Ctrl+0)"
              >
                {Math.round(zoomLevel * 100)}%
              </button>
              <button
                onClick={() => setZoomLevel(z => Math.min(ZOOM_MAX, z + ZOOM_STEP))}
                disabled={zoomLevel >= ZOOM_MAX}
                className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] disabled:opacity-30 transition-colors"
                title="放大 (Ctrl++)"
              >
                <ZoomIn size={14} />
              </button>
              <div className="w-px h-4 bg-[var(--color-border)] mx-0.5" />
              <button
                onClick={() => setGraphFullscreen(!graphFullscreen)}
                className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
                title={graphFullscreen ? "退出全屏" : "全屏"}
              >
                <Maximize size={14} />
              </button>
            </div>
          </div>
        </div>

        {/* 右侧详情面板 */}
        {layoutPref.showDetailPanel && selectedNode && (
          <>
            {/* 右侧拖拽分割线 */}
            <ResizeHandle side="right" onResize={(dx: number) => {
              setLayoutPref(p => ({ ...p, detailWidth: Math.max(200, Math.min(600, p.detailWidth - dx)) }));
            }} />
            <AutoCollapsePanel
              side="right"
              width={layoutPref.detailWidth}
              onCollapse={() => { setSelectedNode(null); setLayoutPref(p => ({ ...p, showDetailPanel: false })); }}
            >
              <div className="flex-shrink-0 border-l border-[var(--color-border)] bg-[var(--color-surface)] overflow-y-auto h-full"
                style={{ width: `${layoutPref.detailWidth}px` }}>
                <NodeDetailPanel
                  node={selectedNode}
                  partitionId={partitionId}
                  onClose={() => setSelectedNode(null)}
                  onNodeUpdated={loadGraph}
                  onStartPractice={() => {}}
                  onRequestExplain={() => {}}
                  parentNode={selectedNode?.parent ? graphData?.nodes.find(n => n.id === selectedNode.parent) ?? null : null}
                  onNavigateToParent={(parent) => { setSelectedNode(parent); }}
                />
              </div>
            </AutoCollapsePanel>
          </>
        )}
      </div>

      {/* ═══════ 浮动节点卡片（详情面板关闭时显示） ═══════ */}
      {!layoutPref.showDetailPanel && selectedNode && (
        <FloatingNodeCard
          node={selectedNode}
          partitionId={partitionId}
          onClose={() => setSelectedNode(null)}
          onNodeUpdated={loadGraph}
          onStartPractice={() => {}}
          onRequestExplain={() => {}}
          parentNode={selectedNode?.parent ? graphData?.nodes.find(n => n.id === selectedNode.parent) ?? null : null}
          onNavigateToParent={(parent) => { setSelectedNode(parent); }}
        />
      )}

      {/* ═══════ 状态栏 ═══════ */}
      <StatusBar
        stats={stats}
        onStatClick={(filter: string) => {
          if (filter === "all") {
            setMasteryFilter(new Set(["mastered", "learning", "untouched"]));
          } else {
            setMasteryFilter(new Set([filter]));
          }
          setToast({ message: `已筛选掌握度: ${filter === "all" ? "全部" : filter === "mastered" ? "已掌握" : filter === "learning" ? "学习中" : "未接触"}`, type: "info" });
        }}
        activeFilter={masteryFilter.size === 3 ? "all" : masteryFilter.size === 1 ? Array.from(masteryFilter)[0] : "custom"}
      />

      {/* ═══════ 浮动气泡 ═══════ */}
      {!layoutPref.showDialogPanel && (
        <FloatDialogWrapper
        dialogState={dialogState}
        onDialogStateChange={setDialogState}
        partitionId={partitionId}
        selectedNode={selectedNode}
        onNodeUpdated={loadGraph}
      />
      )}

      {/* ═══════ 添加节点弹窗 ═══════ */}
      {addNodeOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-5 w-80 space-y-4 shadow-xl animate-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-[var(--color-accent)]/10 flex items-center justify-center">
                  <Plus size={14} className="text-[var(--color-accent)]" />
                </div>
                <h3 className="text-sm font-semibold text-[var(--color-text)]">
                  {newNodeParent ? "添加子节点" : "添加根节点"}
                </h3>
              </div>
              <button onClick={() => setAddNodeOpen(false)} className="p-1 rounded-md hover:bg-[var(--color-surface-hover)] transition-colors">
                <X size={14} className="text-[var(--color-text-muted)]" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[10px] font-medium text-[var(--color-text-muted)] mb-1 uppercase tracking-wider">节点名称</label>
                <input value={newNodeLabel} onChange={e => setNewNodeLabel(e.target.value)}
                  placeholder="输入知识节点名称"
                  autoFocus
                  className="w-full px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] rounded-lg focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]/30 placeholder:text-[var(--color-text-muted)]/50"
                  onKeyDown={e => { if (e.key === "Enter" && newNodeLabel.trim()) handleAddNode(); if (e.key === "Escape") setAddNodeOpen(false); }} />
              </div>

              <div>
                <label className="block text-[10px] font-medium text-[var(--color-text-muted)] mb-1 uppercase tracking-wider">父节点</label>
                <select value={newNodeParent} onChange={e => setNewNodeParent(e.target.value)}
                  className="w-full px-3 py-2 text-xs bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] rounded-lg focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]/30">
                  <option value="">无父节点（根节点）</option>
                  {graphData?.nodes?.map(n => (
                    <option key={n.id} value={n.id}>{n.label}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="flex gap-2 justify-end pt-1">
              <button onClick={() => setAddNodeOpen(false)}
                className="px-3 py-1.5 text-xs border border-[var(--color-border)] rounded-lg text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors">
                取消
              </button>
              <button onClick={handleAddNode} disabled={addNodeLoading || !newNodeLabel.trim()}
                className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 transition-colors flex items-center gap-1.5">
                {addNodeLoading ? <><Loader2 size={10} className="animate-spin" /> 添加中</> : <><Check size={12} /> 确认添加</>}
              </button>
            </div>

            <div className="text-[9px] text-[var(--color-text-muted)] border-t border-[var(--color-border)] pt-2 text-center">
              快捷键: <kbd className="px-1 py-0.5 bg-[var(--color-bg)] rounded text-[9px] border border-[var(--color-border)]">Ctrl+N</kbd> 添加根节点 · <kbd className="px-1 py-0.5 bg-[var(--color-bg)] rounded text-[9px] border border-[var(--color-border)]">Ctrl+Shift+N</kbd> 添加子节点
            </div>
          </div>
        </div>
      )}

      {/* ═══════ 内联编辑弹窗 ═══════ */}
      {inlineEditNode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-5 w-80 space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="w-7 h-7 rounded-lg bg-[var(--color-accent)]/10 flex items-center justify-center">
                  <Edit3 size={14} className="text-[var(--color-accent)]" />
                </div>
                <h3 className="text-sm font-semibold text-[var(--color-text)]">编辑节点</h3>
              </div>
              <button onClick={() => setInlineEditNode(null)} className="p-1 rounded-md hover:bg-[var(--color-surface-hover)] transition-colors">
                <X size={14} className="text-[var(--color-text-muted)]" />
              </button>
            </div>
            <div>
              <label className="block text-[10px] font-medium text-[var(--color-text-muted)] mb-1 uppercase tracking-wider">节点名称</label>
              <input value={inlineEditLabel} onChange={e => setInlineEditLabel(e.target.value)}
                autoFocus
                className="w-full px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] rounded-lg focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]/30"
                onKeyDown={e => { if (e.key === "Enter" && inlineEditLabel.trim()) handleInlineEditSave(); if (e.key === "Escape") setInlineEditNode(null); }} />
            </div>
            <div className="flex gap-2 justify-end pt-1">
              <button onClick={() => setInlineEditNode(null)}
                className="px-3 py-1.5 text-xs border border-[var(--color-border)] rounded-lg text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors">
                取消
              </button>
              <button onClick={handleInlineEditSave} disabled={inlineEditSaving || !inlineEditLabel.trim()}
                className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 transition-colors flex items-center gap-1.5">
                {inlineEditSaving ? <><Loader2 size={10} className="animate-spin" /> 保存中</> : <><Check size={12} /> 确认</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══════ Toast 通知 ═══════ */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-in slide-in-from-bottom-2 duration-200">
          <div className={`flex items-center gap-2 px-4 py-2.5 rounded-lg shadow-lg text-xs font-medium
            ${toast.type === "success" ? "bg-emerald-500/90 text-white" : ""}
            ${toast.type === "error" ? "bg-red-500/90 text-white" : ""}
            ${toast.type === "info" ? "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text)]" : ""}`}>
            {toast.type === "success" && <Check size={13} />}
            {toast.type === "error" && <AlertCircle size={13} />}
            {toast.type === "info" && <Sparkles size={13} />}
            {toast.message}
          </div>
        </div>
      )}

      {/* ═══════ 右键菜单 ═══════ */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          items={getDefaultContextMenuItems(contextMenu.node.label, contextMenu.node.id, {
            onEdit: () => handleContextMenuAction("edit"),
            onAddChild: () => handleContextMenuAction("add-child"),
            onAiExpand: () => handleContextMenuAction("ai-expand"),
            onAiEdit: () => handleContextMenuAction("ai-edit"),
            onLinkConversation: () => handleContextMenuAction("link"),
            onExplain: () => handleContextMenuAction("explain"),
            onFocus: () => handleContextMenuAction("focus"),
            onDelete: () => handleContextMenuAction("delete"),
          })}
          onClose={() => setContextMenu(null)}
        />
      )}
    </div>
  );
}

// ══════════════════════════════════════════
// 顶部导航栏子组件 — 匹配 demo 品质
// ══════════════════════════════════════════

function TopBar({
  partitionId, partitionList, onPartitionChange,
  graphMode, onGraphModeChange,
  showDialogPanel, onToggleDialogPanel,
  showDetailPanel, onToggleDetailPanel,
  graphSearch, onGraphSearchChange, matchCount,
  onAddNode, onToggleFullscreen, graphFullscreen,
  layerOpen, onToggleLayer,
}: {
  partitionId: string; partitionList: { id: string; name: string; emoji?: string }[];
  onPartitionChange: (id: string) => void;
  graphMode: GraphMode; onGraphModeChange: (m: GraphMode) => void;
  showDialogPanel: boolean; onToggleDialogPanel: () => void;
  showDetailPanel: boolean; onToggleDetailPanel: () => void;
  graphSearch: string; onGraphSearchChange: (s: string) => void; matchCount: number;
  onAddNode: () => void; onToggleFullscreen: () => void; graphFullscreen: boolean;
  layerOpen: boolean; onToggleLayer: () => void;
}) {
  return (
    <div className="flex items-center gap-3 h-[48px] px-4 bg-[var(--color-surface)] border-b border-[var(--color-border)] flex-shrink-0 z-20">
      {/* 分区选择器 */}
      <div className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--color-page-secondary)] border border-[var(--color-border)] rounded-lg text-xs font-medium cursor-pointer hover:border-[var(--color-accent)] transition-colors">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[var(--color-text-muted)]">
          <circle cx="12" cy="12" r="3"/>
        </svg>
        <select value={partitionId} onChange={e => onPartitionChange(e.target.value)}
          className="appearance-none bg-transparent text-[var(--color-text)] text-xs font-medium focus:outline-none cursor-pointer">
          {partitionList.map(p => (
            <option key={p.id} value={p.id}>{p.emoji || "📚"} {p.name}</option>
          ))}
        </select>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[var(--color-text-muted)]">
          <path d="M6 9l6 6 6-6"/>
        </svg>
      </div>

      <div className="w-px h-5 bg-[var(--color-border)] flex-shrink-0" />

      {/* 视图模式切换 — 单按钮循环 */}
      <button onClick={() => {
          const modes: GraphMode[] = ["mindmap", "force", "dag"];
          const next = modes[(modes.indexOf(graphMode) + 1) % modes.length];
          onGraphModeChange(next);
        }}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium bg-[var(--color-page-secondary)] border border-[var(--color-border)] text-[var(--color-text)] hover:border-[var(--color-accent)] transition-all">
        {graphMode === "mindmap" && (
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
          </svg>
        )}
        {graphMode === "force" && (
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3"/><circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><circle cx="6" cy="18" r="2"/>
          </svg>
        )}
        {graphMode === "dag" && (
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="4" y="4" width="16" height="4" rx="1"/><rect x="2" y="12" width="20" height="4" rx="1"/><rect x="6" y="20" width="12" height="3" rx="1"/>
          </svg>
        )}
        {graphMode === "mindmap" ? "思维导图" : graphMode === "force" ? "力导向" : "依赖图"}
      </button>

      <div className="w-px h-5 bg-[var(--color-border)] flex-shrink-0" />

      {/* 面板开关 */}
      <button onClick={onToggleDialogPanel}
        className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-all ${
          showDialogPanel ? "bg-[var(--color-accent)] text-white shadow-sm" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
        }`}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/></svg>
        对话面板
      </button>
      <button onClick={onToggleDetailPanel}
        className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-all ${
          showDetailPanel ? "bg-[var(--color-accent)] text-white shadow-sm" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
        }`}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="20" height="18" rx="1"/><path d="M2 8h20"/></svg>
        详情面板
      </button>

      {/* 图层面板开关 */}
      <button onClick={onToggleLayer}
        className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-all ${
          layerOpen ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
        }`}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        层级
      </button>

      {/* 搜索框 */}
      <div className="relative flex-1 max-w-[200px]">
        <input value={graphSearch} onChange={e => onGraphSearchChange(e.target.value)}
          placeholder="搜索节点…"
          className="w-full pl-7 pr-2 py-1.5 text-[11px] rounded-md border border-[var(--color-border)] bg-[var(--color-page-secondary)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] focus:bg-[var(--color-surface)] transition-colors" />
        <svg className="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
        </svg>
        {graphSearch && (
          <>
            <button onClick={() => onGraphSearchChange("")} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"><X size={12} /></button>
            {matchCount > 0 && (
              <span className="absolute right-7 top-1/2 -translate-y-1/2 text-[10px] text-[var(--color-accent)] font-medium">{matchCount} 匹配</span>
            )}
          </>
        )}
      </div>

      <div className="flex-1" />

      {/* 添加节点 */}
      <button onClick={onAddNode}
        className="flex items-center gap-1 px-2.5 py-1.5 text-[11px] rounded-md bg-[var(--color-accent)]/10 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20 transition-all font-medium">
        <Plus size={12} />添加节点
      </button>

      {/* 全屏 */}
      <button onClick={onToggleFullscreen}
        className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-all"
        title={graphFullscreen ? "退出全屏" : "全屏"}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M8 3H5a2 2 0 00-2 2v3m18 0V5a2 2 0 00-2-2h-3m0 18h3a2 2 0 002-2v-3M3 16v3a2 2 0 002 2h3"/>
        </svg>
      </button>
    </div>
  );
}

// ══════════════════════════════════════════
// 状态栏 — 匹配 demo 品质
// ══════════════════════════════════════════

function StatusBar({
  stats,
  onStatClick,
  activeFilter,
}: {
  stats: { total: number; mastered: number; learning: number; untouched: number; avgMastery: number };
  onStatClick?: (filter: string) => void;
  activeFilter?: string;
}) {
  if (stats.total === 0) return null;

  const filterBtn = (filter: string, label: string, color: string, count: number, icon: string) => {
    const isActive = activeFilter === filter;
    return (
      <button
        onClick={() => onStatClick?.(filter)}
        className={`flex items-center gap-1 px-2 py-1 rounded-md transition-colors cursor-pointer
          ${isActive ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)] font-medium" : "hover:bg-[var(--color-surface-hover)]"}`}
        title={`筛选: ${label}`}
      >
        <span className="text-[10px]">{icon}</span>
        <span className="text-[10px]">{label}</span>
        <strong className="text-[11px]">{count}</strong>
      </button>
    );
  };

  return (
    <div className="flex items-center gap-1 h-[32px] px-4 bg-[var(--color-page-secondary)] border-t border-[var(--color-border)] flex-shrink-0 text-[10px] text-[var(--color-text-muted)]">
      <span className="mr-2 text-[10px]">📊 <strong className="text-[var(--color-text)]">{stats.total}</strong> 节点</span>
      <div className="w-px h-4 bg-[var(--color-border)]" />
      {filterBtn("mastered", "已掌握", "var(--color-success)", stats.mastered, "✅")}
      {filterBtn("learning", "学习中", "var(--color-warning)", stats.learning, "📖")}
      {filterBtn("untouched", "未接触", "var(--color-text-muted)", stats.untouched, "📐")}
      <div className="w-px h-4 bg-[var(--color-border)]" />
      <span className="text-[10px]">平均掌握度 <strong style={{ color: getMasteryColor(stats.avgMastery) }}>{Math.round(stats.avgMastery * 100)}%</strong></span>
      <span className="ml-auto text-[10px]">
        快捷键: <kbd className="inline-block px-1 py-0.5 bg-[var(--color-surface-hover)] border border-[var(--color-border)] rounded text-[9px] font-mono">↑↓←→</kbd> 切换
        · <kbd className="inline-block px-1 py-0.5 bg-[var(--color-surface-hover)] border border-[var(--color-border)] rounded text-[9px] font-mono">F2</kbd> 编辑
        · <kbd className="inline-block px-1 py-0.5 bg-[var(--color-surface-hover)] border border-[var(--color-border)] rounded text-[9px] font-mono">Del</kbd> 删除
        · <kbd className="inline-block px-1 py-0.5 bg-[var(--color-surface-hover)] border border-[var(--color-border)] rounded text-[9px] font-mono">Esc</kbd> 取消
      </span>
    </div>
  );
}

// ══════════════════════════════════════════
// 侧栏自动收起 — 鼠标滑到外侧5%触发
// ══════════════════════════════════════════
function AutoCollapsePanel({ side, width, onCollapse, children }: {
  side: "left" | "right";
  width: number;
  onCollapse: () => void;
  children: React.ReactNode;
}) {
  const triggerZone = Math.max(width * 0.05, 10); // 5%宽度，至少10px

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const inTriggerZone = side === "left"
      ? e.clientX - rect.left < triggerZone
      : rect.right - e.clientX < triggerZone;

    if (inTriggerZone) {
      onCollapse();
    }
  }, [side, triggerZone, onCollapse]);

  return (
    <div
      className="flex-shrink-0 relative"
      style={{ width: `${width}px` }}
      onMouseMove={handleMouseMove}
    >
      {children}
    </div>
  );
}

// ══════════════════════════════════════════
// 可拖拽分割线
// ══════════════════════════════════════════
function ResizeHandle({ side, onResize }: { side: "left" | "right"; onResize: (dx: number) => void }) {
  const dragging = useRef(false);
  const lastX = useRef(0);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    e.preventDefault();
    dragging.current = true;
    lastX.current = e.clientX;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const dx = e.clientX - lastX.current;
      lastX.current = e.clientX;
      onResize(dx);
    };
    const onMouseUp = () => {
      if (!dragging.current) return;
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    return () => { document.removeEventListener("mousemove", onMouseMove); document.removeEventListener("mouseup", onMouseUp); };
  }, [onResize]);

  return (
    <div
      className="flex-shrink-0 relative cursor-col-resize group"
      style={{ width: 6 }}
      onMouseDown={handleMouseDown}
    >
      <div className={`absolute inset-y-0 ${side === "left" ? "right-0.5" : "left-0.5"} w-[2px] bg-[var(--color-border)] group-hover:bg-[var(--color-accent)] transition-colors rounded-full`} />
    </div>
  );
}

// ══════════════════════════════════════════
// 浮动气泡对话 — 匹配 demo 优雅气泡样式
// ══════════════════════════════════════════

function FloatDialogWrapper({
  dialogState, onDialogStateChange, partitionId, selectedNode, onNodeUpdated,
}: {
  dialogState: DialogState | null;
  onDialogStateChange: (s: DialogState | null) => void;
  partitionId: string;
  selectedNode: GraphNode | null;
  onNodeUpdated: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState<{ role: "ai" | "user"; text: string }[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  // 自动滚动
  useEffect(() => {
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [msgs]);

  // 拖动
  const btnRef = useRef<HTMLButtonElement>(null);
  const dragRef = useRef({ dragging: false, moved: false, startX: 0, startY: 0, startLeft: 0, startTop: 0 });
  const SNAP_THRESHOLD = 30;
  const POS_KEY = "kt-float-pos";
  const [pos, setPos] = useState<{ x: number; y: number }>(() => {
    try { const s = localStorage.getItem(POS_KEY); if (s) return JSON.parse(s); } catch {}
    return { x: typeof window !== "undefined" ? window.innerWidth - 72 : 0, y: typeof window !== "undefined" ? window.innerHeight - 80 : 0 };
  });

  const [snapped, setSnapped] = useState<"none" | "left" | "right">(() => {
    try { const s = localStorage.getItem(POS_KEY); if (s) { const p = JSON.parse(s); if (p.x <= SNAP_THRESHOLD) return "left"; if (p.x >= window.innerWidth - 52 - SNAP_THRESHOLD) return "right"; } } catch {}
    return "right";
  });

  const handleDragStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    const cx = "touches" in e ? e.touches[0].clientX : e.clientX;
    const cy = "touches" in e ? e.touches[0].clientY : e.clientY;
    let adjustedX = pos.x;
    if (snapped === "left") adjustedX = 8;
    else if (snapped === "right") adjustedX = window.innerWidth - 60;
    if (adjustedX !== pos.x) setPos({ x: adjustedX, y: pos.y });
    setSnapped("none");
    dragRef.current = { dragging: true, moved: false, startX: cx, startY: cy, startLeft: adjustedX, startTop: pos.y };
  }, [pos, snapped]);

  useEffect(() => {
    const onMove = (e: MouseEvent | TouchEvent) => {
      if (!dragRef.current.dragging) return;
      e.preventDefault();
      const cx = "touches" in e ? e.touches[0].clientX : e.clientX;
      const cy = "touches" in e ? e.touches[0].clientY : e.clientY;
      const dx = cx - dragRef.current.startX;
      const dy = cy - dragRef.current.startY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) dragRef.current.moved = true;
      setPos({
        x: Math.max(0, Math.min(window.innerWidth - 52, dragRef.current.startLeft + dx)),
        y: Math.max(0, Math.min(window.innerHeight - 52, dragRef.current.startTop + dy)),
      });
    };
    const onUp = () => {
      if (!dragRef.current.dragging) return;
      dragRef.current.dragging = false;
      if (dragRef.current.moved) {
        setPos(prev => {
          const vw = window.innerWidth;
          let newX = prev.x;
          let newSnap: "none" | "left" | "right" = "none";
          if (prev.x < 60) { newX = -26; newSnap = "left"; }
          else if (prev.x > vw - 52 - 60) { newX = vw - 26; newSnap = "right"; }
          setSnapped(newSnap);
          const s = { x: newX, y: prev.y };
          try { localStorage.setItem(POS_KEY, JSON.stringify(s)); } catch {}
          return s;
        });
      }
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    window.addEventListener("touchmove", onMove, { passive: false });
    window.addEventListener("touchend", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); window.removeEventListener("touchmove", onMove); window.removeEventListener("touchend", onUp); };
  }, []);

  const handleClick = () => {
    if (dragRef.current.moved) { dragRef.current.moved = false; return; }
    setOpen(!open);
  };

  const isNodeMode = dialogState?.type === "tree_exploration" && !!dialogState.boundNode;

  const send = async () => {
    if (!input.trim() || sending) return;
    const text = input.trim();
    setMsgs(p => [...p, { role: "user", text }]);
    setInput("");
    setSending(true);
    try {
      if (dialogState && dialogState.conversationId) {
        const res = await fetch(`${API_BASE}/api/conversations/tree/conversation/${dialogState.conversationId}/message`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, partition_id: partitionId }),
        });
        const data = await res.json();
        setMsgs(p => [...p, { role: "ai", text: data.response || data.text || "（收到）" }]);
      } else {
        // 没有对话时模拟回复
        setMsgs(p => [...p, { role: "ai", text: `你好！已收到关于「${text}」的消息。可以点击右侧节点选择具体知识点进行深入学习。` }]);
      }
    } catch {
      setMsgs(p => [...p, { role: "ai", text: "发送失败，请重试。" }]);
    } finally {
      setSending(false);
    }
  };

  // 吸附 + hover 恢复
  const [hovering, setHovering] = useState(false);
  const isSnapped = snapped !== "none";
  const showFull = !isSnapped || hovering || open;

  return (
    <>
      <button ref={btnRef}
        onMouseDown={handleDragStart}
        onTouchStart={handleDragStart}
        onClick={handleClick}
        onMouseEnter={() => setHovering(true)}
        onMouseLeave={() => setHovering(false)}
        className="fixed w-[52px] h-[52px] rounded-full bg-[var(--color-accent)] text-white border-none cursor-pointer flex items-center justify-center shadow-lg z-50 hover:scale-105 transition-all duration-300 overflow-hidden"
        style={{
          left: isSnapped ? (showFull ? (snapped === "left" ? 8 : pos.x - 18) : pos.x) : pos.x,
          top: `${pos.y}px`,
        }}>
        {open ? (
          <X size={20} />
        ) : (
          <MessageCircle size={22} />
        )}
      </button>

      {open && (
        <div className="fixed w-[380px] max-h-[560px] bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl shadow-2xl z-50 flex flex-col overflow-hidden animate-in slide-in-from-bottom-4 duration-200"
          style={{
            left: `${Math.min(snapped === "left" ? 12 : pos.x, window.innerWidth - 400)}px`,
            bottom: `${window.innerHeight - pos.y + 8}px`,
          }}>
          {/* 头部 */}
          <div className="flex items-center gap-2 px-4 py-3 border-b border-[var(--color-border)] flex-shrink-0">
            <MessageCircle size={15} className="text-[var(--color-accent)]" />
            <span className="text-xs font-medium text-[var(--color-text)]">
              {isNodeMode ? "节点探索" : "知识树助手"}
            </span>
            {isNodeMode && dialogState?.boundNode && (
              <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--color-accent)]/10 text-[var(--color-accent)] truncate max-w-[100px]">
                {dialogState.boundNode.label}
              </span>
            )}
          </div>

          {/* 消息列表 */}
          <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-0">
            {msgs.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-center gap-2 py-6">
                <Bot size={24} className="text-[var(--color-accent)] opacity-40" />
                <p className="text-xs text-[var(--color-text-muted)]">
                  {isNodeMode ? "选中节点后会自动进入探索模式" : "点击节点选择具体知识点"}
                </p>
              </div>
            )}
            {msgs.map((msg, i) => (
              <div key={i} className={`flex gap-2 ${msg.role === "user" ? "flex-row-reverse" : ""}`} style={{ maxWidth: "92%" }}>
                <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs shrink-0 ${
                  msg.role === "user" ? "bg-[var(--color-accent)]/10" : "bg-[var(--color-page-secondary)]"
                }`}>
                  {msg.role === "user" ? "👤" : "🤖"}
                </div>
                <div className={`px-3 py-2 text-[11px] leading-relaxed whitespace-pre-wrap rounded-xl ${
                  msg.role === "user"
                    ? "bg-[var(--color-accent)] text-white rounded-tr-md"
                    : "bg-[var(--color-page-secondary)] border border-[var(--color-border)] text-[var(--color-text)] rounded-tl-md"
                }`}>
                  {msg.text}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex gap-2" style={{ maxWidth: "92%" }}>
                <div className="w-6 h-6 rounded-full bg-[var(--color-page-secondary)] flex items-center justify-center text-xs shrink-0">🤖</div>
                <div className="px-3 py-2 rounded-xl rounded-tl-md border border-[var(--color-border)] bg-[var(--color-page-secondary)]">
                  <Loader2 size={12} className="animate-spin text-[var(--color-text-muted)]" />
                </div>
              </div>
            )}
          </div>

          {/* 输入区 */}
          <div className="flex-shrink-0 px-4 py-3 border-t border-[var(--color-border)] bg-[var(--color-surface)]">
            <div className="flex items-center gap-2">
              <input value={input} onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && send()}
                placeholder="输入消息…"
                className="flex-1 px-3 py-2 text-[12px] border border-[var(--color-border)] rounded-lg bg-[var(--color-page-secondary)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors" />
              <button onClick={send} disabled={sending || !input.trim()}
                className="p-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-40 transition-opacity">
                {sending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

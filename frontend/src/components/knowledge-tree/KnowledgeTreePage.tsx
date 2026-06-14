"use client";

import React, { useState } from "react";
import { Plus, X, Check, AlertCircle, Sparkles, Loader2, ZoomIn, ZoomOut, Maximize, RefreshCw } from "lucide-react";
import type { GraphData, GraphNode } from "@/lib/types/graph-types";
import { filterByLevel, subtreeFilter, findNodeById } from "@/lib/types/graph-types";
import FocusGraph from "@/components/graph/graphs/FocusGraph";
import ForceGraph from "@/components/graph/graphs/ForceGraph";
import DAGGraph from "@/components/graph/graphs/DAGGraph";
import NodeDetailPanel from "@/components/graph/panels/NodeDetailPanel";
import FloatingNodeCard from "@/components/graph/panels/FloatingNodeCard";
import LayerPanel from "./LayerPanel";
import DialogContainer from "./DialogContainer";
import ContextMenu, { getDefaultContextMenuItems } from "./ContextMenu";
import { TopBar, StatusBar, FloatDialogWrapper, AutoCollapsePanel, ResizeHandle } from "./index";
import { useTreeLayout } from "@/hooks/graph/useTreeLayout";
import { useGraphCanvas } from "@/hooks/graph/useGraphCanvas";
import EmojiPicker from "@/components/ui/EmojiPicker";
import { authedFetch } from "@/lib/api/api";

// ── 导出类型（供外部引用） ──
export type GraphMode = "mindmap" | "force" | "dag";
export interface DialogState {
  type: "normal" | "tree_exploration" | "temporary";
  conversationId: string;
  parentId: string;
  parentType: "dir";
  boundNode?: GraphNode | null;
}

// ══════════════════════════════════════════════════════════════
//  子组件 — Loading / Empty / Error / NoPartition
// ══════════════════════════════════════════════════════════════

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

function EmptyState({ partitionId, onLoad }: { partitionId: string; onLoad: () => void }) {
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
  const handleGenerate = async () => {
    setGenerating(true);
    setGenError(null);
    try {
      const res = await authedFetch(`/api/knowledge/graph/${partitionId}/generate`, { method: "POST" });
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
        <p className="text-sm text-[var(--color-text-muted)] leading-relaxed">学习分区创建后，知识树需要手动或通过 AI 生成。</p>
      </div>
      {genError && <div className="px-4 py-2.5 rounded-lg bg-red-500/5 border border-red-500/20 text-xs text-[var(--color-danger)] max-w-sm">{genError}</div>}
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
    </div>
  );
}

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
    setCreating(true); setCreateError(null);
    try {
      const res = await authedFetch(`/api/conversations/tree/partition`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName.trim(), emoji: newEmoji }),
      });
      if (!res.ok) throw new Error(`创建失败（${res.status}）`);
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
    { name: "机器学习", emoji: "📐" }, { name: "Python 编程", emoji: "🐍" },
    { name: "系统设计", emoji: "🔢" }, { name: "数据结构", emoji: "🗃️" },
    { name: "数据科学", emoji: "⚛️" }, { name: "英语单词", emoji: "📖" },
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[500px] gap-8 px-6">
      <div className="relative">
        <div className="w-32 h-32 rounded-3xl bg-gradient-to-br from-[var(--color-accent)]/15 to-[var(--color-accent)]/5 flex items-center justify-center shadow-sm border border-[var(--color-border)]">
          <svg width="56" height="56" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" className="text-[var(--color-accent)]">
            <circle cx="12" cy="5" r="2.5" strokeWidth="1.5"/><circle cx="5" cy="12" r="2.5" strokeWidth="1.5"/>
            <circle cx="19" cy="12" r="2.5" strokeWidth="1.5"/><circle cx="8" cy="19" r="2.5" strokeWidth="1.5"/>
            <circle cx="16" cy="19" r="2.5" strokeWidth="1.5"/>
            <line x1="10" y1="7" x2="7" y2="10" strokeWidth="1.2"/><line x1="14" y1="7" x2="17" y2="10" strokeWidth="1.2"/>
            <line x1="7" y1="14" x2="9" y2="17" strokeWidth="1.2"/><line x1="17" y1="14" x2="15" y2="17" strokeWidth="1.2"/>
          </svg>
        </div>
        <div className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-[var(--color-success)]/30 animate-pulse" />
        <div className="absolute -bottom-1 -left-1 w-3 h-3 rounded-full bg-[var(--color-accent)]/20" />
      </div>
      <div className="text-center max-w-md space-y-2">
        <h3 className="text-xl font-semibold text-[var(--color-text)] tracking-tight">开始构建你的知识树</h3>
        <p className="text-sm text-[var(--color-text-muted)] leading-relaxed">知识树是学习的大脑地图 — 将学科知识结构化，让 AI 帮你梳理脉络。</p>
      </div>
      {showCreate ? (
        <div className="w-full max-w-sm bg-[var(--color-surface-elevated)] border border-[var(--color-border)] rounded-2xl shadow-md p-5 space-y-4">
          <div className="flex items-center gap-2">
            <div className="w-1 h-5 rounded-full bg-[var(--color-accent)]" />
            <span className="text-sm font-semibold text-[var(--color-text)]">新建学习分区</span>
          </div>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] font-medium text-[var(--color-text-muted)] uppercase tracking-wide">名称</label>
              <input value={newName} onChange={e => setNewName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleCreate()}
                className="mt-1 w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg bg-[var(--color-page-secondary)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)]"
                placeholder="例如：机器学习" autoFocus />
            </div>
            <EmojiPicker value={newEmoji} onChange={setNewEmoji} label="选择图标" />
          </div>
          {createError && <div className="px-3 py-2 rounded-lg bg-red-500/5 border border-red-500/20 text-[10px] text-[var(--color-danger)]">{createError}</div>}
          <div className="flex items-center gap-2 pt-1">
            <button onClick={handleCreate} disabled={creating || !newName.trim()}
              className="flex-1 inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium bg-[var(--color-accent)] text-white rounded-xl hover:opacity-90 disabled:opacity-40 transition-all shadow-sm">
              {creating ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />} 创建并生成知识树
            </button>
            <button onClick={() => setShowCreate(false)}
              className="px-4 py-2.5 text-sm font-medium border border-[var(--color-border)] rounded-xl text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors">取消</button>
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
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg> 临时对话
            </button>
          )}
        </div>
      )}
      <div className="w-full max-w-lg">
        <div className="flex items-center gap-2 mb-3">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[var(--color-text-muted)]">
            <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
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
    </div>
  );
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[400px] gap-4 px-4">
      <div className="w-20 h-20 rounded-2xl bg-red-500/5 border border-red-500/10 flex items-center justify-center">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-[var(--color-danger)]">
          <circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/></svg>
      </div>
      <div className="text-center max-w-sm space-y-1">
        <h3 className="text-sm font-semibold text-[var(--color-text)]">加载失败</h3>
        <p className="text-xs text-[var(--color-text-muted)]">{message}</p>
      </div>
      <button onClick={onRetry}
        className="inline-flex items-center gap-2 px-4 py-2 text-xs font-medium border border-[var(--color-border)] rounded-lg text-[var(--color-text-secondary)] hover:bg-[var(--color-surface)] transition-colors">
        <RefreshCw size={12} /> 重试
      </button>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
//  子组件 — FocusBreadcrumb / ZoomControls / AddNodeDialog
// ══════════════════════════════════════════════════════════════

function FocusBreadcrumb({ focusRootId, graphData, focusBreadcrumb, onClearFocus, onSetFocus }: {
  focusRootId: string; graphData: GraphData; focusBreadcrumb: GraphNode[];
  onClearFocus: () => void; onSetFocus: (id: string) => void;
}) {
  return (
    <div className="flex-shrink-0 flex items-center gap-1.5 px-4 py-1.5 border-b border-[var(--color-border)] bg-[var(--color-page-secondary)] text-[11px] text-[var(--color-text-muted)]">
      <button onClick={onClearFocus} className="text-[var(--color-accent)] hover:underline font-medium">全局视图</button>
      <span className="text-[var(--color-text-muted)] mx-0.5">›</span>
      {focusBreadcrumb.map(ancestor => (
        <span key={ancestor.id} className="flex items-center gap-1">
          <button onClick={() => onSetFocus(ancestor.id)} className="hover:text-[var(--color-accent)] hover:underline transition-colors">{ancestor.label}</button>
          <span className="text-[var(--color-text-muted)] mx-0.5">›</span>
        </span>
      ))}
      <span className="text-[var(--color-text)] font-medium">{findNodeById(graphData, focusRootId)?.label || "当前聚焦"}</span>
    </div>
  );
}

function ZoomControls({ zoomLevel, graphFullscreen, onZoomIn, onZoomOut, onReset, onToggleFullscreen }: {
  zoomLevel: number; graphFullscreen: boolean;
  onZoomIn: () => void; onZoomOut: () => void; onReset: () => void; onToggleFullscreen: () => void;
}) {
  return (
    <div className="absolute bottom-4 right-4 flex items-center gap-0.5 bg-[var(--color-surface)] border border-[var(--color-border)] rounded-lg shadow-md p-1 z-20">
      <button onClick={onZoomOut} disabled={zoomLevel <= 0.3}
        className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] disabled:opacity-30 transition-colors" title="缩小 (Ctrl+-)">
        <ZoomOut size={14} />
      </button>
      <button onClick={onReset}
        className="px-2 py-1 text-[10px] font-medium text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] rounded transition-colors" title="重置缩放 (Ctrl+0)">
        {Math.round(zoomLevel * 100)}%
      </button>
      <button onClick={onZoomIn} disabled={zoomLevel >= 3}
        className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] disabled:opacity-30 transition-colors" title="放大 (Ctrl++)">
        <ZoomIn size={14} />
      </button>
      <div className="w-px h-4 bg-[var(--color-border)] mx-0.5" />
      <button onClick={onToggleFullscreen}
        className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors" title={graphFullscreen ? "退出全屏" : "全屏"}>
        <Maximize size={14} />
      </button>
    </div>
  );
}

function AddNodeDialog({ onClose, onAdd, graphData, label, setLabel, parentId, setParentId }: {
  onClose: () => void; onAdd: () => void; graphData: GraphData | null;
  label: string; setLabel: (v: string) => void; parentId: string; setParentId: (v: string) => void;
}) {
  const [loading, setLoading] = useState(false);

  const handleAdd = async () => {
    if (!label.trim() || loading) return;
    setLoading(true);
    // The actual add logic is in canvas.handleAddNode which reads from state
    // This dialog is for UI only — the orchestrator uses inline state
    onAdd();
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-5 w-80 space-y-4 shadow-xl animate-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-[var(--color-accent)]/10 flex items-center justify-center"><Plus size={14} className="text-[var(--color-accent)]" /></div>
            <h3 className="text-sm font-semibold text-[var(--color-text)]">{parentId ? "添加子节点" : "添加根节点"}</h3>
          </div>
          <button onClick={onClose} className="p-1 rounded-md hover:bg-[var(--color-surface-hover)] transition-colors"><X size={14} className="text-[var(--color-text-muted)]" /></button>
        </div>
        <div className="space-y-3">
          <div>
            <label className="block text-[10px] font-medium text-[var(--color-text-muted)] mb-1 uppercase tracking-wider">节点名称</label>
            <input value={label} onChange={e => setLabel(e.target.value)}
              placeholder="输入知识节点名称" autoFocus
              className="w-full px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] rounded-lg focus:outline-none focus:border-[var(--color-accent)] focus:ring-1 focus:ring-[var(--color-accent)]/30"
              onKeyDown={e => { if (e.key === "Enter" && label.trim()) handleAdd(); if (e.key === "Escape") onClose(); }} />
          </div>
          <div>
            <label className="block text-[10px] font-medium text-[var(--color-text-muted)] mb-1 uppercase tracking-wider">父节点</label>
            <select value={parentId} onChange={e => setParentId(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] rounded-lg focus:outline-none focus:border-[var(--color-accent)]">
              <option value="">无父节点（根节点）</option>
              {graphData?.nodes?.map(n => <option key={n.id} value={n.id}>{n.label}</option>)}
            </select>
          </div>
        </div>
        <div className="flex gap-2 justify-end pt-1">
          <button onClick={onClose} className="px-3 py-1.5 text-xs border border-[var(--color-border)] rounded-lg text-[var(--color-text-muted)] hover:bg-[var(--color-surface-hover)] transition-colors">取消</button>
          <button onClick={handleAdd} disabled={loading || !label.trim()}
            className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 transition-colors flex items-center gap-1.5">
            {loading ? <><Loader2 size={10} className="animate-spin" /> 添加中</> : <><Check size={12} /> 确认添加</>}
          </button>
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════════
//  主组件 — 编排器
// ══════════════════════════════════════════════════════════════

export default function KnowledgeTreePage() {
  const { layoutPref, setLayoutPref } = useTreeLayout();
  const canvas = useGraphCanvas(layoutPref, setLayoutPref);

  if (canvas.loading) return <LoadingSkeleton />;
  if (canvas.error) return <ErrorState message={canvas.error} onRetry={canvas.loadGraph} />;

  if (!canvas.graphData || canvas.graphData.nodes.length === 0) {
    if (!canvas.partitionId) {
      return <NoPartitionState onPartitionCreated={canvas.setPartitionId} onStartTemporary={canvas.handleStartTemporary} />;
    }
    return <EmptyState partitionId={canvas.partitionId} onLoad={canvas.loadGraph} />;
  }

  return (
    <div className="flex flex-col h-full">
      <TopBar
        partitionId={canvas.partitionId}
        partitionList={canvas.partitionList}
        onPartitionChange={canvas.setPartitionId}
        graphMode={canvas.graphMode}
        onGraphModeChange={(m) => setLayoutPref(p => ({ ...p, graphMode: m }))}
        showDialogPanel={layoutPref.showDialogPanel}
        onToggleDialogPanel={() => setLayoutPref(p => ({ ...p, showDialogPanel: !p.showDialogPanel }))}
        showDetailPanel={layoutPref.showDetailPanel}
        onToggleDetailPanel={() => setLayoutPref(p => ({ ...p, showDetailPanel: !p.showDetailPanel }))}
        graphSearch={canvas.graphSearch}
        onGraphSearchChange={canvas.setGraphSearch}
        matchCount={canvas.matchedNodeIds.length}
        onAddNode={() => canvas.setAddNodeOpen(true)}
        onToggleFullscreen={() => canvas.setGraphFullscreen(!canvas.graphFullscreen)}
        graphFullscreen={canvas.graphFullscreen}
        layerOpen={layoutPref.layerOpen}
        onToggleLayer={() => setLayoutPref(p => ({ ...p, layerOpen: !p.layerOpen }))}
      />

      {canvas.focusRootId && (
        <FocusBreadcrumb
          focusRootId={canvas.focusRootId}
          graphData={canvas.graphData!}
          focusBreadcrumb={canvas.focusBreadcrumb}
          onClearFocus={canvas.handleClearFocus}
          onSetFocus={canvas.handleSetFocus}
        />
      )}

      <div className="flex flex-1 overflow-hidden">
        {layoutPref.showDialogPanel && (
          <>
            <AutoCollapsePanel side="left" width={layoutPref.dialogWidth}
              onCollapse={() => setLayoutPref(p => ({ ...p, showDialogPanel: false }))}>
              <DialogContainer
                dialogState={canvas.dialogState}
                onDialogStateChange={canvas.setDialogState}
                partitionId={canvas.partitionId}
                selectedNode={canvas.selectedNode}
                onNodeUpdated={canvas.loadGraph}
                width={layoutPref.dialogWidth}
                onWidthChange={(w) => setLayoutPref(p => ({ ...p, dialogWidth: w }))}
              />
            </AutoCollapsePanel>
            <ResizeHandle side="left" onResize={(dx) => setLayoutPref(p => ({ ...p, dialogWidth: Math.max(200, Math.min(600, p.dialogWidth + dx)) }))} />
          </>
        )}

        <div ref={canvas.canvasRef as React.RefObject<HTMLDivElement>}
          className="flex-1 min-w-0 relative overflow-hidden bg-[var(--color-bg)]"
          style={{ backgroundImage: "radial-gradient(circle at 1px 1px, var(--color-border) 1px, transparent 0)", backgroundSize: "24px 24px" }}>
          {layoutPref.layerOpen && canvas.graphData && (
            <LayerPanel
              graphData={canvas.graphData}
              searchQuery={canvas.graphSearch}
              onSearchChange={canvas.setGraphSearch}
              matchedNodeIds={canvas.matchedNodeIds}
              selectedNodeId={canvas.selectedNode?.id}
              onNodeSelect={canvas.handleNodeSelect}
              maxDisplayLevel={canvas.maxDisplayLevel}
              onMaxLevelChange={(l) => setLayoutPref(p => ({ ...p, maxDisplayLevel: l }))}
              onClose={() => setLayoutPref(p => ({ ...p, layerOpen: false }))}
              masteryFilter={canvas.masteryFilter}
              onMasteryFilterChange={canvas.setMasteryFilter}
            />
          )}
          <div ref={canvas.graphContainerRef as React.RefObject<HTMLDivElement>} className="absolute inset-0">
            <div className="w-full h-full transition-transform duration-200 ease-out origin-top-left"
              style={{ transform: `scale(${canvas.zoomLevel})`, transformOrigin: "top left" }}>
              {canvas.graphMode === "mindmap" && (
                <FocusGraph
                  data={filterByLevel(subtreeFilter(canvas.graphData, canvas.focusRootId), canvas.maxDisplayLevel)}
                  selectedNodeId={canvas.selectedNode?.id} onNodeSelect={canvas.handleNodeSelect}
                  onFocusNode={canvas.handleSetFocus} onNodeContextMenu={canvas.handleNodeContextMenu}
                  activePath={[]} width={canvas.graphSize.width} height={canvas.graphSize.height}
                  searchQuery={canvas.graphSearch} matchedNodeIds={canvas.matchedNodeIds}
                />
              )}
              {canvas.graphMode === "force" && (
                <ForceGraph
                  data={filterByLevel(subtreeFilter(canvas.graphData, canvas.focusRootId), canvas.maxDisplayLevel)}
                  selectedNodeId={canvas.selectedNode?.id} onNodeSelect={canvas.handleNodeSelect}
                  onNodeContextMenu={canvas.handleNodeContextMenu}
                  width={canvas.graphSize.width} height={canvas.graphSize.height}
                />
              )}
              {canvas.graphMode === "dag" && (
                <DAGGraph
                  data={filterByLevel(subtreeFilter(canvas.graphData, canvas.focusRootId), canvas.maxDisplayLevel)}
                  selectedNodeId={canvas.selectedNode?.id} onNodeSelect={canvas.handleNodeSelect}
                  onNodeContextMenu={canvas.handleNodeContextMenu} activePath={[]}
                  width={canvas.graphSize.width} height={canvas.graphSize.height}
                  searchQuery={canvas.graphSearch} matchedNodeIds={canvas.matchedNodeIds}
                />
              )}
            </div>
            <ZoomControls zoomLevel={canvas.zoomLevel} graphFullscreen={canvas.graphFullscreen}
              onZoomIn={() => canvas.setZoomLevel(z => Math.min(3, z + 0.15))}
              onZoomOut={() => canvas.setZoomLevel(z => Math.max(0.3, z - 0.15))}
              onReset={() => canvas.setZoomLevel(1)}
              onToggleFullscreen={() => canvas.setGraphFullscreen(!canvas.graphFullscreen)}
            />
          </div>
        </div>

        {layoutPref.showDetailPanel && canvas.selectedNode && (
          <>
            <ResizeHandle side="right" onResize={(dx) => setLayoutPref(p => ({ ...p, detailWidth: Math.max(200, Math.min(600, p.detailWidth - dx)) }))} />
            <AutoCollapsePanel side="right" width={layoutPref.detailWidth}
              onCollapse={() => { canvas.setSelectedNode(null); setLayoutPref(p => ({ ...p, showDetailPanel: false })); }}>
              <div className="border-l border-[var(--color-border)] bg-[var(--color-surface)] overflow-y-auto h-full" style={{ width: `${layoutPref.detailWidth}px` }}>
                <NodeDetailPanel
                  node={canvas.selectedNode} partitionId={canvas.partitionId}
                  onClose={() => canvas.setSelectedNode(null)} onNodeUpdated={canvas.loadGraph}
                  onStartPractice={() => {}} onRequestExplain={() => {}}
                  parentNode={canvas.selectedNode?.parent ? canvas.graphData?.nodes.find(n => n.id === canvas.selectedNode!.parent) ?? null : null}
                  onNavigateToParent={(parent) => canvas.setSelectedNode(parent)}
                />
              </div>
            </AutoCollapsePanel>
          </>
        )}
      </div>

      {!layoutPref.showDetailPanel && canvas.selectedNode && (
        <FloatingNodeCard node={canvas.selectedNode} partitionId={canvas.partitionId}
          onClose={() => canvas.setSelectedNode(null)} onNodeUpdated={canvas.loadGraph}
          onStartPractice={() => {}} onRequestExplain={() => {}}
          parentNode={canvas.selectedNode?.parent ? canvas.graphData?.nodes.find(n => n.id === canvas.selectedNode!.parent) ?? null : null}
          onNavigateToParent={(parent) => canvas.setSelectedNode(parent)}
        />
      )}

      <StatusBar stats={canvas.stats}
        activeFilter={canvas.masteryFilter.size === 3 ? "all" : canvas.masteryFilter.size === 1 ? Array.from(canvas.masteryFilter)[0] : "custom"}
        onStatClick={(filter) => {
          if (filter === "all") canvas.setMasteryFilter(new Set(["mastered", "learning", "untouched"]));
          else canvas.setMasteryFilter(new Set([filter]));
        }}
      />

      {!layoutPref.showDialogPanel && (
        <FloatDialogWrapper dialogState={canvas.dialogState} onDialogStateChange={canvas.setDialogState}
          partitionId={canvas.partitionId} selectedNode={canvas.selectedNode} onNodeUpdated={canvas.loadGraph} />
      )}

      {canvas.addNodeOpen && <AddNodeDialog
        onClose={() => canvas.setAddNodeOpen(false)}
        onAdd={canvas.handleAddNode}
        graphData={canvas.graphData}
        label={canvas.newNodeLabel}
        setLabel={canvas.setNewNodeLabel}
        parentId={canvas.newNodeParent}
        setParentId={canvas.setNewNodeParent}
      />}

      {canvas.toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-in slide-in-from-bottom-2 duration-200">
          <div className={`flex items-center gap-2 px-4 py-2.5 rounded-lg shadow-lg text-xs font-medium
            ${canvas.toast.type === "success" ? "bg-emerald-500/90 text-white" : ""}
            ${canvas.toast.type === "error" ? "bg-red-500/90 text-white" : ""}
            ${canvas.toast.type === "info" ? "bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text)]" : ""}`}>
            {canvas.toast.type === "success" && <Check size={13} />}
            {canvas.toast.type === "error" && <AlertCircle size={13} />}
            {canvas.toast.type === "info" && <Sparkles size={13} />}
            {canvas.toast.message}
          </div>
        </div>
      )}

      {canvas.contextMenu && (
        <ContextMenu x={canvas.contextMenu.x} y={canvas.contextMenu.y}
          items={getDefaultContextMenuItems(canvas.contextMenu.node.label, canvas.contextMenu.node.id, {
            onEdit: () => canvas.handleContextMenuAction("edit"),
            onAddChild: () => canvas.handleContextMenuAction("add-child"),
            onAiExpand: () => canvas.handleContextMenuAction("ai-expand"),
            onAiEdit: () => canvas.handleContextMenuAction("ai-edit"),
            onLinkConversation: () => canvas.handleContextMenuAction("link"),
            onExplain: () => canvas.handleContextMenuAction("explain"),
            onFocus: () => canvas.handleContextMenuAction("focus"),
            onDelete: () => canvas.handleContextMenuAction("delete"),
          })}
          onClose={() => canvas.setContextMenu(null)}
        />
      )}
    </div>
  );
}

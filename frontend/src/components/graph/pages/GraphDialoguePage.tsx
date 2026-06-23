"use client";

import React, { useState, useEffect, useRef, useMemo } from "react";
import {
  Loader2, MessageSquare, FileText, Brain, Sparkles, Rocket,
  Play, StickyNote, Lightbulb, Network, Focus,
  GitGraph, RefreshCw, Search, X, Plus, MessageCircle,
} from "lucide-react";
import dynamic from "next/dynamic";
import { getMasteryColor, filterByLevel } from "@/lib/types/graph-types";
import { useGraphDialogue } from "@/hooks/graph/useGraphDialogue";
import type { UseGraphDialogueReturn } from "@/hooks/graph/useGraphDialogue";
import type { GraphData } from "@/lib/types/graph-types";
import PracticePanel from "@/components/practice/panels/PracticePanel";
import NodeDetailPanel from "@/components/graph/panels/NodeDetailPanel";
import TreeChatPanel from "@/components/graph/panels/TreeChatPanel";
import { authedFetch, API_BASE } from "@/lib/api/api";
import { knowledgeNodesApi } from "@/lib/api/knowledge-tree-api";
import { useIsMobile } from '@/hooks/useMediaQuery';
import { useGraphNodeActions } from "@/hooks/graph/useGraphNodeActions";

// ── 动态导入 ──
const FocusGraph = dynamic(() => import("@/components/graph/graphs/FocusGraph"), { ssr: false });
const ForceGraph = dynamic(() => import("@/components/graph/graphs/ForceGraph"), { ssr: false });
const DAGGraph = dynamic(() => import("@/components/graph/graphs/DAGGraph"), { ssr: false });
const DeepReadToolbar = dynamic(() => import("@/components/graph/panels/DeepReadToolbar"), { ssr: false });
const DialogueCardList = dynamic(() => import("@/components/graph/pages/DialogueCardList"), { ssr: false });
const ExplainModal = dynamic(() => import("@/components/graph/modals/ExplainModal"), { ssr: false });
const NoteSidebar = dynamic(() => import("@/components/graph/panels/NoteSidebar"), { ssr: false });
const ReflectionModal = dynamic(() => import("@/components/graph/modals/ReflectionModal"), { ssr: false });
const GoalSettingModal = dynamic(() => import("@/components/graph/modals/GoalSettingModal"), { ssr: false });
const AggregateNotesModal = dynamic(() => import("@/components/graph/modals/AggregateNotesModal"), { ssr: false });
const ProjectsPanel = dynamic(() => import("@/components/graph/panels/ProjectsPanel"), { ssr: false });

// ── 骨架屏 ──
function LoadingSkeleton() {
  return (
    <div className="flex h-full min-h-[600px] gap-0 animate-pulse">
      <div className="flex-1 p-4 space-y-4">
        <div className="h-8 bg-[var(--color-surface)] rounded w-1/3" />
        <div className="h-6 bg-[var(--color-surface)] rounded w-1/4" />
        <div className="grid grid-cols-2 gap-3">
          {[1, 2, 3, 4].map(i => <div key={i} className="h-24 bg-[var(--color-surface)] rounded-lg" />)}
        </div>
      </div>
      <div className="flex-1 bg-[var(--color-surface)] m-4 rounded-lg" />
    </div>
  );
}

// ── 无分区引导页 ──
function NoPartitionState() {
  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[500px] gap-4">
      <div className="w-20 h-20 rounded-full bg-[var(--color-surface)] flex items-center justify-center">
        <GitGraph size={36} className="text-[var(--color-text-muted)] opacity-40" />
      </div>
      <h3 className="text-base font-medium text-[var(--color-text)]">还没有学习分区</h3>
      <p className="text-xs text-[var(--color-text-muted)] max-w-xs text-center leading-relaxed">
        知识树是基于学习分区自动构建的。
        <br />请先到对话系统中创建会话，分区会自动生成。
      </p>
      <div className="flex items-center gap-3">
        <a href="/"
          className="inline-flex items-center gap-2 px-5 py-2.5 text-sm bg-[var(--color-accent)] text-white rounded-lg hover:opacity-90 active:scale-[0.97] transition-all">
          <MessageCircle size={14} />
          前往对话系统
        </a>
      </div>
    </div>
  );
}

// ── 空状态 ──
function EmptyState({ onLoad, onGenerate }: { onLoad: () => void; onGenerate: () => Promise<boolean> }) {
  const [generating, setGenerating] = useState(false);
  const handleGenerate = async () => {
    setGenerating(true);
    try {
      await onGenerate();
      onLoad();
    } catch {}
    setGenerating(false);
  };

  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[500px] gap-4">
      <div className="w-20 h-20 rounded-full bg-[var(--color-surface)] flex items-center justify-center">
        <GitGraph size={36} className="text-[var(--color-text-muted)] opacity-40" />
      </div>
      <h3 className="text-base font-medium text-[var(--color-text)]">该分区暂无知识树</h3>
      <p className="text-xs text-[var(--color-text-muted)] max-w-xs text-center leading-relaxed">
        让 AI 为你生成该学科的知识树结构，
        <br />之后你可以手动补充和编辑。
      </p>
      <div className="flex items-center gap-3">
        <button onClick={handleGenerate} disabled={generating}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm bg-[var(--color-accent)] text-white rounded-lg hover:opacity-90 disabled:opacity-50 active:scale-[0.97] transition-all">
          {generating ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          AI 预生成知识树
        </button>
        <button onClick={onLoad}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm border border-[var(--color-border)] text-[var(--color-text-secondary)] rounded-lg hover:bg-[var(--color-surface)]">
          <RefreshCw size={14} /> 刷新
        </button>
      </div>
      <div className="mt-2 pt-4 border-t border-[var(--color-border)]/50 w-64 text-center">
        <p className="text-[10px] text-[var(--color-text-muted)] mb-2">或者先与 AI 对话，知识树会随学习自动生成</p>
        <a href="/"
          className="inline-flex items-center gap-2 px-4 py-2 text-sm border border-[var(--color-accent)]/30 text-[var(--color-accent)] rounded-lg hover:bg-[var(--color-accent)]/5 transition-all">
          <MessageCircle size={14} />
          开始临时对话
        </a>
      </div>
    </div>
  );
}

export type GraphMode = "mindmap" | "force" | "dag";
export type LeftTab = "dialogue" | "practice" | "notes" | "resources" | "projects";

export default function GraphDialoguePage() {
  const ctx = useGraphDialogue();
  const nodeActions = useGraphNodeActions({
    onNodeUpdated: ctx.loadGraph,
  });

  const generateGraph = nodeActions.generateGraph;

  // ── 加载骨架屏 ──
  if (ctx.loading) return <LoadingSkeleton />;

  if (ctx.error) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <div className="text-center space-y-3">
          <p className="text-sm text-[var(--color-error)]">加载失败: {ctx.error}</p>
          <button onClick={ctx.loadGraph} className="inline-flex items-center gap-1 text-xs text-[var(--color-accent)] hover:underline">
            <RefreshCw size={12} />重试
          </button>
        </div>
      </div>
    );
  }

  // ── 空状态 ──
  if (!ctx.graphData || ctx.graphData.nodes.length === 0) {
    if (!ctx.partitionId) {
      return <NoPartitionState />;
    }
    return <EmptyState onLoad={ctx.loadGraph} onGenerate={generateGraph} />;
  }

  return <GraphDialogueLayout ctx={ctx} />;
}

// ── 主布局 ──
function GraphDialogueLayout({ ctx }: { ctx: UseGraphDialogueReturn }) {
  const hasNode = !!ctx.selectedNode;
  const graphContainerRef = useRef<HTMLDivElement>(null);
  const [graphSize, setGraphSize] = useState({ width: 600, height: 500 });
  const [fsSize, setFsSize] = useState({ width: 800, height: 600 });
  const [addNodeOpen, setAddNodeOpen] = useState(false);
  const [newNodeLabel, setNewNodeLabel] = useState("");
  const [newNodeParent, setNewNodeParent] = useState("");
  const [addNodeLoading, setAddNodeLoading] = useState(false);
  const isMobile = useIsMobile();
  const [mobilePanelOpen, setMobilePanelOpen] = useState(false);

  const stats = useMemo(() => {
    if (!ctx.graphData || !ctx.graphData.nodes.length) return { total: 0, mastered: 0, learning: 0, avgMastery: 0 };
    const nodes = ctx.graphData.nodes;
    return {
      total: nodes.length,
      mastered: nodes.filter(n => n.mastery >= 0.8).length,
      learning: nodes.filter(n => n.mastery >= 0.05 && n.mastery < 0.8).length,
      avgMastery: nodes.reduce((s, n) => s + (n.mastery || 0), 0) / nodes.length,
    };
  }, [ctx.graphData]);

  // ── ResizeObserver ──
  useEffect(() => {
    const el = graphContainerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        setGraphSize({ width: Math.max(300, width), height: Math.max(300, height) });
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // ── 全屏尺寸 ──
  useEffect(() => {
    const update = () => setFsSize({ width: window.innerWidth - 40, height: window.innerHeight - 40 });
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [ctx.graphFullscreen]);

  // ── 键盘快捷键 ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (ctx.graphFullscreen) { ctx.setGraphFullscreen(false); return; }
        if (addNodeOpen) { setAddNodeOpen(false); return; }
        if (ctx.selectedNode) { ctx.setSelectedNode(null); }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [ctx, addNodeOpen]);

  // ── 添加节点 ──
  const handleAddNode = async () => {
    if (!newNodeLabel.trim()) return;
    setAddNodeLoading(true);
    try {
      await knowledgeNodesApi.create({
        label: newNodeLabel.trim(),
        parent_id: newNodeParent || undefined,
      });
      setAddNodeOpen(false);
      setNewNodeLabel("");
      ctx.loadGraph();
    } catch {}
    setAddNodeLoading(false);
  };

  // ── 模式切换 ──
  const graphMode = ctx.graphMode as GraphMode;
  const setGraphMode = (m: GraphMode) => ctx.setGraphMode(m as any);

  const modeBtn = (mode: GraphMode, label: string, icon: React.ReactNode) => (
    <button onClick={() => setGraphMode(mode)}
      className={`flex items-center gap-1 px-2 py-1 rounded-md text-[11px] transition-all ${
        graphMode === mode ? "bg-[var(--color-accent)] text-white font-medium shadow-sm" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
      }`}>{icon}{label}</button>
  );

  const tabBtn = (key: LeftTab, label: string, icon: React.ReactNode, badge?: number) => (
    <button onClick={() => ctx.setLeftTab(key as any)}
      className={`flex items-center gap-1.5 pb-2 text-xs font-medium border-b-2 transition-all ${
        ctx.leftTab === key
          ? "text-[var(--color-accent)] border-[var(--color-accent)]"
          : "text-[var(--color-text-muted)] border-transparent hover:text-[var(--color-text)]"
      }`}>
      {icon}{label}
      {badge != null && badge > 0 && (
        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[var(--color-surface-hover)]">{badge}</span>
      )}
    </button>
  );

  const graphTopbar = (
    <div className="flex-shrink-0 flex items-center gap-2 px-3 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
      {/* 模式切换 */}
      <div className="flex items-center gap-1 bg-[var(--color-page-secondary)] rounded-lg border border-[var(--color-border)] p-0.5">
        {modeBtn("mindmap", "思维导图", <GitGraph size={13} />)}
        {modeBtn("force", "力导向", <Network size={13} />)}
        {modeBtn("dag", "依赖图", <GitGraph size={13} />)}
      </div>

      {/* 搜索 */}
      <div className="flex-1 max-w-[180px] relative">
        <input value={ctx.graphSearch} onChange={(e) => ctx.setGraphSearch(e.target.value)}
          placeholder="搜索节点…"
          className="w-full pl-7 pr-2 py-1 text-[11px] rounded-md border border-[var(--color-border)] bg-[var(--color-page-secondary)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors"
        />
        <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
        {ctx.graphSearch && (
          <button onClick={() => ctx.setGraphSearch("")}
            className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"><X size={12} /></button>
        )}
      </div>
      {ctx.graphSearch && ctx.matchedNodeIds.length > 0 && (
        <span className="text-[10px] text-[var(--color-accent)] font-medium">{ctx.matchedNodeIds.length} 匹配</span>
      )}

      <div className="flex-1" />

      {/* 添加节点 */}
      <button onClick={() => setAddNodeOpen(true)}
        className="flex items-center gap-1 px-2 py-1 text-[10px] rounded-md bg-[var(--color-accent)]/10 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20 transition-all">
        <Plus size={12} />添加节点
      </button>

      <button onClick={() => ctx.setGraphFullscreen(!ctx.graphFullscreen)}
        className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-all"
        title={ctx.graphFullscreen ? "退出全屏 (Esc)" : "全屏"}><Focus size={14} /></button>
    </div>
  );

  // ── 统计概览 ──
  const statsBar = stats.total > 0 && (
    <div className="flex-shrink-0 flex items-center gap-4 px-3 py-1.5 border-b border-[var(--color-border)] bg-[var(--color-page-secondary)] text-[10px] text-[var(--color-text-muted)]">
      <span>📊 <strong className="text-[var(--color-text)]">{stats.total}</strong> 节点</span>
      <span>✅ 已掌握 <strong className="text-[var(--color-success)]">{stats.mastered}</strong></span>
      <span>📖 学习中 <strong className="text-[var(--color-warning)]">{stats.learning}</strong></span>
      <span>平均掌握度 <strong style={{ color: getMasteryColor(stats.avgMastery) }}>{Math.round(stats.avgMastery * 100)}%</strong></span>
    </div>
  );

  // ── 图谱面板 ──
  const graphPanel = (
    <div className="relative w-full h-full flex flex-col">
      {graphTopbar}
      {statsBar}

      <div ref={graphContainerRef} className="flex-1 overflow-hidden relative">
        {graphMode === "mindmap" && (
          <FocusGraph
            data={filterByLevel(ctx.graphData ?? { nodes: [], edges: [] }, ctx.maxDisplayLevel)}
            selectedNodeId={ctx.selectedNode?.id}
            onNodeSelect={ctx.handleNodeSelect}
            activePath={ctx.activePath}
            width={ctx.graphFullscreen ? fsSize.width : graphSize.width}
            height={ctx.graphFullscreen ? fsSize.height : graphSize.height}
            searchQuery={ctx.graphSearch}
            matchedNodeIds={ctx.matchedNodeIds}
          />
        )}
        {graphMode === "force" && (
          <ForceGraph
            data={filterByLevel(ctx.graphData ?? { nodes: [], edges: [] }, ctx.maxDisplayLevel)}
            selectedNodeId={ctx.selectedNode?.id}
            onNodeSelect={ctx.handleNodeSelect}
            width={ctx.graphFullscreen ? fsSize.width : graphSize.width}
            height={ctx.graphFullscreen ? fsSize.height : graphSize.height}
          />
        )}
        {graphMode === "dag" && (
          <DAGGraph
            data={filterByLevel(ctx.graphData ?? { nodes: [], edges: [] }, ctx.maxDisplayLevel)}
            selectedNodeId={ctx.selectedNode?.id}
            onNodeSelect={ctx.handleNodeSelect}
            activePath={ctx.activePath}
            width={graphSize.width}
            height={graphSize.height}
            searchQuery={ctx.graphSearch}
            matchedNodeIds={ctx.matchedNodeIds}
          />
        )}
      </div>
    </div>
  );

  // ── 全屏模式 ──
  if (ctx.graphFullscreen) {
    return (
      <div className="fixed inset-0 z-50 bg-[var(--color-bg)]">
        <button onClick={() => ctx.setGraphFullscreen(false)}
          className="absolute top-3 right-3 z-10 p-2 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors shadow-lg"
          title="退出全屏 (Esc)"><X size={16} /></button>
        {graphPanel}
      </div>
    );
  }

  // ── 左侧面板内容（桌面侧栏 / 移动端底部弹出） ──
  const leftPanelInner = (
    <>
      <div className="flex-shrink-0 border-b border-[var(--color-border)] px-4 pt-3 pb-0 flex items-center gap-4 overflow-x-auto">
        {tabBtn("dialogue", ctx.selectedNode ? "探索会话" : "学习对话", <MessageSquare size={12} />)}
        {tabBtn("practice", "练习", <Play size={12} />, ctx.practiceStats.total)}
        {tabBtn("notes", "笔记", <FileText size={12} />, ctx.relatedNotes.length)}
        {tabBtn("resources", "资源", <Sparkles size={12} />)}
        {tabBtn("projects", "项目", <Rocket size={12} />)}
      </div>

      <div className="flex-1 overflow-y-auto" onMouseUp={ctx.handleTextSelect}>
        <div className="p-4">
          {ctx.selectedNode && (
            <div className="mb-4 p-3 rounded-lg bg-[var(--color-accent)]/5 border border-[var(--color-accent)]/20 animate-fadeIn">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: getMasteryColor(ctx.selectedNode.mastery) }} />
                <span className="text-sm font-medium">{ctx.selectedNode.label}</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] ml-auto">{ctx.selectedNode.level}</span>
              </div>
              <div className="flex items-center gap-3 mt-2 text-[11px] text-[var(--color-text-muted)]">
                <span>掌握度: {Math.round(ctx.selectedNode.mastery * 100)}%</span>
                <button onClick={() => ctx.handleRequestExplain(ctx.selectedNode!.id)} className="text-[var(--color-accent)] hover:underline ml-auto">请求讲解 →</button>
              </div>
            </div>
          )}

          {ctx.leftTab === "dialogue" && (
            <div className="animate-fadeIn h-full">
              {ctx.cardLoading ? (
                <div className="flex items-center justify-center py-8"><Loader2 size={16} className="animate-spin text-[var(--color-text-muted)]" /></div>
              ) : ctx.selectedNode ? (
                <div className="h-[calc(100vh-280px)] min-h-[400px] -mx-4 -mb-4">
                  <TreeChatPanel
                    node={ctx.selectedNode}
                    partitionId={ctx.partitionId}
                    onNodeUpdated={() => ctx.loadGraph()}
                  />
                </div>
              ) : (
                <DialogueCardList cards={ctx.relatedCards} selectedNode={ctx.selectedNode} />
              )}
            </div>
          )}

          {ctx.leftTab === "practice" && (
            <PracticePanel nodeId={ctx.selectedNode?.id} nodeLabel={ctx.selectedNode?.label} onClose={() => ctx.setLeftTab("dialogue")} />
          )}

          {ctx.leftTab === "notes" && (
            <div className="space-y-3 animate-fadeIn">
              <p className="text-xs text-[var(--color-text-muted)]">所有高亮、自我解释、反思自动汇聚为个人笔记流</p>
              {ctx.relatedNotes.length === 0 ? (
                <div className="text-center py-6"><FileText size={24} className="mx-auto mb-2 text-[var(--color-text-muted)] opacity-30" /><p className="text-xs text-[var(--color-text-muted)]">选中文本后使用工具栏添加笔记</p></div>
              ) : (
                ctx.relatedNotes.map(note => (
                  <div key={note.id} className="p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] transition-all hover:border-[var(--color-border-hover)]">
                    <div className="flex items-center gap-1 mb-1">
                      {note.type === "explain" ? <Lightbulb size={10} className="text-[var(--color-accent)]" />
                        : note.type === "reflect" ? <Brain size={10} className="text-[var(--color-accent)]" />
                        : <StickyNote size={10} className="text-[var(--color-success)]" />}
                      <span className="text-[9px] text-[var(--color-text-muted)]">
                        {note.type === "explain" ? "自我解释" : note.type === "reflect" ? "反思" : "笔记"}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--color-text)] leading-relaxed">{note.content}</p>
                  </div>
                ))
              )}
              {ctx.relatedNotes.length > 0 && (
                <button onClick={() => ctx.setAggregateOpen(true)} className="flex items-center gap-1 text-xs text-[var(--color-accent)] hover:underline mx-auto"><Sparkles size={12} /> AI整理笔记</button>
              )}
            </div>
          )}

          {ctx.leftTab === "resources" && (
            <div className="space-y-3 animate-fadeIn">
              <p className="text-xs text-[var(--color-text-muted)]">
                {ctx.selectedNode ? `围绕「${ctx.selectedNode.label}」的学习资源` : "选择知识点查看关联资源"}
              </p>
              {ctx.selectedNode ? (
                <>
                  <div className="p-4 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-center">
                    <Sparkles size={24} className="mx-auto mb-2 text-[var(--color-accent)]" />
                    <p className="text-xs text-[var(--color-text-muted)]">视频讲解功能正在接入中</p>
                  </div>
                </>
              ) : (
                <div className="text-center py-6"><Sparkles size={24} className="mx-auto mb-2 text-[var(--color-text-muted)] opacity-30" /><p className="text-xs text-[var(--color-text-muted)]">点击图谱中的节点查看资源</p></div>
              )}
            </div>
          )}

          {ctx.leftTab === "projects" && (
            <ProjectsPanel open selectedNodeId={ctx.selectedNode?.id} selectedNodeLabel={ctx.selectedNode?.label} onClose={() => ctx.setLeftTab("dialogue")} />
          )}
        </div>
      </div>
    </>
  );

  // ── 移动端布局 ──
  if (isMobile) {
    return (
      <div className="flex flex-col h-full min-h-[600px]">
        <div className="flex-1 min-w-0 overflow-hidden relative">{graphPanel}</div>

        <div className="fixed bottom-20 right-4 z-40">
          <button onClick={() => setMobilePanelOpen(!mobilePanelOpen)}
            className="w-12 h-12 rounded-full bg-accent text-white shadow-lg flex items-center justify-center active:scale-95 transition-transform"
            style={{minWidth:44,minHeight:44}}>
            {mobilePanelOpen ? <X size={20} /> : <MessageCircle size={20} />}
          </button>
        </div>

        {mobilePanelOpen && (
          <>
            <div className="fixed inset-0 z-30 bg-black/30" onClick={() => setMobilePanelOpen(false)} />
            <div className="fixed bottom-0 left-0 right-0 z-30 bg-[var(--color-bg)] border-t border-[var(--color-border)] rounded-t-xl max-h-[75vh] flex flex-col animate-slideUp shadow-2xl">
              <div className="flex flex-col overflow-hidden">
                {leftPanelInner}
              </div>

              {hasNode && (
                <div className="flex-shrink-0 border-t border-[var(--color-border)] p-4">
                  <NodeDetailPanel
                    node={ctx.selectedNode!}
                    partitionId={ctx.partitionId}
                    onClose={() => ctx.setSelectedNode(null)}
                    onNodeUpdated={() => ctx.loadGraph()}
                    onStartPractice={ctx.handleStartPractice}
                    onRequestExplain={ctx.handleRequestExplain}
                  />
                </div>
              )}
            </div>
          </>
        )}

        {addNodeOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
            <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-5 w-80 space-y-3 shadow-xl">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-[var(--color-text)]">添加知识节点</h3>
                <button onClick={() => setAddNodeOpen(false)}><X size={14} className="text-[var(--color-text-muted)]" /></button>
              </div>
              <input value={newNodeLabel} onChange={e => setNewNodeLabel(e.target.value)}
                placeholder="节点名称" autoFocus
                className="w-full px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] rounded-lg focus:outline-none focus:border-[var(--color-accent)]"
                onKeyDown={e => e.key === "Enter" && handleAddNode()} />
              <select value={newNodeParent} onChange={e => setNewNodeParent(e.target.value)}
                className="w-full px-3 py-2 text-xs bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] rounded-lg focus:outline-none focus:border-[var(--color-accent)]">
                <option value="">无父节点（根节点）</option>
                {ctx.graphData?.nodes?.map(n => (
                  <option key={n.id} value={n.id}>{n.label}</option>
                ))}
              </select>
              <div className="flex gap-2 justify-end">
                <button onClick={() => setAddNodeOpen(false)} className="px-3 py-1.5 text-xs border border-[var(--color-border)] rounded-lg text-[var(--color-text-muted)]">取消</button>
                <button onClick={handleAddNode} disabled={addNodeLoading || !newNodeLabel.trim()}
                  className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white rounded-lg hover:opacity-90 disabled:opacity-50">
                  {addNodeLoading ? <Loader2 size={11} className="animate-spin" /> : "添加"}
                </button>
              </div>
            </div>
          </div>
        )}

        <DeepReadToolbar position={ctx.toolbar.position} visible={ctx.toolbar.visible}
          selectedText={ctx.toolbar.text} level={ctx.toolbar.level as any}
          onHighlight={() => {}} onQuote={() => {}} onExplain={ctx.handleExplain}
          onNote={ctx.handleNote} onClose={() => ctx.setToolbar({ ...ctx.toolbar, visible: false })} />
        <ExplainModal open={ctx.explainModal} originalText={ctx.selectedText}
          onClose={() => ctx.setExplainModal(false)} onSave={ctx.handleExplainSave} />
        <NoteSidebar open={ctx.noteSidebar} onClose={() => ctx.setNoteSidebar(false)}
          sourceText={ctx.selectedText} nodeId={ctx.selectedNode?.id} nodeLabel={ctx.selectedNode?.label} />
        <ReflectionModal open={ctx.reflectionOpen} trigger={ctx.reflectionTrigger}
          relatedNodes={ctx.selectedNode ? [ctx.selectedNode.label] : []}
          context={ctx.selectedNode ? `围绕 "${ctx.selectedNode.label}" 的当前学习对话` : undefined}
          onClose={() => ctx.setReflectionOpen(false)} onSave={ctx.handleReflectionSave} />
        {ctx.selectedNode && (
          <GoalSettingModal open={ctx.goalModalOpen} nodeId={ctx.selectedNode.id}
            nodeLabel={ctx.selectedNode.label} currentMastery={ctx.selectedNode.mastery}
            onClose={() => ctx.setGoalModalOpen(false)} onSaved={() => ctx.loadGraph()} />
        )}
        <AggregateNotesModal open={ctx.aggregateOpen}
          nodeIds={ctx.selectedNode ? [ctx.selectedNode.id] : undefined}
          onClose={() => ctx.setAggregateOpen(false)} />
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-[600px] transition-all duration-200">
      {/* 左侧面板 */}
      <div className="flex flex-col overflow-hidden border-r border-[var(--color-border)]"
        style={{ width: hasNode ? "calc(50% - 160px)" : "50%" }}>
        {leftPanelInner}
      </div>

      {/* 图谱面板 */}
      <div className="flex-1 min-w-0 overflow-hidden relative">{graphPanel}</div>

      {/* 右侧详情面板 — 使用 NodeDetailPanel（编辑/AI扩充/AI对话） */}
      {hasNode && (
        <div className="flex-shrink-0 w-[320px] animate-slideIn">
          <NodeDetailPanel
            node={ctx.selectedNode!}
            partitionId={ctx.partitionId}
            onClose={() => ctx.setSelectedNode(null)}
            onNodeUpdated={() => ctx.loadGraph()}
            onStartPractice={ctx.handleStartPractice}
            onRequestExplain={ctx.handleRequestExplain}
          />
        </div>
      )}

      {/* 添加节点弹窗 */}
      {addNodeOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
          <div className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-xl p-5 w-80 space-y-3 shadow-xl">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-[var(--color-text)]">添加知识节点</h3>
              <button onClick={() => setAddNodeOpen(false)}><X size={14} className="text-[var(--color-text-muted)]" /></button>
            </div>
            <input value={newNodeLabel} onChange={e => setNewNodeLabel(e.target.value)}
              placeholder="节点名称" autoFocus
              className="w-full px-3 py-2 text-sm bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] rounded-lg focus:outline-none focus:border-[var(--color-accent)]"
              onKeyDown={e => e.key === "Enter" && handleAddNode()} />
            <select value={newNodeParent} onChange={e => setNewNodeParent(e.target.value)}
              className="w-full px-3 py-2 text-xs bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] rounded-lg focus:outline-none focus:border-[var(--color-accent)]">
              <option value="">无父节点（根节点）</option>
              {ctx.graphData?.nodes?.map(n => (
                <option key={n.id} value={n.id}>{n.label}</option>
              ))}
            </select>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setAddNodeOpen(false)} className="px-3 py-1.5 text-xs border border-[var(--color-border)] rounded-lg text-[var(--color-text-muted)]">取消</button>
              <button onClick={handleAddNode} disabled={addNodeLoading || !newNodeLabel.trim()}
                className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white rounded-lg hover:opacity-90 disabled:opacity-50">
                {addNodeLoading ? <Loader2 size={11} className="animate-spin" /> : "添加"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 浮动组件 */}
      <DeepReadToolbar position={ctx.toolbar.position} visible={ctx.toolbar.visible}
        selectedText={ctx.toolbar.text} level={ctx.toolbar.level as any}
        onHighlight={() => {}} onQuote={() => {}} onExplain={ctx.handleExplain}
        onNote={ctx.handleNote} onClose={() => ctx.setToolbar({ ...ctx.toolbar, visible: false })} />
      <ExplainModal open={ctx.explainModal} originalText={ctx.selectedText}
        onClose={() => ctx.setExplainModal(false)} onSave={ctx.handleExplainSave} />
      <NoteSidebar open={ctx.noteSidebar} onClose={() => ctx.setNoteSidebar(false)}
        sourceText={ctx.selectedText} nodeId={ctx.selectedNode?.id} nodeLabel={ctx.selectedNode?.label} />
      <ReflectionModal open={ctx.reflectionOpen} trigger={ctx.reflectionTrigger}
        relatedNodes={ctx.selectedNode ? [ctx.selectedNode.label] : []}
        context={ctx.selectedNode ? `围绕 "${ctx.selectedNode.label}" 的当前学习对话` : undefined}
        onClose={() => ctx.setReflectionOpen(false)} onSave={ctx.handleReflectionSave} />
      {ctx.selectedNode && (
        <GoalSettingModal open={ctx.goalModalOpen} nodeId={ctx.selectedNode.id}
          nodeLabel={ctx.selectedNode.label} currentMastery={ctx.selectedNode.mastery}
          onClose={() => ctx.setGoalModalOpen(false)} onSaved={() => ctx.loadGraph()} />
      )}
      <AggregateNotesModal open={ctx.aggregateOpen}
        nodeIds={ctx.selectedNode ? [ctx.selectedNode.id] : undefined}
        onClose={() => ctx.setAggregateOpen(false)} />
    </div>
  );
}

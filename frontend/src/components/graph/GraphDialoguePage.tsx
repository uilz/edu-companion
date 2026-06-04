"use client";

import React, { useMemo } from "react";
import {
  Loader2, MessageSquare, FileText, Brain, Sparkles, Rocket,
  Play, StickyNote, Lightbulb, Network, Focus, ChevronLeft, ChevronRight,
  GitGraph, BookOpen, RefreshCw, Search, X,
} from "lucide-react";
import dynamic from "next/dynamic";
import { getMasteryColor, getTrendIcon } from "@/lib/graph-types";
import { useGraphDialogue } from "@/hooks/useGraphDialogue";
import type { UseGraphDialogueReturn } from "@/hooks/useGraphDialogue";
import type { GraphData } from "@/lib/graph-types";
import PracticePanel from "@/components/practice/PracticePanel";

// ── 层级筛选：只显示 <= maxLevel 的节点及其关联边 ──
const LEVEL_ORDER: Record<string, number> = {
  partition: 0, domain: 1, topic: 2, conversation: 3, concept: 4, atom: 5,
};
function filterByLevel(data: GraphData | null, maxLevel: string | undefined): GraphData | null {
  if (!data || !maxLevel) return data;
  const maxIdx = LEVEL_ORDER[maxLevel] ?? 99;
  const keep = data.nodes.filter(n => (LEVEL_ORDER[n.level] ?? 99) <= maxIdx);
  const keepIds = new Set(keep.map(n => n.id));
  return { nodes: keep, edges: data.edges.filter(e => keepIds.has(e.source) && keepIds.has(e.target)) };
}

// ── 动态导入模态框组件 ──
const KnowledgeCardNode = dynamic(() => import("@/components/graph/KnowledgeCardNode"), { ssr: false });
const FocusGraph = dynamic(() => import("@/components/graph/FocusGraph"), { ssr: false });
const ForceGraph = dynamic(() => import("@/components/graph/ForceGraph"), { ssr: false });
const DeepReadToolbar = dynamic(() => import("@/components/graph/DeepReadToolbar"), { ssr: false });
const ExplainModal = dynamic(() => import("@/components/graph/ExplainModal"), { ssr: false });
const NoteSidebar = dynamic(() => import("@/components/graph/NoteSidebar"), { ssr: false });
const ReflectionModal = dynamic(() => import("@/components/graph/ReflectionModal"), { ssr: false });
const GoalSettingModal = dynamic(() => import("@/components/graph/GoalSettingModal"), { ssr: false });
const AggregateNotesModal = dynamic(() => import("@/components/graph/AggregateNotesModal"), { ssr: false });
const ProjectsPanel = dynamic(() => import("@/components/graph/ProjectsPanel"), { ssr: false });
const DialogueCardList = dynamic(() => import("@/components/graph/DialogueCardList"), { ssr: false });

export default function GraphDialoguePage() {
  const ctx = useGraphDialogue();

  // ── 加载状态 ──
  if (ctx.loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
        <span className="ml-2 text-sm text-[var(--color-text-muted)]">加载知识图谱…</span>
      </div>
    );
  }

  if (ctx.error) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <p className="text-sm text-[var(--color-error)]">加载失败: {ctx.error}</p>
        <button onClick={ctx.loadGraph} className="ml-3 flex items-center gap-1 text-xs text-[var(--color-accent)] hover:underline">
          <RefreshCw size={12} />重试
        </button>
      </div>
    );
  }

  return <GraphDialogueLayout ctx={ctx} />;
}

// ── 主布局 ──
function GraphDialogueLayout({ ctx }: { ctx: UseGraphDialogueReturn }) {
  const hasNode = !!ctx.selectedNode;

  const tabBtn = (key: string, label: string, icon: React.ReactNode, badge?: number) => (
    <button onClick={() => ctx.setLeftTab(key as any)}
      className={`flex items-center gap-1.5 pb-2 text-xs font-medium border-b-2 transition-colors ${
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

  const graphPanel = (
    <div className="relative w-full h-full flex flex-col">
      {/* 顶部栏：模式切换 + 搜索 */}
      <div className="flex-shrink-0 flex items-center gap-2 px-3 py-2 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-1 bg-[var(--color-surface)] rounded-lg border border-[var(--color-border)] p-0.5">
          <button onClick={() => ctx.setGraphMode("mindmap")}
            className={`flex items-center gap-1 px-2 py-1 rounded-md text-[11px] transition-colors ${
              ctx.graphMode === "mindmap" ? "bg-[var(--color-accent)] text-white font-medium" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}><GitGraph size={13} />思维导图</button>
          <button onClick={() => ctx.setGraphMode("force")}
            className={`flex items-center gap-1 px-2 py-1 rounded-md text-[11px] transition-colors ${
              ctx.graphMode === "force" ? "bg-[var(--color-accent)] text-white font-medium" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            }`}><Network size={13} />力导向</button>
        </div>

        <div className="flex-1 max-w-[240px] relative">
          <input value={ctx.graphSearch} onChange={(e) => ctx.setGraphSearch(e.target.value)}
            placeholder="搜索节点..."
            className="w-full pl-7 pr-2 py-1 text-[11px] rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors"
          />
          <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
          {ctx.graphSearch && (
            <button onClick={() => ctx.setGraphSearch("")}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"><X size={12} /></button>
          )}
        </div>
        {ctx.graphSearch && ctx.matchedNodeIds.length > 0 && (
          <span className="text-[10px] text-[var(--color-text-muted)]">{ctx.matchedNodeIds.length} 个匹配</span>
        )}

        <div className="flex-1" />
        <button onClick={() => ctx.setGoalModalOpen(true)}
          className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors" title="设定目标"><BookOpen size={14} /></button>
        <button onClick={() => ctx.setGraphFullscreen(!ctx.graphFullscreen)}
          className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
          title={ctx.graphFullscreen ? "退出全屏" : "全屏"}><Focus size={14} /></button>
      </div>

      {/* 层级筛选条 */}
      {ctx.graphMode === "mindmap" && (
        <div className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 border-b border-[var(--color-border)] bg-[var(--color-page-secondary)]">
          <span className="text-[10px] text-[var(--color-text-muted)] font-medium mr-1">显示层级：</span>
          {(ctx.availableLevels || ["all","partition","domain","topic","concept","atom"]).map((lv: string) => {
            const label: Record<string,string> = { all:"全部", partition:"分区", domain:"领域", topic:"专题", conversation:"会话", concept:"概念", atom:"知识点" };
            const active = lv === "all" ? !ctx.maxDisplayLevel : ctx.maxDisplayLevel === lv;
            return (
              <button key={lv} onClick={() => ctx.setMaxDisplayLevel(lv === "all" ? undefined : lv)}
                className={`px-2 py-0.5 rounded text-[10px] font-medium transition-colors ${
                  active ? "bg-[var(--color-accent)] text-white" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
                }`}>{label[lv] || lv}</button>
            );
          })}
        </div>
      )}

      {/* 图谱 */}
      <div className="flex-1 overflow-hidden relative">
        {ctx.graphMode === "mindmap" ? (
          <FocusGraph
            data={filterByLevel(ctx.graphData, ctx.maxDisplayLevel) || { nodes: [], edges: [] }}
            selectedNodeId={ctx.selectedNode?.id}
            onNodeSelect={ctx.handleNodeSelect}
            activePath={ctx.activePath}
            width={ctx.graphFullscreen ? window.innerWidth - 40 : 600}
            height={ctx.graphFullscreen ? window.innerHeight - 40 : 500}
            searchQuery={ctx.graphSearch}
            matchedNodeIds={ctx.matchedNodeIds}
          />
        ) : (
          <ForceGraph
            data={{
              nodes: (ctx.graphData?.nodes || []).filter((n) => new Set(["partition", "domain", "topic"]).has(n.level)),
              edges: (() => {
                const validIds = new Set((ctx.graphData?.nodes || []).filter((n) => new Set(["partition", "domain", "topic"]).has(n.level)).map(n => n.id));
                return (ctx.graphData?.edges || []).filter((e) => validIds.has(e.source) && validIds.has(e.target));
              })(),
            }}
            selectedNodeId={ctx.selectedNode?.id}
            onNodeSelect={ctx.handleNodeSelect}
            width={600}
            height={500}
          />
        )}
      </div>
    </div>
  );

  // ── 全屏模式 ──
  if (ctx.graphFullscreen) {
    return (
      <div className="fixed inset-0 z-50 bg-[var(--color-bg)]">{graphPanel}</div>
    );
  }

  return (
    <div ref={ctx.containerRef} className="flex h-full min-h-[600px]">
      {/* 左侧面板 */}
      <div className="flex flex-col overflow-hidden border-r border-[var(--color-border)]"
        style={{ width: `calc(${ctx.splitPercent}% - ${hasNode ? 320 : 0}px)` }}>
        <div className="flex-shrink-0 border-b border-[var(--color-border)] px-4 pt-3 pb-0 flex items-center gap-4 overflow-x-auto">
          {tabBtn("dialogue", "学习对话", <MessageSquare size={12} />)}
          {tabBtn("practice", "练习", <Play size={12} />, ctx.practiceStats.total)}
          {tabBtn("notes", "笔记", <FileText size={12} />, ctx.relatedNotes.length)}
          {tabBtn("resources", "资源", <Sparkles size={12} />)}
          {tabBtn("projects", "项目", <Rocket size={12} />)}
        </div>

        <div className="flex-1 overflow-y-auto" onMouseUp={ctx.handleTextSelect}>
          <div className="p-4">
            {/* 选中节点摘要 */}
            {ctx.selectedNode && (
              <div className="mb-4 p-3 rounded-lg bg-[var(--color-accent)]/5 border border-[var(--color-accent)]/20">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: getMasteryColor(ctx.selectedNode.mastery) }} />
                  <span className="text-sm font-medium">{ctx.selectedNode.emoji} {ctx.selectedNode.label}</span>
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]">{ctx.selectedNode.level}</span>
                </div>
                <div className="flex items-center gap-3 mt-2 text-[11px] text-[var(--color-text-muted)]">
                  <span>掌握度: {Math.round(ctx.selectedNode.mastery * 100)}%</span>
                  <span>趋势: {getTrendIcon(ctx.selectedNode.trend)}</span>
                  <button onClick={() => ctx.setGoalModalOpen(true)} className="text-[var(--color-accent)] hover:underline ml-auto">设定目标 →</button>
                  <button onClick={() => ctx.handleRequestExplain(ctx.selectedNode!.id)} className="text-[var(--color-accent)] hover:underline">请求讲解 →</button>
                </div>
              </div>
            )}

            {/* 对话 */}
            {ctx.leftTab === "dialogue" && (
              <div>
                {ctx.cardLoading ? (
                  <div className="flex items-center justify-center py-8"><Loader2 size={16} className="animate-spin text-[var(--color-text-muted)]" /></div>
                ) : ctx.selectedNode ? (
                  <DialogueCardList cards={ctx.relatedCards} selectedNode={ctx.selectedNode} />
                ) : (
                  <div className="text-center py-8"><p className="text-xs text-[var(--color-text-muted)]">点击图谱中的节点查看关联对话</p></div>
                )}
              </div>
            )}

            {/* 练习 */}
            {ctx.leftTab === "practice" && (
              <PracticePanel
                nodeId={ctx.selectedNode?.id}
                nodeLabel={ctx.selectedNode?.label}
                onClose={() => ctx.setLeftTab("dialogue")}
              />
            )}

            {/* 笔记 */}
            {ctx.leftTab === "notes" && (
              <div className="space-y-3">
                <p className="text-xs text-[var(--color-text-muted)]">所有高亮、自我解释、反思自动汇聚为个人笔记流</p>
                {ctx.relatedNotes.length === 0 ? (
                  <p className="text-xs text-[var(--color-text-muted)] text-center py-6">选中文本后使用工具栏添加笔记</p>
                ) : (
                  ctx.relatedNotes.map((note) => (
                    <div key={note.id} className="p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">
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
                <button onClick={() => ctx.setAggregateOpen(true)}
                  className="flex items-center gap-1 text-xs text-[var(--color-accent)] hover:underline mx-auto">
                  <Sparkles size={12} /> AI整理笔记
                </button>
              </div>
            )}

            {/* 资源 */}
            {ctx.leftTab === "resources" && (
              <div className="space-y-3">
                <p className="text-xs text-[var(--color-text-muted)]">
                  {ctx.selectedNode ? `围绕「${ctx.selectedNode.label}」的学习资源` : "选择知识点查看关联资源"}
                </p>
                {ctx.selectedNode ? (
                  <>
                    <div className="p-4 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] text-center">
                      <Sparkles size={24} className="mx-auto mb-2 text-[var(--color-accent)]" />
                      <p className="text-xs text-[var(--color-text-muted)]">视频讲解功能正在接入中</p>
                      <p className="text-[10px] text-[var(--color-text-muted)] mt-1">后续支持：B站搜索 · AI生成讲解视频 · 习题视频解析</p>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <button className="flex items-center gap-2 p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-accent)]/30 transition-colors">
                        <BookOpen size={14} className="text-[var(--color-accent)]" /><span className="text-xs text-[var(--color-text)]">搜索B站</span>
                      </button>
                      <button className="flex items-center gap-2 p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-accent)]/30 transition-colors">
                        <Rocket size={14} className="text-[var(--color-accent)]" /><span className="text-xs text-[var(--color-text)]">推荐教材</span>
                      </button>
                    </div>
                  </>
                ) : (
                  <p className="text-xs text-[var(--color-text-muted)] text-center py-6">点击图谱中的节点查看资源</p>
                )}
              </div>
            )}

            {/* 项目 */}
            {ctx.leftTab === "projects" && (
              <ProjectsPanel open selectedNodeId={ctx.selectedNode?.id}
                selectedNodeLabel={ctx.selectedNode?.label} onClose={() => ctx.setLeftTab("dialogue")} />
            )}
          </div>
        </div>
      </div>

      {/* 图谱面板 */}
      <div className="flex-1 min-w-0 overflow-hidden relative">{graphPanel}</div>

      {/* 知识卡侧栏 */}
      {hasNode && (
        <div className="flex-shrink-0 border-l border-[var(--color-border)]" style={{ width: 320 }}>
          <KnowledgeCardNode node={ctx.selectedNode!}
            relatedCards={ctx.relatedCards}
            relatedNotes={ctx.relatedNotes.map((n) => ({ id: n.id, text: n.content, type: n.type }))}
            childNodes={ctx.childNodes}
            onClose={() => ctx.setSelectedNode(null)}
            onStartPractice={ctx.handleStartPractice}
            onRequestExplain={ctx.handleRequestExplain}
            onMarkMastered={ctx.handleMarkMastered}
            onMarkQuestion={ctx.handleMarkQuestion}
          />
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

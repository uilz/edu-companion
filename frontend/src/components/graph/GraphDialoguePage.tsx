"use client";

import React, { useState, useEffect, useCallback } from "react";
import { fetchGraphData } from "@/lib/graph-api";
import type { GraphData, GraphNode, DialogueCardInfo } from "@/lib/graph-types";
import { getMasteryColor, getTrendIcon } from "@/lib/graph-types";
import ForceGraph from "@/components/graph/ForceGraph";
import MindMapGraph from "@/components/graph/MindMapGraph";
import DialogueCardList from "@/components/graph/DialogueCardList";
import DeepReadToolbar from "@/components/graph/DeepReadToolbar";
import ExplainModal from "@/components/graph/ExplainModal";
import NoteSidebar from "@/components/graph/NoteSidebar";
import FocusMode from "@/components/graph/FocusMode";
import KnowledgeCardNode from "@/components/graph/KnowledgeCardNode";
import ReflectionModal from "@/components/graph/ReflectionModal";
import {
  GitGraph,
  Network,
  Maximize2,
  Minimize2,
  Loader2,
  StickyNote,
  Focus,
  Brain,
  MessageSquare,
  FileText,
  Lightbulb,
} from "lucide-react";

type GraphMode = "force" | "mindmap";

// Mock dialogue cards — will be replaced with real API data
const MOCK_CARDS: DialogueCardInfo[] = [
  {
    id: "c1",
    question: "什么是导数？",
    summary: "导数描述函数在某一点的变化率，即函数值随自变量变化的瞬时速度。从几何上看，导数是函数曲线上某点切线的斜率。",
    knowledgeNodes: ["导数", "变化率"],
    timestamp: "2026-06-01 10:30",
  },
  {
    id: "c2",
    question: "导数的几何意义是什么？",
    summary: "函数f(x)在点x₀处的导数f'(x₀)等于曲线y=f(x)在点(x₀, f(x₀))处切线的斜率。这是理解导数最直观的方式。",
    knowledgeNodes: ["导数", "切线"],
    timestamp: "2026-06-01 10:32",
  },
  {
    id: "c3",
    question: "链式法则怎么理解？",
    summary: "链式法则用于求复合函数的导数。如果y=f(u)且u=g(x)，则dy/dx = dy/du · du/dx。",
    knowledgeNodes: ["链式法则", "导数"],
    timestamp: "2026-06-01 10:35",
  },
  {
    id: "c4",
    question: "高阶导数有什么实际应用？",
    summary: "二阶导数描述加速度，在物理中用于描述变速运动。在经济学中，二阶导数可用于判断函数的凹凸性。",
    knowledgeNodes: ["高阶导数", "加速度"],
    timestamp: "2026-06-01 10:40",
  },
];

// Mock notes
const MOCK_NOTES = [
  { id: "n1", text: "导数就是瞬间的变化率，好比车速表上显示的瞬时速度，不是平均速度。", type: "explain" },
  { id: "n2", text: "链式法则就像剥洋葱，一层一层从外到内求导。", type: "explain" },
  { id: "n3", text: "需要再练习一下高阶导数的物理应用题目", type: "note" },
];

export default function GraphDialoguePage() {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [graphMode, setGraphMode] = useState<GraphMode>("mindmap");
  const [graphFullscreen, setGraphFullscreen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Focus mode state
  const [focusMode, setFocusMode] = useState(false);

  // Reflection modal state
  const [reflectionOpen, setReflectionOpen] = useState(false);
  const [reflectionTrigger, setReflectionTrigger] = useState<"practice_done" | "node_mastered" | "cognitive_conflict" | "weekly_review">("practice_done");

  // Deep reading state
  const [toolbar, setToolbar] = useState<{
    visible: boolean;
    position: { x: number; y: number };
    text: string;
    level: "sentence" | "paragraph" | "all";
  }>({ visible: false, position: { x: 0, y: 0 }, text: "", level: "sentence" });

  const [explainModal, setExplainModal] = useState(false);
  const [noteSidebar, setNoteSidebar] = useState(false);
  const [selectedText, setSelectedText] = useState("");

  // Tabs for left pane
  const [leftTab, setLeftTab] = useState<"dialogue" | "notes">("dialogue");

  // Fetch graph data
  useEffect(() => {
    setLoading(true);
    fetchGraphData()
      .then((data) => {
        setGraphData(data);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleNodeSelect = useCallback((node: GraphNode) => {
    setSelectedNode(node);
    // If mastery >= 0.8, consider triggering reflection
    if (node.mastery >= 0.8 && node.trend === "ascending") {
      setReflectionTrigger("node_mastered");
      setReflectionOpen(true);
    }
  }, []);

  // Handle text selection in the dialogue area
  const handleTextSelect = useCallback(() => {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !sel.toString().trim()) {
      setToolbar((p) => ({ ...p, visible: false }));
      return;
    }

    const text = sel.toString().trim();
    const range = sel.getRangeAt(0);
    const rect = range.getBoundingClientRect();
    const level: "sentence" | "paragraph" | "all" =
      text.length < 50 ? "sentence" : text.length < 200 ? "paragraph" : "all";

    setSelectedText(text);
    setToolbar({
      visible: true,
      position: { x: rect.left + rect.width / 2, y: rect.top },
      text,
      level,
    });
  }, []);

  const handleToolbarClose = useCallback(() => {
    setToolbar((p) => ({ ...p, visible: false }));
    window.getSelection()?.removeAllRanges();
  }, []);

  const handleExplain = useCallback(() => {
    setToolbar((p) => ({ ...p, visible: false }));
    setExplainModal(true);
  }, []);

  const handleNote = useCallback(() => {
    setToolbar((p) => ({ ...p, visible: false }));
    setNoteSidebar(true);
  }, []);

  const handleHighlight = useCallback(() => {
    setToolbar((p) => ({ ...p, visible: false }));
    window.getSelection()?.removeAllRanges();
  }, []);

  const handleQuote = useCallback(() => {
    setToolbar((p) => ({ ...p, visible: false }));
    navigator.clipboard.writeText(selectedText);
    window.getSelection()?.removeAllRanges();
  }, [selectedText]);

  const handleExplainSave = useCallback((explanation: string) => {
    console.log("Self-explanation saved:", explanation);
  }, []);

  // KnowledgeCard actions
  const handleStartPractice = useCallback((nodeId: string) => {
    console.log("Start practice for node:", nodeId);
  }, []);

  const handleRequestExplain = useCallback((nodeId: string) => {
    console.log("Request explain for node:", nodeId);
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

  // Reflection save
  const handleReflectionSave = useCallback((reflection: any) => {
    console.log("Reflection saved:", reflection);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
        <span className="ml-2 text-sm text-[var(--color-text-muted)]">加载知识图谱…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full min-h-[400px]">
        <p className="text-sm text-[var(--color-error)]">加载失败: {error}</p>
      </div>
    );
  }

  // ----- Graph panel (right side) -----
  const graphPanel = (
    <div className="relative w-full h-full">
      {/* Graph mode switcher */}
      <div className="absolute top-3 left-3 z-10 flex items-center gap-1 bg-[var(--color-surface)]/90 backdrop-blur-sm rounded-lg border border-[var(--color-border)] p-0.5 shadow-sm">
        <button
          onClick={() => setGraphMode("mindmap")}
          className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs transition-colors ${
            graphMode === "mindmap"
              ? "bg-[var(--color-accent)] text-white"
              : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          }`}
        >
          <GitGraph size={14} />
          思维导图
        </button>
        <button
          onClick={() => setGraphMode("force")}
          className={`flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs transition-colors ${
            graphMode === "force"
              ? "bg-[var(--color-accent)] text-white"
              : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          }`}
        >
          <Network size={14} />
          力导向
        </button>
      </div>

      {/* Top-right controls */}
      <div className="absolute top-3 right-3 z-10 flex items-center gap-1">
        <button
          onClick={() => setNoteSidebar(true)}
          className="p-1.5 rounded-md bg-[var(--color-surface)]/80 backdrop-blur-sm border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-success)] transition-colors"
          title="笔记"
        >
          <StickyNote size={14} />
        </button>
        <button
          onClick={() => setGraphFullscreen(!graphFullscreen)}
          className="p-1.5 rounded-md bg-[var(--color-surface)]/80 backdrop-blur-sm border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
          title={graphFullscreen ? "退出全屏" : "全屏"}
        >
          {graphFullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
        </button>
      </div>

      {/* Graph canvas */}
      <div className="w-full h-full pt-2">
        {graphMode === "force" ? (
          <ForceGraph
            data={graphData || { nodes: [], edges: [] }}
            selectedNodeId={selectedNode?.id}
            onNodeSelect={handleNodeSelect}
            width={graphFullscreen ? window.innerWidth - 40 : 600}
            height={graphFullscreen ? window.innerHeight - 40 : 500}
          />
        ) : (
          <MindMapGraph
            data={graphData || { nodes: [], edges: [] }}
            selectedNodeId={selectedNode?.id}
            onNodeSelect={handleNodeSelect}
            width={600}
            height={500}
          />
        )}
      </div>

      {/* KnowledgeCard: bottom overlay when node selected in normal mode */}
      {selectedNode && !graphFullscreen && (
        <div className="absolute bottom-3 left-3 right-3 z-10 max-h-[360px] overflow-y-auto rounded-xl shadow-lg border border-[var(--color-border)]/80">
          <div className="max-h-[360px] overflow-y-auto">
            <KnowledgeCardNode
              node={selectedNode}
              relatedCards={MOCK_CARDS.filter((c) =>
                c.knowledgeNodes.some((kn) =>
                  selectedNode.label.includes(kn) || kn.includes(selectedNode.label)
                )
              )}
              relatedNotes={MOCK_NOTES}
              onClose={() => setSelectedNode(null)}
              onStartPractice={handleStartPractice}
              onRequestExplain={handleRequestExplain}
              onMarkMastered={handleMarkMastered}
              onMarkQuestion={handleMarkQuestion}
            />
          </div>
        </div>
      )}
    </div>
  );

  // Fullscreen graph mode
  if (graphFullscreen) {
    return (
      <div className="fixed inset-0 z-50 bg-[var(--color-bg)]">
        {graphPanel}
      </div>
    );
  }

  // ----- Main dual-pane content -----
  const mainContent = (
    <div className="flex h-full min-h-[600px]">
      {/* Deep Reading Toolbar (floating) */}
      <DeepReadToolbar
        position={toolbar.position}
        visible={toolbar.visible}
        selectedText={toolbar.text}
        level={toolbar.level}
        onHighlight={handleHighlight}
        onQuote={handleQuote}
        onExplain={handleExplain}
        onNote={handleNote}
        onClose={handleToolbarClose}
      />

      {/* Explain Modal */}
      <ExplainModal
        open={explainModal}
        originalText={selectedText}
        onClose={() => setExplainModal(false)}
        onSave={handleExplainSave}
      />

      {/* Note Sidebar */}
      <NoteSidebar
        open={noteSidebar}
        onClose={() => setNoteSidebar(false)}
        sourceText={selectedText}
        nodeId={selectedNode?.id}
        nodeLabel={selectedNode?.label}
      />

      {/* Reflection Modal */}
      <ReflectionModal
        open={reflectionOpen}
        trigger={reflectionTrigger}
        relatedNodes={selectedNode ? [selectedNode.label] : []}
        context={selectedNode ? `围绕 "${selectedNode.label}" 的当前学习对话` : undefined}
        onClose={() => setReflectionOpen(false)}
        onSave={handleReflectionSave}
      />

      {/* Left pane: Conversation dialogue */}
      <div className="flex-1 border-r border-[var(--color-border)] overflow-y-auto" onMouseUp={handleTextSelect}>
        <div className="p-4">
          {/* Tab switcher */}
          <div className="flex items-center gap-4 mb-4 border-b border-[var(--color-border)]/50">
            <button
              onClick={() => setLeftTab("dialogue")}
              className={`flex items-center gap-1.5 pb-2 text-xs font-medium border-b-2 transition-colors ${
                leftTab === "dialogue"
                  ? "text-[var(--color-accent)] border-[var(--color-accent)]"
                  : "text-[var(--color-text-muted)] border-transparent hover:text-[var(--color-text)]"
              }`}
            >
              <MessageSquare size={12} />
              学习对话
            </button>
            <button
              onClick={() => setLeftTab("notes")}
              className={`flex items-center gap-1.5 pb-2 text-xs font-medium border-b-2 transition-colors ${
                leftTab === "notes"
                  ? "text-[var(--color-accent)] border-[var(--color-accent)]"
                  : "text-[var(--color-text-muted)] border-transparent hover:text-[var(--color-text)]"
              }`}
            >
              <FileText size={12} />
              笔记流
            </button>
            <button
              onClick={() => setReflectionOpen(true)}
              className={`flex items-center gap-1.5 pb-2 text-xs font-medium border-b-2 transition-colors ${
                reflectionOpen
                  ? "text-[var(--color-accent)] border-[var(--color-accent)]"
                  : "text-[var(--color-text-muted)] border-transparent hover:text-[var(--color-text)]"
              }`}
            >
              <Brain size={12} />
              反思
            </button>
          </div>

          {/* Tab content: dialogue cards */}
          {leftTab === "dialogue" && (
            <>
              {/* Selected node info card (compact) */}
              {selectedNode ? (
                <div className="mb-4 p-3 rounded-lg bg-[var(--color-accent)]/5 border border-[var(--color-accent)]/20">
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full"
                      style={{ backgroundColor: getMasteryColor(selectedNode.mastery) }}
                    />
                    <span className="text-sm font-medium">{selectedNode.emoji} {selectedNode.label}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[var(--color-surface-hover)] text-[var(--color-text-muted)]">
                      {selectedNode.level}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 mt-2 text-[11px] text-[var(--color-text-muted)]">
                    <span>掌握度: {Math.round(selectedNode.mastery * 100)}%</span>
                    <span>趋势: {getTrendIcon(selectedNode.trend)}</span>
                    <button
                      onClick={handleRequestExplain.bind(null, selectedNode.id)}
                      className="ml-auto text-[var(--color-accent)] hover:underline"
                    >
                      请求讲解 →
                    </button>
                  </div>
                </div>
              ) : null}

              {/* Dialogue cards */}
              <DialogueCardList
                cards={MOCK_CARDS}
                selectedNode={selectedNode}
              />
            </>
          )}

          {/* Tab content: notes flow */}
          {leftTab === "notes" && (
            <div className="space-y-3">
              <p className="text-xs text-[var(--color-text-muted)]">
                所有高亮、自我解释、反思自动汇聚为个人笔记流
              </p>
              {MOCK_NOTES.length === 0 ? (
                <p className="text-xs text-[var(--color-text-muted)] text-center py-6">
                  暂无笔记，选中文本后使用工具栏添加
                </p>
              ) : (
                MOCK_NOTES.map((note) => (
                  <div
                    key={note.id}
                    className="p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]"
                  >
                    <div className="flex items-center gap-1 mb-1">
                      {note.type === "explain" ? (
                        <Lightbulb size={10} className="text-[var(--color-accent)]" />
                      ) : (
                        <StickyNote size={10} className="text-[var(--color-success)]" />
                      )}
                      <span className="text-[9px] text-[var(--color-text-muted)]">
                        {note.type === "explain" ? "自我解释" : "笔记"}
                      </span>
                    </div>
                    <p className="text-xs text-[var(--color-text)] leading-relaxed">
                      {note.text}
                    </p>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right pane: Knowledge graph */}
      <div className="w-[600px] flex-shrink-0 overflow-hidden">
        {graphPanel}
      </div>
    </div>
  );

  // ----- Wrap with FocusMode -----
  return (
    <>
      {/* Focus mode toggle button (shown when not in focus mode) */}
      {!focusMode && (
        <button
          onClick={() => setFocusMode(true)}
          className="fixed bottom-6 left-6 z-30 flex items-center gap-1.5 px-3 py-2 rounded-full bg-[var(--color-accent)] text-white shadow-lg hover:shadow-xl hover:opacity-90 transition-all text-xs"
          title="进入专注模式"
        >
          <Focus size={14} />
          专注模式
        </button>
      )}

      <FocusMode
        open={focusMode}
        currentTopic={selectedNode?.label}
        cognitiveLoad={0.4}
        currentGoal={
          selectedNode
            ? `掌握 ${selectedNode.label}（当前 ${Math.round(selectedNode.mastery * 100)}%）`
            : "选择知识点开始学习"
        }
        onExit={() => setFocusMode(false)}
      >
        {mainContent}
      </FocusMode>
    </>
  );
}

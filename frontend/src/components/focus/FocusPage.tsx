"use client";

import React, { useState, useEffect, useCallback, useRef, useMemo } from "react";
import {
  X, Volume2, VolumeX, Lightbulb, Network, Play,
  ChevronLeft, ChevronRight, ChevronDown,
} from "lucide-react";
import { useConversationStore } from "@/store/conversation/conversation-store";
import { useMessageStore } from "@/store/conversation/message-store";
import { useChatStream } from "@/hooks/conversation/useChatStream";
import { setChatStreamAPI } from "@/store/conversation/actions/send-message";

import { apiFetch } from "@/store/conversation/tree-helpers";
import MessageList from "@/components/conversation/core/MessageList";
import ConversationChatInput from "@/components/conversation/core/ChatInput";
import { useGraphData } from "@/hooks/graph/useGraphData";
import type { GraphData, GraphNode } from "@/lib/types/graph-types";
import type { SelectedNode } from "@/components/conversation/tree/SidebarTreeNode";
import FocusGraph from "@/components/graph/graphs/FocusGraph";
import ForceGraph from "@/components/graph/graphs/ForceGraph";
import PracticePanel from "@/components/practice/panels/PracticePanel";

export default function FocusPage() {
  // ── Store data ──
  const messages = useMessageStore((s) => s.messages);
  const isLoading = useConversationStore((s) => s.isLoading);
  const sendMessage = useConversationStore((s) => s.sendMessage);
  const deleteMessage = useConversationStore((s) => s.deleteMessage);
  const editMessage = useConversationStore((s) => s.editMessage);
  const versionSwitch = useConversationStore((s) => s.versionSwitch);
  const dirList = useConversationStore((s) => s.dirList);
  const loadDirList = useConversationStore((s) => s.loadDirList);
  const loadMessages = useConversationStore((s) => s.loadMessages);
  const wsConnected = useConversationStore((s) => s.wsConnected);

  // ── 所有导航状态统一由 selectedNode 推导 ──
  const storeSelectedNode = useConversationStore((s) => s.selectedNode);
  const activeConversationId = storeSelectedNode?.level === "conv" ? storeSelectedNode.id : null;
  const selectedDirId = storeSelectedNode?.level === "conv" ? (storeSelectedNode.parent ?? null) : (storeSelectedNode?.id ?? null);

  // ── useChatStream（替代 StreamPipeline） ──
  const chatStream = useChatStream();
  useEffect(() => {
    setChatStreamAPI(chatStream);
    return () => setChatStreamAPI({ send: async () => {}, stop: async () => {}, submitToolResult: async () => {} });
  }, [chatStream]);

  // ── Init: navigation + load dirs ──
  useEffect(() => {
    loadDirList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Load messages when conversation changes ──
  useEffect(() => {
    if (activeConversationId) {
      loadMessages(activeConversationId);
    }
  }, [activeConversationId, loadMessages]);

  // ── Split pane state ──
  const [splitPercent, setSplitPercent] = useState(50);
  const dragging = useRef(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const [collapsedSide, setCollapsedSide] = useState<"left" | "right" | null>(null);

  // Flag: skip auto-collapse on the first mousemove after restoring from collapsed
  const justRestored = useRef(false);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;

      // Auto-collapse when dragged past threshold
      if (justRestored.current) {
        // First mousemove after restore — skip auto-collapse
        justRestored.current = false;
      } else if (pct <= 20) {
        dragging.current = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        setCollapsedSide("left");
        setSplitPercent(0);
        return;
      } else if (pct >= 80) {
        dragging.current = false;
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
        setCollapsedSide("right");
        setSplitPercent(100);
        return;
      }

      const clamped = Math.max(8, Math.min(92, pct));
      setSplitPercent(clamped);
      setCollapsedSide(null);
    };
    const onUp = () => {
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  const collapseTo = useCallback((side: "left" | "right") => {
    setCollapsedSide(side);
    setSplitPercent(side === "left" ? 0 : 100);
  }, []);

  const restoreFromCollapsed = useCallback(() => {
    setCollapsedSide(null);
    setSplitPercent(50);
  }, []);

  const onCollapsedDragLeft = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const pct = ((e.clientX - rect.left) / rect.width) * 100;
    setCollapsedSide(null);
    setSplitPercent(Math.max(25, Math.min(50, pct)));
    justRestored.current = true;
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  const onCollapsedDragRight = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const pct = ((e.clientX - rect.left) / rect.width) * 100;
    setCollapsedSide(null);
    setSplitPercent(Math.max(50, Math.min(75, pct)));
    justRestored.current = true;
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  // ── Socratic prompt bar ──
  const [showSocratic, setShowSocratic] = useState(false);
  // ── Practice mode ──
  const [showPractice, setShowPractice] = useState(false);
  const handleSend = useCallback(
    (text: string) => {
      if (text.trim()) {
        sendMessage(text.trim());
        setShowSocratic(false);
      }
    },
    [sendMessage]
  );

  // ── Voice state ──
  const [voiceEnabled, setVoiceEnabled] = useState(true);

  // ── Graph data ──
  const { graphData, loading: graphLoading, graphContainerRef, graphSize } = useGraphData({ maxRetries: 3 });
  const [graphMode, setGraphMode] = useState<"tree" | "force">("tree");
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  // Active path: IDs from root to selected node (for path-specific collapse)
  const activePath = useMemo(() => {
    if (!selectedNode || !graphData) return [];
    const path: string[] = [];
    let current: GraphNode | undefined = selectedNode;
    while (current) {
      path.unshift(current.id);
      current = current.parent ? graphData.nodes.find((n) => n.id === current!.parent) : undefined;
    }
    return path;
  }, [selectedNode, graphData]);
  // Force mode data: filter to valid levels
  const forceGraphData = useMemo(() => {
    if (!graphData) return { nodes: [], edges: [] };
    const validLevels = new Set(["partition", "domain", "topic", "conversation"]);
    const validIds = new Set(graphData.nodes.filter((n) => validLevels.has(n.level)).map((n) => n.id));
    const nodes = graphData.nodes.filter((n) => validLevels.has(n.level));
    const edges = graphData.edges.filter((e) => {
      return validIds.has(e.source) && validIds.has(e.target);
    });
    return { nodes, edges };
  }, [graphData]);

  // ── Breadcrumb state — domain/topic data loading ──
  const [domains, setDomains] = useState<any[]>([]);
  const [topics, setTopics] = useState<any[]>([]);
  const [loadingDomains, setLoadingDomains] = useState(false);
  const [loadingTopics, setLoadingTopics] = useState(false);
  const [openDropdown, setOpenDropdown] = useState<'partition' | 'domain' | 'topic' | null>(null);

  // Load sub-directories when partition changes
  useEffect(() => {
    if (selectedDirId) {
      setLoadingDomains(true);
      setOpenDropdown(null);
      apiFetch<any>(`/tree/directory?parent_id=${selectedDirId}`)
        .then((data) => setDomains(data.directory_nodes || []))
        .catch(() => setDomains([]))
        .finally(() => setLoadingDomains(false));
    } else {
      setDomains([]);
      setTopics([]);
    }
  }, [selectedDirId]);

  // Load sub-directories (same API, no separate "topic" concept)
  useEffect(() => {
    if (selectedDirId) {
      setLoadingTopics(true);
      setOpenDropdown(null);
      apiFetch<any>(`/tree/directory?parent_id=${selectedDirId}`)
        .then((data) => setTopics(data.directory_nodes || []))
        .catch(() => setTopics([]))
        .finally(() => setLoadingTopics(false));
    } else {
      setTopics([]);
    }
  }, [selectedDirId]);

  // ── Breadcrumb handlers ──
  const handleSelectDir = useCallback((pid: string) => {
    setDomains([]);
    setTopics([]);
    setOpenDropdown(null);
    useConversationStore.getState().selectConversation(pid, "");
    loadDirList();
  }, [loadDirList]);

  const handleSelectDomain = useCallback((did: string) => {
    setTopics([]);
    setOpenDropdown(null);
    useConversationStore.getState().selectConversation(did, "");
  }, []);

  const handleSelectTopic = useCallback((tid: string) => {
    setOpenDropdown(null);
    useConversationStore.getState().selectConversation(tid, "");
    // Load first empty conversation or create one
    apiFetch<{ conversations: { id: string; message_count?: number }[] }>(`/tree/conversation?parent_id=${tid}`)
      .then((data) => {
        const convs = data.conversations || [];
        const empty = convs.find((c: { id: string; message_count?: number }) => !c.message_count || c.message_count === 0);
        const foundConvId = empty?.id || convs[0]?.id;
        if (foundConvId) {
          useConversationStore.getState().selectConversation(tid, foundConvId);
        }
      })
      .catch(() => {});
  }, []);

  // Close dropdown on outside click
  useEffect(() => {
    if (!openDropdown) return;
    const handler = () => setOpenDropdown(null);
    window.addEventListener('click', handler);
    return () => window.removeEventListener('click', handler);
  }, [openDropdown]);

  // ── Collapsed views ──
  if (collapsedSide === "left") {
    return (
      <div ref={containerRef} className="fixed inset-0 bg-[var(--color-bg)] z-30 flex" style={{ bottom: "var(--bottom-nav-height, 56px)" }}>
        <div
          onMouseDown={onCollapsedDragLeft}
          className="flex-shrink-0 w-8 flex flex-col items-center justify-center hover:bg-[var(--color-surface)] border-r border-[var(--color-border)] cursor-col-resize transition-colors group"
          title="拖动恢复分栏"
        >
          <ChevronRight size={16} className="group-hover:scale-110 transition-transform" />
          <div className="absolute inset-y-1/4 w-[2px] rounded-full bg-[var(--color-border)] opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
        <div ref={graphContainerRef as React.RefObject<HTMLDivElement>} className="flex-1 overflow-hidden p-2">
          {graphLoading ? (
            <div className="flex items-center justify-center h-full text-sm text-[var(--color-text-muted)]">加载知识图谱…</div>
          ) : graphData ? (
            graphMode === "tree" ? (
              <FocusGraph data={graphData} selectedNodeId={selectedNode?.id} onNodeSelect={setSelectedNode} activePath={activePath} width={graphSize.width} height={1000} />
            ) : (
              <ForceGraph data={forceGraphData} selectedNodeId={selectedNode?.id} onNodeSelect={setSelectedNode} width={graphSize.width} height={1000} />
            )
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-[var(--color-text-muted)]">暂无图谱数据</div>
          )}
        </div>
      </div>
    );
  }

  if (collapsedSide === "right") {
    return (
      <div ref={containerRef} className="fixed inset-0 bg-[var(--color-bg)] z-30 flex" style={{ bottom: "var(--bottom-nav-height, 56px)" }}>
        <div className="flex-1 flex flex-col overflow-hidden">
          {renderConversationPanel()}
        </div>
        <div
          onMouseDown={onCollapsedDragRight}
          className="flex-shrink-0 w-8 flex flex-col items-center justify-center hover:bg-[var(--color-surface)] border-l border-[var(--color-border)] cursor-col-resize transition-colors group"
          title="拖动恢复分栏"
        >
          <ChevronLeft size={16} className="group-hover:scale-110 transition-transform" />
          <div className="absolute inset-y-1/4 w-[2px] rounded-full bg-[var(--color-border)] opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </div>
    );
  }

  // ── Full split view ──
  return (
    <div ref={containerRef} className="fixed inset-0 bg-[var(--color-bg)] z-30 flex" style={{ bottom: "var(--bottom-nav-height, 56px)" }}>
      {/* Left: Conversation */}
      <div className="flex flex-col overflow-hidden" style={{ width: `${splitPercent}%` }}>
        {renderConversationPanel()}
      </div>

      {/* Draggable divider */}
      <div className="flex-shrink-0 relative cursor-col-resize group flex items-center justify-center"
        style={{ width: 8 }} onMouseDown={onMouseDown}>
        {/* Thin vertical line */}
        <div className="w-[2px] h-full bg-gradient-to-b from-transparent via-[var(--color-border)] to-transparent group-hover:via-[var(--color-accent)]/50 transition-all duration-200" />
        {/* Grip indicator dots */}
        <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none">
          <div className="flex flex-col items-center gap-[3px]">
            <div className="w-[3px] h-[3px] rounded-full bg-[var(--color-accent)]/40" />
            <div className="w-[3px] h-[3px] rounded-full bg-[var(--color-accent)]/40" />
            <div className="w-[3px] h-[3px] rounded-full bg-[var(--color-accent)]/40" />
          </div>
        </div>
        {/* Collapse chevrons */}
        <button onClick={() => collapseTo("left")}
          className="absolute top-1/2 -left-2.5 -translate-y-1/2 w-4 h-6 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-[var(--color-surface)] rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"
          title="折叠左侧"><ChevronLeft size={10} /></button>
        <button onClick={() => collapseTo("right")}
          className="absolute top-1/2 -right-2.5 -translate-y-1/2 w-4 h-6 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity hover:bg-[var(--color-surface)] rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"
          title="折叠右侧"><ChevronRight size={10} /></button>
      </div>

      {/* Right: Knowledge graph */}
      <div ref={graphContainerRef as React.RefObject<HTMLDivElement>} className="flex flex-col overflow-hidden" style={{ width: `${100 - splitPercent}%` }}>
        <div className="flex-shrink-0 border-b border-[var(--color-border)] px-4 py-3 flex items-center gap-2">
          <Network size={16} className="text-[var(--color-accent)]" />
          <span className="text-sm font-semibold text-[var(--color-text)]">知识图谱</span>
          {graphLoading && <span className="text-xs text-[var(--color-text-muted)]">加载中…</span>}
          <div className="flex-1" />
          {/* Mode toggle */}
          <div className="flex items-center bg-[var(--color-surface)] rounded-lg p-0.5 gap-0.5">
            <button
              onClick={() => setGraphMode("tree")}
              className={`px-2 py-1 text-[11px] rounded-md transition-colors ${
                graphMode === "tree"
                  ? "bg-[var(--color-accent)] text-white font-medium"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              }`}
            >
              思维导图
            </button>
            <button
              onClick={() => setGraphMode("force")}
              className={`px-2 py-1 text-[11px] rounded-md transition-colors ${
                graphMode === "force"
                  ? "bg-[var(--color-accent)] text-white font-medium"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              }`}
            >
              力导向
            </button>
          </div>
          {wsConnected && <span className="text-[8px] text-green-500">●</span>}
        </div>
        <div className="flex-1 overflow-hidden p-2">
          {graphLoading ? (
            <div className="flex items-center justify-center h-full text-sm text-[var(--color-text-muted)]">加载知识图谱…</div>
          ) : graphData ? (
            graphMode === "tree" ? (
              <FocusGraph data={graphData} selectedNodeId={selectedNode?.id} onNodeSelect={setSelectedNode} activePath={activePath} width={graphSize.width} height={1000} />
            ) : (
              <ForceGraph data={forceGraphData} selectedNodeId={selectedNode?.id} onNodeSelect={setSelectedNode} width={graphSize.width} height={1000} />
            )
          ) : (
            <div className="flex items-center justify-center h-full text-sm text-[var(--color-text-muted)]">暂无图谱数据</div>
          )}
        </div>
      </div>
    </div>
  );

  // ── Breadcrumb bar renderer ──
  function renderBreadcrumb() {
    // Helper: dropdown for any level
    const dropdown = (opts: {
      level: 'partition' | 'domain' | 'topic';
      items: { id: string; name: string; emoji?: string; subtitle?: string }[];
      currentId: string | null;
      onSelect: (id: string) => void;
      placeholder: string;
      loading?: boolean;
      onAddNew?: () => void;
    }) => {
      const isOpen = openDropdown === opts.level;
      return (
        <div className="relative">
          <button
            onClick={(e) => { e.stopPropagation(); setOpenDropdown(isOpen ? null : opts.level); }}
            className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
              opts.currentId
                ? 'text-[var(--color-text)] hover:bg-[var(--color-surface)]'
                : 'text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]'
            }`}
          >
            {opts.currentId && opts.items.find(i => i.id === opts.currentId)?.emoji && (
              <span className="text-xs">{opts.items.find(i => i.id === opts.currentId)!.emoji}</span>
            )}
            <span className="truncate max-w-[120px]">
              {opts.currentId ? opts.items.find(i => i.id === opts.currentId)?.name || opts.placeholder : opts.placeholder}
            </span>
            {opts.loading ? (
              <span className="w-2 h-2 rounded-full bg-[var(--color-accent)] animate-pulse" />
            ) : (
              <ChevronDown size={10} className={`transition-transform ${isOpen ? 'rotate-180' : ''} text-[var(--color-text-muted)]`} />
            )}
          </button>
          {isOpen && (
            <div className="absolute left-0 top-full mt-1 z-30 w-52 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg shadow-xl max-h-52 overflow-y-auto"
              onClick={(e) => e.stopPropagation()}>
              {opts.items.length === 0 && !opts.loading && (
                <div className="px-3 py-2 text-xs text-[var(--color-text-muted)]">{opts.loading ? '加载中...' : '暂无'}</div>
              )}
              {opts.items.map((item) => (
                <button key={item.id}
                  onClick={() => opts.onSelect(item.id)}
                  className={`w-full text-left px-3 py-2 text-xs flex items-center gap-2 hover:bg-[var(--color-surface)] transition-colors ${
                    item.id === opts.currentId ? 'text-[var(--color-accent)] font-medium' : 'text-[var(--color-text)]'
                  }`}>
                  {item.emoji && <span>{item.emoji}</span>}
                  <span className="truncate flex-1">{item.name}</span>
                  {item.subtitle && <span className="text-[10px] text-[var(--color-text-muted)]">{item.subtitle}</span>}
                </button>
              ))}
              {opts.onAddNew && (
                <button onClick={opts.onAddNew}
                  className="w-full text-left px-3 py-2 text-xs text-[var(--color-accent)] hover:bg-[var(--color-surface)] border-t border-[var(--color-border)] flex items-center gap-1.5">
                  + 新建
                </button>
              )}
            </div>
          )}
        </div>
      );
    };

    return (
      <>
        {/* Back button */}
        <button onClick={() => window.history.back()}
          className="flex-shrink-0 p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)] rounded transition-colors"
          title="退出专注模式">
          <X size={14} />
        </button>

        <div className="flex items-center gap-0.5 flex-1 min-w-0 flex-wrap">
          {/* Dir level */}
          {dropdown({
            level: 'partition',
            items: dirList.map(p => ({ id: p.id, name: p.name, emoji: p.emoji })),
            currentId: selectedDirId,
            onSelect: handleSelectDir,
            placeholder: '选择',
          })}

          {/* Arrow + Domain level */}
          {selectedDirId && (
            <>
              <ChevronRight size={10} className="flex-shrink-0 text-[var(--color-text-muted)]" />
              {dropdown({
                level: 'domain',
                items: domains.map(d => ({ id: d.id, name: d.name, emoji: d.emoji, subtitle: d.topic_count ? `${d.topic_count} 专题` : undefined })),
                currentId: selectedDirId,
                onSelect: handleSelectDomain,
                placeholder: loadingDomains ? '...' : '选择领域',
                loading: loadingDomains,
                onAddNew: undefined,
              })}
            </>
          )}

          {/* Arrow + Topic level */}
          {selectedDirId && (
            <>
              <ChevronRight size={10} className="flex-shrink-0 text-[var(--color-text-muted)]" />
              {dropdown({
                level: 'topic',
                items: topics.map(t => ({ id: t.id, name: t.name, emoji: t.emoji, subtitle: t.conversation_count ? `${t.conversation_count} 对话` : undefined })),
                currentId: selectedDirId,
                onSelect: handleSelectTopic,
                placeholder: loadingTopics ? '...' : '选择专题',
                loading: loadingTopics,
              })}
            </>
          )}
        </div>
      </>
    );
  }

  // ── Conversation panel renderer ──
  function renderConversationPanel() {
    return (
      <>
      {/* Top bar with breadcrumb path */}
      <div className="flex-shrink-0 border-b border-[var(--color-border)]">
        <div className="flex items-center gap-1 px-3 py-2 min-h-[44px]">
          {renderBreadcrumb()}
        </div>
      </div>

        {/* Socratic prompt bar */}
        {showSocratic && (
          <div className="flex-shrink-0 border-b border-[var(--color-accent)]/20 bg-[var(--color-accent)]/5 px-4 py-2">
            <div className="flex items-start gap-2">
              <Lightbulb size={14} className="mt-1 text-amber-500 flex-shrink-0" />
              <textarea
                placeholder="输入你想深入探究的问题..."
                className="flex-1 bg-transparent text-sm resize-none focus:outline-none leading-relaxed"
                rows={2}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    const val = (e.target as HTMLTextAreaElement).value;
                    handleSend(val);
                  }
                }}
              />
            </div>
          </div>
        )}

        {/* Messages */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {showPractice ? (
            <PracticePanel
              nodeId={selectedNode?.id}
              nodeLabel={selectedNode?.label}
              onClose={() => setShowPractice(false)}
            />
          ) : (
            <>
              <div className="flex-1 overflow-y-auto px-4 pt-6 pb-2 space-y-4">
                <MessageList
                  messages={messages}
                  isLoading={isLoading}
                  onDeleteMessage={deleteMessage}
                  onEditMessage={(mid, text) => editMessage(mid, text)}
                />
              </div>
            </>
          )}
        </div>

        {/* Input area */}
        <div className="flex-shrink-0 border-t border-[var(--color-border)] bg-[var(--color-bg)]">
          <div className="max-w-xl mx-auto px-4 py-3">
            <ConversationChatInput
              onSend={handleSend}
              disabled={isLoading}
              conversationId={activeConversationId}
            />
            <div className="flex items-center justify-between mt-2 px-2">
              <div className="flex items-center gap-2">
                <button onClick={() => setShowSocratic((p) => !p)}
                  className={`flex items-center gap-1 text-xs transition-colors ${
                    showSocratic ? "text-amber-500" : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
                  }`}>
                  <Lightbulb size={12} />苏格拉底追问
                </button>
                <span className="text-[var(--color-border)]">|</span>
                <button onClick={() => { setShowPractice((p) => !p); setShowSocratic(false); }}
                  className={`flex items-center gap-1 text-xs transition-colors ${
                    showPractice ? "text-[var(--color-accent)]" : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
                  }`}>
                  <Play size={12} />{showPractice ? "返回对话" : "智能练习"}
                </button>
              </div>
              <button onClick={() => setVoiceEnabled((p) => !p)}
                className="flex items-center gap-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)] transition-colors">
                {voiceEnabled ? <Volume2 size={12} /> : <VolumeX size={12} />}
                {voiceEnabled ? "语音已开" : "语音已关"}
              </button>
            </div>
          </div>
        </div>
      </>
    );
  }
}


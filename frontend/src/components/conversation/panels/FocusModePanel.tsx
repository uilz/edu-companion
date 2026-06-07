"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  ChevronLeft, ChevronRight,
  BookOpen, Volume2, VolumeX, Play, Network,
} from "lucide-react";
import { useRouter } from "next/navigation";
import ConversationMessageArea from "@/components/conversation/core/ConversationMessageArea";
import PracticePanel from "@/components/practice/panels/PracticePanel";
import { PartitionPicker } from "@/components/conversation/tree/PartitionPicker";
import TreeBreadcrumb from "@/components/conversation/tree/TreeBreadcrumb";
import { useConversationStore } from "@/store/conversation/conversation-store";
import { useSocraticMode } from "@/components/conversation/hooks/useSocraticMode";
import { apiFetch } from "@/store/conversation/tree-helpers";
import type { Conversation, Domain, Topic } from "@/types";

/** FocusModePanel — 专注模式面板
 *
 * 布局：顶栏（分区选择器 + 控制按钮）
 *       下方：左对话 | 可拖拽分隔线 | 右图谱
 * 苏格拉底模式设置已迁移到设置页 /settings
 */
export default function FocusModePanel({
  onExitFocusMode,
}: {
  onExitFocusMode?: () => void;
}) {
  const messages = useConversationStore((s) => s.messages);
  const responseBlocks = useConversationStore((s) => s.responseBlocks);
  const activeConversationId = useConversationStore((s) => s.activeConversationId);
  const activeDomainId = useConversationStore((s) => s.activeDomainId);
  const activeTopicId = useConversationStore((s) => s.activeTopicId);
  const isLoading = useConversationStore((s) => s.isLoading);
  const statusMessage = useConversationStore((s) => s.statusMessage);
  const sendMessage = useConversationStore((s) => s.sendMessage);
  const deleteMessage = useConversationStore((s) => s.deleteMessage);
  const editMessage = useConversationStore((s) => s.editMessage);
  const versionSwitch = useConversationStore((s) => s.versionSwitch);
  const partitions = useConversationStore((s) => s.partitions);
  const selectedPartitionId = useConversationStore((s) => s.selectedPartitionId);
  const loadPartitions = useConversationStore((s) => s.loadPartitions);
  const loadMessages = useConversationStore((s) => s.loadMessages);

  // ── 从设置页读取配置 ──
  const socraticEnabled = useRef(false);
  const [socraticMode, setSocraticMode] = useState(false);
  useEffect(() => {
    try {
      const saved = localStorage.getItem("edu-companion-settings");
      if (saved) {
        const parsed = JSON.parse(saved);
        setSocraticMode(!!parsed.socraticMode);
        socraticEnabled.current = !!parsed.socraticMode;
      }
    } catch { /* ignore */ }
  }, []);

  // ── 苏格拉底模式（配置来自设置页） ──
  const {
    followUpMode, setFollowUpMode,
    hasPendingQuestion,
    handleSend: socraticSend,
  } = useSocraticMode(messages, sendMessage, socraticMode);

  // ── 语音 ──
  const [voiceEnabled, setVoiceEnabled] = useState(true);

  // ── 智能练习 ──
  const [showPractice, setShowPractice] = useState(false);

  // ── 路径名称 ──
  const [domainName, setDomainName] = useState("");
  const [topicName, setTopicName] = useState("");
  const [conversationName, setConversationName] = useState("");
  const [domainOptions, setDomainOptions] = useState<Domain[]>([]);
  const [topicOptions, setTopicOptions] = useState<Topic[]>([]);
  const [conversationOptions, setConversationOptions] = useState<Conversation[]>([]);
  const partitionName = partitions.find(p => p.id === selectedPartitionId)?.name || "";

  // Fetch domain/topic names when selection changes
  useEffect(() => {
    if (!selectedPartitionId) {
      setDomainName("");
      setTopicName("");
      setConversationName("");
      setDomainOptions([]);
      setTopicOptions([]);
      setConversationOptions([]);
      return;
    }

    let cancelled = false;

    const loadNames = async () => {
      try {
        const domainsRes = await apiFetch<{ domains: Domain[] }>(
          `/tree/domain?parent_id=${selectedPartitionId}`,
        );
        if (cancelled) return;

        const domains = domainsRes.domains || [];
        setDomainOptions(domains);

        let resolvedDomain: Domain | undefined = activeDomainId
          ? domains.find((item) => item.id === activeDomainId)
          : undefined;
        let resolvedTopic: Topic | undefined;
        let resolvedConversation: Conversation | undefined;

        if (!resolvedDomain && (activeTopicId || activeConversationId)) {
          for (const candidateDomain of domains) {
            const topicsRes = await apiFetch<{ topics: Topic[] }>(
              `/tree/topic?parent_id=${candidateDomain.id}`,
            );
            if (cancelled) return;
            const candidateTopics = topicsRes.topics || [];
            const matchedTopic = activeTopicId
              ? candidateTopics.find((item) => item.id === activeTopicId)
              : undefined;
            if (matchedTopic) {
              resolvedDomain = candidateDomain;
              resolvedTopic = matchedTopic;
              setTopicOptions(candidateTopics);
              break;
            }

            if (activeConversationId) {
              for (const candidateTopic of candidateTopics) {
                const convRes = await apiFetch<{ conversations: Conversation[] }>(
                  `/tree/conversation?parent_id=${candidateTopic.id}`,
                );
                if (cancelled) return;
                const candidateConversations = convRes.conversations || [];
                const matchedConversation = candidateConversations.find((item) => item.id === activeConversationId);
                if (matchedConversation) {
                  resolvedDomain = candidateDomain;
                  resolvedTopic = candidateTopic;
                  resolvedConversation = matchedConversation;
                  setTopicOptions(candidateTopics);
                  setConversationOptions(candidateConversations);
                  break;
                }
              }
              if (resolvedConversation) break;
            }
          }
        }

        if (resolvedDomain) {
          const nextDomainId = resolvedDomain.id;
          if (activeDomainId !== nextDomainId) {
            useConversationStore.setState({ activeDomainId: nextDomainId });
          }
          setDomainName(resolvedDomain.name || "");

          const topicsRes = await apiFetch<{ topics: Topic[] }>(
            `/tree/topic?parent_id=${nextDomainId}`,
          );
          if (cancelled) return;
          const topics = topicsRes.topics || [];
          setTopicOptions(topics);

          if (!resolvedTopic && activeTopicId) {
            resolvedTopic = topics.find((item) => item.id === activeTopicId);
          }
          if (resolvedTopic && activeTopicId !== resolvedTopic.id) {
            useConversationStore.setState({ activeTopicId: resolvedTopic.id });
          }
          setTopicName(resolvedTopic?.name || "");

          if (resolvedTopic) {
            const convRes = await apiFetch<{ conversations: Conversation[] }>(
              `/tree/conversation?parent_id=${resolvedTopic.id}`,
            );
            if (cancelled) return;
            const conversations = convRes.conversations || [];
            setConversationOptions(conversations);

            if (!resolvedConversation && activeConversationId) {
              resolvedConversation = conversations.find((item) => item.id === activeConversationId);
            }
            setConversationName(resolvedConversation?.name || "");
          } else {
            setConversationOptions([]);
            setConversationName("");
          }
          return;
        }

        if (activeDomainId) {
          const topicsRes = await apiFetch<{ topics: Topic[] }>(
            `/tree/topic?parent_id=${activeDomainId}`,
          );
          if (cancelled) return;
          const topics = topicsRes.topics || [];
          setTopicOptions(topics);
          const fallbackDomain = domains.find((item) => item.id === activeDomainId);
          setDomainName((resolvedDomain || fallbackDomain)?.name || "");

          if (activeTopicId) {
            resolvedTopic = topics.find((item) => item.id === activeTopicId);
            setTopicName(resolvedTopic?.name || "");
          } else {
            setTopicName("");
            setConversationOptions([]);
            setConversationName("");
          }

          if (resolvedTopic) {
            const convRes = await apiFetch<{ conversations: Conversation[] }>(
              `/tree/conversation?parent_id=${resolvedTopic.id}`,
            );
            if (cancelled) return;
            const conversations = convRes.conversations || [];
            setConversationOptions(conversations);
            if (activeConversationId) {
              resolvedConversation = conversations.find((item) => item.id === activeConversationId);
            }
            setConversationName(resolvedConversation?.name || "");
          }

          return;
        }

        setDomainName("");
        setTopicName("");
        setConversationName("");
        setDomainOptions([]);
        setTopicOptions([]);
        setConversationOptions([]);
      } catch {
        if (cancelled) return;
        setDomainName("");
        setTopicName("");
        setConversationName("");
        setDomainOptions([]);
        setTopicOptions([]);
        setConversationOptions([]);
      }
    };

    loadNames();

    return () => {
      cancelled = true;
    };
  }, [selectedPartitionId, activeDomainId, activeTopicId, activeConversationId]);

  // ── 分栏 ──
  const [splitPercent, setSplitPercent] = useState(50);
  const dragging = useRef(false);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const COLLAPSE_THRESHOLD_PERCENT = 4;
  const SPLITTER_WIDTH_PX = 8;

  const stopDragging = useCallback(() => {
    dragging.current = false;
    setIsDragging(false);
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
  }, []);

  const isAtEdge = useCallback((value: number) => {
    return value <= COLLAPSE_THRESHOLD_PERCENT || value >= 100 - COLLAPSE_THRESHOLD_PERCENT;
  }, [COLLAPSE_THRESHOLD_PERCENT]);

  const handleLeftButtonClick = useCallback(() => {
    setSplitPercent((prev) => {
      if (isAtEdge(prev)) {
        // Expand left pane to 40% when currently collapsed to either side.
        return 40;
      }
      return 0;
    });
  }, [isAtEdge]);

  const handleRightButtonClick = useCallback(() => {
    setSplitPercent((prev) => {
      if (isAtEdge(prev)) {
        // Expand right pane to 40% when currently collapsed to either side.
        return 60;
      }
      return 100;
    });
  }, [isAtEdge]);

  const updateSplitFromClientX = useCallback((clientX: number) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const pct = ((clientX - rect.left) / rect.width) * 100;

    if (pct <= COLLAPSE_THRESHOLD_PERCENT) {
      setSplitPercent(0);
      return;
    }
    if (pct >= 100 - COLLAPSE_THRESHOLD_PERCENT) {
      setSplitPercent(100);
      return;
    }

    setSplitPercent(Math.max(0, Math.min(100, pct)));
  }, []);

  const onMouseDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.preventDefault();
    dragging.current = true;
    setIsDragging(true);
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    updateSplitFromClientX(e.clientX);
  }, [updateSplitFromClientX]);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      updateSplitFromClientX(e.clientX);
    };

    const onMouseUp = () => {
      if (!dragging.current) return;
      stopDragging();
    };

    const onWindowBlur = () => stopDragging();
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    window.addEventListener("blur", onWindowBlur);

    return () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
      window.removeEventListener("blur", onWindowBlur);
    };
  }, [stopDragging, updateSplitFromClientX]);

  // ── 对话面板渲染 ──
  function renderConversation() {
    return (
      <div className="flex flex-col h-full">
        <div className="flex-shrink-0 border-b border-[var(--color-border)]">
          <div className="px-4 py-2 flex items-center gap-2">
            <button onClick={onExitFocusMode} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" title="返回侧栏模式">
              <ChevronLeft size={16} />
            </button>
            <BookOpen size={14} className="text-[var(--color-accent)]" />
            <span className="text-xs text-[var(--color-text-muted)]">专注模式</span>
            <div className="flex-1" />
            <button onClick={() => setShowPractice((p) => !p)}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors mr-1 ${
                showPractice ? "text-[var(--color-accent)] bg-[var(--color-accent)]/10" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              }`}>
              <Play size={12} />{showPractice ? "返回对话" : "智能练习"}
            </button>
            <button onClick={() => setVoiceEnabled((p) => !p)}
              className={`p-1 rounded ${voiceEnabled ? "text-[var(--color-text)]" : "text-[var(--color-text-muted)]"}`}
              title={voiceEnabled ? "语音已开" : "语音已关"}>
              {voiceEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />}
            </button>
          </div>
          <div className="px-2 pb-1.5">
            <TreeBreadcrumb
              partitionName={partitionName}
              domainName={domainName || undefined}
              topicName={topicName || undefined}
              conversationName={conversationName || undefined}
              partitions={partitions.map((partition) => ({ id: partition.id, label: partition.name, emoji: partition.emoji }))}
              domains={domainOptions.map((domain) => ({ id: domain.id, label: domain.name, emoji: domain.emoji }))}
              topics={topicOptions.map((topic) => ({ id: topic.id, label: topic.name, emoji: topic.emoji }))}
              conversations={conversationOptions.map((conversation) => ({ id: conversation.id, label: conversation.name || "未命名会话" }))}
              selectedPartitionId={selectedPartitionId}
              selectedDomainId={activeDomainId}
              selectedTopicId={activeTopicId}
              selectedConversationId={activeConversationId}
              onSelectPartition={(pid) => {
                useConversationStore.setState({
                  selectedPartitionId: pid,
                  activeDomainId: null,
                  activeTopicId: null,
                  activeConversationId: null,
                  messages: [],
                  responseBlocks: [],
                });
                loadPartitions();
              }}
              onSelectDomain={(did) => {
                useConversationStore.setState({
                  activeDomainId: did,
                  activeTopicId: null,
                  activeConversationId: null,
                  messages: [],
                  responseBlocks: [],
                });
              }}
              onSelectTopic={(tid) => {
                useConversationStore.setState({
                  activeTopicId: tid,
                  activeConversationId: null,
                  messages: [],
                  responseBlocks: [],
                });
                apiFetch<{ conversations: Conversation[] }>(`/tree/conversation?parent_id=${tid}`)
                  .then((data) => {
                    const convs = data.conversations || [];
                    const empty = convs.find((c) => !c.message_count || c.message_count === 0);
                    const convId = empty?.id || convs[0]?.id;
                    if (convId) {
                      useConversationStore.setState({ activeConversationId: convId });
                      loadMessages(convId);
                    }
                  })
                  .catch(() => { });
              }}
              onSelectConversation={(cid) => {
                useConversationStore.setState({
                  activeConversationId: cid,
                });
                loadMessages(cid);
              }}
            />
          </div>
        </div>

        {showPractice ? (
          <PracticePanel
            onClose={() => setShowPractice(false)}
          />
        ) : (
          <ConversationMessageArea
            messages={messages}
            responseBlocks={responseBlocks}
            isLoading={isLoading}
            statusMessage={statusMessage}
            activeConversationId={activeConversationId}
            replyingToId={null}
            onSend={socraticSend}
            onDeleteMessage={deleteMessage}
            onEditMessage={editMessage}
            onVersionSwitch={versionSwitch}
            socraticEnabled={socraticMode}
            followUpMode={followUpMode}
            setFollowUpMode={setFollowUpMode}
            messageListClassName="flex-1 overflow-y-auto px-4 pt-6 pb-2 space-y-4"
          />
        )}
      </div>
    );
  }

  // ── 完整分栏 ──
  return (
    <div ref={containerRef} className="fixed inset-0 bg-[var(--color-bg)] z-30 flex" style={{ bottom: 0 }}>
      <div
        className="flex flex-col overflow-hidden"
        style={{ width: `calc((100% - ${SPLITTER_WIDTH_PX}px) * ${splitPercent / 100})` }}
      >
        {renderConversation()}
      </div>

      <div
        className="flex-shrink-0 relative cursor-col-resize group"
        style={{ width: SPLITTER_WIDTH_PX }}
        onMouseDown={onMouseDown}
      >
        <div className="absolute inset-y-0 left-1/2 -translate-x-1/2 w-[3px] bg-[var(--color-border)] group-hover:bg-[var(--color-accent)] transition-colors rounded-full" />
        <button
          onClick={handleLeftButtonClick}
          onMouseDown={(e) => e.stopPropagation()} // 阻止冒泡，不触发拖拽
          className="absolute top-1/2 -left-4 -translate-y-1/2 w-6 h-12 flex items-center justify-center hover:bg-[var(--color-surface)] rounded opacity-0 group-hover:opacity-100 transition-opacity"
          title={isAtEdge(splitPercent) ? "展开左侧" : "收起左侧"}>
          {isAtEdge(splitPercent) ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
        </button>
        <button
          onClick={handleRightButtonClick}
          onMouseDown={(e) => e.stopPropagation()} // 阻止冒泡
          className="absolute top-1/2 -right-4 -translate-y-1/2 w-6 h-12 flex items-center justify-center hover:bg-[var(--color-surface)] rounded opacity-0 group-hover:opacity-100 transition-opacity"
          title={isAtEdge(splitPercent) ? "展开右侧" : "收起右侧"}>
          {isAtEdge(splitPercent) ? <ChevronLeft size={12} /> : <ChevronRight size={12} />}
        </button>
      </div>

      <div
        className="flex flex-col overflow-hidden"
        style={{ width: `calc((100% - ${SPLITTER_WIDTH_PX}px) * ${(100 - splitPercent) / 100})` }}
      >
        <KnowledgeTreeEntry activeTopicId={activeTopicId} partitionId={selectedPartitionId} />
      </div>

      {isDragging && (
        <div className="fixed inset-0 z-40 cursor-col-resize" />
      )}
    </div>
  );
}

/** 知识树入口面板 — 替代原 GraphPanel，点击跳转知识树页并智能锚定节点 */
function KnowledgeTreeEntry({ activeTopicId, partitionId }: { activeTopicId?: string | null; partitionId?: string | null }) {
  const router = useRouter();

  const handleNavigate = () => {
    const params = new URLSearchParams();
    if (partitionId) params.set("partition", partitionId);
    if (activeTopicId) params.set("node", activeTopicId);
    router.push(`/knowledge-tree?${params.toString()}`);
  };

  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 p-6">
      <div className="w-16 h-16 rounded-2xl bg-[var(--color-accent)]/10 flex items-center justify-center">
        <Network size={28} className="text-[var(--color-accent)]" />
      </div>
      <div className="text-center space-y-1.5">
        <h3 className="text-sm font-semibold text-[var(--color-text)]">知识树</h3>
        <p className="text-xs text-[var(--color-text-muted)] max-w-[240px]">
          可视化知识结构，探索学习路径，管理知识节点
        </p>
      </div>
      <button
        onClick={handleNavigate}
        className="px-5 py-2.5 bg-[var(--color-accent)] text-white rounded-lg text-sm font-medium hover:opacity-90 transition-opacity flex items-center gap-2"
      >
        <Network size={16} />
        打开知识树
      </button>
      {activeTopicId && (
        <p className="text-[10px] text-[var(--color-text-muted)]">
          将自动定位到当前话题节点
        </p>
      )}
    </div>
  );
}

"use client";

import React from "react";
import {
  Menu, X, Bot, ChevronLeft, ChevronRight,
} from "lucide-react";
import type { Partition, TreeNode, ResponseBlock } from "@/types";
import PartitionSidebar from "@/components/conversation/PartitionSidebar";
import MessageList from "@/components/conversation/MessageList";
import ConversationChatInput from "@/components/conversation/ChatInput";
import type { UseConversationReturn } from "@/components/conversation/useConversation";

// ── New partition dialog ──
function NewPartitionDialog({
  open,
  onClose,
  onCreate,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (name: string, emoji: string) => void;
}) {
  const [name, setName] = React.useState("");
  const [emoji, setEmoji] = React.useState("📐");

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] w-full max-w-sm mx-4 rounded-xl" onClick={(e) => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-[var(--color-border)] flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[var(--color-text)]">
            新建分区
          </h3>
          <button onClick={onClose} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <X size={16} />
          </button>
        </div>
        <div className="px-4 py-4 space-y-3">
          <div>
            <label className="text-xs text-[var(--color-text-muted)] block mb-1">分区名称</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如: 高等数学-极限"
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-[var(--color-border-hover)]"
              autoFocus
            />
          </div>
          <div>
            <label className="text-xs text-[var(--color-text-muted)] block mb-1">Emoji</label>
            <input value={emoji} onChange={(e) => setEmoji(e.target.value)} className="w-16 bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 text-center rounded-lg" />
          </div>
        </div>
        <div className="px-4 py-3 border-t border-[var(--color-border)] flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-[var(--color-text-secondary)]">取消</button>
          <button onClick={() => { if (name.trim()) { onCreate(name.trim(), emoji); setName(""); setEmoji("📐"); onClose(); } }} disabled={!name.trim()} className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white rounded-lg disabled:opacity-30">
            创建
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Context switch banner ──
function SwitchBanner({
  domainName, topicName, onSwitch, onDismiss,
}: {
  domainName: string;
  topicName: string;
  onSwitch: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="mx-4 mt-2 px-4 py-3 bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/30 rounded-lg">
      <div className="flex items-start gap-3">
        <span className="text-lg">🔀</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-[var(--color-text)] leading-relaxed">
            检测到你在聊 <strong>{domainName}{topicName ? ` → ${topicName}` : ""}</strong>，要切换到对应会话吗？
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={onSwitch}
            className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)] rounded-lg transition-colors"
          >
            切换
          </button>
          <button
            onClick={onDismiss}
            className="px-2 py-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            留在此处
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Mobile bottom sheet ──
function MobileBottomSheet({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-[var(--color-bg)] border-t border-[var(--color-border)] max-h-[70vh] flex flex-col rounded-t-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <span className="text-sm font-semibold text-[var(--color-text)]">导航</span>
          <button onClick={onClose} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-hidden">{children}</div>
      </div>
    </div>
  );
}

// ── ConversationPanel Component ──
export default function ConversationPanel(props: UseConversationReturn) {
  const {
    // State
    partitions,
    selectedPartitionId,
    activeConversationId,
    messages,
    responseBlocks,
    isLoading,
    statusMessage,
    switchBanner,
    showPartitionSidebar,
    sidebarCollapsed,
    showNewPartition,
    loadingPartitions,
    convError,
    isDesktop,
    activePartition,

    // Handlers
    handleSelectConversation,
    handleNewConversation,
    handleSend,
    handleDeleteMessage,
    handleEditMessage,
    handleVersionSwitch,
    handleCreatePartition,
    handleRenamePartition,
    handleDeletePartition,
    handleSwitchConfirm,
    handleSwitchDismiss,
    setShowPartitionSidebar,
    setShowNewPartition,
    setSidebarCollapsed,
    loadPartitions,
  } = props;

  // ── Mobile layout ──
  if (!isDesktop) {
    return (
      <div
        className="fixed inset-0 bg-[var(--color-bg)] z-30 flex flex-col"
        style={{ bottom: "var(--bottom-nav-height)" }}
      >
        <div className="flex-shrink-0 border-b border-[var(--color-border)] px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setShowPartitionSidebar(true)}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            <Menu size={20} />
          </button>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-[var(--color-text)] truncate">
              {activePartition
                ? `${activePartition.emoji} ${activePartition.name}`
                : "对话"}
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-hidden flex flex-col">
          {switchBanner && (
            <SwitchBanner
              domainName={switchBanner.domainName}
              topicName={switchBanner.topicName}
              onSwitch={handleSwitchConfirm}
              onDismiss={handleSwitchDismiss}
            />
          )}
          {convError && (
            <div className="flex-shrink-0 mx-4 mt-2 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
              {convError}
            </div>
          )}
          <MessageList
            messages={messages}
            responseBlocks={responseBlocks}
            isLoading={isLoading}
            statusMessage={statusMessage}
            onDeleteMessage={handleDeleteMessage}
            onEditMessage={handleEditMessage}
            onVersionSwitch={handleVersionSwitch}
          />
          <ConversationChatInput
            onSend={handleSend}
            disabled={isLoading}
            conversationId={activeConversationId}
          />
        </div>

        {showPartitionSidebar && (
          <MobileBottomSheet onClose={() => setShowPartitionSidebar(false)}>
            <PartitionSidebar
              partitions={partitions}
              selectedPartitionId={selectedPartitionId}
              activeConversationId={activeConversationId}
              initialConversationId={activeConversationId ?? undefined}
              onSelectConversation={handleSelectConversation}
              onCreatePartition={() => {
                setShowPartitionSidebar(false);
                setShowNewPartition(true);
              }}
              onRenamePartition={handleRenamePartition}
              onDeletePartition={handleDeletePartition}
              loading={loadingPartitions}
              onNewConversation={handleNewConversation}
              onTreeChanged={loadPartitions}
            />
          </MobileBottomSheet>
        )}

        <NewPartitionDialog
          open={showNewPartition}
          onClose={() => setShowNewPartition(false)}
          onCreate={handleCreatePartition}
        />
      </div>
    );
  }

  // ── Desktop layout: merged sidebar ──
  const SIDEBAR_WIDTH = 260;

  return (
    <div className="fixed inset-0 bg-[var(--color-bg)] z-30 flex">
      {/* Merged sidebar: nav links + partition tree */}
      <div
        className="flex-shrink-0 flex flex-col border-r border-[var(--color-border)] transition-all duration-200"
        style={{ width: sidebarCollapsed ? "0px" : `${SIDEBAR_WIDTH}px`, overflow: "hidden" }}
      >
        {!sidebarCollapsed && (
          <div className="flex flex-col h-full">
            {/* Mini header with back to dashboard link */}
            <div className="flex items-center justify-between px-3 py-2.5 border-b border-[var(--color-border)]">
              <a
                href="/dashboard"
                className="flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
              >
                <ChevronLeft size={14} />
                <span>驾驶舱</span>
              </a>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => {
                    if (selectedPartitionId) {
                      handleNewConversation("partition", selectedPartitionId);
                    } else {
                      // No partition selected — create default first
                      handleNewConversation("default", "");
                    }
                  }}
                  className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded"
                  title="新建会话"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </button>
                <button
                  onClick={() => setShowNewPartition(true)}
                  className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded"
                  title="新建分区"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>
                </button>
                <button
                  onClick={() => setSidebarCollapsed(true)}
                  className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)] rounded"
                  title="收起侧栏"
                >
                  <ChevronLeft size={14} />
                </button>
              </div>
            </div>

            {/* Partition tree */}
            <div className="flex-1 overflow-hidden">
              <PartitionSidebar
                partitions={partitions}
                selectedPartitionId={selectedPartitionId}
                activeConversationId={activeConversationId}
                initialConversationId={activeConversationId ?? undefined}
                onSelectConversation={handleSelectConversation}
                onCreatePartition={() => setShowNewPartition(true)}
                onRenamePartition={handleRenamePartition}
                onDeletePartition={handleDeletePartition}
                loading={loadingPartitions}
                compact
                onNewConversation={handleNewConversation}
                onTreeChanged={loadPartitions}
              />
            </div>
          </div>
        )}
      </div>

      {/* Collapse toggle when sidebar hidden */}
      {sidebarCollapsed && (
        <button
          onClick={() => setSidebarCollapsed(false)}
          className="flex-shrink-0 w-6 border-r border-[var(--color-border)] flex items-center justify-center text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-colors"
          title="展开侧栏"
        >
          <ChevronRight size={14} />
        </button>
      )}

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0">
        {selectedPartitionId && activePartition && (
          <div className="flex-shrink-0 border-b border-[var(--color-border)] px-6 py-3 flex items-center gap-3">
            <Bot size={18} className="text-[var(--color-accent)]" />
            <div>
              <div className="text-sm font-semibold text-[var(--color-text)]">
                {activePartition.emoji} {activePartition.name}
              </div>
            </div>
          </div>
        )}

        {switchBanner && (
          <SwitchBanner
            domainName={switchBanner.domainName}
            topicName={switchBanner.topicName}
            onSwitch={handleSwitchConfirm}
            onDismiss={handleSwitchDismiss}
          />
        )}

        {convError && (
          <div className="flex-shrink-0 mx-6 mt-2 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
            {convError}
          </div>
        )}
        <MessageList
          messages={messages}
          responseBlocks={responseBlocks}
          isLoading={isLoading}
          statusMessage={statusMessage}
          onDeleteMessage={handleDeleteMessage}
          onEditMessage={handleEditMessage}
          onVersionSwitch={handleVersionSwitch}
        />

        <ConversationChatInput
          onSend={handleSend}
          disabled={isLoading}
          conversationId={activeConversationId}
        />
      </div>

      <NewPartitionDialog
        open={showNewPartition}
        onClose={() => setShowNewPartition(false)}
        onCreate={handleCreatePartition}
      />
    </div>
  );
}

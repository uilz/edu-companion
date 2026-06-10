"use client";

import React from "react";
import {
  Menu, Bot, ChevronLeft, ChevronRight, BarChart3,
} from "lucide-react";
import type { Partition } from "@/types";
import StudySidebar from "@/components/conversation/panels/StudySidebar";
import ConversationMessageArea from "@/components/conversation/core/ConversationMessageArea";
import MobileBottomSheet from "@/components/conversation/panels/MobileBottomSheet";
import type { UseConversationReturn } from "@/components/conversation/hooks/useConversation";
import { useConversationStore } from "@/store/conversation/conversation-store";
import { NewNodeDialog } from "@/components/ui/NewNodeDialog";
import KnowledgeTreeRecommendBanner from "@/components/conversation/banners/KnowledgeTreeRecommendBanner";
import NodePathBreadcrumb from "@/components/conversation/tree/NodePathBreadcrumb";

/**
 * ConversationPanel — 对话面板主布局组件
 *
 * 侧栏模式（默认）：左 StudySidebar + 右 ConversationMessageArea。
 * 桌面端支持侧栏折叠，移动端为全屏布局。
 */
export default function ConversationPanel(
  props: UseConversationReturn & { onEnterFocusMode?: () => void }
) {
  const isInSubBranch = useConversationStore((s) => s.isInSubBranch);
  const exitSubBranch = useConversationStore((s) => s.exitSubBranch);
  const subBranchMessages = useConversationStore((s) => s.messages);

  const subBranchQuotedText = React.useMemo(() => {
    if (!isInSubBranch) return "";
    const q = subBranchMessages[0]?.content_blocks?.find((b) => b.type === "quote");
    return q?.quoted_text || "";
  }, [isInSubBranch, subBranchMessages]);

  const activeDomainId = useConversationStore(s => s.activeDomainId);
  const activeTopicId = useConversationStore(s => s.activeTopicId);

  const {
    partitions,
    selectedPartitionId,
    activeConversationId,
    messages,
    responseBlocks,
    isLoading,
    statusMessage,
    replyingToId,
    switchBanner,
    showPartitionSidebar,
    sidebarCollapsed,
    showNewPartition,
    loadingPartitions,
    convError,
    isDesktop,
    activePartition,
    handleSelectConversation,
    handleNewConversation,
    handleSend,
    handleDeleteMessage,
    handleEditMessage,
    handleVersionSwitch,
    handleCreatePartition,
    handleRenamePartition,
    handleSwitchConfirm,
    handleSwitchDismiss,
    setShowPartitionSidebar,
    setShowNewPartition,
    setSidebarCollapsed,
    loadPartitions,
  } = props;

  const switchBannerPartitionName = React.useMemo(() => {
    if (!switchBanner?.partitionId) return "";
    const p = partitions.find((pp) => pp.id === switchBanner.partitionId);
    return p ? `${(p as { emoji?: string }).emoji || ""} ${(p as { name: string }).name}` : "";
  }, [partitions, switchBanner?.partitionId]);

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
          <KnowledgeTreeRecommendBanner partitionId={selectedPartitionId} />
          <ConversationMessageArea
            messages={messages}
            responseBlocks={responseBlocks}
            isLoading={isLoading}
            statusMessage={statusMessage}
            activeConversationId={activeConversationId}
            replyingToId={replyingToId}
            onSend={handleSend}
            onDeleteMessage={handleDeleteMessage}
            onEditMessage={handleEditMessage}
            switchBanner={switchBanner}
            switchBannerPartitionName={switchBannerPartitionName}
            handleSwitchConfirm={handleSwitchConfirm}
            handleSwitchDismiss={handleSwitchDismiss}
            isInSubBranch={isInSubBranch}
            subBranchQuotedText={subBranchQuotedText}
            exitSubBranch={exitSubBranch}
            convError={convError}
          />
        </div>

        {showPartitionSidebar && (
          <MobileBottomSheet onClose={() => setShowPartitionSidebar(false)}>
            <StudySidebar
              partitions={partitions}
              selectedPartitionId={selectedPartitionId}
              activeConversationId={activeConversationId}
              activeDomainId={activeDomainId}
              activeTopicId={activeTopicId}
              onSelectConversation={handleSelectConversation}
              onCreatePartition={() => {
                setShowPartitionSidebar(false);
                setShowNewPartition(true);
              }}
              loading={loadingPartitions}
              onNewConversation={(level, parentId, partitionId) => {
                setShowPartitionSidebar(false);
                handleNewConversation(level, parentId, partitionId);
              }}
              onConversationReady={(pid, cid) => {
                setShowPartitionSidebar(false);
                handleSelectConversation(pid, cid);
              }}
              onTreeChanged={loadPartitions}
              onSelectConv={(pid, cid) => {
                setShowPartitionSidebar(false);
                handleSelectConversation(pid, cid);
              }}
            />
          </MobileBottomSheet>
        )}

        <NewNodeDialog
          open={showNewPartition}
          onClose={() => setShowNewPartition(false)}
          onCreate={handleCreatePartition}
          title="新建分区"
          namePlaceholder="例如: 高等数学"
          defaultEmoji="📐"
          nameLabel="分区名称"
        />
      </div>
    );
  }

  // ── Desktop layout ──
  const SIDEBAR_WIDTH = 280;

  return (
    <div className="fixed inset-0 bg-[var(--color-bg)] z-30 flex">
      {/* Sidebar */}
      <div
        className="flex-shrink-0 flex flex-col border-r border-[var(--color-border)] transition-all duration-200 bg-[var(--color-page-secondary)]"
        style={{ width: sidebarCollapsed ? "0px" : `${SIDEBAR_WIDTH}px`, overflow: "hidden" }}
      >
        {!sidebarCollapsed && (
          <div className="flex flex-col h-full">
            <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
              <a
                href="/dashboard"
                className="flex items-center gap-1.5 text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors font-medium"
              >
                <ChevronLeft size={13} />
                <span>驾驶舱</span>
              </a>
              <div className="flex items-center gap-0.5">
                <button
                  onClick={() => {
                    handleNewConversation("default", "");
                  }}
                  className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
                  title="临时新建会话"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </button>
                <button
                  onClick={() => setShowNewPartition(true)}
                  className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
                  title="新建分区"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>
                </button>
                <button
                  onClick={() => setSidebarCollapsed(true)}
                  className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
                  title="收起侧栏"
                >
                  <ChevronLeft size={14} />
                </button>
                <button
                  onClick={props.onEnterFocusMode}
                  className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent-soft)]"
                  title="专注模式"
                >
                  <BarChart3 size={14} />
                </button>
              </div>
            </div>

            <div className="flex-1 overflow-hidden">
              <StudySidebar
                key={`sidebar-${useConversationStore.getState().treeRefreshKey}`}
                partitions={partitions}
                selectedPartitionId={selectedPartitionId}
                activeConversationId={activeConversationId}
                activeDomainId={activeDomainId}
                activeTopicId={activeTopicId}
                onSelectConversation={handleSelectConversation}
                onCreatePartition={() => setShowNewPartition(true)}
                onRenamePartition={handleRenamePartition}
                loading={loadingPartitions}
                compact
                onNewConversation={handleNewConversation}
                onConversationReady={handleSelectConversation}
                onTreeChanged={loadPartitions}
                onSelectConv={handleSelectConversation}
              />
            </div>
          </div>
        )}
      </div>

      {/* Collapsed sidebar toggle */}
      {sidebarCollapsed && (
        <button
          onClick={() => setSidebarCollapsed(false)}
          className="flex-shrink-0 w-7 border-r border-[var(--color-border)] flex items-center justify-center text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-colors"
          title="展开侧栏"
        >
          <ChevronRight size={14} />
        </button>
      )}

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {selectedPartitionId && (
          <div className="flex-shrink-0 border-b border-[var(--color-border)] bg-[var(--color-bg)]">
            <div className="max-w-3xl mx-auto px-6 py-3">
              <NodePathBreadcrumb />
            </div>
          </div>
        )}

        <KnowledgeTreeRecommendBanner partitionId={selectedPartitionId} />
        <ConversationMessageArea
          messages={messages}
          responseBlocks={responseBlocks}
          isLoading={isLoading}
          statusMessage={statusMessage}
          activeConversationId={activeConversationId}
          replyingToId={replyingToId}
          onSend={handleSend}
          onDeleteMessage={handleDeleteMessage}
          onEditMessage={handleEditMessage}
          onVersionSwitch={handleVersionSwitch}
          switchBanner={switchBanner}
          switchBannerPartitionName={switchBannerPartitionName}
          handleSwitchConfirm={handleSwitchConfirm}
          handleSwitchDismiss={handleSwitchDismiss}
          isInSubBranch={isInSubBranch}
          subBranchQuotedText={subBranchQuotedText}
          exitSubBranch={exitSubBranch}
          convError={convError}
        />
      </div>

      <NewNodeDialog
        open={showNewPartition}
        onClose={() => setShowNewPartition(false)}
        onCreate={handleCreatePartition}
        title="新建分区"
        namePlaceholder="例如: 高等数学"
        defaultEmoji="📐"
        nameLabel="分区名称"
      />
    </div>
  );
}

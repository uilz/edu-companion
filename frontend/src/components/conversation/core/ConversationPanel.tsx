"use client";

import React from "react";
import {
  Menu, Bot, ChevronLeft, ChevronRight, BarChart3,
} from "lucide-react";
import StudySidebar from "@/components/conversation/panels/StudySidebar";
import ConversationMessageArea from "@/components/conversation/core/ConversationMessageArea";
import MobileBottomSheet from "@/components/conversation/panels/MobileBottomSheet";
import type { UseConversationReturn } from "@/hooks/conversation/useConversation";
import { useConversationStore } from "@/store/conversation/conversation-store";
import { useTreeStore } from "@/store/conversation/tree-store";
import { NewNodeDialog } from "@/components/ui/NewNodeDialog";
import KnowledgeTreeRecommendBanner from "@/components/conversation/banners/KnowledgeTreeRecommendBanner";
import NodePathBreadcrumb from "@/components/conversation/tree/NodePathBreadcrumb";
import { useBreakpoint } from "@/hooks/useBreakpoint";

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



  const {
    dirList,
    selectedNodeId,
    selectedNodeType,
    messages,
    responseBlocks,
    isLoading,
    statusMessage,
    replyingToId,
    switchBanner,
    showDirSidebar,
    sidebarCollapsed,
    showNewDir,
    loadingDirList,
    convError,
    activeDir,
    handleSelectConversation,
    handleNewConversation,
    handleSend,
    handleDeleteMessage,
    handleEditMessage,
    handleVersionSwitch,
    handleCreateDirectory,
    handleRenameDirectory,
    handleSwitchConfirm,
    handleSwitchDismiss,
    setShowDirSidebar,
    setShowNewDir,
    setSidebarCollapsed,
    loadDirList,
  } = props;

  const { isDesktop } = useBreakpoint();

  const activeConversationId = selectedNodeType === "conv" ? selectedNodeId : null;

  const switchBannerPartitionName = React.useMemo(() => {
    if (!switchBanner?.dirId) return "";
    const p = dirList.find((pp) => pp.id === switchBanner.dirId);
    return p ? `${(p as { emoji?: string }).emoji || ""} ${(p as { name: string }).name}` : "";
  }, [dirList, switchBanner?.dirId]);

  // ── Mobile layout ──
  if (!isDesktop) {
    return (
      <div
        className="fixed inset-0 bg-[var(--color-bg)] z-30 flex flex-col"
        style={{ bottom: "var(--bottom-nav-height)" }}
      >
        <div className="flex-shrink-0 border-b border-[var(--color-border)] px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setShowDirSidebar(true)}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            style={{ minWidth: 44, minHeight: 44 }}
          >
            <Menu size={20} />
          </button>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-[var(--color-text)] truncate">
              {activeDir
                ? `${activeDir.emoji} ${activeDir.name}`
                : "对话"}
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-hidden flex flex-col">
          <KnowledgeTreeRecommendBanner />
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

        {showDirSidebar && (
          <MobileBottomSheet onClose={() => setShowDirSidebar(false)}>
            <StudySidebar
              selectedDirId={selectedNodeId}
              activeConversationId={activeConversationId}
              onSelectConversation={handleSelectConversation}
              onCreateDir={() => {
                setShowDirSidebar(false);
                setShowNewDir(true);
              }}
              loading={loadingDirList}
              onNewConversation={(level, parentId, partitionId) => {
                setShowDirSidebar(false);
                handleNewConversation(level, parentId, partitionId);
              }}
              onConversationReady={(pid, cid) => {
                setShowDirSidebar(false);
                handleSelectConversation(pid, cid);
              }}
              onTreeChanged={loadDirList}
              onSelectConv={(pid, cid) => {
                setShowDirSidebar(false);
                handleSelectConversation(pid, cid);
              }}
            />
          </MobileBottomSheet>
        )}

        <NewNodeDialog
          open={showNewDir}
          onClose={() => setShowNewDir(false)}
          onCreate={handleCreateDirectory}
          title="新建目录"
          namePlaceholder="例如: 机器学习"
          defaultEmoji="📐"
          nameLabel="目录名称"
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
                  onClick={() => setShowNewDir(true)}
                  className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
                  title="新建目录"
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
                key={`sidebar-${useTreeStore.getState().treeRefreshKey}`}
                selectedDirId={selectedNodeId}
                activeConversationId={activeConversationId}
                onSelectConversation={handleSelectConversation}
                onCreateDir={() => setShowNewDir(true)}
                onRenameDir={handleRenameDirectory}
                loading={loadingDirList}
                compact
                onNewConversation={handleNewConversation}
                onConversationReady={handleSelectConversation}
                onTreeChanged={loadDirList}
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
          style={{ minWidth: 44, minHeight: 44 }}
        >
          <ChevronRight size={14} />
        </button>
      )}

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-w-0">
        {selectedNodeId && (
          <div className="flex-shrink-0 border-b border-[var(--color-border)] bg-[var(--color-bg)]">
            <div className="max-w-3xl mx-auto px-6 py-3">
              <NodePathBreadcrumb />
            </div>
          </div>
        )}

        <KnowledgeTreeRecommendBanner />
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
        open={showNewDir}
        onClose={() => setShowNewDir(false)}
        onCreate={handleCreateDirectory}
        title="新建目录"
        namePlaceholder="例如: 机器学习"
        defaultEmoji="📐"
        nameLabel="目录名称"
      />
    </div>
  );
}

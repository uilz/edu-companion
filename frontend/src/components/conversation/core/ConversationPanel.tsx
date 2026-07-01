"use client";

import React from "react";
import {
  Menu, Bot, ChevronLeft, ChevronRight, List, GitBranch,
} from "lucide-react";
import StudySidebar from "@/components/conversation/panels/StudySidebar";
import ConversationMessageArea from "@/components/conversation/core/ConversationMessageArea";
import MobileBottomSheet from "@/components/conversation/panels/MobileBottomSheet";
import type { UseConversationReturn } from "@/hooks/conversation/useConversation";
import { useConversationStore } from "@/store/conversation/conversation-store";
import { useMessageStore } from "@/store/conversation/message-store";
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
  props: UseConversationReturn
) {
  const isInSubBranch = useConversationStore((s) => s.isInSubBranch);
  const exitSubBranch = useConversationStore((s) => s.exitSubBranch);
  const subBranchMessages = useMessageStore((s) => s.messages);
  const sidebarMode = useConversationStore((s) => s.sidebarMode);
  const setSidebarMode = useConversationStore((s) => s.setSidebarMode);
  const conversationMode = useConversationStore((s) => s.conversationMode);
  const createSubBranch = useConversationStore((s) => s.createSubBranch);
  const isFeynmanMode = conversationMode === "feynman";

  const subBranchQuotedText = React.useMemo(() => {
    if (!isInSubBranch) return "";
    const q = subBranchMessages[0]?.content_blocks?.find((b) => b.type === "quote");
    return q?.quoted_text || "";
  }, [isInSubBranch, subBranchMessages]);

  // ── 费曼讲学回调 ──
  const handleFeynmanTeach = React.useCallback(
    async (messageId: string, messageText: string, sourceConvId: string) => {
      if (!sourceConvId) return;
      // Create a feynman sub-branch from the AI's message
      await createSubBranch(
        sourceConvId,
        messageId,
        0,
        messageText.length,
        messageText.slice(0, 100),
        "我来给你讲讲这个知识点",
        "feynman",
      );
    },
    [createSubBranch],
  );


  const {
    dirList,
    selectedNodeId,
    selectedNodeType,
    messages,
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

  // ── Mobile: 选中节点变化时自动关闭侧边栏 ──
  const prevSelectedNodeId = React.useRef(selectedNodeId);
  React.useEffect(() => {
    if (!isDesktop && prevSelectedNodeId.current !== selectedNodeId) {
      if (showDirSidebar) setShowDirSidebar(false);
    }
    prevSelectedNodeId.current = selectedNodeId;
  }, [selectedNodeId, isDesktop, showDirSidebar, setShowDirSidebar]);

  const activeConversationId = selectedNodeType === "conv" ? selectedNodeId : null;

  const switchBannerPartitionName = React.useMemo(() => {
    if (!switchBanner?.dirId) return "";
    const p = dirList.find((pp) => pp.id === switchBanner.dirId);
    return p ? `${(p as { emoji?: string }).emoji || ""} ${(p as { name: string }).name}` : "";
  }, [dirList, switchBanner?.dirId]);

  // ── Mobile layout ──
  if (!isDesktop) {
    const headerTitle = activeDir
      ? `${activeDir.emoji} ${activeDir.name}`
      : "对话";

    return (
      <div
        className="fixed inset-0 bg-[var(--color-bg)] z-30 flex flex-col"
        style={{ bottom: "var(--bottom-nav-height)" }}
      >
        <div className="flex-1 overflow-hidden flex flex-col">
          <KnowledgeTreeRecommendBanner />
          <ConversationMessageArea
            messages={messages}
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
            isFeynmanMode={isFeynmanMode}
            onFeynmanTeach={handleFeynmanTeach}
            convError={convError}
            breadcrumb={
              <div className="flex items-center gap-3 py-3 px-1">
                <button
                  onClick={() => setShowDirSidebar(true)}
                  className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                  style={{ minWidth: 44, minHeight: 44 }}
                >
                  <Menu size={20} />
                </button>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-semibold text-[var(--color-text)] truncate">
                    {headerTitle}
                  </div>
                </div>
                <button
                  onClick={() => setSidebarMode(sidebarMode === "tree" ? "flat" : "tree")}
                  className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
                  style={{ minWidth: 44, minHeight: 44 }}
                  title={sidebarMode === "tree" ? "切换为扁平列表" : "切换为树状视图"}
                >
                  {sidebarMode === "tree" ? <List size={18} /> : <GitBranch size={18} />}
                </button>
                <button
                  onClick={() => {
                    (handleSelectConversation as (dirId: string | null, cid: string | null) => void)(null, null);
                    window.history.replaceState(null, "", "/conversation");
                  }}
                  className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
                  style={{ minWidth: 44, minHeight: 44 }}
                  title="临时新建会话"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </button>
              </div>
            }
          />
        </div>

        {showDirSidebar && (
          <MobileBottomSheet onClose={() => setShowDirSidebar(false)}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
              <span className="text-xs font-semibold text-[var(--color-text-muted)]">学习空间</span>
              <div className="flex items-center gap-0.5">
                <button
                  onClick={() => setSidebarMode(sidebarMode === "tree" ? "flat" : "tree")}
                  className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
                  title={sidebarMode === "tree" ? "切换为扁平列表" : "切换为树状视图"}
                >
                  {sidebarMode === "tree" ? <List size={15} /> : <GitBranch size={15} />}
                </button>
                <button
                  onClick={() => {
                    (handleSelectConversation as (dirId: string | null, cid: string | null) => void)(null, null);
                    setShowDirSidebar(false);
                    window.history.replaceState(null, "", "/conversation");
                  }}
                  className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
                  title="临时新建会话"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </button>
                {sidebarMode !== "flat" && (
                  <button
                    onClick={() => {
                      setShowDirSidebar(false);
                      setShowNewDir(true);
                    }}
                    className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
                    title="新建目录"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>
                  </button>
                )}
              </div>
            </div>
            <StudySidebar
              selectedDirId={selectedNodeId}
              activeConversationId={activeConversationId}
              onSelectConversation={handleSelectConversation}
              onCreateDir={() => {
                setShowDirSidebar(false);
                setShowNewDir(true);
              }}
              onRenameDir={handleRenameDirectory}
              loading={loadingDirList}
              compact
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
                  onClick={() => setSidebarMode(sidebarMode === "tree" ? "flat" : "tree")}
                  className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
                  title={sidebarMode === "tree" ? "切换为扁平列表" : "切换为树状视图"}
                >
                  {sidebarMode === "tree" ? <List size={15} /> : <GitBranch size={15} />}
                </button>
                <button
                  onClick={() => {
                    (handleSelectConversation as (dirId: string | null, cid: string | null) => void)(null, null);
                    window.history.replaceState(null, "", "/conversation");
                  }}
                  className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
                  title="临时新建会话"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </button>
                {sidebarMode !== "flat" && (
                  <button
                    onClick={() => setShowNewDir(true)}
                    className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
                    title="新建目录"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>
                  </button>
                )}
                <button
                  onClick={() => setSidebarCollapsed(true)}
                  className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
                  title="收起侧栏"
                >
                  <ChevronLeft size={14} />
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
        <KnowledgeTreeRecommendBanner />
        <ConversationMessageArea
          messages={messages}
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
          isFeynmanMode={isFeynmanMode}
          onFeynmanTeach={handleFeynmanTeach}
          convError={convError}
          breadcrumb={
            selectedNodeId ? (
              <div className="max-w-3xl mx-auto px-6 py-3">
                <NodePathBreadcrumb />
              </div>
            ) : undefined
          }
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

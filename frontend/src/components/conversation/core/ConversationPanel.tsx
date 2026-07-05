"use client";

import React from "react";
import {
  Menu, List, GitBranch,
} from "lucide-react";
import StudySidebar from "@/components/conversation/panels/StudySidebar";
import ConversationMessageArea from "@/components/conversation/core/ConversationMessageArea";
import MobileBottomSheet from "@/components/conversation/panels/MobileBottomSheet";
import type { UseConversationReturn } from "@/hooks/conversation/useConversation";
import { useConversationPanelPrefs, PANEL_BOUNDS } from "@/hooks/conversation/useConversationPanelPrefs";
import { useConversationStore } from "@/store/conversation/conversation-store";
import { useTreeStore } from "@/store/conversation/tree-store";
import { NewNodeDialog } from "@/components/ui/NewNodeDialog";
import KnowledgeTreeRecommendBanner from "@/components/conversation/banners/KnowledgeTreeRecommendBanner";
import { useBreakpoint } from "@/hooks/useBreakpoint";

/**
 * ConversationPanel — 对话面板主布局
 *
 * 桌面端：Workbench 中心区域的 2 栏布局
 *   ┌─────────────┬────────────────────────────────┐
 *   │ StudySidebar│  ConversationMessageArea        │
 *   │ (目录树)     │  (消息列表 + 输入框)             │
 *   └─────────────┴────────────────────────────────┘
 *
 * 移动端：全屏 + 底部抽屉
 */
export default function ConversationPanel(
  props: UseConversationReturn
) {
  const sidebarMode = useConversationStore((s) => s.sidebarMode);
  const setSidebarMode = useConversationStore((s) => s.setSidebarMode);
  const conversationMode = useConversationStore((s) => s.conversationMode);
  const selectedNode = useConversationStore((s) => s.selectedNode);
  const createSubBranch = useConversationStore((s) => s.createSubBranch);
  const isFeynmanMode = conversationMode === "feynman";
  const { pref, setWidth, toggleCollapsed } = useConversationPanelPrefs();

  // ── 费曼讲学回调 ──
  const handleFeynmanTeach = React.useCallback(
    async (messageId: string, messageText: string, sourceConvId: string) => {
      if (!sourceConvId) return;
      await createSubBranch(
        sourceConvId, messageId, 0, messageText.length,
        messageText.slice(0, 100), "我来给你讲讲这个知识点", "feynman",
      );
    },
    [createSubBranch],
  );

  const {
    selectedNodeId, selectedNodeType, messages, isLoading, statusMessage,
    replyingToId, switchBanner, showDirSidebar, showNewDir, loadingDirList,
    convError, activeDir, dirList,
    handleSelectConversation, handleNewConversation, handleSend,
    handleDeleteMessage, handleEditMessage, handleVersionSwitch,
    handleCreateDirectory, handleRenameDirectory,
    handleSwitchConfirm, handleSwitchDismiss,
    setShowDirSidebar, setShowNewDir, loadDirList,
  } = props;

  const { isDesktop } = useBreakpoint();

  // ── Mobile: 自动关闭侧边栏 ──
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
    const p = props.dirList.find((pp) => pp.id === switchBanner.dirId);
    return p ? `${(p as { emoji?: string }).emoji || ""} ${(p as { name: string }).name}` : "";
  }, [props.dirList, switchBanner?.dirId]);

  // ══════════════════════════════════════════════════════════
  //  Resize 处理
  // ══════════════════════════════════════════════════════════
  const contentRef = React.useRef<HTMLDivElement>(null);
  const handleResizerRef = React.useRef<{ startX: number; startW: number } | null>(null);

  const SIDEBAR_DEFAULT = PANEL_BOUNDS.leftSidebar.default;
  const MIN_SIDEBAR = PANEL_BOUNDS.leftSidebar.min;
  const MAX_SIDEBAR = PANEL_BOUNDS.leftSidebar.max;
  const COLLAPSE_THRESHOLD = 80;

  const onResizerPointerDown = React.useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      const curW = pref.leftSidebar.collapsed ? 0 : pref.leftSidebar.width;
      handleResizerRef.current = { startX: e.clientX, startW: curW };
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    },
    [pref],
  );

  React.useEffect(() => {
    const el = contentRef.current;
    if (!el) return;

    const onMove = (e: PointerEvent) => {
      const h = handleResizerRef.current;
      if (!h) return;
      const delta = e.clientX - h.startX;
      const newW = h.startW + delta;

      if (newW < COLLAPSE_THRESHOLD) {
        toggleCollapsed("leftSidebar");
        handleResizerRef.current = null;
        return;
      }
      const clamped = Math.max(MIN_SIDEBAR, Math.min(MAX_SIDEBAR, newW));
      setWidth("leftSidebar", clamped);
    };

    const onUp = () => {
      handleResizerRef.current = null;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, [setWidth, toggleCollapsed]);

  // ══════════════════════════════════════════════════════════
  //  MOBILE LAYOUT
  // ══════════════════════════════════════════════════════════
  if (!isDesktop) {
    const headerTitle = activeDir ? `${activeDir.emoji} ${activeDir.name}` : "对话";
    return (
      <div className="fixed inset-0 bg-[var(--color-bg)] z-30 flex flex-col" style={{ bottom: "var(--bottom-nav-height)" }}>
        <div className="flex-1 overflow-hidden flex flex-col">
          <KnowledgeTreeRecommendBanner />
          <div className="flex items-center gap-3 py-3 px-4 border-b border-[var(--color-border)] bg-[var(--color-bg)]">
            <button onClick={() => setShowDirSidebar(true)} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]" style={{ minWidth: 44, minHeight: 44 }}>
              <Menu size={20} />
            </button>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold text-[var(--color-text)] truncate">{headerTitle}</div>
            </div>
            <button onClick={() => setSidebarMode(sidebarMode === "tree" ? "flat" : "tree")}
              className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
              style={{ minWidth: 44, minHeight: 44 }}>
              {sidebarMode === "tree" ? <List size={18} /> : <GitBranch size={18} />}
            </button>
            <button onClick={() => {
              (handleSelectConversation as any)(null, null);
              window.history.replaceState(null, "", "/conversation");
            }} className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
              style={{ minWidth: 44, minHeight: 44 }}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </button>
          </div>
          <ConversationMessageArea
            messages={messages} isLoading={isLoading} statusMessage={statusMessage}
            activeConversationId={activeConversationId} replyingToId={replyingToId}
            onSend={handleSend} onDeleteMessage={handleDeleteMessage} onEditMessage={handleEditMessage}
            switchBanner={switchBanner} switchBannerPartitionName={switchBannerPartitionName}
            handleSwitchConfirm={handleSwitchConfirm} handleSwitchDismiss={handleSwitchDismiss}
            isFeynmanMode={isFeynmanMode} onFeynmanTeach={handleFeynmanTeach} convError={convError}
          />
        </div>
        {showDirSidebar && (
          <MobileBottomSheet onClose={() => setShowDirSidebar(false)}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
              <span className="text-xs font-semibold text-[var(--color-text-muted)]">学习空间</span>
              <div className="flex items-center gap-0.5">
                <button onClick={() => setSidebarMode(sidebarMode === "tree" ? "flat" : "tree")} className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]">
                  {sidebarMode === "tree" ? <List size={15} /> : <GitBranch size={15} />}
                </button>
                <button onClick={() => { (handleSelectConversation as any)(null, null); setShowDirSidebar(false); window.history.replaceState(null, "", "/conversation"); }} className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </button>
                {sidebarMode !== "flat" && (
                  <button onClick={() => { setShowDirSidebar(false); setShowNewDir(true); }} className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>
                  </button>
                )}
              </div>
            </div>
            <StudySidebar selectedDirId={selectedNodeId} activeConversationId={activeConversationId}
              onSelectConversation={handleSelectConversation} onCreateDir={() => { setShowDirSidebar(false); setShowNewDir(true); }}
              onRenameDir={handleRenameDirectory} loading={loadingDirList} compact
              onNewConversation={(l, p, di) => { setShowDirSidebar(false); handleNewConversation(l, p, di); }}
              onConversationReady={(p, c) => { setShowDirSidebar(false); handleSelectConversation(p, c); }}
              onTreeChanged={loadDirList} onSelectConv={(p, c) => { setShowDirSidebar(false); handleSelectConversation(p, c); }}
            />
          </MobileBottomSheet>
        )}
        <NewNodeDialog open={showNewDir} onClose={() => setShowNewDir(false)} onCreate={handleCreateDirectory}
          title="新建目录" namePlaceholder="例如: 机器学习" defaultEmoji="📐" nameLabel="目录名称" />
      </div>
    );
  }

  // ══════════════════════════════════════════════════════════
  //  DESKTOP LAYOUT — 2 栏 (sidebar + messages)
  //  由 Workbench 提供 TopBar / LeftPanel / RightPanel
  // ══════════════════════════════════════════════════════════
  const sidebarW = pref.leftSidebar.collapsed ? 0 : pref.leftSidebar.width;

  return (
    <div ref={contentRef} className="h-full flex overflow-hidden" style={{ position: "relative" }}>
      {/* ── Sidebar ── */}
      <div style={{
        width: sidebarW, flexShrink: 0,
        overflow: "hidden",
        display: "flex", flexDirection: "column",
        backgroundColor: "var(--color-sidebar-paper)",
        borderRight: "1px solid var(--color-divider)",
        transition: sidebarW === 0 ? "width 0.2s" : "none",
      }}>
        <div className="flex items-center justify-between px-2.5 py-2 border-b border-[var(--color-divider)]" style={{ flexShrink: 0 }}>
          <span className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--color-ink-primary)" }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>
            学习空间
          </span>
          <div className="flex items-center gap-0.5">
            <button onClick={() => setSidebarMode(sidebarMode === "tree" ? "flat" : "tree")}
              className="icon-btn" style={{ width: 26, height: 26 }}
              title={sidebarMode === "tree" ? "切换为扁平列表" : "切换为树状视图"}>
              {sidebarMode === "tree" ? <List size={13} /> : <GitBranch size={13} />}
            </button>
            <button onClick={() => { (handleSelectConversation as any)(null, null); window.history.replaceState(null, "", "/conversation"); }}
              className="icon-btn" style={{ width: 26, height: 26 }} title="临时新建会话">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            </button>
            {sidebarMode !== "flat" && (
              <button onClick={() => setShowNewDir(true)} className="icon-btn" style={{ width: 26, height: 26 }} title="新建目录">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14"/></svg>
              </button>
            )}
            <button onClick={() => toggleCollapsed("leftSidebar")} className="icon-btn" style={{ width: 26, height: 26 }} title="收起侧栏">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 18l-6-6 6-6"/></svg>
            </button>
          </div>
        </div>

        {/* 搜索 */}
        <div style={{ padding: "6px 8px", position: "relative", flexShrink: 0 }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ position: "absolute", left: 15, top: "50%", transform: "translateY(-50%)", color: "var(--color-ink-muted)" }}>
            <circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>
          </svg>
          <input type="text" placeholder="搜索..."
            style={{
              width: "100%", padding: "4px 8px 4px 24px", fontSize: 11.5, outline: "none",
              background: "var(--color-card)", border: "1px solid var(--color-divider)",
              borderRadius: 6, color: "var(--color-ink-primary)",
            }}
          />
        </div>

        <div className="flex-1 overflow-hidden">
          <StudySidebar
            key={`sidebar-${useTreeStore.getState().treeRefreshKey}`}
            selectedDirId={selectedNodeId} activeConversationId={activeConversationId}
            onSelectConversation={handleSelectConversation} onCreateDir={() => setShowNewDir(true)}
            onRenameDir={handleRenameDirectory} loading={loadingDirList} compact={false}
            onNewConversation={handleNewConversation} onConversationReady={handleSelectConversation}
            onTreeChanged={loadDirList} onSelectConv={handleSelectConversation}
          />
        </div>
      </div>

      {/* ── Resize handle ── */}
      <div
        onPointerDown={onResizerPointerDown}
        onDoubleClick={() => toggleCollapsed("leftSidebar")}
        style={{
          position: "absolute", top: 0, bottom: 0, zIndex: 50,
          left: sidebarW - 3, width: 6,
          cursor: "col-resize",
          background: "transparent",
        }}
        title="拖动调整 · 双击收起"
      />

      {/* ── Main: messages + input ── */}
      <div className="flex-1 flex flex-col min-w-0" style={{ backgroundColor: "var(--color-page-paper)" }}>
        <div style={{ maxWidth: 880, width: "100%", margin: "0 auto" }}>
          <KnowledgeTreeRecommendBanner />
        </div>
        <ConversationMessageArea
          messages={messages} isLoading={isLoading} statusMessage={statusMessage}
          activeConversationId={activeConversationId} replyingToId={replyingToId}
          onSend={handleSend} onDeleteMessage={handleDeleteMessage} onEditMessage={handleEditMessage}
          switchBanner={switchBanner} switchBannerPartitionName={switchBannerPartitionName}
          handleSwitchConfirm={handleSwitchConfirm} handleSwitchDismiss={handleSwitchDismiss}
          isFeynmanMode={isFeynmanMode} onFeynmanTeach={handleFeynmanTeach} convError={convError}
        />
      </div>

      {/* ── Collapsed expand button ── */}
      {pref.leftSidebar.collapsed && (
        <button onClick={() => toggleCollapsed("leftSidebar")}
          style={{
            position: "absolute", left: 0, top: "50%", transform: "translateY(-50%)",
            width: 24, height: 56, zIndex: 51,
            background: "var(--color-card)", border: "1px solid var(--color-divider)", borderLeft: "none",
            borderRadius: "0 6px 6px 0", cursor: "pointer", color: "var(--color-ink-muted)",
            display: "grid", placeItems: "center",
          }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18l6-6-6-6"/></svg>
        </button>
      )}

      <NewNodeDialog open={showNewDir} onClose={() => setShowNewDir(false)} onCreate={handleCreateDirectory}
        title="新建目录" namePlaceholder="例如: 机器学习" defaultEmoji="📐" nameLabel="目录名称" />
    </div>
  );
}

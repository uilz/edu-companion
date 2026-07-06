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
import ResizeHandle from "@/components/ui/ResizeHandle";

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
  const { pref, setWidth, setCollapsed, toggleCollapsed } = useConversationPanelPrefs();

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
  //  Resize 处理（委托给通用 ResizeHandle 组件）
  //
  //  使用总位移（totalDelta）：每次拖动始终从 pointerdown 时的
  //  初始宽度 + 鼠标总位移 计算，避免 rAF 节流下累积误差。
  // ══════════════════════════════════════════════════════════
  // ── 阈值 & 边界（基于默认宽度 x 的比例）──
  //   收起阈值 20%x · 展开阈值 25%x · 最小 30%x · 最大 150%x
  const LX = PANEL_BOUNDS.leftSidebar.default;     // 240
  const RX = PANEL_BOUNDS.rightPanel.default;       // 300
  const LEFT_COLLAPSE = Math.round(0.20 * LX);      // 48
  const LEFT_EXPAND   = Math.round(0.25 * LX);      // 60
  const RIGHT_COLLAPSE = Math.round(0.20 * RX);     // 60
  const RIGHT_EXPAND   = Math.round(0.25 * RX);     // 75

  const contentRef = React.useRef<HTMLDivElement>(null);
  const dragStartWidthRef = React.useRef(pref.leftSidebar.width);
  // 状态切换时记录"已消耗位移"，后续 effectiveDelta = totalDelta - consumed 使切换后从零算起
  const consumedDeltaRef = React.useRef(0);

  const handleResizeStart = React.useCallback(() => {
    dragStartWidthRef.current = pref.leftSidebar.collapsed ? 0 : pref.leftSidebar.width;
    consumedDeltaRef.current = 0;
  }, [pref]);

  const handleResize = React.useCallback(
    (totalDelta: number) => {
      const eff = totalDelta - consumedDeltaRef.current;
      const startW = pref.leftSidebar.collapsed ? 0 : dragStartWidthRef.current;
      const newW = startW + eff;

      if (pref.leftSidebar.collapsed) {
        // 收起态 → 拖出展开阈值(25%x)即展开
        if (eff >= LEFT_EXPAND) {
          const clamped = Math.max(PANEL_BOUNDS.leftSidebar.min, Math.min(PANEL_BOUNDS.leftSidebar.max, newW));
          setWidth("leftSidebar", clamped);
          setCollapsed("leftSidebar", false);
          dragStartWidthRef.current = clamped;
          consumedDeltaRef.current = totalDelta;
        }
      } else {
        // 展开态 → 拖入收起阈值(20%x)或低于 min 即收起
        if (eff <= -LEFT_COLLAPSE || newW < PANEL_BOUNDS.leftSidebar.min) {
          toggleCollapsed("leftSidebar");
          consumedDeltaRef.current = totalDelta;
          return;
        }
        const clamped = Math.max(PANEL_BOUNDS.leftSidebar.min, Math.min(PANEL_BOUNDS.leftSidebar.max, newW));
        setWidth("leftSidebar", clamped);
      }
    },
    [pref, setWidth, toggleCollapsed, setCollapsed],
  );

  // ══ 右栏 Drag ══
  const rightDragStartWidthRef = React.useRef(pref.rightPanel.width);
  const rightConsumedDeltaRef = React.useRef(0);

  const handleRightResizeStart = React.useCallback(() => {
    rightDragStartWidthRef.current = pref.rightPanel.collapsed ? 0 : pref.rightPanel.width;
    rightConsumedDeltaRef.current = 0;
  }, [pref]);

  const handleRightResize = React.useCallback(
    (totalDelta: number) => {
      const eff = totalDelta - rightConsumedDeltaRef.current;
      const startW = pref.rightPanel.collapsed ? 0 : rightDragStartWidthRef.current;
      const newW = startW - eff; // 向左拖 → totalDelta 负数 → newW 增大

      if (pref.rightPanel.collapsed) {
        // 收起态 → 向左拖出展开阈值(25%x)即展开
        if (eff <= -RIGHT_EXPAND) {
          const clamped = Math.max(PANEL_BOUNDS.rightPanel.min, Math.min(PANEL_BOUNDS.rightPanel.max, newW));
          setWidth("rightPanel", clamped);
          setCollapsed("rightPanel", false);
          rightDragStartWidthRef.current = clamped;
          rightConsumedDeltaRef.current = totalDelta;
        }
      } else {
        // 展开态 → 向右拖入收起阈值(20%x)或低于 min 即收起
        if (eff >= RIGHT_COLLAPSE || newW < PANEL_BOUNDS.rightPanel.min) {
          toggleCollapsed("rightPanel");
          rightConsumedDeltaRef.current = totalDelta;
          return;
        }
        const clamped = Math.max(PANEL_BOUNDS.rightPanel.min, Math.min(PANEL_BOUNDS.rightPanel.max, newW));
        setWidth("rightPanel", clamped);
      }
    },
    [pref, setWidth, toggleCollapsed, setCollapsed],
  );

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
  const rightPanelW = pref.rightPanel.collapsed ? 0 : pref.rightPanel.width;

  return (
    <div ref={contentRef} className="h-full flex" style={{ position: "relative" }}>
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
      <ResizeHandle
        orientation="horizontal"
        onResizeStart={handleResizeStart}
        onResize={handleResize}
        onDoubleClick={() => toggleCollapsed("leftSidebar")}
        collapsed={pref.leftSidebar.collapsed}
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

      {/* ── 右栏 Resize handle ── */}
      <ResizeHandle
        orientation="horizontal"
        onResizeStart={handleRightResizeStart}
        onResize={handleRightResize}
        onDoubleClick={() => toggleCollapsed("rightPanel")}
        collapsed={pref.rightPanel.collapsed}
      />

      {/* ── 右栏 ── */}
      <div style={{
        width: rightPanelW, flexShrink: 0,
        overflow: "hidden",
        display: "flex", flexDirection: "column",
        borderLeft: "1px solid var(--color-divider)",
        transition: rightPanelW === 0 ? "width 0.2s" : "none",
      }}>
        <div className="flex items-center justify-between px-2.5 py-2 border-b border-[var(--color-divider)]" style={{ flexShrink: 0 }}>
          <span className="flex items-center gap-1.5 text-xs font-semibold" style={{ color: "var(--color-ink-primary)" }}>
            详情
          </span>
        </div>
        <div className="flex-1 flex items-center justify-center text-xs" style={{ color: "var(--color-ink-muted)" }}>
          右栏内容
        </div>
      </div>

      {/* ── 左栏 Collapsed expand button ── */}
      {pref.leftSidebar.collapsed && (
        <button onClick={() => toggleCollapsed("leftSidebar")}
          style={{
            position: "absolute", left: 0, bottom: 12, top: "auto",
            width: 24, height: 56, zIndex: 51,
            background: "var(--color-card)", border: "1px solid var(--color-divider)", borderLeft: "none",
            borderRadius: "0 6px 6px 0", cursor: "pointer", color: "var(--color-ink-muted)",
            display: "grid", placeItems: "center",
          }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18l6-6-6-6"/></svg>
        </button>
      )}

      {/* ── Expanded collapse button（在左栏外侧边界） ── */}
      {!pref.leftSidebar.collapsed && (
        <button onClick={() => toggleCollapsed("leftSidebar")}
          style={{
            position: "absolute", left: sidebarW, bottom: 12, top: "auto",
            width: 24, height: 56, zIndex: 51,
            background: "var(--color-card)", border: "1px solid var(--color-divider)", borderLeft: "none",
            borderRadius: "0 6px 6px 0", cursor: "pointer", color: "var(--color-ink-muted)",
            display: "grid", placeItems: "center",
          }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 18l-6-6 6-6"/></svg>
        </button>
      )}

      {/* ── 右栏展开/收起按钮 ── */}
      {pref.rightPanel.collapsed && (
        <button onClick={() => toggleCollapsed("rightPanel")}
          style={{
            position: "absolute", right: 0, bottom: 12,
            width: 24, height: 56, zIndex: 51,
            background: "var(--color-card)", border: "1px solid var(--color-divider)", borderRight: "none",
            borderRadius: "6px 0 0 6px", cursor: "pointer", color: "var(--color-ink-muted)",
            display: "grid", placeItems: "center",
          }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 18l-6-6 6-6"/></svg>
        </button>
      )}
      {!pref.rightPanel.collapsed && (
        <button onClick={() => toggleCollapsed("rightPanel")}
          style={{
            position: "absolute", right: rightPanelW, bottom: 12,
            width: 24, height: 56, zIndex: 51,
            background: "var(--color-card)", border: "1px solid var(--color-divider)", borderRight: "none",
            borderRadius: "6px 0 0 6px", cursor: "pointer", color: "var(--color-ink-muted)",
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

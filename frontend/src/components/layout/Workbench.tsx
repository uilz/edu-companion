// ============================================================
// Workbench — 5 栏驾驶舱骨架 (任务 #76)
//
// 布局：
//   ┌──────────────────────────────────────────────┐
//   │  TopBar (resizable height)                   │  visible?
//   ├──────┬────────────────────────────┬─────────┤
//   │ L    │   Main (cockpit/children)    │  R       │
//   │      │                              │         │
//   ├──────┴────────────────────────────┴─────────┤
//   │  BottomBar (resizable height)                │  visible?
//   └──────────────────────────────────────────────┘
//
// 4 栏可 DIY：
//   - 拖动分隔条改尺寸（节流 + requestAnimationFrame）
//   - 双击分隔条折叠
//   - PanelHeader ◀/▶ 按钮折叠
//   - 设置页可见性开关
//   - 全部状态由 useLayoutPrefs 持久化到 localStorage
//
// SSR 安全：默认 pref 渲染完成 → useEffect 同步 localStorage → 一次性切换。
// 移动端 fallback：< 1024px 时不渲染 Workbench，由 AppShell 走 MobileDrawer / BottomNav。
// ============================================================

"use client";

import { type ReactNode, useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useBreakpoint } from "@/hooks/useBreakpoint";
import { useLayoutPrefs, PANEL_BOUNDS } from "@/hooks/useLayoutPrefs";
import { PanelContentProvider, usePanelContent } from "@/contexts/PanelContentContext";
import ResizableContainer from "./ResizableContainer";
import TopBar from "./TopBar";
import BottomBar from "./BottomBar";
import LeftPanel from "./LeftPanel";
import RightPanel from "./RightPanel";
import Cockpit from "@/components/dashboard/Cockpit";
import { Home } from "lucide-react";
import ResizeHandle from "@/components/ui/ResizeHandle";

export interface WorkbenchProps {
  /** 当前路由对应的页面内容 */
  children: ReactNode;
}

/**
 * Cockpit 自动接管 /dashboard 路由，其他路径渲染 children。
 * 路径前缀包含 /dashboard 时进入智能驾驶舱模式。
 */
function useIsCockpitRoute(): boolean {
  const pathname = usePathname() || "/";
  return pathname === "/" || pathname === "/dashboard" || pathname.startsWith("/dashboard/");
}

/** 对话路由 → 隐藏全局右栏，由 ConversationPanel 自管 */
function useIsConversationRoute(): boolean {
  const pathname = usePathname() || "/";
  return pathname === "/conversation" || pathname.startsWith("/conversation/");
}

// ── 内部组件：读取 context 决定 RightPanel 内容 ──
function WorkbenchInner({ children }: WorkbenchProps) {
  const { rightPanel } = usePanelContent();

  // 当页面设置了自定义右栏时使用，否则用默认
  const renderRight = rightPanel ?? <RightPanel />;

  return <>{renderRight}</>;
}

export default function Workbench({ children }: WorkbenchProps) {
  const { isDesktop, isMounted } = useBreakpoint();
  const { pref, setWidth, setHeight, toggleCollapsed } = useLayoutPrefs();
  const router = useRouter();
  const isCockpit = useIsCockpitRoute();
  const isConversation = useIsConversationRoute();

  // 右栏拖拽初始宽度 ref — 用于总位移计算
  const rightDragStartWidthRef = useRef(0);

  // 移动端：完全不渲染 Workbench，由 AppShell 走 BottomNav / MobileDrawer 分支
  if (!isMounted) {
    return (
      <div className="min-h-screen bg-page flex items-center justify-center text-ink-muted text-sm">
        加载中…
      </div>
    );
  }
  if (!isDesktop) return null;

  // ── 实际尺寸（折叠时取 collapsedSize）──
  const topH = pref.topBar.collapsed
    ? PANEL_BOUNDS.topBar.collapsed
    : (pref.topBar.height ?? PANEL_BOUNDS.topBar.default);
  const bottomH = pref.bottomBar.collapsed
    ? PANEL_BOUNDS.bottomBar.collapsed
    : (pref.bottomBar.height ?? PANEL_BOUNDS.bottomBar.default);
  const leftW = pref.leftPanel.collapsed
    ? PANEL_BOUNDS.leftPanel.collapsed
    : (pref.leftPanel.width ?? PANEL_BOUNDS.leftPanel.default);
  const rightW = pref.rightPanel.collapsed
    ? PANEL_BOUNDS.rightPanel.collapsed
    : (pref.rightPanel.width ?? PANEL_BOUNDS.rightPanel.default);

  // ── CSS Grid 模板 ──
  // 行：topBar / mid / bottomBar
  // 列：leftPanel / main / rightPanel
  const gridRows = [
    pref.topBar.visible ? `${topH}px` : "0px",
    "1fr",
    pref.bottomBar.visible ? `${bottomH}px` : "0px",
  ].join(" ");
  const gridCols = [
    pref.leftPanel.visible ? `${leftW}px` : "0px",
    "1fr",
    pref.rightPanel.visible ? `${rightW}px` : "0px",
  ].join(" ");

  return (
    <PanelContentProvider>
      <div
        className="h-screen w-screen overflow-hidden bg-page text-ink-primary"
        style={{
          display: "grid",
          gridTemplateRows: gridRows,
          gridTemplateColumns: gridCols,
        }}
      >
        {/* ── 顶栏 (row 1, col 1 / -1) ── */}
        {pref.topBar.visible && (
          <div
            className="row-start-1 col-span-3 min-w-0 overflow-hidden"
            style={{ gridColumn: "1 / -1" }}
          >
            <ResizableContainer
              visible
              size={topH}
              collapsed={pref.topBar.collapsed}
              direction="vertical"
              minSize={PANEL_BOUNDS.topBar.min}
              maxSize={PANEL_BOUNDS.topBar.max}
              collapsedSize={PANEL_BOUNDS.topBar.collapsed}
              onResize={(s) => setHeight("topBar", s)}
              onResizeEnd={(s) => setHeight("topBar", s)}
              onToggleCollapse={() => toggleCollapsed("topBar")}
              title="顶栏"
              hideHeader
              resizable
              className="h-full"
            >
              <TopBar />
            </ResizableContainer>
          </div>
        )}

        {/* ── 左栏 (row 2, col 1) ── */}
        {pref.leftPanel.visible && (
          <div className="row-start-2 col-start-1 min-h-0 overflow-hidden border-r border-divider">
            <ResizableContainer
              visible
              size={leftW}
              collapsed={pref.leftPanel.collapsed}
              direction="horizontal"
              minSize={PANEL_BOUNDS.leftPanel.min}
              maxSize={PANEL_BOUNDS.leftPanel.max}
              collapsedSize={PANEL_BOUNDS.leftPanel.collapsed}
              onResize={(s) => setWidth("leftPanel", s)}
              onResizeEnd={(s) => setWidth("leftPanel", s)}
              onToggleCollapse={() => toggleCollapsed("leftPanel")}
              title="导航"
              headerRight={
                pref.leftPanel.collapsed ? (
                  <button
                    onClick={() => router.push("/")}
                    className="p-1 rounded text-ink-muted hover:text-ink-primary hover:bg-surface-hover"
                    title="首页"
                  >
                    <Home size={14} />
                  </button>
                ) : undefined
              }
              resizable
              className="h-full"
            >
              <LeftPanel />
            </ResizableContainer>
          </div>
        )}

        {/* ── 中心 Main (row 2, col 2) ── */}
        <div className="row-start-2 col-start-2 min-h-0 min-w-0 overflow-y-auto bg-page">
          {isCockpit ? <Cockpit /> : children}
        </div>

        {/* ── 右栏 (row 2, col 3) — 对话路由全局隐藏，由 ConversationPanel 自管 ── */}
        {!isConversation && pref.rightPanel.visible && (
          <div className="row-start-2 col-start-3 min-h-0 border-l border-divider relative" style={{ overflow: 'visible' }}>
            <ResizeHandle
              orientation="horizontal"
              onResizeStart={() => { rightDragStartWidthRef.current = pref.rightPanel.collapsed ? 0 : rightW; }}
              onResize={(totalDelta) => setWidth("rightPanel", rightDragStartWidthRef.current - totalDelta)}
              onDoubleClick={() => toggleCollapsed("rightPanel")}
              collapsed={pref.rightPanel.collapsed}
              style={{ position: 'absolute', left: -3, top: 0, bottom: 0, zIndex: 10 }}
            />
            <ResizableContainer
              visible
              size={rightW}
              collapsed={pref.rightPanel.collapsed}
              direction="horizontal"
              minSize={PANEL_BOUNDS.rightPanel.min}
              maxSize={PANEL_BOUNDS.rightPanel.max}
              collapsedSize={PANEL_BOUNDS.rightPanel.collapsed}
              onResize={(s) => setWidth("rightPanel", s)}
              onResizeEnd={(s) => setWidth("rightPanel", s)}
              onToggleCollapse={() => toggleCollapsed("rightPanel")}
              title="工作面板"
              className="h-full"
            >
              <WorkbenchInner>{children}</WorkbenchInner>
            </ResizableContainer>

            {/* ── 右栏展开/收起按钮（放在右栏 div 内，relative 定位） ── */}
            {pref.rightPanel.collapsed && (
              <button onClick={() => toggleCollapsed("rightPanel")}
                style={{
                  position: "absolute", left: -24, bottom: 12,
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
                  position: "absolute", left: -24, bottom: 12,
                  width: 24, height: 56, zIndex: 51,
                  background: "var(--color-card)", border: "1px solid var(--color-divider)", borderRight: "none",
                  borderRadius: "6px 0 0 6px", cursor: "pointer", color: "var(--color-ink-muted)",
                  display: "grid", placeItems: "center",
                }}>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M9 18l6-6-6-6"/></svg>
              </button>
            )}
          </div>
        )}

        {/* ── 底栏 (row 3, col 1 / -1) ── */}
        {pref.bottomBar.visible && (
          <div
            className="row-start-3 col-span-3 min-w-0 overflow-hidden"
            style={{ gridColumn: "1 / -1" }}
          >
            <ResizableContainer
              visible
              size={bottomH}
              collapsed={pref.bottomBar.collapsed}
              direction="vertical"
              minSize={PANEL_BOUNDS.bottomBar.min}
              maxSize={PANEL_BOUNDS.bottomBar.max}
              collapsedSize={PANEL_BOUNDS.bottomBar.collapsed}
              onResize={(s) => setHeight("bottomBar", s)}
              onResizeEnd={(s) => setHeight("bottomBar", s)}
              onToggleCollapse={() => toggleCollapsed("bottomBar")}
              title="底栏"
              hideHeader
              resizable
              className="h-full"
            >
              <BottomBar />
            </ResizableContainer>
          </div>
        )}
      </div>
    </PanelContentProvider>
  );
}

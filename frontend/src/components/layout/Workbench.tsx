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
//   - 拖动分隔栏 / 胶囊按钮改尺寸
//   - 双击分隔栏折叠 / 展开
//   - 胶囊按钮单击切换 collapsed
//   - 设置页可见性开关
//   - 全部状态由 useLayoutPrefs 持久化到 localStorage
//
// SSR 安全：默认 pref 渲染完成 → useEffect 同步 localStorage → 一次性切换。
// 移动端 fallback：< 1024px 时不渲染 Workbench，由 AppShell 走 MobileDrawer / BottomNav。
// ============================================================

"use client";

import { type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Home } from "lucide-react";
import { useBreakpoint } from "@/hooks/useBreakpoint";
import { useLayoutPrefs, PANEL_BOUNDS, type PanelKey, type PanelState } from "@/hooks/useLayoutPrefs";
import { PanelContentProvider, usePanelContent } from "@/contexts/PanelContentContext";
import ResizableContainer from "./ResizableContainer";
import TopBar from "./TopBar";
import BottomBar from "./BottomBar";
import LeftPanel from "./LeftPanel";
import RightPanel from "./RightPanel";
import Cockpit from "@/components/dashboard/Cockpit";

export interface WorkbenchProps {
  /** 当前路由对应的页面内容 */
  children: ReactNode;
}

/**
 * Cockpit 仅接管 /dashboard/ 子路由，/ 和 /dashboard 渲染 children。
 * 任务 #120: 秘书仪表盘替代首页。
 */
function useIsCockpitRoute(): boolean {
  const pathname = usePathname() || "/";
  return pathname.startsWith("/dashboard/") && pathname !== "/dashboard";
}

/** 对话路由 → 隐藏全局右栏，由 ConversationPanel 自管 */
function useIsConversationRoute(): boolean {
  const pathname = usePathname() || "/";
  return pathname === "/conversation" || pathname.startsWith("/conversation/");
}

// ── 内部组件：读取 context 决定 RightPanel 内容 ──
function WorkbenchInner({ children }: WorkbenchProps) {
  const { rightPanel } = usePanelContent();
  const renderRight = rightPanel ?? <RightPanel />;
  return <>{renderRight}</>;
}

export default function Workbench({ children }: WorkbenchProps) {
  const { isDesktop, isMounted } = useBreakpoint();
  const { pref, isReady, setWidth, setHeight, setState } = useLayoutPrefs();
  const router = useRouter();
  const isCockpit = useIsCockpitRoute();
  const isConversation = useIsConversationRoute();

  // 挂载 / 布局偏好加载完成前：避免用默认值闪烁渲染
  if (!isMounted || !isReady) {
    return (
      <div className="min-h-screen bg-page flex items-center justify-center text-ink-muted text-sm">
        加载中…
      </div>
    );
  }
  if (!isDesktop) return null;

  // ── 根据状态计算实际渲染尺寸 ──
  const sizeFor = (key: PanelKey, userSize: number | undefined, defaultSize: number, collapsedSize: number) => {
    const s = pref[key].state;
    if (s === "fullyCollapsed") return 0;
    if (s === "collapsed") return collapsedSize;
    return userSize ?? defaultSize;
  };

  const topH = sizeFor("topBar", pref.topBar.height, PANEL_BOUNDS.topBar.default, PANEL_BOUNDS.topBar.collapsed);
  const bottomH = sizeFor("bottomBar", pref.bottomBar.height, PANEL_BOUNDS.bottomBar.default, PANEL_BOUNDS.bottomBar.collapsed);
  const leftW = sizeFor("leftPanel", pref.leftPanel.width, PANEL_BOUNDS.leftPanel.default, PANEL_BOUNDS.leftPanel.collapsed);
  const rightW = sizeFor("rightPanel", pref.rightPanel.width, PANEL_BOUNDS.rightPanel.default, PANEL_BOUNDS.rightPanel.collapsed);

  // ── CSS Grid 模板 ──
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

  // 右栏拖拽时，Workbench 需要把总位移传给 setWidth
  // ResizableContainer 内部基于当前 renderSize 计算 delta，这里直接透传
  const handleResize = (key: PanelKey) => (size: number) => {
    if (key === "topBar" || key === "bottomBar") {
      setHeight(key, size);
    } else {
      setWidth(key, size);
    }
  };

  const handleStateChange = (key: PanelKey) => (state: PanelState) => {
    setState(key, state);
  };

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
            className="row-start-1 col-span-3 min-w-0"
            style={{ gridColumn: "1 / -1" }}
          >
            <ResizableContainer
              visible
              size={topH}
              state={pref.topBar.state}
              direction="vertical"
              panelPosition="top"
              minSize={PANEL_BOUNDS.topBar.min}
              maxSize={PANEL_BOUNDS.topBar.max}
              collapsedSize={PANEL_BOUNDS.topBar.collapsed}
              panelKey="topBar"
              onResize={handleResize("topBar")}
              onResizeEnd={(size) => setHeight("topBar", size)}
              onStateChange={handleStateChange("topBar")}
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
          <div className="row-start-2 col-start-1 min-h-0 border-r border-divider">
            <ResizableContainer
              visible
              size={leftW}
              state={pref.leftPanel.state}
              direction="horizontal"
              panelPosition="left"
              minSize={PANEL_BOUNDS.leftPanel.min}
              maxSize={PANEL_BOUNDS.leftPanel.max}
              collapsedSize={PANEL_BOUNDS.leftPanel.collapsed}
              panelKey="leftPanel"
              onResize={handleResize("leftPanel")}
              onResizeEnd={(size) => setWidth("leftPanel", size)}
              onStateChange={handleStateChange("leftPanel")}
              title="导航"
              headerRight={
                pref.leftPanel.state !== "expanded" ? (
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
          <div className="row-start-2 col-start-3 min-h-0 border-l border-divider relative">
            <ResizableContainer
              visible
              size={rightW}
              state={pref.rightPanel.state}
              direction="horizontal"
              panelPosition="right"
              minSize={PANEL_BOUNDS.rightPanel.min}
              maxSize={PANEL_BOUNDS.rightPanel.max}
              collapsedSize={PANEL_BOUNDS.rightPanel.collapsed}
              panelKey="rightPanel"
              onResize={handleResize("rightPanel")}
              onResizeEnd={(size) => setWidth("rightPanel", size)}
              onStateChange={handleStateChange("rightPanel")}
              title="工作面板"
              className="h-full"
            >
              <WorkbenchInner>{children}</WorkbenchInner>
            </ResizableContainer>
          </div>
        )}

        {/* ── 底栏 (row 3, col 1 / -1) ── */}
        {pref.bottomBar.visible && (
          <div
            className="row-start-3 col-span-3 min-w-0"
            style={{ gridColumn: "1 / -1" }}
          >
            <ResizableContainer
              visible
              size={bottomH}
              state={pref.bottomBar.state}
              direction="vertical"
              panelPosition="bottom"
              minSize={PANEL_BOUNDS.bottomBar.min}
              maxSize={PANEL_BOUNDS.bottomBar.max}
              collapsedSize={PANEL_BOUNDS.bottomBar.collapsed}
              panelKey="bottomBar"
              onResize={handleResize("bottomBar")}
              onResizeEnd={(size) => setHeight("bottomBar", size)}
              onStateChange={handleStateChange("bottomBar")}
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

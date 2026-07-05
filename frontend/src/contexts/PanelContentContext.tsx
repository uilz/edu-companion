// ============================================================
// PanelContentContext — 页面声明面板插槽内容
//
// 允许页面覆盖 Workbench 的 RightPanel 内容和 TopBar 面包屑。
// 页面在 useEffect 中设置内容，离开时自动清空。
//
// 使用：
//   const { setRightPanel, setBreadcrumbs } = usePanelContent();
//   useEffect(() => {
//     setRightPanel(<RightInfoPanel ... />);
//     setBreadcrumbs([{ label: "驾驶舱", href: "/" }, { label: "当前页面" }]);
//     return () => { setRightPanel(null); setBreadcrumbs([]); };
//   }, [deps]);
// ============================================================

"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

// ── 面包屑项 ──
export interface BreadcrumbItem {
  label: string;
  href?: string;
}

// ── Context 值 ──
interface PanelContentValue {
  /** 右栏自定义内容（null = 使用默认 RightPanel） */
  rightPanel: ReactNode;
  /** 顶栏面包屑（空数组 = 显示默认路径名） */
  breadcrumbs: BreadcrumbItem[];
  /** 设置右栏内容 */
  setRightPanel: (node: ReactNode) => void;
  /** 设置顶栏面包屑 */
  setBreadcrumbs: (crumbs: BreadcrumbItem[]) => void;
}

const PanelContentContext = createContext<PanelContentValue>({
  rightPanel: null,
  breadcrumbs: [],
  setRightPanel: () => {},
  setBreadcrumbs: () => {},
});

export function PanelContentProvider({ children }: { children: ReactNode }) {
  const [rightPanel, setRightPanel] = useState<ReactNode>(null);
  const [breadcrumbs, setBreadcrumbs] = useState<BreadcrumbItem[]>([]);

  return (
    <PanelContentContext.Provider
      value={{ rightPanel, breadcrumbs, setRightPanel, setBreadcrumbs }}
    >
      {children}
    </PanelContentContext.Provider>
  );
}

export function usePanelContent() {
  return useContext(PanelContentContext);
}

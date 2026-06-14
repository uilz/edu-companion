// ══════════════════════════════════════════════════════════════
//  useTreeLayout — 知识图谱布局偏好管理
//
//  封装 LayoutPreference 的读写和 localStorage 持久化。
// ══════════════════════════════════════════════════════════════

import { useState, useEffect } from "react";
import type { GraphMode } from "@/components/knowledge-tree/KnowledgeTreePage";

export interface LayoutPreference {
  showDialogPanel: boolean;
  showDetailPanel: boolean;
  dialogWidth: number;
  detailWidth: number;
  graphMode: GraphMode;
  layerOpen: boolean;
  maxDisplayLevel: string | undefined;
}

const STORAGE_KEY = "knowledge-tree-layout";

function loadLayout(): LayoutPreference {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  return {
    showDialogPanel: true,
    showDetailPanel: false,
    dialogWidth: 320,
    detailWidth: 320,
    graphMode: "mindmap",
    layerOpen: true,
    maxDisplayLevel: undefined,
  };
}

export function useTreeLayout() {
  const [layoutPref, setLayoutPref] = useState<LayoutPreference>(loadLayout);

  // 自动持久化到 localStorage
  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(layoutPref)); } catch { /* ignore */ }
  }, [layoutPref]);

  return { layoutPref, setLayoutPref };
}

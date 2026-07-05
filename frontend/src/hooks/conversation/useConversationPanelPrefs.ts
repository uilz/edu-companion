// ══════════════════════════════════════════════════════════════
// useConversationPanelPrefs — 对话页左/右栏尺寸 + 折叠状态持久化
//
// 与 Workbench 的 useLayoutPrefs 隔离，不共用 leftPanel/rightPanel
// 语义（Workbench 的 leftPanel = 56px 主导航）。
//
// 持久化到 localStorage key: conversation-panel-prefs
// 跨 tab 同步：自定义事件 + storage 事件
// ══════════════════════════════════════════════════════════════

"use client";

import { useCallback, useEffect, useState } from "react";

// ── 边界常量 ────────────────────────────────────────
export const PANEL_BOUNDS = {
  leftSidebar: { min: 200, max: 400, default: 280, collapsed: 4 },
  rightPanel: { min: 240, max: 400, default: 300, collapsed: 0 },
} as const;

type PanelKey = "leftSidebar" | "rightPanel";

interface PanelPref {
  width: number;
  collapsed: boolean;
}

export interface ConversationPanelPrefs {
  leftSidebar: PanelPref;
  rightPanel: PanelPref;
}

const DEFAULTS: ConversationPanelPrefs = {
  leftSidebar: { width: PANEL_BOUNDS.leftSidebar.default, collapsed: false },
  rightPanel: { width: PANEL_BOUNDS.rightPanel.default, collapsed: true },
};

const STORAGE_KEY = "conversation-panel-prefs";
const STORAGE_EVENT = "conversation-panel-prefs-storage";
const NATIVE_STORAGE_EVENT = "storage";

// ── 工具 ────────────────────────────────────────────

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function sanitize(input: unknown): ConversationPanelPrefs {
  if (!input || typeof input !== "object") return DEFAULTS;
  const obj = input as Record<string, unknown>;
  const safe = (key: PanelKey, fallback: PanelPref): PanelPref => {
    const raw = obj[key] as PanelPref | undefined;
    if (!raw || typeof raw !== "object") return fallback;
    const b = PANEL_BOUNDS[key];
    return {
      width: typeof raw.width === "number"
        ? clamp(raw.width, b.collapsed || b.min, b.max)
        : fallback.width,
      collapsed: typeof raw.collapsed === "boolean" ? raw.collapsed : fallback.collapsed,
    };
  };
  return {
    leftSidebar: safe("leftSidebar", DEFAULTS.leftSidebar),
    rightPanel: safe("rightPanel", DEFAULTS.rightPanel),
  };
}

function readFromStorage(): ConversationPanelPrefs {
  if (typeof window === "undefined") return DEFAULTS;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    return sanitize(JSON.parse(raw));
  } catch {
    return DEFAULTS;
  }
}

function writeToStorage(pref: ConversationPanelPrefs) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(pref));
  } catch {
    // 隐私模式 / 配额超限：静默忽略
  }
}

// ── Hook ────────────────────────────────────────────

export function useConversationPanelPrefs() {
  const [pref, setPrefState] = useState<ConversationPanelPrefs>(DEFAULTS);
  const [ready, setReady] = useState(false);

  // 首次挂载：从 localStorage 读
  useEffect(() => {
    setPrefState(readFromStorage());
    setReady(true);
  }, []);

  // 跨 tab / 跨组件同步
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) {
        setPrefState(readFromStorage());
      }
    };
    const onCustom = () => setPrefState(readFromStorage());
    window.addEventListener(NATIVE_STORAGE_EVENT, onStorage);
    window.addEventListener(STORAGE_EVENT, onCustom);
    return () => {
      window.removeEventListener(NATIVE_STORAGE_EVENT, onStorage);
      window.removeEventListener(STORAGE_EVENT, onCustom);
    };
  }, []);

  const setPref = useCallback((updater: ConversationPanelPrefs | ((p: ConversationPanelPrefs) => ConversationPanelPrefs)) => {
    setPrefState((prev) => {
      const next = typeof updater === "function" ? updater(prev) : updater;
      const sanitized = sanitize(next);
      writeToStorage(sanitized);
      if (typeof window !== "undefined") {
        window.dispatchEvent(new Event(STORAGE_EVENT));
      }
      return sanitized;
    });
  }, []);

  const setWidth = useCallback(
    (key: PanelKey, width: number) => {
      const b = PANEL_BOUNDS[key];
      setPref((p) => ({
        ...p,
        [key]: { ...p[key], width: clamp(width, b.collapsed || b.min, b.max) },
      }));
    },
    [setPref],
  );

  const toggleCollapsed = useCallback(
    (key: PanelKey) => {
      setPref((p) => ({ ...p, [key]: { ...p[key], collapsed: !p[key].collapsed } }));
    },
    [setPref],
  );

  const setCollapsed = useCallback(
    (key: PanelKey, collapsed: boolean) => {
      setPref((p) => ({ ...p, [key]: { ...p[key], collapsed } }));
    },
    [setPref],
  );

  return {
    pref,
    ready,
    setWidth,
    toggleCollapsed,
    setCollapsed,
  };
}

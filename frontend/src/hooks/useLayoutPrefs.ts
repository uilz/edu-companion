// ============================================================
// useLayoutPrefs — 全局布局偏好 (任务 #76: 5 栏驾驶舱 + 4 栏 DIY)
//
// 单一数据源 (Single Source of Truth)：
//   4 个 panel (topBar / bottomBar / leftPanel / rightPanel) 的：
//   - visible    是否渲染
//   - width/height 实际尺寸 (px)
//   - state      expanded | collapsed | fullyCollapsed
//
// 状态语义：
//   - expanded       正常展开（width/height 为用户设定值）
//   - collapsed      窄边栏（保留图标/触发条，宽度为 collapsed 值）
//   - fullyCollapsed 完全折叠（只留分隔栏 + 胶囊按钮）
//
// 持久化策略：
//   - 优先 localStorage (key: layout-pref)
//   - localStorage 不可用时回退到内存默认值
//   - 跨 tab 同步：通过 storage 事件
//   - 跨组件同步：自定义事件 layout-pref-changed
//
// 约束：
//   - 所有尺寸 min/max 边界由 setWidth/setHeight 内部强制
// ============================================================

"use client";

import { useCallback, useEffect, useState } from "react";

// ── 边界常量 (与设计语言保持一致) ────────────────────────

export type PanelState = "expanded" | "collapsed" | "fullyCollapsed";

export const PANEL_BOUNDS = {
  topBar: { min: 40, max: 96, default: 56, collapsed: 32 },
  bottomBar: { min: 32, max: 80, default: 40, collapsed: 24 },
  leftPanel: { min: 160, max: 400, default: 280, collapsed: 56 },
  rightPanel: { min: 200, max: 500, default: 320, collapsed: 56 },
} as const;

export type PanelKey = keyof typeof PANEL_BOUNDS;

// ── 形状 ───────────────────────────────────────────────

export interface PanelPref {
  visible: boolean;
  width?: number;
  height?: number;
  state: PanelState;
}

export interface LayoutPref {
  topBar: PanelPref;
  bottomBar: PanelPref;
  leftPanel: PanelPref;
  rightPanel: PanelPref;
}

// ── 默认值 ─────────────────────────────────────────────

export const DEFAULT_LAYOUT_PREF: LayoutPref = {
  topBar: { visible: true, height: PANEL_BOUNDS.topBar.default, state: "expanded" },
  bottomBar: { visible: true, height: PANEL_BOUNDS.bottomBar.default, state: "expanded" },
  leftPanel: { visible: true, width: PANEL_BOUNDS.leftPanel.default, state: "expanded" },
  rightPanel: { visible: true, width: PANEL_BOUNDS.rightPanel.default, state: "expanded" },
};

const STORAGE_KEY = "layout-pref";
const STORAGE_EVENT = "layout-pref-storage";
const NATIVE_STORAGE_EVENT = "storage";

// ── 工具 ───────────────────────────────────────────────

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

function isPanelState(v: unknown): v is PanelState {
  return v === "expanded" || v === "collapsed" || v === "fullyCollapsed";
}

function sanitize(input: unknown): LayoutPref {
  if (!input || typeof input !== "object") return DEFAULT_LAYOUT_PREF;
  const obj = input as Record<string, unknown>;
  const safe = (key: PanelKey, fallback: PanelPref): PanelPref => {
    const raw = obj[key] as PanelPref | undefined;
    if (!raw || typeof raw !== "object") return fallback;
    const b = PANEL_BOUNDS[key];
    return {
      visible: typeof raw.visible === "boolean" ? raw.visible : fallback.visible,
      width: typeof raw.width === "number"
        ? clamp(raw.width, b.min, b.max)
        : fallback.width,
      height: typeof raw.height === "number"
        ? clamp(raw.height, b.min, b.max)
        : fallback.height,
      state: isPanelState(raw.state) ? raw.state : fallback.state,
    };
  };
  return {
    topBar: safe("topBar", DEFAULT_LAYOUT_PREF.topBar),
    bottomBar: safe("bottomBar", DEFAULT_LAYOUT_PREF.bottomBar),
    leftPanel: safe("leftPanel", DEFAULT_LAYOUT_PREF.leftPanel),
    rightPanel: safe("rightPanel", DEFAULT_LAYOUT_PREF.rightPanel),
  };
}

function readFromStorage(): LayoutPref {
  if (typeof window === "undefined") return DEFAULT_LAYOUT_PREF;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_LAYOUT_PREF;
    return sanitize(JSON.parse(raw));
  } catch {
    return DEFAULT_LAYOUT_PREF;
  }
}

function writeToStorage(pref: LayoutPref) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(pref));
  } catch {
    // 隐私模式 / 配额超限：静默忽略，仍有内存状态
  }
}

// ── Hook ───────────────────────────────────────────────

export function useLayoutPrefs() {
  const [pref, setPrefState] = useState<LayoutPref>(DEFAULT_LAYOUT_PREF);
  const [isReady, setIsReady] = useState(false);

  // 首次挂载：从 localStorage 读
  useEffect(() => {
    setPrefState(readFromStorage());
    setIsReady(true);
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

  // 写操作：setter 包一层，统一处理持久化 + 事件
  const setPref = useCallback((updater: LayoutPref | ((p: LayoutPref) => LayoutPref)) => {
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

  // ── 操作 API ──

  const toggleVisible = useCallback(
    (key: PanelKey) => {
      setPref((p) => ({ ...p, [key]: { ...p[key], visible: !p[key].visible } }));
    },
    [setPref],
  );

  const setState = useCallback(
    (key: PanelKey, state: PanelState) => {
      setPref((p) => {
        const next = { ...p[key], state };
        if (state === "expanded") {
          const b = PANEL_BOUNDS[key];
          if (key === "topBar" || key === "bottomBar") {
            next.height = Math.max(b.min, p[key].height ?? b.default);
          } else {
            next.width = Math.max(b.min, p[key].width ?? b.default);
          }
        }
        return { ...p, [key]: next };
      });
    },
    [setPref],
  );

  const toggleCollapsed = useCallback(
    (key: PanelKey) => {
      setPref((p) => {
        const current = p[key].state;
        const nextState: PanelState = current === "expanded" ? "collapsed" : "expanded";
        const next = { ...p[key], state: nextState };
        if (nextState === "expanded") {
          const b = PANEL_BOUNDS[key];
          if (key === "topBar" || key === "bottomBar") {
            next.height = Math.max(b.min, p[key].height ?? b.default);
          } else {
            next.width = Math.max(b.min, p[key].width ?? b.default);
          }
        }
        return { ...p, [key]: next };
      });
    },
    [setPref],
  );

  const setWidth = useCallback(
    (key: PanelKey, width: number) => {
      const b = PANEL_BOUNDS[key];
      setPref((p) => ({
        ...p,
        [key]: { ...p[key], width: clamp(width, 0, b.max) },
      }));
    },
    [setPref],
  );

  const setHeight = useCallback(
    (key: PanelKey, height: number) => {
      const b = PANEL_BOUNDS[key];
      setPref((p) => ({
        ...p,
        [key]: { ...p[key], height: clamp(height, 0, b.max) },
      }));
    },
    [setPref],
  );

  const resetAll = useCallback(() => {
    setPref(DEFAULT_LAYOUT_PREF);
  }, [setPref]);

  return {
    pref,
    isReady,
    toggleVisible,
    setState,
    toggleCollapsed,
    setWidth,
    setHeight,
    setPref,
    resetAll,
  };
}

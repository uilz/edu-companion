// ============================================================
// useLayoutPrefs — 全局布局偏好 (任务 #76: 5 栏驾驶舱 + 4 栏 DIY)
//
// 单一数据源 (Single Source of Truth)：
//   4 个 panel (topBar / bottomBar / leftPanel / rightPanel) 的：
//   - visible    是否渲染
//   - width/height 实际尺寸 (px)
//   - collapsed  是否折叠（折叠时退化为最小尺寸）
//
// 持久化策略：
//   - 优先 localStorage (key: layout-pref)
//   - localStorage 不可用（SSR / 隐私模式）时回退到内存默认值
//   - 跨 tab 同步：通过 storage 事件
//   - 跨组件同步：自定义事件 layout-pref-changed
//
// 约束：
//   - 所有尺寸 min/max 边界由 setWidth/setHeight 内部强制
//   - 折叠 = 收缩到 0 + 留一条窄边（panel 实际渲染最小尺寸）
//
// 任务 #76 验收：SSR 安全 + 持久化 + 跨 tab 同步。
// ============================================================

"use client";

import { useCallback, useEffect, useState, useRef } from "react";

// ── 边界常量 (与设计语言保持一致) ────────────────────────

export const PANEL_BOUNDS = {
  topBar: { min: 40, max: 96, default: 56, collapsed: 0 },
  bottomBar: { min: 32, max: 80, default: 40, collapsed: 0 },
  leftPanel: { min: 56, max: 400, default: 280, collapsed: 56 },
  rightPanel: { min: 200, max: 500, default: 320, collapsed: 4 },
} as const;

export type PanelKey = keyof typeof PANEL_BOUNDS;

// ── 形状 ───────────────────────────────────────────────

export interface PanelPref {
  visible: boolean;
  width?: number;
  height?: number;
  collapsed: boolean;
}

export interface LayoutPref {
  topBar: PanelPref;
  bottomBar: PanelPref;
  leftPanel: PanelPref;
  rightPanel: PanelPref;
}

// ── 默认值 ─────────────────────────────────────────────

export const DEFAULT_LAYOUT_PREF: LayoutPref = {
  topBar: { visible: true, height: PANEL_BOUNDS.topBar.default, collapsed: false },
  bottomBar: { visible: true, height: PANEL_BOUNDS.bottomBar.default, collapsed: false },
  leftPanel: { visible: true, width: PANEL_BOUNDS.leftPanel.default, collapsed: false },
  rightPanel: { visible: true, width: PANEL_BOUNDS.rightPanel.default, collapsed: false },
};

const STORAGE_KEY = "layout-pref";
const STORAGE_EVENT = "layout-pref-storage"; // 自定义事件：跨组件实时同步
const NATIVE_STORAGE_EVENT = "storage"; // 跨 tab

// ── 工具 ───────────────────────────────────────────────

function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
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
        ? clamp(raw.width, b.collapsed || b.min, b.max)
        : fallback.width,
      height: typeof raw.height === "number"
        ? clamp(raw.height, b.collapsed || b.min, b.max)
        : fallback.height,
      collapsed: typeof raw.collapsed === "boolean" ? raw.collapsed : fallback.collapsed,
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
  // SSR 安全：服务端无 localStorage
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

/**
 * useLayoutPrefs — 读写 5 栏布局偏好
 *
 * 关键约定：
 *   - 初始状态为 DEFAULT_LAYOUT_PREF（SSR 占位），首挂载时立即从 localStorage 同步，
 *     避免 SSR 闪烁
 *   - 所有 setter 内部会强制约束尺寸到合法范围
 *   - 写操作同时更新 localStorage + 派发自定义事件
 */
export function useLayoutPrefs() {
  const [pref, setPrefState] = useState<LayoutPref>(DEFAULT_LAYOUT_PREF);
  const isFirstRender = useRef(true);

  // 首次挂载：从 localStorage 读
  useEffect(() => {
    setPrefState(readFromStorage());
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
      // 派发自定义事件通知同 tab 其他组件
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

  const toggleCollapsed = useCallback(
    (key: PanelKey) => {
      setPref((p) => ({ ...p, [key]: { ...p[key], collapsed: !p[key].collapsed } }));
    },
    [setPref],
  );

  const setWidth = useCallback(
    (key: PanelKey, width: number) => {
      const b = PANEL_BOUNDS[key];
      if (b.collapsed === undefined) return; // 非 width 类型
      setPref((p) => ({
        ...p,
        [key]: { ...p[key], width: clamp(width, b.collapsed || b.min, b.max) },
      }));
    },
    [setPref],
  );

  const setHeight = useCallback(
    (key: PanelKey, height: number) => {
      const b = PANEL_BOUNDS[key];
      if (b.collapsed === undefined) return; // 非 height 类型
      setPref((p) => ({
        ...p,
        [key]: { ...p[key], height: clamp(height, b.collapsed || b.min, b.max) },
      }));
    },
    [setPref],
  );

  const resetAll = useCallback(() => {
    setPref(DEFAULT_LAYOUT_PREF);
  }, [setPref]);

  // 首次 render 时跳过 storage 写入（避免 mount 时把 default 覆盖回去）
  // 实际逻辑：writeToStorage 在 setPref 内部被调用，而 setPref 仅在用户操作时被调用。

  return {
    pref,
    isReady: !isFirstRender.current,
    toggleVisible,
    toggleCollapsed,
    setWidth,
    setHeight,
    setPref,
    resetAll,
  };
}

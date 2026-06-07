// ══════════════════════════════════════════════════════════════
//  NotificationPreferenceStore — 通知偏好设置
//
//  管理用户对通知的个性化偏好：按源开关、优先级阈值等。
//  通过 localStorage 持久化，必要时同步到后端。
// ══════════════════════════════════════════════════════════════

import { create } from "zustand";
import type { NotificationSource } from "./types";

// ══════════════════════════════════════════════════════════════
//  Types
// ══════════════════════════════════════════════════════════════

export interface NotificationPreference {
  /** 按通知来源启用/禁用 */
  sourceEnabled: Record<NotificationSource, boolean>;
  /** 优先级阈值：只显示 >= 此值的通知 (1-5) */
  priorityThreshold: number;
  /** 免打扰开始时间 HH:mm */
  quietHoursStart: string;
  /** 免打扰结束时间 HH:mm */
  quietHoursEnd: string;
  /** 每日推送上限 (0 = 无限) */
  dailyPushLimit: number;
}

const STORAGE_KEY = "edu-companion:notification-preferences";

const DEFAULT_PREFS: NotificationPreference = {
  sourceEnabled: {
    secretary: true,
    context_switch: true,
    tree_recommendation: true,
    temp_recommendation: true,
    job_update: true,
  },
  priorityThreshold: 1,
  quietHoursStart: "22:00",
  quietHoursEnd: "08:00",
  dailyPushLimit: 0,
};

/** 从 localStorage 读取 */
function loadPrefs(): NotificationPreference {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      // 合并默认值，确保新字段有值
      return { ...DEFAULT_PREFS, ...parsed, sourceEnabled: { ...DEFAULT_PREFS.sourceEnabled, ...parsed.sourceEnabled } };
    }
  } catch {
    // ignore
  }
  return { ...DEFAULT_PREFS, sourceEnabled: { ...DEFAULT_PREFS.sourceEnabled } };
}

/** 写入 localStorage */
function savePrefs(prefs: NotificationPreference) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // ignore
  }
}

// ══════════════════════════════════════════════════════════════
//  Store
// ══════════════════════════════════════════════════════════════

export interface NotificationPreferenceState {
  prefs: NotificationPreference;

  /** 更新整个偏好（覆盖合并） */
  updatePrefs: (patch: Partial<NotificationPreference>) => void;

  /** 设置某个通知源开关 */
  setSourceEnabled: (source: NotificationSource, enabled: boolean) => void;

  /** 重置为默认 */
  resetPrefs: () => void;

  /** 判断当前是否在免打扰时段 */
  isInQuietHours: () => boolean;

  /** 生成一个过滤对象（供 NotificationFilter 使用） */
  toFilter: () => { priorityMin?: number; enabledSources?: NotificationSource[] };
}

export const useNotificationPreferenceStore = create<NotificationPreferenceState>((set, get) => ({
  prefs: loadPrefs(),

  updatePrefs: (patch) =>
    set((s) => {
      const next = { ...s.prefs, ...patch };
      savePrefs(next);
      return { prefs: next };
    }),

  setSourceEnabled: (source, enabled) =>
    set((s) => {
      const next = {
        ...s.prefs,
        sourceEnabled: { ...s.prefs.sourceEnabled, [source]: enabled },
      };
      savePrefs(next);
      return { prefs: next };
    }),

  resetPrefs: () => {
    const defaults = { ...DEFAULT_PREFS, sourceEnabled: { ...DEFAULT_PREFS.sourceEnabled } };
    savePrefs(defaults);
    set({ prefs: defaults });
  },

  isInQuietHours: () => {
    const { quietHoursStart, quietHoursEnd } = get().prefs;
    const now = new Date();
    const currentMinutes = now.getHours() * 60 + now.getMinutes();

    const [startH, startM] = quietHoursStart.split(":").map(Number);
    const [endH, endM] = quietHoursEnd.split(":").map(Number);
    const startMinutes = startH * 60 + startM;
    const endMinutes = endH * 60 + endM;

    if (startMinutes <= endMinutes) {
      // 同一天内: 22:00 ~ 08:00 跨天，不会进入此分支
      return currentMinutes >= startMinutes && currentMinutes <= endMinutes;
    } else {
      // 跨天: 22:00 ~ 08:00
      return currentMinutes >= startMinutes || currentMinutes <= endMinutes;
    }
  },

  toFilter: () => {
    const { prefs } = get();
    const filter: { priorityMin?: number; enabledSources?: NotificationSource[] } = {};
    if (prefs.priorityThreshold > 1) {
      filter.priorityMin = prefs.priorityThreshold;
    }
    const enabledSources = (Object.entries(prefs.sourceEnabled) as [NotificationSource, boolean][])
      .filter(([, enabled]) => enabled)
      .map(([source]) => source);
    // 只有当有源被禁用时才传递
    if (enabledSources.length < Object.keys(prefs.sourceEnabled).length) {
      filter.enabledSources = enabledSources;
    }
    return filter;
  },
}));

/** 快捷 API：检查通知是否应展示（基于用户偏好） */
export function isNotificationVisibleByPreference(
  source: NotificationSource,
  priority: number,
): boolean {
  const { prefs, isInQuietHours } = useNotificationPreferenceStore.getState();
  if (!prefs.sourceEnabled[source]) return false;
  if (priority < prefs.priorityThreshold) return false;
  if (isInQuietHours()) return false;
  return true;
}
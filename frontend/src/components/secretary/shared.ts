import type {
  SecretaryNotification, PageType, ActionType, NotificationSource,
} from "@/store/notification/types";

// ══════════════════════════════════════════════════════════════
//  Constants
// ══════════════════════════════════════════════════════════════

export const SOURCE_OPTIONS: { value: NotificationSource | ""; label: string }[] = [
  { value: "", label: "全部来源" },
  { value: "secretary", label: "秘书引擎" },
  { value: "context_switch", label: "上下文切换" },
  { value: "tree_recommendation", label: "知识树推荐" },
  { value: "temp_recommendation", label: "会话推荐" },
  { value: "job_update", label: "后台任务" },
];

export const ACTION_TYPE_OPTIONS: { value: ActionType | ""; label: string }[] = [
  { value: "", label: "全部类型" },
  { value: "review", label: "复习" },
  { value: "practice", label: "练习" },
  { value: "rest", label: "休息" },
  { value: "explore", label: "探索" },
  { value: "exam_prep", label: "备考" },
];

export const ACTION_TYPE_LABELS: Record<string, string> = {
  review: "复习",
  practice: "练习",
  rest: "休息",
  explore: "探索",
  exam_prep: "备考",
};

export const SNOOZE_PRESETS = [
  { label: "1 小时", ms: 60 * 60 * 1000 },
  { label: "4 小时", ms: 4 * 60 * 60 * 1000 },
  { label: "明天", ms: 24 * 60 * 60 * 1000 },
];

export const PRIORITY_LABELS: Record<number, string> = {
  1: "低",
  2: "较低",
  3: "中",
  4: "高",
  5: "紧急",
};

// ══════════════════════════════════════════════════════════════
//  Types
// ══════════════════════════════════════════════════════════════

export type TabKey = "pending" | "snoozed" | "history" | "events";
export type ViewMode = "flat" | "grouped";

export interface ProposalItem {
  id: string;
  emoji: string;
  title: string;
  description: string;
  action_type: string;
  priority: number;
  status: string;
  created_at?: string;
}

export interface SnapshotData {
  cognitive_load: number;
  weak_count: number;
  stagnant_count: number;
  streak_days: number;
  summary: string;
}

// ══════════════════════════════════════════════════════════════
//  Helper: convert API item to SecretaryNotification
// ══════════════════════════════════════════════════════════════

export function toNotification(p: ProposalItem): SecretaryNotification {
  return {
    id: p.id,
    emoji: p.emoji,
    title: p.title,
    description: p.description,
    priority: p.priority,
    target: { pages: ["learn" as PageType] },
    source: "secretary",
    actionType: (p.action_type || undefined) as ActionType | undefined,
    sourceModule: "secretary",
    read: false,
    status: "pending",
    created_at: p.created_at ? new Date(p.created_at).getTime() : Date.now(),
  };
}
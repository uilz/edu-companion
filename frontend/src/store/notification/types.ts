// ══════════════════════════════════════════════════════════════
//  Notification System — Type Definitions
//
//  统一通知模型，支持页面感知路由和内联对话注入。
// ══════════════════════════════════════════════════════════════

/** 页面类型 — 通知可以路由到的目标页面 */
export type PageType =
  | "learn"           // 学习空间（对话）
  | "dashboard"       // 驾驶舱
  | "practice"        // 练习中心
  | "knowledge-tree"  // 知识树
  | "secretary"       // 秘书面板
  | "files"           // 文件管理
  | "settings";      // 设置

/** 通知来源 */
export type NotificationSource =
  | "secretary"              // 秘书引擎
  | "context_switch"         // 上下文切换推荐
  | "tree_recommendation"    // 知识树推荐
  | "temp_recommendation"    // 临时会话推荐
  | "job_update";           // 后台任务更新

/** 动作类型 — 对应后端 Proposal.action_type */
export type ActionType =
  | "review"
  | "practice"
  | "rest"
  | "explore"
  | "exam_prep"
  | "";

/** 通知路由目标 */
export interface NotificationTarget {
  /** 在哪些页面显示通知栏 */
  pages: PageType[];
  /** 可选：关联的资源 ID（用于深度链接） */
  resourceId?: string;
  /** 可选：深度链接路径 */
  actionPath?: string;
  /** 可选：如果有此字段，通知还会注入到指定对话的消息列表中 */
  inlineConversationId?: string;
}

/** 通知状态 */
export type NotificationStatus = "pending" | "accepted" | "dismissed" | "snoozed" | "deleted";

/** 统一通知模型 */
export interface SecretaryNotification {
  id: string;
  emoji: string;
  title: string;
  description: string;
  priority: number; // 1-5, 5 最高
  target: NotificationTarget;
  source: NotificationSource;
  actionType?: ActionType;        // 后端 action_type
  sourceModule?: string;          // 后端 generated_by（来源模块名）
  read: boolean;
  status: NotificationStatus;
  created_at: number;

  // ── 延后 / 隐藏（仅前端） ──
  snoozedUntil?: number;          // 时间戳，未到时不显示
  hidden?: boolean;               // 用户手动隐藏
}

/** 通知筛选条件 */
export interface NotificationFilter {
  source?: NotificationSource;
  sourceModule?: string;          // 按来源模块名过滤
  actionType?: ActionType;
  priorityMin?: number;
  priorityMax?: number;
  page?: PageType;
  search?: string;                // 标题/描述全文搜索
}

/** 历史记录条目（后端 history API 返回格式） */
export interface NotificationHistoryItem {
  id: string;
  proposal: {
    emoji: string;
    title: string;
    description: string;
    action_type: string;
    payload: unknown;
    priority: number;
    generated_by: string;
    overrideable: boolean;
  };
  status: string;
  created_at: string;
  metadata: unknown;
}

/** 秘书更新 WS 事件载荷 */
export interface SecretaryUpdatePayload {
  reason: string[];
  proposal_count: number;
}

/** 动作执行结果反馈 */
export interface ActionResult {
  success?: boolean;
  message?: string;
  details?: string;
  generated_count?: number;
  target_node_id?: string;
}

/** 动作反馈（UI 用） */
export interface ActionFeedback {
  id: string;
  proposalId: string;
  actionType: ActionType;
  title: string;
  result: ActionResult | null;
  planAdjustment: Record<string, unknown> | null;
  timestamp: number;
}
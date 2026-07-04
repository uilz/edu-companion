/**
 * 集中导航配置 — 统一 404 / 兜底 / 跨页面跳链
 *
 * Task #87 重建（原源文件丢失）
 *
 * 设计：
 *   - HOME_PATH 是所有「回首页」按钮的汇聚点
 *   - DEFAULT_NAV_CONTEXT 给 useUser 等 hook 兜底
 *   - UserRole / SubscriptionTier 决定导航项可见性
 */

export const HOME_PATH = "/dashboard";

/** 抽象用户角色 */
export type UserRole = "student" | "guest";

/** 订阅档位 */
export type SubscriptionTier = "free" | "pro" | "enterprise";

/** 导航上下文 — 跨组件共享 */
export interface NavContext {
  userRole: UserRole;
  subscriptionTier: SubscriptionTier;
}

export const DEFAULT_NAV_CONTEXT: NavContext = {
  userRole: "guest",
  subscriptionTier: "free",
};

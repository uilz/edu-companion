"use client";

import { useState } from "react";
import { ChevronDown, FlaskConical, X } from "lucide-react";
import {
  ROLE_LABELS,
  TIER_LABELS,
  type UserRole,
  type SubscriptionTier,
} from "@/lib/navConfig";
import { useUser } from "@/hooks/useUser";

// 任务 #45：admin 已从主前端移除（admin 走独立 3001 项目），dev 切换器
// 不再提供 admin 档位。只保留 student（已登录）与 guest（未登录）2 档。
const ALL_ROLES: UserRole[] = ["guest", "student"];
const ALL_TIERS: SubscriptionTier[] = ["free", "pro", "enterprise"];

/**
 * DevRoleSwitcher — 开发模式角色 / 订阅档位切换器（任务 #34 / 任务 #45）。
 *
 * - 浮窗位于右下角，仅在 dev 模式可见
 * - 提供真实角色 vs 覆盖值的视觉对比
 * - 覆盖值会写入 localStorage，触发 useUser 重渲染
 * - "重置" 按钮清除 localStorage 恢复真实身份
 * - 任务 #45：admin 已从主前端移除 → 角色档位变为 2（student / guest），
 *   订阅档位保持 3（free / pro / enterprise）
 *
 * 生产环境可通过 NEXT_PUBLIC_NAV_DEV_SWITCHER=off 关闭
 * （未来如需更复杂的环境控制可扩展）
 */
export default function DevRoleSwitcher() {
  const { user, userRole, subscriptionTier, hasDevOverride, setDevOverride, clearDevOverride } = useUser();
  const [open, setOpen] = useState(false);

  // 生产构建时整组件不渲染
  if (process.env.NODE_ENV === "production") return null;

  return (
    <div className="fixed bottom-3 right-3 z-[100] font-mono text-xs">
      {open ? (
        <div
          className="bg-[var(--color-card)] border border-[var(--color-border)] rounded-lg shadow-2xl p-3 w-72 space-y-3"
          data-testid="dev-role-switcher"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 font-semibold text-[var(--color-text)]">
              <FlaskConical size={12} className="text-[var(--color-warning)]" />
              Dev Role Switcher
            </div>
            <button
              onClick={() => setOpen(false)}
              className="p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)]"
              aria-label="关闭"
            >
              <X size={12} />
            </button>
          </div>

          {/* 真实身份显示 */}
          <div className="text-[10px] text-[var(--color-text-muted)] space-y-0.5">
            <div>
              真实身份:{" "}
              <span className="text-[var(--color-text)]">
                {user ? `${user.username} (${user.role})` : "未登录"}
              </span>
            </div>
            <div>
              当前生效:{" "}
              <span className="text-[var(--color-accent)]">
                {ROLE_LABELS[userRole]} · {TIER_LABELS[subscriptionTier]}
              </span>
              {hasDevOverride && (
                <span className="ml-1 text-[var(--color-warning)]">[覆盖]</span>
              )}
            </div>
          </div>

          {/* 角色切换 */}
          <div>
            <div className="text-[10px] text-[var(--color-text-muted)] mb-1">
              User Role
            </div>
            <div className="grid grid-cols-2 gap-1">
              {ALL_ROLES.map((r) => {
                const active = userRole === r;
                return (
                  <button
                    key={r}
                    onClick={() => setDevOverride({ userRole: r, subscriptionTier })}
                    className={`px-2 py-1.5 rounded text-[10px] transition-colors ${
                      active
                        ? "bg-[var(--color-accent)] text-white"
                        : "bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:bg-[var(--color-hover)]"
                    }`}
                  >
                    {ROLE_LABELS[r]}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 档位切换 */}
          <div>
            <div className="text-[10px] text-[var(--color-text-muted)] mb-1">
              Subscription Tier
            </div>
            <div className="grid grid-cols-3 gap-1">
              {ALL_TIERS.map((t) => {
                const active = subscriptionTier === t;
                return (
                  <button
                    key={t}
                    onClick={() => setDevOverride({ userRole, subscriptionTier: t })}
                    className={`px-2 py-1.5 rounded text-[10px] transition-colors ${
                      active
                        ? "bg-[var(--color-accent)] text-white"
                        : "bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:bg-[var(--color-hover)]"
                    }`}
                  >
                    {TIER_LABELS[t]}
                  </button>
                );
              })}
            </div>
          </div>

          {/* 重置按钮 */}
          <div className="flex gap-1.5">
            <button
              onClick={() => clearDevOverride()}
              disabled={!hasDevOverride}
              className="flex-1 px-2 py-1.5 rounded text-[10px] bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:bg-[var(--color-hover)] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              重置为真实身份
            </button>
          </div>

          <div className="text-[9px] text-[var(--color-text-muted)] leading-relaxed">
            注：仅在 dev 模式可见。覆盖值仅存在 localStorage，
            刷新或清缓存后恢复真实角色。
          </div>
        </div>
      ) : (
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-full bg-[var(--color-card)] border border-[var(--color-border)] shadow-lg text-[var(--color-text-secondary)] hover:text-[var(--color-text)] hover:border-[var(--color-accent)] transition-colors"
          data-testid="dev-role-switcher-trigger"
        >
          <FlaskConical size={12} className="text-[var(--color-warning)]" />
          <span>
            {ROLE_LABELS[userRole]} · {TIER_LABELS[subscriptionTier]}
          </span>
          <ChevronDown size={10} />
        </button>
      )}
    </div>
  );
}

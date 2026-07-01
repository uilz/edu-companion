"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuthStore } from "./auth-store";
import type { AdminRole } from "./types";

const TABS: { href: string; label: string; icon: string; min: AdminRole }[] = [
  { href: "/users", label: "用户管理", icon: "\uD83D\uDC65", min: "super_admin" },
  { href: "/data", label: "全局数据", icon: "\uD83D\uDCCA", min: "data_admin" },
  { href: "/monitor", label: "系统监控", icon: "\uD83D\uDCE1", min: "analyst" },
  { href: "/analytics", label: "BI 分析", icon: "\uD83D\uDCC8", min: "analyst" },
  { href: "/settings", label: "系统设置", icon: "\u2699\uFE0F", min: "super_admin" },
];

const ROLE_CLASS: Record<string, string> = {
  super_admin: "bg-danger/15 text-danger border border-danger/20",
  data_admin: "bg-accent/15 text-accent border border-accent/20",
  analyst: "bg-success/15 text-success border border-success/20",
  user: "bg-ink-muted/15 text-ink-muted border border-divider",
};

export function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, sync, logout, can } = useAuthStore();

  useEffect(() => {
    sync();
  }, [pathname, sync]);

  function handleLogout() {
    logout();
    window.location.href = "/login";
  }

  return (
    <header className="sticky top-0 z-50 flex items-center gap-4 px-6 h-[52px]
                        bg-surface-elevated border-b border-divider shadow-sm">
      <Link href="/" className="flex items-center gap-2 font-bold text-body text-ink-primary no-underline whitespace-nowrap">
        <span className="text-accent">&#x1F6E1;&#xFE0F;</span>
        <span>Edu Admin</span>
      </Link>

      <nav className="flex gap-0.5 flex-1 overflow-x-auto py-1">
        {TABS.map((t) => {
          if (!can(t.min)) return null;
          const active = pathname?.startsWith(t.href);
          return (
            <Link
              key={t.href}
              href={t.href}
              className={`px-3.5 py-1.5 rounded-md text-caption font-medium whitespace-nowrap transition-colors duration-fast
                ${active
                  ? "bg-accent text-white shadow-glow"
                  : "text-ink-secondary hover:bg-accent-soft hover:text-ink-primary"
                }`}
            >
              <span className="mr-1">{t.icon}</span>
              {t.label}
            </Link>
          );
        })}
      </nav>

      <div className="flex items-center gap-2 flex-shrink-0">
        {user ? (
          <>
            <span className="text-caption text-ink-secondary">
              {user.username}
              <span className={`ml-1 px-1.5 py-0.5 rounded-full text-fine font-semibold ${ROLE_CLASS[user.role] || ROLE_CLASS.user}`}>
                {user.role}
              </span>
            </span>
            <button
              onClick={handleLogout}
              className="px-3 py-1 rounded-md text-fine text-ink-secondary border border-divider
                         hover:bg-surface-hover hover:text-ink-primary transition-colors duration-fast"
            >
              退出
            </button>
          </>
        ) : (
          <Link
            href="/login"
            className="px-3 py-1 rounded-md text-fine text-ink-secondary border border-divider
                       hover:bg-surface-hover hover:text-ink-primary transition-colors duration-fast"
          >
            登录
          </Link>
        )}
      </div>
    </header>
  );
}

"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { clearSession, getCurrentUser, hasRole, type AdminRole, type AdminUser } from "@/lib/api";

const TABS: { href: string; label: string; min: AdminRole }[] = [
  { href: "/users", label: "用户管理", min: "super_admin" },
  { href: "/data", label: "全局数据", min: "data_admin" },
  { href: "/monitor", label: "系统监控", min: "analyst" },
  { href: "/analytics", label: "BI 分析", min: "analyst" },
];

export function Topbar() {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<AdminUser | null>(null);

  useEffect(() => {
    setUser(getCurrentUser());
  }, [pathname]);

  function logout() {
    clearSession();
    router.push("/login");
  }

  return (
    <header className="topbar">
      <div className="brand">🛡️ Edu Admin</div>
      <nav className="tabs">
        {TABS.map((t) => {
          const ok = hasRole(user?.role, t.min);
          if (!ok) return null;
          const active = pathname?.startsWith(t.href);
          return (
            <Link key={t.href} href={t.href} className={active ? "tab active" : "tab"}>
              {t.label}
            </Link>
          );
        })}
      </nav>
      <div className="userbox">
        {user ? (
          <>
            <span className="user-info">
              {user.username} <span className={`role-pill role-${user.role}`}>{user.role}</span>
            </span>
            <button onClick={logout} className="btn-sm">退出</button>
          </>
        ) : (
          <Link href="/login" className="btn-sm">登录</Link>
        )}
      </div>
    </header>
  );
}

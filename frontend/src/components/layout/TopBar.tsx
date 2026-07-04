// ============================================================
// TopBar — 顶栏 (任务 #76)
//
// 设计目标：
//   - 高度 56px (默认)，可被 Workbench 拖动调整
//   - 左侧：Logo 折叠按钮 / 搜索 ⌘K
//   - 中部：可扩展（命令面板弹层）
//   - 右侧：同步状态 / Pro 徽章 / 用户菜单 / AI 唤起 ⌘J
//
// 风格遵循 design-language.md professional 风格：
//   圆角 6px / 字号 13-14px / 间距 8-12 / 颜色 slate
// ============================================================

"use client";

import { useEffect, useRef, useState, useCallback, useMemo } from "react";
import { createPortal } from "react-dom";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import {
  Search,
  Cloud,
  CloudOff,
  RefreshCw,
  Sparkles,
  ChevronDown,
  Sun,
  Moon,
  LogOut,
  User as UserIcon,
  Settings as SettingsIcon,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import { useAuth } from "@/contexts/AuthContext";
import { useUser } from "@/hooks/useUser";
import { useLayoutPrefs } from "@/hooks/useLayoutPrefs";
import { primaryNavItems } from "@/lib/navConfig";
import { authedFetch } from "@/lib/api/api";

// ── 同步状态 hook（轻量心跳） ──
function useSyncStatus() {
  const [status, setStatus] = useState<"online" | "syncing" | "offline">("online");
  useEffect(() => {
    const onOnline = () => setStatus("syncing");
    const onOffline = () => setStatus("offline");
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);
  return { status, setStatus };
}

// ── 搜索结果类型 ──
interface SearchResult {
  id: string;
  type: "page" | "nav" | "command";
  title: string;
  subtitle?: string;
  href?: string;
  action?: () => void;
}

export default function TopBar() {
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();
  const { navContext } = useUser();
  const { pref, toggleCollapsed } = useLayoutPrefs();
  const router = useRouter();
  const pathname = usePathname();
  const { status: syncStatus } = useSyncStatus();

  // ── 全局搜索 (⌘K) ──
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const searchInputRef = useRef<HTMLInputElement>(null);

  // ── 用户菜单 ──
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);
  const userButtonRef = useRef<HTMLButtonElement>(null);
  const userDropdownRef = useRef<HTMLDivElement>(null);
  const [userMenuPos, setUserMenuPos] = useState<{ top: number; right: number } | null>(null);

  // ⌘K / Ctrl+K 唤起搜索
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
      if (e.key === "Escape" && searchOpen) {
        setSearchOpen(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [searchOpen]);

  useEffect(() => {
    if (searchOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    } else {
      setSearchQuery("");
    }
  }, [searchOpen]);

  // 点击外部关闭用户菜单
  useEffect(() => {
    if (!userMenuOpen) return;
    const onClick = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        !userButtonRef.current?.contains(target) &&
        !userDropdownRef.current?.contains(target)
      ) {
        setUserMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [userMenuOpen]);

  // 同步计算 dropdown 位置：基于按钮 bounding rect
  // 用 position: fixed + portal 渲染，绕过 grid cell / ResizableContainer 的 overflow 裁剪
  const computeMenuPos = useCallback(() => {
    const btn = userButtonRef.current;
    if (!btn) return null;
    const rect = btn.getBoundingClientRect();
    return {
      top: rect.bottom + 4,
      right: window.innerWidth - rect.right,
    };
  }, []);

  // 切换菜单：同步算位置（避免 effect 时序导致首次 render 不显示）
  const toggleUserMenu = useCallback(() => {
    setUserMenuOpen((prev) => {
      const next = !prev;
      if (next) {
        const pos = computeMenuPos();
        if (pos) setUserMenuPos(pos);
      } else {
        setUserMenuPos(null);
      }
      return next;
    });
  }, [computeMenuPos]);

  // 打开后：跟随 scroll / resize 实时更新位置
  useEffect(() => {
    if (!userMenuOpen) return;
    const updatePos = () => {
      const pos = computeMenuPos();
      if (pos) setUserMenuPos(pos);
    };
    window.addEventListener("scroll", updatePos, true);
    window.addEventListener("resize", updatePos);
    return () => {
      window.removeEventListener("scroll", updatePos, true);
      window.removeEventListener("resize", updatePos);
    };
  }, [userMenuOpen, computeMenuPos]);

  // SSR 守卫：portal 需要 document.body
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  // 搜索结果：合并 nav + 常用命令
  const searchResults = useMemo<SearchResult[]>(() => {
    const items: SearchResult[] = primaryNavItems
      .filter((n) => n.visibleIn.sidebar)
      .filter((n) => n.requiresAuth ? navContext.userRole !== "guest" : true)
      .map((n) => ({
        id: n.path,
        type: "nav" as const,
        title: n.label,
        subtitle: n.path,
        href: n.path,
      }));
    const commands: SearchResult[] = [
      { id: "cmd-ai", type: "command", title: "唤起 AI 助手", subtitle: "⌘J", action: () => alert("AI 助手面板见右栏") },
      { id: "cmd-sync", type: "command", title: "立即同步", subtitle: "系统", action: () => alert("已触发同步") },
      { id: "cmd-theme", type: "command", title: "切换主题", subtitle: "深/浅色", action: () => toggleTheme() },
      { id: "cmd-logout", type: "command", title: "退出登录", subtitle: "账户", action: () => logout() },
    ];
    const all = [...items, ...commands];
    if (!searchQuery.trim()) return all.slice(0, 8);
    const q = searchQuery.toLowerCase();
    return all
      .filter((r) => r.title.toLowerCase().includes(q) || r.subtitle?.toLowerCase().includes(q))
      .slice(0, 12);
  }, [searchQuery, navContext, toggleTheme, logout]);

  const runResult = useCallback((r: SearchResult) => {
    setSearchOpen(false);
    if (r.href) router.push(r.href);
    else if (r.action) r.action();
  }, [router]);

  // AI 唤起 ⌘J
  const onAIInvoke = useCallback(() => {
    // 唤起右栏
    const event = new CustomEvent("workbench-ai-invoke");
    window.dispatchEvent(event);
  }, []);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "j") {
        e.preventDefault();
        onAIInvoke();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onAIInvoke]);

  return (
    <>
      <div
        className="h-full w-full flex items-center gap-2 px-3 bg-page border-b border-divider"
        style={{ minHeight: 40 }}
      >
        {/* 左侧：左栏折叠按钮 + 面包屑 */}
        <button
          onClick={() => toggleCollapsed("leftPanel")}
          className="p-1.5 rounded text-ink-muted hover:text-ink-primary hover:bg-surface-hover transition-colors"
          title={pref.leftPanel.collapsed ? "展开左栏" : "折叠左栏"}
        >
          {pref.leftPanel.collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
        </button>

        <Link href="/" className="flex items-center gap-2 mr-2 group">
          <div className="w-7 h-7 bg-accent flex items-center justify-center rounded active:scale-[0.97] transition-transform group-hover:scale-105">
            <span className="text-white font-semibold text-xs">果</span>
          </div>
          <span className="font-semibold text-ink-primary tracking-tight text-sm">苹果果</span>
        </Link>

        {/* 路径指示 */}
        <span className="text-ink-muted text-[12px] hidden md:inline">
          {pathname === "/" ? "首页" : pathname}
        </span>

        {/* 中部：搜索框 */}
        <button
          onClick={() => setSearchOpen(true)}
          className="flex-1 max-w-md mx-auto flex items-center gap-2 px-3 h-8 text-[13px] rounded-md bg-surface text-ink-muted hover:bg-surface-hover transition-colors border border-divider"
        >
          <Search size={14} />
          <span className="flex-1 text-left">搜索…</span>
          <kbd className="hidden sm:inline-block text-[10px] px-1.5 py-0.5 rounded border border-divider bg-page-secondary text-ink-muted">
            ⌘K
          </kbd>
        </button>

        {/* 右侧 */}
        <div className="flex items-center gap-1.5">
          {/* 同步状态 */}
          <div
            className="flex items-center gap-1 px-2 h-8 rounded text-[12px] text-ink-muted hover:bg-surface-hover transition-colors cursor-default"
            title={syncStatus === "online" ? "已同步" : syncStatus === "syncing" ? "同步中…" : "离线"}
          >
            {syncStatus === "online" && <Cloud size={14} className="text-success" />}
            {syncStatus === "syncing" && <RefreshCw size={14} className="animate-spin text-accent" />}
            {syncStatus === "offline" && <CloudOff size={14} className="text-error" />}
            <span className="hidden lg:inline">
              {syncStatus === "online" ? "已同步" : syncStatus === "syncing" ? "同步中" : "离线"}
            </span>
          </div>

          {/* Pro 徽章 */}
          {navContext.subscriptionTier === "pro" || navContext.subscriptionTier === "enterprise" ? (
            <div className="px-2 h-8 flex items-center gap-1 rounded bg-amber-500/10 text-amber-500 text-[11px] font-semibold border border-amber-500/20">
              <Sparkles size={12} />
              {navContext.subscriptionTier === "pro" ? "Pro" : "Enterprise"}
            </div>
          ) : null}

          {/* AI 唤起 */}
          <button
            onClick={onAIInvoke}
            className="flex items-center gap-1.5 px-2.5 h-8 rounded-md bg-accent text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
            title="唤起 AI 助手 (⌘J)"
          >
            <Sparkles size={14} />
            <span className="hidden sm:inline">AI</span>
            <kbd className="hidden sm:inline text-[10px] px-1 py-0.5 rounded bg-white/20">
              ⌘J
            </kbd>
          </button>

          {/* 主题切换 */}
          <button
            onClick={toggleTheme}
            className="p-1.5 rounded text-ink-muted hover:text-ink-primary hover:bg-surface-hover transition-colors"
            title={theme === "dark" ? "切换到浅色" : "切换到深色"}
          >
            {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
          </button>

          {/* 用户菜单 */}
          {user && (
            <div ref={userMenuRef} className="relative">
              <button
                ref={userButtonRef}
                onClick={toggleUserMenu}
                aria-haspopup="menu"
                aria-expanded={userMenuOpen}
                className="flex items-center gap-1.5 px-1.5 h-8 rounded hover:bg-surface-hover transition-colors"
              >
                <div className="w-6 h-6 rounded-full bg-accent flex items-center justify-center text-white text-[11px] font-semibold">
                  {(user.display_name || user.username).charAt(0).toUpperCase()}
                </div>
                <ChevronDown size={12} className="text-ink-muted" />
              </button>
              {userMenuOpen && mounted && userMenuPos &&
                createPortal(
                  <div
                    ref={userDropdownRef}
                    style={{
                      position: "fixed",
                      top: userMenuPos.top,
                      right: userMenuPos.right,
                    }}
                    className="w-56 bg-page-secondary border border-divider rounded-md shadow-lg z-[100] py-1 text-[13px]"
                  >
                    <div className="px-3 py-2 border-b border-divider">
                      <div className="font-medium text-ink-primary truncate">{user.display_name || user.username}</div>
                      <div className="text-[11px] text-ink-muted truncate">@{user.username}</div>
                    </div>
                    <Link
                      href="/settings"
                      onClick={() => setUserMenuOpen(false)}
                      className="flex items-center gap-2 px-3 py-1.5 text-ink-secondary hover:bg-surface-hover hover:text-ink-primary"
                    >
                      <SettingsIcon size={14} /> 设置
                    </Link>
                    <Link
                      href="/settings/account"
                      onClick={() => setUserMenuOpen(false)}
                      className="flex items-center gap-2 px-3 py-1.5 text-ink-secondary hover:bg-surface-hover hover:text-ink-primary"
                    >
                      <UserIcon size={14} /> 账户
                    </Link>
                    <button
                      onClick={() => { setUserMenuOpen(false); logout(); }}
                      className="w-full flex items-center gap-2 px-3 py-1.5 text-ink-secondary hover:bg-surface-hover hover:text-red-500 border-t border-divider"
                    >
                      <LogOut size={14} /> 退出登录
                    </button>
                  </div>,
                  document.body
                )
              }
            </div>
          )}
        </div>
      </div>

      {/* 搜索弹层（命令面板） */}
      {searchOpen && (
        <div
          className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh] bg-black/40 backdrop-blur-sm"
          onClick={() => setSearchOpen(false)}
        >
          <div
            className="w-full max-w-xl mx-4 bg-page border border-divider rounded-lg shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-2 px-3 h-11 border-b border-divider">
              <Search size={16} className="text-ink-muted" />
              <input
                ref={searchInputRef}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="搜索导航、命令…"
                className="flex-1 bg-transparent text-[14px] text-ink-primary placeholder-ink-muted focus:outline-none"
              />
              <kbd className="text-[10px] px-1.5 py-0.5 rounded border border-divider text-ink-muted">
                Esc
              </kbd>
            </div>
            <div className="max-h-[50vh] overflow-y-auto py-1">
              {searchResults.length === 0 ? (
                <div className="px-4 py-8 text-center text-ink-muted text-sm">
                  没有匹配项
                </div>
              ) : (
                searchResults.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => runResult(r)}
                    className="w-full flex items-center gap-3 px-3 py-2 text-left text-[13px] text-ink-secondary hover:bg-surface-hover hover:text-ink-primary"
                  >
                    <div className="w-7 h-7 rounded bg-surface flex items-center justify-center text-ink-muted">
                      {r.type === "nav" ? "↗" : r.type === "command" ? "⚡" : "·"}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="truncate text-ink-primary">{r.title}</div>
                      {r.subtitle && (
                        <div className="text-[11px] text-ink-muted truncate">{r.subtitle}</div>
                      )}
                    </div>
                    <span className="text-[10px] text-ink-muted uppercase">
                      {r.type}
                    </span>
                  </button>
                ))
              )}
            </div>
            <div className="px-3 py-2 border-t border-divider text-[11px] text-ink-muted flex items-center gap-3">
              <span>↑↓ 选择</span>
              <span>↵ 确认</span>
              <span>Esc 关闭</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

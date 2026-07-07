"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  BarChart3, CalendarDays, Trophy, Target,
} from "lucide-react";
import { PageSkeleton } from "@/components/ui/Skeleton";

// ── 子标签组件导入 ──
import AnalyticsContent from "@/app/analytics/_content";
import CalendarTab from "@/components/analytics/tabs/CalendarTab";
import AchievementsTab from "@/components/analytics/tabs/AchievementsTab";
import StatsTab from "@/components/analytics/tabs/StatsTab";

// ── 子标签定义 ──
type TabId = "analytics" | "calendar" | "achievements" | "stats";

interface TabDef {
  id: TabId;
  label: string;
  icon: React.ReactNode;
}

const TABS: TabDef[] = [
  { id: "analytics", label: "学情分析", icon: <BarChart3 size={14} /> },
  { id: "calendar",  label: "日历热力", icon: <CalendarDays size={14} /> },
  { id: "achievements", label: "成就墙", icon: <Trophy size={14} /> },
  { id: "stats",     label: "学习统计", icon: <Target size={14} /> },
];

const STORAGE_KEY = "analytics_active_tab";

// ── 主组件 ──
export default function AnalyticsRootPage() {
  // 从 URL 参数或 localStorage 读取初始 tab
  const [activeTab, setActiveTab] = useState<TabId>("analytics");
  const [ready, setReady] = useState(false);
  const initialized = useRef(false);

  // 初始化：URL 参数优先，其次 localStorage，最后默认 analytics
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;

    const params = new URLSearchParams(window.location.search);
    const tabParam = params.get("tab") as TabId | null;

    if (tabParam && TABS.some((t) => t.id === tabParam)) {
      setActiveTab(tabParam);
    } else {
      const saved = localStorage.getItem(STORAGE_KEY) as TabId | null;
      if (saved && TABS.some((t) => t.id === saved)) {
        setActiveTab(saved);
      }
    }
    setReady(true);
  }, []);

  // 切换 tab 时保存偏好
  const handleTabChange = useCallback((tabId: TabId) => {
    setActiveTab(tabId);
    localStorage.setItem(STORAGE_KEY, tabId);
    // 清除 URL 中的 tab 参数，避免刷新后错乱
    const params = new URLSearchParams(window.location.search);
    params.delete("tab");
    const qs = params.toString();
    const newUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
    window.history.replaceState(null, "", newUrl);
  }, []);

  if (!ready) {
    return (
      <main className="min-h-screen bg-page">
        <PageSkeleton />
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-page">
      <div className="max-w-6xl mx-auto px-4 sm:px-6">
        {/* ── 顶栏：标题 + Tab 导航 ── */}
        <div className="sticky top-0 z-30 bg-page border-b border -mx-4 sm:-mx-6 px-4 sm:px-6">
          <div className="flex items-center gap-4 py-3">
            <h1 className="text-lg font-semibold tracking-tight text shrink-0">
              学习统计
            </h1>
            <div className="flex items-center gap-0.5 overflow-x-auto scrollbar-hide">
              {TABS.map((tab) => {
                const isActive = tab.id === activeTab;
                return (
                  <button
                    key={tab.id}
                    onClick={() => handleTabChange(tab.id)}
                    className={`
                      flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-medium whitespace-nowrap
                      transition-all rounded-md
                      ${isActive
                        ? "bg-accent text-white shadow-sm"
                        : "text-muted hover:text hover:bg-surface"
                      }
                    `}
                  >
                    {tab.icon}
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* ── Tab 内容 ── */}
        <div className="py-4">
          {activeTab === "analytics" && <AnalyticsContent />}
          {activeTab === "calendar" && <CalendarTab />}
          {activeTab === "achievements" && <AchievementsTab />}
          {activeTab === "stats" && <StatsTab />}
        </div>
      </div>
    </main>
  );
}
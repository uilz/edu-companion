"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import Link from "next/link";
import { BookOpen, Brain, Target, TrendingUp, MessageCircle, Search, Loader2, ExternalLink, FileText, Video, Dumbbell } from "lucide-react";
import Card from "@/components/ui/Card";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface StudyTask {
  id: number;
  subject: string;
  task: string;
  done: boolean;
}

interface ContentItem {
  content_id: string;
  title: string;
  subject: string;
  content_type: string;
  description?: string;
  url?: string;
}

const todayTasks: StudyTask[] = [
  { id: 1, subject: "高等数学", task: "复习极限与连续（第三章）", done: true },
  { id: 2, subject: "线性代数", task: "完成矩阵运算练习题 15 道", done: false },
  { id: 3, subject: "大学物理", task: "观看电磁学专题视频", done: false },
  { id: 4, subject: "英语", task: "背诵学术词汇 Unit 8", done: false },
];

const weeklyData = [
  { day: "一", hours: 3.2 }, { day: "二", hours: 2.5 }, { day: "三", hours: 4.1 },
  { day: "四", hours: 1.8 }, { day: "五", hours: 3.6 }, { day: "六", hours: 5.0 },
  { day: "日", hours: 2.8 },
];

const TYPE_ICONS: Record<string, { icon: React.ReactNode; color: string }> = {
  video: { icon: <Video size={14} />, color: "text-[#ef4444]" },
  article: { icon: <FileText size={14} />, color: "text-[#3b82f6]" },
  exercise: { icon: <Dumbbell size={14} />, color: "text-[#10b981]" },
  quiz: { icon: <Target size={14} />, color: "text-[#f59e0b]" },
};

export default function HomePage() {
  const greeting = useMemo(() => {
    const h = new Date().getHours();
    if (h < 6) return "夜深了，注意休息";
    if (h < 12) return "早上好";
    if (h < 18) return "下午好";
    return "晚上好";
  }, []);

  const completedCount = todayTasks.filter((t) => t.done).length;
  const totalHours = weeklyData.reduce((s, d) => s + d.hours, 0);
  const maxHours = Math.max(...weeklyData.map((d) => d.hours));
  const streak = 12;

  // ── Content search ──
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<ContentItem[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [showResults, setShowResults] = useState(false);

  const handleSearch = useCallback(async () => {
    const q = searchQuery.trim();
    if (!q) return;
    setSearching(true);
    setSearched(true);
    setShowResults(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/content/search?query=${encodeURIComponent(q)}&limit=8`
      );
      if (res.ok) {
        const data = await res.json();
        setSearchResults(data || []);
      }
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }, [searchQuery]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-16">
        {/* Header */}
        <header className="mb-10 sm:mb-16">
          <h1 className="text-4xl sm:text-5xl font-bold tracking-tight text-[var(--color-text)] mb-3">
            {greeting}
          </h1>
          <p className="text-base sm:text-lg text-[var(--color-text-muted)]">
            今天是学习的第 <span className="text-[var(--color-text)] font-semibold">{streak}</span> 天
          </p>
        </header>

        {/* ── Global Search ── */}
        <div className="mb-12">
          <div className="flex gap-2 max-w-xl">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="搜索学习内容 (文章/视频/练习)..."
                className="w-full pl-10 pr-4 py-3 text-sm bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] placeholder-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-border-hover)]"
              />
            </div>
            <button
              onClick={handleSearch}
              disabled={searching || !searchQuery.trim()}
              className="px-5 py-3 text-sm font-medium bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-30 transition-opacity"
            >
              {searching ? <Loader2 size={15} className="animate-spin" /> : "搜索"}
            </button>
          </div>

          {/* Search results dropdown */}
          {showResults && searched && (
            <div className="mt-2 max-w-xl border border-[var(--color-border)] bg-[var(--color-bg)] shadow-lg">
              {searchResults.length > 0 ? (
                <div className="divide-y divide-[var(--color-border)]">
                  {searchResults.map((item) => {
                    const typeInfo = TYPE_ICONS[item.content_type] || TYPE_ICONS.article;
                    return (
                      <Link
                        key={item.content_id}
                        href={
                          item.content_type === "exercise" || item.content_type === "quiz"
                            ? "/practice"
                            : item.url || "#"
                        }
                        className="flex items-start gap-3 px-4 py-3 hover:bg-[var(--color-surface)] transition-colors group"
                      >
                        <span className={`flex-shrink-0 mt-0.5 ${typeInfo.color}`}>
                          {typeInfo.icon}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-[var(--color-text)] group-hover:text-[var(--color-accent)] transition-colors truncate">
                              {item.title || item.content_id}
                            </span>
                            <ExternalLink size={10} className="flex-shrink-0 text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100" />
                          </div>
                          {item.description && (
                            <p className="text-xs text-[var(--color-text-muted)] mt-0.5 line-clamp-1">
                              {item.description}
                            </p>
                          )}
                          <div className="flex items-center gap-2 mt-1 text-[10px] text-[var(--color-text-muted)]">
                            <span>{item.subject}</span>
                            <span>·</span>
                            <span>{item.content_type}</span>
                          </div>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              ) : (
                <div className="px-4 py-6 text-center text-sm text-[var(--color-text-muted)]">
                  {searching ? "搜索中..." : "没有找到相关内容"}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="grid grid-cols-3 gap-3 sm:gap-4 mb-12">
          {[
            { href: "/chat", emoji: "💬", title: "提问", desc: "向 AI 助手提问" },
            { href: "/practice", emoji: "📝", title: "练习", desc: "做题巩固知识" },
            { href: "/graph", emoji: "🧠", title: "知识图谱", desc: "查看知识关联" },
          ].map((action) => (
            <Link
              key={action.href}
              href={action.href}
              className="border border-[var(--color-border)] bg-[var(--color-card)] p-4 sm:p-6 hover:border-[var(--color-border-hover)] transition-colors group"
            >
              <div className="text-xl sm:text-2xl mb-2 sm:mb-3">{action.emoji}</div>
              <div className="text-xs sm:text-sm font-semibold text-[var(--color-text)] group-hover:text-[var(--color-accent)] transition-colors">
                {action.title}
              </div>
              <div className="text-[10px] sm:text-xs text-[var(--color-text-muted)] mt-0.5 sm:mt-1">{action.desc}</div>
            </Link>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 sm:gap-8">
          {/* Today's Plan */}
          <div className="lg:col-span-2">
            <Card title="今日学习计划">
              <div className="space-y-0 divide-y divide-[var(--color-surface)]">
                {todayTasks.map((task) => (
                  <label key={task.id} className="flex items-start gap-3 py-3 cursor-pointer group">
                    <input type="checkbox" defaultChecked={task.done}
                      className="mt-0.5 accent-[var(--color-accent)] w-4 h-4" />
                    <div className="flex-1">
                      <div className={`text-sm ${task.done ? "text-[var(--color-text-muted)] line-through" : "text-[var(--color-text)]"}`}>
                        {task.task}
                      </div>
                      <div className="text-xs text-[var(--color-text-muted)] mt-0.5">{task.subject}</div>
                    </div>
                  </label>
                ))}
              </div>
              <div className="mt-4 pt-4 border-t border-[var(--color-surface)] text-xs text-[var(--color-text-muted)]">
                已完成 {completedCount}/{todayTasks.length}
              </div>
            </Card>
          </div>

          {/* Weekly Overview */}
          <div>
            <Card title="本周概览">
              <div className="mb-4">
                <div className="text-3xl font-bold text-[var(--color-text)]">
                  {totalHours.toFixed(1)}<span className="text-sm font-normal text-[var(--color-text-muted)] ml-1">小时</span>
                </div>
                <div className="text-xs text-[var(--color-text-muted)] mt-1">
                  连续学习 <span className="text-[var(--color-accent)] font-semibold">{streak}</span> 天
                </div>
              </div>
              <div className="flex gap-1 mb-6">
                {Array.from({ length: 30 }).map((_, i) => (
                  <div key={i} className={`h-1.5 flex-1 ${i < 12 ? "bg-[var(--color-accent)]" : "bg-[var(--color-surface)]"}`} />
                ))}
              </div>
              <div className="space-y-2">
                {weeklyData.map((d) => (
                  <div key={d.day} className="flex items-center gap-2">
                    <span className="text-xs text-[var(--color-text-muted)] w-4">{d.day}</span>
                    <div className="flex-1 bg-[var(--color-surface)] h-2">
                      <div className="h-full bg-[var(--color-text)]" style={{ width: `${(d.hours / maxHours) * 100}%` }} />
                    </div>
                    <span className="text-xs text-[var(--color-text-muted)] w-8 text-right">{d.hours}h</span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mt-6 sm:mt-8">
          {[
            { icon: <BookOpen size={18} />, label: "今日学习", value: "2.4 小时" },
            { icon: <Target size={18} />, label: "完成题目", value: "38 道" },
            { icon: <Brain size={18} />, label: "掌握知识点", value: "156 个" },
            { icon: <TrendingUp size={18} />, label: "正确率", value: "87.3%" },
          ].map((stat) => (
            <div key={stat.label} className="border border-[var(--color-border)] bg-[var(--color-card)] p-4 sm:p-5">
              <div className="text-[var(--color-text-muted)] mb-2">{stat.icon}</div>
              <div className="text-xl sm:text-2xl font-bold text-[var(--color-text)]">{stat.value}</div>
              <div className="text-xs text-[var(--color-text-muted)] mt-1">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}

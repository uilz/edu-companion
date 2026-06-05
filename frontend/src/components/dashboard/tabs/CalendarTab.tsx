"use client";

// ── 外部依赖导入 ──
import { useState, useEffect, useCallback } from "react";
import { CalendarDays, ChevronLeft, ChevronRight, Loader2, Flame, Target, Zap } from "lucide-react";
import Link from "next/link";
import { API_BASE } from "@/lib/api/api";

// ── 类型定义 ──

// 单日学习记录
interface DayEntry {
  date: string;       // 日期字符串（YYYY-MM-DD）
  day: number;        // 日（1-31）
  total: number;      // 当日总答题数
  correct: number;    // 当日正确数
  accuracy: number | null;  // 正确率（0-1），无数据时为 null
}

// 月历整体数据
interface CalendarData {
  year: number;
  month: number;
  days: DayEntry[];
  month_total: number;       // 本月总答题数
  month_correct: number;     // 本月总正确数
  month_accuracy: number | null;  // 本月正确率
  month_streak: number;      // 本月连续学习天数
  best_day: { date: string; total: number } | null;  // 本月答题最多的一天
}

// ── 热力图颜色函数 ──
// 根据答题数量返回背景色（GitHub 贡献图风格）

function heatColor(total: number): string {
  if (total === 0) return "var(--color-surface)";
  if (total <= 5) return "#0e4429";
  if (total <= 10) return "#006d32";
  if (total <= 20) return "#26a641";
  return "#39d353";
}

// 根据答题数量返回文字颜色（深色背景用白色，浅色用灰色）

function textColor(total: number): string {
  if (total === 0) return "var(--color-text-muted)";
  if (total <= 5) return "#666";
  return "#fff";
}

// ── 辅助常量与工具函数 ──

// 月份中文名称数组
const MONTH_NAMES = [
  "1月", "2月", "3月", "4月", "5月", "6月",
  "7月", "8月", "9月", "10月", "11月", "12月",
];

// 星期表头（周一至周日，与日历网格对齐）
const DAY_HEADERS = ["一", "二", "三", "四", "五", "六", "日"];

// 计算某月1日是星期几，返回值 0=周一 ... 6=周日

function dayOfWeek(year: number, month: number, day: number): number {
  // 0=Sun, 1=Mon, ..., 6=Sat → 我们 0=Mon, 6=Sun
  const d = new Date(year, month - 1, day).getDay();
  return d === 0 ? 6 : d - 1;
}

// ── 日期详情弹窗组件 ──
// 点击日历格子后弹出，显示该日答题数、正确数和正确率

function DayDetail({ day, onClose }: { day: DayEntry; onClose: () => void }) {
  const date = new Date(day.date);
  const weekdays = ["日", "一", "二", "三", "四", "五", "六"];
  const label = `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日 星期${weekdays[date.getDay()]}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-[var(--color-card)] border border-[var(--color-border)] w-full max-w-xs mx-4 p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="text-sm font-semibold text-[var(--color-text)] mb-3">{label}</h3>

        {day.total === 0 ? (
          <p className="text-xs text-[var(--color-text-muted)]">这天没有学习记录 🛌</p>
        ) : (
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">答题</span>
              <span className="text-[var(--color-text)] font-medium">{day.total} 题</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">正确</span>
              <span className="text-[var(--color-text)] font-medium">{day.correct} 题</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-muted)]">正确率</span>
              <span className="text-[var(--color-text)] font-medium">
                {day.accuracy != null ? `${(day.accuracy * 100).toFixed(0)}%` : "—"}
              </span>
            </div>
          </div>
        )}

        <div className="flex gap-2 mt-4">
          <Link
            href="/practice"
            className="flex-1 text-center text-xs px-3 py-2 bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)] active:scale-[0.97] transition-colors"
          >
            去练习
          </Link>
          {day.total > 0 && (
            <Link
              href="/errors"
              className="flex-1 text-center text-xs px-3 py-2 border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors"
            >
              看错题
            </Link>
          )}
        </div>

        <button
          onClick={onClose}
          className="mt-3 w-full text-center text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
        >
          关闭
        </button>
      </div>
    </div>
  );
}

// ── 主页面组件 ──

export function CalendarTab() {
  // 当前选中的年/月
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [data, setData] = useState<CalendarData | null>(null);   // 月历数据
  const [loading, setLoading] = useState(true);                  // 加载状态
  const [selectedDay, setSelectedDay] = useState<DayEntry | null>(null); // 当前选中的日

  // 获取指定年月的日历数据

  const fetchCalendar = useCallback(async (y: number, m: number) => {
    setLoading(true);
    try {
      // 调用后端 API 获取月历数据
      const res = await fetch(
        `${API_BASE}/api/progress/default_user/calendar?year=${y}&month=${m}`
      );
      if (!res.ok) throw new Error("Failed");
      const json: CalendarData = await res.json();
      setData(json);
    } catch (e) {
      setData(null);  // 请求失败时清空数据
    } finally {
      setLoading(false);
    }
  }, []);

  // 当年或月份变化时重新获取数据

  useEffect(() => {
    fetchCalendar(year, month);
  }, [year, month, fetchCalendar]);

  // ── 月份导航 ──

  // 上一个月

  const goPrev = () => {
    if (month === 1) { setYear(y => y - 1); setMonth(12); }
    else setMonth(m => m - 1);
  };

  // 下一个月

  const goNext = () => {
    if (month === 12) { setYear(y => y + 1); setMonth(1); }
    else setMonth(m => m + 1);
  };

  // 跳转到本月

  const goToday = () => {
    const n = new Date();
    setYear(n.getFullYear());
    setMonth(n.getMonth() + 1);
  };

  // ── 构建日历网格 ──

  const days = data?.days || [];
  const firstDow = dayOfWeek(year, month, 1);                     // 当月1日的星期索引
  const totalDays = new Date(year, month, 0).getDate();          // 当月总天数

  const cells: (DayEntry | null)[] = [];
  // 填充月初空白格子（使1日对齐到正确星期列）
  for (let i = 0; i < firstDow; i++) cells.push(null);
  // 填充当月每一天，若后端无数据则用默认空记录
  for (let d = 1; d <= totalDays; d++) {
    const entry = days.find((dd) => dd.day === d) || {
      date: `${year}-${String(month).padStart(2, "0")}-${String(d).padStart(2, "0")}`,
      day: d,
      total: 0,
      correct: 0,
      accuracy: null,
    };
    cells.push(entry);
  }

  const todayStr = new Date().toISOString().slice(0, 10);

  // ── 加载中：显示旋转图标 ──

  if (loading) {
    return (
      <div>
        <Loader2 size={24} className="animate-spin text-[var(--color-accent)]" />
      </div>
    );
  }

  return (
    <div>
      <div>
        {/* ── 页面标题 ── */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl md:text-3xl font-semibold tracking-tight text-[var(--color-text)]">
              <CalendarDays size={24} className="inline mr-2 text-[var(--color-accent)]" />
              学习日历
            </h1>
            <p className="text-xs text-[var(--color-text-muted)] mt-1">
              每天学一点，日积月累 📅
            </p>
          </div>
        </div>

        {/* ── 月份选择器（上/下月切换，跳转今天） ── */}
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={goPrev}
            className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-text)] active:scale-[0.97] transition-all"
          >
            <ChevronLeft size={18} />
          </button>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-semibold text-[var(--color-text)]">
              {year}年 {MONTH_NAMES[month - 1]}
            </h2>
            <button
              onClick={goToday}
              className="text-[10px] px-2 py-0.5 border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] active:scale-[0.97] transition-all"
            >
              今天
            </button>
          </div>
          <button
            onClick={goNext}
            className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-text)] active:scale-[0.97] transition-all"
          >
            <ChevronRight size={18} />
          </button>
        </div>

        {/* ── 热力图网格（GitHub 贡献图风格） ── */}
        <div className="border border-[var(--color-border)] bg-[var(--color-card)] p-4 mb-6">
          {/* 星期表头行 */}
          <div className="grid grid-cols-7 gap-1 mb-2">
            {DAY_HEADERS.map((h) => (
              <div key={h} className="text-center text-[10px] text-[var(--color-text-muted)] py-1">
                {h}
              </div>
            ))}
          </div>

          {/* 日历格子：空白占位 / 当日格子 */}
          <div className="grid grid-cols-7 gap-1">
            {cells.map((cell, i) => {
              if (!cell) {
                // 空白占位格
                return <div key={`empty-${i}`} className="aspect-square" />;
              }
              const isToday = cell.date === todayStr;
              const isFuture = cell.date > todayStr;
              return (
                <button
                  key={cell.date}
                  onClick={() => !isFuture && setSelectedDay(cell)}
                  disabled={isFuture}
                  className={`aspect-square flex flex-col items-center justify-center text-xs font-medium transition-colors ${
                    isFuture
                      ? "opacity-30 cursor-default"
                      : "cursor-pointer hover:ring-1 hover:ring-[var(--color-accent)]"
                  }`}
                  style={{
                    backgroundColor: isFuture ? "var(--color-surface)" : heatColor(cell.total),
                    color: isFuture ? "var(--color-text-muted)" : textColor(cell.total),
                    border: isToday ? "2px solid var(--color-accent)" : "1px solid transparent",
                  }}
                  title={`${cell.date}: ${cell.total}题`}
                >
                  <span className={isToday ? "font-semibold" : ""}>{cell.day}</span>
                  {cell.total > 0 && (
                    <span className="text-[8px] opacity-70">{cell.total}</span>
                  )}
                </button>
              );
            })}
          </div>

          {/* ── 图例（少 → 多） ── */}
          <div className="flex items-center gap-2 mt-4 justify-end text-[10px] text-[var(--color-text-muted)]">
            <span>少</span>
            {[0, 5, 10, 20].map((n) => (
              <div
                key={n}
                className="w-3 h-3"
                style={{ backgroundColor: heatColor(n === 0 ? 0 : n) }}
              />
            ))}
            <div className="w-3 h-3" style={{ backgroundColor: "#39d353" }} />
            <span>多</span>
          </div>
        </div>

        {/* ── 本月统计概览（答题数、正确率、连续学习、学习天数） ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          <div className="border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-center">
            <div className="text-xl font-semibold text-[var(--color-text)]">{data?.month_total || 0}</div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1">本月答题</div>
          </div>
          <div className="border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-center">
            <div className="text-xl font-semibold text-[var(--color-text)]">
              {data?.month_accuracy != null ? `${(data.month_accuracy * 100).toFixed(0)}%` : "—"}
            </div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1">正确率</div>
          </div>
          <div className="border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-center">
            <div className="text-xl font-semibold text-[var(--color-text)] flex items-center justify-center gap-1">
              <Flame size={16} className="text-[var(--color-warning)]" />
              {data?.month_streak || 0}
            </div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1">连续学习</div>
          </div>
          <div className="border border-[var(--color-border)] bg-[var(--color-card)] p-4 text-center">
            <div className="text-xl font-semibold text-[var(--color-text)]">
              {data?.days?.filter(d => d.total > 0).length || 0}
            </div>
            <div className="text-[10px] text-[var(--color-text-muted)] mt-1">学习天数</div>
          </div>
        </div>

        {/* ── 本月最佳学习日高亮 ── */}
        {data?.best_day && (
          <div className="border border-[var(--color-border)] bg-[var(--color-card)] p-4 flex items-center gap-3">
            <Zap size={18} className="text-[var(--color-warning)] flex-shrink-0" />
            <div>
              <p className="text-xs text-[var(--color-text-secondary)]">
                本月最佳：<span className="font-semibold text-[var(--color-text)]">{data.best_day.date}</span>
                {" "}· {data.best_day.total} 题
              </p>
              <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                保持这个势头！💪
              </p>
            </div>
          </div>
        )}

        {/* ── 快捷操作链接（开始练习 / 查看学情） ── */}
        <div className="flex gap-3 mt-6">
          <Link
            href="/practice"
            className="flex items-center gap-1.5 px-4 py-2 bg-[var(--color-accent)] text-white text-xs hover:bg-[var(--color-accent-hover)] active:scale-[0.97] transition-colors"
          >
            <Target size={13} /> 开始练习
          </Link>
          <Link
            href="/analytics"
            className="flex items-center gap-1.5 px-4 py-2 border border-[var(--color-border)] text-[var(--color-text-secondary)] text-xs hover:text-[var(--color-text)] transition-colors"
          >
            查看学情 →
          </Link>
        </div>
      </div>

      {/* ── 日期详情弹窗 ── */}
      {selectedDay && (
        <DayDetail day={selectedDay} onClose={() => setSelectedDay(null)} />
      )}
    </div>
  );
}

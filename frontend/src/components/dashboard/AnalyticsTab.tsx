"use client";

// ── 依赖导入：React 状态管理、图标库、路由、UI 组件 ──
import { useState, useEffect, useMemo } from "react";
import {
  BarChart3, Target, Clock, TrendingUp, Loader2, BookOpen,
  CalendarDays, Zap, AlertTriangle, Heart, Flame, Timer,
} from "lucide-react";
import Link from "next/link";
import Card from "@/components/ui/Card";
import RadarChart from "@/components/analytics/RadarChart";

// ── API 地址：优先使用环境变量，否则回退到本地 8000 ──
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ═══════════════════════════════════════════════
//  类型定义 — 对应后端返回的数据结构
// ═══════════════════════════════════════════════

// ── 总览统计 ──
interface Overview {
  total_questions: number;   // 总答题数
  accuracy: number;          // 正确率（0~1）
  study_days: number;        // 学习天数
  study_minutes: number;     // 总学习分钟数
  prev_week: {               // 上周对比数据
    total_questions: number;
    accuracy: number;
    study_days: number;
    study_minutes: number;
  };
}

// ── 每日趋势数据点 ──
interface DailyPoint {
  date: string;       // 日期
  questions: number;  // 答题数
  correct: number;    // 正确数
  accuracy: number;   // 正确率
}

// ── 知识点掌握度条 ──
interface MasteryBar {
  skill_id: string;       // 知识点 ID
  p_known: number;        // 掌握概率（0~1）
  mastery_level: string;  // 掌握等级文本
  attempt_count: number;  // 尝试次数
  correct_count: number;  // 正确次数
}

// ── 热力图单元格 ──
interface HeatmapCell {
  day: number;   // 星期几（1=周一…7=周日）
  hour: number;  // 小时（0~23）
  count: number; // 答题数
}

// ── 遗忘曲线数据点 ──
interface RetentionPoint {
  day: number;       // 距学习的天数
  retention: number; // 保留率（0~100）
}

// ── 单个知识点的遗忘曲线 ──
interface RetentionSkill {
  skill_id: string;          // 知识点 ID
  label: string;             // 显示标签
  subject: string;           // 所属学科
  mastery: number;           // 当前掌握度
  attempt_count: number;     // 练习次数
  curve: RetentionPoint[];   // 遗忘曲线点序列
}

// ── 遗忘曲线整体数据 ──
interface RetentionData {
  skills: RetentionSkill[];          // 所有知识点
  total: number;                     // 知识点总数
  avg_retention_7d: number;          // 7 日平均保留率
  at_risk: RetentionSkill[];         // 高风险（7日后 < 50%）知识点
}

// ── 错因分布项 ──
interface ErrorDist {
  type: string;  // 错误类型标识
  count: number; // 出现次数
  pct: number;   // 占比（0~1）
}

// ── 行为数据中的学习时段点 ──
interface BehaviorPoint {
  day: number;     // 星期几
  day_name: string; // 星期名称
  hour: number;    // 小时
  questions: number; // 答题数
}

// ── 完整分析数据（analytics Tab） ──
interface AnalyticsData {
  user_id: string;
  time_range: string;
  overview: Overview;
  daily_trend: DailyPoint[];
  mastery_bars: MasteryBar[];
  error_distribution: ErrorDist[];
  hourly_heatmap: HeatmapCell[];
}

// ── 完整行为数据（habits Tab） ──
interface BehaviorData {
  behavior: {
    current_streak: number;           // 当前连续天数
    longest_streak: number;           // 历史最长连续
    best_study_hours: number[];       // 效率最高时段（小时）
    regularity_score: number;         // 规律性评分（0~1）
    fatigue_drop_minute: number | null; // 疲劳下降时间点（分钟）
    total_sessions: number;           // 总练习次数
    avg_session_minutes: number;      // 平均每次时长
    recommendations: string[];        // 个性化建议列表
  };
  daily_goal: {                       // 每日目标
    level: string;                    // 强度等级
    target_questions: number;         // 目标题数
    today_done: number;               // 今日已完成
    today_remaining: number;          // 今日剩余
    today_accuracy: number;           // 今日正确率
    is_completed: boolean;            // 是否完成
    streak_days: number;              // 连续达标天数
    message: string;                  // 提示消息
  };
  tiny_habits: {                      // 微习惯推荐
    name: string;                     // 习惯名称
    anchor: string;                   // 锚点行为
    behavior: string;                 // 新行为
    celebration: string;              // 庆祝方式
    days_done: number;                // 已坚持天数
    total_days: number;               // 总天数
    consistency: number;              // 坚持率（0~1）
  }[];
  pomodoro: {                         // 番茄钟建议
    work_minutes: number;
    break_minutes: number;
    message: string;
  };
}

// ── Tab 切换类型 ──
type Tab = "analytics" | "habits";

// ═══════════════════════════════════════════════
//  工具常量 & 函数
// ═══════════════════════════════════════════════

// ── 错误类型中文标签映射 ──
const ERROR_LABELS: Record<string, string> = {
  conceptual: "概念错误",
  procedural: "程序错误",
  computation: "计算错误",
  reading: "审题错误",
  transfer: "迁移错误",
  meta: "元认知",
};

// ── 掌握等级 → 颜色映射 ──
const MASTERY_COLORS: Record<string, string> = {
  "已掌握": "var(--color-success)",
  "接近掌握": "#60a5fa",
  "发展中": "var(--color-warning)",
  "初学": "var(--color-error)",
  "未接触": "var(--color-text-muted)",
};

// ── 掌握等级 → Emoji 映射 ──
const MASTERY_EMOJI: Record<string, string> = {
  "已掌握": "✅",
  "接近掌握": "🔷",
  "发展中": "🔶",
  "初学": "🔴",
  "未接触": "⬜",
};

// ── 生成环比变化字符串（↑/↓/→） ──
function deltaStr(curr: number, prev: number, fmt: (n: number) => string): string {
  const d = curr - prev;
  if (d > 0) return `↑${fmt(d)}`;
  if (d < 0) return `↓${fmt(Math.abs(d))}`;
  return "→ 0";
}

// ── 根据环比变化返回颜色（上升绿 / 下降红 / 持平灰） ──
function deltaColor(curr: number, prev: number): string {
  if (curr > prev) return "var(--color-success)";
  if (curr < prev) return "var(--color-error)";
  return "var(--color-text-muted)";
}

// ═══════════════════════════════════════════════
//  趋势图组件 — 纯 SVG 线形图（题量趋势）
// ═══════════════════════════════════════════════

function TrendChart({ data }: { data: DailyPoint[] }) {
  const w = 600, h = 160, pad = { t: 20, r: 20, b: 30, l: 40 };
  const pw = w - pad.l - pad.r;
  const ph = h - pad.t - pad.b;

  const maxQ = Math.max(...data.map((d) => d.questions), 1);
  const xs = data.map((_, i) => pad.l + (i / Math.max(data.length - 1, 1)) * pw);
  const ys = data.map((d) => pad.t + ph - (d.questions / maxQ) * ph);

  const pointsQ = xs.map((x, i) => `${x},${ys[i].toFixed(1)}`).join(" ");
  const maxY = pad.t + ph;

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-auto" style={{ fontFamily: "inherit" }}>
      {/* 网格线 */}
      {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
        const y = pad.t + ph * (1 - frac);
        return (
          <g key={frac}>
            <line x1={pad.l} y1={y} x2={w - pad.r} y2={y} stroke="var(--color-border)" strokeWidth="0.5" />
            <text x={pad.l - 8} y={y + 4} textAnchor="end" fill="var(--color-text-muted)" fontSize="10">
              {Math.round(maxQ * frac)}
            </text>
          </g>
        );
      })}
      {/* 日期标签 */}
      {data.map((d, i) => (
        <text
          key={d.date}
          x={xs[i]}
          y={maxY + 18}
          textAnchor="middle"
          fill="var(--color-text-muted)"
          fontSize="9"
        >
          {d.date}
        </text>
      ))}
      {/* 面积填充 */}
      <polygon
        points={`${xs[0]},${maxY} ${pointsQ} ${xs[xs.length - 1]},${maxY}`}
        fill="var(--color-accent)"
        opacity="0.08"
      />
      {/* 折线 */}
      <polyline
        points={pointsQ}
        fill="none"
        stroke="var(--color-accent)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* 数据点圆点 */}
      {xs.map((x, i) => (
        <circle key={i} cx={x} cy={ys[i]} r="3" fill="var(--color-accent)" />
      ))}
    </svg>
  );
}

// ═══════════════════════════════════════════════
//  热力图组件 — 星期 × 时段答题分布
// ═══════════════════════════════════════════════

function HeatmapGrid({ data }: { data: HeatmapCell[] }) {
  const dayNames = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
  const hours = [8, 10, 14, 16, 20, 22];
  const maxQ = Math.max(...data.map((d) => d.count), 1);

  const getCell = (day: number, hour: number) =>
    data.find((d) => d.day === day && d.hour === hour)?.count ?? 0;

  // 根据题量计算单元格背景色（透明度渐变）
  const bg = (q: number) => {
    if (q === 0) return "var(--color-surface)";
    const alpha = 0.2 + (q / maxQ) * 0.8;
    return `rgba(0,102,255,${alpha.toFixed(2)})`;
  };

  return (
    <div className="overflow-x-auto">
      <div className="grid gap-px" style={{ gridTemplateColumns: `60px repeat(7, 1fr)` }}>
        {/* 表头：星期 */}
        <div />
        {dayNames.map((d) => (
          <div key={d} className="text-center text-[10px] text-[var(--color-text-muted)] py-1">{d}</div>
        ))}
        {/* 数据行：各时段 */}
        {hours.map((h) => (
          <div key={h} className="contents">
            <div className="text-[10px] text-[var(--color-text-muted)] flex items-center justify-end pr-2">
              {h}:00
            </div>
            {[1, 2, 3, 4, 5, 6, 7].map((day) => {
              const q = getCell(day, h);
              return (
                <div
                  key={day}
                  className="aspect-square flex items-center justify-center text-[9px] font-mono text-[var(--color-text-secondary)]"
                  style={{ backgroundColor: bg(q) }}
                  title={`${dayNames[day - 1]} ${h}:00 — ${q}题`}
                >
                  {q > 0 ? q : ""}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      {/* 图例：少 → 多 */}
      <div className="flex items-center gap-2 mt-3 justify-end text-[10px] text-[var(--color-text-muted)]">
        <span>少</span>
        <div className="w-3 h-3" style={{ backgroundColor: "var(--color-surface)" }} />
        <div className="w-3 h-3" style={{ backgroundColor: "rgba(0,102,255,0.3)" }} />
        <div className="w-3 h-3" style={{ backgroundColor: "rgba(0,102,255,0.6)" }} />
        <div className="w-3 h-3" style={{ backgroundColor: "rgba(0,102,255,0.9)" }} />
        <span>多</span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════
//  建议行动生成 — 基于当前数据规则化推荐
// ═══════════════════════════════════════════════

function generateSuggestions(
  overview: Overview | undefined,
  masteryBars: MasteryBar[] | undefined,
  errorDist: ErrorDist[] | undefined,
): { text: string; action: string; link: string }[] {
  const suggestions: { text: string; action: string; link: string }[] = [];
  if (!overview) return suggestions;

  // 规则1: 最弱知识点（p_known 最低）
  if (masteryBars && masteryBars.length > 0) {
    const weakest = masteryBars[0]; // 已按 p_known 升序排列
    if (weakest.p_known < 0.5) {
      suggestions.push({
        text: `${weakest.skill_id || "未命名"}(${(weakest.p_known * 100).toFixed(0)}%)是你当前最大短板，建议今天重点练习`,
        action: "针对性练习",
        link: `/practice?skill=${weakest.skill_id}`,
      });
    }
  }

  // 规则2: 最常见错误类型（占比 > 25% 时提醒）
  if (errorDist && errorDist.length > 0) {
    const top = errorDist[0];
    if (top.pct > 0.25) {
      const label = ERROR_LABELS[top.type] || top.type;
      suggestions.push({
        text: `${label}占${(top.pct * 100).toFixed(0)}%（偏高），去错题本专项突破`,
        action: "错题本",
        link: `/errors?filter=${top.type}`,
      });
    }
  }

  // 规则3: 连续3天未练习
  if (overview.study_days < 3) {
    suggestions.push({
      text: `最近练习偏少（${overview.study_days}天），来一组保持手感？💪`,
      action: "开始练习",
      link: "/practice",
    });
  }

  // 规则4: 正确率上升
  const accDelta = overview.accuracy - overview.prev_week.accuracy;
  if (accDelta > 0.05) {
    suggestions.push({
      text: `正确率上升${(accDelta * 100).toFixed(0)}%！继续保持势头 🔥`,
      action: "",
      link: "",
    });
  }

  // 规则5: 通用鼓励
  if (overview.study_minutes > 0) {
    suggestions.push({
      text: "坚持练习就是最好的进步，熟能生巧 ✨",
      action: "",
      link: "",
    });
  }

  return suggestions.slice(0, 5);
}

// ═══════════════════════════════════════════════
//  习惯养成 Tab — 展示每日目标、番茄钟、微习惯等
// ═══════════════════════════════════════════════

// ── 将数字小时转为中文时段描述 ──
function hourLabel(h: number): string {
  if (h < 12) return `上午${h}点`;
  if (h < 18) return `下午${h - 12}点`;
  return `晚上${h - 12}点`;
}

// ── 习惯 Tab 主组件 ──
function HabitTab({ data }: { data: BehaviorData | null }) {
  if (!data) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="animate-spin text-[var(--color-accent)]" size={24} />
      </div>
    );
  }

  const { behavior, daily_goal, tiny_habits, pomodoro } = data;
  const levelLabels: Record<string, string> = { beginner: "入门", regular: "日常", intensive: "强化" };

  return (
    <div className="space-y-6">
      {/* ── 每日目标卡片 ── */}
      <Card className="!p-5">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-[var(--color-text)]">
            🎯 今日目标 · {levelLabels[daily_goal.level] || daily_goal.level}模式
          </h3>
          <span className="text-[10px] text-[var(--color-text-muted)]">
            目标：{daily_goal.target_questions}题/天
          </span>
        </div>

        {/* 进度环 */}
        <div className="flex items-center gap-6 mb-4">
          <div className="relative w-20 h-20 flex-shrink-0">
            <svg viewBox="0 0 80 80" className="w-full h-full -rotate-90">
              <circle cx="40" cy="40" r="34" fill="none" stroke="var(--color-surface)" strokeWidth="6" />
              <circle
                cx="40" cy="40" r="34" fill="none"
                stroke={daily_goal.is_completed ? "var(--color-success)" : "var(--color-accent)"}
                strokeWidth="6" strokeLinecap="round"
                strokeDasharray={`${2 * Math.PI * 34}`}
                strokeDashoffset={`${2 * Math.PI * 34 * (1 - Math.min(daily_goal.today_done / daily_goal.target_questions, 1))}`}
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-lg font-bold text-[var(--color-text)]">{daily_goal.today_done}</span>
              <span className="text-[9px] text-[var(--color-text-muted)]">/{daily_goal.target_questions}</span>
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-[var(--color-text-secondary)] leading-relaxed">
              {daily_goal.message}
            </p>
            {daily_goal.today_accuracy > 0 && (
              <p className="text-[11px] text-[var(--color-text-muted)] mt-1">
                今日正确率 {(daily_goal.today_accuracy * 100).toFixed(0)}%
              </p>
            )}
          </div>
        </div>

        {/* 未完成时显示「去练习」按钮 */}
        {!daily_goal.is_completed && daily_goal.today_remaining > 0 && (
          <Link
            href="/practice"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-[var(--color-accent)] text-white text-xs hover:bg-[var(--color-accent-hover)] transition-colors"
            style={{ borderRadius: "2px" }}
          >
            <Timer size={13} /> 去完成今日目标
          </Link>
        )}
      </Card>

      {/* ── Streak + 最佳时段 + 规律性（三栏） ── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 连续学习 */}
        <Card className="!p-4">
          <div className="flex items-center gap-2 mb-2">
            <Flame size={16} className="text-[var(--color-warning)]" />
            <span className="text-xs font-bold text-[var(--color-text)]">连续学习</span>
          </div>
          <div className="text-2xl font-bold text-[var(--color-text)]">
            {behavior.current_streak}<span className="text-sm text-[var(--color-text-muted)]">天</span>
          </div>
          <div className="text-[10px] text-[var(--color-text-muted)] mt-1">
            最长连续 {behavior.longest_streak} 天
          </div>
          {behavior.current_streak >= 7 && (
            <div className="mt-2 text-[10px] text-[var(--color-success)] font-medium">🔥 习惯已形成</div>
          )}
        </Card>

        {/* 最佳时段 */}
        <Card className="!p-4">
          <div className="flex items-center gap-2 mb-2">
            <Zap size={16} className="text-[var(--color-accent)]" />
            <span className="text-xs font-bold text-[var(--color-text)]">最佳时段</span>
          </div>
          {behavior.best_study_hours.length > 0 ? (
            <div className="text-sm text-[var(--color-text-secondary)]">
              {behavior.best_study_hours.map((h) => hourLabel(h)).join(" · ")}
            </div>
          ) : (
            <div className="text-sm text-[var(--color-text-muted)]">数据收集中</div>
          )}
          <div className="text-[10px] text-[var(--color-text-muted)] mt-1">
            效率最高的学习时段
          </div>
        </Card>

        {/* 规律性评分 */}
        <Card className="!p-4">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp size={16} className="text-[var(--color-success)]" />
            <span className="text-xs font-bold text-[var(--color-text)]">规律性</span>
          </div>
          <div className="text-2xl font-bold text-[var(--color-text)]">
            {(behavior.regularity_score * 100).toFixed(0)}<span className="text-sm text-[var(--color-text-muted)]">分</span>
          </div>
          <div className="text-[10px] text-[var(--color-text-muted)] mt-1">
            {behavior.regularity_score > 0.7 ? "学习节奏很稳定 ✨" :
             behavior.regularity_score > 0.4 ? "正在形成规律 💪" : "时间不太固定"}
          </div>
        </Card>
      </div>

      {/* ── 番茄钟建议 ── */}
      <Card title="🍅 番茄钟建议" className="!p-5">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 px-4 py-2 bg-[var(--color-surface)]" style={{ borderRadius: "2px" }}>
            <span className="text-lg font-bold text-[var(--color-accent)]">{pomodoro.work_minutes}</span>
            <span className="text-xs text-[var(--color-text-muted)]">分钟学习</span>
          </div>
          <span className="text-[var(--color-text-muted)] text-xs">+</span>
          <div className="flex items-center gap-2 px-4 py-2 bg-[var(--color-surface)]" style={{ borderRadius: "2px" }}>
            <span className="text-lg font-bold text-[var(--color-success)]">{pomodoro.break_minutes}</span>
            <span className="text-xs text-[var(--color-text-muted)]">分钟休息</span>
          </div>
        </div>
        <p className="text-xs text-[var(--color-text-secondary)] mt-3">{pomodoro.message}</p>
      </Card>

      {/* ── 微习惯推荐 ── */}
      <Card title="🌱 微习惯推荐 (TinyHabits)" className="!p-5">
        <div className="space-y-4">
          {tiny_habits.map((h, i) => (
            <div key={i} className="flex items-start gap-3 p-3 bg-[var(--color-surface)]" style={{ borderRadius: "2px" }}>
              <div className="w-8 h-8 bg-[var(--color-accent)] flex items-center justify-center flex-shrink-0" style={{ borderRadius: "2px" }}>
                <span className="text-white text-xs font-bold">{i + 1}</span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-[var(--color-text)]">{h.name}</p>
                <p className="text-[11px] text-[var(--color-text-secondary)] mt-0.5">
                  <span className="text-[var(--color-text-muted)]">{h.anchor}</span> → {h.behavior}
                </p>
                <p className="text-[10px] text-[var(--color-text-muted)] mt-1">
                  坚持率 {(h.consistency * 100).toFixed(0)}% · {h.celebration}
                </p>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* ── 行为分析建议 ── */}
      {behavior.recommendations.length > 0 && (
        <Card title="💡 个性化建议" className="!p-5">
          <div className="space-y-2">
            {behavior.recommendations.map((r, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-[var(--color-text-secondary)] leading-relaxed">
                <span className="text-[var(--color-accent)] mt-0.5">•</span>
                <span>{r}</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* ── 汇总统计 ── */}
      <Card className="!p-5">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-lg font-bold text-[var(--color-text)]">{behavior.total_sessions}</div>
            <div className="text-[10px] text-[var(--color-text-muted)]">总练习次数</div>
          </div>
          <div>
            <div className="text-lg font-bold text-[var(--color-text)]">{behavior.avg_session_minutes.toFixed(0)}min</div>
            <div className="text-[10px] text-[var(--color-text-muted)]">平均每次</div>
          </div>
          <div>
            <div className="text-lg font-bold text-[var(--color-text)]">
              {behavior.fatigue_drop_minute ? `${behavior.fatigue_drop_minute}min` : "—"}
            </div>
            <div className="text-[10px] text-[var(--color-text-muted)]">专注力峰值</div>
          </div>
        </div>
      </Card>
    </div>
  );
}

// ═══════════════════════════════════════════════
//  遗忘曲线面板 — SVG 多线图展示各知识点遗忘趋势
// ═══════════════════════════════════════════════

function RetentionPanel() {
  const [data, setData] = useState<RetentionData | null>(null);
  const [loading, setLoading] = useState(true);

  // 请求遗忘曲线数据
  useEffect(() => {
    fetch(`${API_BASE}/api/knowledge/retention?user_id=default_user`)
      .then((r) => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return null;
  if (!data || data.skills.length === 0) return null;

  const colors = ["#0066FF", "#f59e0b", "#22c55e", "#a855f7", "#ec4899"];
  const days = [0, 1, 3, 7, 14, 30, 60, 90];
  const w = 500, h = 220, pad = { l: 40, r: 20, t: 20, b: 30 };
  const pw = w - pad.l - pad.r, ph = h - pad.t - pad.b;

  return (
    <Card title={`🧠 遗忘曲线预估 · 7日后平均保留 ${data.avg_retention_7d}%`} className="mb-8 !p-5">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full max-w-lg mx-auto">
        {/* 网格线（保留率参考线） */}
        {[0, 25, 50, 75, 100].map((v) => (
          <line key={v} x1={pad.l} y1={pad.t + ph * (1 - v / 100)}
            x2={pad.l + pw} y2={pad.t + ph * (1 - v / 100)}
            stroke="#1a1a1a" strokeWidth={0.5} />
        ))}
        {/* X 轴标签（天） */}
        {days.map((d, i) => (
          <text key={d} x={pad.l + (pw * i) / (days.length - 1)} y={h - 4}
            textAnchor="middle" fill="#525252" fontSize={9}>{d === 0 ? "现在" : `${d}天`}</text>
        ))}
        {/* 各知识点遗忘曲线（最多5条，每条不同颜色） */}
        {data.skills.slice(0, 5).map((skill, si) => (
          <polyline key={skill.skill_id}
            points={skill.curve.map((p, i) =>
              `${pad.l + (pw * i) / (days.length - 1)},${pad.t + ph * (1 - p.retention / 100)}`
            ).join(" ")}
            fill="none" stroke={colors[si]} strokeWidth={2} opacity={0.8}
          />
        ))}
        {/* 图例 */}
        {data.skills.slice(0, 5).map((skill, si) => (
          <text key={skill.skill_id} x={pad.l + pw + 8} y={pad.t + si * 16 + 4}
            fill={colors[si]} fontSize={9}>{skill.label}</text>
        ))}
      </svg>
      {/* 高风险知识点提醒 */}
      {data.at_risk.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[var(--color-surface)]">
          <div className="text-xs text-[var(--color-text-muted)] mb-1">
            ⚠️ 7天后保持率 &lt; 50% 的高风险知识点：
          </div>
          <div className="flex flex-wrap gap-1.5">
            {data.at_risk.map((s) => (
              <span key={s.skill_id} className="text-xs px-2 py-0.5 border border-[#f59e0b] text-[#f59e0b]">
                {s.label}
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

// ═══════════════════════════════════════════════
//  每日摘要组件 — 昨日回顾 + 今日推荐
// ═══════════════════════════════════════════════

// ── 每日摘要数据结构 ──
interface DailySummary {
  yesterday: { date: string; total: number; correct: number; accuracy: number };
  vs_previous: { total: number; delta: number };
  streak: number;
  recommendations: { skill_id: string; mastery: number }[];
  encourage: string;
}

function DailySummaryCard() {
  const [summary, setSummary] = useState<DailySummary | null>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/progress/default_user/summary`)
      .then((r) => r.json())
      .then((d) => {
        if (d.yesterday) setSummary(d);
      })
      .catch(() => {});
  }, []);

  if (!summary) return null;

  // 环比变化文本
  const deltaStr = summary.vs_previous.delta > 0
    ? `↑${summary.vs_previous.delta}`
    : summary.vs_previous.delta < 0
    ? `↓${Math.abs(summary.vs_previous.delta)}`
    : "→";

  return (
    <div className="mb-8 p-5 border border-[var(--color-accent)]/30 bg-[var(--color-accent)]/5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-[var(--color-text)]">
          📊 昨日回顾 · {summary.yesterday.date}
        </h3>
        {/* 连续学习天数 */}
        {summary.streak > 0 && (
          <span className="text-xs text-[var(--color-warning)] flex items-center gap-1">
            🔥 连续 {summary.streak} 天
          </span>
        )}
      </div>
      {/* 三列摘要统计 */}
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <div className="text-lg font-bold text-[var(--color-text)]">
            {summary.yesterday.total}<span className="text-xs text-[var(--color-text-muted)]">题</span>
          </div>
          <div className="text-[10px] text-[var(--color-text-muted)]">
            较前日 {deltaStr}
          </div>
        </div>
        <div>
          <div className="text-lg font-bold text-[var(--color-text)]">
            {(summary.yesterday.accuracy * 100).toFixed(0)}<span className="text-xs text-[var(--color-text-muted)]">%</span>
          </div>
          <div className="text-[10px] text-[var(--color-text-muted)]">正确率</div>
        </div>
        <div>
          <div className="text-lg font-bold text-[var(--color-text)]">
            {summary.yesterday.correct}/{summary.yesterday.total}
          </div>
          <div className="text-[10px] text-[var(--color-text-muted)]">正确/总题</div>
        </div>
      </div>
      {/* 今日推荐知识点 */}
      {summary.recommendations.length > 0 && (
        <div className="flex items-center gap-2 text-[10px] text-[var(--color-text-muted)]">
          <span>🎯 今日推荐：</span>
          {summary.recommendations.map((r) => (
            <span key={r.skill_id} className="px-1.5 py-0.5 bg-[var(--color-surface)] text-[var(--color-text-secondary)]">
              {r.skill_id} ({r.mastery}%)
            </span>
          ))}
        </div>
      )}
      <p className="text-[10px] text-[var(--color-text-muted)] mt-2">{summary.encourage}</p>
    </div>
  );
}

// ═══════════════════════════════════════════════
//  主导出组件 — AnalyticsTab（学情分析页面）
// ═══════════════════════════════════════════════

export function AnalyticsTab() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [behaviorData, setBehaviorData] = useState<BehaviorData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("analytics");          // 当前 Tab
  const [timeRange, setTimeRange] = useState<"week" | "month" | "all">("week"); // 时间范围

  // 获取分析数据（切换时间范围时重新请求）
  useEffect(() => {
    setLoading(true);
    fetch(`${API_BASE}/api/practice/stats?time_range=${timeRange}`)
      .then((r) => r.json())
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [timeRange]);

  // 切换到 habits Tab 时获取行为数据
  useEffect(() => {
    if (tab === "habits") {
      fetch(`${API_BASE}/api/practice/behavior?time_range=${timeRange}`)
        .then((r) => r.json())
        .then((d) => setBehaviorData(d))
        .catch(() => {});
    }
  }, [tab, timeRange]);

  // 基于数据生成建议（memo 缓存）
  const suggestions = useMemo(() => {
    if (!data) return [];
    return generateSuggestions(data.overview, data.mastery_bars, data.error_distribution);
  }, [data]);

  // ── 加载中状态 ──
  if (loading) {
    return (
      <div>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="animate-spin text-[var(--color-accent)]" size={24} />
        </div>
      </div>
    );
  }

  // ── 无数据（首次使用）状态 ──
  if (!data || data.overview.total_questions === 0) {
    return (
      <div>
        <div className="max-w-3xl mx-auto px-6 py-16 text-center">
          <BarChart3 size={40} className="mx-auto mb-4 text-[var(--color-text-muted)]" />
          <h1 className="text-3xl font-bold text-[var(--color-text)] mb-2">学情分析</h1>
          <p className="text-[var(--color-text-muted)] mb-6">还没有练习数据</p>
          <Link
            href="/practice"
            className="inline-block px-6 py-2.5 bg-[var(--color-accent)] text-white text-sm hover:bg-[var(--color-accent-hover)] transition-colors"
          >
            去练习
          </Link>
        </div>
      </div>
    );
  }

  // ── 解构数据 ──
  const overview = data?.overview;
  const daily_trend = data?.daily_trend || [];
  const mastery_bars = data?.mastery_bars || [];
  const error_distribution = data?.error_distribution || [];
  const hourly_heatmap = data?.hourly_heatmap || [];
  const acc = overview ? (overview.accuracy * 100).toFixed(0) : "0";
  const h = overview ? Math.floor(overview.study_minutes / 60) : 0;
  const min = overview ? Math.round(overview.study_minutes % 60) : 0;

  return (
    <div>
      <div>
        {/* ── 页面头部：标题 + Tab 切换 + 时间范围 + 错题本入口 ── */}
        <div className="flex items-center justify-between mb-8 flex-wrap gap-3">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl md:text-3xl font-bold tracking-tight text-[var(--color-text)]">
              <BarChart3 size={24} className="inline mr-2 text-[var(--color-accent)]" />
              学情分析
            </h1>
            {/* Tab 切换器：数据 / 习惯 */}
            <div className="flex bg-[var(--color-surface)] p-0.5" style={{ borderRadius: "2px" }}>
              {([
                { key: "analytics", label: "数据", icon: <BarChart3 size={12} /> },
                { key: "habits", label: "习惯", icon: <Heart size={12} /> },
              ] as { key: Tab; label: string; icon: React.ReactNode }[]).map((t) => (
                <button
                  key={t.key}
                  onClick={() => setTab(t.key)}
                  className={`flex items-center gap-1 px-3 py-1 text-xs font-medium transition-colors ${
                    tab === t.key
                      ? "bg-[var(--color-accent)] text-white"
                      : "text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                  }`}
                  style={{ borderRadius: "2px" }}
                >
                  {t.icon}
                  {t.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {/* 时间范围切换 */}
            {(["week", "month", "all"] as const).map((r) => (
              <button
                key={r}
                onClick={() => setTimeRange(r)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  timeRange === r
                    ? "bg-[var(--color-accent)] text-white"
                    : "bg-[var(--color-surface)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                }`}
              >
                {r === "week" ? "本周" : r === "month" ? "本月" : "全部"}
              </button>
            ))}
            <Link
              href="/errors"
              className="ml-2 flex items-center gap-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
            >
              <BookOpen size={13} /> 错题本
            </Link>
          </div>
        </div>

        {/* ── 根据当前 Tab 显示不同内容 ── */}
        {tab === "analytics" ? (
          <>
            {/* ── ① 总览概览卡片（4 张：总题数、正确率、学习天数、时长） ── */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          {[
            {
              icon: <Target size={16} />,
              label: "总题数",
              val: overview.total_questions,
              prev: overview.prev_week.total_questions,
              fmt: (n: number) => `${n}`,
            },
            {
              icon: <TrendingUp size={16} />,
              label: "正确率",
              val: overview.accuracy,
              prev: overview.prev_week.accuracy,
              fmt: (n: number) => `${(n * 100).toFixed(0)}%`,
            },
            {
              icon: <CalendarDays size={16} />,
              label: "学习天数",
              val: overview.study_days,
              prev: overview.prev_week.study_days,
              fmt: (n: number) => `${n}天`,
            },
            {
              icon: <Clock size={16} />,
              label: "学习时长",
              val: overview.study_minutes,
              prev: overview.prev_week.study_minutes,
              fmt: (n: number) => {
                const hh = Math.floor(n / 60);
                const mm = Math.round(n % 60);
                return hh > 0 ? `${hh}h${mm}m` : `${mm}m`;
              },
            },
          ].map((c, i) => (
            <Card key={i} className="!p-4">
              <div className="text-[var(--color-accent)] mb-1.5">{c.icon}</div>
              <div className="text-xl md:text-2xl font-bold text-[var(--color-text)]">
                {c.fmt(c.val)}
              </div>
              <div className="text-[11px] text-[var(--color-text-muted)] mt-0.5">
                {c.label}
              </div>
              {/* 环比变化 */}
              <div
                className="text-[10px] mt-1"
                style={{ color: deltaColor(c.val, c.prev) }}
              >
                {deltaStr(c.val, c.prev, c.fmt)} vs 上期
              </div>
            </Card>
          ))}
        </div>

        {/* ── ② 每日练习趋势图 ── */}
        <Card title={`📈 每日练习趋势 · ${timeRange === "week" ? "7天" : timeRange === "month" ? "30天" : "全部"}`} className="mb-8 !p-5">
          <TrendChart data={daily_trend} />
        </Card>

        {/* ── ③ 知识掌握度 + ④ 错因分布（两栏并排） ── */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* 知识掌握度柱状图 */}
          <Card title="🔥 知识掌握度" className="!p-5">
            {mastery_bars.length === 0 ? (
              <p className="text-xs text-[var(--color-text-muted)]">暂无数据，答几道题就出来了</p>
            ) : (
              <div className="space-y-3">
                {mastery_bars.map((mb) => {
                  const pct = Math.round(mb.p_known * 100);
                  const color =
                    mb.p_known >= 0.8
                      ? "var(--color-success)"
                      : mb.p_known >= 0.5
                      ? "var(--color-warning)"
                      : "var(--color-error)";
                  return (
                    <div key={mb.skill_id}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-[var(--color-text-secondary)] truncate max-w-[140px]">
                          {MASTERY_EMOJI[mb.mastery_level] || ""} {mb.skill_id}
                        </span>
                        <span className="text-xs text-[var(--color-text-muted)]">{pct}%</span>
                      </div>
                      {/* 进度条 */}
                      <div className="w-full h-1.5 bg-[var(--color-surface)]">
                        <div
                          className="h-full transition-all"
                          style={{ width: `${pct}%`, backgroundColor: color }}
                        />
                      </div>
                      <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                        {mb.correct_count}/{mb.attempt_count}正确 · {mb.mastery_level}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </Card>

          {/* 错因分布 */}
          <Card title="📊 错因分布" className="!p-5">
            {error_distribution.length === 0 ? (
              <p className="text-xs text-[var(--color-text-muted)]">暂无错题，继续保持！</p>
            ) : (
              <div className="space-y-3">
                {error_distribution.map((e) => {
                  const label = ERROR_LABELS[e.type] || e.type;
                  return (
                    <div key={e.type}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-[var(--color-text-secondary)]">{label}</span>
                        <span className="text-xs text-[var(--color-text-muted)]">
                          {e.count}次 · {(e.pct * 100).toFixed(0)}%
                        </span>
                      </div>
                      {/* 错误占比条 */}
                      <div className="w-full h-1.5 bg-[var(--color-surface)]">
                        <div
                          className="h-full bg-[var(--color-error)] transition-all"
                          style={{ width: `${(e.pct * 100).toFixed(0)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            {error_distribution.length > 0 && (
              <Link
                href="/errors"
                className="inline-block mt-4 text-[11px] text-[var(--color-accent)] hover:underline"
              >
                查看全部错题 →
              </Link>
            )}
          </Card>
        </div>

        {/* ── ⑤ 学习时段热力图 ── */}
        <Card title="⏰ 学习时段" className="mb-8 !p-5">
          <HeatmapGrid data={hourly_heatmap} />
        </Card>

        {/* ── ⑤.5 雷达图（综合能力） ── */}
        <div className="mb-8">
          <RadarChart />
        </div>

        {/* ── ⑥ 遗忘曲线 ── */}
        <RetentionPanel />

        {/* ── ⑦ 建议行动列表 ── */}
        {suggestions.length > 0 && (
          <Card title="🎯 建议行动" className="!p-5">
            <div className="space-y-2">
              {suggestions.map((s, i) => (
                <div
                  key={i}
                  className="flex items-start gap-2 text-sm text-[var(--color-text-secondary)] leading-relaxed"
                >
                  <span className="text-[var(--color-accent)] mt-0.5">•</span>
                  <span>
                    {s.text}
                    {s.link && (
                      <Link
                        href={s.link}
                        className="ml-1 text-[var(--color-accent)] hover:underline text-xs"
                      >
                        {s.action || "去看看"} →
                      </Link>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        )}
          </>
        ) : (
          /* ── habits Tab：渲染习惯养成面板 ── */
          <HabitTab data={behaviorData} />
        )}
      </div>
    </div>
  );
}

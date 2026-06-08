// ═══════════════════════════════════════════════
//  类型定义 — 对应后端返回的数据结构
// ═══════════════════════════════════════════════

// ── 总览统计 ──
export interface Overview {
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
export interface DailyPoint {
  date: string;       // 日期
  questions: number;  // 答题数
  correct: number;    // 正确数
  accuracy: number;   // 正确率
}

// ── 知识点掌握度条 ──
export interface MasteryBar {
  skill_id: string;       // 知识点 ID
  p_known: number;        // 掌握概率（0~1）
  mastery_level: string;  // 掌握等级文本
  attempt_count: number;  // 尝试次数
  correct_count: number;  // 正确次数
}

// ── 热力图单元格 ──
export interface HeatmapCell {
  day: number;   // 星期几（1=周一…7=周日）
  hour: number;  // 小时（0~23）
  count: number; // 答题数
}

// ── 遗忘曲线数据点 ──
export interface RetentionPoint {
  day: number;       // 距学习的天数
  retention: number; // 保留率（0~100）
}

// ── 单个知识点的遗忘曲线 ──
export interface RetentionSkill {
  skill_id: string;          // 知识点 ID
  label: string;             // 显示标签
  subject: string;           // 所属学科
  mastery: number;           // 当前掌握度
  attempt_count: number;     // 练习次数
  curve: RetentionPoint[];   // 遗忘曲线点序列
}

// ── 遗忘曲线整体数据 ──
export interface RetentionData {
  skills: RetentionSkill[];          // 所有知识点
  total: number;                     // 知识点总数
  avg_retention_7d: number;          // 7 日平均保留率
  at_risk: RetentionSkill[];         // 高风险（7日后 < 50%）知识点
}

// ── 错因分布项 ──
export interface ErrorDist {
  type: string;  // 错误类型标识
  count: number; // 出现次数
  pct: number;   // 占比（0~1）
}

// ── 行为数据中的学习时段点 ──
export interface BehaviorPoint {
  day: number;     // 星期几
  day_name: string; // 星期名称
  hour: number;    // 小时
  questions: number; // 答题数
}

// ── 每日目标 ──
export interface DailyGoal {
  level: string;                    // 强度等级
  target_questions: number;         // 目标题数
  today_done: number;               // 今日已完成
  today_remaining: number;          // 今日剩余
  today_accuracy: number;           // 今日正确率
  is_completed: boolean;            // 是否完成
  streak_days: number;              // 连续达标天数
  message: string;                  // 提示消息
}

// ── 微习惯推荐 ──
export interface TinyHabit {
  name: string;                     // 习惯名称
  anchor: string;                   // 锚点行为
  behavior: string;                 // 新行为
  celebration: string;              // 庆祝方式
  days_done: number;                // 已坚持天数
  total_days: number;               // 总天数
  consistency: number;              // 坚持率（0~1）
}

// ── 番茄钟建议 ──
export interface Pomodoro {
  work_minutes: number;
  break_minutes: number;
  message: string;
}

// ── 完整行为数据（habits Tab） ──
export interface BehaviorData {
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
  daily_goal: DailyGoal;
  tiny_habits: TinyHabit[];
  pomodoro: Pomodoro;
}

// ── 完整分析数据（analytics Tab） ──
export interface AnalyticsData {
  user_id: string;
  time_range: string;
  overview: Overview;
  daily_trend: DailyPoint[];
  mastery_bars: MasteryBar[];
  error_distribution: ErrorDist[];
  hourly_heatmap: HeatmapCell[];
}

// ── 每日摘要数据结构 ──
export interface DailySummary {
  yesterday: { date: string; total: number; correct: number; accuracy: number };
  vs_previous: { total: number; delta: number };
  streak: number;
  recommendations: { skill_id: string; mastery: number }[];
  encourage: string;
}

// ── 建议行动项 ──
export interface Suggestion {
  text: string;
  action: string;
  link: string;
}

// ── Tab 切换类型 ──
export type Tab = "analytics" | "habits";

// ═══════════════════════════════════════════════
//  工具常量 & 函数
// ═══════════════════════════════════════════════

// ── 错误类型中文标签映射 ──
export const ERROR_LABELS: Record<string, string> = {
  conceptual: "概念错误",
  procedural: "程序错误",
  computation: "计算错误",
  reading: "审题错误",
  transfer: "迁移错误",
  meta: "元认知",
};

// ── 掌握等级 → 颜色映射 ──
export const MASTERY_COLORS: Record<string, string> = {
  "已掌握": "var(--color-success)",
  "接近掌握": "#60a5fa",
  "发展中": "var(--color-warning)",
  "初学": "var(--color-error)",
  "未接触": "var(--color-text-muted)",
};

// ── 掌握等级 → Emoji 映射 ──
export const MASTERY_EMOJI: Record<string, string> = {
  "已掌握": "✅",
  "接近掌握": "🔷",
  "发展中": "🔶",
  "初学": "🔴",
  "未接触": "⬜",
};

// ── 生成环比变化字符串（↑/↓/→） ──
export function deltaStr(curr: number, prev: number, fmt: (n: number) => string): string {
  const d = curr - prev;
  if (d > 0) return `↑${fmt(d)}`;
  if (d < 0) return `↓${fmt(Math.abs(d))}`;
  return "→ 0";
}

// ── 根据环比变化返回颜色（上升绿 / 下降红 / 持平灰） ──
export function deltaColor(curr: number, prev: number): string {
  if (curr > prev) return "var(--color-success)";
  if (curr < prev) return "var(--color-error)";
  return "var(--color-text-muted)";
}

// ── 将数字小时转为中文时段描述 ──
export function hourLabel(h: number): string {
  if (h < 12) return `上午${h}点`;
  if (h < 18) return `下午${h - 12}点`;
  return `晚上${h - 12}点`;
}

// ── 建议行动生成 — 基于当前数据规则化推荐 ──
export function generateSuggestions(
  overview: Overview | undefined,
  masteryBars: MasteryBar[] | undefined,
  errorDist: ErrorDist[] | undefined,
): Suggestion[] {
  const suggestions: Suggestion[] = [];
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
        link: `/practice/errors?filter=${top.type}`,
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

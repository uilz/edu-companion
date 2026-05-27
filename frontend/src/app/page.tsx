// ============================================================
// 首页入口页面 (app/page.tsx)
// 展示欢迎语、学习概览、快速入口、薄弱项、学习建议及成就等
// ============================================================

"use client";

// React / Next 核心依赖
import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
// Lucide 图标库
import {
  Brain,
  Target,
  MessageCircle,
  Loader2,
  Dumbbell,
  Trophy,
  AlertCircle,
  Sparkles,
  ArrowRight,
  TrendingUp,
  BookOpen,
  GitGraph,
  Zap,
  Clock,
} from "lucide-react";
// 内部组件
import Card from "@/components/ui/Card";
import UnifiedSearch from "@/components/search/UnifiedSearch";

// API 基础地址，优先使用环境变量，否则回退到本地 8000 端口
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ---------- 类型定义 ----------

/** 后端返回的学习进度摘要 */
interface ProgressSummary {
  total_questions: number;      // 总答题数
  correct_answers: number;     // 正确数
  accuracy_rate: number;       // 正确率（0~1）
  study_minutes: number;       // 学习时长（分钟）
  mastered_skills: string[];   // 已掌握的知识点
  struggling_skills: string[]; // 薄弱知识点
  recommendations: string[];   // 个性化建议列表
}

/** 成就项 */
interface Achievement {
  id: string;
  name: string;
  icon: string;       // 表情符号
  unlocked: boolean;  // 是否已解锁
  tier: string;       // 等级
}

// ---------- 常量 ----------

/** 首页四宫格快捷入口配置 */
const QUICK_ACTIONS = [
  { emoji: "💬", title: "智能对话", desc: "随时提问，启发式学习", href: "/learn", color: "from-blue-500/20 to-cyan-500/10" },
  { emoji: "✏️", title: "开始练习", desc: "定制化刷题检测", href: "/practice", color: "from-emerald-500/20 to-teal-500/10" },
  { emoji: "📊", title: "学情分析", desc: "全方位进度追踪", href: "/analytics", color: "from-violet-500/20 to-purple-500/10" },
  { emoji: "🧠", title: "知识图谱", desc: "查漏补缺", href: "/dashboard?tab=graph", color: "from-amber-500/20 to-orange-500/10" },
];

export default function HomePage() {
  // ---- 根据当前时间生成问候语 ----
  const greeting = useMemo(() => {
    const h = new Date().getHours();
    if (h < 5) return { text: "夜深了", sub: "注意休息，明天继续 🌙", emoji: "🌙" };
    if (h < 9) return { text: "早上好", sub: "一日之计在于晨 ☀️", emoji: "☀️" };
    if (h < 13) return { text: "上午好", sub: "精力充沛，适合深度学习 💪", emoji: "💪" };
    if (h < 18) return { text: "下午好", sub: "保持节奏，稳扎稳打 🌤️", emoji: "🌤️" };
    return { text: "晚上好", sub: "温故知新，沉淀一天 🏠", emoji: "🏠" };
  }, []);

  // ---- 状态管理 ----
  const [progress, setProgress] = useState<ProgressSummary | null>(null);   // 学习进度数据
  const [achievements, setAchievements] = useState<Achievement[]>([]);      // 成就列表
  const [loading, setLoading] = useState(true);                             // 加载中标志

  // ---- 页面初始化：并行拉取进度和成就数据 ----
  useEffect(() => {
    async function loadData() {
      try {
        const [progressRes, achieveRes] = await Promise.all([
          fetch(`${API_BASE}/api/progress/default_user`),
          fetch(`${API_BASE}/api/achievements/default_user`),
        ]);
        if (progressRes.ok) setProgress(await progressRes.json());
        if (achieveRes.ok) {
          const aData = await achieveRes.json();
          setAchievements(aData.achievements || []);
        }
      } catch (e) {
        console.error("Failed to load dashboard data:", e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  // ---- 从原始数据派生展示值 ----
  const accuracy = progress?.accuracy_rate
    ? `${(progress.accuracy_rate * 100).toFixed(1)}%`
    : "—";
  const masteredCount = progress?.mastered_skills?.length || 0;
  const strugglingCount = progress?.struggling_skills?.length || 0;
  const unlockedAchievements = achievements.filter((a) => a.unlocked).length;
  const studyHours = progress?.study_minutes
    ? (progress.study_minutes / 60).toFixed(1)
    : "—";

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 sm:py-12">
        {/* ═════════ Hero 区域：问候语 + 统计小标签 ═════════ */}
        <header className="mb-10 sm:mb-14">
          <div className="flex items-center gap-3 mb-3">
            <span className="text-3xl">{greeting.emoji}</span>
            <div>
              <h1 className="text-3xl sm:text-4xl font-extrabold text-[var(--color-text)] tracking-tight">
                {greeting.text}
              </h1>
              <p className="text-sm text-[var(--color-text-muted)] mt-0.5">
                {greeting.sub}
              </p>
            </div>
          </div>

          {/* Stats mini-bar: 总题数、正确率、学习时长、掌握数 */}
          <div className="flex flex-wrap gap-3 mt-6">
            {loading ? (
              <Loader2 size={14} className="animate-spin text-[var(--color-text-muted)]" />
            ) : (
              <>
                <span className="swiss-badge swiss-badge-accent">
                  <Dumbbell size={12} />
                  {progress?.total_questions || 0} 题
                </span>
                <span className="swiss-badge">
                  <Target size={12} />
                  正确率 {accuracy}
                </span>
                <span className="swiss-badge">
                  <Clock size={12} />
                  {studyHours}h
                </span>
                <span className="swiss-badge">
                  <Brain size={12} />
                  {masteredCount} 掌握
                </span>
              </>
            )}
          </div>
        </header>

        {/* ═════════ 全局搜索框 ═════════ */}
        <div className="mb-8">
          <UnifiedSearch />
        </div>

        {/* ═════════ 四宫格快捷入口 ═════════ */}
        <section className="mb-10">
          <div className="swiss-section-header">
            <span className="swiss-section-title">快速入口</span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {QUICK_ACTIONS.map((action) => (
              <Link
                key={action.href}
                href={action.href}
                className="group relative overflow-hidden border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-4 sm:p-5 transition-all duration-200 hover:border-[var(--color-accent)] hover:shadow-md hover:-translate-y-0.5"
              >
                {/* Gradient background on hover */}
                <div className={`absolute inset-0 bg-gradient-to-br ${action.color} opacity-0 group-hover:opacity-100 transition-opacity duration-300`} />
                <div className="relative">
                  <div className="text-2xl mb-2">{action.emoji}</div>
                  <div className="text-sm font-semibold text-[var(--color-text)]">
                    {action.title}
                  </div>
                  <div className="text-xs text-[var(--color-text-muted)] mt-1">
                    {action.desc}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>

        {/* ═════════ 学习概览统计卡片 (四列网格) ═════════ */}
        <section className="mb-10">
          <div className="swiss-section-header">
            <span className="swiss-section-title">学习概览</span>
            <Link
              href="/analytics"
              className="flex items-center gap-1 text-xs text-[var(--color-accent)] hover:underline"
            >
              详细分析 <ArrowRight size={12} />
            </Link>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[
              { icon: Dumbbell, label: "完成题目", value: loading ? "—" : `${progress?.total_questions || 0} 道`, accent: "text-blue-400", bg: "bg-blue-500/5" },
              { icon: Target, label: "正确率", value: loading ? "—" : accuracy, accent: "text-emerald-400", bg: "bg-emerald-500/5" },
              { icon: Brain, label: "已掌握", value: loading ? "—" : `${masteredCount} 个`, accent: "text-violet-400", bg: "bg-violet-500/5" },
              { icon: Trophy, label: "成就", value: loading ? "—" : `${unlockedAchievements} 个`, accent: "text-amber-400", bg: "bg-amber-500/5" },
            ].map((stat) => (
              <div
                key={stat.label}
                className="swiss-card flex flex-col gap-2 p-4 sm:p-5"
              >
                <div className={`w-9 h-9 rounded-lg ${stat.bg} flex items-center justify-center ${stat.accent}`}>
                  <stat.icon size={17} />
                </div>
                <div>
                  <div className="text-xl sm:text-2xl font-bold text-[var(--color-text)]">
                    {stat.value}
                  </div>
                  <div className="text-xs text-[var(--color-text-muted)] mt-0.5">
                    {stat.label}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* ═════════ 主内容区：薄弱项 + 学习建议 + 成就 ═════════ */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* ---- 薄弱知识点 ---- */}
          <Card title="⚠️ 需要加强" accent>
            {loading ? (
              <div className="py-6 flex justify-center">
                <Loader2 size={18} className="animate-spin text-[var(--color-text-muted)]" />
              </div>
            ) : strugglingCount > 0 ? (
              <div className="space-y-2">
                {progress?.struggling_skills.slice(0, 5).map((skill) => (
                  <div
                    key={skill}
                    className="flex items-center gap-2.5 px-3 py-2.5 rounded-md bg-[var(--color-surface)] text-sm group hover:bg-[var(--color-surface-hover)] transition-colors"
                  >
                    <AlertCircle size={14} className="text-amber-400 flex-shrink-0" />
                    <span className="text-[var(--color-text-secondary)] flex-1">
                      {skill.replace(/_/g, " ")}
                    </span>
                    <ArrowRight size={12} className="text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                ))}
                <Link
                  href="/practice"
                  className="swiss-btn swiss-btn-outline w-full mt-3 text-xs"
                >
                  针对性练习 →
                </Link>
              </div>
            ) : (
              <div className="py-6 text-center">
                <Sparkles size={24} className="mx-auto mb-2 text-amber-400" />
                <p className="text-sm text-[var(--color-text-muted)]">暂无薄弱项，继续保持！</p>
              </div>
            )}
          </Card>

          {/* ---- 个性化学习建议 ---- */}
          <Card title="💡 学习建议" accent>
            {loading ? (
              <div className="py-6 flex justify-center">
                <Loader2 size={18} className="animate-spin text-[var(--color-text-muted)]" />
              </div>
            ) : progress?.recommendations?.length ? (
              <div className="space-y-2">
                {progress.recommendations.slice(0, 4).map((rec, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2.5 px-3 py-2.5 rounded-md bg-[var(--color-surface)] hover:bg-[var(--color-surface-hover)] transition-colors"
                  >
                    <Sparkles size={14} className="text-[var(--color-accent)] flex-shrink-0 mt-0.5" />
                    <span className="text-sm text-[var(--color-text-secondary)] leading-relaxed">
                      {rec}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-6 text-center">
                <MessageCircle size={24} className="mx-auto mb-2 text-blue-400" />
                <p className="text-sm text-[var(--color-text-muted)]">
                  开始对话获取个性化学习建议
                </p>
                <Link
                  href="/learn"
                  className="swiss-btn swiss-btn-primary mt-3 text-xs inline-flex"
                >
                  <MessageCircle size={13} />
                  开始对话
                </Link>
              </div>
            )}
          </Card>

          {/* ---- 成就展示 ---- */}
          {achievements.length > 0 && (
            <div className="lg:col-span-2">
              <Card title={`🏆 成就 (${unlockedAchievements}/${achievements.length})`} accent>
                <div className="flex flex-wrap gap-2">
                  {achievements.slice(0, 10).map((a) => (
                    <div
                      key={a.id}
                      className={`flex items-center gap-1.5 px-3 py-2 rounded-lg border text-sm transition-all ${
                        a.unlocked
                          ? "border-[var(--color-accent)] bg-[var(--color-accent-soft)] shadow-sm"
                          : "border-[var(--color-border)] opacity-35 grayscale"
                      }`}
                      title={a.unlocked ? a.name : `${a.name} (未解锁)`}
                    >
                      <span className="text-base">{a.icon}</span>
                      <span className={a.unlocked ? "text-[var(--color-text)] font-medium" : "text-[var(--color-text-muted)]"}>
                        {a.name}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          )}
        </div>

        {/* ═════════ 底部行动号召按钮 ═════════ */}
        <div className="mt-12 text-center">
          <div className="swiss-divider" />
          <Link
            href="/learn"
            className="inline-flex items-center gap-2 px-8 py-3.5 bg-[var(--color-accent)] text-white font-semibold rounded-lg hover:bg-[var(--color-accent-hover)] hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200"
          >
            <Zap size={18} />
            开始学习
          </Link>
          <p className="text-xs text-[var(--color-text-muted)] mt-3">
            随时随地，苹小果陪伴你的学习之旅
          </p>
        </div>
      </div>
    </main>
  );
}

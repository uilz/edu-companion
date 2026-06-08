'use client'; // 客户端组件标识

// React 与 Next.js 核心导入
import { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
// 图标库导入
import {
  BookOpen, Brain, Target, TrendingUp, MessageCircle,
  Loader2, Dumbbell, Trophy, AlertCircle, Sparkles,
  CheckCircle2, Clock, Flame,
} from 'lucide-react';
// 自定义 UI 组件导入
import Card from '@/components/ui/Card';
import UnifiedSearch from '@/components/search/UnifiedSearch';
import { API_BASE } from "@/lib/api/api";

// 学习进度概览（来自 analytics stats/overview）
interface StatsOverview {
  total_questions: number;
  total_correct: number;
  total_wrong: number;
  accuracy: number;
  total_sessions: number;
  study_minutes: number;
  mastered_count: number;
  weak_count: number;
  due_review_count: number;
  today_questions: number;
  cold_start: boolean;
}

// 薄弱知识点（来自 analytics stats/weak-skills）
interface WeakSkill {
  skill_id: string;
  label: string;
  mastery: number;
}

// 成就
interface Achievement {
  id: string;
  name: string;
  icon: string;
  unlocked: boolean;
  tier: string;
}

// CognitiveNode Dashboard (Phase 12)
interface DashboardOverview {
  mastery: Record<string, number>;
  queue: {
    node_id: string;
    label: string;
    level: string;
    urgency: number;
    proficiency_mean: number;
    direction: string;
    stagnation_days: number;
    action_type: string;
    reason: string;
  }[];
  trends: {
    improving: { label: string; proficiency_mean: number; stagnation_days: number; direction: string }[];
    declining: { label: string; proficiency_mean: number; stagnation_days: number; direction: string }[];
    stagnating: { label: string; proficiency_mean: number; stagnation_days: number; direction: string }[];
  };
  errors: Record<string, number>;
  engagement: {
    xp: number;
    streak: number;
    today_accuracy: number;
    today_practiced: number;
  };
}

// 快捷操作
const QUICK_ACTIONS = [
  { emoji: '💬', title: '智能对话', desc: '随时提问', href: '/learn' },
  { emoji: '✏️', title: '开始练习', desc: '刷题检测', href: '/practice' },
  { emoji: '📈', title: '学情分析', desc: '深度追踪', href: '/analytics' },
  { emoji: '🧠', title: '知识图谱', desc: '补充薄弱', href: '/knowledge-tree' },
];

export function OverviewTab() {
  const greeting = useMemo(() => {
    const h = new Date().getHours();
    if (h < 6) return '夜深了，注意休息 🌙';
    if (h < 12) return '早上好 ☀️';
    if (h < 18) return '下午好 🌤️';
    return '晚上好 🌙';
  }, []);

  const [stats, setStats] = useState<StatsOverview | null>(null);
  const [dashboard, setDashboard] = useState<DashboardOverview | null>(null);
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [weakSkills, setWeakSkills] = useState<WeakSkill[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [statsRes, dashRes, achieveRes, weakRes] = await Promise.all([
          fetch(`${API_BASE}/api/v7/practice/stats/overview`),
          fetch(`${API_BASE}/api/v2/dashboard/overview?user_id=default_user`),
          fetch(`${API_BASE}/api/v7/practice/achievements`),
          fetch(`${API_BASE}/api/v7/practice/stats/weak-skills`),
        ]);
        if (statsRes.ok) setStats(await statsRes.json());
        if (dashRes.ok) setDashboard(await dashRes.json());
        if (achieveRes.ok) {
          const aData = await achieveRes.json();
          setAchievements(aData.achievements || aData || []);
        }
        if (weakRes.ok) {
          const wData = await weakRes.json();
          setWeakSkills(wData.weak_skills || wData || []);
        }
      } catch (e) {
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const accuracy = dashboard
    ? `${(dashboard.engagement.today_accuracy * 100).toFixed(1)}%`
    : stats?.accuracy
      ? `${stats.accuracy}%`
      : '—';
  const masteredCount = stats?.mastered_count || 0;
  const unlockedAchievements = achievements.filter((a) => a.unlocked).length;

  // 练习队列：urgent 优先，取前 5
  const urgentItems = dashboard?.queue?.filter((q) => q.urgency > 0.5) || [];
  const learningItems = dashboard?.queue?.filter((q) => q.urgency <= 0.5) || [];
  const queueItems = [...urgentItems, ...learningItems].slice(0, 6);

  return (
    <div>
      {/* Header */}
      <header className="mb-8">
        <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight text-[var(--color-text)] mb-2">
          {greeting}
        </h1>
        <p className="text-sm sm:text-base text-[var(--color-text-muted)]">
          {loading ? (
            <Loader2 size={14} className="animate-spin inline" />
          ) : (
            <>
              已练习{' '}
              <span className="text-[var(--color-text)] font-semibold">
                {stats?.today_questions || dashboard?.engagement.today_practiced || 0}
              </span>
              题 · 正确率{' '}
              <span className="text-[var(--color-accent)] font-semibold">{accuracy}</span>
              {dashboard && (
                <>
                  {' · '}经验值{' '}
                  <span className="text-[var(--color-warning)] font-semibold">{dashboard.engagement.xp}</span>
                  {' · '}连续
                  <span className="text-[var(--color-warning)] font-semibold"> {dashboard.engagement.streak} 天</span>
                  <Flame size={14} className="inline ml-1 text-[var(--color-warning)]" />
                </>
              )}
            </>
          )}
        </p>
      </header>

      {/* 搜索栏 */}
      <div className="mb-8">
        <UnifiedSearch />
      </div>

      {/* 快捷操作 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        {QUICK_ACTIONS.map((action) => (
          <Link
            key={action.href}
            href={action.href}
            className="border border-[var(--color-border)] bg-[var(--color-card)] p-4 hover:border-[var(--color-accent)] transition-colors group"
          >
            <div className="text-xl mb-1.5">{action.emoji}</div>
            <div className="text-sm font-semibold text-[var(--color-text)] group-hover:text-[var(--color-accent)]">
              {action.title}
            </div>
            <div className="text-xs text-[var(--color-text-muted)]">{action.desc}</div>
          </Link>
        ))}
      </div>

      {/* 统计卡片 */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8">
        {[
          { icon: <Dumbbell size={18} />, label: '今日练习', value: loading ? '—' : `${stats?.today_questions || dashboard?.engagement.today_practiced || 0} 题`, color: 'text-[var(--color-info)]' },
          { icon: <Target size={18} />, label: '今日正确率', value: loading ? '—' : accuracy, color: 'text-[var(--color-success)]' },
          { icon: <Brain size={18} />, label: '已掌握', value: loading ? '—' : `${masteredCount} 个`, color: 'text-[var(--color-accent)]' },
          { icon: <Trophy size={18} />, label: '成就', value: loading ? '—' : `${unlockedAchievements} 个`, color: 'text-[var(--color-warning)]' },
        ].map((stat) => (
          <div key={stat.label} className="border border-[var(--color-border)] bg-[var(--color-card)] p-4 sm:p-5">
            <div className={`mb-2 ${stat.color}`}>{stat.icon}</div>
            <div className="text-xl sm:text-2xl font-semibold text-[var(--color-text)]">{stat.value}</div>
            <div className="text-xs text-[var(--color-text-muted)] mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 练习队列（Phase 10+12） */}
        <div>
          <Card title="🎯 今日练习队列">
            {loading ? (
              <div className="py-4 text-center"><Loader2 size={14} className="animate-spin mx-auto" /></div>
            ) : queueItems.length > 0 ? (
              <div className="space-y-1">
                {queueItems.map((item) => {
                  const isUrgent = item.urgency > 0.5;
                  return (
                    <Link
                      key={item.node_id}
                      href={`/practice?skill=${encodeURIComponent(item.label)}`}
                      className="flex items-center gap-2 px-3 py-2.5 bg-[var(--color-surface)] text-xs hover:bg-[var(--color-accent)]/10 active:scale-[0.97] transition-colors group"
                    >
                      <span className={`flex-shrink-0 ${isUrgent ? 'text-[var(--color-error)]' : 'text-[var(--color-info)]'}`}>
                        {isUrgent ? <Clock size={13} /> : <BookOpen size={13} />}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-[var(--color-text-secondary)] group-hover:text-[var(--color-accent)] truncate font-medium">
                          {item.label}
                        </div>
                        <div className="text-[10px] text-[var(--color-text-muted)] mt-0.5">
                          掌握度 {Math.round(item.proficiency_mean * 100)}% · {item.reason}
                        </div>
                      </div>
                      <div className={`text-[10px] font-semibold flex-shrink-0 ${isUrgent ? 'text-[var(--color-error)]' : 'text-[var(--color-text-muted)]'}`}>
                        {isUrgent ? '⚠ 复习' : '📖 练习'}
                      </div>
                    </Link>
                  );
                })}
                <Link
                  href="/practice"
                  className="block text-center text-xs text-[var(--color-accent)] hover:underline mt-2"
                >
                  查看更多练习 →
                </Link>
              </div>
            ) : (
              <div className="py-4 text-center text-xs text-[var(--color-text-muted)]">
                <CheckCircle2 size={16} className="mx-auto mb-1 text-[var(--color-success)]" />
                暂无待办练习，继续学习新知识吧！
              </div>
            )}
          </Card>
        </div>

        {/* 掌握度热力图 */}
        {dashboard?.mastery && Object.keys(dashboard.mastery).length > 0 && (
          <div>
            <Card title="🧠 掌握度概览">
              <div className="space-y-2">
                {Object.entries(dashboard.mastery).sort(([, a], [, b]) => a - b).map(([label, score]) => {
                  const pct = Math.round(score * 100);
                  let color: string;
                  if (pct >= 80) color = 'bg-[var(--color-success)]';
                  else if (pct >= 60) color = 'bg-[var(--color-success)]';
                  else if (pct >= 40) color = 'bg-[var(--color-warning)]';
                  else if (pct >= 20) color = 'bg-[var(--color-warning)]';
                  else color = 'bg-[var(--color-error)]';
                  return (
                    <div key={label} className="flex items-center gap-2">
                      <span className="text-xs text-[var(--color-text-secondary)] w-20 truncate flex-shrink-0">{label}</span>
                      <div className="flex-1 h-2.5 bg-[var(--color-surface)] rounded-full overflow-hidden">
                        <div className={`h-full ${color} rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-[10px] text-[var(--color-text-muted)] w-8 text-right flex-shrink-0">{pct}%</span>
                    </div>
                  );
                })}
              </div>
            </Card>
          </div>
        )}

        {/* 趋势（下降/停滞的知识点） */}
        {dashboard && (dashboard.trends.declining.length > 0 || dashboard.trends.stagnating.length > 0) && (
          <div>
            <Card title="📉 需要关注">
              {dashboard.trends.declining.slice(0, 3).map((item) => (
                <Link
                  key={`dec-${item.label}`}
                  href={`/practice?skill=${encodeURIComponent(item.label)}`}
                  className="flex items-center gap-2 px-3 py-2 bg-[var(--color-surface)] text-xs hover:bg-[var(--color-accent)]/10 active:scale-[0.97] transition-colors group mb-1"
                >
                  <TrendingUp size={13} className="text-[var(--color-error)] flex-shrink-0 rotate-180" />
                  <span className="text-[var(--color-text-secondary)] group-hover:text-[var(--color-accent)] flex-1">{item.label}</span>
                  <span className="text-[10px] text-[var(--color-error)]">{Math.round(item.proficiency_mean * 100)}% ↓</span>
                </Link>
              ))}
              {dashboard.trends.stagnating.slice(0, 3).map((item) => (
                <Link
                  key={`stg-${item.label}`}
                  href={`/practice?skill=${encodeURIComponent(item.label)}`}
                  className="flex items-center gap-2 px-3 py-2 bg-[var(--color-surface)] text-xs hover:bg-[var(--color-accent)]/10 active:scale-[0.97] transition-colors group mb-1"
                >
                  <AlertCircle size={13} className="text-[var(--color-warning)] flex-shrink-0" />
                  <span className="text-[var(--color-text-secondary)] group-hover:text-[var(--color-accent)] flex-1">{item.label}</span>
                  <span className="text-[10px] text-[var(--color-warning)]">停滞 {Math.round(item.stagnation_days)}天</span>
                </Link>
              ))}
            </Card>
          </div>
        )}

        {/* 薄弱知识点 */}
        <div>
          <Card title="需要加强">
            {loading ? (
              <div className="py-4 text-center"><Loader2 size={14} className="animate-spin mx-auto" /></div>
            ) : weakSkills.length > 0 ? (
              <div className="space-y-2">
                {weakSkills.slice(0, 5).map((skill) => (
                  <Link
                    key={skill.skill_id}
                    href={`/practice?skill=${encodeURIComponent(skill.label)}`}
                    className="flex items-center gap-2 px-3 py-2 bg-[var(--color-surface)] text-xs hover:bg-[var(--color-accent)]/10 active:scale-[0.97] transition-colors group"
                  >
                    <AlertCircle size={13} className="text-[var(--color-warning)] flex-shrink-0" />
                    <span className="text-[var(--color-text-secondary)] group-hover:text-[var(--color-accent)]">
                      {skill.label}
                    </span>
                    <span className="ml-auto text-[10px] text-[var(--color-text-muted)]">{Math.round(skill.mastery * 100)}%</span>
                  </Link>
                ))}
                <Link
                  href="/practice"
                  className="block text-center text-xs text-[var(--color-accent)] hover:underline mt-2"
                >
                  针对性练习 →
                </Link>
              </div>
            ) : (
              <div className="py-4 text-center text-xs text-[var(--color-text-muted)]">
                <Sparkles size={16} className="mx-auto mb-1 text-[var(--color-warning)]" />
                暂无薄弱项，继续保持！
              </div>
            )}
          </Card>
        </div>

        {/* 学习建议 */}
        <div>
          <Card title="学习建议">
            {loading ? (
              <div className="py-4 text-center"><Loader2 size={14} className="animate-spin mx-auto" /></div>
            ) : (() => {
              const tips: string[] = [];
              if (stats?.cold_start) tips.push("开始你的第一次练习吧！");
              if (weakSkills.length > 0) tips.push(`建议重点复习: ${weakSkills.slice(0, 3).map(s => s.label).join(', ')}`);
              if (stats && stats.accuracy < 60) tips.push("正确率较低，建议降低难度巩固基础");
              else if (stats && stats.accuracy > 90) tips.push("掌握不错！可以尝试更高难度的挑战");
              if (stats?.due_review_count && stats.due_review_count > 0) tips.push(`有 ${stats.due_review_count} 个知识点待复习`);
              return tips.length > 0 ? (
                <div className="space-y-2">
                  {tips.slice(0, 3).map((tip, i) => (
                    <div key={i} className="flex items-start gap-2 px-3 py-2 text-xs">
                      <Sparkles size={13} className="text-[var(--color-accent)] flex-shrink-0 mt-0.5" />
                      <span className="text-[var(--color-text-secondary)]">{tip}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="py-4 text-center text-xs text-[var(--color-text-muted)]">
                  <MessageCircle size={16} className="mx-auto mb-1 text-[var(--color-info)]" />
                  开始对话获取个性化建议
                </div>
              );
            })()}
          </Card>
        </div>

        {/* 成就（原有） */}
        {achievements.length > 0 && (
          <div className="lg:col-span-2">
            <Card title={`成就 (${unlockedAchievements}/${achievements.length})`}>
              <div className="flex flex-wrap gap-2">
                {achievements.slice(0, 8).map((a) => (
                  <div
                    key={a.id}
                    className={`flex items-center gap-1.5 px-3 py-1.5 border text-xs transition-all ${
                      a.unlocked
                        ? 'border-[var(--color-accent)] bg-[var(--color-accent)]/5'
                        : 'border-[var(--color-border)] opacity-40'
                    }`}
                  >
                    <span className="text-sm">{a.icon}</span>
                    <span className={a.unlocked ? 'text-[var(--color-text)]' : 'text-[var(--color-text-muted)]'}>
                      {a.name}
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}

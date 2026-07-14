"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  TrendingUp, Clock, Zap, Calendar, ChevronRight,
  BarChart3, Target, BookOpen,
} from "lucide-react";
import { authedFetch } from "@/lib/api/api";
import { Skeleton } from "@/components/ui/Skeleton";

// ── 类型 ──

interface GrowthRecord {
  id: string;
  session_id: string;
  session_title: string;
  session_started_at: number;
  session_finished_at: number | null;
  duration_minutes: number;
  skill_gains: SkillGain[];
  summary: string;
  reflection_snippet: string;
  key_takeaways: string[];
  total_gain: number;
}

interface SkillGain {
  skill: string;
  before: number;
  after: number;
  delta: number;
  evidence: string;
  category: string;
}

interface GrowthSummary {
  total_sessions: number;
  total_duration_minutes: number;
  total_skill_gains: number;
  total_gain_score: number;
  streak_days: number;
  recent_records: GrowthRecord[];
}

// ── 页面组件 ──

export default function GrowthPage() {
  const [summary, setSummary] = useState<GrowthSummary | null>(null);
  const [records, setRecords] = useState<GrowthRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        const [sumRes, recRes] = await Promise.all([
          authedFetch("/api/growth/summary"),
          authedFetch("/api/growth/records"),
        ]);
        if (sumRes.ok) setSummary(await sumRes.json());
        if (recRes.ok) {
          const data = await recRes.json();
          setRecords(data.records || []);
        }
      } catch (e) {
        console.error("Growth load failed:", e);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // ── Loading ──
  if (loading) return <GrowthSkeleton />;

  // ── Empty ──
  if (records.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 px-6">
        <div className="w-16 h-16 rounded-2xl bg-brand/10 flex items-center justify-center">
          <BarChart3 size={32} className="text-brand" />
        </div>
        <h2 className="text-xl font-bold text-ink-primary">还没有成长记录</h2>
        <p className="text-ink-muted text-sm text-center max-w-xs">
          完成一次学习 Session 后，这里会展示你的成长轨迹
        </p>
        <Link
          href="/"
          className="text-brand text-sm font-medium hover:underline"
        >
          返回首页开始学习 →
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-bg-primary">
      {/* ── 摘要卡片 ── */}
      {summary && <SummaryCard summary={summary} />}

      {/* ── 成长记录列表 ── */}
      <div className="px-4 py-4">
        <h2 className="text-sm font-semibold text-ink-muted mb-3">
          成长记录
        </h2>
        <div className="space-y-3">
          {records.map((record) => (
            <GrowthCard
              key={record.id}
              record={record}
              expanded={expanded === record.id}
              onToggle={() =>
                setExpanded(expanded === record.id ? null : record.id)
              }
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── 摘要卡片 ──

function SummaryCard({ summary }: { summary: GrowthSummary }) {
  const items = [
    { icon: Calendar, label: "学习天数", value: `${summary.total_sessions} 次`, color: "text-blue-600" },
    { icon: Clock, label: "累计时长", value: `${summary.total_duration_minutes}min`, color: "text-green-600" },
    { icon: TrendingUp, label: "技能提升", value: `${summary.total_skill_gains} 项`, color: "text-purple-600" },
    { icon: Zap, label: "连续学习", value: `${summary.streak_days} 天`, color: "text-orange-600" },
  ];

  return (
    <div className="p-4 border-b border-border bg-gradient-to-r from-brand/5 to-purple-500/5">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 size={18} className="text-brand" />
        <h2 className="text-lg font-bold text-ink-primary">成长概览</h2>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.label}
              className="flex items-center gap-3 p-3 bg-white rounded-xl"
            >
              <Icon size={20} className={item.color} />
              <div>
                <p className="text-xs text-ink-muted">{item.label}</p>
                <p className="text-base font-bold text-ink-primary">
                  {item.value}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── 成长记录卡片 ──

function GrowthCard({
  record,
  expanded,
  onToggle,
}: {
  record: GrowthRecord;
  expanded: boolean;
  onToggle: () => void;
}) {
  const date = new Date(record.session_started_at * 1000);
  const dateStr = `${date.getMonth() + 1}月${date.getDate()}日`;
  const timeStr = `${date.getHours()}:${String(date.getMinutes()).padStart(2, "0")}`;

  return (
    <div
      className="bg-bg-secondary rounded-xl p-4 cursor-pointer hover:bg-bg-tertiary transition-colors"
      onClick={onToggle}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <BookOpen size={14} className="text-brand shrink-0" />
            <h3 className="text-sm font-semibold text-ink-primary truncate">
              {record.session_title || "学习 Session"}
            </h3>
          </div>
          <div className="flex items-center gap-3 text-xs text-ink-muted">
            <span className="flex items-center gap-1">
              <Calendar size={11} />
              {dateStr} {timeStr}
            </span>
            <span className="flex items-center gap-1">
              <Clock size={11} />
              {record.duration_minutes}min
            </span>
            {record.skill_gains.length > 0 && (
              <span className="flex items-center gap-1 text-green-600">
                <TrendingUp size={11} />
                +{record.total_gain.toFixed(2)}
              </span>
            )}
          </div>
        </div>
        <ChevronRight
          size={16}
          className={`text-ink-muted shrink-0 transition-transform ${
            expanded ? "rotate-90" : ""
          }`}
        />
      </div>

      {/* 展开详情 */}
      {expanded && (
        <div className="mt-3 pt-3 border-t border-border space-y-3">
          {/* 技能增益 */}
          {record.skill_gains.length > 0 && (
            <div>
              <p className="text-xs font-medium text-ink-muted mb-2">技能提升</p>
              <div className="space-y-2">
                {record.skill_gains.map((g, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-xs font-medium text-ink-primary w-20 truncate">
                      {g.skill}
                    </span>
                    <div className="flex-1 h-2 bg-bg-tertiary rounded-full overflow-hidden">
                      <div
                        className="h-full bg-green-500 rounded-full transition-all"
                        style={{ width: `${Math.min(g.after * 100, 100)}%` }}
                      />
                    </div>
                    <span className="text-xs text-ink-muted w-16 text-right">
                      {Math.round(g.before * 100)}% → {Math.round(g.after * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 反思 */}
          {record.key_takeaways.length > 0 && (
            <div>
              <p className="text-xs font-medium text-ink-muted mb-1">收获</p>
              <ul className="space-y-1">
                {record.key_takeaways.map((t, i) => (
                  <li key={i} className="text-xs text-ink-secondary pl-3 border-l-2 border-brand/30">
                    {t}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {record.reflection_snippet && !record.key_takeaways.length && (
            <div>
              <p className="text-xs font-medium text-ink-muted mb-1">反思</p>
              <p className="text-xs text-ink-secondary leading-relaxed">
                {record.reflection_snippet}
              </p>
            </div>
          )}

          {/* 苹果果寄语 */}
          <p className="text-xs text-brand italic">
            &ldquo;我比今天开始的时候更了解你了。&rdquo;
          </p>
        </div>
      )}
    </div>
  );
}

// ── 骨架屏 ──

function GrowthSkeleton() {
  return (
    <div className="flex flex-col min-h-screen bg-bg-primary">
      <div className="p-4 border-b border-border">
        <Skeleton className="h-6 w-32 mb-3" />
        <div className="grid grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-16 rounded-xl" />
          ))}
        </div>
      </div>
      <div className="px-4 py-4 space-y-3">
        <Skeleton className="h-4 w-24" />
        {[1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-20 rounded-xl" />
        ))}
      </div>
    </div>
  );
}

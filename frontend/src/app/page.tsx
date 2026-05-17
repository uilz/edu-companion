"use client";

import { useMemo } from "react";
import Link from "next/link";
import { BookOpen, Brain, Target, TrendingUp, MessageCircle, PenTool, Video } from "lucide-react";
import Card from "@/components/ui/Card";

interface StudyTask {
  id: number;
  subject: string;
  task: string;
  done: boolean;
}

const todayTasks: StudyTask[] = [
  { id: 1, subject: "高等数学", task: "复习极限与连续（第三章）", done: true },
  { id: 2, subject: "线性代数", task: "完成矩阵运算练习题 15 道", done: false },
  { id: 3, subject: "大学物理", task: "观看电磁学专题视频", done: false },
  { id: 4, subject: "英语", task: "背诵学术词汇 Unit 8", done: false },
];

const weeklyData = [
  { day: "一", hours: 3.2 },
  { day: "二", hours: 2.5 },
  { day: "三", hours: 4.1 },
  { day: "四", hours: 1.8 },
  { day: "五", hours: 3.6 },
  { day: "六", hours: 5.0 },
  { day: "日", hours: 2.8 },
];

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

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-5xl mx-auto px-6 py-16">
        {/* Header */}
        <header className="mb-16">
          <h1 className="text-5xl font-bold tracking-tight text-[var(--color-text)] mb-3">
            {greeting}
          </h1>
          <p className="text-lg text-[var(--color-text-muted)]">
            今天是学习的第 <span className="text-[var(--color-text)] font-semibold">{streak}</span> 天
          </p>
        </header>

        {/* Quick Actions */}
        <div className="grid grid-cols-3 gap-4 mb-12">
          <Link
            href="/chat"
            className="border border-[var(--color-border)] bg-[var(--color-card)] p-6 hover:border-[var(--color-border-hover)] transition-colors group min-h-[120px]"
          >
            <div className="text-2xl mb-3">💬</div>
            <div className="text-sm font-semibold text-[var(--color-text)] group-hover:text-[var(--color-accent)] transition-colors">
              提问
            </div>
            <div className="text-xs text-[var(--color-text-muted)] mt-1">向 AI 助手提问</div>
          </Link>
          <Link
            href="/practice"
            className="border border-[var(--color-border)] bg-[var(--color-card)] p-6 hover:border-[var(--color-border-hover)] transition-colors group min-h-[120px]"
          >
            <div className="text-2xl mb-3">📝</div>
            <div className="text-sm font-semibold text-[var(--color-text)] group-hover:text-[var(--color-accent)] transition-colors">
              练习
            </div>
            <div className="text-xs text-[var(--color-text-muted)] mt-1">做题巩固知识</div>
          </Link>
          <Link
            href="/graph"
            className="border border-[var(--color-border)] bg-[var(--color-card)] p-6 hover:border-[var(--color-border-hover)] transition-colors group min-h-[120px]"
          >
            <div className="text-2xl mb-3">🎬</div>
            <div className="text-sm font-semibold text-[var(--color-text)] group-hover:text-[var(--color-accent)] transition-colors">
              知识图谱
            </div>
            <div className="text-xs text-[var(--color-text-muted)] mt-1">查看知识关联</div>
          </Link>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Today's Plan */}
          <div className="lg:col-span-2">
            <Card title="今日学习计划">
              <div className="space-y-0 divide-y divide-[var(--color-surface)]">
                {todayTasks.map((task) => (
                  <label
                    key={task.id}
                    className="flex items-start gap-3 py-3 cursor-pointer group"
                  >
                    <input
                      type="checkbox"
                      defaultChecked={task.done}
                      className="mt-0.5 accent-[var(--color-accent)] w-4 h-4"
                    />
                    <div className="flex-1">
                      <div
                        className={`text-sm ${
                          task.done
                            ? "text-[var(--color-text-muted)] line-through"
                            : "text-[var(--color-text)]"
                        }`}
                      >
                        {task.task}
                      </div>
                      <div className="text-xs text-[var(--color-text-muted)] mt-0.5">
                        {task.subject}
                      </div>
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
                  {totalHours.toFixed(1)}
                  <span className="text-sm font-normal text-[var(--color-text-muted)] ml-1">小时</span>
                </div>
                <div className="text-xs text-[var(--color-text-muted)] mt-1">
                  连续学习 <span className="text-[var(--color-accent)] font-semibold">{streak}</span> 天
                </div>
              </div>

              {/* Streak bar */}
              <div className="flex gap-1 mb-6">
                {Array.from({ length: 30 }).map((_, i) => (
                  <div
                    key={i}
                    className={`h-1.5 flex-1 ${
                      i < 12 ? "bg-[var(--color-accent)]" : "bg-[var(--color-surface)]"
                    }`}
                  />
                ))}
              </div>

              {/* Daily bar chart */}
              <div className="space-y-2">
                {weeklyData.map((d) => (
                  <div key={d.day} className="flex items-center gap-2">
                    <span className="text-xs text-[var(--color-text-muted)] w-4">{d.day}</span>
                    <div className="flex-1 bg-[var(--color-surface)] h-2">
                      <div
                        className="h-full bg-[var(--color-text)]"
                        style={{ width: `${(d.hours / maxHours) * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-[var(--color-text-muted)] w-8 text-right">
                      {d.hours}h
                    </span>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mt-8">
          {[
            { icon: <BookOpen size={18} />, label: "今日学习", value: "2.4 小时" },
            { icon: <Target size={18} />, label: "完成题目", value: "38 道" },
            { icon: <Brain size={18} />, label: "掌握知识点", value: "156 个" },
            { icon: <TrendingUp size={18} />, label: "正确率", value: "87.3%" },
          ].map((stat) => (
            <div
              key={stat.label}
              className="border border-[var(--color-border)] bg-[var(--color-card)] p-5"
            >
              <div className="text-[var(--color-text-muted)] mb-2">{stat.icon}</div>
              <div className="text-2xl font-bold text-[var(--color-text)]">{stat.value}</div>
              <div className="text-xs text-[var(--color-text-muted)] mt-1">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>
    </main>
  );
}

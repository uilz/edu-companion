"use client";

import Card from "@/components/ui/Card";

const subjects = [
  { name: "高等数学", mastery: 82, total: 45, correct: 37 },
  { name: "线性代数", mastery: 68, total: 30, correct: 20 },
  { name: "大学物理", mastery: 74, total: 38, correct: 28 },
  { name: "概率论", mastery: 56, total: 25, correct: 14 },
  { name: "英语", mastery: 90, total: 60, correct: 54 },
  { name: "数据结构", mastery: 61, total: 32, correct: 19 },
];

const weeklyTrend = [
  { day: "5/12", hours: 2.1, questions: 28 },
  { day: "5/13", hours: 3.4, questions: 42 },
  { day: "5/14", hours: 1.8, questions: 22 },
  { day: "5/15", hours: 4.2, questions: 55 },
  { day: "5/16", hours: 2.9, questions: 36 },
  { day: "5/17", hours: 3.6, questions: 48 },
  { day: "5/18", hours: 2.4, questions: 31 },
  { day: "5/19", hours: 1.5, questions: 18 },
  { day: "5/20", hours: 3.8, questions: 50 },
  { day: "5/21", hours: 2.7, questions: 35 },
  { day: "5/22", hours: 4.5, questions: 58 },
  { day: "5/23", hours: 3.1, questions: 40 },
  { day: "5/24", hours: 2.0, questions: 26 },
  { day: "5/25", hours: 3.3, questions: 43 },
];

// Streak: last 30 days, 1 = studied, 0 = rest
const streakData = [
  1, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1, 0, 1, 1, 1, 1, 1, 1, 0, 1, 1, 1,
];

const errorCategories = [
  { label: "计算错误", value: 34, color: "#0066FF" },
  { label: "概念混淆", value: 28, color: "#737373" },
  { label: "审题不清", value: 22, color: "#404040" },
  { label: "其他", value: 16, color: "#262626" },
];

export default function ProgressPage() {
  const totalQuestions = subjects.reduce((s, sub) => s + sub.total, 0);
  const totalCorrect = subjects.reduce((s, sub) => s + sub.correct, 0);
  const maxHours = Math.max(...weeklyTrend.map((d) => d.hours));

  // Build pie chart segments using conic gradient
  const totalPct = errorCategories.reduce((s, c) => s + c.value, 0);
  let cumPct = 0;
  const gradientStops = errorCategories.map((c) => {
    const start = cumPct;
    cumPct += (c.value / totalPct) * 100;
    return `${c.color} ${start}% ${cumPct}%`;
  });
  const pieGradient = `conic-gradient(${gradientStops.join(", ")})`;

  return (
    <main className="min-h-screen bg-[#0a0a0a]">
      <div className="max-w-5xl mx-auto px-6 py-16">
        <h1 className="text-4xl font-bold tracking-tight text-white mb-12">
          学情
        </h1>

        {/* Summary stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-12">
          {[
            { label: "总做题数", value: totalQuestions.toString() },
            { label: "正确率", value: `${((totalCorrect / totalQuestions) * 100).toFixed(1)}%` },
            { label: "连续学习", value: "12 天" },
            { label: "知识点掌握", value: "156 个" },
          ].map((s) => (
            <div key={s.label} className="border border-[#262626] bg-[#0d0d0d] p-5">
              <div className="text-2xl font-bold text-white">{s.value}</div>
              <div className="text-xs text-[#737373] mt-1">{s.label}</div>
            </div>
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Knowledge mastery */}
          <Card title="知识掌握度">
            <div className="space-y-4">
              {subjects.map((sub) => (
                <div key={sub.name}>
                  <div className="flex items-center justify-between text-sm mb-1.5">
                    <span className="text-[#e5e5e5]">{sub.name}</span>
                    <span className="text-[#737373]">{sub.mastery}%</span>
                  </div>
                  <div className="w-full bg-[#1a1a1a] h-2">
                    <div
                      className="h-full transition-all"
                      style={{
                        width: `${sub.mastery}%`,
                        backgroundColor:
                          sub.mastery >= 80
                            ? "#22c55e"
                            : sub.mastery >= 60
                            ? "#0066FF"
                            : "#f59e0b",
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Study trend */}
          <Card title="学习趋势">
            <div className="flex items-end gap-1 h-40">
              {weeklyTrend.map((d) => (
                <div key={d.day} className="flex-1 flex flex-col items-center gap-1">
                  <div
                    className="w-full bg-[#0066FF]/80 hover:bg-[#0066FF] transition-colors cursor-pointer group relative"
                    style={{ height: `${(d.hours / maxHours) * 100}%` }}
                  >
                    <div className="absolute -top-6 left-1/2 -translate-x-1/2 text-[10px] text-[#737373] opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
                      {d.hours}h / {d.questions}题
                    </div>
                  </div>
                  <span className="text-[9px] text-[#525252]">{d.day.slice(-2)}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Streak calendar */}
          <Card title="学习日历（近30天）">
            <div className="grid grid-cols-10 gap-1.5">
              {streakData.map((active, i) => (
                <div
                  key={i}
                  className={`aspect-square flex items-center justify-center text-[10px] ${
                    active
                      ? "bg-[#0066FF]"
                      : "bg-[#1a1a1a]"
                  }`}
                  title={active ? "已学习" : "未学习"}
                />
              ))}
            </div>
            <div className="flex items-center gap-4 mt-4 text-xs text-[#737373]">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 bg-[#0066FF]" />
                已学习
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-3 bg-[#1a1a1a]" />
                未学习
              </div>
            </div>
          </Card>

          {/* Error analysis */}
          <Card title="错题分析">
            <div className="flex items-center gap-8">
              <div
                className="w-32 h-32 rounded-full flex-shrink-0"
                style={{ background: pieGradient }}
              />
              <div className="space-y-3">
                {errorCategories.map((cat) => (
                  <div key={cat.label} className="flex items-center gap-3">
                    <div
                      className="w-3 h-3 flex-shrink-0"
                      style={{ backgroundColor: cat.color }}
                    />
                    <span className="text-sm text-[#a3a3a3]">{cat.label}</span>
                    <span className="text-sm text-white font-medium ml-auto">
                      {cat.value}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </div>
      </div>
    </main>
  );
}

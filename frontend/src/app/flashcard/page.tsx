"use client";

import Link from "next/link";
import { Layers, Brain, Calendar, TrendingUp, Sparkles, BarChart3, Construction } from "lucide-react";

const PREVIEW_FEATURES = [
  { icon: Layers, title: "卡片管理", desc: "正反面 / 挖空 / 多选 / 笔记" },
  { icon: Brain, title: "FSRS 调度", desc: "基于 FSRS 算法的间隔重复" },
  { icon: Calendar, title: "今日复习", desc: "每日复习列表 + 优先级排序" },
  { icon: TrendingUp, title: "掌握度追踪", desc: "stability/difficulty/retention 可视化" },
  { icon: Sparkles, title: "AI 出题", desc: "对话中自动生成闪卡" },
  { icon: BarChart3, title: "学习统计", desc: "复习曲线 + 保留率分析" },
];

export default function FlashcardPage() {
  return (
    <div className="min-h-screen px-6 py-12 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-3 rounded-xl bg-gradient-to-br from-violet-500/20 to-blue-500/20 border border-violet-500/30">
          <Layers className="w-7 h-7 text-violet-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">闪卡</h1>
          <p className="text-sm text-[var(--color-text-muted)]">FSRS 间隔重复 · 跨模块笔记 · AI 出题</p>
        </div>
      </div>

      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-5 mb-8 flex gap-3">
        <Construction className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
        <div>
          <p className="font-medium text-amber-700 dark:text-amber-300">页面正在重建中</p>
          <p className="text-sm text-amber-600/80 dark:text-amber-400/80 mt-1">
            路由可达，但功能未就绪。后端 services（fsrs_scheduler/belief_writer）源文件不在 git 历史中，<br />
            已确认 git / stash 中均无副本。等待按模块任务（Task #88+）重新实现。
          </p>
        </div>
      </div>

      <h2 className="text-lg font-semibold mb-4">即将到来的功能</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {PREVIEW_FEATURES.map((f) => (
          <div
            key={f.title}
            className="rounded-xl border border-[var(--color-border)]/50 bg-[var(--color-surface)]/50 p-4"
          >
            <div className="flex items-center gap-3 mb-2">
              <f.icon className="w-5 h-5 text-violet-500" />
              <span className="font-medium">{f.title}</span>
            </div>
            <p className="text-sm text-[var(--color-text-muted)]">{f.desc}</p>
          </div>
        ))}
      </div>

      <div className="mt-8 flex gap-3 text-sm">
        <Link
          href="/practice"
          className="px-4 py-2 rounded-lg bg-[var(--color-primary)] text-white hover:opacity-90"
        >
          前往练习
        </Link>
        <Link
          href="/reading"
          className="px-4 py-2 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface)]"
        >
          前往阅读
        </Link>
      </div>
    </div>
  );
}

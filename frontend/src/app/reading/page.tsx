"use client";

import Link from "next/link";
import { BookOpen, Bookmark, Brain, Clock, FileText, Highlighter, Construction } from "lucide-react";

const PREVIEW_FEATURES = [
  { icon: FileText, title: "PDF/文档导入", desc: "支持 PDF、EPUB、Markdown" },
  { icon: Highlighter, title: "标注系统", desc: "划线 + 笔记 + 闪卡关联" },
  { icon: Bookmark, title: "笔记复用", desc: "笔记自动转 FlashCard 复习" },
  { icon: Clock, title: "回顾提醒", desc: "间隔重复 + 知识图谱联动" },
  { icon: Brain, title: "多维知识状态", desc: "concept/procedure/application/transfer" },
  { icon: BookOpen, title: "阅读会话", desc: "精读/略读/回顾三种模式" },
];

export default function ReadingPage() {
  return (
    <div className="min-h-screen px-6 py-12 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-3 rounded-xl bg-gradient-to-br from-emerald-500/20 to-teal-500/20 border border-emerald-500/30">
          <BookOpen className="w-7 h-7 text-emerald-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">阅读</h1>
          <p className="text-sm text-[var(--color-text-muted)]">文档阅读 · 标注 · 笔记 · 回顾提醒</p>
        </div>
      </div>

      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-5 mb-8 flex gap-3">
        <Construction className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
        <div>
          <p className="font-medium text-amber-700 dark:text-amber-300">页面正在重建中</p>
          <p className="text-sm text-amber-600/80 dark:text-amber-400/80 mt-1">
            路由可达，但功能未就绪。后端 services (sessions/annotations/notes/review_reminder) 正在从 .pyc 缓存反编译恢复，
            <br />后续会按模块任务（Task #88+）逐步推出。
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
              <f.icon className="w-5 h-5 text-emerald-500" />
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
          href="/flashcard"
          className="px-4 py-2 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface)]"
        >
          前往闪卡
        </Link>
      </div>
    </div>
  );
}

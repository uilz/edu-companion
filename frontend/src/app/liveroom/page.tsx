"use client";

import Link from "next/link";
import { Brain, BookOpen, Sparkles, Mic, Languages, Construction } from "lucide-react";

const PREVIEW_FEATURES = [
  { icon: Mic, title: "实时语音", desc: "低延迟多人语音通话" },
  { icon: Languages, title: "AI 角色", desc: "情景对话 + 角色扮演" },
  { icon: BookOpen, title: "转写笔记", desc: "实时语音转写 + 关键句高亮" },
  { icon: Sparkles, title: "个性化推荐", desc: "基于学习空间的场景推荐" },
];

export default function LiveroomPage() {
  return (
    <div className="min-h-screen px-6 py-12 max-w-4xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-3 rounded-xl bg-gradient-to-br from-pink-500/20 to-violet-500/20 border border-pink-500/30">
          <Mic className="w-7 h-7 text-pink-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">语言房间</h1>
          <p className="text-sm text-[var(--color-text-muted)]">实时语音 · AI 角色 · 情景对话</p>
        </div>
      </div>

      <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-5 mb-8 flex gap-3">
        <Construction className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
        <div>
          <p className="font-medium text-amber-700 dark:text-amber-300">页面正在重建中</p>
          <p className="text-sm text-amber-600/80 dark:text-amber-400/80 mt-1">
            路由可达，但功能未就绪。后端 services（LiveKit 集成 / 实时转写 / AI 角色）源文件不在 git 历史中，<br />
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
              <f.icon className="w-5 h-5 text-pink-500" />
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
          href="/conversation"
          className="px-4 py-2 rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-surface)]"
        >
          前往对话
        </Link>
      </div>
    </div>
  );
}

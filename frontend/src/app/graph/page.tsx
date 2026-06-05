// 知识图谱可视化 — 独立页面
// 力导向布局 + 节点颜色按掌握度 + 交互展开

"use client";

import dynamic from "next/dynamic";
import { Loader2 } from "lucide-react";

const GraphTab = dynamic(
  () => import("@/components/dashboard/tabs/GraphTab").then((m) => m.GraphTab),
  {
    loading: () => (
      <div className="flex items-center justify-center min-h-screen">
        <Loader2 className="animate-spin text-[var(--color-accent)]" size={32} />
      </div>
    ),
  }
);

export default function GraphPage() {
  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-[1400px] mx-auto px-4 py-6">
        <GraphTab />
      </div>
    </main>
  );
}

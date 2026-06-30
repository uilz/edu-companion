// 知识树独立页面 — Phase 11 重构
// 独立路由，脱离 /resources tab 嵌套

import KnowledgeTreePage from "@/components/knowledge-tree/KnowledgeTreePage";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "知识树 · 伴学",
  description: "可视化知识结构，AI 对话探索学习路径",
};

export default function KnowledgeTreeRoute() {
  return (
    <main className="route-fullscreen absolute inset-0 overflow-hidden bg-[var(--color-bg)]">
      <ErrorBoundary>
        <KnowledgeTreePage />
      </ErrorBoundary>
    </main>
  );
}

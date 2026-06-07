// 知识图谱可视化 — 独立页面
// 使用统一知识树组件，支持思维导图/力导向/DAG三种模式

import GraphDialoguePage from "@/components/graph/pages/GraphDialoguePage";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "知识图谱 · 知识树",
};

export default function GraphPage() {
  return (
    <main className="h-[calc(100vh-3.5rem)]">
      <ErrorBoundary>
        <GraphDialoguePage />
      </ErrorBoundary>
    </main>
  );
}

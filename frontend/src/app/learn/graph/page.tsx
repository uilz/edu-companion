import GraphDialoguePage from "@/components/graph/GraphDialoguePage";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "认知可视化 · 图谱对话",
};

export default function LearnGraphPage() {
  return (
    <main className="h-[calc(100vh-3.5rem)]">
      <GraphDialoguePage />
    </main>
  );
}

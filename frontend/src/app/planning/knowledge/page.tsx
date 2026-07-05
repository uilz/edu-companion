"use client";

import { useState, useMemo } from "react";
import { Network, Loader2, Search } from "lucide-react";
import { useKnowledgeView, PlanItem } from "@/hooks/planning/usePlanning";
import Card from "@/components/ui/Card";

const LEVEL_COLORS: Record<string, string> = {
  atom: "bg-blue-100 text-blue-700",
  topic: "bg-emerald-100 text-emerald-700",
  partition: "bg-purple-100 text-purple-700",
};

const SOURCE_LABELS: Record<string, string> = {
  flashcard: "卡片",
  practice: "练习",
  project: "项目",
  reading: "阅读",
  language_room: "语言房",
  manual: "手动",
};

export default function KnowledgePage() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [keyword, setKeyword] = useState("");
  const { data, loading, reload } = useKnowledgeView(selectedNodeId ?? undefined);

  const filteredNodes = useMemo(() => {
    if (!data) return [];
    const kw = keyword.trim().toLowerCase();
    if (!kw) return data.nodes;
    return data.nodes.filter((n) => n.label.toLowerCase().includes(kw));
  }, [data, keyword]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-[var(--color-text)] tracking-tight flex items-center gap-2">
              <Network size={20} /> 知识视图
            </h1>
            <p className="text-sm text-[var(--color-text-muted)] mt-1">
              知识点维度 · 待办密度
            </p>
          </div>
          <div className="flex items-center gap-2 border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1.5">
            <Search size={14} className="text-[var(--color-text-muted)]" />
            <input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索知识点…"
              className="bg-transparent text-sm outline-none w-48"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* 节点列表 */}
          <Card title={`知识点 (${filteredNodes.length})`}>
            {filteredNodes.length === 0 ? (
              <div className="text-sm text-[var(--color-text-muted)] py-4 text-center">
                暂无数据
              </div>
            ) : (
              <div className="max-h-[600px] overflow-y-auto space-y-1">
                {filteredNodes.map((n) => {
                  const isSel = n.id === selectedNodeId;
                  const colorClass = LEVEL_COLORS[n.level] || "bg-zinc-100 text-zinc-700";
                  return (
                    <button
                      key={n.id}
                      onClick={() => {
                        setSelectedNodeId(n.id);
                        reload(n.id);
                      }}
                      className={`w-full text-left p-2 border ${
                        isSel
                          ? "border-[var(--color-accent)] bg-[var(--color-card)]"
                          : "border-transparent hover:bg-[var(--color-card)]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className={`text-xs px-1.5 py-0.5 ${colorClass}`}>
                            {n.level}
                          </span>
                          <span className="text-sm font-medium truncate">{n.label}</span>
                        </div>
                        <span
                          className={`text-xs px-1.5 py-0.5 ${
                            n.todo_count > 0
                              ? "bg-amber-100 text-amber-700"
                              : "bg-zinc-100 text-zinc-500"
                          }`}
                        >
                          {n.todo_count} 待办
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </Card>

          {/* 选中节点的待办 */}
          <Card title={selectedNodeId ? "节点待办" : "选择知识点"}>
            {!selectedNodeId ? (
              <div className="text-sm text-[var(--color-text-muted)] py-8 text-center">
                从左侧选择一个知识点查看其下待办
              </div>
            ) : data?.selected_node_todos.length === 0 ? (
              <div className="text-sm text-[var(--color-text-muted)] py-8 text-center">
                该知识点下暂无待办
              </div>
            ) : (
              <div className="space-y-2 max-h-[600px] overflow-y-auto">
                {(data?.selected_node_todos || []).map((it: PlanItem) => (
                  <div
                    key={it.id}
                    className="p-3 border border-[var(--color-border)]"
                  >
                    <div className="flex items-center justify-between mb-1 gap-2 flex-wrap">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs px-1.5 py-0.5 bg-[var(--color-card)] border border-[var(--color-border)]">
                          {SOURCE_LABELS[it.source_module] || it.source_module}
                        </span>
                        <span className="text-xs text-[var(--color-text-muted)]">
                          {it.status}
                        </span>
                      </div>
                      <span className="text-xs text-[var(--color-text-muted)]">
                        {it.estimated_minutes} min
                      </span>
                    </div>
                    <div className="text-sm font-medium text-[var(--color-text)]">
                      {it.title}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}

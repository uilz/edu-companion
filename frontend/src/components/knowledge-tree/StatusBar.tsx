"use client";

import { getMasteryColor } from "@/lib/types/graph-types";

export interface StatsInfo {
  total: number;
  mastered: number;
  learning: number;
  untouched: number;
  avgMastery: number;
}

export default function StatusBar({
  stats, onStatClick, activeFilter,
}: {
  stats: StatsInfo;
  onStatClick: (filter: string) => void;
  activeFilter?: string;
}) {
  if (stats.total === 0) return null;

  const filterBtn = (filter: string, label: string, count: number, icon: string) => {
    const isActive = activeFilter === filter;
    return (
      <button
        onClick={() => onStatClick(filter)}
        className={`flex items-center gap-1 px-2 py-1 rounded-md transition-colors cursor-pointer
          ${isActive ? "bg-accent/10 text-accent font-medium" : "hover:bg-surface-hover"}`}
        title={`筛选: ${label}`}
      >
        <span className="text-[10px]">{icon}</span>
        <span className="text-[10px]">{label}</span>
        <strong className="text-[11px]">{count}</strong>
      </button>
    );
  };

  return (
    <div className="flex items-center gap-1 h-[32px] px-4 bg-page-secondary border-t border flex-shrink-0 text-[10px] text-muted overflow-hidden">
      <span className="mr-2 text-[10px] shrink-0">📊 <strong className="text">{stats.total}</strong> 节点</span>
      <div className="w-px h-4 bg-divider shrink-0" />
      {filterBtn("mastered", "已掌握", stats.mastered, "✅")}
      {filterBtn("learning", "学习中", stats.learning, "📖")}
      {filterBtn("untouched", "未接触", stats.untouched, "📐")}
      <div className="w-px h-4 bg-divider shrink-0" />
      <span className="text-[10px] shrink-0 hidden sm:inline">平均掌握度 <strong style={{ color: getMasteryColor(stats.avgMastery) }}>{Math.round(stats.avgMastery * 100)}%</strong></span>
      <span className="ml-auto text-[10px] shrink-0 hidden lg:inline">
        快捷键: <kbd className="inline-block px-1 py-0.5 bg-surface-hover border border rounded text-[9px] font-mono">↑↓←→</kbd> 切换
        · <kbd className="inline-block px-1 py-0.5 bg-surface-hover border border rounded text-[9px] font-mono">F2</kbd> 编辑
        · <kbd className="inline-block px-1 py-0.5 bg-surface-hover border border rounded text-[9px] font-mono">Del</kbd> 删除
        · <kbd className="inline-block px-1 py-0.5 bg-surface-hover border border rounded text-[9px] font-mono">Ctrl+N</kbd> 添加
      </span>
    </div>
  );
}

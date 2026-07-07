"use client";

import type { GraphMode } from "./KnowledgeTreePage";
import type { GraphNode } from "@/lib/types/graph-types";

export default function TopBar({
  partitionId, partitionList, onPartitionChange,
  graphMode, onGraphModeChange,
  showDialogPanel, onToggleDialogPanel,
  showDetailPanel, onToggleDetailPanel,
  graphSearch, onGraphSearchChange, matchCount,
  onAddNode, onToggleFullscreen, graphFullscreen,
  layerOpen, onToggleLayer,
  // ── 面包屑（统一数据源） ──
  breadcrumbs,
  focusRootId, onClearFocus, onSetFocus,
  rootLabel,
}: {
  partitionId: string; partitionList: { id: string; name: string; emoji?: string }[];
  onPartitionChange: (id: string) => void;
  graphMode: GraphMode; onGraphModeChange: (m: GraphMode) => void;
  showDialogPanel: boolean; onToggleDialogPanel: () => void;
  showDetailPanel: boolean; onToggleDetailPanel: () => void;
  graphSearch: string; onGraphSearchChange: (s: string) => void; matchCount: number;
  onAddNode: () => void; onToggleFullscreen: () => void; graphFullscreen: boolean;
  layerOpen: boolean; onToggleLayer: () => void;
  // 面包屑
  breadcrumbs: GraphNode[];
  focusRootId?: string;
  onClearFocus: () => void;
  onSetFocus: (id: string) => void;
  rootLabel?: string;
}) {
  return (
    <div className="flex flex-col flex-shrink-0 z-20 border-b border bg-surface">
      {/* ══ 第一行: 工具栏 ══ */}
      <div className="flex items-center gap-3 h-[48px] px-4">
        {/* 节点显示器：显示当前深入的节点名称 */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-page-secondary border border rounded-lg text-xs font-medium select-none">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-muted">
            <circle cx="12" cy="12" r="3"/>
          </svg>
          <span className="text text-xs font-medium">
            {focusRootId
              ? (partitionList.find(p => p.id === focusRootId)?.emoji || "📚") + " " + (partitionList.find(p => p.id === focusRootId)?.name || focusRootId)
              : "全部节点"}
          </span>
        </div>

        <div className="w-px h-5 bg-divider flex-shrink-0" />

        {/* 视图模式切换 */}
        <button onClick={() => {
            const modes: GraphMode[] = ["mindmap", "force", "dag"];
            const next = modes[(modes.indexOf(graphMode) + 1) % modes.length];
            onGraphModeChange(next);
          }}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium bg-page-secondary border border text hover:border-accent transition-all">
          {graphMode === "mindmap" && (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/>
            </svg>
          )}
          {graphMode === "force" && (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3"/><circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="18" cy="18" r="2"/><circle cx="6" cy="18" r="2"/>
            </svg>
          )}
          {graphMode === "dag" && (
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="4" y="4" width="16" height="4" rx="1"/><rect x="2" y="12" width="20" height="4" rx="1"/><rect x="6" y="20" width="12" height="3" rx="1"/>
            </svg>
          )}
          {graphMode === "mindmap" ? "思维导图" : graphMode === "force" ? "力导向" : "依赖图"}
        </button>

        <div className="w-px h-5 bg-divider flex-shrink-0" />

        {/* 面板开关 */}
        <button onClick={onToggleDialogPanel}
          className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-all ${
            showDialogPanel ? "bg-accent text-white shadow-sm" : "text-muted hover:text hover:bg-surface-hover"
          }`}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/></svg>
          对话面板
        </button>
        <button onClick={onToggleDetailPanel}
          className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-all ${
            showDetailPanel ? "bg-accent text-white shadow-sm" : "text-muted hover:text hover:bg-surface-hover"
          }`}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="20" height="18" rx="1"/><path d="M2 8h20"/></svg>
          详情面板
        </button>

        {/* 图层面板开关 */}
        <button onClick={onToggleLayer}
          className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-all ${
            layerOpen ? "bg-accent/10 text-accent" : "text-muted hover:text"
          }`}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
          层级
        </button>

        {/* 搜索框 */}
        <div className="relative flex-1 max-w-[200px]">
          <input value={graphSearch} onChange={e => onGraphSearchChange(e.target.value)}
            placeholder="搜索节点…"
            className="w-full pl-7 pr-2 py-1.5 text-[11px] rounded-md border border bg-page-secondary text placeholder:text-muted focus:outline-none focus:border-accent focus:bg-surface transition-colors" />
          <svg className="absolute left-2 top-1/2 -translate-y-1/2 text-muted" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
          </svg>
          {matchCount > 0 && (
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[9px] text-accent font-medium bg-accent/10 px-1.5 py-0.5 rounded-full">
              {matchCount}
            </span>
          )}
        </div>

        <div className="w-px h-5 bg-divider flex-shrink-0" />

        {/* 添加节点 */}
        <button onClick={onAddNode}
          className="flex items-center gap-1 px-2 py-1 rounded text-[11px] text-muted hover:text hover:bg-surface-hover transition-colors">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14"/></svg>
          添加
        </button>

        {/* 全屏 */}
        <button onClick={onToggleFullscreen}
          className="p-1.5 rounded-md text-muted hover:text hover:bg-surface-hover transition-colors"
          title={graphFullscreen ? "退出全屏" : "全屏"}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>
        </button>
      </div>

      {/* ══ 第二行: 面包屑导航（聚焦时显示） ══ */}
      {focusRootId && breadcrumbs.length > 0 && (
        <div className="flex items-center gap-1.5 px-4 py-1.5 border-t border/50 bg-page-secondary text-[11px] text-muted">
          <button onClick={onClearFocus}
            className="text-accent hover:underline font-medium">
            全局视图
          </button>
          {breadcrumbs.map((ancestor) => (
            <span key={ancestor.id} className="flex items-center gap-1">
              <span className="text-muted mx-0.5">›</span>
              <button
                onClick={() => onSetFocus(ancestor.id)}
                className="hover:text-accent hover:underline transition-colors"
              >
                {ancestor.emoji && <span className="mr-0.5">{ancestor.emoji}</span>}
                {ancestor.label}
              </button>
            </span>
          ))}
          <span className="text-muted mx-0.5">›</span>
          <span className="text font-medium">
            {rootLabel}
          </span>
        </div>
      )}
    </div>
  );
}
"use client";

import type { GraphMode } from "./KnowledgeTreePage";

export default function TopBar({
  partitionId, partitionList, onPartitionChange,
  graphMode, onGraphModeChange,
  showDialogPanel, onToggleDialogPanel,
  showDetailPanel, onToggleDetailPanel,
  graphSearch, onGraphSearchChange, matchCount,
  onAddNode, onToggleFullscreen, graphFullscreen,
  layerOpen, onToggleLayer,
}: {
  partitionId: string; partitionList: { id: string; name: string; emoji?: string }[];
  onPartitionChange: (id: string) => void;
  graphMode: GraphMode; onGraphModeChange: (m: GraphMode) => void;
  showDialogPanel: boolean; onToggleDialogPanel: () => void;
  showDetailPanel: boolean; onToggleDetailPanel: () => void;
  graphSearch: string; onGraphSearchChange: (s: string) => void; matchCount: number;
  onAddNode: () => void; onToggleFullscreen: () => void; graphFullscreen: boolean;
  layerOpen: boolean; onToggleLayer: () => void;
}) {
  return (
    <div className="flex items-center gap-3 h-[48px] px-4 bg-[var(--color-surface)] border-b border-[var(--color-border)] flex-shrink-0 z-20">
      {/* 分区选择器 */}
      <div className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--color-page-secondary)] border border-[var(--color-border)] rounded-lg text-xs font-medium cursor-pointer hover:border-[var(--color-accent)] transition-colors">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[var(--color-text-muted)]">
          <circle cx="12" cy="12" r="3"/>
        </svg>
        <select value={partitionId} onChange={e => onPartitionChange(e.target.value)}
          className="appearance-none bg-transparent text-[var(--color-text)] text-xs font-medium focus:outline-none cursor-pointer">
          {partitionList.map(p => (
            <option key={p.id} value={p.id}>{p.emoji || "📚"} {p.name}</option>
          ))}
        </select>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-[var(--color-text-muted)]">
          <path d="M6 9l6 6 6-6"/>
        </svg>
      </div>

      <div className="w-px h-5 bg-[var(--color-border)] flex-shrink-0" />

      {/* 视图模式切换 — 单按钮循环 */}
      <button onClick={() => {
          const modes: GraphMode[] = ["mindmap", "force", "dag"];
          const next = modes[(modes.indexOf(graphMode) + 1) % modes.length];
          onGraphModeChange(next);
        }}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[11px] font-medium bg-[var(--color-page-secondary)] border border-[var(--color-border)] text-[var(--color-text)] hover:border-[var(--color-accent)] transition-all">
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

      <div className="w-px h-5 bg-[var(--color-border)] flex-shrink-0" />

      {/* 面板开关 */}
      <button onClick={onToggleDialogPanel}
        className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-all ${
          showDialogPanel ? "bg-[var(--color-accent)] text-white shadow-sm" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
        }`}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/></svg>
        对话面板
      </button>
      <button onClick={onToggleDetailPanel}
        className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-all ${
          showDetailPanel ? "bg-[var(--color-accent)] text-white shadow-sm" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)]"
        }`}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="2" y="3" width="20" height="18" rx="1"/><path d="M2 8h20"/></svg>
        详情面板
      </button>

      {/* 图层面板开关 */}
      <button onClick={onToggleLayer}
        className={`flex items-center gap-1 px-2 py-1 rounded text-[11px] transition-all ${
          layerOpen ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
        }`}>
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
        层级
      </button>

      {/* 搜索框 */}
      <div className="relative flex-1 max-w-[200px]">
        <input value={graphSearch} onChange={e => onGraphSearchChange(e.target.value)}
          placeholder="搜索节点…"
          className="w-full pl-7 pr-2 py-1.5 text-[11px] rounded-md border border-[var(--color-border)] bg-[var(--color-page-secondary)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] focus:bg-[var(--color-surface)] transition-colors" />
        <svg className="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/>
        </svg>
        {matchCount > 0 && (
          <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[9px] text-[var(--color-accent)] font-medium bg-[var(--color-accent)]/10 px-1.5 py-0.5 rounded-full">
            {matchCount}
          </span>
        )}
      </div>

      <div className="w-px h-5 bg-[var(--color-border)] flex-shrink-0" />

      {/* 添加节点 */}
      <button onClick={onAddNode}
        className="flex items-center gap-1 px-2 py-1 rounded text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14"/></svg>
        添加
      </button>

      {/* 全屏 */}
      <button onClick={onToggleFullscreen}
        className="p-1.5 rounded-md text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface-hover)] transition-colors"
        title={graphFullscreen ? "退出全屏" : "全屏"}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>
      </button>
    </div>
  );
}

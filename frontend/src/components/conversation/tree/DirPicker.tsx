"use client";

import React from "react";
import { Layers, Plus, ChevronDown } from "lucide-react";

interface DirInfo {
  id: string;
  name: string;
  emoji?: string;
  kind?: string;
  domain_count?: number;
}

/**
 * DirItem — 单个目录的可视化行
 *
 * 共享组件：StudySidebar 和 FocusModePanel 的 DirTreeDropdown
 * 都使用它来渲染目录列表项。
 */
export function DirItem({
  dir,
  selected,
  onClick,
}: {
  dir: DirInfo;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2 text-sm flex items-center gap-2 hover:bg-[var(--color-surface)] transition-colors ${
        selected
          ? "text-[var(--color-accent)] font-medium"
          : "text-[var(--color-text)]"
      }`}
    >
      <span>{dir.emoji}</span>
      <span className="truncate flex-1">{dir.name}</span>
      {dir.domain_count != null && (
        <span className="text-[10px] text-[var(--color-text-muted)]">
          {dir.domain_count} 领域
        </span>
      )}
    </button>
  );
}

/**
 * DirPicker — 目录选择器
 *
 * 顶部按钮显示当前选中目录，点击展开下拉列表。
 * 可内嵌在侧栏标题栏或专注模式顶栏使用。
 */
export function DirPicker({
  dirs,
  selectedDirId,
  onSelectDir,
  onCreateDir,
}: {
  dirs: DirInfo[];
  selectedDirId: string | null;
  onSelectDir: (id: string) => void;
  onCreateDir: () => void;
}) {
  const [expanded, setExpanded] = React.useState(false);
  const selected = selectedDirId
    ? dirs.find((d) => d.id === selectedDirId)
    : undefined;

  return (
    <div className="relative">
      <button
        onClick={() => setExpanded((p) => !p)}
        className="flex items-center gap-1.5 text-xs text-[var(--color-text-secondary)] hover:text-[var(--color-text)] transition-colors px-2 py-1 rounded hover:bg-[var(--color-surface)]"
      >
        <Layers size={12} />
        {selected ? (
          <>
            <span>{selected.emoji}</span>
            <span className="truncate max-w-[120px]">{selected.name}</span>
          </>
        ) : (
          <span className="truncate max-w-[120px]">选择目录</span>
        )}
        <ChevronDown
          size={12}
          className={`transition-transform ${expanded ? "rotate-180" : ""}`}
        />
      </button>
      {expanded && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setExpanded(false)} />
          <div className="absolute left-0 top-full mt-1 z-20 w-64 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg shadow-xl max-h-64 overflow-y-auto">
            {dirs.length === 0 ? (
              <div className="px-3 py-2 text-xs text-[var(--color-text-muted)]">
                暂无目录
              </div>
            ) : (
              dirs.map((d) => (
                <DirItem
                  key={d.id}
                  dir={d}
                  selected={d.id === selectedDirId}
                  onClick={() => {
                    onSelectDir(d.id);
                    setExpanded(false);
                  }}
                />
              ))
            )}
            <div className="border-t border-[var(--color-border)] px-2 py-1.5">
              <button
                onClick={() => {
                  setExpanded(false);
                  onCreateDir();
                }}
                className="w-full text-left px-2 py-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] rounded flex items-center gap-1.5"
              >
                <Plus size={11} />
                新建目录
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

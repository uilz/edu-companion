"use client";

import { Search } from "lucide-react";
import type { ActionType, NotificationSource } from "@/store/notification/types";
import { SOURCE_OPTIONS, ACTION_TYPE_OPTIONS, ViewMode, TabKey } from "./shared";

// ══════════════════════════════════════════════════════════════
//  FilterBar
// ══════════════════════════════════════════════════════════════

interface FilterBarProps {
  activeTab: TabKey;
  filterSource: NotificationSource | "";
  filterActionType: ActionType | "";
  priorityMin: number;
  searchText: string;
  viewMode: ViewMode;
  batchMode: boolean;
  onFilterSourceChange: (value: NotificationSource | "") => void;
  onFilterActionTypeChange: (value: ActionType | "") => void;
  onPriorityMinChange: (value: number) => void;
  onSearchTextChange: (value: string) => void;
  onViewModeToggle: () => void;
  onBatchModeToggle: () => void;
  onClearFilters: () => void;
}

export default function FilterBar({
  activeTab,
  filterSource,
  filterActionType,
  priorityMin,
  searchText,
  viewMode,
  batchMode,
  onFilterSourceChange,
  onFilterActionTypeChange,
  onPriorityMinChange,
  onSearchTextChange,
  onViewModeToggle,
  onBatchModeToggle,
  onClearFilters,
}: FilterBarProps) {
  if (activeTab === "events") return null;

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* 来源 */}
      <select
        value={filterSource}
        onChange={(e) => onFilterSourceChange(e.target.value as NotificationSource | "")}
        className="text-xs px-2 py-1 rounded border border bg-surface text"
      >
        {SOURCE_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      {/* 动作类型 */}
      <select
        value={filterActionType}
        onChange={(e) => onFilterActionTypeChange(e.target.value as ActionType | "")}
        className="text-xs px-2 py-1 rounded border border bg-surface text"
      >
        {ACTION_TYPE_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>

      {/* 优先级 */}
      <select
        value={priorityMin}
        onChange={(e) => onPriorityMinChange(Number(e.target.value))}
        className="text-xs px-2 py-1 rounded border border bg-surface text"
      >
        <option value={1}>优先级 {">="} 1</option>
        <option value={2}>优先级 {">="} 2</option>
        <option value={3}>优先级 {">="} 3</option>
        <option value={4}>优先级 {">="} 4</option>
        <option value={5}>优先级 {"="} 5</option>
      </select>

      {/* 搜索 */}
      <div className="relative flex-1 min-w-[120px] max-w-[200px]">
        <Search size={12} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted" />
        <input
          value={searchText}
          onChange={(e) => onSearchTextChange(e.target.value)}
          placeholder="搜索标题/描述..."
          className="w-full text-xs pl-7 pr-2 py-1 rounded border border bg-surface text placeholder:text-muted outline-none focus:border-accent"
        />
      </div>

      {/* 分组切换 */}
      <button
        onClick={onViewModeToggle}
        className={`text-xs px-2 py-1 rounded border transition-colors ${
          viewMode === "grouped"
            ? "border-accent text-accent bg-accent/5"
            : "border text-muted bg-surface"
        }`}
      >
        按类型{viewMode === "grouped" ? " ✓" : ""}
      </button>

      {/* 批量模式 */}
      {activeTab === "pending" && (
        <button
          onClick={onBatchModeToggle}
          className={`text-xs px-2 py-1 rounded border transition-colors ${
            batchMode
              ? "border-accent text-accent bg-accent/5"
              : "border text-muted bg-surface"
          }`}
        >
          批量{batchMode ? " ✓" : ""}
        </button>
      )}

      {/* 如果有筛选，显示清理 */}
      {(filterSource || filterActionType || priorityMin > 1 || searchText) && (
        <button
          onClick={onClearFilters}
          className="text-xs px-2 py-1 rounded text-muted hover:text-error transition-colors"
        >
          清除筛选
        </button>
      )}
    </div>
  );
}
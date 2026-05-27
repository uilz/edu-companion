"use client";

import { useEffect, useRef, useState } from "react";
import { Check, Search, X, ChevronDown } from "lucide-react";

// ── Props ──
export interface ClassifyConfirmPopoverProps {
  /** AI 推测的知识节点名称 */
  skillName: string;
  /** 用户确认分类时回调 */
  onConfirm: () => void;
  /** 用户忽略/关闭弹窗时回调 */
  onDismiss: () => void;
  /**
   * 用户搜索其他知识节点时回调。
   * 返回匹配的节点列表（{ label, id }）。
   * 若返回空数组，下拉框显示"无匹配结果"。
   */
  onSearch: (query: string) => Promise<{ label: string; id: string }[]>;
  /** 自动消失毫秒数（默认 8000），0 表示不自动消失 */
  autoHideDelay?: number;
}

/**
 * ClassifyConfirmPopover
 *
 * 发送消息后浮动出现的分类确认气泡。
 * 显示 "AI 推测这个对话属于：[节点名称]"，带确认/换一个按钮。
 *
 * 使用方式：
 * ```tsx
 * <ClassifyConfirmPopover
 *   skillName="微积分-极限"
 *   onConfirm={() => { ... }}
 *   onDismiss={() => { ... }}
 *   onSearch={async (q) => [{ label: q, id: q }]}
 * />
 * ```
 */
export default function ClassifyConfirmPopover({
  skillName,
  onConfirm,
  onDismiss,
  onSearch,
  autoHideDelay = 8000,
}: ClassifyConfirmPopoverProps) {
  const [showSearch, setShowSearch] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ label: string; id: string }[]>([]);
  const [searching, setSearching] = useState(false);
  const [selectedLabel, setSelectedLabel] = useState<string | null>(null);
  const popoverRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const autoHideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── 自动隐藏 ──
  useEffect(() => {
    if (autoHideDelay <= 0) return;
    autoHideTimerRef.current = setTimeout(() => {
      onDismiss();
    }, autoHideDelay);
    return () => {
      if (autoHideTimerRef.current) clearTimeout(autoHideTimerRef.current);
    };
  }, [autoHideDelay, onDismiss]);

  // ── 搜索防抖 ──
  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const items = await onSearch(query.trim());
        setResults(items);
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query, onSearch]);

  // ── 打开搜索时聚焦输入框 ──
  useEffect(() => {
    if (showSearch && searchInputRef.current) {
      searchInputRef.current.focus();
    }
  }, [showSearch]);

  // ── 点击外部关闭 ──
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        if (showSearch) setShowSearch(false);
        else onDismiss();
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [onDismiss, showSearch]);

  // ── 确认（可能是替换后的节点） ──
  const handleConfirm = () => {
    onConfirm();
  };

  // ── 换一个：打开搜索下拉 ──
  const handleChange = () => {
    setShowSearch(true);
    setQuery("");
    setResults([]);
    setSelectedLabel(null);
  };

  // ── 从搜索结果中选择 ──
  const handleSelectResult = (item: { label: string; id: string }) => {
    setSelectedLabel(item.label);
    setShowSearch(false);
    // 选择后自动确认
    onConfirm();
  };

  // ── 关闭弹窗 ──
  const handleClose = () => {
    onDismiss();
  };

  const displayName = selectedLabel || skillName;

  return (
    <div
      ref={popoverRef}
      className="fixed bottom-24 right-4 z-50 w-72 animate-in fade-in slide-in-from-bottom-2 duration-200"
    >
      {/* 主气泡 */}
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] rounded-xl shadow-xl overflow-hidden">
        {/* 头部 */}
        <div className="flex items-center justify-between px-3 py-2 border-b border-[var(--color-border)] bg-[var(--color-surface)]">
          <span className="text-xs text-[var(--color-text-muted)] font-medium flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--color-accent)] animate-pulse" />
            AI 分类建议
          </span>
          <button
            onClick={handleClose}
            className="p-0.5 text-[var(--color-text-muted)] hover:text-[var(--color-text)] rounded"
            title="关闭"
          >
            <X size={14} />
          </button>
        </div>

        {/* 主体 */}
        <div className="px-3 py-3 space-y-2.5">
          <p className="text-sm text-[var(--color-text)] leading-relaxed">
            AI 推测这个对话属于：
            <span className="font-semibold text-[var(--color-accent)] ml-1">
              {displayName}
            </span>
          </p>

          {/* 搜索模式 */}
          {showSearch && (
            <div className="relative">
              <div className="relative">
                <Search
                  size={14}
                  className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]"
                />
                <input
                  ref={searchInputRef}
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="搜索知识节点..."
                  className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-xs pl-8 pr-3 py-2 rounded-lg focus:outline-none focus:border-[var(--color-accent)] placeholder-[var(--color-text-muted)]"
                />
              </div>

              {/* 搜索结果 */}
              {query.trim() && (
                <div className="mt-1 max-h-36 overflow-y-auto border border-[var(--color-border)] rounded-lg bg-[var(--color-bg)]">
                  {searching ? (
                    <div className="px-3 py-2 text-xs text-[var(--color-text-muted)] text-center">
                      搜索中...
                    </div>
                  ) : results.length > 0 ? (
                    results.map((item) => (
                      <button
                        key={item.id}
                        onClick={() => handleSelectResult(item)}
                        className="w-full px-3 py-2 text-left text-xs text-[var(--color-text)] hover:bg-[var(--color-surface)] flex items-center gap-2 transition-colors"
                      >
                        <ChevronDown size={10} className="text-[var(--color-text-muted)] rotate-[-90deg]" />
                        {item.label}
                      </button>
                    ))
                  ) : (
                    <div className="px-3 py-2 text-xs text-[var(--color-text-muted)] text-center">
                      无匹配结果
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 按钮组 */}
          {!showSearch && (
            <div className="flex items-center gap-2">
              <button
                onClick={handleConfirm}
                className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-[var(--color-accent)] text-white rounded-lg hover:opacity-90 transition-opacity"
              >
                <Check size={13} />
                确认
              </button>
              <button
                onClick={handleChange}
                className="flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-[var(--color-border)] text-[var(--color-text-secondary)] rounded-lg hover:bg-[var(--color-surface)] transition-colors"
              >
                <Search size={13} />
                换一个
              </button>
            </div>
          )}
        </div>

        {/* 底部提示 */}
        <div className="px-3 py-1.5 border-t border-[var(--color-border)] bg-[var(--color-surface)]">
          <p className="text-[10px] text-[var(--color-text-muted)] text-center">
            确认后知识图谱将关联此对话
          </p>
        </div>
      </div>
    </div>
  );
}

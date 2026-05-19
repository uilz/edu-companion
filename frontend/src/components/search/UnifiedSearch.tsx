"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Search, X, Loader2, MessageSquare, FileText, Brain, AlertTriangle } from "lucide-react";
import { useRouter } from "next/navigation";

interface SearchResultItem {
  type: "conversation" | "material" | "knowledge" | "error";
  title: string;
  subtitle: string;
  link: string;
  score: number;
}

interface SearchResponse {
  query: string;
  conversations: SearchResultItem[];
  materials: SearchResultItem[];
  knowledge: SearchResultItem[];
  errors: SearchResultItem[];
  total: number;
}

const CATEGORY_CONFIG = {
  conversation: { label: "对话", icon: MessageSquare, color: "text-blue-400" },
  material: { label: "资料", icon: FileText, color: "text-green-400" },
  knowledge: { label: "知识点", icon: Brain, color: "text-purple-400" },
  error: { label: "错题", icon: AlertTriangle, color: "text-red-400" },
};

export default function UnifiedSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [focused, setFocused] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const router = useRouter();

  const doSearch = useCallback(async (q: string) => {
    if (q.length < 2) {
      setResults(null);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(
        `/api/search?q=${encodeURIComponent(q)}&limit=5`
      );
      if (res.ok) {
        const data = await res.json();
        setResults(data);
      }
    } catch (e) {
      console.error("搜索失败:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleInput = useCallback(
    (value: string) => {
      setQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => doSearch(value), 250);
    },
    [doSearch]
  );

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setFocused(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Keyboard shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  const showDropdown = focused && (query.length >= 2 || loading);

  const renderCategory = (
    items: SearchResultItem[],
    type: "conversation" | "material" | "knowledge" | "error"
  ) => {
    if (items.length === 0) return null;
    const cfg = CATEGORY_CONFIG[type];
    const Icon = cfg.icon;

    return (
      <div key={type} className="py-1">
        <div className="flex items-center gap-1.5 px-3 py-1 text-[11px] font-medium text-[var(--color-text-muted)]">
          <Icon size={12} className={cfg.color} />
          <span>{cfg.label}</span>
          <span className="text-[10px] opacity-60">({items.length})</span>
        </div>
        {items.map((item, i) => (
          <button
            key={`${type}-${i}`}
            onClick={() => {
              if (item.link) router.push(item.link);
              setFocused(false);
              setQuery("");
            }}
            className="w-full text-left px-5 py-1.5 text-xs hover:bg-[var(--color-surface)] transition-colors group"
          >
            <div className="truncate text-[var(--color-text-secondary)] group-hover:text-[var(--color-text)]">
              {item.title}
            </div>
            {item.subtitle && (
              <div className="text-[10px] text-[var(--color-text-muted)] truncate">
                {item.subtitle}
              </div>
            )}
          </button>
        ))}
      </div>
    );
  };

  return (
    <div ref={containerRef} className="relative w-full max-w-[560px] mx-auto">
      {/* Search box */}
      <div
        className={`flex items-center gap-2 px-4 py-2.5 bg-[var(--color-bg)] border transition-all ${
          focused
            ? "border-[var(--color-accent)] shadow-[0_0_0_1px_var(--color-accent)]"
            : "border-[var(--color-border)]"
        }`}
        style={{ borderRadius: "2px" }}
      >
        <Search size={16} className="text-[var(--color-text-muted)] flex-shrink-0" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => handleInput(e.target.value)}
          onFocus={() => setFocused(true)}
          placeholder="搜索对话、资料、知识点..."
          className="flex-1 bg-transparent border-none outline-none text-sm text-[var(--color-text)] placeholder:text-[var(--color-text-muted)]"
        />
        {loading && <Loader2 size={14} className="animate-spin text-[var(--color-text-muted)]" />}
        {query && !loading && (
          <button
            onClick={() => {
              setQuery("");
              setResults(null);
              inputRef.current?.focus();
            }}
          >
            <X size={14} className="text-[var(--color-text-muted)]" />
          </button>
        )}
        <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-mono text-[var(--color-text-muted)] bg-[var(--color-surface)] border border-[var(--color-border)]">
          ⌘K
        </kbd>
      </div>

      {/* Dropdown results */}
      {showDropdown && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-[var(--color-bg)] border border-[var(--color-border)] shadow-xl max-h-[420px] overflow-y-auto z-50">
          {results && results.total === 0 ? (
            <div className="px-4 py-6 text-center">
              <div className="text-xs text-[var(--color-text-muted)]">
                未找到相关内容
              </div>
            </div>
          ) : results ? (
            <>
              {renderCategory(results.conversations, "conversation")}
              {renderCategory(results.materials, "material")}
              {renderCategory(results.knowledge, "knowledge")}
              {renderCategory(results.errors, "error")}
            </>
          ) : loading ? (
            <div className="px-4 py-6 text-center">
              <Loader2 size={14} className="animate-spin mx-auto text-[var(--color-text-muted)]" />
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Search, X, Loader2, MessageSquare, FileText, Brain, AlertTriangle } from "lucide-react";
import { useRouter } from "next/navigation";

// 搜索结果项类型定义：对话、资料、知识点、错题
interface SearchResultItem {
  type: "conversation" | "material" | "knowledge" | "error";
  title: string;
  subtitle: string;
  link: string;
  score: number;
}

// 搜索响应数据结构定义
interface SearchResponse {
  query: string;
  conversations: SearchResultItem[];
  materials: SearchResultItem[];
  knowledge: SearchResultItem[];
  errors: SearchResultItem[];
  total: number;
}

// 分类配置：标签、图标、颜色
const CATEGORY_CONFIG = {
  conversation: { label: "对话", icon: MessageSquare, color: "text-info" },
  material: { label: "资料", icon: FileText, color: "text-success" },
  knowledge: { label: "知识点", icon: Brain, color: "text-accent" },
  error: { label: "错题", icon: AlertTriangle, color: "text-error" },
};

// 统一搜索组件：搜索对话、资料、知识点、错题
export default function UnifiedSearch() {
  // 状态管理：查询关键词、搜索结果、加载状态、焦点状态
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [focused, setFocused] = useState(false);
  // ref：输入框、容器、防抖定时器
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();
  const router = useRouter();

  // 执行搜索：调用 /api/search 接口，查询长度 >= 2 时才发起请求
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

    } finally {
      setLoading(false);
    }
  }, []);

  // 输入处理：更新查询值并防抖触发搜索（250ms 延迟）
  const handleInput = useCallback(
    (value: string) => {
      setQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => doSearch(value), 250);
    },
    [doSearch]
  );

  // 点击外部关闭下拉框
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setFocused(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // 键盘快捷键：⌘K / Ctrl+K 聚焦搜索框
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

  // 是否显示下拉：有焦点且查询长度 >= 2 或正在加载
  const showDropdown = focused && (query.length >= 2 || loading);

  // 渲染分类结果：按类型分组展示搜索项，点击跳转对应链接
  const renderCategory = (
    items: SearchResultItem[],
    type: "conversation" | "material" | "knowledge" | "error"
  ) => {
    if (items.length === 0) return null;
    const cfg = CATEGORY_CONFIG[type];
    const Icon = cfg.icon;

    return (
      <div key={type} className="py-1">
        <div className="flex items-center gap-1.5 px-3 py-1 text-[11px] font-medium text-muted">
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
            className="w-full text-left px-5 py-1.5 text-xs hover:bg-surface transition-colors group"
          >
            <div className="truncate text-secondary group-hover:text">
              {item.title}
            </div>
            {item.subtitle && (
              <div className="text-[10px] text-muted truncate">
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
      {/* 搜索框 */}
      <div
        className={`flex items-center gap-2 px-4 py-2.5 bg-page border transition-all ${
          focused
            ? "border-accent ring-1 ring-accent"
            : "border"
        }`}
        style={{ borderRadius: "2px" }}
      >
        <Search size={16} className="text-muted flex-shrink-0" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => handleInput(e.target.value)}
          onFocus={() => setFocused(true)}
          placeholder="搜索对话、资料、知识点..."
          className="flex-1 bg-transparent border-none outline-none text-sm text placeholder:text-muted"
        />
        {loading && <Loader2 size={14} className="animate-spin text-muted" />}
        {query && !loading && (
          <button
            onClick={() => {
              setQuery("");
              setResults(null);
              inputRef.current?.focus();
            }}
          >
            <X size={14} className="text-muted" />
          </button>
        )}
        <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 text-[10px] font-mono text-muted bg-surface border border">
          ⌘K
        </kbd>
      </div>

      {/* 下拉结果面板 */}
      {showDropdown && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-page border border max-h-[420px] overflow-y-auto z-50">
          {/* 无结果提示 */}
          {results && results.total === 0 ? (
            <div className="px-4 py-6 text-center">
              <div className="text-xs text-muted">
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
              {/* 加载中状态 */}
              <Loader2 size={14} className="animate-spin mx-auto text-muted" />
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}

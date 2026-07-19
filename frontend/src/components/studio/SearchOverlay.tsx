"use client";

import React, { useState, useRef, useEffect } from "react";
import { X } from "lucide-react";

// ─── Types ──────────────────────────────────────────────────────
export type ResultBadge = "对话" | "资源" | "笔记" | "闪卡";

export interface SearchResult {
  icon: string;
  title: string;
  snippet: string;
  meta: string;
  badge: ResultBadge;
}

export interface SearchOverlayProps {
  open: boolean;
  onClose: () => void;
  /** Returns results for a query (can be sync or async) */
  onSearch: (query: string) => SearchResult[] | Promise<SearchResult[]>;
}

// ─── Component ──────────────────────────────────────────────────
export default function SearchOverlay({
  open,
  onClose,
  onSearch,
}: SearchOverlayProps) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus input when overlay opens
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open]);

  // Reset state on close
  useEffect(() => {
    if (!open) {
      setQuery("");
      setResults([]);
      setHasSearched(false);
    }
  }, [open]);

  const handleSearch = async (q: string) => {
    setQuery(q);
    if (q.trim()) {
      const r = await onSearch(q);
      setResults(r);
      setHasSearched(true);
    } else {
      setResults([]);
      setHasSearched(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleSearch(e.currentTarget.value);
    }
    if (e.key === "Escape") {
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-start justify-center pt-[14vh]"
      style={{ background: "rgba(0,0,0,0.25)" }}
      onClick={onClose}
    >
      <div
        className="rounded-2xl w-[540px] overflow-hidden animate-fadeIn"
        style={{
          background: "#fff",
          boxShadow: "0 8px 32px rgba(0,0,0,0.08)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* ── Input Row ── */}
        <div
          className="flex items-center gap-[10px] px-4 py-4"
          style={{ borderBottom: "1px solid #e6dcd0" }}
        >
          <input
            ref={inputRef}
            type="text"
            placeholder="搜索所有资源、对话、闪卡..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              // Don't auto-search on every keystroke — user presses Enter
            }}
            onKeyDown={handleKeyDown}
            className="flex-1 text-[17px] outline-none bg-transparent"
            style={{ color: "#2a2420" }}
          />
          <button
            className="p-[6px] rounded-md text-[18px] transition-colors duration-100"
            style={{ color: "#a69c8f" }}
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </div>

        {/* ── Results ── */}
        <div className="max-h-[400px] overflow-y-auto py-2">
          {hasSearched && results.length === 0 && (
            <div
              className="py-8 text-center text-[14px]"
              style={{ color: "#a69c8f" }}
            >
              没有找到结果，试试其他关键词
            </div>
          )}
          {!hasSearched && (
            <div
              className="py-8 text-center text-[14px]"
              style={{ color: "#a69c8f" }}
            >
              输入关键词开始搜索...
            </div>
          )}
          {results.map((r, i) => (
            <div
              key={i}
              className="flex gap-3 p-3 mx-2 my-[2px] rounded-xl cursor-pointer transition-all duration-100 hover:-translate-y-px"
              style={{
                background: "#fff",
                boxShadow:
                  "0 1px 2px rgba(0,0,0,0.04), 0 0 0 1px #e6dcd0",
              }}
            >
              <div
                className="text-[9px] font-semibold tracking-[0.02em] flex-shrink-0 w-8 text-center"
                style={{ color: "#a69c8f" }}
              >
                {r.icon}
              </div>
              <div className="flex-1 min-w-0">
                <div
                  className="text-[13px] font-semibold"
                  style={{ color: "#2a2420" }}
                >
                  {r.title}
                </div>
                <div
                  className="text-[13px] mt-[3px] leading-[1.5]"
                  style={{ color: "#7a7068" }}
                >
                  {r.snippet}
                </div>
                <div
                  className="text-[11px] mt-1"
                  style={{ color: "#a69c8f" }}
                >
                  {r.meta}
                </div>
              </div>
              <span
                className="text-[9px] px-2 py-[2px] rounded-full font-medium flex-shrink-0"
                style={{
                  background: "#e6dcd0",
                  color: "#7a7068",
                }}
              >
                {r.badge}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

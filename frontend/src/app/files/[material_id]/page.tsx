"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import {
  FileText,
  Loader2,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  BookOpen,
  Sparkles,
  Trash2,
  ArrowLeft,
  Search,
  ChevronUp,
  RefreshCw,
} from "lucide-react";
import { authedFetch, API_BASE } from "@/lib/api/api";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import PreviewContent from "@/components/PreviewContent";

interface TocNode {
  toc_id: string;
  level: number;
  heading: string;
  children: TocNode[];
  chunk_start: number;
  chunk_end: number;
}

interface ChunkItem {
  chunk_index: number;
  text: string;
  chunk_type: string;
  page_number: number | null;
  heading_path: string;
}

interface FileDetail {
  material_id: string;
  file_name: string;
  file_type: string;
  file_size: string;
  purpose: string;
  status: string;
  chunk_count: number;
  toc_count: number;
  skills: string[];
  summary: string;
  created_at: string;
}

type ChunkRefs = Record<number, HTMLDivElement | null>;

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

export default function FileDetailPage() {
  const params = useParams();
  const materialId = params?.material_id as string;

  const [file, setFile] = useState<FileDetail | null>(null);
  const [toc, setToc] = useState<TocNode[]>([]);
  const [chunks, setChunks] = useState<ChunkItem[]>([]);
  const [chunkFullText, setChunkFullText] = useState<Record<number, string>>({});
  const [loadingFull, setLoadingFull] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [expandedToc, setExpandedToc] = useState<Set<string>>(new Set());
  const [activeChunk, setActiveChunk] = useState<number | null>(null);
  const [tocCollapsed, setTocCollapsed] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const chunkRefs = useRef<ChunkRefs>({});
  const tocContainerRef = useRef<HTMLDivElement | null>(null);
  const tocNodeRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const manualScrollRef = useRef(false);
  const activeChunkRef = useRef<number | null>(null);
  activeChunkRef.current = activeChunk;

  // Initial data loading: file info, TOC, chunks
  useEffect(() => {
    if (!materialId) return;
    Promise.all([
      authedFetch(`/api/files/${materialId}`).then((r) => r.json()),
      authedFetch(`/api/files/${materialId}/toc`).then((r) => r.json()),
      authedFetch(`/api/files/${materialId}/chunks?page_size=200`).then((r) => r.json()),
    ])
      .then(([fileData, tocData, chunksData]) => {
        setFile(fileData);
        setToc(tocData.toc || []);
        setChunks(chunksData.items || []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [materialId]);

  const handleReindex = async () => {
    setReindexing(true);
    try {
      const res = await authedFetch(`/api/files/${materialId}/reindex`, { method: "POST" });
      if (!res.ok) throw new Error((await res.json()).detail || "重新索引失败");
      // 重新加载数据
      const [fileData, tocData, chunksData] = await Promise.all([
        authedFetch(`/api/files/${materialId}`).then((r) => r.json()),
        authedFetch(`/api/files/${materialId}/toc`).then((r) => r.json()),
        authedFetch(`/api/files/${materialId}/chunks?page_size=200`).then((r) => r.json()),
      ]);
      setFile(fileData);
      setToc(tocData.toc || []);
      setChunks(chunksData.items || []);
      setExpandedToc(new Set());
      setActiveChunk(null);
    } catch (e: any) {
      console.error("Reindex failed:", e);
      alert(e.message || "重新索引失败");
    } finally {
      setReindexing(false);
    }
  };

  // 滚动追踪：找到 OFFSET 线处的 chunk（正在阅读的位置）
  useEffect(() => {
    if (chunks.length === 0) return;

    let rafId: number;
    let scrollEndTimer: ReturnType<typeof setTimeout> | null = null;
    const OFFSET = 120;

    const handleScroll = () => {
      // 用户停止滚动 400ms 后认为手动滚动结束
      if (scrollEndTimer) clearTimeout(scrollEndTimer);
      scrollEndTimer = setTimeout(() => {
        manualScrollRef.current = false;
      }, 400);

      if (manualScrollRef.current) return;
      cancelAnimationFrame(rafId);
      rafId = requestAnimationFrame(() => {
        // 遍历所有 chunk，找到最后一个 top ≤ OFFSET 的
        // 即「当前读到哪」的自然追踪
        let foundIdx = activeChunkRef.current ?? 0;
        for (const chunk of chunks) {
          const el = chunkRefs.current[chunk.chunk_index];
          if (el) {
            const top = el.getBoundingClientRect().top;
            if (top <= OFFSET) {
              foundIdx = chunk.chunk_index;
            } else {
              break; // DOM 有序，后续 top 只会更大
            }
          }
        }
        if (foundIdx !== activeChunkRef.current) setActiveChunk(foundIdx);
      });
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll(); // 初始计算一次
    return () => {
      window.removeEventListener("scroll", handleScroll);
      cancelAnimationFrame(rafId);
      if (scrollEndTimer) clearTimeout(scrollEndTimer);
    };
  }, [chunks]);

  const scrollToChunk = useCallback((chunkIndex: number) => {
    const el = chunkRefs.current[chunkIndex];
    if (el) {
      manualScrollRef.current = true;
      el.scrollIntoView({ behavior: "smooth", block: "start" });
      setActiveChunk(chunkIndex);
      // manualScrollRef 会在下次滚动停止 400ms 后被置为 false
    }
  }, []);

  const toggleToc = (tocId: string) => {
    setExpandedToc((prev) => {
      const next = new Set(prev);
      if (next.has(tocId)) next.delete(tocId);
      else next.add(tocId);
      return next;
    });
  };

  const toggleFullText = async (chunkIndex: number) => {
    if (chunkFullText[chunkIndex]) {
      setChunkFullText((prev) => {
        const next = { ...prev };
        delete next[chunkIndex];
        return next;
      });
      return;
    }
    setLoadingFull(chunkIndex);
    try {
      const res = await authedFetch(`/api/files/${materialId}/chunks/${chunkIndex}/full`);
      const data = await res.json();
      setChunkFullText((prev) => ({ ...prev, [chunkIndex]: data.text }));
    } catch (e) {
      console.error("Failed to load full chunk:", e);
    } finally {
      setLoadingFull(null);
    }
  };

  // Build heading_path → toc_id map for precise matching
  const headingPathToTocId = React.useMemo(() => {
    const map = new Map<string, string>();
    const walk = (nodes: TocNode[], ancestors: string[]) => {
      for (const node of nodes) {
        const path = [...ancestors, node.heading].join(" > ");
        map.set(path, node.toc_id);
        if (node.children.length > 0) {
          walk(node.children, [...ancestors, node.heading]);
        }
      }
    };
    walk(toc, []);
    return map;
  }, [toc]);

  // Find deepest active TOC node: 优先 heading_path 精确匹配，回退到范围匹配
  const activeTocId = React.useMemo(() => {
    if (activeChunk === null) return null;
    const chunk = chunks.find(c => c.chunk_index === activeChunk);
    if (!chunk) return null;

    // 优先使用 heading_path 精确匹配
    if (chunk.heading_path) {
      const tocId = headingPathToTocId.get(chunk.heading_path);
      if (tocId) return tocId;
    }

    // 回退：范围匹配（用于 heading_path 为空的 chunk）
    const findLeaf = (nodes: TocNode[]): string | null => {
      for (const node of nodes) {
        if (node.chunk_start >= 0 && activeChunk >= node.chunk_start && activeChunk <= node.chunk_end) {
          if (node.children.length > 0) {
            const childMatch = findLeaf(node.children);
            if (childMatch) return childMatch;
          }
          return node.toc_id;
        }
      }
      return null;
    };
    return findLeaf(toc);
  }, [activeChunk, toc, chunks, headingPathToTocId]);

  // Auto-expand active node's ancestors, auto-collapse others
  useEffect(() => {
    if (!activeTocId || toc.length === 0) return;
    const pathIds = new Set<string>();
    const findPath = (nodes: TocNode[]): boolean => {
      for (const node of nodes) {
        if (node.toc_id === activeTocId) { pathIds.add(node.toc_id); return true; }
        if (node.children.length > 0 && findPath(node.children)) {
          pathIds.add(node.toc_id);
          return true;
        }
      }
      return false;
    };
    findPath(toc);
    if (pathIds.size > 0) {
      setExpandedToc(pathIds);
    }
  }, [activeTocId, toc]);

  // Auto-scroll TOC sidebar to keep active node visible
  useEffect(() => {
    if (!activeTocId) return;
    const container = tocContainerRef.current;
    const nodeEl = tocNodeRefs.current[activeTocId];
    if (!container || !nodeEl) return;

    const containerRect = container.getBoundingClientRect();
    const nodeRect = nodeEl.getBoundingClientRect();

    // 节点超出容器顶部 → 向上滚动
    if (nodeRect.top < containerRect.top) {
      container.scrollBy({ top: nodeRect.top - containerRect.top - 8, behavior: "smooth" });
    }
    // 节点超出容器底部 → 向下滚动
    else if (nodeRect.bottom > containerRect.bottom) {
      container.scrollBy({ top: nodeRect.bottom - containerRect.bottom + 8, behavior: "smooth" });
    }
  }, [activeTocId]);

  const renderTocNode = (node: TocNode, depth: number = 0) => {
    const hasChildren = node.children.length > 0;
    const isExpanded = expandedToc.has(node.toc_id);
    const chunkCount = node.chunk_end - node.chunk_start + 1;
    const isActive = node.toc_id === activeTocId;

    return (
      <TocNodeItem
        key={node.toc_id}
        node={node}
        depth={depth}
        isExpanded={isExpanded}
        isActive={isActive}
        hasChildren={hasChildren}
        chunkCount={chunkCount}
        onToggle={toggleToc}
        onScroll={scrollToChunk}
        tocRef={(el) => { tocNodeRefs.current[node.toc_id] = el; }}
        renderChild={(child, d) => renderTocNode(child, d)}
      />
    );
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" />
      </div>
    );
  }

  if (!file) {
    return (
      <div className="p-6 text-center text-sm text-[var(--color-text-muted)]">
        文件不存在
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <style>{`
        .toc-scrollbar::-webkit-scrollbar { width: 4px; }
        .toc-scrollbar::-webkit-scrollbar-thumb { background: var(--color-border); border-radius: 4px; }
        .toc-scrollbar::-webkit-scrollbar-thumb:hover { background: var(--color-text-muted); }
        .toc-scrollbar { scrollbar-width: thin; }
      `}</style>
      {/* Breadcrumb */}
      <a
        href="/resources"
        className="inline-flex items-center gap-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-accent)] mb-4"
      >
        <ArrowLeft size={12} />
        返回资源管理
      </a>

      {/* File header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-[var(--color-surface-hover)] flex items-center justify-center text-[var(--color-text-muted)]">
            <FileText size={20} />
          </div>
          <div>
            <h1 className="text-lg font-bold text-[var(--color-text)]">{file.file_name}</h1>
            <div className="flex items-center gap-2 mt-1 text-[11px] text-[var(--color-text-muted)]">
              <span>{file.file_type?.toUpperCase()}</span>
              <span>·</span>
              <span>{file.chunk_count} 个分块</span>
              {file.toc_count > 0 && (
                <>
                  <span>·</span>
                  <span>{file.toc_count} 章</span>
                </>
              )}
              <span>·</span>
              <span>{file.created_at?.slice(0, 10)}</span>
            </div>
            {/* Skills tags */}
            {file.skills && file.skills.length > 0 && (
              <div className="flex items-center gap-1 mt-2 flex-wrap">
                <Sparkles size={11} className="text-amber-500 shrink-0" />
                {file.skills.map((skill) => (
                  <span key={skill} className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400">
                    {skill}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Summary */}
      {file.summary && (
        <div className="mb-4 p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]">
          <div className="flex items-center gap-1.5 mb-1">
            <BookOpen size={12} className="text-[var(--color-accent)]" />
            <span className="text-[10px] font-medium text-[var(--color-text-muted)]">摘要</span>
          </div>
          <p className="text-xs text-[var(--color-text)] leading-relaxed">{file.summary}</p>
        </div>
      )}

      <div className="flex gap-4">
        {/* TOC sidebar - collapsible */}
        {toc.length > 0 && (
          <div className={`transition-all duration-200 ease-in-out flex-shrink-0 ${
            tocCollapsed ? "w-0 overflow-hidden min-w-0" : "w-64"
          }`}>
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden sticky top-6 w-full">
              <div className="px-3 py-2.5 border-b border-[var(--color-border)]/50 flex items-center justify-between">
                <span className="text-[11px] font-semibold text-[var(--color-text-muted)] tracking-wide">目录</span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={handleReindex}
                    disabled={reindexing}
                    className="p-1 rounded-md hover:bg-[var(--color-border)]/30 text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
                    title="重新索引"
                  >
                    <RefreshCw size={12} className={reindexing ? "animate-spin" : ""} />
                  </button>
                  <button
                    onClick={() => setTocCollapsed(true)}
                    className="p-1 rounded-md hover:bg-[var(--color-border)]/30 text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
                    title="收起目录"
                  >
                    <ChevronLeft size={13} />
                  </button>
                </div>
              </div>
              <div ref={tocContainerRef} className="py-0.5 max-h-[60vh] overflow-y-auto toc-scrollbar">
                {toc.map((node) => renderTocNode(node))}
              </div>
            </div>
          </div>
        )}

        {/* TOC toggle button (when collapsed) */}
        {toc.length > 0 && tocCollapsed && (
          <button
            onClick={() => setTocCollapsed(false)}
            className="flex-shrink-0 w-6 h-14 mt-10 rounded-r-lg bg-[var(--color-surface)] border border-l-0 border-[var(--color-border)] flex items-center justify-center hover:bg-[var(--color-surface-hover)] transition-colors text-[var(--color-text-muted)]"
            title="展开目录"
          >
            <ChevronRight size={13} />
          </button>
        )}

        {/* Main content area */}
        <div className="flex-1 min-w-0 space-y-4">
          {/* 统一预览区域（图片/PDF/HTML/音视频/DOCX/代码/Markdown） */}
          <PreviewContent file={{ material_id: file.material_id, file_name: file.file_name, file_type: file.file_type }} />

          {/* PPTX note */}
          {file.file_name?.toLowerCase().endsWith(".pptx") && (
            <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/20">
              <p className="text-xs text-amber-600 dark:text-amber-400">
                PPTX 文件以文本分块形式展示。如需查看完整幻灯片，请下载文件后使用 PowerPoint 打开。
              </p>
            </div>
          )}

          {/* .doc note */}
          {file.file_name?.toLowerCase().endsWith(".doc") && !file.file_name?.toLowerCase().endsWith(".docx") && (
            <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/20">
              <p className="text-xs text-amber-600 dark:text-amber-400">
                旧版 .doc 文件以文本分块形式展示。如需查看原始格式，请下载文件后使用 Word 打开。
              </p>
            </div>
          )}

          {/* Chunks */}
          {chunks.length > 0 && (
            <div className="space-y-2">
              <div className="text-[11px] font-medium text-[var(--color-text-muted)] mb-2">
                内容分块（{chunks.length}）
              </div>
              {chunks.map((chunk) => {
                const fullTextLoaded = chunkFullText[chunk.chunk_index];
                const displayText = fullTextLoaded || chunk.text;
                const isLong = chunk.text.length > 300;
                const isActive = activeChunk === chunk.chunk_index;
                return (
                  <div
                    key={chunk.chunk_index}
                    ref={(el) => { chunkRefs.current[chunk.chunk_index] = el; }}
                    data-chunk-index={chunk.chunk_index}
                    id={`chunk-${chunk.chunk_index}`}
                    className={`p-3 rounded-xl border transition-all scroll-mt-6 ${
                      isActive
                        ? "bg-[var(--color-accent)]/5 border-[var(--color-accent)]/30 shadow-sm"
                        : "bg-[var(--color-surface)] border-[var(--color-border)]"
                    }`}
                  >
                    <div className="text-[10px] text-[var(--color-text-muted)] mb-1">
                      #{chunk.chunk_index + 1}
                      {chunk.page_number && <span> · 第 {chunk.page_number} 页</span>}
                    </div>
                    <div className={`text-xs text-[var(--color-text)] leading-relaxed ${!fullTextLoaded ? "line-clamp-4" : ""}`}>
                      <MarkdownRenderer>{displayText}</MarkdownRenderer>
                    </div>
                    {isLong && (
                      <button
                        onClick={() => toggleFullText(chunk.chunk_index)}
                        className="mt-1.5 flex items-center gap-1 text-[10px] text-[var(--color-accent)] hover:opacity-80 transition-opacity"
                      >
                        {loadingFull === chunk.chunk_index ? (
                          <Loader2 size={10} className="animate-spin" />
                        ) : fullTextLoaded ? (
                          <><ChevronUp size={10} /> 收起</>
                        ) : (
                          <><ChevronDown size={10} /> 展开全文 ({chunk.text.length}字)</>
                        )}
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
    );
  }

  // ── TOC 节点组件 ──
  function TocNodeItem({
  node, depth, isExpanded, isActive, hasChildren, chunkCount,
  onToggle, onScroll, tocRef, renderChild,
}: {
  node: TocNode; depth: number; isExpanded: boolean; isActive: boolean;
  hasChildren: boolean; chunkCount: number;
  onToggle: (id: string) => void; onScroll: (idx: number) => void;
  tocRef: (el: HTMLDivElement | null) => void;
  renderChild: (node: TocNode, depth: number) => React.ReactNode;
}) {
  return (
    <div ref={tocRef}>
      <div className="flex items-center min-h-[28px] text-[12px] leading-tight border-l-2 cursor-pointer transition-colors"
        style={{ paddingLeft: `${10 + depth * 14}px`, paddingRight: '8px' }}
      >
        {/* Chevron area: only toggles expand/collapse */}
        <span
          className={`w-3.5 flex-shrink-0 flex items-center justify-center ${hasChildren ? "cursor-pointer hover:opacity-70" : ""}`}
          onClick={(e) => { e.stopPropagation(); if (hasChildren) onToggle(node.toc_id); }}
        >
          {hasChildren ? (
            isExpanded
              ? <ChevronDown size={9} className="text-[var(--color-text-muted)]" />
              : <ChevronRight size={9} className="text-[var(--color-text-muted)]" />
          ) : null}
        </span>
        {/* Text area: scroll + auto-expand */}
        <span
          className={`flex-1 flex items-center gap-1 cursor-pointer`}
          onClick={(e) => {
            if (node.chunk_start >= 0) onScroll(node.chunk_start);
          }}
        >
          <span className={`truncate ${isActive ? "text-[var(--color-accent)] font-medium" : "text-[var(--color-text)]"}`}>{node.heading}</span>
          {chunkCount > 0 && (
            <span className="flex-shrink-0 text-[9px] text-[var(--color-text-muted)] opacity-50 ml-auto tabular-nums">{chunkCount}个分块</span>
          )}
        </span>
      </div>
      {hasChildren && isExpanded && (
        <div>
          {node.children.map((child) => renderChild(child, depth + 1))}
        </div>
      )}
    </div>
  );
}
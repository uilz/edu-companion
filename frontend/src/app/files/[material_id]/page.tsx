"use client";

import React, { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import {
  FileText,
  Loader2,
  ChevronRight,
  ChevronDown,
  BookOpen,
  Sparkles,
  Trash2,
  ArrowLeft,
  Search,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

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
  created_at: string;
}

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
  const [loading, setLoading] = useState(true);
  const [expandedToc, setExpandedToc] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!materialId) return;
    Promise.all([
      fetch(`${API_BASE}/api/files/${materialId}`).then((r) => r.json()),
      fetch(`${API_BASE}/api/files/${materialId}/toc`).then((r) => r.json()),
      fetch(`${API_BASE}/api/files/${materialId}/chunks`).then((r) => r.json()),
    ])
      .then(([fileData, tocData, chunksData]) => {
        setFile(fileData);
        setToc(tocData.toc || []);
        setChunks(chunksData.items || []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [materialId]);

  const toggleToc = (tocId: string) => {
    setExpandedToc((prev) => {
      const next = new Set(prev);
      if (next.has(tocId)) next.delete(tocId);
      else next.add(tocId);
      return next;
    });
  };

  const renderTocNode = (node: TocNode, depth: number = 0) => {
    const hasChildren = node.children.length > 0;
    const isExpanded = expandedToc.has(node.toc_id);
    const chunkCount = node.chunk_end - node.chunk_start + 1;

    return (
      <div key={node.toc_id}>
        <button
          onClick={() => toggleToc(node.toc_id)}
          className={`w-full flex items-center gap-1.5 px-3 py-1.5 rounded text-xs hover:bg-[var(--color-surface-hover)] transition-colors text-left ${
            depth === 0 ? "font-medium text-[var(--color-text)]" : "text-[var(--color-text-muted)]"
          }`}
          style={{ paddingLeft: `${12 + depth * 16}px` }}
        >
          {hasChildren ? (
            isExpanded ? <ChevronDown size={10} /> : <ChevronRight size={10} />
          ) : (
            <span className="w-2.5" />
          )}
          <span className="truncate">{node.heading}</span>
          {chunkCount > 0 && (
            <span className="text-[9px] text-[var(--color-text-muted)] ml-auto opacity-60">
              {chunkCount}个分块
            </span>
          )}
        </button>
        {hasChildren && isExpanded && (
          <div>
            {node.children.map((child) => renderTocNode(child, depth + 1))}
          </div>
        )}
      </div>
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
      {/* Breadcrumb */}
      <a
        href="/resources"
        className="inline-flex items-center gap-1 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-accent)] mb-4"
      >
        <ArrowLeft size={12} />
        返回资源管理
      </a>

      {/* File header */}
      <div className="flex items-start justify-between mb-6">
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
          </div>
        </div>
      </div>

      <div className="flex gap-6">
        {/* TOC sidebar */}
        {toc.length > 0 && (
          <div className="w-64 flex-shrink-0">
            <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] overflow-hidden">
              <div className="px-3 py-2 border-b border-[var(--color-border)]/50 text-[11px] font-medium text-[var(--color-text-muted)]">
                📖 目录导航
              </div>
              <div className="py-1 max-h-[60vh] overflow-y-auto">
                {toc.map((node) => renderTocNode(node))}
              </div>
            </div>
          </div>
        )}

        {/* Chunks */}
        <div className="flex-1 space-y-2">
          <div className="text-[11px] font-medium text-[var(--color-text-muted)] mb-2">
            内容分块（{chunks.length}）
          </div>
          {chunks.map((chunk) => (
            <div
              key={chunk.chunk_index}
              className="p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]"
            >
              <div className="text-[10px] text-[var(--color-text-muted)] mb-1">
                #{chunk.chunk_index + 1}
                {chunk.page_number && <span> · 第 {chunk.page_number} 页</span>}
              </div>
              <p className="text-xs text-[var(--color-text)] leading-relaxed line-clamp-4">
                {chunk.text}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

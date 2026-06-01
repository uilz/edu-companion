"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Upload,
  FileText,
  Image,
  File,
  Search,
  Trash2,
  Loader2,
  BookOpen,
  Clock,
  CheckCircle,
  AlertCircle,
  Sparkles,
  ChevronDown,
  X,
} from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FileItem {
  material_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  purpose: string;
  status: string;
  chunk_count: number;
  toc_count: number;
  created_at: string;
  indexed_at: string | null;
}

type Tab = "library" | "session";
type TypeFilter = "all" | "pdf" | "docx" | "image" | "document";

export default function FilesPage() {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("library");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [search, setSearch] = useState("");
  const [uploading, setUploading] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [deleting, setDeleting] = useState<string | null>(null);

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        purpose: tab,
        page: String(page),
        page_size: "20",
      });
      if (typeFilter !== "all") params.set("type", typeFilter);
      if (search) params.set("search", search);

      const res = await fetch(`${API_BASE}/api/files?${params}`);
      const data = await res.json();
      setFiles(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      console.error("Failed to load files:", e);
    } finally {
      setLoading(false);
    }
  }, [tab, typeFilter, search, page]);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("purpose", tab);
      formData.append("upload_source", "files_page");

      const res = await fetch(`${API_BASE}/api/files/upload`, {
        method: "POST",
        body: formData,
      });
      if (res.ok) {
        // 轮询直到索引完成
        const data = await res.json();
        pollIndexStatus(data.material_id);
      }
    } catch (e) {
      console.error("Upload failed:", e);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  };

  const pollIndexStatus = async (materialId: string) => {
    for (let i = 0; i < 30; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const res = await fetch(`${API_BASE}/api/files/${materialId}`);
        const data = await res.json();
        if (data.status === "indexed" || data.status === "index_failed") {
          fetchFiles();
          return;
        }
      } catch {
        fetchFiles();
        return;
      }
    }
    fetchFiles();
  };

  const handleDelete = async (materialId: string) => {
    setDeleting(materialId);
    try {
      await fetch(`${API_BASE}/api/files/${materialId}`, { method: "DELETE" });
      fetchFiles();
    } catch (e) {
      console.error("Delete failed:", e);
    } finally {
      setDeleting(null);
    }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  };

  const typeIcon = (ft: string) => {
    switch (ft) {
      case "pdf": return <BookOpen size={16} />;
      case "image": return <Image size={16} />;
      default: return <File size={16} />;
    }
  };

  const statusBadge = (status: string) => {
    switch (status) {
      case "indexed":
        return <span className="flex items-center gap-1 text-[10px] text-[var(--color-success)]"><CheckCircle size={10} />已索引</span>;
      case "uploading":
      case "pending":
        return <span className="flex items-center gap-1 text-[10px] text-[var(--color-accent)]"><Loader2 size={10} className="animate-spin" />索引中</span>;
      case "index_failed":
        return <span className="flex items-center gap-1 text-[10px] text-[var(--color-error)]"><AlertCircle size={10} />索引失败</span>;
      default:
        return <span className="text-[10px] text-[var(--color-text-muted)]">{status}</span>;
    }
  };

  const typeFilters: { key: TypeFilter; label: string }[] = [
    { key: "all", label: "全部" },
    { key: "pdf", label: "PDF" },
    { key: "docx", label: "文档" },
    { key: "image", label: "图片" },
    { key: "document", label: "笔记" },
  ];

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-bold text-[var(--color-text)]">资料库</h1>
          <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
            管理你的学习文件，知识库文件自动索引供 AI 参考
          </p>
        </div>
        <label className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium bg-[var(--color-accent)] text-white hover:opacity-90 cursor-pointer transition-opacity">
          <Upload size={14} />
          {uploading ? "上传中..." : "上传文件"}
          <input
            type="file"
            className="hidden"
            accept=".pdf,.docx,.pptx,.xlsx,.md,.txt,.jpg,.jpeg,.png,.gif,.webp,.mp3,.wav"
            onChange={handleUpload}
            disabled={uploading}
          />
        </label>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-4 mb-4 border-b border-[var(--color-border)]/50">
        {(["library", "session"] as const).map((t) => (
          <button
            key={t}
            onClick={() => { setTab(t); setPage(1); }}
            className={`flex items-center gap-1.5 pb-2 text-xs font-medium border-b-2 transition-colors ${
              tab === t
                ? "text-[var(--color-accent)] border-[var(--color-accent)]"
                : "text-[var(--color-text-muted)] border-transparent hover:text-[var(--color-text)]"
            }`}
          >
            {t === "library" ? <BookOpen size={12} /> : <Clock size={12} />}
            {t === "library" ? "📁 知识库" : "📋 临时文件"}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        {typeFilters.map((tf) => (
          <button
            key={tf.key}
            onClick={() => { setTypeFilter(tf.key); setPage(1); }}
            className={`px-2.5 py-1 rounded-lg text-[10px] font-medium border transition-colors ${
              typeFilter === tf.key
                ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-accent)]/30"
            }`}
          >
            {tf.label}
          </button>
        ))}
        <div className="flex-1" />
        <div className="relative">
          <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            placeholder="搜索文件..."
            className="w-40 pl-7 pr-2 py-1.5 text-[11px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)]"
          />
        </div>
      </div>

      {/* File list */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" />
        </div>
      ) : files.length === 0 ? (
        <div className="flex flex-col items-center py-16 text-center border border-dashed border-[var(--color-border)] rounded-xl">
          <FileText size={32} className="text-[var(--color-text-muted)] mb-3 opacity-40" />
          <p className="text-sm text-[var(--color-text-muted)]">
            {tab === "library" ? "知识库为空" : "没有临时文件"}
          </p>
          <p className="text-xs text-[var(--color-text-muted)] mt-1 opacity-60">
            点击右上角「上传文件」开始
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {files.map((file) => (
            <div
              key={file.material_id}
              className="flex items-center gap-3 p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] hover:border-[var(--color-accent)]/30 transition-all group"
            >
              {/* Icon */}
              <div className="w-8 h-8 rounded-lg bg-[var(--color-surface-hover)] flex items-center justify-center text-[var(--color-text-muted)] flex-shrink-0">
                {typeIcon(file.file_type)}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--color-text)] truncate">
                    {file.file_name}
                  </span>
                  <span className="text-[9px] px-1 py-0.5 rounded-full bg-[var(--color-surface-hover)] text-[var(--color-text-muted)] uppercase">
                    {file.file_type}
                  </span>
                </div>
                <div className="flex items-center gap-3 mt-1 text-[10px] text-[var(--color-text-muted)]">
                  <span>{formatSize(file.file_size)}</span>
                  {file.chunk_count > 0 && <span>{file.chunk_count} 个分块</span>}
                  {file.toc_count > 0 && <span>{file.toc_count} 章</span>}
                  <span>{file.created_at?.slice(0, 10)}</span>
                  {statusBadge(file.status)}
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                {file.status === "indexed" && (
                  <>
                    <a
                      href={`/files/${file.material_id}`}
                      className="p-1.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent)]/5"
                      title="查看详情"
                    >
                      <FileText size={12} />
                    </a>
                    <button
                      onClick={() => handleDelete(file.material_id)}
                      disabled={deleting === file.material_id}
                      className="p-1.5 rounded text-[var(--color-text-muted)] hover:text-[var(--color-error)] hover:bg-[var(--color-error)]/5"
                      title="删除"
                    >
                      {deleting === file.material_id ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}

          {/* Pagination */}
          {total > 20 && (
            <div className="flex items-center justify-center gap-2 pt-4">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="px-2.5 py-1 rounded text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-30"
              >
                上一页
              </button>
              <span className="text-[10px] text-[var(--color-text-muted)]">
                {page} / {Math.ceil(total / 20)}
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page >= Math.ceil(total / 20)}
                className="px-2.5 py-1 rounded text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-30"
              >
                下一页
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

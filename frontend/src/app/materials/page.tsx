"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  Upload,
  FileText,
  Search,
  Trash2,
  Loader2,
  BookOpen,
  File,
  CheckCircle2,
  XCircle,
  ChevronRight,
} from "lucide-react";

// ── Types ──
interface Material {
  material_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  status: string;
  chunk_count: number;
  question_count: number;
  skills_covered: string[];
  created_at: string | null;
  indexed_at: string | null;
}

interface SearchResult {
  chunk_id: string;
  text: string;
  chunk_type: string;
  skill_ids: string[];
  source_file: string;
  page_number: number | null;
  material_id: string;
  similarity: number;
}

// ── API helpers ──
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

// ── File size formatter ──
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// ── Status badge ──
function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
    ready: { icon: <CheckCircle2 size={12} />, label: "已索引", color: "#22c55e" },
    indexing: { icon: <Loader2 size={12} className="animate-spin" />, label: "索引中", color: "#f59e0b" },
    uploaded: { icon: <File size={12} />, label: "已上传", color: "#3b82f6" },
    uploaded_only: { icon: <File size={12} />, label: "已上传", color: "#3b82f6" },
    parse_failed: { icon: <XCircle size={12} />, label: "解析失败", color: "#ef4444" },
    index_failed: { icon: <XCircle size={12} />, label: "索引失败", color: "#ef4444" },
  };

  const c = config[status] || config.uploaded;
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px]"
      style={{ color: c.color, border: `1px solid ${c.color}30` }}
    >
      {c.icon}
      {c.label}
    </span>
  );
}

// ── Main page ──
export default function MaterialsPage() {
  const [materials, setMaterials] = useState<Material[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");

  // Search state
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);

  // Upload ref
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Load materials ──
  const loadMaterials = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiFetch<{ materials: Material[] }>("/materials");
      setMaterials(data.materials || []);
    } catch (e) {
      console.error("Failed to load materials:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMaterials();
  }, [loadMaterials]);

  // ── Upload ──
  const handleUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate
    const allowed = [".pdf", ".docx", ".pptx", ".md", ".txt"];
    const ext = "." + file.name.split(".").pop()?.toLowerCase();
    if (!allowed.includes(ext)) {
      setUploadStatus(`不支持的文件格式: ${ext}`);
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setUploadStatus("文件过大，最大 50MB");
      return;
    }

    setUploading(true);
    setUploadStatus("上传中...");

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch("/api/materials/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (res.ok) {
        setUploadStatus(
          data.status === "ready"
            ? `✅ ${file.name} 上传并索引完成 (${data.chunk_count} 块)`
            : `✅ ${file.name} 上传成功`
        );
        loadMaterials();
      } else {
        setUploadStatus(`❌ 上传失败: ${data.detail || "未知错误"}`);
      }
    } catch (e) {
      setUploadStatus(`❌ 上传失败: ${e instanceof Error ? e.message : "网络错误"}`);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }, [loadMaterials]);

  // ── Search ──
  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;
    setSearching(true);
    setSearched(true);

    try {
      const data = await apiFetch<{ results: SearchResult[] }>("/materials/search", {
        method: "POST",
        body: JSON.stringify({ query: searchQuery, top_k: 10 }),
      });
      setSearchResults(data.results || []);
    } catch (e) {
      console.error("Search failed:", e);
    } finally {
      setSearching(false);
    }
  }, [searchQuery]);

  // ── Delete ──
  const handleDelete = useCallback(async (materialId: string) => {
    try {
      await apiFetch(`/materials/${materialId}`, { method: "DELETE" });
      loadMaterials();
    } catch (e) {
      console.error("Delete failed:", e);
    }
  }, [loadMaterials]);

  // ── Render ──
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-[var(--color-text)] mb-2">
            📚 学习资料
          </h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            上传你的讲义、笔记、习题集，系统自动解析索引，搜索并生成相关练习题
          </p>
        </div>

        {/* Upload area */}
        <div className="mb-8">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.pptx,.md,.txt"
            onChange={handleUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="w-full border-2 border-dashed border-[var(--color-border)] hover:border-[var(--color-accent)] transition-colors px-6 py-8 flex flex-col items-center justify-center gap-2 disabled:opacity-50"
          >
            {uploading ? (
              <>
                <Loader2 size={24} className="animate-spin text-[var(--color-accent)]" />
                <span className="text-sm text-[var(--color-text-muted)]">
                  {uploadStatus}
                </span>
              </>
            ) : (
              <>
                <Upload size={24} className="text-[var(--color-text-muted)]" />
                <span className="text-sm text-[var(--color-text-secondary)]">
                  点击上传资料 (PDF/Word/PPT/Markdown/TXT, 最大 50MB)
                </span>
                <span className="text-[10px] text-[var(--color-text-muted)]">
                  支持自动解析和语义索引
                </span>
              </>
            )}
          </button>
          {uploadStatus && !uploading && (
            <div className="mt-2 text-xs text-[var(--color-text-secondary)] px-2">
              {uploadStatus}
            </div>
          )}
        </div>

        {/* Search bar */}
        <div className="mb-6 flex gap-2">
          <div className="flex-1 relative">
            <Search
              size={14}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]"
            />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="搜索资料内容... (如: 极限的定义)"
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm pl-9 pr-3 py-2 focus:outline-none focus:border-[var(--color-accent)] transition-colors"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={searching || !searchQuery.trim()}
            className="px-4 py-2 bg-[var(--color-accent)] text-white text-sm disabled:opacity-30 hover:bg-[var(--color-accent-hover)] transition-colors"
          >
            {searching ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              "搜索"
            )}
          </button>
        </div>

        {/* Search results */}
        {searched && (
          <div className="mb-8">
            <h3 className="text-sm font-medium text-[var(--color-text)] mb-3">
              搜索结果 {searchResults.length > 0 && `(${searchResults.length})`}
            </h3>
            {searchResults.length === 0 ? (
              <div className="text-sm text-[var(--color-text-muted)] px-3 py-4 border border-[var(--color-border)]">
                未找到相关内容
              </div>
            ) : (
              <div className="space-y-2">
                {searchResults.map((r) => (
                  <div
                    key={r.chunk_id}
                    className="border border-[var(--color-border)] px-3 py-2.5 hover:bg-[var(--color-surface)] transition-colors"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] text-[var(--color-text-muted)]">
                        {r.source_file}
                        {r.page_number && ` · p${r.page_number}`}
                      </span>
                      <span className="text-[10px] text-[var(--color-accent)]">
                        {(r.similarity * 100).toFixed(0)}%
                      </span>
                      <span className="text-[10px] px-1.5 py-0.5 bg-[var(--color-bg)] text-[var(--color-text-muted)]">
                        {r.chunk_type}
                      </span>
                    </div>
                    <div className="text-xs text-[var(--color-text-secondary)] leading-relaxed line-clamp-3">
                      {r.text}
                    </div>
                    {r.skill_ids && r.skill_ids.length > 0 && (
                      <div className="flex gap-1 mt-1.5">
                        {r.skill_ids.slice(0, 3).map((s) => (
                          <span
                            key={s}
                            className="text-[9px] px-1.5 py-0.5 bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Materials list */}
        <div>
          <h3 className="text-sm font-medium text-[var(--color-text)] mb-3">
            我的资料 ({materials.length})
          </h3>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
            </div>
          ) : materials.length === 0 ? (
            <div className="text-center py-12 border border-[var(--color-border)]">
              <BookOpen size={32} className="mx-auto mb-3 text-[var(--color-text-muted)]" />
              <p className="text-sm text-[var(--color-text-muted)]">
                还没有上传资料
              </p>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">
                上传 PDF 讲义、Word 笔记或 Markdown 文档开始学习
              </p>
            </div>
          ) : (
            <div className="border border-[var(--color-border)]">
              {materials.map((m) => (
                <div
                  key={m.material_id}
                  className="flex items-center gap-3 px-4 py-3 border-b border-[var(--color-border)] last:border-b-0 hover:bg-[var(--color-surface)] transition-colors"
                >
                  {/* File icon */}
                  <div className="flex-shrink-0 w-8 h-8 bg-[var(--color-bg)] border border-[var(--color-border)] flex items-center justify-center">
                    <FileText size={14} className="text-[var(--color-text-muted)]" />
                  </div>

                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="text-sm text-[var(--color-text)] truncate">
                        {m.file_name}
                      </span>
                      <StatusBadge status={m.status} />
                    </div>
                    <div className="flex items-center gap-3 text-[10px] text-[var(--color-text-muted)]">
                      <span>{formatSize(m.file_size)}</span>
                      <span>{m.file_type}</span>
                      {m.chunk_count > 0 && <span>{m.chunk_count} 块</span>}
                      {m.status === "ready" && (
                        <span>{formatDate(m.indexed_at)}</span>
                      )}
                    </div>
                    {m.skills_covered && m.skills_covered.length > 0 && (
                      <div className="flex gap-1 mt-1">
                        {m.skills_covered.slice(0, 4).map((s) => (
                          <span
                            key={s}
                            className="text-[9px] px-1 py-0.5 bg-[var(--color-bg)] text-[var(--color-text-muted)]"
                          >
                            {s}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <button
                    onClick={() => handleDelete(m.material_id)}
                    className="flex-shrink-0 p-1.5 text-[var(--color-text-muted)] hover:text-red-400 transition-colors"
                    title="删除"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

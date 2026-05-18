"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
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
  X,
  Filter,
  ArrowUpDown,
  CheckSquare,
  Square,
  Eye,
  BarChart3,
  Music,
  ImageIcon,
  FileIcon,
} from "lucide-react";

// ── Types ──
interface Material {
  material_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  purpose: string;
  status: string;
  chunk_count: number;
  question_count: number;
  skills_covered: string[];
  created_at: string | null;
  indexed_at: string | null;
  expires_at: string | null;
}

interface Chunk {
  chunk_id: string;
  text: string;
  chunk_type: string;
  skill_ids: string[];
  source_file: string;
  page_number: number | null;
  chunk_index: number;
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

// ── File type helper ──
function getFileCategory(fileType: string): "document" | "audio" | "image" {
  if (["pdf", "docx", "pptx", "markdown", "text"].includes(fileType)) return "document";
  if (["mp3", "wav", "m4a", "ogg", "flac", "aac"].includes(fileType)) return "audio";
  return "image";
}

// ── Status + Purpose badge ──
function MaterialBadge({ status, purpose }: { status: string; purpose: string }) {
  const purposeLabels: Record<string, { icon: string; label: string }> = {
    permanent: { icon: "📚", label: "知识库" },
    session: { icon: "⏳", label: "临时·7天" },
    reference: { icon: "📝", label: "参考" },
  };
  const pl = purposeLabels[purpose] || { icon: "📄", label: purpose };

  const statusIcons: Record<string, { icon: React.ReactNode; color: string }> = {
    ready: { icon: <CheckCircle2 size={12} />, color: "#22c55e" },
    indexing: { icon: <Loader2 size={12} className="animate-spin" />, color: "#f59e0b" },
    stored: { icon: <File size={12} />, color: "#3b82f6" },
    stored_index_failed: { icon: <XCircle size={12} />, color: "#ef4444" },
    uploaded: { icon: <File size={12} />, color: "#3b82f6" },
  };
  const si = statusIcons[status] || statusIcons.stored;

  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="text-[9px] px-1.5 py-0.5 border border-[var(--color-border)] text-[var(--color-text-muted)]">
        {pl.icon} {pl.label}
      </span>
      <span
        className="inline-flex items-center gap-1 text-[10px]"
        style={{ color: si.color }}
      >
        {si.icon}
      </span>
    </span>
  );
}

// ── Filter / Sort types ──
type FilterTab = "all" | "permanent" | "session" | "document" | "audio" | "image";
type SortKey = "newest" | "largest" | "name";

const FILTER_TABS: { key: FilterTab; label: string; icon: string }[] = [
  { key: "all", label: "全部", icon: "📂" },
  { key: "permanent", label: "知识库", icon: "📚" },
  { key: "session", label: "临时", icon: "⏳" },
  { key: "document", label: "文档", icon: "📄" },
  { key: "audio", label: "音频", icon: "🎵" },
  { key: "image", label: "图片", icon: "🖼️" },
];

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "newest", label: "最新上传" },
  { key: "largest", label: "文件最大" },
  { key: "name", label: "名称排序" },
];

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

  // Filter & Sort
  const [activeFilter, setActiveFilter] = useState<FilterTab>("all");
  const [sortBy, setSortBy] = useState<SortKey>("newest");
  const [showSortMenu, setShowSortMenu] = useState(false);

  // Batch select
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [batchDeleting, setBatchDeleting] = useState(false);

  // Preview modal
  const [previewMaterial, setPreviewMaterial] = useState<Material | null>(null);
  const [previewChunks, setPreviewChunks] = useState<Chunk[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);

  // Upload ref
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Promote state
  const [suggestions, setSuggestions] = useState<Array<{
    material_id: string; file_name: string; file_type: string;
    file_size: number; score: number; reasons: string[];
  }>>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [promoting, setPromoting] = useState<string | null>(null);

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

  // ── Stats ──
  const stats = useMemo(() => {
    const total = materials.length;
    const permanent = materials.filter(m => m.purpose === "permanent").length;
    const session = materials.filter(m => m.purpose === "session").length;
    const docs = materials.filter(m => getFileCategory(m.file_type) === "document").length;
    const audio = materials.filter(m => getFileCategory(m.file_type) === "audio").length;
    const images = materials.filter(m => getFileCategory(m.file_type) === "image").length;
    const totalSize = materials.reduce((sum, m) => sum + (m.file_size || 0), 0);
    const totalChunks = materials.reduce((sum, m) => sum + (m.chunk_count || 0), 0);
    return { total, permanent, session, docs, audio, images, totalSize, totalChunks };
  }, [materials]);

  // ── Filtered + Sorted ──
  const filteredMaterials = useMemo(() => {
    let result = [...materials];

    // Apply filter
    switch (activeFilter) {
      case "permanent":
        result = result.filter(m => m.purpose === "permanent");
        break;
      case "session":
        result = result.filter(m => m.purpose === "session");
        break;
      case "document":
        result = result.filter(m => getFileCategory(m.file_type) === "document");
        break;
      case "audio":
        result = result.filter(m => getFileCategory(m.file_type) === "audio");
        break;
      case "image":
        result = result.filter(m => getFileCategory(m.file_type) === "image");
        break;
    }

    // Apply sort
    switch (sortBy) {
      case "newest":
        result.sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime());
        break;
      case "largest":
        result.sort((a, b) => (b.file_size || 0) - (a.file_size || 0));
        break;
      case "name":
        result.sort((a, b) => a.file_name.localeCompare(b.file_name, "zh-CN"));
        break;
    }

    return result;
  }, [materials, activeFilter, sortBy]);

  // ── Upload ──
  const handleUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const allowed = [".pdf", ".docx", ".pptx", ".md", ".txt", ".mp3", ".wav", ".m4a", ".jpg", ".jpeg", ".png", ".webp"];
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
        setUploadStatus(`✅ ${file.name} 上传成功`);
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
      setSelectedIds(prev => { const s = new Set(prev); s.delete(materialId); return s; });
      loadMaterials();
    } catch (e) {
      console.error("Delete failed:", e);
    }
  }, [loadMaterials]);

  // ── Batch delete ──
  const handleBatchDelete = useCallback(async () => {
    if (selectedIds.size === 0) return;
    setBatchDeleting(true);
    try {
      for (const id of Array.from(selectedIds)) {
        await apiFetch(`/materials/${id}`, { method: "DELETE" });
      }
      setSelectedIds(new Set());
      loadMaterials();
    } catch (e) {
      console.error("Batch delete failed:", e);
    } finally {
      setBatchDeleting(false);
    }
  }, [selectedIds, loadMaterials]);

  // ── Select toggle ──
  const toggleSelect = useCallback((id: string) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    if (selectedIds.size === filteredMaterials.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(filteredMaterials.map(m => m.material_id)));
    }
  }, [selectedIds, filteredMaterials]);

  // ── Preview ──
  const handlePreview = useCallback(async (material: Material) => {
    if (getFileCategory(material.file_type) !== "document") return;
    setPreviewMaterial(material);
    setPreviewLoading(true);
    try {
      const data = await apiFetch<{ chunks: Chunk[] }>(`/materials/${material.material_id}/chunks`);
      setPreviewChunks(data.chunks || []);
    } catch (e) {
      console.error("Preview failed:", e);
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  // ── Promote ──
  const loadSuggestions = useCallback(async () => {
    setSuggestionsLoading(true);
    try {
      const data = await apiFetch<{ suggestions: typeof suggestions }>("/materials/promote-suggestions");
      setSuggestions(data.suggestions || []);
    } catch (e) {
      console.error("Suggestions failed:", e);
    } finally {
      setSuggestionsLoading(false);
    }
  }, []);

  const handlePromote = useCallback(async (materialId: string) => {
    setPromoting(materialId);
    try {
      await apiFetch(`/materials/${materialId}/promote`, { method: "POST" });
      setUploadStatus("✅ 已转为知识库资料");
      loadMaterials();
      loadSuggestions();
    } catch (e) {
      setUploadStatus(`❌ 转换失败: ${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setPromoting(null);
    }
  }, [loadMaterials, loadSuggestions]);

  // ── Render ──
  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-[var(--color-text)] mb-2">
            📚 学习资料
          </h1>
          <p className="text-sm text-[var(--color-text-muted)]">
            上传讲义、笔记、习题集，AI 自动解析索引，支持搜索和生成练习
          </p>
        </div>

        {/* Stats bar */}
        <div className="grid grid-cols-4 gap-2 mb-6">
          <div className="border border-[var(--color-border)] px-3 py-2 text-center">
            <div className="text-lg font-bold text-[var(--color-text)]">{stats.total}</div>
            <div className="text-[9px] text-[var(--color-text-muted)]">文件总数</div>
          </div>
          <div className="border border-[var(--color-border)] px-3 py-2 text-center">
            <div className="text-lg font-bold text-[var(--color-accent)]">{stats.permanent}</div>
            <div className="text-[9px] text-[var(--color-text-muted)]">知识库</div>
          </div>
          <div className="border border-[var(--color-border)] px-3 py-2 text-center">
            <div className="text-lg font-bold text-[var(--color-text)]">{stats.totalChunks}</div>
            <div className="text-[9px] text-[var(--color-text-muted)]">索引块</div>
          </div>
          <div className="border border-[var(--color-border)] px-3 py-2 text-center">
            <div className="text-lg font-bold text-[var(--color-text-muted)]">{formatSize(stats.totalSize)}</div>
            <div className="text-[9px] text-[var(--color-text-muted)]">总大小</div>
          </div>
        </div>

        {/* Upload area */}
        <div className="mb-6">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.pptx,.md,.txt,.mp3,.wav,.m4a,.jpg,.jpeg,.png,.webp"
            onChange={handleUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="w-full border-2 border-dashed border-[var(--color-border)] hover:border-[var(--color-accent)] transition-colors px-6 py-5 flex flex-col items-center justify-center gap-1.5 disabled:opacity-50"
          >
            {uploading ? (
              <>
                <Loader2 size={22} className="animate-spin text-[var(--color-accent)]" />
                <span className="text-xs text-[var(--color-text-muted)]">{uploadStatus}</span>
              </>
            ) : (
              <>
                <Upload size={22} className="text-[var(--color-text-muted)]" />
                <span className="text-xs text-[var(--color-text-secondary)]">
                  上传文件 (PDF/Word/PPT/MD/TXT · 音频 · 图片, ≤50MB)
                </span>
                <span className="text-[10px] text-[var(--color-text-muted)]">
                  临时资料7天自动清理 · 点「转为知识库」建立索引
                </span>
              </>
            )}
          </button>
          {uploadStatus && !uploading && (
            <div className="mt-2 text-xs text-[var(--color-text-secondary)] px-2">{uploadStatus}</div>
          )}
        </div>

        {/* Smart promotion suggestions */}
        <div className="mb-6">
          <button
            onClick={loadSuggestions}
            disabled={suggestionsLoading}
            className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors flex items-center gap-1 mb-2"
          >
            {suggestionsLoading ? <Loader2 size={12} className="animate-spin" /> : "💡"}
            智能推荐可转为知识库的资料
          </button>
          {suggestions.length > 0 && (
            <div className="space-y-1.5">
              {suggestions.map((s) => (
                <div key={s.material_id} className="flex items-center gap-2 px-3 py-2 border border-[var(--color-border)] bg-[var(--color-surface)]">
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-[var(--color-text)] truncate">{s.file_name}</div>
                    <div className="flex items-center gap-2 text-[9px] text-[var(--color-text-muted)]">
                      <span>{formatSize(s.file_size)}</span>
                      <span>{s.file_type}</span>
                      <span className="text-[var(--color-accent)]">评分:{s.score}</span>
                      {s.reasons.map((r, i) => <span key={i} className="px-1 bg-[var(--color-bg)]">{r}</span>)}
                    </div>
                  </div>
                  <button
                    onClick={() => handlePromote(s.material_id)}
                    disabled={promoting === s.material_id}
                    className="flex-shrink-0 px-2 py-1 text-[10px] bg-[var(--color-accent)] text-white hover:opacity-80 transition-opacity disabled:opacity-30"
                  >
                    {promoting === s.material_id ? <Loader2 size={12} className="animate-spin" /> : "转为知识库"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Search bar */}
        <div className="mb-4 flex gap-2">
          <div className="flex-1 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="语义搜索资料内容... (如: 泰勒展开)"
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm pl-9 pr-3 py-2 focus:outline-none focus:border-[var(--color-accent)] transition-colors"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={searching || !searchQuery.trim()}
            className="px-4 py-2 bg-[var(--color-accent)] text-white text-sm disabled:opacity-30 hover:opacity-80 transition-opacity"
          >
            {searching ? <Loader2 size={14} className="animate-spin" /> : "搜索"}
          </button>
        </div>

        {/* Search results */}
        {searched && (
          <div className="mb-6">
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
                  <div key={r.chunk_id} className="border border-[var(--color-border)] px-3 py-2.5 hover:bg-[var(--color-surface)] transition-colors">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-[10px] text-[var(--color-text-muted)]">
                        {r.source_file}{r.page_number && ` · p${r.page_number}`}
                      </span>
                      <span className="text-[10px] text-[var(--color-accent)]">{(r.similarity * 100).toFixed(0)}%</span>
                      <span className="text-[10px] px-1.5 py-0.5 bg-[var(--color-bg)] text-[var(--color-text-muted)]">{r.chunk_type}</span>
                    </div>
                    <div className="text-xs text-[var(--color-text-secondary)] leading-relaxed line-clamp-3">{r.text}</div>
                    {r.skill_ids && r.skill_ids.length > 0 && (
                      <div className="flex gap-1 mt-1.5">
                        {r.skill_ids.slice(0, 3).map((s) => (
                          <span key={s} className="text-[9px] px-1.5 py-0.5 bg-[var(--color-accent)]/10 text-[var(--color-accent)]">{s}</span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Toolbar: Filter + Sort + Batch */}
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          {/* Filter tabs */}
          <div className="flex items-center gap-1 flex-1 flex-wrap">
            {FILTER_TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => { setActiveFilter(tab.key); setSelectedIds(new Set()); }}
                className={`text-[11px] px-2.5 py-1 border transition-colors ${
                  activeFilter === tab.key
                    ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                    : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-text-muted)]"
                }`}
              >
                {tab.icon} {tab.label}
              </button>
            ))}
          </div>

          {/* Sort dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowSortMenu(!showSortMenu)}
              className="flex items-center gap-1 text-[11px] px-2.5 py-1 border border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-text-muted)] transition-colors"
            >
              <ArrowUpDown size={12} />
              {SORT_OPTIONS.find(o => o.key === sortBy)?.label}
            </button>
            {showSortMenu && (
              <div className="absolute right-0 top-full mt-1 border border-[var(--color-border)] bg-[var(--color-bg)] shadow-lg z-20 min-w-[120px]">
                {SORT_OPTIONS.map((opt) => (
                  <button
                    key={opt.key}
                    onClick={() => { setSortBy(opt.key); setShowSortMenu(false); }}
                    className={`block w-full text-left text-[11px] px-3 py-1.5 hover:bg-[var(--color-surface)] transition-colors ${
                      sortBy === opt.key ? "text-[var(--color-accent)]" : "text-[var(--color-text-secondary)]"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Batch action bar */}
        {selectedIds.size > 0 && (
          <div className="mb-3 px-3 py-2 border border-[var(--color-accent)] bg-[var(--color-accent)]/5 flex items-center gap-3">
            <span className="text-xs text-[var(--color-text)]">已选 {selectedIds.size} 项</span>
            <button
              onClick={handleBatchDelete}
              disabled={batchDeleting}
              className="flex items-center gap-1 text-[11px] px-2 py-1 border border-red-400 text-red-400 hover:bg-red-50 transition-colors disabled:opacity-30"
            >
              {batchDeleting ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
              批量删除
            </button>
            <button
              onClick={() => setSelectedIds(new Set())}
              className="text-[11px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
            >
              取消选择
            </button>
          </div>
        )}

        {/* Materials list */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-medium text-[var(--color-text)]">
              资料列表 ({filteredMaterials.length})
            </h3>
            {filteredMaterials.length > 0 && (
              <button onClick={toggleSelectAll} className="text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors flex items-center gap-1">
                {selectedIds.size === filteredMaterials.length ? <CheckSquare size={12} /> : <Square size={12} />}
                {selectedIds.size === filteredMaterials.length ? "取消全选" : "全选"}
              </button>
            )}
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
            </div>
          ) : filteredMaterials.length === 0 ? (
            <div className="text-center py-12 border border-[var(--color-border)]">
              <BookOpen size={32} className="mx-auto mb-3 text-[var(--color-text-muted)]" />
              <p className="text-sm text-[var(--color-text-muted)]">还没有资料</p>
              <p className="text-xs text-[var(--color-text-muted)] mt-1">
                上传 PDF 讲义、Word 笔记或其它文档开始学习
              </p>
            </div>
          ) : (
            <div className="border border-[var(--color-border)]">
              {filteredMaterials.map((m) => {
                const cat = getFileCategory(m.file_type);
                const FileIconComp = cat === "audio" ? Music : cat === "image" ? ImageIcon : FileText;
                return (
                  <div
                    key={m.material_id}
                    className="flex items-center gap-3 px-4 py-3 border-b border-[var(--color-border)] last:border-b-0 hover:bg-[var(--color-surface)] transition-colors"
                  >
                    {/* Checkbox */}
                    <button onClick={() => toggleSelect(m.material_id)} className="flex-shrink-0 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors">
                      {selectedIds.has(m.material_id) ? <CheckSquare size={14} /> : <Square size={14} />}
                    </button>

                    {/* File icon */}
                    <div className="flex-shrink-0 w-8 h-8 bg-[var(--color-bg)] border border-[var(--color-border)] flex items-center justify-center">
                      <FileIconComp size={14} className="text-[var(--color-text-muted)]" />
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-0.5">
                        <span className="text-sm text-[var(--color-text)] truncate">{m.file_name}</span>
                        <MaterialBadge status={m.status} purpose={m.purpose || "session"} />
                      </div>
                      <div className="flex items-center gap-3 text-[10px] text-[var(--color-text-muted)]">
                        <span>{formatSize(m.file_size)}</span>
                        <span>{m.file_type}</span>
                        {m.chunk_count > 0 && <span>{m.chunk_count} 块</span>}
                        {m.status === "ready" && <span>{formatDate(m.indexed_at)}</span>}
                        {m.expires_at && (
                          <span className="text-[var(--color-warning)]">过期: {formatDate(m.expires_at)}</span>
                        )}
                      </div>
                      {m.skills_covered && m.skills_covered.length > 0 && (
                        <div className="flex gap-1 mt-1">
                          {m.skills_covered.slice(0, 4).map((s) => (
                            <span key={s} className="text-[9px] px-1 py-0.5 bg-[var(--color-bg)] text-[var(--color-text-muted)]">{s}</span>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1">
                      {/* Preview button (documents only) */}
                      {cat === "document" && m.status === "ready" && (
                        <button
                          onClick={() => handlePreview(m)}
                          className="flex-shrink-0 p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors"
                          title="预览内容"
                        >
                          <Eye size={14} />
                        </button>
                      )}
                      {m.purpose === "session" && (
                        <button
                          onClick={() => handlePromote(m.material_id)}
                          disabled={promoting === m.material_id}
                          className="flex-shrink-0 px-2 py-1 text-[10px] border border-[var(--color-accent)] text-[var(--color-accent)] hover:bg-[var(--color-accent)]/10 transition-colors disabled:opacity-30"
                          title="转为知识库资料"
                        >
                          {promoting === m.material_id ? <Loader2 size={12} className="animate-spin" /> : "转为知识库"}
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(m.material_id)}
                        className="flex-shrink-0 p-1.5 text-[var(--color-text-muted)] hover:text-red-400 transition-colors"
                        title="删除"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* ── Preview Modal ── */}
      {previewMaterial && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setPreviewMaterial(null)}>
          <div
            className="bg-[var(--color-bg)] border border-[var(--color-border)] w-full max-w-2xl max-h-[80vh] mx-4 flex flex-col shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
              <div className="flex items-center gap-2 min-w-0">
                <FileText size={16} className="text-[var(--color-text-muted)] flex-shrink-0" />
                <span className="text-sm font-medium text-[var(--color-text)] truncate">{previewMaterial.file_name}</span>
                <span className="text-[10px] text-[var(--color-text-muted)] flex-shrink-0">
                  {previewMaterial.chunk_count} 块
                </span>
              </div>
              <button onClick={() => setPreviewMaterial(null)} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">
                <X size={16} />
              </button>
            </div>

            {/* Modal body */}
            <div className="flex-1 overflow-y-auto px-4 py-3">
              {previewLoading ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" />
                </div>
              ) : previewChunks.length === 0 ? (
                <div className="text-sm text-[var(--color-text-muted)] text-center py-8">
                  暂无分块内容
                </div>
              ) : (
                <div className="space-y-3">
                  {previewChunks.map((chunk) => (
                    <div key={chunk.chunk_id} className="border border-[var(--color-border)] px-3 py-2.5">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="text-[10px] text-[var(--color-text-muted)]">
                          第 {chunk.chunk_index + 1} 块
                          {chunk.page_number && ` · p${chunk.page_number}`}
                        </span>
                        <span className="text-[10px] px-1.5 py-0.5 bg-[var(--color-bg)] text-[var(--color-text-muted)]">
                          {chunk.chunk_type}
                        </span>
                      </div>
                      <div className="text-xs text-[var(--color-text-secondary)] leading-relaxed whitespace-pre-wrap line-clamp-6">
                        {chunk.text}
                      </div>
                      {chunk.skill_ids && chunk.skill_ids.length > 0 && (
                        <div className="flex gap-1 mt-1.5">
                          {chunk.skill_ids.map((s) => (
                            <span key={s} className="text-[9px] px-1.5 py-0.5 bg-[var(--color-accent)]/10 text-[var(--color-accent)]">{s}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

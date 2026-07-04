"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { Upload, FileText, Image, Search, Trash2, Loader2,
  Library, ExternalLink, File, CheckCircle, AlertCircle, Play,
  Download, Pencil, FolderPlus, Folder, FolderOpen, Tag, X,
  Check, ChevronRight, Home, RefreshCw, Eye, Grid, List,
  HardDrive, Clock, Star, BarChart3, ZoomIn, ZoomOut, MoreVertical,
} from "lucide-react";
import { authedFetch, API_BASE } from "@/lib/api/api";
import { getAccessToken } from "@/lib/api/auth";
import FilePreview, { getExt } from "@/components/ui/FilePreview";

// ── 类型 ──

interface FileItem {
  material_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  purpose: string;
  status: string;
  chunk_count: number;
  toc_count: number;
  level: string;
  parent_id: string;
  tags: string[];
  is_folder: boolean;
  is_deleted: boolean;
  deleted_at: string | null;
  created_at: string;
  indexed_at: string | null;
}

interface FolderItem {
  material_id: string;
  file_name: string;
  created_at: string;
  child_count: number;
}

interface BankItem {
  id: string;
  name: string;
  description: string;
  question_count: number;
  auto_created: boolean;
  ref_node_label?: string;
}

interface FileStats {
  total_files: number;
  total_size: number;
  total_size_formatted: string;
  by_type: { file_type: string; count: number; total_size: number }[];
  by_purpose: { purpose: string; count: number }[];
  folder_count: number;
  trash_count: number;
  recent_files: { material_id: string; file_name: string; file_type: string; file_size: number; created_at: string }[];
}

type Tab = "files" | "banks" | "stats" | "trash";
type TypeFilter = "all" | "pdf" | "docx" | "image" | "document";
type ViewMode = "list" | "grid";

const PAGE_SIZE = 20;

// ── 格式化工具 ──

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

function formatDate(d: string): string {
  return d?.slice(0, 16).replace("T", " ") || "";
}

function getFileIcon(ext: string) {
  if (["jpg", "jpeg", "png", "gif", "webp", "bmp"].includes(ext)) return <Image size={14} className="text-blue-500" />;
  if (ext === "pdf") return <FileText size={14} className="text-red-500" />;
  if (["docx", "pptx", "xlsx", "csv"].includes(ext)) return <FileText size={14} className="text-[var(--color-accent)]" />;
  if (["mp3", "wav", "m4a", "ogg"].includes(ext)) return <File size={14} className="text-purple-500" />;
  return <File size={14} className="text-[var(--color-text-muted)]" />;
}

function getTagColor(tag: string): string {
  const colors = [
    "bg-blue-500/10 text-blue-500",
    "bg-green-500/10 text-green-500",
    "bg-purple-500/10 text-purple-500",
    "bg-amber-500/10 text-amber-500",
    "bg-pink-500/10 text-pink-500",
    "bg-cyan-500/10 text-cyan-500",
    "bg-orange-500/10 text-orange-500",
    "bg-indigo-500/10 text-indigo-500",
  ];
  let hash = 0;
  for (let i = 0; i < tag.length; i++) hash = tag.charCodeAt(i) + ((hash << 5) - hash);
  return colors[Math.abs(hash) % colors.length];
}

// ── 组件 ──

export default function ResourcesPage() {
  const [tab, setTab] = useState<Tab>("files");
  const [files, setFiles] = useState<FileItem[]>([]);
  const [folders, setFolders] = useState<FolderItem[]>([]);
  const [banks, setBanks] = useState<BankItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [search, setSearch] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [editFile, setEditFile] = useState<FileItem | null>(null);
  const [editName, setEditName] = useState("");
  const [editTags, setEditTags] = useState<string[]>([]);
  const [editTagInput, setEditTagInput] = useState("");
  const [editLevel, setEditLevel] = useState("dir");
  const [editParentId, setEditParentId] = useState("");
  const [saving, setSaving] = useState(false);
  const [deletingBank, setDeletingBank] = useState<string | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [currentFolder, setCurrentFolder] = useState<string>("");
  const [folderBreadcrumbs, setFolderBreadcrumbs] = useState<{ id: string; name: string }[]>([]);
  const [showCreateFolder, setShowCreateFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState("");
  const [allTags, setAllTags] = useState<string[]>([]);
  const [selectedTag, setSelectedTag] = useState<string>("");
  const [viewMode, setViewMode] = useState<ViewMode>("list");
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dropZoneRef = useRef<HTMLDivElement>(null);
  const [previewFile, setPreviewFile] = useState<FileItem | null>(null);
  const [zoom, setZoom] = useState(1);
  const [actionMenu, setActionMenu] = useState<string | null>(null);
  const [stats, setStats] = useState<FileStats | null>(null);

  // 切换预览文件时重置缩放
  useEffect(() => { setZoom(1); }, [previewFile]);
  const previewableFiles = React.useMemo(() => files.filter(f => !f.is_folder), [files]);

  // 预览弹窗键盘导航：← → 切换文件，Esc 关闭
  useEffect(() => {
    if (!previewFile) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") { setPreviewFile(null); return; }
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        const idx = previewableFiles.findIndex(f => f.material_id === previewFile.material_id);
        if (idx === -1) return;
        const next = e.key === "ArrowRight"
          ? Math.min(idx + 1, previewableFiles.length - 1)
          : Math.max(idx - 1, 0);
        if (next !== idx) setPreviewFile(previewableFiles[next]);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [previewFile, previewableFiles]);
  const [searchInput, setSearchInput] = useState("");
  const [trashFiles, setTrashFiles] = useState<FileItem[]>([]);

  useEffect(() => {
    const t = setTimeout(() => setSearch(searchInput), 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  const fetchFiles = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(PAGE_SIZE),
        include_folders: tab === "files" ? "true" : "false",
      });
      if (typeFilter !== "all") params.set("type", typeFilter);
      if (search) params.set("search", search);
      if (selectedTag) params.set("tag", selectedTag);
      if (tab === "files") params.set("parent_id", currentFolder);
      const res = await authedFetch(`/api/files?${params}`);
      const data = await res.json();
      setFiles(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      console.error("Failed to load files:", e);
    } finally {
      setLoading(false);
    }
  }, [typeFilter, search, page, selectedTag, currentFolder, tab]);

  const fetchFolders = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (currentFolder) params.set("parent_id", currentFolder);
      const res = await authedFetch(`/api/files/folders?${params}`);
      const data = await res.json();
      setFolders(data.folders || []);
    } catch (e) {
      console.error("Failed to load folders:", e);
    }
  }, [currentFolder]);

  const fetchTags = useCallback(async () => {
    try {
      const res = await authedFetch(`/api/files/tags`);
      const data = await res.json();
      setAllTags(data.tags || []);
    } catch (e) {
      console.error("Failed to load tags:", e);
    }
  }, []);

  const fetchStats = useCallback(async () => {
    try {
      const res = await authedFetch(`/api/files/stats`);
      const data = await res.json();
      setStats(data);
    } catch (e) {
      console.error("Failed to load stats:", e);
    }
  }, []);

  const fetchBanks = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authedFetch(`/api/practice/banks`);
      const data = await res.json();
      setBanks(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error("Failed to load banks:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTrash = useCallback(async () => {
    setLoading(true);
    try {
      const res = await authedFetch(`/api/files/trash`);
      const data = await res.json();
      setTrashFiles(data.files || []);
    } catch (e) {
      console.error("Failed to load trash:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab === "files") { fetchFiles(); fetchFolders(); fetchTags(); }
    else if (tab === "banks") fetchBanks();
    else if (tab === "stats") fetchStats();
    else if (tab === "trash") fetchTrash();
  }, [tab, fetchFiles, fetchBanks, fetchStats, fetchFolders, fetchTags, fetchTrash]);

  const handleRestore = async (id: string) => {
    try { await authedFetch(`/api/files/${id}/restore`, { method: "POST" }); fetchTrash(); }
    catch (e) { console.error("Restore failed:", e); }
  };

  const handlePermanentDelete = async (id: string) => {
    if (!confirm("确定永久删除？此操作不可恢复！")) return;
    try { await authedFetch(`/api/files/${id}/permanent`, { method: "DELETE" }); fetchTrash(); }
    catch (e) { console.error("Permanent delete failed:", e); }
  };

  const handleEmptyTrash = async () => {
    if (!confirm("确定清空回收站？所有文件将永久删除！")) return;
    try { await authedFetch(`/api/files/trash/empty`, { method: "POST" }); fetchTrash(); }
    catch (e) { console.error("Empty trash failed:", e); }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await uploadFile(file);
    if (e.target) e.target.value = "";
  };

  const uploadFile = async (file: File) => {
    setUploading(true);
    setUploadProgress(0);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("purpose", "library");
      if (currentFolder) formData.append("parent_id", currentFolder);
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${API_BASE}/api/files/upload`);
      const token = getAccessToken();
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) setUploadProgress(Math.round((event.loaded / event.total) * 100));
      };
      xhr.onload = () => {
        setUploading(false);
        setUploadProgress(0);
        if (xhr.status >= 200 && xhr.status < 300) { fetchFiles(); fetchFolders(); }
        else console.error("Upload failed:", xhr.statusText);
      };
      xhr.onerror = () => { setUploading(false); setUploadProgress(0); console.error("Upload error"); };
      xhr.send(formData);
    } catch (e) {
      setUploading(false);
      setUploadProgress(0);
      console.error("Upload failed:", e);
    }
  };

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setIsDragOver(true); };
  const handleDragLeave = (e: React.DragEvent) => { e.preventDefault(); setIsDragOver(false); };
  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    for (const file of droppedFiles) await uploadFile(file);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确定删除该文件？文件将移入回收站")) return;
    setDeleting(id);
    try { await authedFetch(`/api/files/${id}/trash`, { method: "POST" }); fetchFiles(); fetchFolders(); }
    catch (e) { console.error("Delete failed:", e); }
    finally { setDeleting(null); }
  };

  const openEdit = (f: FileItem) => {
    setEditFile(f);
    setEditName(f.file_name);
    setEditTags(f.tags || []);
    setEditLevel(f.level || "dir");
    setEditParentId(f.parent_id || "");
    setEditTagInput("");
  };

  const addTag = () => {
    const tag = editTagInput.trim();
    if (tag && !editTags.includes(tag)) { setEditTags([...editTags, tag]); setEditTagInput(""); }
  };

  const removeTag = (tag: string) => { setEditTags(editTags.filter(t => t !== tag)); };

  const handleSaveEdit = async () => {
    if (!editFile || !editName.trim()) return;
    setSaving(true);
    try {
      await authedFetch(`/api/files/${editFile.material_id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_name: editName.trim(), level: editLevel, parent_id: editParentId }),
      });
      await authedFetch(`/api/files/${editFile.material_id}/tags`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tags: editTags }),
      });
      setEditFile(null);
      fetchFiles();
      fetchTags();
    } catch (e) { console.error("Save failed:", e); }
    finally { setSaving(false); }
  };

  const handleDownload = async (f: FileItem) => {
    try {
      const res = await authedFetch(`/api/files/${f.material_id}/download`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = f.file_name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (e) {
      console.error("Download failed:", e);
    }
  };

  const handlePreview = (f: FileItem) => {
    setPreviewFile(f);
  };

  const handleDeleteBank = async (id: string) => {
    if (!confirm("确定删除该题库？")) return;
    setDeletingBank(id);
    try { await authedFetch(`/api/practice/banks/${id}`, { method: "DELETE" }); fetchBanks(); }
    catch (e) { console.error("Delete bank failed:", e); }
    finally { setDeletingBank(null); }
  };

  const toggleSelect = (id: string) => {
    const newSet = new Set(selectedFiles);
    if (newSet.has(id)) newSet.delete(id); else newSet.add(id);
    setSelectedFiles(newSet);
  };

  const selectAll = () => {
    if (selectedFiles.size === files.length) setSelectedFiles(new Set());
    else setSelectedFiles(new Set(files.map(f => f.material_id)));
  };

  const handleBatchAction = async (action: string) => {
    if (selectedFiles.size === 0) return;
    try {
      await authedFetch(`/api/files/batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ material_ids: Array.from(selectedFiles), action, target_folder_id: action === "move" ? currentFolder : undefined }),
      });
      setSelectedFiles(new Set());
      fetchFiles();
    } catch (e) { console.error("Batch action failed:", e); }
  };

  const handleCreateFolder = async () => {
    if (!newFolderName.trim()) return;
    try {
      await authedFetch(`/api/files/folder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newFolderName.trim(), parent_id: currentFolder || undefined }),
      });
      setNewFolderName("");
      setShowCreateFolder(false);
      fetchFolders();
    } catch (e) { console.error("Create folder failed:", e); }
  };

  const navigateToFolder = (folderId: string, folderName: string) => {
    setCurrentFolder(folderId);
    setFolderBreadcrumbs([...folderBreadcrumbs, { id: folderId, name: folderName }]);
    setPage(1);
  };

  const navigateToBreadcrumb = (index: number) => {
    if (index < 0) { setCurrentFolder(""); setFolderBreadcrumbs([]); }
    else {
      const bc = folderBreadcrumbs[index];
      setCurrentFolder(bc.id);
      setFolderBreadcrumbs(folderBreadcrumbs.slice(0, index + 1));
    }
    setPage(1);
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  // 关闭 actionMenu 的 Escape 键
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") setActionMenu(null); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, []);

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        {/* ── 页面标题 ── */}
        <div className="mb-6">
          <div className="flex items-center gap-3 mb-1">
            <div className="w-10 h-10 rounded-xl bg-violet-500/10 flex items-center justify-center">
              <Library size={20} className="text-violet-500" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-[var(--color-text)]">我的资源</h1>
              <p className="text-[12px] text-[var(--color-text-muted)] mt-0.5">管理学习文件、题库与知识资料</p>
            </div>
          </div>
        </div>

        {/* ── Tab 栏 ── */}
        <div className="flex items-center gap-1 mb-6 border-b border-[var(--color-border)]/50 overflow-x-auto scrollbar-none">
          {[
            { id: "files" as Tab, label: "文件资料", icon: <FolderOpen size={16} /> },
            { id: "banks" as Tab, label: "题库", icon: <Library size={16} /> },
            { id: "stats" as Tab, label: "统计", icon: <BarChart3 size={16} /> },
            { id: "trash" as Tab, label: "回收站", icon: <Trash2 size={16} /> },
          ].map((t) => (
            <button key={t.id} onClick={() => { setTab(t.id); setPage(1); }}
              className={`relative flex items-center gap-1.5 px-4 py-2.5 text-[13px] font-medium transition-colors whitespace-nowrap shrink-0 ${
                tab === t.id
                  ? "text-[var(--color-accent)]"
                  : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
              }`}>
              {t.icon}
              {t.label}
              {tab === t.id && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--color-accent)] rounded-full" />}
              {t.id === "trash" && stats?.trash_count ? (
                <span className="ml-1 text-[9px] px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-500">{stats.trash_count}</span>
              ) : null}
            </button>
          ))}
        </div>

        {/* ════════════════════════════════════
            TAB: 文件资料
            ════════════════════════════════════ */}
        {tab === "files" && (
          <>
            {/* ── 筛选 / 工具栏 ── */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-4">
              {/* 移动端：搜索框占满 */}
              <div className="relative w-full sm:w-auto sm:order-2 sm:ml-auto">
                <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
                <input value={searchInput} onChange={(e) => { setSearchInput(e.target.value); setPage(1); }}
                  placeholder="搜索文件..."
                  className="w-full sm:w-44 pl-8 pr-3 py-2 text-[12px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)] transition-colors" />
              </div>
              {/* 类型过滤：横向滚动 pills ／ 桌面行内 */}
              <div className="flex items-center gap-1.5 overflow-x-auto scrollbar-none w-full sm:w-auto order-1">
                {([
                  { value: "all", label: "全部" },
                  { value: "pdf", label: "PDF" },
                  { value: "docx", label: "文档" },
                  { value: "image", label: "图片" },
                  { value: "document", label: "笔记" },
                ] as { value: TypeFilter; label: string }[]).map((f) => (
                  <button key={f.value} onClick={() => { setTypeFilter(f.value); setPage(1); }}
                    className={`shrink-0 px-3 py-1.5 rounded-lg text-[11px] font-medium border transition-all ${
                      typeFilter === f.value
                        ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                        : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-accent)]/30 hover:text-[var(--color-text)]"
                    }`}>
                    {f.label}
                  </button>
                ))}
                {/* 标签选择 */}
                {allTags.length > 0 && (
                  <div className="flex items-center gap-1 shrink-0 pl-1.5 border-l border-[var(--color-border)]/50 ml-1.5">
                    <Tag size={12} className="text-[var(--color-text-muted)]" />
                    <select value={selectedTag} onChange={(e) => { setSelectedTag(e.target.value); setPage(1); }}
                      className="text-[11px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1.5 focus:outline-none focus:border-[var(--color-accent)]">
                      <option value="">全部标签</option>
                      {allTags.map(tag => <option key={tag} value={tag}>{tag}</option>)}
                    </select>
                  </div>
                )}
              </div>
              {/* 操作按钮组 */}
              <div className="flex items-center gap-2 w-full sm:w-auto order-3">
                {/* 视图切换 */}
                <div className="flex items-center gap-0.5 border border-[var(--color-border)] rounded-lg p-0.5">
                  <button onClick={() => setViewMode("list")}
                    className={`p-1.5 rounded-md transition-colors ${viewMode === "list" ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"}`}
                    title="列表视图"><List size={14} /></button>
                  <button onClick={() => setViewMode("grid")}
                    className={`p-1.5 rounded-md transition-colors ${viewMode === "grid" ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"}`}
                    title="网格视图"><Grid size={14} /></button>
                </div>
                <button onClick={() => setShowCreateFolder(!showCreateFolder)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium border border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-all">
                  <FolderPlus size={13} /> 新建文件夹
                </button>
                <label className={`flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-[12px] font-medium bg-[var(--color-accent)] text-white hover:opacity-90 cursor-pointer transition-all ${
                  uploading ? "opacity-50 pointer-events-none" : ""
                }`}>
                  {uploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
                  {uploading ? `${uploadProgress}%` : "上传文件"}
                  <input type="file" ref={fileInputRef} className="hidden" onChange={handleUpload} disabled={uploading}
                    accept=".pdf,.docx,.pptx,.xlsx,.md,.txt,.jpg,.jpeg,.png,.gif,.webp,.mp3,.wav" />
                </label>
              </div>
            </div>

            {/* ── 上传进度 ── */}
            {uploading && (
              <div className="mb-4 p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] shadow-sm">
                <div className="flex items-center gap-2 mb-1.5">
                  <Loader2 size={13} className="animate-spin text-[var(--color-accent)]" />
                  <span className="text-[12px] text-[var(--color-text-muted)]">上传中...</span>
                  <span className="text-[12px] font-medium text-[var(--color-accent)] ml-auto">{uploadProgress}%</span>
                </div>
                <div className="w-full h-2 bg-[var(--color-border)] rounded-full overflow-hidden">
                  <div className="h-full bg-[var(--color-accent)] rounded-full transition-all duration-300" style={{ width: `${uploadProgress}%` }} />
                </div>
              </div>
            )}

            {/* ── 新建文件夹输入 ── */}
            {showCreateFolder && (
              <div className="mb-4 p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)] flex items-center gap-2 shadow-sm">
                <Folder size={16} className="text-amber-500 shrink-0" />
                <input value={newFolderName} onChange={(e) => setNewFolderName(e.target.value)} placeholder="文件夹名称"
                  className="flex-1 text-[13px] px-2.5 py-1.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)]"
                  onKeyDown={(e) => e.key === "Enter" && handleCreateFolder()} autoFocus />
                <button onClick={handleCreateFolder} className="px-3 py-1.5 text-[12px] rounded-lg bg-[var(--color-accent)] text-white font-medium hover:opacity-90">创建</button>
                <button onClick={() => setShowCreateFolder(false)} className="px-3 py-1.5 text-[12px] rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">取消</button>
              </div>
            )}

            {/* ── 面包屑导航 ── */}
            {folderBreadcrumbs.length > 0 && (
              <div className="mb-4 flex items-center gap-1 text-[12px] overflow-x-auto scrollbar-none">
                <button onClick={() => navigateToBreadcrumb(-1)}
                  className="flex items-center gap-1 px-2 py-1.5 rounded-lg hover:bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] whitespace-nowrap transition-colors">
                  <Home size={13} /> 根目录
                </button>
                {folderBreadcrumbs.map((bc, i) => (
                  <React.Fragment key={bc.id}>
                    <ChevronRight size={11} className="text-[var(--color-text-muted)] shrink-0" />
                    <button onClick={() => navigateToBreadcrumb(i)}
                      className={`flex items-center gap-1 px-2 py-1.5 rounded-lg whitespace-nowrap transition-colors ${
                        i === folderBreadcrumbs.length - 1
                          ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)] font-medium"
                          : "hover:bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
                      }`}>
                      <FolderOpen size={12} /> {bc.name}
                    </button>
                  </React.Fragment>
                ))}
              </div>
            )}

            {/* ── 拖拽上传区域 ── */}
            <div ref={dropZoneRef} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}
              className={`mb-4 rounded-xl border-2 border-dashed transition-all ${
                isDragOver
                  ? "border-[var(--color-accent)] bg-[var(--color-accent)]/5"
                  : "border-[var(--color-border)]/40 hover:border-[var(--color-border)]"
              }`}>
              {isDragOver ? (
                <div className="py-8 text-center">
                  <Upload size={28} className="mx-auto text-[var(--color-accent)] mb-2" />
                  <p className="text-[14px] text-[var(--color-accent)] font-medium">松开鼠标上传文件</p>
                </div>
              ) : (
                <div className="py-4 text-center">
                  <p className="text-[12px] text-[var(--color-text-muted)]">拖拽文件到此处上传，或点击上传按钮</p>
                </div>
              )}
            </div>

            {/* ── 文件夹列表（桌面列表视图） ── */}
            {folders.length > 0 && viewMode === "list" && (
              <div className="space-y-1 mb-3">
                {folders.map((folder) => (
                  <div key={folder.material_id} onClick={() => navigateToFolder(folder.material_id, folder.file_name)}
                    className="group flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-[var(--color-surface)] border border-transparent hover:border-[var(--color-border)]/50 cursor-pointer transition-all">
                    <FolderOpen size={18} className="text-amber-500 shrink-0" />
                    <span className="text-[13px] font-medium text-[var(--color-text)] flex-1 truncate">{folder.file_name}</span>
                    <span className="text-[11px] text-[var(--color-text-muted)] hidden sm:inline">{folder.child_count} 个项目</span>
                    <span className="text-[11px] text-[var(--color-text-muted)]">{formatDate(folder.created_at)}</span>
                    <ChevronRight size={14} className="text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                ))}
              </div>
            )}

            {/* ── 加载中 ── */}
            {loading ? (
              <div className="flex items-center justify-center py-20">
                <Loader2 size={22} className="animate-spin text-[var(--color-text-muted)]" />
              </div>
            ) : files.length === 0 && folders.length === 0 ? (
              /* ── 空状态 ── */
              <div className="text-center py-16">
                <div className="w-16 h-16 rounded-2xl bg-[var(--color-surface)] flex items-center justify-center mx-auto mb-4 border border-[var(--color-border)]/50">
                  <Upload size={28} className="text-[var(--color-text-muted)]" />
                </div>
                <p className="text-[15px] font-medium text-[var(--color-text)]">还没有文件</p>
                <p className="text-[12px] text-[var(--color-text-muted)] mt-1.5 mb-5">上传学习资料后自动解析索引，供 AI 和练习系统参考</p>
                <label className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--color-accent)] text-white text-[13px] font-medium hover:opacity-90 cursor-pointer transition-opacity">
                  <Upload size={15} /> 上传第一个文件
                  <input type="file" className="hidden" onChange={handleUpload} accept=".pdf,.docx,.pptx,.xlsx,.md,.txt,.jpg,.jpeg,.png,.gif,.webp,.mp3,.wav" />
                </label>
              </div>
            ) : viewMode === "list" ? (
              <>
                {/* ── 桌面端表格视图（hidden sm:block） ── */}
                <div className="hidden sm:block">
                  <div className="space-y-1">
                    {/* 表头：复选框 / 文件名(弹性) / 标签 / 大小 / 状态 / 日期 / 操作 */}
                    <div className="grid grid-cols-[28px_minmax(220px,1fr)_minmax(0,120px)_64px_minmax(0,90px)_minmax(0,110px)_72px] gap-2 px-3 py-2.5 text-[11px] font-medium text-[var(--color-text-muted)] border-b border-[var(--color-border)]/50">
                      <div><input type="checkbox" checked={selectedFiles.size === files.length && files.length > 0} onChange={selectAll} className="rounded accent-[var(--color-accent)]" /></div>
                      <span>文件名</span>
                      <span>标签</span>
                      <span>大小</span>
                      <span>状态</span>
                      <span>日期</span>
                      <span className="text-right">操作</span>
                    </div>
                    {/* 文件行 */}
                    {files.map((f) => {
                      const ext = f.file_type?.toLowerCase() || "";
                      const isIndexing = f.status === "uploading" || f.status === "pending";
                      const isFailed = f.status === "index_failed";
                      const isSelected = selectedFiles.has(f.material_id);
                      return (
                        <div key={f.material_id}
                          className={`group grid grid-cols-[28px_minmax(220px,1fr)_minmax(0,120px)_64px_minmax(0,90px)_minmax(0,110px)_72px] gap-2 items-center px-3 py-2.5 rounded-xl border transition-all ${
                            isSelected
                              ? "border-[var(--color-accent)]/30 bg-[var(--color-accent)]/5"
                              : "border-transparent hover:bg-[var(--color-surface)] hover:border-[var(--color-border)]/50"
                          }`}>
                          <input type="checkbox" checked={isSelected} onChange={() => toggleSelect(f.material_id)} className="rounded accent-[var(--color-accent)]" />
                          {f.is_folder ? (
                            <div onClick={() => navigateToFolder(f.material_id, f.file_name)}
                              className="flex items-center gap-2 min-w-0 text-[var(--color-text)] hover:text-[var(--color-accent)] cursor-pointer transition-colors">
                              <FolderOpen size={15} className="text-amber-500 shrink-0" />
                              <span className="text-[13px] truncate font-medium">{f.file_name || "未命名文件夹"}</span>
                            </div>
                          ) : (
                            <Link href={`/files/${f.material_id}`}
                              className="flex items-center gap-2 min-w-0 hover:text-[var(--color-accent)] transition-colors group/link">
                              {getFileIcon(ext)}
                              <span className="text-[13px] truncate flex-1 !text-[var(--color-text)]" title={f.file_name || ""}>
                                {f.file_name || `未命名·${ext || "文件"}`}
                              </span>
                              <ExternalLink size={10} className="text-[var(--color-text-muted)] opacity-0 group-hover/link:opacity-100 shrink-0 transition-opacity" />
                            </Link>
                          )}
                          <div className="flex items-center gap-1 flex-wrap min-w-0">
                            {(f.tags || []).slice(0, 2).map(tag => (
                              <span key={tag} className={`text-[9px] px-1.5 py-0.5 rounded leading-none ${getTagColor(tag)}`}>{tag}</span>
                            ))}
                            {(f.tags || []).length > 2 && <span className="text-[9px] text-[var(--color-text-muted)] shrink-0">+{f.tags.length - 2}</span>}
                          </div>
                          <span className="text-[12px] text-[var(--color-text-muted)] truncate">{f.is_folder ? `${f.toc_count}项` : formatSize(f.file_size)}</span>
                          <span>
                            {isIndexing ? (
                              <span className="inline-flex items-center gap-1 text-[11px] text-blue-500"><Loader2 size={11} className="animate-spin" /> 索引中</span>
                            ) : isFailed ? (
                              <span className="inline-flex items-center gap-1 text-[11px] text-red-500"><AlertCircle size={11} /> 失败</span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-[11px] text-green-500"><CheckCircle size={11} /> {f.chunk_count}块</span>
                            )}
                          </span>
                          <span className="text-[12px] text-[var(--color-text-muted)] truncate">{formatDate(f.created_at)}</span>
                          <div className="flex items-center gap-0.5 justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                            {!f.is_folder && (
                              <button onClick={() => handlePreview(f)} className="p-1.5 rounded-lg text-[var(--color-text-muted)] hover:text-blue-500 hover:bg-blue-500/10 transition-colors" title="预览"><Eye size={13} /></button>
                            )}
                            <button onClick={() => openEdit(f)} className="p-1.5 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent)]/10 transition-colors" title="编辑"><Pencil size={13} /></button>
                            {/* 更多操作下拉 */}
                            <div className="relative">
                              <button onClick={(e) => { e.stopPropagation(); e.preventDefault(); setActionMenu(actionMenu === f.material_id ? null : f.material_id); }}
                                className="p-1.5 rounded-lg text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-border)]/30 transition-colors" title="更多">
                                <MoreVertical size={13} />
                              </button>
                              {actionMenu === f.material_id && (
                                <>
                                  <div className="fixed inset-0 z-10" onClick={() => setActionMenu(null)} />
                                  <div className="absolute right-0 top-full mt-1 z-20 min-w-[120px] bg-[var(--color-surface)] rounded-xl shadow-lg border border-[var(--color-border)]/50 py-1 overflow-hidden">
                                    <button onClick={(e) => { e.stopPropagation(); handleDownload(f); setActionMenu(null); }}
                                      className="flex items-center gap-2 w-full px-3 py-2 text-[12px] text-green-600 hover:bg-green-500/10 transition-colors">
                                      <Download size={12} /> 下载
                                    </button>
                                    <div className="border-t border-[var(--color-border)]/30 mx-2" />
                                    <button onClick={(e) => { e.stopPropagation(); handleDelete(f.material_id); setActionMenu(null); }}
                                      className="flex items-center gap-2 w-full px-3 py-2 text-[12px] text-red-500 hover:bg-red-500/10 transition-colors">
                                      <Trash2 size={12} /> 删除
                                    </button>
                                  </div>
                                </>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* ── 移动端卡片视图（block sm:hidden） ── */}
                <div className="block sm:hidden space-y-2">
                  {files.map((f) => {
                    const ext = f.file_type?.toLowerCase() || "";
                    const isIndexing = f.status === "uploading" || f.status === "pending";
                    const isFailed = f.status === "index_failed";
                    return (
                      <div key={f.material_id} className="p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 shadow-sm">
                        <div className="flex items-start gap-2.5">
                          <input type="checkbox" checked={selectedFiles.has(f.material_id)} onChange={() => toggleSelect(f.material_id)}
                            className="mt-0.5 rounded accent-[var(--color-accent)] shrink-0" />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              {f.is_folder ? (
                                <FolderOpen size={15} className="text-amber-500 shrink-0" />
                              ) : (
                                getFileIcon(ext)
                              )}
                              <span className="text-[13px] font-medium text-[var(--color-text)] break-all leading-snug">{f.file_name}</span>
                            </div>
                            {/* tags */}
                            {(f.tags || []).length > 0 && (
                              <div className="flex items-center gap-1 mt-1.5 flex-wrap">
                                {(f.tags || []).map(tag => (
                                  <span key={tag} className={`text-[9px] px-1.5 py-0.5 rounded leading-none ${getTagColor(tag)}`}>{tag}</span>
                                ))}
                              </div>
                            )}
                            {/* meta */}
                            <div className="flex items-center gap-2 mt-1.5 text-[11px] text-[var(--color-text-muted)]">
                              <span>{f.is_folder ? `${f.toc_count}项` : formatSize(f.file_size)}</span>
                              <span>·</span>
                              <span>{formatDate(f.created_at)}</span>
                            </div>
                            {/* status */}
                            <div className="mt-1">
                              {isIndexing ? (
                                <span className="inline-flex items-center gap-1 text-[11px] text-blue-500"><Loader2 size={11} className="animate-spin" /> 索引中</span>
                              ) : isFailed ? (
                                <span className="inline-flex items-center gap-1 text-[11px] text-red-500"><AlertCircle size={11} /> 失败</span>
                              ) : (
                                <span className="inline-flex items-center gap-1 text-[11px] text-green-500"><CheckCircle size={11} /> 就绪</span>
                              )}
                            </div>
                          </div>
                        </div>
                        {/* 操作按钮，始终可见 */}
                        <div className="flex items-center gap-1 mt-3 pt-2.5 border-t border-[var(--color-border)]/30">
                          {!f.is_folder && (
                            <button onClick={() => handlePreview(f)}
                              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-blue-500 bg-blue-500/10 hover:bg-blue-500/20 transition-colors min-h-[32px]">
                              <Eye size={12} /> 预览
                            </button>
                          )}
                          <button onClick={() => openEdit(f)}
                            className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-[var(--color-accent)] bg-[var(--color-accent)]/10 hover:bg-[var(--color-accent)]/20 transition-colors min-h-[32px]">
                            <Pencil size={12} /> 编辑
                          </button>
                          {/* 更多操作 */}
                          <div className="relative ml-auto">
                            <button onClick={(e) => { e.stopPropagation(); e.preventDefault(); setActionMenu(actionMenu === f.material_id ? null : f.material_id); }}
                              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[11px] font-medium text-[var(--color-text-muted)] hover:bg-[var(--color-border)]/30 transition-colors min-h-[32px]">
                              <MoreVertical size={12} />
                            </button>
                            {actionMenu === f.material_id && (
                              <>
                                <div className="fixed inset-0 z-10" onClick={() => setActionMenu(null)} />
                                <div className="absolute right-0 top-full mt-1 z-20 min-w-[110px] bg-[var(--color-surface)] rounded-lg shadow-lg border border-[var(--color-border)]/50 py-1 overflow-hidden">
                                  <button onClick={(e) => { e.stopPropagation(); handleDownload(f); setActionMenu(null); }}
                                    className="flex items-center gap-1.5 w-full px-3 py-2 text-[12px] text-green-600 hover:bg-green-500/10 transition-colors">
                                    <Download size={12} /> 下载
                                  </button>
                                  <div className="border-t border-[var(--color-border)]/30 mx-2" />
                                  <button onClick={(e) => { e.stopPropagation(); handleDelete(f.material_id); setActionMenu(null); }} disabled={deleting === f.material_id}
                                    className="flex items-center gap-1.5 w-full px-3 py-2 text-[12px] text-red-500 hover:bg-red-500/10 transition-colors">
                                    {deleting === f.material_id ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />} 删除
                                  </button>
                                </div>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </>
            ) : (
              /* ── 网格视图 ── */
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                {files.map((f) => {
                  const ext = f.file_type?.toLowerCase() || "";
                  const isIndexing = f.status === "uploading" || f.status === "pending";
                  const isFailed = f.status === "index_failed";
                  return (
                    <div key={f.material_id} className="group relative p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 hover:border-[var(--color-accent)]/30 hover:shadow-md transition-all">
                      <div className="flex flex-col items-center text-center">
                        <input type="checkbox" checked={selectedFiles.has(f.material_id)} onChange={() => toggleSelect(f.material_id)}
                          className="absolute top-2 left-2 rounded accent-[var(--color-accent)]" />
                        {f.is_folder ? (
                          <FolderOpen size={36} className="text-amber-500 mb-2.5" />
                        ) : (
                          <div className="w-14 h-14 rounded-xl bg-[var(--color-bg)] flex items-center justify-center mb-2.5 border border-[var(--color-border)]/30">
                            {getFileIcon(ext)}
                          </div>
                        )}
                        <p className="text-[12px] font-medium text-[var(--color-text)] truncate w-full">{f.file_name}</p>
                        <p className="text-[10px] text-[var(--color-text-muted)] mt-1">{f.is_folder ? `${f.toc_count}项` : formatSize(f.file_size)}</p>
                        {(f.tags || []).length > 0 && (
                          <div className="flex items-center gap-0.5 mt-1.5 flex-wrap justify-center">
                            {(f.tags || []).slice(0, 2).map(tag => (
                              <span key={tag} className={`text-[8px] px-1.5 py-0.5 rounded leading-none ${getTagColor(tag)}`}>{tag}</span>
                            ))}
                          </div>
                        )}
                        <div className="mt-1.5">
                          {isIndexing ? (
                            <span className="text-[10px] text-blue-500 flex items-center gap-0.5"><Loader2 size={9} className="animate-spin" /> 索引中</span>
                          ) : isFailed ? (
                            <span className="text-[10px] text-red-500 flex items-center gap-0.5"><AlertCircle size={9} /> 失败</span>
                          ) : (
                            <span className="text-[10px] text-green-500 flex items-center gap-0.5"><CheckCircle size={9} /> 就绪</span>
                          )}
                        </div>
                      </div>
                      {/* hover 操作 */}
                      <div className="absolute top-2 right-2 hidden group-hover:flex items-center gap-0.5 bg-[var(--color-surface)] rounded-lg p-0.5 shadow-sm border border-[var(--color-border)]/30">
                        {!f.is_folder && (
                          <button onClick={() => handlePreview(f)} className="p-1 rounded-md hover:bg-blue-500/10 text-[var(--color-text-muted)] hover:text-blue-500 transition-colors" title="预览"><Eye size={12} /></button>
                        )}
                        <button onClick={() => openEdit(f)} className="p-1 rounded-md hover:bg-[var(--color-accent)]/10 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] transition-colors" title="编辑"><Pencil size={12} /></button>
                        {/* 更多操作下拉 */}
                        <div className="relative">
                          <button onClick={(e) => { e.stopPropagation(); e.preventDefault(); setActionMenu(actionMenu === f.material_id ? null : f.material_id); }}
                            className="p-1 rounded-md hover:bg-[var(--color-border)]/30 text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors" title="更多">
                            <MoreVertical size={12} />
                          </button>
                          {actionMenu === f.material_id && (
                            <>
                              <div className="fixed inset-0 z-10" onClick={() => setActionMenu(null)} />
                              <div className="absolute right-0 top-full mt-1 z-20 min-w-[100px] bg-[var(--color-surface)] rounded-lg shadow-lg border border-[var(--color-border)]/50 py-1 overflow-hidden">
                                <button onClick={(e) => { e.stopPropagation(); handleDownload(f); setActionMenu(null); }}
                                  className="flex items-center gap-1.5 w-full px-2.5 py-1.5 text-[11px] text-green-600 hover:bg-green-500/10 transition-colors">
                                  <Download size={11} /> 下载
                                </button>
                                <div className="border-t border-[var(--color-border)]/30 mx-2" />
                                <button onClick={(e) => { e.stopPropagation(); handleDelete(f.material_id); setActionMenu(null); }}
                                  className="flex items-center gap-1.5 w-full px-2.5 py-1.5 text-[11px] text-red-500 hover:bg-red-500/10 transition-colors">
                                  <Trash2 size={11} /> 删除
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {/* ── 分页 ── */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-3 mt-8">
                <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}
                  className="px-4 py-2 text-[12px] rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-accent)]/30 disabled:opacity-30 disabled:pointer-events-none transition-all">
                  上一页
                </button>
                <span className="text-[12px] text-[var(--color-text-muted)]">{page} / {totalPages}</span>
                <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
                  className="px-4 py-2 text-[12px] rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:border-[var(--color-accent)]/30 disabled:opacity-30 disabled:pointer-events-none transition-all">
                  下一页
                </button>
              </div>
            )}

            {/* ── 批量操作 ── */}
            {selectedFiles.size > 0 && (
              <>
                {/* 移动端：底部固定栏 */}
                <div className="fixed bottom-0 left-0 right-0 z-40 p-3 bg-[var(--color-surface)] border-t border-[var(--color-border)] shadow-[0_-4px_12px_rgba(0,0,0,0.08)] sm:hidden">
                  <div className="flex items-center gap-2">
                    <span className="text-[12px] text-[var(--color-text)] font-medium">已选 {selectedFiles.size} 项</span>
                    <div className="flex-1" />
                    <button onClick={() => handleBatchAction("delete")}
                      className="px-4 py-2 text-[12px] rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 font-medium transition-colors min-h-[36px]">
                      删除
                    </button>
                    <button onClick={() => setSelectedFiles(new Set())}
                      className="px-4 py-2 text-[12px] rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors min-h-[36px]">
                      取消
                    </button>
                  </div>
                </div>
                {/* 桌面端：随内容显示 */}
                <div className="hidden sm:block mt-4 p-3 rounded-xl bg-[var(--color-accent)]/5 border border-[var(--color-accent)]/20">
                  <div className="flex items-center gap-3">
                    <span className="text-[13px] text-[var(--color-accent)] font-medium">已选择 {selectedFiles.size} 个文件</span>
                    <button onClick={() => handleBatchAction("delete")}
                      className="px-3 py-1.5 text-[11px] rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 font-medium transition-colors">
                      <Trash2 size={12} className="inline mr-1" />删除
                    </button>
                    <button onClick={() => setSelectedFiles(new Set())}
                      className="ml-auto text-[12px] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">
                      取消选择
                    </button>
                  </div>
                </div>
              </>
            )}

            {/* ── 编辑弹窗（桌面居中 / 移动端底部滑出） ── */}
            {editFile && (
              <>
                {/* 移动端：底部滑出面板 */}
                <div className="sm:hidden fixed inset-0 z-50" onClick={() => setEditFile(null)}>
                  <div className="absolute inset-0 bg-black/50" />
                  <div className="absolute bottom-0 left-0 right-0 bg-[var(--color-surface)] rounded-t-2xl shadow-xl max-h-[85vh] overflow-auto"
                    onClick={(e) => e.stopPropagation()}>
                    <div className="sticky top-0 bg-[var(--color-surface)] border-b border-[var(--color-border)]/50 px-5 py-3.5 flex items-center justify-between rounded-t-2xl">
                      <h3 className="text-[15px] font-semibold text-[var(--color-text)]">编辑文件</h3>
                      <button onClick={() => setEditFile(null)} className="p-1.5 rounded-lg hover:bg-[var(--color-border)]/30 text-[var(--color-text-muted)] transition-colors">
                        <X size={18} />
                      </button>
                    </div>
                    <div className="p-5 space-y-4">
                      <div>
                        <label className="text-[11px] text-[var(--color-text-muted)] block mb-1.5 font-medium">文件名</label>
                        <input value={editName} onChange={(e) => setEditName(e.target.value)}
                          className="w-full px-3.5 py-2.5 text-[13px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)] transition-colors" />
                      </div>
                      <div>
                        <label className="text-[11px] text-[var(--color-text-muted)] block mb-1.5 font-medium">标签</label>
                        <div className="flex items-center gap-1.5 flex-wrap mb-2">
                          {editTags.map(tag => (
                            <span key={tag} className={`inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg ${getTagColor(tag)}`}>
                              {tag}
                              <button onClick={() => removeTag(tag)} className="hover:opacity-70"><X size={10} /></button>
                            </span>
                          ))}
                        </div>
                        <div className="flex items-center gap-2">
                          <input value={editTagInput} onChange={(e) => setEditTagInput(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addTag())}
                            placeholder="输入标签后回车"
                            className="flex-1 px-3 py-2 text-[12px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)] transition-colors" />
                          <button onClick={addTag}
                            className="p-2 rounded-lg bg-[var(--color-accent)]/10 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20 transition-colors">
                            <Tag size={14} />
                          </button>
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] text-[var(--color-text-muted)] block mb-1.5 font-medium">所属层级</label>
                        <select value={editLevel} onChange={(e) => setEditLevel(e.target.value)}
                          className="w-full px-3.5 py-2.5 text-[13px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)] transition-colors">
                          <option value="dir">目录</option>
                          <option value="node">节点</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-[11px] text-[var(--color-text-muted)] block mb-1.5 font-medium">归属 ID</label>
                        <input value={editParentId} onChange={(e) => setEditParentId(e.target.value)} placeholder="留空表示未分类"
                          className="w-full px-3.5 py-2.5 text-[13px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)] transition-colors" />
                      </div>
                    </div>
                    <div className="sticky bottom-0 bg-[var(--color-surface)] border-t border-[var(--color-border)]/50 px-5 py-3.5 flex items-center justify-end gap-3">
                      <button onClick={() => setEditFile(null)}
                        className="px-4 py-2.5 text-[13px] rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors min-h-[36px]">
                        取消
                      </button>
                      <button onClick={handleSaveEdit} disabled={saving}
                        className="px-4 py-2.5 text-[13px] rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 transition-all flex items-center gap-1.5 min-h-[36px] font-medium">
                        {saving ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                        {saving ? "保存中..." : "保存"}
                      </button>
                    </div>
                  </div>
                </div>
                {/* 桌面端：居中弹窗 */}
                <div className="hidden sm:flex fixed inset-0 z-50 items-center justify-center bg-black/40" onClick={() => setEditFile(null)}>
                  <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] w-full max-w-md mx-4 p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
                    <h3 className="text-[15px] font-semibold text-[var(--color-text)] mb-5">编辑文件</h3>
                    <div className="space-y-4">
                      <div>
                        <label className="text-[11px] text-[var(--color-text-muted)] block mb-1.5 font-medium">文件名</label>
                        <input value={editName} onChange={(e) => setEditName(e.target.value)}
                          className="w-full px-3.5 py-2.5 text-[13px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)] transition-colors" />
                      </div>
                      <div>
                        <label className="text-[11px] text-[var(--color-text-muted)] block mb-1.5 font-medium">标签</label>
                        <div className="flex items-center gap-1.5 flex-wrap mb-2">
                          {editTags.map(tag => (
                            <span key={tag} className={`inline-flex items-center gap-1 text-[11px] px-2.5 py-1 rounded-lg ${getTagColor(tag)}`}>
                              {tag}
                              <button onClick={() => removeTag(tag)} className="hover:opacity-70"><X size={10} /></button>
                            </span>
                          ))}
                        </div>
                        <div className="flex items-center gap-2">
                          <input value={editTagInput} onChange={(e) => setEditTagInput(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addTag())}
                            placeholder="输入标签后回车"
                            className="flex-1 px-3 py-2 text-[12px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)] transition-colors" />
                          <button onClick={addTag}
                            className="p-2 rounded-lg bg-[var(--color-accent)]/10 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20 transition-colors">
                            <Tag size={14} />
                          </button>
                        </div>
                      </div>
                      <div>
                        <label className="text-[11px] text-[var(--color-text-muted)] block mb-1.5 font-medium">所属层级</label>
                        <select value={editLevel} onChange={(e) => setEditLevel(e.target.value)}
                          className="w-full px-3.5 py-2.5 text-[13px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)] transition-colors">
                          <option value="dir">目录</option>
                          <option value="node">节点</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-[11px] text-[var(--color-text-muted)] block mb-1.5 font-medium">归属 ID</label>
                        <input value={editParentId} onChange={(e) => setEditParentId(e.target.value)} placeholder="留空表示未分类"
                          className="w-full px-3.5 py-2.5 text-[13px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)] transition-colors" />
                      </div>
                    </div>
                    <div className="flex items-center justify-end gap-3 mt-6">
                      <button onClick={() => setEditFile(null)}
                        className="px-4 py-2 text-[12px] rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors">
                        取消
                      </button>
                      <button onClick={handleSaveEdit} disabled={saving}
                        className="px-4 py-2 text-[12px] rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 transition-all flex items-center gap-1.5 font-medium">
                        {saving ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                        {saving ? "保存中..." : "保存"}
                      </button>
                    </div>
                  </div>
                </div>
              </>
            )}

            {/* ── 预览弹窗（移动端全屏 / 桌面居中） ── */}
            <style>{`
              @keyframes previewFadeIn { from { opacity: 0; } to { opacity: 1; } }
              @keyframes previewScaleIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
            `}</style>
            {previewFile && (
              <>
                {/* 移动端：全屏 */}
                <div className="sm:hidden fixed inset-0 z-50 bg-black/70 flex flex-col" style={{ animation: "previewFadeIn 0.15s ease-out" }} onClick={() => setPreviewFile(null)}>
                  <div className="bg-[var(--color-surface)] flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]/50" onClick={(e) => e.stopPropagation()}>
                    <h3 className="text-[14px] font-medium text-[var(--color-text)] truncate flex-1 mr-3">{previewFile.file_name}</h3>
                    <button onClick={() => setPreviewFile(null)} className="p-1.5 rounded-lg hover:bg-[var(--color-border)]/30 text-[var(--color-text-muted)] transition-colors">
                      <X size={20} />
                    </button>
                  </div>
                  <div className="flex-1 flex items-center justify-center p-4 bg-[var(--color-bg)] overflow-auto" onClick={(e) => e.stopPropagation()}>
                    <FilePreview file={previewFile} />
                  </div>
                  <div className="bg-[var(--color-surface)] border-t border-[var(--color-border)]/50 px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <button onClick={() => handleDownload(previewFile)}
                      className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--color-accent)] text-white text-[13px] font-medium hover:opacity-90 transition-opacity">
                      <Download size={15} /> 下载文件
                    </button>
                  </div>
                </div>
                {/* 桌面端：居中弹窗 + 缩放 + 缩略图 */}
                <div className="hidden sm:flex fixed inset-0 z-50 items-center justify-center bg-black/60" style={{ animation: "previewFadeIn 0.15s ease-out" }} onClick={() => setPreviewFile(null)}>
                  <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] w-full max-w-6xl mx-4 shadow-xl max-h-[90vh] flex flex-col" style={{ animation: "previewScaleIn 0.15s ease-out" }} onClick={(e) => e.stopPropagation()}>
                    {/* 标题栏 */}
                    <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--color-border)]/50">
                      <h3 className="text-[15px] font-semibold text-[var(--color-text)] truncate flex-1 mr-3">{previewFile.file_name}</h3>
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] text-[var(--color-text-muted)]">{formatSize(previewFile.file_size)}</span>
                        <button onClick={() => setPreviewFile(null)} className="p-1.5 rounded-lg hover:bg-[var(--color-border)]/30 text-[var(--color-text-muted)] transition-colors"><X size={18} /></button>
                      </div>
                    </div>
                    {/* 缩放工具栏 */}
                    <div className="flex items-center justify-between px-5 py-2 border-b border-[var(--color-border)]/30 bg-[var(--color-bg)]/50">
                      <div className="flex items-center gap-1">
                        <button onClick={() => setZoom(z => Math.max(0.25, +(z - 0.25).toFixed(2)))}
                          className="p-1.5 rounded-lg hover:bg-[var(--color-border)]/30 text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors" title="缩小">
                          <ZoomOut size={14} />
                        </button>
                        <span className="text-[11px] text-[var(--color-text-muted)] w-12 text-center font-medium tabular-nums">{Math.round(zoom * 100)}%</span>
                        <button onClick={() => setZoom(z => Math.min(4, +(z + 0.25).toFixed(2)))}
                          className="p-1.5 rounded-lg hover:bg-[var(--color-border)]/30 text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors" title="放大">
                          <ZoomIn size={14} />
                        </button>
                        <button onClick={() => setZoom(1)}
                          className="px-2.5 py-1 text-[10px] rounded-lg hover:bg-[var(--color-border)]/30 text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors ml-1 font-medium">
                          重置
                        </button>
                      </div>
                      <button onClick={() => handleDownload(previewFile)}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-[11px] rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 font-medium transition-opacity">
                        <Download size={12} /> 下载
                      </button>
                    </div>
                    {/* 预览内容区（可滚动/平移 + 滚轮缩放） */}
                    <div className="flex-1 overflow-auto bg-[var(--color-bg)] min-h-[300px]"
                      onWheel={(e) => {
                        if (e.ctrlKey || e.metaKey) { e.preventDefault(); const d = e.deltaY > 0 ? -0.1 : 0.1; setZoom(z => Math.max(0.25, Math.min(4, +(z + d).toFixed(2)))); }
                      }}>
                      <div className="w-full" style={{ transform: `scale(${zoom})`, transformOrigin: 'top center' }}>
                        <FilePreview file={previewFile} />
                      </div>
                    </div>
                    {/* 缩略图导航条 */}
                    {previewableFiles.length > 1 && (
                      <div className="border-t border-[var(--color-border)]/50 px-5 py-3">
                        <div className="flex items-center gap-2 overflow-x-auto scrollbar-none">
                          {previewableFiles.map((f) => {
                            const ext = f.file_type?.toLowerCase() || "";
                            const isActive = f.material_id === previewFile.material_id;
                            return (
                              <button key={f.material_id} onClick={() => { setPreviewFile(f); setZoom(1); }}
                                className={`flex-shrink-0 w-14 h-14 rounded-lg border-2 transition-all flex items-center justify-center overflow-hidden ${
                                  isActive
                                    ? 'border-[var(--color-accent)] ring-1 ring-[var(--color-accent)]/30 opacity-100'
                                    : 'border-[var(--color-border)]/30 hover:border-[var(--color-accent)]/50 opacity-60 hover:opacity-100'
                                }`}
                                title={f.file_name}>
                                {["jpg","jpeg","png","gif","bmp","webp","svg","ico","avif"].includes(ext) ? (
                                  <img src={`/api/files/${f.material_id}/preview?token=${encodeURIComponent(getAccessToken() || "")}`}
                                    alt={f.file_name} className="w-full h-full object-cover" loading="lazy" />
                                ) : (
                                  <div className="flex items-center justify-center w-full h-full bg-[var(--color-bg)] text-[var(--color-text-muted)]">
                                    {getFileIcon(ext)}
                                  </div>
                                )}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </>
        )}

        {/* ════════════════════════════════════
            TAB: 统计
            ════════════════════════════════════ */}
        {tab === "stats" && (
          <div className="space-y-5">
            {stats ? (
              <>
                {/* 统计卡片 */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
                  <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 hover:shadow-md transition-shadow">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-8 h-8 rounded-lg bg-[var(--color-accent)]/10 flex items-center justify-center">
                        <FileText size={15} className="text-[var(--color-accent)]" />
                      </div>
                    </div>
                    <p className="text-[22px] font-bold text-[var(--color-text)]">{stats.total_files}</p>
                    <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">文件总数</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 hover:shadow-md transition-shadow">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-8 h-8 rounded-lg bg-green-500/10 flex items-center justify-center">
                        <HardDrive size={15} className="text-green-500" />
                      </div>
                    </div>
                    <p className="text-[22px] font-bold text-[var(--color-text)]">{stats.total_size_formatted}</p>
                    <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">总大小</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 hover:shadow-md transition-shadow">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-8 h-8 rounded-lg bg-amber-500/10 flex items-center justify-center">
                        <Folder size={15} className="text-amber-500" />
                      </div>
                    </div>
                    <p className="text-[22px] font-bold text-[var(--color-text)]">{stats.folder_count}</p>
                    <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">文件夹</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 hover:shadow-md transition-shadow">
                    <div className="flex items-center gap-2 mb-2">
                      <div className="w-8 h-8 rounded-lg bg-red-500/10 flex items-center justify-center">
                        <Trash2 size={15} className="text-red-500" />
                      </div>
                    </div>
                    <p className="text-[22px] font-bold text-[var(--color-text)]">{stats.trash_count}</p>
                    <p className="text-[11px] text-[var(--color-text-muted)] mt-0.5">回收站</p>
                  </div>
                </div>
                {/* 类型分布 */}
                <div className="p-5 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50">
                  <h3 className="text-[14px] font-semibold text-[var(--color-text)] mb-4 flex items-center gap-2">
                    <BarChart3 size={16} className="text-[var(--color-accent)]" />
                    文件类型分布
                  </h3>
                  <div className="space-y-3">
                    {stats.by_type.map((t) => (
                      <div key={t.file_type} className="flex items-center gap-3">
                        <span className="text-[12px] text-[var(--color-text)] w-16 font-medium uppercase">{t.file_type || "其他"}</span>
                        <div className="flex-1 h-2.5 bg-[var(--color-border)] rounded-full overflow-hidden">
                          <div className="h-full bg-[var(--color-accent)] rounded-full transition-all" style={{ width: `${stats.total_files > 0 ? (t.count / stats.total_files) * 100 : 0}%` }} />
                        </div>
                        <span className="text-[11px] text-[var(--color-text-muted)] w-24 text-right">{t.count} 个 ({formatSize(t.total_size)})</span>
                      </div>
                    ))}
                  </div>
                </div>
                {/* 最近上传 */}
                <div className="p-5 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50">
                  <h3 className="text-[14px] font-semibold text-[var(--color-text)] mb-4 flex items-center gap-2">
                    <Clock size={16} className="text-[var(--color-accent)]" />
                    最近上传
                  </h3>
                  <div className="space-y-2">
                    {stats.recent_files.map((f) => (
                      <div key={f.material_id} className="flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-[var(--color-bg)] transition-colors">
                        {getFileIcon(f.file_type?.toLowerCase() || "")}
                        <span className="text-[13px] text-[var(--color-text)] flex-1 truncate">{f.file_name}</span>
                        <span className="text-[11px] text-[var(--color-text-muted)]">{formatSize(f.file_size)}</span>
                        <span className="text-[11px] text-[var(--color-text-muted)]">{formatDate(f.created_at)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="flex items-center justify-center py-20">
                <Loader2 size={22} className="animate-spin text-[var(--color-text-muted)]" />
              </div>
            )}
          </div>
        )}

        {/* ════════════════════════════════════
            TAB: 回收站
            ════════════════════════════════════ */}
        {tab === "trash" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-[12px] text-[var(--color-text-muted)]">回收站中的文件将保留 30 天</p>
              {trashFiles.length > 0 && (
                <button onClick={handleEmptyTrash}
                  className="flex items-center gap-1.5 px-4 py-2 text-[12px] rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 font-medium transition-colors">
                  <Trash2 size={14} /> 清空回收站
                </button>
              )}
            </div>
            {loading ? (
              <div className="flex items-center justify-center py-20">
                <Loader2 size={22} className="animate-spin text-[var(--color-text-muted)]" />
              </div>
            ) : trashFiles.length === 0 ? (
              <div className="text-center py-16">
                <div className="w-16 h-16 rounded-2xl bg-[var(--color-surface)] flex items-center justify-center mx-auto mb-4 border border-[var(--color-border)]/50">
                  <Trash2 size={28} className="text-[var(--color-text-muted)]" />
                </div>
                <p className="text-[15px] font-medium text-[var(--color-text)]">回收站为空</p>
                <p className="text-[12px] text-[var(--color-text-muted)] mt-1.5">删除的文件会出现在这里</p>
              </div>
            ) : (
              <>
                {/* 桌面端表格 */}
                <div className="hidden sm:block space-y-1">
                  <div className="grid grid-cols-[1fr_100px_120px_140px] gap-3 px-4 py-2.5 text-[11px] font-medium text-[var(--color-text-muted)] border-b border-[var(--color-border)]/50">
                    <span>文件名</span>
                    <span>大小</span>
                    <span>删除时间</span>
                    <span>操作</span>
                  </div>
                  {trashFiles.map((f) => (
                    <div key={f.material_id}
                      className="group grid grid-cols-[1fr_100px_120px_140px] gap-3 items-center px-4 py-2.5 rounded-xl hover:bg-[var(--color-surface)] border border-transparent hover:border-[var(--color-border)]/50 transition-all">
                      <div className="flex items-center gap-2.5 min-w-0">
                        {getFileIcon(f.file_type?.toLowerCase() || "")}
                        <span className="text-[13px] text-[var(--color-text)] truncate">{f.file_name}</span>
                      </div>
                      <span className="text-[12px] text-[var(--color-text-muted)]">{formatSize(f.file_size)}</span>
                      <span className="text-[12px] text-red-400 flex items-center gap-1">
                        <Clock size={11} /> {f.deleted_at ? formatDate(f.deleted_at) : ""}
                      </span>
                      <div className="flex items-center gap-2">
                        <button onClick={() => handleRestore(f.material_id)}
                          className="px-3 py-1.5 text-[11px] rounded-lg bg-green-500/10 text-green-500 hover:bg-green-500/20 font-medium transition-colors flex items-center gap-1">
                          <RefreshCw size={11} /> 恢复
                        </button>
                        <button onClick={() => handlePermanentDelete(f.material_id)}
                          className="px-3 py-1.5 text-[11px] rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 font-medium transition-colors flex items-center gap-1">
                          <Trash2 size={11} /> 永久删除
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                {/* 移动端卡片 */}
                <div className="block sm:hidden space-y-2">
                  {trashFiles.map((f) => (
                    <div key={f.material_id} className="p-3 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 shadow-sm">
                      <div className="flex items-center gap-2.5">
                        {getFileIcon(f.file_type?.toLowerCase() || "")}
                        <span className="text-[13px] font-medium text-[var(--color-text)] break-all flex-1">{f.file_name}</span>
                      </div>
                      <div className="flex items-center gap-3 mt-2 text-[11px] text-[var(--color-text-muted)]">
                        <span>{formatSize(f.file_size)}</span>
                        <span>·</span>
                        <span className="text-red-400 flex items-center gap-1"><Clock size={11} /> {f.deleted_at ? formatDate(f.deleted_at) : ""}</span>
                      </div>
                      <div className="flex items-center gap-2 mt-3 pt-2.5 border-t border-[var(--color-border)]/30">
                        <button onClick={() => handleRestore(f.material_id)}
                          className="flex items-center gap-1 px-3 py-1.5 text-[12px] rounded-lg bg-green-500/10 text-green-500 hover:bg-green-500/20 font-medium transition-colors min-h-[36px]">
                          <RefreshCw size={13} /> 恢复
                        </button>
                        <button onClick={() => handlePermanentDelete(f.material_id)}
                          className="flex items-center gap-1 px-3 py-1.5 text-[12px] rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 font-medium transition-colors min-h-[36px]">
                          <Trash2 size={13} /> 永久删除
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {/* ════════════════════════════════════
            TAB: 题库
            ════════════════════════════════════ */}
        {tab === "banks" && (
          <>
            <div className="flex items-center justify-between mb-4">
              <p className="text-[12px] text-[var(--color-text-muted)]">共 {banks.length} 个题库</p>
              <Link href="/import"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white text-[12px] font-medium hover:opacity-90 transition-opacity">
                <Upload size={14} /> 导入题库
              </Link>
            </div>
            {loading ? (
              <div className="flex items-center justify-center py-20">
                <Loader2 size={22} className="animate-spin text-[var(--color-text-muted)]" />
              </div>
            ) : banks.length === 0 ? (
              <div className="text-center py-16">
                <div className="w-16 h-16 rounded-2xl bg-[var(--color-surface)] flex items-center justify-center mx-auto mb-4 border border-[var(--color-border)]/50">
                  <Library size={28} className="text-[var(--color-text-muted)]" />
                </div>
                <p className="text-[15px] font-medium text-[var(--color-text)]">还没有题库</p>
                <p className="text-[12px] text-[var(--color-text-muted)] mt-1.5 mb-5">导入或创建题库，开始练习</p>
                <Link href="/import"
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[var(--color-accent)] text-white text-[13px] font-medium hover:opacity-90 transition-opacity">
                  <Upload size={15} /> 导入题库
                </Link>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {banks.map((bank) => (
                  <div key={bank.id}
                    className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 hover:border-[var(--color-accent)]/30 hover:shadow-md transition-all group">
                    <div className="flex items-start gap-3">
                      <div className="w-10 h-10 rounded-lg bg-violet-500/10 flex items-center justify-center shrink-0">
                        <Library size={18} className="text-violet-500" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h3 className="text-[14px] font-medium text-[var(--color-text)] truncate">{bank.name}</h3>
                          {bank.auto_created && <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-500 shrink-0">自动</span>}
                        </div>
                        {bank.description && <p className="text-[11px] text-[var(--color-text-muted)] mt-1 line-clamp-1">{bank.description}</p>}
                        <div className="flex items-center gap-3 mt-2">
                          <span className="text-[11px] text-[var(--color-text-muted)]">{bank.question_count} 题</span>
                          {bank.ref_node_label && <span className="text-[11px] text-violet-500/70">关联: {bank.ref_node_label}</span>}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 mt-3 pt-3 border-t border-[var(--color-border)]/30">
                      <Link href={`/practice/banks/${bank.id}`}
                        className="flex-1 text-center px-3 py-2 rounded-lg bg-[var(--color-accent)]/10 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20 text-[11px] font-medium transition-colors min-h-[36px] leading-[36px]">
                        管理
                      </Link>
                      <Link href={`/practice?tab=practice&bank=${bank.id}`}
                        className="flex-1 text-center px-3 py-2 rounded-lg bg-green-500/10 text-green-600 hover:bg-green-500/20 text-[11px] font-medium transition-colors min-h-[36px] leading-[36px] flex items-center justify-center gap-1">
                        <Play size={12} /> 练习
                      </Link>
                      <button onClick={() => handleDeleteBank(bank.id)} disabled={deletingBank === bank.id}
                        className="flex-1 text-center px-3 py-2 rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 text-[11px] font-medium transition-colors min-h-[36px] leading-[36px] flex items-center justify-center gap-1">
                        {deletingBank === bank.id ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />} 删除
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// Note: StatsPanel removed — unused
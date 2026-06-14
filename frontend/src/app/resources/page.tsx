"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { Upload, FileText, Image, Search, Trash2, Loader2,
  Library, ExternalLink, File, CheckCircle, AlertCircle, Play,
  Download, Pencil, FolderPlus, Folder, FolderOpen, Tag, X,
  Check, ChevronRight, Home, RefreshCw, Eye, Grid, List,
  HardDrive, Clock, Star,
} from "lucide-react";
import { authedFetch, API_BASE } from "@/lib/api/api";

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
  const [stats, setStats] = useState<FileStats | null>(null);
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
      const res = await authedFetch(`/api/v7/practice/banks`);
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

  const handleDownload = (f: FileItem) => { window.open(`${API_BASE}/api/files/${f.material_id}/download`, "_blank"); };

  const handlePreview = (f: FileItem) => {
    const ext = f.file_type?.toLowerCase() || "";
    if (["jpg", "jpeg", "png", "gif", "webp", "bmp", "pdf"].includes(ext)) setPreviewFile(f);
    else handleDownload(f);
  };

  const handleDeleteBank = async (id: string) => {
    if (!confirm("确定删除该题库？")) return;
    setDeletingBank(id);
    try { await authedFetch(`/api/v7/practice/banks/${id}`, { method: "DELETE" }); fetchBanks(); }
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

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
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

        <div className="flex items-center gap-1 mb-6 border-b border-[var(--color-border)]/50 overflow-x-auto">
          {[
            { id: "files" as Tab, label: "📁 文件资料" },
            { id: "banks" as Tab, label: "📚 题库资料" },
            { id: "stats" as Tab, label: "📊 统计" },
            { id: "trash" as Tab, label: "🗑️ 回收站" },
          ].map((t) => (
            <button key={t.id} onClick={() => { setTab(t.id); setPage(1); }}
              className={`relative px-4 py-2.5 text-[13px] font-medium transition-colors whitespace-nowrap ${tab === t.id ? "text-[var(--color-accent)]" : "text-[var(--color-text-muted)] hover:text-[var(--color-text)]"}`}>
              {t.label}
              {tab === t.id && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-[var(--color-accent)] rounded-full" />}
              {t.id === "trash" && stats?.trash_count ? <span className="ml-1 text-[9px] px-1 rounded bg-red-500/10 text-red-500">{stats.trash_count}</span> : null}
            </button>
          ))}
        </div>

        {tab === "files" && (
          <>
            <div className="flex items-center gap-3 mb-4 flex-wrap">
              <div className="flex items-center gap-1">
                {([
                  { value: "all", label: "全部" },
                  { value: "pdf", label: "PDF" },
                  { value: "docx", label: "文档" },
                  { value: "image", label: "图片" },
                  { value: "document", label: "笔记" },
                ] as { value: TypeFilter; label: string }[]).map((f) => (
                  <button key={f.value} onClick={() => { setTypeFilter(f.value); setPage(1); }}
                    className={`px-2.5 py-1 rounded-lg text-[10px] font-medium border transition-all ${typeFilter === f.value ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]" : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-accent)]/30"}`}>
                    {f.label}
                  </button>
                ))}
              </div>
              {allTags.length > 0 && (
                <div className="flex items-center gap-1">
                  <Tag size={12} className="text-[var(--color-text-muted)]" />
                  <select value={selectedTag} onChange={(e) => { setSelectedTag(e.target.value); setPage(1); }}
                    className="text-[10px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] px-2 py-1 focus:outline-none focus:border-[var(--color-accent)]">
                    <option value="">全部标签</option>
                    {allTags.map(tag => <option key={tag} value={tag}>{tag}</option>)}
                  </select>
                </div>
              )}
              <div className="flex-1" />
              <div className="flex items-center gap-1">
                <button onClick={() => setViewMode("list")} className={`p-1.5 rounded ${viewMode === "list" ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]" : "text-[var(--color-text-muted)]"}`} title="列表视图"><List size={14} /></button>
                <button onClick={() => setViewMode("grid")} className={`p-1.5 rounded ${viewMode === "grid" ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]" : "text-[var(--color-text-muted)]"}`} title="网格视图"><Grid size={14} /></button>
              </div>
              <div className="relative">
                <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-muted)]" />
                <input value={searchInput} onChange={(e) => { setSearchInput(e.target.value); setPage(1); }} placeholder="搜索文件..."
                  className="w-40 pl-7 pr-2 py-1.5 text-[11px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)]" />
              </div>
              <button onClick={() => setShowCreateFolder(!showCreateFolder)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] font-medium border border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-accent)] hover:text-[var(--color-accent)] transition-all">
                <FolderPlus size={12} /> 新建文件夹
              </button>
              <label className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-medium bg-[var(--color-accent)] text-white hover:opacity-90 cursor-pointer transition-opacity ${uploading ? "opacity-50 pointer-events-none" : ""}`}>
                {uploading ? <Loader2 size={12} className="animate-spin" /> : <Upload size={12} />}
                {uploading ? `${uploadProgress}%` : "上传文件"}
                <input type="file" ref={fileInputRef} className="hidden" onChange={handleUpload} disabled={uploading}
                  accept=".pdf,.docx,.pptx,.xlsx,.md,.txt,.jpg,.jpeg,.png,.gif,.webp,.mp3,.wav" />
              </label>
            </div>

            {uploading && (
              <div className="mb-4 p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]">
                <div className="flex items-center gap-2 mb-1">
                  <Loader2 size={12} className="animate-spin text-[var(--color-accent)]" />
                  <span className="text-[11px] text-[var(--color-text-muted)]">上传中...</span>
                  <span className="text-[11px] font-medium text-[var(--color-accent)]">{uploadProgress}%</span>
                </div>
                <div className="w-full h-1.5 bg-[var(--color-border)] rounded-full overflow-hidden">
                  <div className="h-full bg-[var(--color-accent)] rounded-full transition-all duration-300" style={{ width: `${uploadProgress}%` }} />
                </div>
              </div>
            )}

            {showCreateFolder && (
              <div className="mb-4 p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)] flex items-center gap-2">
                <Folder size={14} className="text-[var(--color-accent)]" />
                <input value={newFolderName} onChange={(e) => setNewFolderName(e.target.value)} placeholder="文件夹名称"
                  className="flex-1 text-[12px] px-2 py-1 rounded border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)]"
                  onKeyDown={(e) => e.key === "Enter" && handleCreateFolder()} autoFocus />
                <button onClick={handleCreateFolder} className="px-2 py-1 text-[11px] rounded bg-[var(--color-accent)] text-white">创建</button>
                <button onClick={() => setShowCreateFolder(false)} className="px-2 py-1 text-[11px] rounded border border-[var(--color-border)] text-[var(--color-text-muted)]">取消</button>
              </div>
            )}

            {selectedFiles.size > 0 && (
              <div className="mb-4 p-3 rounded-lg bg-[var(--color-accent)]/5 border border-[var(--color-accent)]/20 flex items-center gap-3">
                <span className="text-[11px] text-[var(--color-accent)] font-medium">已选择 {selectedFiles.size} 个文件</span>
                <button onClick={() => handleBatchAction("delete")} className="px-2 py-1 text-[10px] rounded bg-red-500/10 text-red-500 hover:bg-red-500/20">删除</button>
                <button onClick={() => setSelectedFiles(new Set())} className="ml-auto text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">取消选择</button>
              </div>
            )}

            {folderBreadcrumbs.length > 0 && (
              <div className="mb-4 flex items-center gap-1 text-[11px]">
                <button onClick={() => navigateToBreadcrumb(-1)} className="flex items-center gap-1 px-2 py-1 rounded hover:bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                  <Home size={12} /> 根目录
                </button>
                {folderBreadcrumbs.map((bc, i) => (
                  <React.Fragment key={bc.id}>
                    <ChevronRight size={10} className="text-[var(--color-text-muted)]" />
                    <button onClick={() => navigateToBreadcrumb(i)}
                      className={`flex items-center gap-1 px-2 py-1 rounded ${i === folderBreadcrumbs.length - 1 ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]" : "hover:bg-[var(--color-surface)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]"}`}>
                      <FolderOpen size={10} /> {bc.name}
                    </button>
                  </React.Fragment>
                ))}
              </div>
            )}

            <div ref={dropZoneRef} onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}
              className={`mb-4 rounded-xl border-2 border-dashed transition-all ${isDragOver ? "border-[var(--color-accent)] bg-[var(--color-accent)]/5" : "border-[var(--color-border)]/50 hover:border-[var(--color-border)]"}`}>
              {isDragOver ? (
                <div className="py-8 text-center">
                  <Upload size={24} className="mx-auto text-[var(--color-accent)] mb-2" />
                  <p className="text-sm text-[var(--color-accent)] font-medium">松开鼠标上传文件</p>
                </div>
              ) : (
                <div className="py-4 text-center">
                  <p className="text-[11px] text-[var(--color-text-muted)]">拖拽文件到此处上传，或点击上传按钮</p>
                </div>
              )}
            </div>

            {folders.length > 0 && viewMode === "list" && (
              <div className="space-y-1 mb-2">
                {folders.map((folder) => (
                  <div key={folder.material_id} onClick={() => navigateToFolder(folder.material_id, folder.file_name)}
                    className="group flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[var(--color-surface)] border border-transparent hover:border-[var(--color-border)]/50 cursor-pointer transition-all">
                    <FolderOpen size={16} className="text-amber-500" />
                    <span className="text-[13px] font-medium text-[var(--color-text)] flex-1">{folder.file_name}</span>
                    <span className="text-[10px] text-[var(--color-text-muted)]">{folder.child_count} 个项目</span>
                    <span className="text-[10px] text-[var(--color-text-muted)]">{formatDate(folder.created_at)}</span>
                  </div>
                ))}
              </div>
            )}

            {loading ? (
              <div className="flex items-center justify-center py-16"><Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" /></div>
            ) : files.length === 0 ? (
              <div className="text-center py-16">
                <div className="w-14 h-14 rounded-2xl bg-[var(--color-surface)] flex items-center justify-center mx-auto mb-3 border border-[var(--color-border)]/50">
                  <Upload size={24} className="text-[var(--color-text-muted)]" />
                </div>
                <p className="text-[14px] font-medium text-[var(--color-text)]">还没有文件</p>
                <p className="text-[11px] text-[var(--color-text-muted)] mt-1 mb-4">上传学习资料后自动解析索引，供 AI 和练习系统参考</p>
                <label className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--color-accent)] text-white text-[12px] font-medium hover:opacity-90 cursor-pointer">
                  <Upload size={14} /> 上传第一个文件
                  <input type="file" className="hidden" onChange={handleUpload} accept=".pdf,.docx,.pptx,.xlsx,.md,.txt,.jpg,.jpeg,.png,.gif,.webp,.mp3,.wav" />
                </label>
              </div>
            ) : viewMode === "list" ? (
              <div className="space-y-1.5">
                <div className="grid grid-cols-[40px_1fr_80px_80px_80px_80px_80px] gap-3 px-3 py-2 text-[10px] font-medium text-[var(--color-text-muted)] uppercase tracking-wider">
                  <span><input type="checkbox" checked={selectedFiles.size === files.length && files.length > 0} onChange={selectAll} className="rounded" /></span>
                  <span>文件名</span>
                  <span>标签</span>
                  <span>大小</span>
                  <span>状态</span>
                  <span>日期</span>
                  <span>操作</span>
                </div>
                {files.map((f) => {
                  const ext = f.file_type?.toLowerCase() || "";
                  const isIndexing = f.status === "uploading" || f.status === "pending";
                  const isFailed = f.status === "index_failed";
                  const isSelected = selectedFiles.has(f.material_id);
                  return (
                    <div key={f.material_id}
                      className={`group grid grid-cols-[40px_1fr_80px_80px_80px_80px_80px] gap-3 items-center px-3 py-2.5 rounded-lg hover:bg-[var(--color-surface)] border transition-all ${isSelected ? "border-[var(--color-accent)]/30 bg-[var(--color-accent)]/5" : "border-transparent hover:border-[var(--color-border)]/50"}`}>
                      <input type="checkbox" checked={isSelected} onChange={() => toggleSelect(f.material_id)} className="rounded" />
                      {f.is_folder ? (
                        <div onClick={() => navigateToFolder(f.material_id, f.file_name)} className="flex items-center gap-2.5 min-w-0 text-[var(--color-text)] hover:text-[var(--color-accent)] cursor-pointer transition-colors">
                          <FolderOpen size={14} className="text-amber-500" />
                          <span className="text-[13px] truncate font-medium">{f.file_name}</span>
                        </div>
                      ) : (
                        <Link href={`/files/${f.material_id}`} className="flex items-center gap-2.5 min-w-0 text-[var(--color-text)] hover:text-[var(--color-accent)] transition-colors">
                          {getFileIcon(ext)}
                          <span className="text-[13px] truncate">{f.file_name}</span>
                          <ExternalLink size={10} className="text-[var(--color-text-muted)] opacity-0 group-hover:opacity-100 shrink-0" />
                        </Link>
                      )}
                      <div className="flex items-center gap-1 flex-wrap">
                        {(f.tags || []).slice(0, 2).map(tag => (
                          <span key={tag} className={`text-[9px] px-1.5 py-0.5 rounded ${getTagColor(tag)}`}>{tag}</span>
                        ))}
                        {(f.tags || []).length > 2 && <span className="text-[9px] text-[var(--color-text-muted)]">+{f.tags.length - 2}</span>}
                      </div>
                      <span className="text-[11px] text-[var(--color-text-muted)]">{f.is_folder ? `${f.toc_count}项` : formatSize(f.file_size)}</span>
                      <span>
                        {isIndexing ? <span className="inline-flex items-center gap-1 text-[10px] text-blue-500"><Loader2 size={10} className="animate-spin" /> 索引中</span>
                          : isFailed ? <span className="inline-flex items-center gap-1 text-[10px] text-red-500"><AlertCircle size={10} /> 失败</span>
                          : <span className="inline-flex items-center gap-1 text-[10px] text-green-500"><CheckCircle size={10} /> {f.chunk_count}块</span>}
                      </span>
                      <span className="text-[11px] text-[var(--color-text-muted)]">{formatDate(f.created_at)}</span>
                      <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        {!f.is_folder && (
                          <>
                            <button onClick={() => handlePreview(f)} className="p-1 rounded text-[var(--color-text-muted)] hover:text-blue-500 hover:bg-blue-500/10" title="预览"><Eye size={12} /></button>
                            <button onClick={() => handleDownload(f)} className="p-1 rounded text-[var(--color-text-muted)] hover:text-green-500 hover:bg-green-500/10" title="下载"><Download size={12} /></button>
                          </>
                        )}
                        <button onClick={() => openEdit(f)} className="p-1 rounded text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-accent)]/10" title="编辑"><Pencil size={12} /></button>
                        <button onClick={() => handleDelete(f.material_id)} disabled={deleting === f.material_id}
                          className="p-1 rounded text-[var(--color-text-muted)] hover:text-red-500 hover:bg-red-500/10" title="删除">
                          {deleting === f.material_id ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
                {files.map((f) => {
                  const ext = f.file_type?.toLowerCase() || "";
                  const isIndexing = f.status === "uploading" || f.status === "pending";
                  return (
                    <div key={f.material_id} className="group relative p-3 rounded-lg bg-[var(--color-surface)] border border-[var(--color-border)]/50 hover:border-[var(--color-accent)]/30 transition-all">
                      <div className="flex flex-col items-center text-center">
                        {f.is_folder ? <FolderOpen size={32} className="text-amber-500 mb-2" />
                          : <div className="w-12 h-12 rounded-lg bg-[var(--color-bg)] flex items-center justify-center mb-2">{getFileIcon(ext)}</div>}
                        <p className="text-[11px] font-medium text-[var(--color-text)] truncate w-full">{f.file_name}</p>
                        <p className="text-[9px] text-[var(--color-text-muted)] mt-0.5">{f.is_folder ? `${f.toc_count}项` : formatSize(f.file_size)}</p>
                        {(f.tags || []).length > 0 && (
                          <div className="flex items-center gap-0.5 mt-1 flex-wrap justify-center">
                            {(f.tags || []).slice(0, 2).map(tag => <span key={tag} className={`text-[8px] px-1 py-0.5 rounded ${getTagColor(tag)}`}>{tag}</span>)}
                          </div>
                        )}
                        {isIndexing && <span className="text-[9px] text-blue-500 mt-1 flex items-center gap-0.5"><Loader2 size={8} className="animate-spin" /> 索引中</span>}
                      </div>
                      <div className="absolute top-1 right-1 hidden group-hover:flex items-center gap-0.5 bg-[var(--color-surface)] rounded-md p-0.5 shadow-sm">
                        {!f.is_folder && <button onClick={() => handlePreview(f)} className="p-0.5 rounded hover:bg-[var(--color-accent)]/10 text-[var(--color-text-muted)] hover:text-blue-500"><Eye size={10} /></button>}
                        <button onClick={() => openEdit(f)} className="p-0.5 rounded hover:bg-[var(--color-accent)]/10 text-[var(--color-text-muted)] hover:text-[var(--color-accent)]"><Pencil size={10} /></button>
                        <button onClick={() => handleDelete(f.material_id)} className="p-0.5 rounded hover:bg-red-100 text-[var(--color-text-muted)] hover:text-red-500"><Trash2 size={10} /></button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-6">
                <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}
                  className="px-3 py-1.5 text-[11px] rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-30">上一页</button>
                <span className="text-[11px] text-[var(--color-text-muted)]">{page} / {totalPages}</span>
                <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
                  className="px-3 py-1.5 text-[11px] rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)] disabled:opacity-30">下一页</button>
              </div>
            )}

            {editFile && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => setEditFile(null)}>
                <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] w-full max-w-sm mx-4 p-5 shadow-xl" onClick={(e) => e.stopPropagation()}>
                  <h3 className="text-[14px] font-semibold text-[var(--color-text)] mb-4">编辑文件</h3>
                  <div className="space-y-3">
                    <div>
                      <label className="text-[10px] text-[var(--color-text-muted)] block mb-1">文件名</label>
                      <input value={editName} onChange={(e) => setEditName(e.target.value)}
                        className="w-full px-3 py-2 text-[12px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)]" />
                    </div>
                    <div>
                      <label className="text-[10px] text-[var(--color-text-muted)] block mb-1">标签</label>
                      <div className="flex items-center gap-1 flex-wrap mb-1">
                        {editTags.map(tag => (
                          <span key={tag} className={`inline-flex items-center gap-0.5 text-[10px] px-2 py-0.5 rounded ${getTagColor(tag)}`}>
                            {tag}
                            <button onClick={() => removeTag(tag)} className="hover:opacity-70"><X size={8} /></button>
                          </span>
                        ))}
                      </div>
                      <div className="flex items-center gap-1">
                        <input value={editTagInput} onChange={(e) => setEditTagInput(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addTag())}
                          placeholder="输入标签后回车"
                          className="flex-1 px-2 py-1.5 text-[11px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)]" />
                        <button onClick={addTag} className="px-2 py-1.5 text-[11px] rounded bg-[var(--color-accent)]/10 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20"><Tag size={12} /></button>
                      </div>
                    </div>
                    <div>
                      <label className="text-[10px] text-[var(--color-text-muted)] block mb-1">所属层级</label>
                      <select value={editLevel} onChange={(e) => setEditLevel(e.target.value)}
                        className="w-full px-3 py-2 text-[12px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)]">
                        <option value="dir">目录</option>
                        <option value="node">节点</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-[10px] text-[var(--color-text-muted)] block mb-1">归属 ID</label>
                      <input value={editParentId} onChange={(e) => setEditParentId(e.target.value)} placeholder="留空表示未分类"
                        className="w-full px-3 py-2 text-[12px] rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] focus:outline-none focus:border-[var(--color-accent)]" />
                    </div>
                  </div>
                  <div className="flex items-center justify-end gap-2 mt-4">
                    <button onClick={() => setEditFile(null)} className="px-3 py-1.5 text-[11px] rounded-lg border border-[var(--color-border)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]">取消</button>
                    <button onClick={handleSaveEdit} disabled={saving}
                      className="px-3 py-1.5 text-[11px] rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-1">
                      {saving ? <Loader2 size={10} className="animate-spin" /> : <Check size={10} />}
                      {saving ? "保存中..." : "保存"}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {previewFile && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setPreviewFile(null)}>
                <div className="bg-[var(--color-surface)] rounded-xl border border-[var(--color-border)] w-full max-w-3xl mx-4 p-4 shadow-xl max-h-[80vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-[14px] font-semibold text-[var(--color-text)]">{previewFile.file_name}</h3>
                    <button onClick={() => setPreviewFile(null)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]"><X size={16} /></button>
                  </div>
                  <div className="flex items-center justify-center bg-[var(--color-bg)] rounded-lg min-h-[300px]">
                    {["jpg", "jpeg", "png", "gif", "webp", "bmp"].includes(previewFile.file_type?.toLowerCase() || "") ? (
                      <img src={`${API_BASE}/api/files/${previewFile.material_id}/download`} alt={previewFile.file_name} className="max-w-full max-h-[60vh] object-contain rounded" />
                    ) : previewFile.file_type?.toLowerCase() === "pdf" ? (
                      <iframe src={`${API_BASE}/api/files/${previewFile.material_id}/download`} className="w-full h-[60vh] rounded" title="PDF预览" />
                    ) : (
                      <div className="text-center py-10">
                        <FileText size={40} className="mx-auto text-[var(--color-text-muted)] mb-3" />
                        <p className="text-sm text-[var(--color-text-muted)]">此文件类型不支持预览</p>
                        <button onClick={() => handleDownload(previewFile)} className="mt-2 px-3 py-1.5 text-xs rounded bg-[var(--color-accent)] text-white">下载文件</button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {tab === "stats" && (
          <div className="space-y-6">
            {stats ? (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50">
                    <div className="flex items-center gap-2 mb-2"><FileText size={16} className="text-[var(--color-accent)]" /><span className="text-[11px] text-[var(--color-text-muted)]">文件总数</span></div>
                    <p className="text-2xl font-bold text-[var(--color-text)]">{stats.total_files}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50">
                    <div className="flex items-center gap-2 mb-2"><HardDrive size={16} className="text-green-500" /><span className="text-[11px] text-[var(--color-text-muted)]">总大小</span></div>
                    <p className="text-2xl font-bold text-[var(--color-text)]">{stats.total_size_formatted}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50">
                    <div className="flex items-center gap-2 mb-2"><Folder size={16} className="text-amber-500" /><span className="text-[11px] text-[var(--color-text-muted)]">文件夹</span></div>
                    <p className="text-2xl font-bold text-[var(--color-text)]">{stats.folder_count}</p>
                  </div>
                  <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50">
                    <div className="flex items-center gap-2 mb-2"><Trash2 size={16} className="text-red-500" /><span className="text-[11px] text-[var(--color-text-muted)]">回收站</span></div>
                    <p className="text-2xl font-bold text-[var(--color-text)]">{stats.trash_count}</p>
                  </div>
                </div>
                <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50">
                  <h3 className="text-[13px] font-semibold text-[var(--color-text)] mb-3">文件类型分布</h3>
                  <div className="space-y-2">
                    {stats.by_type.map((t) => (
                      <div key={t.file_type} className="flex items-center gap-3">
                        <span className="text-[11px] text-[var(--color-text)] w-16 uppercase">{t.file_type || "其他"}</span>
                        <div className="flex-1 h-2 bg-[var(--color-border)] rounded-full overflow-hidden">
                          <div className="h-full bg-[var(--color-accent)] rounded-full" style={{ width: `${stats.total_files > 0 ? (t.count / stats.total_files) * 100 : 0}%` }} />
                        </div>
                        <span className="text-[10px] text-[var(--color-text-muted)] w-16 text-right">{t.count} 个 ({formatSize(t.total_size)})</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50">
                  <h3 className="text-[13px] font-semibold text-[var(--color-text)] mb-3">最近上传</h3>
                  <div className="space-y-2">
                    {stats.recent_files.map((f) => (
                      <div key={f.material_id} className="flex items-center gap-3">
                        {getFileIcon(f.file_type?.toLowerCase() || "")}
                        <span className="text-[12px] text-[var(--color-text)] flex-1 truncate">{f.file_name}</span>
                        <span className="text-[10px] text-[var(--color-text-muted)]">{formatSize(f.file_size)}</span>
                        <span className="text-[10px] text-[var(--color-text-muted)]">{formatDate(f.created_at)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="flex items-center justify-center py-16"><Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" /></div>
            )}
          </div>
        )}

        {tab === "trash" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <p className="text-[12px] text-[var(--color-text-muted)]">回收站中的文件将保留 30 天</p>
              {trashFiles.length > 0 && (
                <button onClick={handleEmptyTrash} className="px-3 py-1.5 text-[11px] rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 font-medium">清空回收站</button>
              )}
            </div>
            {loading ? (
              <div className="flex items-center justify-center py-16"><Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" /></div>
            ) : trashFiles.length === 0 ? (
              <div className="text-center py-16">
                <div className="w-14 h-14 rounded-2xl bg-[var(--color-surface)] flex items-center justify-center mx-auto mb-3 border border-[var(--color-border)]/50"><Trash2 size={24} className="text-[var(--color-text-muted)]" /></div>
                <p className="text-[14px] font-medium text-[var(--color-text)]">回收站为空</p>
                <p className="text-[11px] text-[var(--color-text-muted)] mt-1">删除的文件会出现在这里</p>
              </div>
            ) : (
              <div className="space-y-1.5">
                {trashFiles.map((f) => (
                  <div key={f.material_id} className="group flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-[var(--color-surface)] border border-transparent hover:border-[var(--color-border)]/50 transition-all">
                    {getFileIcon(f.file_type?.toLowerCase() || "")}
                    <span className="text-[13px] text-[var(--color-text)] flex-1 truncate">{f.file_name}</span>
                    <span className="text-[10px] text-[var(--color-text-muted)]">{formatSize(f.file_size)}</span>
                    <span className="text-[10px] text-red-400 flex items-center gap-1"><Clock size={10} /> {f.deleted_at ? formatDate(f.deleted_at) : ""}</span>
                    <div className="flex items-center gap-1">
                      <button onClick={() => handleRestore(f.material_id)} className="px-2 py-1 text-[10px] rounded bg-green-500/10 text-green-500 hover:bg-green-500/20 font-medium flex items-center gap-1"><RefreshCw size={10} /> 恢复</button>
                      <button onClick={() => handlePermanentDelete(f.material_id)} className="px-2 py-1 text-[10px] rounded bg-red-500/10 text-red-500 hover:bg-red-500/20 font-medium flex items-center gap-1"><Trash2 size={10} /> 删除</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {tab === "banks" && (
          <>
            <div className="flex items-center justify-between mb-4">
              <p className="text-[12px] text-[var(--color-text-muted)]">共 {banks.length} 个题库</p>
              <Link href="/import" className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--color-accent)] text-white text-[12px] font-medium hover:opacity-90">
                <Upload size={14} /> 导入题库
              </Link>
            </div>
            {loading ? (
              <div className="flex items-center justify-center py-16"><Loader2 size={20} className="animate-spin text-[var(--color-text-muted)]" /></div>
            ) : banks.length === 0 ? (
              <div className="text-center py-16">
                <div className="w-14 h-14 rounded-2xl bg-[var(--color-surface)] flex items-center justify-center mx-auto mb-3 border border-[var(--color-border)]/50"><Library size={24} className="text-[var(--color-text-muted)]" /></div>
                <p className="text-[14px] font-medium text-[var(--color-text)]">还没有题库</p>
                <p className="text-[11px] text-[var(--color-text-muted)] mt-1 mb-4">导入或创建题库，开始练习</p>
                <Link href="/import" className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[var(--color-accent)] text-white text-[12px] font-medium hover:opacity-90"><Upload size={14} /> 导入题库</Link>
              </div>
            ) : (
              <div className="space-y-2">
                {banks.map((bank) => (
                  <div key={bank.id} className="flex items-center gap-3 p-4 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 hover:border-[var(--color-accent)]/30 transition-all group">
                    <div className="w-10 h-10 rounded-lg bg-violet-500/10 flex items-center justify-center shrink-0"><Library size={18} className="text-violet-500" /></div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h3 className="text-[13px] font-medium text-[var(--color-text)] truncate">{bank.name}</h3>
                        {bank.auto_created && <span className="text-[9px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-500 shrink-0">自动</span>}
                      </div>
                      {bank.description && <p className="text-[10px] text-[var(--color-text-muted)] mt-0.5 line-clamp-1">{bank.description}</p>}
                      <div className="flex items-center gap-3 mt-1.5">
                        <span className="text-[10px] text-[var(--color-text-muted)]">{bank.question_count} 题</span>
                        {bank.ref_node_label && <span className="text-[10px] text-violet-500/70">关联: {bank.ref_node_label}</span>}
                      </div>
                    </div>
                    <div className="flex gap-2 shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Link href={`/practice/banks/${bank.id}`} className="px-3 py-1.5 rounded-lg bg-[var(--color-accent)]/10 text-[var(--color-accent)] hover:bg-[var(--color-accent)]/20 text-[10px] font-medium transition-colors">管理</Link>
                      <Link href={`/practice?tab=practice&bank=${bank.id}`} className="px-3 py-1.5 rounded-lg bg-green-500/10 text-green-600 hover:bg-green-500/20 text-[10px] font-medium transition-colors flex items-center gap-1"><Play size={10} /> 练习</Link>
                      <button onClick={() => handleDeleteBank(bank.id)} disabled={deletingBank === bank.id}
                        className="px-2 py-1.5 rounded-lg bg-red-500/10 text-red-500 hover:bg-red-500/20 text-[10px] font-medium transition-colors flex items-center gap-1" title="删除题库">
                        {deletingBank === bank.id ? <Loader2 size={10} className="animate-spin" /> : <Trash2 size={10} />} 删除
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
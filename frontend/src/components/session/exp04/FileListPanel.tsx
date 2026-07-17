"use client";

import { useState, useRef, useCallback } from "react";
import {
  X, FileText, BookOpen, Brain, Link, PenTool,
  Upload, Download, Loader2, FileIcon,
} from "lucide-react";

// ── Props ──────────────────────────────────────────────────

interface Props {
  sessionTitle?: string;
  open: boolean;
  onClose: () => void;
}

// ── Types ──────────────────────────────────────────────────

interface SavedDrawing {
  id: string;
  dataUrl: string;
  timestamp: number;
}

interface UploadedFile {
  material_id: string;
  file_name: string;
  file_size: number;
  file_type: string;
  purpose: string;
  status: string;
}

const STORAGE_KEY = "hw_saved_drawings";

// ── Helpers ────────────────────────────────────────────────

const FILE_ICON_MAP: Record<string, { icon: React.ReactNode; bg: string }> = {
  note: { icon: <FileText size={18} />, bg: "#ccfbf1" },
  book: { icon: <BookOpen size={18} />, bg: "#fee2e2" },
  flashcard: { icon: <Brain size={18} />, bg: "#ede9fe" },
  link: { icon: <Link size={18} />, bg: "#fef3c7" },
  handwrite: { icon: <PenTool size={18} />, bg: "#fef3c7" },
};

const UPLOAD_ICONS: Record<string, { icon: React.ReactNode; bg: string }> = {
  pdf: { icon: <FileText size={18} />, bg: "#fee2e2" },
  docx: { icon: <FileText size={18} />, bg: "#dbeafe" },
  image: { icon: <FileIcon size={18} />, bg: "#fce7f3" },
  document: { icon: <FileText size={18} />, bg: "#ccfbf1" },
  code: { icon: <FileIcon size={18} />, bg: "#e0e7ff" },
  audio: { icon: <FileIcon size={18} />, bg: "#ede9fe" },
  other: { icon: <FileIcon size={18} />, bg: "#f3f4f6" },
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTime(ts: number) {
  const d = new Date(ts);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function loadDrawings(): SavedDrawing[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function buildFiles(sessionTitle?: string) {
  const isLinear = sessionTitle?.includes("矩阵") || sessionTitle?.includes("线性");
  return [
    { ...FILE_ICON_MAP.note, name: isLinear ? "矩阵乘法笔记.md" : "递归笔记.md", meta: "上次学习 · 你写的" },
    { ...FILE_ICON_MAP.book, name: isLinear ? "线性代数及其应用.pdf" : "算法图解.pdf", meta: "还在读" },
    { ...FILE_ICON_MAP.flashcard, name: "闪卡合集", meta: "FSRS 调度中" },
    { ...FILE_ICON_MAP.link, name: sessionTitle ? `上次学习 · ${sessionTitle}` : "上次学习 · 学习 Session", meta: "链接到上次内容" },
  ];
}

// ── Upload helper ─────────────────────────────────────────

async function uploadFile(file: File): Promise<UploadedFile> {
  const form = new FormData();
  form.append("file", file);
  form.append("purpose", "session");
  form.append("upload_source", "session_tool");

  const res = await fetch("/api/files/upload", {
    method: "POST",
    credentials: "include",
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "上传失败" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return res.json();
}

// ── Component ─────────────────────────────────────────────

export default function FileListPanel({ sessionTitle, open, onClose }: Props) {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Handle file select ──

  const handleFileSelect = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setUploadError(null);

    try {
      const result = await uploadFile(file);
      setUploadedFiles((prev) => [result, ...prev]);
    } catch (err: any) {
      setUploadError(err.message || "上传失败");
    } finally {
      setUploading(false);
      // Reset input so the same file can be selected again
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }, []);

  // ── Compute file icon ──

  const getUploadIcon = (ft: string) => UPLOAD_ICONS[ft] || UPLOAD_ICONS.other;

  // ── Render time for uploaded files ──

  if (!open) return null;

  const files = buildFiles(sessionTitle);
  const savedDrawings = loadDrawings();

  return (
    <div className="fixed inset-0 z-[100] bg-black/30 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-surface rounded-2xl shadow-xl border border-border/50 w-full max-w-sm relative animate-in zoom-in-95 duration-300 max-h-[80vh] flex flex-col">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-ink-muted hover:text-ink-secondary transition-colors z-10"
          aria-label="关闭文件"
        >
          <X size={18} />
        </button>

        <div className="p-6 pt-8 flex-1 overflow-y-auto">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-ink-primary">知识文件</h2>

            {/* Upload button */}
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-accent text-white text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
            >
              {uploading ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Upload size={14} />
              )}
              {uploading ? "上传中..." : "上传"}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={handleFileSelect}
              accept="*"
            />
          </div>

          {/* Upload error */}
          {uploadError && (
            <div className="mb-3 px-3 py-2 rounded-lg bg-danger/10 text-xs text-danger border border-danger/20">
              {uploadError}
            </div>
          )}

          <div className="space-y-3">
            {/* Uploaded files */}
            {uploadedFiles.length > 0 && (
              <>
                {uploadedFiles.map((f) => {
                  const ui = getUploadIcon(f.file_type);
                  return (
                    <a
                      key={f.material_id}
                      href={`/api/files/${f.material_id}/download`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-3 px-3 py-3 rounded-xl border border-border/50 hover:border-border hover:shadow-sm transition-all cursor-pointer group"
                    >
                      <span
                        className="w-10 h-10 rounded-xl grid place-items-center flex-shrink-0"
                        style={{ background: ui.bg }}
                      >
                        {ui.icon}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-semibold text-ink-primary truncate">
                          {f.file_name}
                        </p>
                        <p className="text-xs text-ink-muted">
                          {formatSize(f.file_size)} · {f.file_type} · {f.status}
                        </p>
                      </div>
                      <Download size={14} className="text-ink-muted opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0" />
                    </a>
                  );
                })}
                <hr className="border-border/40 my-2" />
              </>
            )}

            {/* Static files */}
            {files.map((file, i) => (
              <div
                key={i}
                className="flex items-center gap-3 px-3 py-3 rounded-xl border border-border/50 hover:border-border hover:shadow-sm transition-all cursor-default"
              >
                <span
                  className="w-10 h-10 rounded-xl grid place-items-center flex-shrink-0"
                  style={{ background: file.bg }}
                >
                  {file.icon}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-ink-primary truncate">
                    {file.name}
                  </p>
                  <p className="text-xs text-ink-muted">{file.meta}</p>
                </div>
              </div>
            ))}

            {/* Saved handwrite drawings */}
            {savedDrawings.length > 0 && (
              <>
                <hr className="border-border/40 my-2" />
                <p className="text-[11px] font-semibold text-ink-muted uppercase tracking-wider mb-2">
                  手写笔记 · {savedDrawings.length} 张
                </p>
                {savedDrawings.slice(0, 3).map((d) => (
                  <div
                    key={d.id}
                    className="flex items-center gap-3 px-3 py-3 rounded-xl border border-border/50 hover:border-border hover:shadow-sm transition-all cursor-pointer"
                    onClick={() => window.open(d.dataUrl, "_blank")}
                  >
                    <span
                      className="w-10 h-10 rounded-xl grid place-items-center flex-shrink-0 overflow-hidden"
                      style={{ background: FILE_ICON_MAP.handwrite.bg }}
                    >
                      <img
                        src={d.dataUrl}
                        alt="手写缩略图"
                        className="w-full h-full object-cover"
                      />
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-ink-primary truncate">
                        手写笔记
                      </p>
                      <p className="text-xs text-ink-muted">
                        {formatTime(d.timestamp)}
                      </p>
                    </div>
                  </div>
                ))}
                {savedDrawings.length > 3 && (
                  <p className="text-xs text-ink-muted text-center pt-1">
                    +{savedDrawings.length - 3} 张更多
                  </p>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

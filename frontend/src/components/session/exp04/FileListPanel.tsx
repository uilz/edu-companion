"use client";

import { X, FileText, BookOpen, Brain, Link, PenTool } from "lucide-react";

// ── Props ──────────────────────────────────────────────────

interface Props {
  sessionTitle?: string;
  open: boolean;
  onClose: () => void;
}

// ── Saved drawing type ────────────────────────────────────

interface SavedDrawing {
  id: string;
  dataUrl: string;
  timestamp: number;
}

const STORAGE_KEY = "hw_saved_drawings";

// ── Helpers ────────────────────────────────────────────────

const ICON_MAP: Record<string, { icon: React.ReactNode; bg: string }> = {
  note: { icon: <FileText size={18} />, bg: "var(--color-teal-soft, #ccfbf1)" },
  book: { icon: <BookOpen size={18} />, bg: "var(--color-danger-soft, #fee2e2)" },
  flashcard: { icon: <Brain size={18} />, bg: "var(--color-purple-soft, #ede9fe)" },
  link: { icon: <Link size={18} />, bg: "var(--color-accent-soft, #fef3c7)" },
  handwrite: { icon: <PenTool size={18} />, bg: "var(--color-warning-soft, #fef3c7)" },
};

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
    { type: "note" as const, ...ICON_MAP.note, name: isLinear ? "矩阵乘法笔记.md" : "递归笔记.md", meta: "上次学习 · 你写的" },
    { type: "book" as const, ...ICON_MAP.book, name: isLinear ? "线性代数及其应用.pdf" : "算法图解.pdf", meta: "还在读" },
    { type: "flashcard" as const, ...ICON_MAP.flashcard, name: "闪卡合集", meta: "FSRS 调度中" },
    { type: "link" as const, ...ICON_MAP.link, name: sessionTitle ? `上次学习 · ${sessionTitle}` : "上次学习 · 学习 Session", meta: "链接到上次内容" },
  ];
}

// ── Format timestamp ──

function formatTime(ts: number) {
  const d = new Date(ts);
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

// ── Component ─────────────────────────────────────────────

export default function FileListPanel({ sessionTitle, open, onClose }: Props) {
  if (!open) return null;

  const files = buildFiles(sessionTitle);
  const savedDrawings = loadDrawings();
  const latestDrawing = savedDrawings[0];

  return (
    <div className="fixed inset-0 z-[100] bg-black/30 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="bg-surface rounded-2xl shadow-xl border border-border/50 w-full max-w-sm relative animate-in zoom-in-95 duration-300 max-h-[80vh] overflow-y-auto">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-ink-muted hover:text-ink-secondary transition-colors z-10"
          aria-label="关闭文件"
        >
          <X size={18} />
        </button>

        <div className="p-6 pt-8">
          <h2 className="text-base font-semibold text-ink-primary mb-4">
            知识文件
          </h2>

          <div className="space-y-3">
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
                      style={{ background: ICON_MAP.handwrite.bg }}
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

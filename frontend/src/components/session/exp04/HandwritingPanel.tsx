"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { X, Trash2, Save, Image as ImageIcon, PenTool } from "lucide-react";

// ── Props ──────────────────────────────────────────────────

interface Props {
  open: boolean;
  onClose: () => void;
}

// ── Saved drawing type ────────────────────────────────────

interface SavedDrawing {
  id: string;
  dataUrl: string;
  timestamp: number;
  materialId?: string;   // server-side material_id for cross-device
}

const STORAGE_KEY = "hw_saved_drawings";

// ── localStorage helpers ──────────────────────────────────

function loadDrawings(): SavedDrawing[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveDrawings(drawings: SavedDrawing[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(drawings));
  } catch {
    // localStorage full or unavailable — silently ignore
  }
}

// ── Color options ─────────────────────────────────────────

const COLORS = [
  { label: "黑色", value: "#1c1c1e" },
  { label: "蓝色", value: "#0a84ff" },
  { label: "红色", value: "#ff3b30" },
  { label: "绿色", value: "#34c759" },
];

type ViewMode = "draw" | "gallery";

// ── Component ─────────────────────────────────────────────

export default function HandwritingPanel({ open, onClose }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeColor, setActiveColor] = useState(COLORS[0].value);
  const drawingRef = useRef(false);
  const lastRef = useRef<{ x: number; y: number } | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("draw");
  const [savedDrawings, setSavedDrawings] = useState<SavedDrawing[]>([]);
  const [savedToast, setSavedToast] = useState(false);
  const [savingToBackend, setSavingToBackend] = useState(false);

  // ── Load saved drawings on open ──

  useEffect(() => {
    if (!open) return;
    setViewMode("draw");
    setSavedDrawings(loadDrawings());
  }, [open]);

  // ── Initialize canvas ──

  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
  }, []);

  useEffect(() => {
    if (!open || viewMode !== "draw") return;
    const id = setTimeout(() => resizeCanvas(), 50);
    window.addEventListener("resize", resizeCanvas);
    return () => {
      clearTimeout(id);
      window.removeEventListener("resize", resizeCanvas);
    };
  }, [open, viewMode, resizeCanvas]);

  // ── Drawing logic ──

  const getPos = (e: React.MouseEvent | React.TouchEvent): { x: number; y: number } | null => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const pt = "touches" in e ? e.touches[0] : e;
    if (!pt) return null;
    return { x: pt.clientX - rect.left, y: pt.clientY - rect.top };
  };

  const startDraw = (e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    drawingRef.current = true;
    const pos = getPos(e);
    if (pos) lastRef.current = pos;
  };

  const draw = (e: React.MouseEvent | React.TouchEvent) => {
    if (!drawingRef.current) return;
    e.preventDefault();
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    const pos = getPos(e);
    if (!ctx || !pos || !lastRef.current) return;
    ctx.strokeStyle = activeColor;
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    ctx.moveTo(lastRef.current.x, lastRef.current.y);
    ctx.lineTo(pos.x, pos.y);
    ctx.stroke();
    lastRef.current = pos;
  };

  const stopDraw = () => {
    drawingRef.current = false;
    lastRef.current = null;
  };

  // ── Clear ──

  const clearCanvas = () => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!ctx || !canvas) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  };

  // ── Save (localStorage + backend upload) ──

  const saveCanvas = async () => {
    const canvas = canvasRef.current;
    if (!canvas || savingToBackend) return;

    const dataUrl = canvas.toDataURL("image/png");

    // 1. Save to localStorage immediately (offline fallback)
    const drawing: SavedDrawing = {
      id: `hw_${Date.now()}`,
      dataUrl,
      timestamp: Date.now(),
    };
    const updated = [drawing, ...savedDrawings].slice(0, 20);
    setSavedDrawings(updated);
    saveDrawings(updated);
    setSavedToast(true);
    setTimeout(() => setSavedToast(false), 2000);

    // 2. Upload to backend (cross-device persistence)
    try {
      setSavingToBackend(true);
      const blob = await new Promise<Blob | null>((resolve) => {
        canvas.toBlob((b) => resolve(b), "image/png");
      });
      if (!blob) return;

      const form = new FormData();
      form.append("file", blob, `handwrite_${Date.now()}.png`);
      form.append("purpose", "session");
      form.append("upload_source", "session_tool");

      const res = await fetch("/api/files/upload", {
        method: "POST",
        credentials: "include",
        body: form,
      });

      if (res.ok) {
        const data = await res.json();
        // Tag the local drawing with the server material_id
        const tagged: SavedDrawing = { ...drawing, materialId: data.material_id };
        const withTag = [tagged, ...updated.slice(1)];
        setSavedDrawings(withTag);
        saveDrawings(withTag);
      }
    } catch {
      // Backend unavailable — localStorage copy is sufficient
    } finally {
      setSavingToBackend(false);
    }
  };

  // ── Delete drawing ──

  const deleteDrawing = (id: string) => {
    const updated = savedDrawings.filter((d) => d.id !== id);
    setSavedDrawings(updated);
    saveDrawings(updated);
  };

  // ── Format timestamp ──

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] bg-black/30 backdrop-blur-sm flex flex-col animate-in fade-in duration-200">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-surface/90 backdrop-blur border-b border-border/50">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode("draw")}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              viewMode === "draw"
                ? "bg-accent text-white"
                : "text-ink-muted hover:text-ink-secondary"
            }`}
          >
            <PenTool size={14} className="inline mr-1" />
            书写
          </button>
          <button
            onClick={() => setViewMode("gallery")}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
              viewMode === "gallery"
                ? "bg-accent text-white"
                : "text-ink-muted hover:text-ink-secondary"
            }`}
          >
            <ImageIcon size={14} className="inline mr-1" />
            历史
            {savedDrawings.length > 0 && (
              <span className="ml-1 text-[10px] opacity-80">({savedDrawings.length})</span>
            )}
          </button>
        </div>
        <button
          onClick={onClose}
          className="text-ink-muted hover:text-ink-secondary transition-colors"
          aria-label="关闭手写"
        >
          <X size={20} />
        </button>
      </div>

      {viewMode === "draw" ? (
        /* ── Draw mode ── */
        <div ref={containerRef} className="flex-1 relative overflow-hidden bg-white">
          <canvas
            ref={canvasRef}
            className="absolute inset-0 touch-none cursor-crosshair"
            onMouseDown={startDraw}
            onMouseMove={draw}
            onMouseUp={stopDraw}
            onMouseLeave={stopDraw}
            onTouchStart={startDraw}
            onTouchMove={draw}
            onTouchEnd={stopDraw}
          />

          {/* Save toast */}
          {savedToast && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-accent text-white text-xs font-medium px-3 py-1.5 rounded-full shadow-md animate-in fade-in slide-in-from-top-2">
              已保存
              {savingToBackend && <span className="ml-1 opacity-80">· 同步中...</span>}
            </div>
          )}

          {/* Toolbar */}
          <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-1 bg-ink-primary/90 backdrop-blur rounded-full px-3 py-1.5">
            {COLORS.map((c) => (
              <button
                key={c.value}
                onClick={() => setActiveColor(c.value)}
                className={`w-7 h-7 rounded-full grid place-items-center transition-all ${
                  activeColor === c.value ? "ring-2 ring-white scale-110" : ""
                }`}
                aria-label={c.label}
              >
                <span
                  className="w-5 h-5 rounded-full border-2 border-white/60"
                  style={{ background: c.value }}
                />
              </button>
            ))}
            <span className="w-px h-5 bg-white/20 mx-1" />
            <button
              onClick={clearCanvas}
              className="w-7 h-7 rounded-full grid place-items-center text-white/70 hover:text-white hover:bg-white/10 transition-colors"
              aria-label="清空"
            >
              <Trash2 size={14} />
            </button>
            <span className="w-px h-5 bg-white/20 mx-1" />
            <button
              onClick={saveCanvas}
              className="w-7 h-7 rounded-full grid place-items-center text-white/70 hover:text-white hover:bg-white/10 transition-colors"
              aria-label="保存"
            >
              <Save size={14} />
            </button>
          </div>
        </div>
      ) : (
        /* ── Gallery mode ── */
        <div className="flex-1 overflow-y-auto bg-page p-4">
          {savedDrawings.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-ink-muted">
              <ImageIcon size={40} className="opacity-40 mb-3" />
              <p className="text-sm">暂无保存的手写笔记</p>
              <p className="text-xs mt-1">写完后点击保存按钮即可保存到这里</p>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-3">
              {savedDrawings.map((d) => (
                <div
                  key={d.id}
                  className="bg-surface rounded-xl border border-border/50 overflow-hidden group relative"
                >
                  <img
                    src={d.dataUrl}
                    alt={`手写笔记 ${formatTime(d.timestamp)}`}
                    className="w-full h-36 object-contain bg-white cursor-pointer"
                    onClick={() => window.open(d.dataUrl, "_blank")}
                  />
                  <div className="px-2 py-1.5 flex items-center justify-between">
                    <span className="text-[10px] text-ink-muted">
                      {formatTime(d.timestamp)}
                      {d.materialId && <span className="ml-1 text-teal-500 font-medium">· 已同步</span>}
                    </span>
                    <button
                      onClick={() => deleteDrawing(d.id)}
                      className="text-[10px] text-danger hover:text-danger/80 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      删除
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

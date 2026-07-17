"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { X, Trash2 } from "lucide-react";

// ── Props ──────────────────────────────────────────────────

interface Props {
  open: boolean;
  onClose: () => void;
}

// ── Color options ─────────────────────────────────────────

const COLORS = [
  { label: "黑色", value: "#1c1c1e" },
  { label: "蓝色", value: "#0a84ff" },
  { label: "红色", value: "#ff3b30" },
  { label: "绿色", value: "#34c759" },
];

// ── Component ─────────────────────────────────────────────

export default function HandwritingPanel({ open, onClose }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [activeColor, setActiveColor] = useState(COLORS[0].value);
  const drawingRef = useRef(false);
  const lastRef = useRef<{ x: number; y: number } | null>(null);

  // ── Initialize canvas ──

  const resizeCanvas = useCallback(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
  }, []);

  useEffect(() => {
    if (!open) return;
    // Wait for DOM
    const id = setTimeout(() => {
      resizeCanvas();
    }, 50);
    window.addEventListener("resize", resizeCanvas);
    return () => {
      clearTimeout(id);
      window.removeEventListener("resize", resizeCanvas);
    };
  }, [open, resizeCanvas]);

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

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] bg-black/30 backdrop-blur-sm flex flex-col animate-in fade-in duration-200">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-3 bg-surface/90 backdrop-blur border-b border-border/50">
        <span className="text-sm font-semibold text-ink-primary">手写演算</span>
        <button
          onClick={onClose}
          className="text-ink-muted hover:text-ink-secondary transition-colors"
          aria-label="关闭手写"
        >
          <X size={20} />
        </button>
      </div>

      {/* Canvas area */}
      <div
        ref={containerRef}
        className="flex-1 relative overflow-hidden bg-white"
      >
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

        {/* Toolbar */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-1 bg-ink-primary/90 backdrop-blur rounded-full px-3 py-1.5">
          {COLORS.map((c) => (
            <button
              key={c.value}
              onClick={() => setActiveColor(c.value)}
              className={`w-7 h-7 rounded-full grid place-items-center transition-all ${
                activeColor === c.value
                  ? "ring-2 ring-white scale-110"
                  : ""
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
        </div>
      </div>
    </div>
  );
}

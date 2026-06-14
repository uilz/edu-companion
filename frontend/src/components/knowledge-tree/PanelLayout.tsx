"use client";

import React, { useCallback } from "react";

export function AutoCollapsePanel({ side, width, onCollapse, children }: {
  side: "left" | "right";
  width: number;
  onCollapse: () => void;
  children: React.ReactNode;
}) {
  const triggerZone = Math.max(width * 0.05, 10);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const inTriggerZone = side === "left"
      ? e.clientX - rect.left < triggerZone
      : rect.right - e.clientX < triggerZone;

    if (inTriggerZone) {
      onCollapse();
    }
  }, [side, triggerZone, onCollapse]);

  return (
    <div
      className="flex-shrink-0 relative"
      style={{ width: `${width}px` }}
      onMouseMove={handleMouseMove}
    >
      {children}
    </div>
  );
}

export function ResizeHandle({ side, onResize }: { side: "left" | "right"; onResize: (dx: number) => void }) {
  const dragging = React.useRef(false);
  const lastX = React.useRef(0);

  const handleMouseDown = React.useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    e.preventDefault();
    dragging.current = true;
    lastX.current = e.clientX;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
  }, []);

  React.useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const dx = e.clientX - lastX.current;
      lastX.current = e.clientX;
      onResize(dx);
    };
    const onMouseUp = () => {
      if (!dragging.current) return;
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    return () => { document.removeEventListener("mousemove", onMouseMove); document.removeEventListener("mouseup", onMouseUp); };
  }, [onResize]);

  return (
    <div
      className="flex-shrink-0 relative cursor-col-resize group"
      style={{ width: 6 }}
      onMouseDown={handleMouseDown}
    >
      <div className={`absolute inset-y-0 ${side === "left" ? "right-0.5" : "left-0.5"} w-[2px] bg-[var(--color-border)] group-hover:bg-[var(--color-accent)] transition-colors rounded-full`} />
    </div>
  );
}

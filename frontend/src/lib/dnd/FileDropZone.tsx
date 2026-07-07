"use client";

/**
 * FileDropZone — 共享文件上传拖放区 (Task #89)
 *
 * 封装 OS 文件拖入 + 视觉反馈:
 *  - 原生 onDrop 拿 e.dataTransfer.files（dnd-kit 管不了 OS 文件）
 *  - useDroppable 提供 isOver 状态做视觉反馈
 *  - 可选 onClick 触发 file input
 */

import { useId, useRef } from "react";
import { useDroppable } from "@dnd-kit/core";

export interface FileDropZoneProps {
  onFiles: (files: File[]) => void | Promise<void>;
  onClick?: () => void;
  className?: string;
  children: React.ReactNode;
  activeClassName?: string;
}

export function FileDropZone({
  onFiles,
  onClick,
  className = "",
  children,
  activeClassName = "ring-2 ring-accent",
}: FileDropZoneProps) {
  const dropId = useId();
  const { setNodeRef, isOver } = useDroppable({ id: `file-drop-${dropId}` });
  const handleRef = useRef<HTMLDivElement | null>(null);

  return (
    <div
      ref={(el) => {
        setNodeRef(el);
        handleRef.current = el;
      }}
      onClick={onClick}
      onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
      }}
      onDragLeave={(e) => {
        e.preventDefault();
      }}
      onDrop={async (e) => {
        e.preventDefault();
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
          await onFiles(files);
        }
      }}
      className={`${className} ${isOver ? activeClassName : ""} transition-all`}
    >
      {children}
    </div>
  );
}

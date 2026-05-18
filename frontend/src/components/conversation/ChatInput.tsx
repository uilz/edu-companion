"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Paperclip, Image, Loader2, X } from "lucide-react";
import VoiceRecorder from "./VoiceRecorder";

interface ConversationChatInputProps {
  onSend: (text: string, files?: UploadedFile[]) => void;
  disabled?: boolean;
  branchId?: string | null;
}

export interface UploadedFile {
  name: string;
  type: "image" | "file";
  url?: string;
  fileId?: string;  // workspace file_id
  materialId?: string;
}

export default function ConversationChatInput({
  onSend,
  disabled = false,
  branchId,
}: ConversationChatInputProps) {
  const [text, setText] = useState("");
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, []);

  useEffect(() => {
    autoResize();
  }, [text, autoResize]);

  // ── Upload handler ──
  const handleFileUpload = useCallback(async (file: File, type: "image" | "file") => {
    setUploading(true);
    setUploadError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      if (branchId) formData.append("branch_id", branchId);
      const res = await fetch("/api/conversations/workspace/upload", { method: "POST", body: formData });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "上传失败");
      }
      const data = await res.json();
      setUploadedFiles(prev => [...prev, {
        name: file.name,
        type,
        fileId: data.file?.id,
      }]);
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : "上传失败");
    } finally {
      setUploading(false);
    }
  }, [branchId]);

  const handleImageChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileUpload(file, "image");
    if (imageInputRef.current) imageInputRef.current.value = "";
  }, [handleFileUpload]);

  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileUpload(file, "file");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, [handleFileUpload]);

  const removeFile = useCallback((index: number) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  }, []);

  // ── Send ──
  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, uploadedFiles.length > 0 ? uploadedFiles : undefined);
    setText("");
    setUploadedFiles([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-[var(--color-border)] bg-[var(--color-bg)]">
      <div className="max-w-3xl mx-auto px-4 py-3">
        {/* Uploaded files preview */}
        {uploadedFiles.length > 0 && (
          <div className="flex items-center gap-1.5 mb-2 flex-wrap">
            {uploadedFiles.map((f, i) => (
              <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] border border-[var(--color-border)] text-[var(--color-text-secondary)]">
                {f.type === "image" ? "🖼️" : "📎"} {f.name}
                <button onClick={() => removeFile(i)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
                  <X size={10} />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Hidden file inputs */}
        <input ref={imageInputRef} type="file" accept="image/*" onChange={handleImageChange} className="hidden" />
        <input ref={fileInputRef} type="file" accept=".pdf,.docx,.pptx,.md,.txt" onChange={handleFileChange} className="hidden" />

        {/* Attachment buttons */}
        <div className="flex items-center gap-1 mb-2">
          <button
            onClick={() => imageInputRef.current?.click()}
            disabled={disabled || uploading}
            className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors disabled:opacity-30"
            title="上传图片"
          >
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <Image size={16} />}
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || uploading}
            className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors disabled:opacity-30"
            title="上传文件"
          >
            <Paperclip size={16} />
          </button>
          <VoiceRecorder
            onTranscription={(t) => setText((prev) => prev + t)}
            disabled={disabled}
          />
        </div>

        {/* Error message */}
        {uploadError && (
          <div className="text-[10px] text-[#ef4444] mb-1">{uploadError}</div>
        )}

        {/* Input area */}
        <div className="flex items-end gap-3">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder="输入你的问题... (Shift+Enter 换行)"
            rows={1}
            className="flex-1 resize-none bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] placeholder-[var(--color-text-muted)] px-4 py-3 text-sm focus:outline-none focus:border-[var(--color-border-hover)] disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={disabled || (!text.trim() && uploadedFiles.length === 0)}
            className="flex-shrink-0 w-10 h-10 flex items-center justify-center bg-[var(--color-accent)] text-white disabled:opacity-30 hover:bg-[var(--color-accent-hover)] transition-colors"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

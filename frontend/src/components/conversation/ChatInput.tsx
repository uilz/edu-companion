"use client";

// ===== 聊天输入框组件 =====
// 提供文本输入、文件上传（图片/文档）以及语音转录功能，是用户与 AI 对话的核心输入入口。
import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Paperclip, Image, Loader2, X } from "lucide-react";
import VoiceRecorder from "./VoiceRecorder";
import QuotePreview from "./QuotePreview";
import { useConversationStore } from "@/store/conversation-store";

// --- 组件属性接口 ---
interface ConversationChatInputProps {
  onSend: (text: string, files?: UploadedFile[]) => void;
  disabled?: boolean;
  branchId?: string | null;
  /** @alias branchId — preferred name */
  conversationId?: string | null;
  placeholder?: string;
}

// --- 已上传文件类型定义 ---
export interface UploadedFile {
  name: string;
  type: "image" | "file";
  url?: string;
  fileId?: string;  // workspace file_id
  materialId?: string;
}

// ===== 组件实现 =====
export default function ConversationChatInput({
  onSend,
  disabled = false,
  branchId,
  conversationId,
  placeholder,
}: ConversationChatInputProps) {
  const _convId = conversationId ?? branchId;

  // --- 状态定义 ---
  const [text, setText] = useState("");               // 输入框文本内容
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]); // 已上传的文件列表
  const [uploading, setUploading] = useState(false);    // 是否正在上传
  const [uploadError, setUploadError] = useState("");   // 上传错误信息
  const [voiceAutoSend, setVoiceAutoSend] = useState(false); // 语音录音后自动发送
  const textareaRef = useRef<HTMLTextAreaElement>(null); // 文本框 DOM 引用
  const imageInputRef = useRef<HTMLInputElement>(null);  // 图片选择 input 引用
  const fileInputRef = useRef<HTMLInputElement>(null);   // 文件选择 input 引用

  // --- 自动调整文本框高度（自适应内容）---
  const autoResize = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, []);

  // --- 文本或高度依赖变化时自动重置文本框高度 ---
  useEffect(() => {
    autoResize();
  }, [text, autoResize]);

  // --- 文件上传处理（图片/文档通用）：上传到 workspace 服务端并记录返回的 fileId ---
  const handleFileUpload = useCallback(async (file: File, type: "image" | "file") => {
    setUploading(true);
    setUploadError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      if (_convId) formData.append("conversation_id", _convId as string);
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
  }, [_convId]);

  // --- 图片选择处理 ---
  const handleImageChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileUpload(file, "image");
    if (imageInputRef.current) imageInputRef.current.value = "";
  }, [handleFileUpload]);

  // --- 文档（PDF/DOCX/PPTX/MD/TXT）选择处理 ---
  const handleFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFileUpload(file, "file");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, [handleFileUpload]);

  // --- 移除指定索引的已上传文件 ---
  const removeFile = useCallback((index: number) => {
    setUploadedFiles(prev => prev.filter((_, i) => i !== index));
  }, []);

  // ── Send ──
  // --- 发送消息：调用 onSend 回调并清空输入框及文件列表 ---
  const handleSend = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed, uploadedFiles.length > 0 ? uploadedFiles : undefined);
    setText("");
    setUploadedFiles([]);
    // Clear pending quote after normal send
    useConversationStore.getState().clearPendingQuote();
  };

  // --- 发送子支消息：创建子支并发送 ---
  const handleSubBranchSend = async () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    const pq = useConversationStore.getState().pendingQuote;
    if (!pq) return;
    try {
      await useConversationStore.getState().createSubBranch(
        pq.sourceConversationId,
        pq.sourceMessageId,
        pq.charStart,
        pq.charEnd,
        pq.quotedText,
        trimmed,
      );
      setText("");
      setUploadedFiles([]);
    } catch (e) {

    }
  };

  // --- 键盘事件：Enter 直接发送，Shift+Enter 换行 ---
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ===== 渲染界面 =====
  const pendingQuote = useConversationStore((s) => s.pendingQuote);
  const clearPendingQuote = useConversationStore((s) => s.clearPendingQuote);

  return (
    <div className="border-t border-[var(--color-border)] bg-[var(--color-bg)]">
      <div className="max-w-xl mx-auto px-4 py-3">
        {/* QuotePreview: show when pendingQuote is set */}
        {pendingQuote && (
          <QuotePreview
            quotedText={pendingQuote.quotedText}
            onClear={clearPendingQuote}
          />
        )}

        {/* 已上传文件预览区域 */}
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

        {/* 隐藏的文件选择 input */}
        <input ref={imageInputRef} type="file" accept="image/*" onChange={handleImageChange} className="hidden" />
        <input ref={fileInputRef} type="file" accept=".pdf,.docx,.pptx,.md,.txt" onChange={handleFileChange} className="hidden" />

        {/* 附件操作按钮组：上传图片、上传文件、语音输入 */}
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
            onTranscription={(t) => {
              const newText = t.trim();
              if (voiceAutoSend && newText) {
                // Voice auto-send: send immediately
                onSend(newText, uploadedFiles.length > 0 ? uploadedFiles : undefined);
                setText("");
                setUploadedFiles([]);
              } else {
                setText((prev) => prev + t);
              }
            }}
            disabled={disabled}
          />
          <button
            onClick={() => setVoiceAutoSend(!voiceAutoSend)}
            className={`p-1.5 text-[10px] transition-colors ${
              voiceAutoSend
                ? "text-[var(--color-accent)] bg-[var(--color-accent)]/10"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
            }`}
            title={voiceAutoSend ? "语音自动发送：开" : "语音自动发送：关"}
          >
            {voiceAutoSend ? "🚀" : "🎙️"}
          </button>
        </div>

        {/* 上传错误提示 */}
        {uploadError && (
          <div className="text-[10px] text-[#ef4444] mb-1">{uploadError}</div>
        )}

        {/* 输入区域：文本框 + 发送按钮 */}
        <div className="flex items-center gap-3 bg-[var(--color-input)] border border-[var(--color-border)] rounded-full px-2 py-1.5 focus-within:border-[var(--color-accent)] transition-colors">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder={placeholder || "输入你的问题... (Shift+Enter 换行)"}
            rows={1}
            className="flex-1 resize-none bg-transparent text-[var(--color-text)] placeholder-[var(--color-text-muted)] px-4 py-2 text-sm focus:outline-none disabled:opacity-50 min-h-[40px] max-h-[160px] leading-relaxed"
          />
          {pendingQuote ? (
            /* Dual-button mode when pendingQuote is set */
            <div className="flex flex-col gap-1 flex-shrink-0">
              <button
                onClick={handleSend}
                disabled={(!text.trim() && uploadedFiles.length === 0)}
                className="text-[10px] px-2 py-1 text-[var(--color-text-muted)] border border-[var(--color-border)]
                           hover:bg-[var(--color-surface)] active:scale-[0.97] transition-all disabled:opacity-30 rounded-full"
                title="普通发送（带引用块）"
              >
                普通发送
              </button>
              <button
                onClick={handleSubBranchSend}
                disabled={(!text.trim() && uploadedFiles.length === 0)}
                className="flex-shrink-0 px-2 py-1.5 flex items-center justify-center gap-1
                           bg-[var(--color-accent)] text-white text-xs font-medium disabled:opacity-30
                           hover:bg-[var(--color-accent-hover)] active:scale-[0.97] transition-colors rounded-full"
                title="创建子支对话"
              >
                📎子支
              </button>
            </div>
          ) : (
            /* Single send button (existing behavior) */
            <button
              onClick={handleSend}
              disabled={(!text.trim() && uploadedFiles.length === 0)}
              className="flex-shrink-0 w-10 h-10 flex items-center justify-center bg-[var(--color-accent)] text-white rounded-full disabled:opacity-30 hover:bg-[var(--color-accent-hover)] active:scale-[0.97] transition-colors"
            >
              {disabled ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

"use client";

// ===== 聊天输入框组件 =====
// 提供文本输入、文件上传（图片/文档）以及语音转录功能，是用户与 AI 对话的核心输入入口。
import { useState, useRef, useEffect, useCallback } from "react";
import { authedFetch } from "@/lib/api/api";
import { Send, Paperclip, Image, Loader2, X, Library } from "lucide-react";
import VoiceRecorder from "./../input/VoiceRecorder";
import QuotePreview from "./../input/QuotePreview";
import ResourcePicker from "./../input/ResourcePicker";
import { useConversationStore, getActiveConvId } from "@/store/conversation/conversation-store";
import { useMessageStore } from "@/store/conversation/message-store";
import { useDraftPersistence } from "@/hooks/conversation/useDraftPersistence";
import { toast } from "@/components/ui/Toast";

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
  conversationId,
  placeholder,
}: ConversationChatInputProps) {

  // --- 状态定义 ---
  const [text, setText, clearDraft] = useDraftPersistence(); // 输入框文本（自动 localStorage 持久化）
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]); // 已上传的文件列表
  const [uploading, setUploading] = useState(false);    // 是否正在上传
  const [uploadError, setUploadError] = useState("");   // 上传错误信息
  const [voiceAutoSend, setVoiceAutoSend] = useState(false); // 语音录音后自动发送
  const [showResourcePicker, setShowResourcePicker] = useState(false); // 资源选择器
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

  // --- 文件上传处理：上传到资料库 (/api/files/upload) 并获取 material_id ---
  const handleFileUpload = useCallback(async (file: File, type: "image" | "file") => {
    setUploading(true);
    setUploadError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      // 对话中上传的资料默认为 library（永久保留），方便后续引用
      formData.append("purpose", "library");
      const res = await authedFetch("/api/files/upload", { method: "POST", body: formData });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "上传失败");
      }
      const data = await res.json();
      setUploadedFiles(prev => [...prev, {
        name: file.name,
        type,
        fileId: data.material_id,
        materialId: data.material_id,
      }]);
      toast.success("文件已上传", file.name);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "上传失败";
      setUploadError(msg);
      toast.error("上传失败", msg);
    } finally {
      setUploading(false);
    }
  }, []);

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
  // 两阶段分离：ChatInput 负责创建会话，store.sendMessage 只负责发送

  /** 确保有活跃会话，没有则创建并等待加载完成 */
  const ensureConv = useCallback(async (): Promise<boolean> => {
    const store = useConversationStore.getState();
    if (getActiveConvId(store)) return true;

    await store.handleNewConversation("default", "", "");

    // 等待 loadConversation 完成
    for (let i = 0; i < 50; i++) {
      if (!useMessageStore.getState().isLoading) return true;
      await new Promise(r => setTimeout(r, 50));
    }
    return !!getActiveConvId(useConversationStore.getState());
  }, []);

  const sendingRef = useRef(false);

  const handleSend = async () => {
    const trimmed = text.trim();
    if (!trimmed || disabled || sendingRef.current) return;
    sendingRef.current = true;
    try {
      const ok = await ensureConv();
      if (!ok) return;

      await new Promise(r => setTimeout(r, 100));

      onSend(trimmed, uploadedFiles.length > 0 ? uploadedFiles : undefined);
      setText("");
      setUploadedFiles([]);
      useConversationStore.getState().clearPendingQuote();
    } finally {
      sendingRef.current = false;
    }
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
      clearDraft();
      setUploadedFiles([]);
    } catch (e) {
      // 子支创建失败，保留输入文字
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
    <div
      className="border-t border-[var(--color-border)] bg-[var(--color-bg)]"
      // iOS safe-area：键盘弹起 + 底部 notch 留出空间
      style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
      data-testid="chat-input-container"
    >
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
                {f.type === "image" ? "🖼️" : "📎"} <span className="truncate max-w-[80px] sm:max-w-[120px]">{f.name}</span>
                <button onClick={() => removeFile(i)} className="text-[var(--color-text-muted)] hover:text-[var(--color-text)]" aria-label="移除附件" style={{ minWidth: 24, minHeight: 24 }}>
                  <X size={10} />
                </button>
              </span>
            ))}
          </div>
        )}

        {/* 隐藏的文件选择 input */}
        <input ref={imageInputRef} type="file" accept="image/*" onChange={handleImageChange} className="hidden" />
        <input ref={fileInputRef} type="file" accept=".pdf,.docx,.pptx,.xlsx,.md,.txt,.jpg,.jpeg,.png,.gif,.webp,.mp3,.wav" onChange={handleFileChange} className="hidden" />

        {/* 附件操作按钮组：上传图片、上传文件、语音输入 */}
        <div className="flex items-center gap-1 mb-2">
          <button
            onClick={() => imageInputRef.current?.click()}
            disabled={disabled || uploading}
            className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors disabled:opacity-30"
            title="上传图片"
            style={{ minWidth: 36, minHeight: 36 }}
          >
            {uploading ? <Loader2 size={16} className="animate-spin" /> : <Image size={16} />}
          </button>
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || uploading}
            className="p-1.5 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] hover:bg-[var(--color-surface)] transition-colors disabled:opacity-30"
            title="上传文件"
            style={{ minWidth: 36, minHeight: 36 }}
          >
            <Paperclip size={16} />
          </button>
          <VoiceRecorder
            onTranscription={async (t) => {
              const newText = t.trim();
              if (voiceAutoSend && newText) {
                sendingRef.current = true;
                try {
                  const ok = await ensureConv();
                  if (!ok) return;
                  await new Promise(r => setTimeout(r, 100));
                  onSend(newText, uploadedFiles.length > 0 ? uploadedFiles : undefined);
                  setText("");
                  setUploadedFiles([]);
                } finally {
                  sendingRef.current = false;
                }
              } else {
                setText((prev) => prev + t);
              }
            }}
            disabled={disabled}
          />
          <button
            onClick={() => setShowResourcePicker(true)}
            disabled={disabled}
            className="p-1.5 text-[var(--color-text-muted)] hover:text-violet-500 hover:bg-violet-500/10 rounded transition-colors disabled:opacity-30"
            title="引用我的资源"
            style={{ minWidth: 36, minHeight: 36 }}
          >
            <Library size={16} />
          </button>
          <button
            onClick={() => setVoiceAutoSend(!voiceAutoSend)}
            className={`p-1.5 text-[10px] transition-colors ${
              voiceAutoSend
                ? "text-[var(--color-accent)] bg-[var(--color-accent)]/10"
                : "text-[var(--color-text-muted)] hover:text-[var(--color-text-secondary)]"
            }`}
            style={{ minWidth: 36, minHeight: 36 }}
            title={voiceAutoSend ? "语音自动发送：开" : "语音自动发送：关"}
            aria-pressed={voiceAutoSend}
          >
            {voiceAutoSend ? "🚀" : "🎙️"}
          </button>
        </div>

        {/* 上传错误提示 */}
        {uploadError && (
          <div className="text-[10px] text-[var(--color-error)] mb-1" role="alert">{uploadError}</div>
        )}

        {/* 输入区域：文本框 + 发送按钮 */}
        <div className="flex items-center gap-3 bg-[var(--color-input)] border border-[var(--color-border)] rounded-xl px-2 py-1.5 focus-within:border-[var(--color-accent)] transition-colors">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            placeholder={placeholder || "输入你的问题... (Shift+Enter 换行)"}
            rows={1}
            aria-label="消息输入框"
            className="flex-1 resize-none bg-transparent text-[var(--color-text)] placeholder-[var(--color-text-muted)] px-4 py-2 text-base sm:text-sm focus:outline-none disabled:opacity-50 min-h-[40px] max-h-[160px] leading-relaxed"
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
                style={{ minHeight: 32 }}
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
                style={{ minHeight: 32 }}
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
              aria-label="发送消息"
            >
              {disabled ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
            </button>
          )}
        </div>
      </div>
      {/* 资源选择器 */}
      <ResourcePicker
        open={showResourcePicker}
        onClose={() => setShowResourcePicker(false)}
        onSelect={(selected) => {
          setUploadedFiles(prev => [...prev, ...selected]);
          setShowResourcePicker(false);
        }}
      />
    </div>
  );
}

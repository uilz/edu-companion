"use client";

// ============================================================
//  NodeEditor — 节点编辑弹窗 (Task #89 从 page.tsx 提取)
// ============================================================

import { useState } from "react";
import { Loader2, X } from "lucide-react";
import { ProjectNode, NODE_TYPE_LABELS } from "../types";

export interface NodeEditorProps {
  node: ProjectNode;
  onClose: () => void;
  onSave: (payload: Record<string, unknown>) => Promise<void>;
  onVersions: () => void;
  onDelete: () => void;
}

export function NodeEditor({ node, onClose, onSave, onVersions, onDelete }: NodeEditorProps) {
  const [title, setTitle] = useState(node.title);
  const [description, setDescription] = useState(node.description || "");
  const [content, setContent] = useState<unknown>(node.content);
  const [code, setCode] = useState(node.code || "");
  const [language, setLanguage] = useState(node.language || "");
  const [explanation, setExplanation] = useState(node.explanation || "");
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<"edit" | "preview">("edit");

  const typeInfo = NODE_TYPE_LABELS[node.type] || NODE_TYPE_LABELS[1];

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        title,
        description: description || null,
      };
      if (node.type === 2) payload.content = content;
      if (node.type === 5) {
        payload.code = code;
        payload.language = language || null;
        payload.explanation = explanation || null;
      }
      await onSave(payload);
      onClose();
    } catch (e) {
      console.error(e);
      alert(`保存失败: ${e}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/30 flex items-center justify-center p-4">
      <div className="bg-page rounded-xl border border-divider w-full max-w-3xl max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-divider">
          <div className="flex items-center gap-2">
            <span className="text-ink-secondary">{typeInfo.icon}</span>
            <span className="text-sm text-ink-secondary">{typeInfo.label}</span>
            <span className="text-sm text-ink-secondary">v{node.version}</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={onVersions}
              className="px-3 py-1.5 rounded text-sm text-ink-secondary hover:text-ink-primary hover:bg-surface-hover"
            >
              版本历史
            </button>
            <button
              onClick={onDelete}
              className="px-3 py-1.5 rounded text-sm text-ink-secondary hover:text-red-500 hover:bg-surface-hover"
            >
              删除
            </button>
            <button
              onClick={onClose}
              className="p-1.5 rounded text-ink-secondary hover:text-ink-primary hover:bg-surface-hover"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="flex border-b border-divider px-4">
          <button
            onClick={() => setActiveTab("edit")}
            className={`px-3 py-2 text-sm ${activeTab === "edit" ? "border-b-2 border-[var(--color-accent)] text-[var(--color-accent)]" : "text-ink-secondary"}`}
          >
            编辑
          </button>
          <button
            onClick={() => setActiveTab("preview")}
            className={`px-3 py-2 text-sm ${activeTab === "preview" ? "border-b-2 border-[var(--color-accent)] text-[var(--color-accent)]" : "text-ink-secondary"}`}
          >
            预览
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {activeTab === "edit" ? (
            <>
              <div>
                <label className="text-sm text-ink-secondary block mb-1">标题</label>
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                />
              </div>
              <div>
                <label className="text-sm text-ink-secondary block mb-1">
                  描述（支持 <code className="text-xs">@[节点标题]</code> 引用）
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={4}
                  className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary font-mono text-sm"
                />
              </div>
              {node.type === 2 && (
                <div>
                  <label className="text-sm text-ink-secondary block mb-1">富文本内容（JSON）</label>
                  <textarea
                    value={JSON.stringify(content, null, 2) || "{}"}
                    onChange={(e) => {
                      try {
                        setContent(JSON.parse(e.target.value));
                      } catch {
                        /* ignore */
                      }
                    }}
                    rows={6}
                    className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary font-mono text-sm"
                  />
                </div>
              )}
              {node.type === 5 && (
                <>
                  <div>
                    <label className="text-sm text-ink-secondary block mb-1">语言</label>
                    <input
                      value={language}
                      onChange={(e) => setLanguage(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                      placeholder="python / javascript / ..."
                    />
                  </div>
                  <div>
                    <label className="text-sm text-ink-secondary block mb-1">代码</label>
                    <textarea
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      rows={10}
                      className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary font-mono text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-sm text-ink-secondary block mb-1">说明</label>
                    <textarea
                      value={explanation}
                      onChange={(e) => setExplanation(e.target.value)}
                      rows={3}
                      className="w-full px-3 py-2 rounded-lg bg-surface border border-divider text-ink-primary"
                    />
                  </div>
                </>
              )}
            </>
          ) : (
            <div className="prose max-w-none">
              <h1 className="text-2xl font-bold text-ink-primary">{title}</h1>
              {description && (
                <div className="text-ink-secondary whitespace-pre-wrap mb-4">{description}</div>
              )}
              {node.type === 5 && code && (
                <pre className="bg-surface-hover p-3 rounded-lg overflow-x-auto text-sm">
                  <code>{code}</code>
                </pre>
              )}
              {node.type === 5 && explanation && (
                <p className="text-ink-secondary mt-2 whitespace-pre-wrap">{explanation}</p>
              )}
            </div>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 p-4 border-t border-divider">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-ink-secondary hover:text-ink-primary"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
          >
            {saving && <Loader2 className="animate-spin" size={14} />}
            保存（自动入栈版本）
          </button>
        </div>
      </div>
    </div>
  );
}

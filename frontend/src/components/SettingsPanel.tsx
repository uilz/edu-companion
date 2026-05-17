"use client";

import React, { useState, useEffect } from "react";
import { X, Save, RotateCcw } from "lucide-react";
import { Settings } from "@/types";
import { getSettings, saveSettings } from "@/lib/api";

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
}

const defaultSettings: Settings = {
  apiEndpoint: "",
  apiKey: "",
  modelName: "",
  systemPrompt:
    "你是一个智能学习助手，善于用简单易懂的方式解释复杂的概念。回答时使用中文，必要时使用数学公式。",
};

export default function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const [settings, setSettings] = useState<Settings>(defaultSettings);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (open) {
      setSettings(getSettings());
      setSaved(false);
    }
  }, [open]);

  const handleSave = () => {
    saveSettings(settings);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleReset = () => {
    setSettings(defaultSettings);
    saveSettings(defaultSettings);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg bg-[var(--color-bg-secondary)] rounded-2xl border border-[var(--color-border-default)] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--color-border-default)]">
          <h2 className="text-lg font-semibold">⚙️ 模型设置</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-hover)]"
            aria-label="关闭"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-5 space-y-5">
          {/* API Endpoint */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1.5">
              API 地址
            </label>
            <input
              type="url"
              value={settings.apiEndpoint}
              onChange={(e) =>
                setSettings({ ...settings, apiEndpoint: e.target.value })
              }
              placeholder="https://api.example.com/v1/chat/completions"
              className="w-full px-3 py-2.5 rounded-lg bg-[var(--color-bg-primary)] border border-[var(--color-border-default)] text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors"
            />
          </div>

          {/* API Key */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1.5">
              API 密钥
            </label>
            <input
              type="password"
              value={settings.apiKey}
              onChange={(e) =>
                setSettings({ ...settings, apiKey: e.target.value })
              }
              placeholder="sk-..."
              className="w-full px-3 py-2.5 rounded-lg bg-[var(--color-bg-primary)] border border-[var(--color-border-default)] text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors"
            />
          </div>

          {/* Model Name */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1.5">
              模型名称
            </label>
            <input
              type="text"
              value={settings.modelName}
              onChange={(e) =>
                setSettings({ ...settings, modelName: e.target.value })
              }
              placeholder="gpt-4o / qwen-plus / deepseek-chat"
              className="w-full px-3 py-2.5 rounded-lg bg-[var(--color-bg-primary)] border border-[var(--color-border-default)] text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors"
            />
          </div>

          {/* System Prompt */}
          <div>
            <label className="block text-sm font-medium text-[var(--color-text-secondary)] mb-1.5">
              系统提示词
            </label>
            <textarea
              value={settings.systemPrompt}
              onChange={(e) =>
                setSettings({ ...settings, systemPrompt: e.target.value })
              }
              rows={4}
              className="w-full px-3 py-2.5 rounded-lg bg-[var(--color-bg-primary)] border border-[var(--color-border-default)] text-sm text-[var(--color-text-primary)] placeholder:text-[var(--color-text-muted)] focus:outline-none focus:border-[var(--color-accent)] transition-colors resize-none"
            />
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-[var(--color-border-default)]">
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-hover)] transition-colors"
          >
            <RotateCcw size={14} />
            恢复默认
          </button>
          <div className="flex items-center gap-3">
            {saved && (
              <span className="text-xs text-green-400">已保存 ✓</span>
            )}
            <button
              onClick={handleSave}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)] transition-colors"
            >
              <Save size={14} />
              保存
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

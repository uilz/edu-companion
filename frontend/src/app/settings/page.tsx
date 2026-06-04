"use client";

// ===== 导入依赖 =====
import { useState, useEffect } from "react";
import { Sun, Moon, Globe, Key, Cpu, MessageSquare, Info, Brain } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import Card from "@/components/ui/Card";

// ===== 设置项类型定义 =====
interface Settings {
  apiEndpoint: string;
  apiKey: string;
  modelName: string;
  systemPrompt: string;
  socraticMode: boolean;
  socraticFollowUpMode: "ask" | "answer";
}

// ===== 默认设置值 =====
const defaultSettings: Settings = {
  apiEndpoint: "",
  apiKey: "",
  modelName: "gpt-4o",
  systemPrompt: "你是一个专业的学习助手，擅长解答各学科问题。",
  socraticMode: true,
  socraticFollowUpMode: "ask",
};

// ===== 设置页面组件 =====
export default function SettingsPage() {
  // 主题上下文
  const { theme, toggleTheme, setTheme } = useTheme();
  // 设置状态
  const [settings, setSettings] = useState<Settings>(defaultSettings);

  // 从 localStorage 加载已保存的设置
  useEffect(() => {
    const saved = localStorage.getItem("edu-companion-settings");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setSettings((s) => ({ ...s, ...parsed }));
      } catch { ; }
    }
  }, []);

  // 设置变更时自动持久化到 localStorage
  useEffect(() => {
    localStorage.setItem("edu-companion-settings", JSON.stringify(settings));
  }, [settings]);

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-3xl mx-auto px-6 py-16">
        <h1 className="text-4xl font-semibold tracking-tight text-[var(--color-text)] mb-12">
          设置
        </h1>

        <div className="space-y-8">
          {/* ===== 外观设置 ===== */}
          <Card title="外观">
            <div className="space-y-4">
              <div>
                <div className="text-sm font-semibold text-[var(--color-text)] mb-3">主题</div>
                <div className="flex gap-3">
                  <button
                    onClick={() => setTheme("dark")}
                    className={`flex items-center gap-2 px-4 py-3 border text-sm transition-colors ${
                      theme === "dark"
                        ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                        : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)]"
                    }`}
                  >
                    <Moon size={16} />
                    深色模式
                  </button>
                  <button
                    onClick={() => setTheme("light")}
                    className={`flex items-center gap-2 px-4 py-3 border text-sm transition-colors ${
                      theme === "light"
                        ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                        : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)]"
                    }`}
                  >
                    <Sun size={16} />
                    浅色模式
                  </button>
                </div>
              </div>
            </div>
          </Card>

          {/* ===== API 设置 ===== */}
          <Card title="API 设置">
            <div className="space-y-4">
              <div>
                <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] block mb-1.5">
                  <Globe size={12} />
                  API 端点
                </label>
                <input
                  value={settings.apiEndpoint}
                  onChange={(e) =>
                    setSettings((s) => ({ ...s, apiEndpoint: e.target.value }))
                  }
                  className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)]"
                  placeholder="留空使用默认"
                />
              </div>
              <div>
                <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] block mb-1.5">
                  <Key size={12} />
                  API Key
                </label>
                <input
                  type="password"
                  value={settings.apiKey}
                  onChange={(e) =>
                    setSettings((s) => ({ ...s, apiKey: e.target.value }))
                  }
                  className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)]"
                  placeholder="sk-..."
                />
              </div>
              <div>
                <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] block mb-1.5">
                  <Cpu size={12} />
                  模型名称
                </label>
                <input
                  value={settings.modelName}
                  onChange={(e) =>
                    setSettings((s) => ({ ...s, modelName: e.target.value }))
                  }
                  className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)]"
                  placeholder="gpt-4o"
                />
              </div>
              <div>
                <label className="flex items-center gap-2 text-xs text-[var(--color-text-muted)] block mb-1.5">
                  <MessageSquare size={12} />
                  系统提示词
                </label>
                <textarea
                  value={settings.systemPrompt}
                  onChange={(e) =>
                    setSettings((s) => ({ ...s, systemPrompt: e.target.value }))
                  }
                  rows={4}
                  className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)] resize-none"
                />
              </div>
            </div>
          </Card>

          {/* ===== 学习偏好设置 ===== */}
          <Card title="学习偏好">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text)]">
                    <Brain size={16} />
                    启发式追问（苏格拉底教学法）
                  </div>
                  <p className="text-xs text-[var(--color-text-muted)] mt-1">
                    概念问题时 AI 会先反问引导思考，而不是直接给答案
                  </p>
                </div>
                <button
                  onClick={() =>
                    setSettings((s) => ({ ...s, socraticMode: !s.socraticMode }))
                  }
                  className={`relative w-11 h-6 transition-colors ${
                    settings.socraticMode ? "bg-[var(--color-accent)]" : "bg-[var(--color-surface)] border border-[var(--color-border)]"
                  }`}
                  style={{ borderRadius: "12px" }}
                >
                  <div
                    className={`absolute top-0.5 w-5 h-5 bg-white transition-transform ${
                      settings.socraticMode ? "translate-x-[22px]" : "translate-x-[2px]"
                    }`}
                    style={{ borderRadius: "50%" }}
                  />
                </button>
              </div>
              {settings.socraticMode && (
                <div className="flex items-center gap-2 pt-1">
                  <span className="text-xs text-[var(--color-text-muted)]">追问模式：</span>
                  <button onClick={() => setSettings((s) => ({ ...s, socraticFollowUpMode: "ask" }))}
                    className={`px-2.5 py-1 text-[10px] rounded-full transition-all ${
                      settings.socraticFollowUpMode === "ask"
                        ? "bg-[var(--color-accent)] text-white font-medium"
                        : "text-[var(--color-text-muted)] border border-[var(--color-border)] hover:border-[var(--color-accent)]"
                    }`}>追问AI</button>
                  <button onClick={() => setSettings((s) => ({ ...s, socraticFollowUpMode: "answer" }))}
                    className={`px-2.5 py-1 text-[10px] rounded-full transition-all ${
                      settings.socraticFollowUpMode === "answer"
                        ? "bg-amber-500 text-white font-medium"
                        : "text-[var(--color-text-muted)] border border-[var(--color-border)] hover:border-amber-400"
                    }`}>回答追问</button>
                  <span className="text-[9px] text-[var(--color-text-muted)] ml-auto">
                    {settings.socraticFollowUpMode === "ask" ? "AI回答后自动出追问选项" : "AI反问时自动切换为回答模式"}
                  </span>
                </div>
              )}
            </div>
          </Card>

          {/* ===== 关于页面 ===== */}
          <Card title="关于">
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-[var(--color-text-secondary)]">应用名称</span>
                <span className="text-[var(--color-text)] font-medium">智学伴</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--color-text-secondary)]">版本</span>
                <span className="text-[var(--color-text)] font-medium">v1.0.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--color-text-secondary)]">框架</span>
                <span className="text-[var(--color-text)] font-medium">Next.js 14 + Tailwind</span>
              </div>
              <div className="pt-3 border-t border-[var(--color-surface)]">
                <div className="flex items-start gap-2 text-xs text-[var(--color-text-muted)]">
                  <Info size={14} className="mt-0.5 flex-shrink-0" />
                  <span>
                    智学伴是一个 AI 驱动的个性化学习助手，支持智能对话、练习题生成、
                    知识图谱和学情分析。
                  </span>
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </main>
  );
}

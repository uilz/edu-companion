"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Wand2, Loader2, Send, Sparkles, Brain,
} from "lucide-react";
import { api } from "@/lib/api/api";

export default function GenerateQuestionsPage() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(5);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState("");

  const handleGenerate = async () => {
    if (!topic.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await api<any>("/api/practice/generate", {
        method: "POST",
        body: JSON.stringify({ message: topic.trim(), count }),
      });
      setResult(data);
    } catch (e: any) {
      setError(e.message || "生成失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="sticky top-0 z-10 bg-[var(--color-bg)]/80 backdrop-blur-sm border-b border-[var(--color-border)]/50">
        <div className="max-w-3xl mx-auto px-4 flex items-center h-12">
          <button onClick={() => router.back()}
            className="text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] mr-3">
            ← 返回
          </button>
          <Wand2 size={15} className="text-[var(--color-text-muted)] mr-2" />
          <span className="text-sm font-semibold text-[var(--color-text)]">AI 出题</span>
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 py-8 space-y-6">
        {/* 输入区 */}
        <div className="p-5 rounded-xl bg-[var(--color-surface)] border border-[var(--color-border)]/50 space-y-4">
          <div>
            <label className="text-xs font-medium text-[var(--color-text-muted)] block mb-1.5">
              题目主题
            </label>
            <textarea
              value={topic}
              onChange={e => setTopic(e.target.value)}
              placeholder="输入知识点或主题，例如：「机器学习中的过拟合问题」"
              rows={3}
              className="w-full px-3 py-2 text-sm rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)]/50 focus:outline-none focus:border-[var(--color-accent)] resize-none"
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <label className="text-xs text-[var(--color-text-muted)]">题目数:</label>
              {[3, 5, 10].map(n => (
                <button key={n} onClick={() => setCount(n)}
                  className={`px-2.5 py-1 text-xs rounded-lg transition-colors ${
                    count === n
                      ? "bg-[var(--color-accent)] text-white"
                      : "bg-[var(--color-bg)] text-[var(--color-text-muted)] border border-[var(--color-border)] hover:border-[var(--color-accent)]"
                  }`}>
                  {n}
                </button>
              ))}
            </div>

            <button onClick={handleGenerate} disabled={loading || !topic.trim()}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white text-xs font-medium hover:opacity-90 disabled:opacity-40 transition-all">
              {loading ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
              {loading ? "生成中..." : "生成"}
            </button>
          </div>

          {error && (
            <p className="text-xs text-red-500">{error}</p>
          )}
        </div>

        {/* 结果区 */}
        {result && (
          <div className="p-5 rounded-xl bg-green-500/5 border border-green-500/20 space-y-3">
            <div className="flex items-center gap-2">
              <Sparkles size={15} className="text-green-500" />
              <span className="text-sm font-medium text-[var(--color-text)]">生成完成</span>
              <span className="text-[10px] text-[var(--color-text-muted)]">
                共 {result.generated || 0} 题
              </span>
            </div>
            <button onClick={() => router.push(`/practice?tab=practice`)}
              className="w-full py-2 rounded-lg bg-green-500 text-white text-xs font-medium hover:bg-green-600 transition-colors">
              开始练习
            </button>
          </div>
        )}

        {/* 提示 */}
        <div className="flex items-start gap-2 p-4 rounded-xl bg-blue-500/5 border border-blue-500/15">
          <Brain size={14} className="text-blue-500 mt-0.5" />
          <p className="text-[11px] text-[var(--color-text-muted)] leading-relaxed">
            AI 会根据你输入的主题自动生成练习题，包含选择题和填空题。
            生成后题目会自动加入当前题库，你可以通过「开始练习」来作答。
          </p>
        </div>
      </div>
    </div>
  );
}

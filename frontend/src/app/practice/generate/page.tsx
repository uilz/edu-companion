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
    <div className="min-h-screen bg-page">
      <div className="sticky top-0 z-10 bg-page/80 backdrop-blur-sm border-b border/50">
        <div className="max-w-3xl mx-auto px-4 flex items-center h-12">
          <button onClick={() => router.back()}
            className="text-xs text-muted hover:text mr-3">
            ← 返回
          </button>
          <Wand2 size={15} className="text-muted mr-2" />
          <span className="text-sm font-semibold text">AI 出题</span>
        </div>
      </div>

      <div className="max-w-lg mx-auto px-4 py-8 space-y-6">
        {/* 输入区 */}
        <div className="p-5 rounded-xl bg-surface border border/50 space-y-4">
          <div>
            <label className="text-xs font-medium text-muted block mb-1.5">
              题目主题
            </label>
            <textarea
              value={topic}
              onChange={e => setTopic(e.target.value)}
              placeholder="输入知识点或主题，例如：「机器学习中的过拟合问题」"
              rows={3}
              className="w-full px-3 py-2 text-sm rounded-lg bg-page border border text placeholder:text-muted/50 focus:outline-none focus:border-accent resize-none"
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <label className="text-xs text-muted">题目数:</label>
              {[3, 5, 10].map(n => (
                <button key={n} onClick={() => setCount(n)}
                  className={`px-2.5 py-1 text-xs rounded-lg transition-colors ${
                    count === n
                      ? "bg-accent text-white"
                      : "bg-page text-muted border border hover:border-accent"
                  }`}>
                  {n}
                </button>
              ))}
            </div>

            <button onClick={handleGenerate} disabled={loading || !topic.trim()}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-accent text-white text-xs font-medium hover:opacity-90 disabled:opacity-40 transition-all">
              {loading ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
              {loading ? "生成中..." : "生成"}
            </button>
          </div>

          {error && (
            <p className="text-xs text-danger">{error}</p>
          )}
        </div>

        {/* 结果区 */}
        {result && (
          <div className="p-5 rounded-xl bg-success/5 border border-success/20 space-y-3">
            <div className="flex items-center gap-2">
              <Sparkles size={15} className="text-success" />
              <span className="text-sm font-medium text">生成完成</span>
              <span className="text-[10px] text-muted">
                共 {result.generated || 0} 题
              </span>
            </div>
            <button onClick={() => router.push(`/practice?tab=practice`)}
              className="w-full py-2 rounded-lg bg-success text-white text-xs font-medium hover:bg-success transition-colors">
              开始练习
            </button>
          </div>
        )}

        {/* 提示 */}
        <div className="flex items-start gap-2 p-4 rounded-xl bg-info/5 border border-info/15">
          <Brain size={14} className="text-info mt-0.5" />
          <p className="text-[11px] text-muted leading-relaxed">
            AI 会根据你输入的主题自动生成练习题，包含选择题和填空题。
            生成后题目会自动加入当前题库，你可以通过「开始练习」来作答。
          </p>
        </div>
      </div>
    </div>
  );
}

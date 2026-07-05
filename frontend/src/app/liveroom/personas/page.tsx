"use client";

/**
 * LanguageRoom AI 角色库
 * 依据 docs/modules/language-room/overview.md + ADR 0004
 *
 * 关键设计:
 *  - AI 纠错倾向 = 用户主动选择 (决策 6)
 *  - 不调用 LLM 做评判
 *  - 共享 tool registry (决策 5)
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles, ArrowLeft, Plus, Loader2,
} from "lucide-react";
import {
  liveroomService, AIPersona, ProficiencyLevel, SpeechRate, Behavior,
  PROFICIENCY_LABELS, CORRECTION_TENDENCY_LABELS,
} from "@/lib/api/liveroom-api";

export default function PersonasPage() {
  const router = useRouter();
  const [personas, setPersonas] = useState<AIPersona[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);

  // 表单
  const [name, setName] = useState("");
  const [targetLanguage, setTargetLanguage] = useState("en");
  const [proficiency, setProficiency] = useState<ProficiencyLevel>("intermediate");
  const [speechRate, setSpeechRate] = useState<SpeechRate>("normal");
  const [behavior, setBehavior] = useState<Behavior>("balanced");
  const [correctionTendency, setCorrectionTendency] = useState<"none" | "occasional" | "proactive">("none");
  const [personality, setPersonality] = useState("");
  const [background, setBackground] = useState("");

  useEffect(() => {
    setLoading(true);
    liveroomService.listPersonas({ limit: 50 })
      .then(setPersonas)
      .finally(() => setLoading(false));
  }, []);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      const p = await liveroomService.createPersona({
        name, target_language: targetLanguage, proficiency, speech_rate: speechRate,
        behavior, correction_tendency: correctionTendency,
        personality, background,
      });
      setPersonas([p, ...personas]);
      setShowCreate(false);
      setName(""); setPersonality(""); setBackground("");
    } catch (e: any) {
      alert(e.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
        <div className="flex items-center justify-between gap-3 mb-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/liveroom")}
              className="p-1.5 hover:bg-[var(--color-card)] rounded"
            >
              <ArrowLeft size={18} />
            </button>
            <div>
              <h1 className="text-xl font-semibold flex items-center gap-2">
                <Sparkles size={20} /> AI 角色库
              </h1>
              <p className="text-xs text-[var(--color-text-muted)] mt-0.5">
                决策 6: AI 纠错倾向 = 用户主动选择, 非 AI 主动评判
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm bg-emerald-600 text-white rounded-md hover:bg-emerald-700"
          >
            <Plus size={14} /> 新建 AI 角色
          </button>
        </div>

        {showCreate && (
          <div className="mb-6 border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-4 space-y-3">
            <div className="text-sm font-medium">新建 AI 角色</div>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="角色名 (例: 咖啡师 Lily)"
              className="w-full text-sm px-3 py-2 border border-[var(--color-border)] rounded bg-[var(--color-bg)]"
            />
            <div className="grid grid-cols-2 gap-2">
              <div>
                <div className="text-[10px] text-[var(--color-text-muted)]">目标语言</div>
                <select
                  value={targetLanguage}
                  onChange={(e) => setTargetLanguage(e.target.value)}
                  className="w-full text-xs px-2 py-1.5 border border-[var(--color-border)] rounded bg-[var(--color-bg)]"
                >
                  <option value="en">英语</option>
                  <option value="zh">中文</option>
                  <option value="ja">日语</option>
                  <option value="ko">韩语</option>
                  <option value="es">西班牙语</option>
                  <option value="fr">法语</option>
                </select>
              </div>
              <div>
                <div className="text-[10px] text-[var(--color-text-muted)]">熟练度</div>
                <select
                  value={proficiency}
                  onChange={(e) => setProficiency(e.target.value as ProficiencyLevel)}
                  className="w-full text-xs px-2 py-1.5 border border-[var(--color-border)] rounded bg-[var(--color-bg)]"
                >
                  {(["beginner", "intermediate", "advanced", "native"] as ProficiencyLevel[]).map((p) => (
                    <option key={p} value={p}>{PROFICIENCY_LABELS[p]}</option>
                  ))}
                </select>
              </div>
              <div>
                <div className="text-[10px] text-[var(--color-text-muted)]">语速</div>
                <select
                  value={speechRate}
                  onChange={(e) => setSpeechRate(e.target.value as SpeechRate)}
                  className="w-full text-xs px-2 py-1.5 border border-[var(--color-border)] rounded bg-[var(--color-bg)]"
                >
                  <option value="slow">慢</option>
                  <option value="normal">正常</option>
                  <option value="fast">快</option>
                </select>
              </div>
              <div>
                <div className="text-[10px] text-[var(--color-text-muted)]">行为</div>
                <select
                  value={behavior}
                  onChange={(e) => setBehavior(e.target.value as Behavior)}
                  className="w-full text-xs px-2 py-1.5 border border-[var(--color-border)] rounded bg-[var(--color-bg)]"
                >
                  <option value="talkative">健谈</option>
                  <option value="balanced">平衡</option>
                  <option value="concise">简洁</option>
                </select>
              </div>
            </div>
            <div>
              <div className="text-[10px] text-[var(--color-text-muted)]">
                纠错倾向 (决策 6: 用户主动选择, 默认 none)
              </div>
              <div className="grid grid-cols-3 gap-2 mt-1">
                {(["none", "occasional", "proactive"] as const).map((c) => (
                  <button
                    key={c}
                    onClick={() => setCorrectionTendency(c)}
                    className={`px-2 py-1.5 text-xs border rounded ${
                      correctionTendency === c
                        ? "bg-emerald-50 border-emerald-300 text-emerald-700"
                        : "border-[var(--color-border)]"
                    }`}
                  >
                    {CORRECTION_TENDENCY_LABELS[c]}
                  </button>
                ))}
              </div>
            </div>
            <textarea
              value={personality}
              onChange={(e) => setPersonality(e.target.value)}
              placeholder="性格描述 (例: 友好、耐心、简短回复)"
              className="w-full text-sm px-3 py-2 border border-[var(--color-border)] rounded bg-[var(--color-bg)] h-14 resize-none"
            />
            <textarea
              value={background}
              onChange={(e) => setBackground(e.target.value)}
              placeholder="角色背景 (例: 在咖啡馆工作 5 年)"
              className="w-full text-sm px-3 py-2 border border-[var(--color-border)] rounded bg-[var(--color-bg)] h-14 resize-none"
            />
            <div className="flex gap-2">
              <button
                onClick={handleCreate}
                disabled={creating}
                className="px-4 py-1.5 text-sm bg-emerald-600 text-white rounded hover:bg-emerald-700"
              >
                {creating ? <Loader2 size={12} className="inline animate-spin" /> : "创建"}
              </button>
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-1.5 text-sm border border-[var(--color-border)] rounded"
              >
                取消
              </button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 size={24} className="animate-spin text-[var(--color-text-muted)]" />
          </div>
        ) : personas.length === 0 ? (
          <div className="border border-dashed border-[var(--color-border)] rounded-lg p-10 text-center text-sm text-[var(--color-text-muted)]">
            暂无 AI 角色
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {personas.map((p) => (
              <div
                key={p.id}
                className="border border-[var(--color-border)] bg-[var(--color-card)] rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="font-medium text-sm flex items-center gap-1.5">
                    <Sparkles size={14} className="text-purple-500" />
                    {p.name}
                  </div>
                  {p.is_system ? (
                    <span className="text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-600 border border-blue-200 rounded">
                      系统
                    </span>
                  ) : (
                    <span className="text-[10px] px-1.5 py-0.5 bg-purple-50 text-purple-600 border border-purple-200 rounded">
                      自定义
                    </span>
                  )}
                </div>
                <div className="text-[10px] text-[var(--color-text-muted)] space-y-0.5">
                  <div>语种: {p.target_language} · {PROFICIENCY_LABELS[p.proficiency as ProficiencyLevel] || p.proficiency}</div>
                  <div>语速: {p.speech_rate} · 行为: {p.behavior}</div>
                  <div>纠错倾向: <strong className="text-emerald-600">
                    {CORRECTION_TENDENCY_LABELS[p.correction_tendency]}
                  </strong></div>
                </div>
                {p.personality && (
                  <div className="text-[10px] mt-2 text-[var(--color-text-muted)] line-clamp-2">
                    {p.personality}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

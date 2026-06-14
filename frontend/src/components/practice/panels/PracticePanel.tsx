"use client";

import { useState, useCallback, useEffect } from "react";
import {
  Play, Check, X, RotateCcw, Brain, Sparkles, Loader2, BookOpen,
} from "lucide-react";
import {
  createPracticeSession, submitAnswer, completeSession,
  resolveBankForNode, generateQuestions, listBanks, listMaterials,
  type V7Session, type V7SubmitResult, type MaterialItem,
} from "@/lib/api/practice-api";
import QuestionCard from "@/components/practice/components/QuestionCard";
import SummaryPanel from "@/components/practice/components/SummaryPanel";

type Phase = "idle" | "loading" | "answering" | "result" | "summary" | "error";

interface Props {
  nodeId?: string;
  nodeLabel?: string;
  bankId?: string;
  onClose?: () => void;
}

export default function PracticePanel({ nodeId, nodeLabel, bankId, onClose }: Props) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [session, setSession] = useState<V7Session | null>(null);
  const [currentIdx, setCurrentIdx] = useState(0);
  const [selected, setSelected] = useState<string[]>([]);
  const [showFeedback, setShowFeedback] = useState(false);
  const [lastResult, setLastResult] = useState<V7SubmitResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [skipped, setSkipped] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"adaptive" | "review" | "challenge">("adaptive");
  const [count, setCount] = useState(5);
  const [difficulty, setDifficulty] = useState<"auto" | "easy" | "medium" | "hard">("auto");
  const [questionStart, setQuestionStart] = useState(0);
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<string[]>([]);
  const [results, setResults] = useState<V7SubmitResult[]>([]);

  const question = session?.questions?.[currentIdx] ?? null;

  // ── 开始练习 ──
  const handleStart = useCallback(async () => {
    setPhase("loading"); setError(""); setResults([]); setCurrentIdx(0);
    try {
      const resolvedBankId = bankId || (nodeId ? (await resolveBankForNode(nodeId)).bank_id : (await listBanks())?.[0]?.id || "bnk_default");
      const config: Record<string, any> = {};
      if (difficulty !== "auto") config.difficulty = difficulty;
      const sess = await createPracticeSession(resolvedBankId, { mode, count, config, cognitive_node_ids: nodeId ? [nodeId] : undefined });

      if (sess.questions?.length > 0) {
        setSession(sess); setPhase("answering"); setSelected([]); setLastResult(null); setQuestionStart(Date.now());
      } else {
        // AI fallback
        const genResult = await generateQuestions(`关于${nodeLabel || "当前知识点"}的练习题`, {
          bank_id: resolvedBankId, node_id: nodeId, material_ids: selectedMaterialIds.length > 0 ? selectedMaterialIds : undefined,
        });
        if (genResult.generated > 0) {
          const sess2 = await createPracticeSession(resolvedBankId, { mode, count: Math.min(count, genResult.generated), cognitive_node_ids: nodeId ? [nodeId] : undefined });
          setSession(sess2); setPhase("answering"); setSelected([]); setLastResult(null); setQuestionStart(Date.now());
        } else {
          setPhase("error"); setError("题库暂无题，AI 出题也未成功。请在对话中先学习相关内容。");
        }
      }
    } catch (e: any) { setPhase("error"); setError(e?.message || "创建练习失败"); }
  }, [nodeId, nodeLabel, mode, count, difficulty, selectedMaterialIds, bankId]);

  const handleSelect = (label: string) => {
    if (showFeedback || submitting) return;
    const t = question?.question_type;
    if (t === "single" || t === "judge") setSelected([label]);
    else setSelected(p => p.includes(label) ? p.filter(l => l !== label) : [...p, label]);
  };

  const handleSubmit = async () => {
    if (!session || !question || !selected.length || submitting) return;
    setSubmitting(true);
    const ts = Math.floor((Date.now() - questionStart) / 1000);
    try {
      const r = await submitAnswer(session.session_id, question.id, selected, ts);
      setLastResult(r); setShowFeedback(true); setResults(p => [...p, r]); setPhase("result");
    } catch { setPhase("answering"); }
    setSubmitting(false);
  };

  const handleSkip = async () => {
    if (!session || !question || submitting) return;
    setSubmitting(true);
    const ts = Math.floor((Date.now() - questionStart) / 1000);
    try {
      const r = await submitAnswer(session.session_id, question.id, [], ts);
      setSkipped(true); setLastResult({ ...r, is_correct: false }); setShowFeedback(true);
      setResults(p => [...p, { ...r, is_correct: false }]); setPhase("result");
    } catch {}
    setSubmitting(false);
  };

  const handleNext = async () => {
    if (!session) return;
    if (currentIdx + 1 >= session.total_count) {
      setPhase("loading");
      try { await completeSession(session.session_id); } catch {}
      setPhase("summary");
    } else {
      setCurrentIdx(i => i + 1); setSelected([]); setLastResult(null); setShowFeedback(false);
      setPhase("answering"); setQuestionStart(Date.now()); setSkipped(false);
    }
  };

  const handleRetry = () => {
    setPhase("idle"); setSession(null); setCurrentIdx(0); setResults([]); setError(""); setSelected([]);
    setShowFeedback(false); setSkipped(false);
  };

  // 键盘快捷键
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (phase === "answering" && question?.options) {
        const idx = parseInt(e.key) - 1;
        if (idx >= 0 && idx < question.options.length) { handleSelect(question.options[idx].letter); return; }
        const letter = e.key.toUpperCase();
        if (/^[A-D]$/.test(letter) && question.options.some(o => o.letter === letter)) { handleSelect(letter); return; }
      }
      if (e.key === "Enter") {
        if (showFeedback) handleNext();
        else if (selected.length > 0) handleSubmit();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [phase, question, selected, handleSubmit, handleNext, handleSelect, showFeedback]);

  if (phase === "loading") return <LoadingScreen />;
  if (phase === "error") return <ErrorScreen message={error} onRetry={handleRetry} />;
  if (phase === "summary") {
    const correct = results.filter(r => r.is_correct).length;
    const wrong = results.length - correct;
    const score = results.length > 0 ? Math.round((correct / results.length) * 100) : 0;
    return (
      <SummaryPanel
        status="completed"
        total={results.length}
        correct={correct}
        wrong={wrong}
        score={score}
        onBack={handleRetry}
      />
    );
  }

  if (phase === "idle") {
    return (
      <IdleScreen
        mode={mode} setMode={setMode} count={count} setCount={setCount}
        difficulty={difficulty} setDifficulty={setDifficulty}
        selectedMaterialIds={selectedMaterialIds} setSelectedMaterialIds={setSelectedMaterialIds}
        nodeLabel={nodeLabel} onStart={handleStart}
      />
    );
  }

  // ── 答题态 ──
  const answeredCount = results.length;
  return (
    <div className="flex flex-col h-full">
      {/* 进度条 */}
      <div className="px-4 pt-3 pb-2">
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10px] text-[var(--color-text-muted)]">
            第 {currentIdx + 1}/{session?.total_count}
          </span>
          <span className="text-[10px] text-[var(--color-text-muted)]">
            {results.filter(r => r.is_correct).length} 正确 · {results.filter(r => !r.is_correct).length} 错误
          </span>
        </div>
        <div className="w-full h-1 bg-[var(--color-border)]/50 rounded-full overflow-hidden flex">
          <div className="h-full bg-green-400 transition-all" style={{ width: `${(answeredCount > 0 ? (results.filter(r => r.is_correct).length / session!.total_count) * 100 : 0)}%` }} />
          <div className="h-full bg-red-400 transition-all" style={{ width: `${(answeredCount > 0 ? (results.filter(r => !r.is_correct).length / session!.total_count) * 100 : 0)}%` }} />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 pb-4">
        {question && (
          <QuestionCard
            question={question}
            index={currentIdx}
            total={session!.total_count}
            showFeedback={showFeedback}
            lastResult={lastResult}
            submitting={submitting}
            selected={selected}
            onSelect={handleSelect}
            onSubmit={handleSubmit}
            onSkip={handleSkip}
            onNext={handleNext}
            isLast={currentIdx + 1 >= session!.total_count}
          />
        )}
      </div>
    </div>
  );
}

// ── 子组件 ──

function LoadingScreen() {
  return (
    <div className="flex flex-col items-center justify-center h-full">
      <Loader2 size={22} className="animate-spin text-[var(--color-accent)] mb-3" />
      <p className="text-xs text-[var(--color-text-muted)]">正在出题...</p>
    </div>
  );
}

function ErrorScreen({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full px-6">
      <X size={22} className="text-red-500 mb-3" />
      <p className="text-sm text-[var(--color-text)] mb-4 text-center">{message}</p>
      <button onClick={onRetry}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[var(--color-accent)] text-white text-xs font-medium">
        <RotateCcw size={12} />返回重试
      </button>
    </div>
  );
}

function IdleScreen({
  mode, setMode, count, setCount, difficulty, setDifficulty,
  selectedMaterialIds, setSelectedMaterialIds,
  nodeLabel, onStart,
}: {
  mode: string; setMode: (m: any) => void; count: number; setCount: (n: number) => void;
  difficulty: string; setDifficulty: (d: any) => void;
  selectedMaterialIds: string[]; setSelectedMaterialIds: (ids: string[]) => void;
  nodeLabel?: string; onStart: () => void;
}) {
  const [materials, setMaterials] = useState<MaterialItem[]>([]);
  const [showPicker, setShowPicker] = useState(false);
  const [loadingMaterials, setLoadingMaterials] = useState(false);

  const loadMaterials = async () => {
    setLoadingMaterials(true);
    try { const r = await listMaterials(); setMaterials(r.items || []); } catch {}
    setLoadingMaterials(false);
  };

  const toggleMaterial = (id: string) => {
    setSelectedMaterialIds(
      selectedMaterialIds.includes(id) ? selectedMaterialIds.filter(i => i !== id) : [...selectedMaterialIds, id]
    );
  };

  return (
    <div className="flex flex-col items-center justify-center h-full px-6">
      {/* 标题 */}
      <div className="text-center mb-6">
        <div className="w-12 h-12 rounded-xl bg-[var(--color-accent)]/10 flex items-center justify-center mx-auto mb-2">
          <Brain size={22} className="text-[var(--color-accent)]" />
        </div>
        <h3 className="text-sm font-semibold text-[var(--color-text)]">
          {nodeLabel || "智能练习"}
        </h3>
        <p className="text-[10px] text-[var(--color-text-muted)] mt-1">自适应出题 · 薄弱优先</p>
      </div>

      {/* 参考资料选择 */}
      <div className="w-full mb-4">
        <button onClick={() => { if (!showPicker) loadMaterials(); setShowPicker(!showPicker); }}
          className="flex items-center gap-1.5 text-[10px] text-[var(--color-text-muted)] hover:text-[var(--color-accent)] mb-2 transition-colors">
          <BookOpen size={12} />{showPicker ? "收起" : selectedMaterialIds.length > 0 ? `已选 ${selectedMaterialIds.length} 份资料` : "基于资料出题"}
        </button>
        {showPicker && (
          <div className="p-3 rounded-lg border border-[var(--color-border)]/50 bg-[var(--color-surface)] max-h-40 overflow-y-auto">
            {loadingMaterials ? (
              <div className="flex items-center justify-center py-3"><Loader2 size={12} className="animate-spin text-[var(--color-text-muted)]" /><span className="ml-1.5 text-[10px] text-[var(--color-text-muted)]">加载中...</span></div>
            ) : materials.length === 0 ? (
              <p className="text-[10px] text-[var(--color-text-muted)] text-center py-3">暂无资料</p>
            ) : (
              <div className="space-y-1">
                {materials.map(m => (
                  <label key={m.material_id} className={`flex items-center gap-2 p-2 rounded-md cursor-pointer ${selectedMaterialIds.includes(m.material_id) ? "bg-[var(--color-accent)]/10" : "hover:bg-[var(--color-bg)]"}`}>
                    <input type="checkbox" checked={selectedMaterialIds.includes(m.material_id)} onChange={() => toggleMaterial(m.material_id)} className="accent-[var(--color-accent)]" />
                    <span className="text-[10px] text-[var(--color-text)] truncate">{m.file_name}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}
        {selectedMaterialIds.length > 0 && !showPicker && (
          <div className="flex flex-wrap gap-1 mt-1">
            {materials.filter(m => selectedMaterialIds.includes(m.material_id)).map(m => (
              <span key={m.material_id} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--color-accent)]/10 text-[9px] text-[var(--color-accent)] border border-[var(--color-accent)]/30">
                {m.file_name.slice(0, 15)}…
              </span>
            ))}
          </div>
        )}
      </div>

      {/* 模式选择 */}
      <div className="w-full mb-4">
        <p className="text-[10px] text-[var(--color-text-muted)] mb-2 font-medium">练习模式</p>
        <div className="grid grid-cols-3 gap-2">
          {[
            { key: "adaptive", label: "自适应", icon: <Brain size={13} /> },
            { key: "review", label: "复习", icon: <RotateCcw size={13} /> },
            { key: "challenge", label: "挑战", icon: <Sparkles size={13} /> },
          ].map(m => (
            <button key={m.key} onClick={() => setMode(m.key)}
              className={`flex flex-col items-center gap-1 p-3 rounded-lg border transition-all ${mode === m.key ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10" : "border-[var(--color-border)]/50 bg-[var(--color-surface)] hover:border-[var(--color-accent)]/30"}`}>
              <span className={mode === m.key ? "text-[var(--color-accent)]" : "text-[var(--color-text-muted)]"}>{m.icon}</span>
              <span className={`text-[11px] font-medium ${mode === m.key ? "text-[var(--color-accent)]" : "text-[var(--color-text)]"}`}>{m.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 题数 */}
      <div className="w-full mb-4">
        <p className="text-[10px] text-[var(--color-text-muted)] mb-2 font-medium">题数</p>
        <div className="flex gap-2">
          {[3, 5, 10].map(n => (
            <button key={n} onClick={() => setCount(n)}
              className={`flex-1 py-2 rounded-lg border text-center text-sm font-medium transition-all ${count === n ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]" : "border-[var(--color-border)]/50 bg-[var(--color-surface)] text-[var(--color-text)] hover:border-[var(--color-accent)]/30"}`}>
              {n} 题
            </button>
          ))}
        </div>
      </div>

      {/* 难度 */}
      <div className="w-full mb-6">
        <p className="text-[10px] text-[var(--color-text-muted)] mb-2 font-medium">难度</p>
        <div className="flex gap-2">
          {[
            { key: "auto", label: "自适应" },
            { key: "easy", label: "简单" },
            { key: "medium", label: "中等" },
            { key: "hard", label: "困难" },
          ].map(d => (
            <button key={d.key} onClick={() => setDifficulty(d.key)}
              className={`flex-1 py-2 rounded-lg border text-center text-xs font-medium transition-all ${difficulty === d.key ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-accent)]" : "border-[var(--color-border)]/50 bg-[var(--color-surface)] text-[var(--color-text)] hover:border-[var(--color-accent)]/30"}`}>
              {d.label}
            </button>
          ))}
        </div>
      </div>

      <button onClick={onStart}
        className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg bg-[var(--color-accent)] text-white text-sm font-medium hover:opacity-90 transition-opacity">
        <Play size={14} />开始练习
      </button>
      <p className="mt-3 text-[9px] text-[var(--color-text-muted)]">键盘: 1-4 选答案 · Enter 提交/下一题</p>
    </div>
  );
}

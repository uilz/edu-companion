"use client";

import { useState, useMemo } from "react";
import { Lightbulb } from "lucide-react";

/**
 * 内联练习卡片 — 替代旧 PracticeCard 全屏覆盖层
 * 嵌入在对话流中，以卡片形式显示选择题
 */

interface PracticeInlineOption {
  letter: string;
  text: string;
  is_correct: boolean;
}

interface PracticeInlineQuestion {
  stem: string;
  options: PracticeInlineOption[];
  hint?: string;
}

interface Props {
  question: PracticeInlineQuestion;
  onDone: (correct: boolean) => void;
  onCreateCard: () => void;
}

export default function PracticeInlineCard({ question, onDone, onCreateCard }: Props) {
  const [selected, setSelected] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [showHint, setShowHint] = useState(false);
  const [cardCreated, setCardCreated] = useState(false);

  const correctLetters = useMemo(
    () => question.options.filter((o) => o.is_correct).map((o) => o.letter),
    [question.options]
  );

  const isCorrect = selected !== null && correctLetters.includes(selected);

  const handleSubmit = () => {
    if (!selected || submitted) return;
    setSubmitted(true);
    setTimeout(() => onDone(isCorrect), 500);
  };

  const handleCreateCard = () => {
    setCardCreated(true);
    onCreateCard();
  };

  return (
    <div className="msg ai">
      <div className="msg-avatar">🍎</div>
      <div className="msg-bubble" style={{ padding: 0, background: "transparent", maxWidth: "100%" }}>
        <div
          className="practice-question"
          style={{ margin: 0, boxShadow: "0 0 0 1px var(--border)", borderRadius: "var(--radius-lg)" }}
        >
          <p className="q-label" style={{ fontSize: 12, color: "var(--ink-muted)", fontWeight: 500, marginBottom: 8 }}>
            {showHint && question.hint ? "提示" : "来一道"}
          </p>
          <p className="q-text" style={{ fontSize: 15, lineHeight: 1.6, marginBottom: 12 }}>
            {question.stem}
          </p>

          {/* 选项 */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12 }}>
            {question.options.map((opt) => {
              const isSelected = selected === opt.letter;
              let cls = "q-option";
              if (submitted) {
                if (opt.is_correct) cls += " correct";
                if (isSelected && !opt.is_correct) cls += " wrong";
              }
              return (
                <button
                  key={opt.letter}
                  className={cls}
                  onClick={() => !submitted && setSelected(opt.letter)}
                  disabled={submitted}
                  style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "10px 14px", borderRadius: "var(--radius-md)",
                    border: "1.5px solid var(--color-divider)",
                    background: isSelected ? "var(--color-surface-hover)" : "var(--color-surface)",
                    fontSize: 14, textAlign: "left", cursor: submitted ? "default" : "pointer",
                    opacity: submitted && !isSelected && !opt.is_correct ? 0.5 : 1,
                  }}
                >
                  <span style={{
                    width: 24, height: 24, borderRadius: "50%",
                    display: "grid", placeItems: "center",
                    fontSize: 12, fontWeight: 600, flexShrink: 0,
                    background: submitted && opt.is_correct ? "var(--color-success)" :
                                submitted && isSelected && !opt.is_correct ? "var(--color-error)" : "var(--color-page)",
                    color: submitted && (opt.is_correct || (isSelected && !opt.is_correct)) ? "#fff" : "var(--color-ink-secondary)",
                  }}>
                    {opt.letter}
                  </span>
                  <span>{opt.text}</span>
                </button>
              );
            })}
          </div>

          {/* 反馈区域 */}
          {!submitted && (
            <div style={{ display: "flex", gap: 8 }}>
              <button
                onClick={handleSubmit}
                disabled={!selected}
                style={{
                  flex: 1, padding: "10px 0", borderRadius: "var(--radius-full)",
                  background: selected ? "var(--color-accent)" : "var(--color-divider)",
                  color: selected ? "#fff" : "var(--color-ink-muted)",
                  fontSize: 14, fontWeight: 500, border: "none", cursor: selected ? "pointer" : "default",
                }}
              >
                提交
              </button>
              {question.hint && (
                <button
                  onClick={() => setShowHint(!showHint)}
                  style={{
                    width: 42, height: 42, borderRadius: "50%",
                    display: "grid", placeItems: "center",
                    background: "var(--color-surface)", border: "1.5px solid var(--color-divider)",
                    cursor: "pointer", color: "var(--color-ink-secondary)",
                  }}
                >
                  <Lightbulb size={16} />
                </button>
              )}
            </div>
          )}

          {submitted && (
            <div>
              <div
                className={`feedback-bubble ${isCorrect ? "ok" : "nope"}`}
                style={{
                  padding: "10px 14px", borderRadius: "var(--radius-md)",
                  background: isCorrect ? "var(--color-success-soft)" : "var(--color-error-soft)",
                  fontSize: 14, lineHeight: 1.5, marginBottom: 12,
                }}
              >
                <strong style={{ display: "block", marginBottom: 4 }}>
                  {isCorrect ? "✓ 算对了。" : "✗ 这里有点绕。"}
                </strong>
                <span style={{ color: "var(--color-ink-secondary)" }}>
                  {isCorrect ? "这个思路很清晰。继续往下。" : "换个角度想的话，" + question.options.find(o => o.is_correct)?.text}
                </span>
              </div>
              {/* 闪卡推荐 */}
              {!cardCreated ? (
                <div
                  className="embed-tool-card"
                  style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "10px 14px", borderRadius: "var(--radius-md)",
                    background: "var(--color-surface)", border: "1px solid var(--color-divider)",
                    marginBottom: 8,
                  }}
                >
                  <div className="et-icon" style={{
                    width: 32, height: 32, borderRadius: 8,
                    background: "var(--color-purple-soft)",
                    display: "grid", placeItems: "center", fontSize: 16,
                  }}>
                    🧠
                  </div>
                  <div className="et-text" style={{ flex: 1, fontSize: 13, lineHeight: 1.4 }}>
                    <strong>做成一张卡记住它</strong>
                    {!isCorrect && <br />}
                    {!isCorrect && <span style={{ color: "var(--color-ink-muted)" }}>这个点值得记住</span>}
                  </div>
                  <button
                    onClick={handleCreateCard}
                    style={{
                      padding: "6px 14px", borderRadius: "var(--radius-full)",
                      background: "var(--color-accent)", color: "#fff",
                      border: "none", fontSize: 12, fontWeight: 500, cursor: "pointer",
                    }}
                  >
                    ＋ 创建
                  </button>
                </div>
              ) : (
                <div style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "10px 14px", borderRadius: "var(--radius-md)",
                  background: "var(--color-success-soft)", marginBottom: 8,
                  fontSize: 13, color: "var(--color-success)",
                }}>
                  ✓ 已经加进你的卡片了
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

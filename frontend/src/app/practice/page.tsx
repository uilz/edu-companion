"use client";

import { useState } from "react";
import { CheckCircle, XCircle, ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";
import Card from "@/components/ui/Card";
import MathContent from "@/components/ui/MathContent";

interface Question {
  id: number;
  subject: string;
  difficulty: "基础" | "进阶" | "挑战";
  question: string;
  options: string[];
  answer: string;
  explanation: string;
}

const questions: Question[] = [
  {
    id: 1,
    subject: "高等数学",
    difficulty: "进阶",
    question: "求函数 $f(x) = x^3 - 3x^2 + 2$ 在区间 $[0, 3]$ 上的最大值和最小值。",
    options: [
      "最大值 2，最小值 -2",
      "最大值 2，最小值 -4",
      "最大值 4，最小值 -2",
      "最大值 4，最小值 0",
    ],
    answer: "A",
    explanation:
      "求导得 $f'(x) = 3x^2 - 6x = 3x(x-2)$，临界点 $x=0, 2$。\n\n$f(0) = 2$，$f(2) = 8-12+2 = -2$，$f(3) = 27-27+2 = 2$\n\n最大值为 $f(0) = f(3) = 2$，最小值为 $f(2) = -2$。",
  },
  {
    id: 2,
    subject: "线性代数",
    difficulty: "基础",
    question: "设 $A$ 是 $3 \\times 3$ 矩阵，$\\det(A) = 2$，则 $\\det(2A)$ 等于多少？",
    options: ["4", "8", "16", "6"],
    answer: "C",
    explanation:
      "$\\det(kA) = k^n \\det(A)$，其中 $n$ 为矩阵阶数。\n\n$n=3$，$k=2$，所以 $\\det(2A) = 2^3 \\times 2 = 16$。",
  },
  {
    id: 3,
    subject: "大学物理",
    difficulty: "进阶",
    question: "一个质点沿 $x$ 轴运动，其位置随时间变化为 $x(t) = 4t^3 - 2t + 1$（国际单位），求 $t = 1\\text{s}$ 时的加速度。",
    options: ["$12 \\text{m/s}^2$", "$24 \\text{m/s}^2$", "$6 \\text{m/s}^2$", "$10 \\text{m/s}^2$"],
    answer: "B",
    explanation:
      "速度 $v(t) = x'(t) = 12t^2 - 2$\n\n加速度 $a(t) = v'(t) = 24t$\n\n$t=1$ 时，$a = 24 \\times 1 = 24 \\text{m/s}^2$。",
  },
  {
    id: 4,
    subject: "概率论",
    difficulty: "挑战",
    question: "设随机变量 $X \\sim N(2, 4)$，则 $P(X > 4)$ 等于（已知 $\\Phi(1) = 0.8413$）：",
    options: ["0.1587", "0.3085", "0.8413", "0.1613"],
    answer: "A",
    explanation:
      "$X \\sim N(\\mu, \\sigma^2) = N(2, 4)$，即 $\\mu = 2$，$\\sigma = 2$\n\n$P(X > 4) = P\\left(\\frac{X-2}{2} > \\frac{4-2}{2}\\right) = P(Z > 1)$\n\n$= 1 - \\Phi(1) = 1 - 0.8413 = 0.1587$",
  },
  {
    id: 5,
    subject: "高等数学",
    difficulty: "基础",
    question: "计算不定积分 $\\int x \\cdot e^x \\, dx$。",
    options: [
      "$xe^x - e^x + C$",
      "$xe^x + e^x + C$",
      "$\\frac{1}{2}x^2 e^x + C$",
      "$x^2 e^x - e^x + C$",
    ],
    answer: "A",
    explanation:
      "使用分部积分法，令 $u = x$，$dv = e^x dx$：\n\n$du = dx$，$v = e^x$\n\n$\\int x e^x dx = xe^x - \\int e^x dx = xe^x - e^x + C$",
  },
];

export default function PracticePage() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [difficulty, setDifficulty] = useState<string>("全部");

  const q = questions[currentIndex];
  const isCorrect = selected === q.answer;

  const handleSubmit = () => {
    if (!selected) return;
    setSubmitted(true);
  };

  const handleNext = () => {
    setSelected(null);
    setSubmitted(false);
    setCurrentIndex((i) => (i + 1) % questions.length);
  };

  const handlePrev = () => {
    setSelected(null);
    setSubmitted(false);
    setCurrentIndex((i) => (i - 1 + questions.length) % questions.length);
  };

  const handleReset = () => {
    setSelected(null);
    setSubmitted(false);
  };

  return (
    <main className="min-h-screen bg-[var(--color-bg)]">
      <div className="max-w-3xl mx-auto px-6 py-16">
        {/* Header */}
        <div className="flex items-center justify-between mb-12">
          <h1 className="text-4xl font-bold tracking-tight text-[var(--color-text)]">
            练习
          </h1>
          <div className="flex items-center gap-2">
            <span className="text-sm text-[var(--color-text-muted)]">难度</span>
            {["全部", "基础", "进阶", "挑战"].map((d) => (
              <button
                key={d}
                onClick={() => setDifficulty(d)}
                className={`text-xs px-3 py-1.5 border transition-colors ${
                  difficulty === d
                    ? "border-[var(--color-accent)] text-[var(--color-accent)] bg-[var(--color-accent)]/10"
                    : "border-[var(--color-border)] text-[var(--color-text-muted)] hover:border-[var(--color-border-hover)]"
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        </div>

        {/* Progress */}
        <div className="mb-8">
          <div className="flex items-center justify-between text-xs text-[var(--color-text-muted)] mb-2">
            <span>
              {q.subject} · {q.difficulty}
            </span>
            <span>
              {currentIndex + 1} / {questions.length}
            </span>
          </div>
          <div className="w-full bg-[var(--color-surface)] h-1">
            <div
              className="h-full bg-[var(--color-accent)] transition-all"
              style={{ width: `${((currentIndex + 1) / questions.length) * 100}%` }}
            />
          </div>
        </div>

        {/* Question */}
        <Card>
          <MathContent
            text={q.question}
            className="text-base text-[var(--color-text)] leading-relaxed mb-8 message-content"
          />

          {/* Options */}
          <div className="space-y-3">
            {q.options.map((opt, i) => {
              const letter = String.fromCharCode(65 + i);
              const isSelected = selected === letter;
              const showResult = submitted && isSelected;

              return (
                <button
                  key={letter}
                  onClick={() => !submitted && setSelected(letter)}
                  disabled={submitted}
                  className={`w-full text-left p-4 border text-sm transition-colors ${
                    submitted
                      ? letter === q.answer
                        ? "border-[var(--color-success)] bg-[var(--color-success)]/10 text-[var(--color-success)]"
                        : showResult && !isCorrect
                        ? "border-[var(--color-error)] bg-[var(--color-error)]/10 text-[var(--color-error)]"
                        : "border-[var(--color-border)] text-[var(--color-text-muted)]"
                      : isSelected
                      ? "border-[var(--color-accent)] bg-[var(--color-accent)]/10 text-[var(--color-text)]"
                      : "border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)]"
                  }`}
                >
                  <span className="font-semibold mr-3">{letter}.</span>
                  {opt}
                </button>
              );
            })}
          </div>

          {/* Action buttons */}
          <div className="flex items-center gap-3 mt-8">
            {!submitted ? (
              <button
                onClick={handleSubmit}
                disabled={!selected}
                className="px-6 py-2.5 bg-[var(--color-accent)] text-[var(--color-text)] text-sm font-medium disabled:opacity-30 hover:bg-[var(--color-accent-hover)] transition-colors"
              >
                提交答案
              </button>
            ) : (
              <button
                onClick={handleReset}
                className="px-6 py-2.5 border border-[var(--color-border)] text-[var(--color-text-secondary)] text-sm hover:border-[var(--color-border-hover)] transition-colors"
              >
                <RotateCcw size={14} className="inline mr-1.5" />
                重做
              </button>
            )}
          </div>

          {/* Result feedback */}
          {submitted && (
            <div
              className={`mt-6 p-5 border text-sm leading-relaxed ${
                isCorrect
                  ? "border-[var(--color-success)]/30 bg-[var(--color-success)]/5"
                  : "border-[var(--color-error)]/30 bg-[var(--color-error)]/5"
              }`}
            >
              <div className="flex items-center gap-2 mb-3 font-semibold">
                {isCorrect ? (
                  <>
                    <CheckCircle size={16} className="text-[var(--color-success)]" />
                    <span className="text-[var(--color-success)]">回答正确！</span>
                  </>
                ) : (
                  <>
                    <XCircle size={16} className="text-[var(--color-error)]" />
                    <span className="text-[var(--color-error)]">
                      回答错误，正确答案是 {q.answer}
                    </span>
                  </>
                )}
              </div>
              <div
                className="text-[var(--color-text-secondary)] message-content"
              >
                {q.explanation.split("\n\n").map((para, i) => (
                  <p key={i} className="mb-2 last:mb-0">
                    <MathContent text={para.replace(/\n/g, " ")} as="span" />
                  </p>
                ))}
              </div>
            </div>
          )}
        </Card>

        {/* Navigation */}
        <div className="flex items-center justify-between mt-6">
          <button
            onClick={handlePrev}
            className="flex items-center gap-1 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
          >
            <ChevronLeft size={16} />
            上一题
          </button>
          <button
            onClick={handleNext}
            className="flex items-center gap-1 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
          >
            下一题
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </main>
  );
}

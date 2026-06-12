import { useState } from "react";
import { BookOpen } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import InlinePracticeBlock from "./InlinePracticeBlock";
import PracticeSetBlock from "./PracticeSetBlock";
import { useRenderedContent } from "@/lib/hooks/useRenderedContent";
import { sanitizeHtml } from "@/lib/utils/sanitize";

/** 练习选项的数据结构：选项字母 + 文本内容 */
interface Option {
  letter: string;
  text: string;
}

/** 练习块路由组件：判断 v7多题集 / 交互式练习 / 旧格式，分发到对应组件 */
export function PracticeBlockRouter({ content }: { content: Record<string, unknown> }) {
  // ── 多题格式（来自对话 generate_practice 工具）──
  const questions = content.questions as
    | Array<{ id?: string; stem: string; options?: Array<{ letter: string; text: string; is_correct?: boolean }>; question_type?: string; answer?: string | string[]; analysis?: string }>
    | undefined;
  if (questions && Array.isArray(questions) && questions.length > 0) {
    return (
      <PracticeSetBlock
        questions={questions}
        bankId={content.bank_id as string | undefined}
      />
    );
  }

  // 提取练习数据：交互式练习需要包含 block_id 和 stem
  const blockId = content.block_id as string;
  const stem = content.stem as string;
  const options = (content.options as Option[]) || [];
  const answerType = (content.answer_type as string) || "choice";
  const hint = (content.hint as string) || "再想想思路";

  // 有 block_id 且 stem 存在 → 渲染交互式练习组件
  if (blockId && stem) {
    // 交互式在线练习（支持答题交互和即时反馈）
    return (
      <InlinePracticeBlock
        blockId={blockId}
        questionId={(content.question_id as string) || ""}
        stem={stem}
        options={options}
        answerType={answerType}
        hint={hint}
        onAnswer={async (_blockId, _answer) => {
          // 答题回调——由组件内部处理逻辑
        }}
      />
    );
  }

  // 兜底：以静态方式展示练习内容（兼容旧格式无交互版本）
  return <PracticeBlock content={content} />;
}

/** 旧格式练习块组件：静态展示题目、选项和解析（无交互） */
function PracticeBlock({ content }: { content: Record<string, unknown> }) {
  // 从 content 中提取练习数据
  const subject = (content.subject as string) || "";
  const question = (content.question as string) || "";
  const options = (content.options as string[]) || [];
  const answer = (content.answer as string) || "";
  const explanation = (content.explanation as string) || "";

  const [selectedAnswer, setSelectedAnswer] = useState<string>("");
  const [submitted, setSubmitted] = useState(false);

  const questionHtml = useRenderedContent(question);

  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2">
      <div className="px-3 py-2 border-b border-[var(--color-border)] flex items-center gap-2">
        <BookOpen size={14} className="text-[var(--color-accent)]" />
        <span className="text-xs font-medium text-[var(--color-text)]">
          练习题 {subject && `· ${subject}`}
        </span>
      </div>
      <div className="px-3 py-3">
        <div
          className="text-sm text-[var(--color-text)] leading-relaxed"
          dangerouslySetInnerHTML={{ __html: sanitizeHtml(questionHtml) }}
        />
        {options.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {options.map((opt, i) => {
              const letter = String.fromCharCode(65 + i);
              const isCorrect = opt === answer || letter === answer;
              const isSelected = selectedAnswer === letter;
              return (
                <button
                  key={i}
                  onClick={() => !submitted && setSelectedAnswer(letter)}
                  className="w-full flex items-start gap-2 text-sm px-3 py-2 border transition-colors text-left"
                  style={{
                    backgroundColor: submitted && isCorrect
                      ? "var(--color-success)/10"
                      : isSelected
                        ? "rgba(0, 102, 255, 0.08)"
                        : "transparent",
                    borderColor: submitted && isCorrect
                      ? "var(--color-success)"
                      : isSelected
                        ? "var(--color-accent)"
                        : "var(--color-border)",
                  }}
                >
                  <span className="text-[var(--color-text-muted)] font-mono text-xs w-5 flex-shrink-0">
                    {letter}.
                  </span>
                  <span className="text-[var(--color-text-secondary)] [&_p]:m-0 [&_.katex]:text-sm">
                    <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]} components={{ p: ({ children }) => <>{children}</> }}>
                      {opt}
                    </ReactMarkdown>
                  </span>
                </button>
              );
            })}
          </div>
        )}
        {options.length > 0 && !submitted && (
          <button
            onClick={() => selectedAnswer && setSubmitted(true)}
            disabled={!selectedAnswer}
            className="mt-2 px-4 py-2 bg-[var(--color-accent)] text-white text-sm disabled:opacity-30 hover:opacity-90 active:scale-[0.97] transition-all rounded-lg"
          >
            提交答案
          </button>
        )}
        {submitted && (() => {
          const selectedIdx = selectedAnswer.charCodeAt(0) - 65;
          const selectedText = options[selectedIdx] || "";
          const isCorrect = selectedAnswer === answer || selectedText === answer;
          return (
            <div className="mt-2 text-sm" style={{
              color: isCorrect ? "var(--color-success)" : "var(--color-error)"
            }}>
              {isCorrect
                ? "✓ 回答正确!"
                : `✗ 回答错误，正确答案: ${answer}`}
            </div>
          );
        })()}
        {submitted && explanation && (
          <div className="mt-3 px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)] rounded-lg">
            <div className="text-[10px] text-[var(--color-accent)] font-medium mb-1">
              解析
            </div>
            <div className="text-xs text-[var(--color-text-secondary)] leading-relaxed [&_p]:m-0 [&_.katex]:text-xs">
              <ReactMarkdown remarkPlugins={[remarkMath]} rehypePlugins={[rehypeKatex]} components={{ p: ({ children }) => <>{children}</> }}>
                {explanation}
              </ReactMarkdown>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

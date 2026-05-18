"use client";

import { useMemo } from "react";
import { Loader2, FileText, Image, GitBranch as MindMap, BookOpen } from "lucide-react";
import MathContent from "@/components/ui/MathContent";
import InlinePracticeBlock from "./InlinePracticeBlock";
import MediaSearchBlock from "./MediaSearchBlock";
import VideoEmbed from "./VideoEmbed";
import { renderContent } from "@/lib/math";
import type { ResponseBlock } from "@/types";

interface ResponseBlockRendererProps {
  block: ResponseBlock;
}

export default function ResponseBlockRenderer({ block }: ResponseBlockRendererProps) {
  const { type, status, content } = block;

  if (status === "generating") {
    return <GeneratingPlaceholder type={type} />;
  }

  if (status === "failed") {
    return (
      <div className="border border-[var(--color-error)] bg-[var(--color-error)]/5 px-4 py-3 mt-2">
        <div className="flex items-center gap-2 text-[var(--color-error)]">
          <span className="text-xs font-medium">生成失败</span>
        </div>
        <div className="text-xs text-[var(--color-text-muted)] mt-1">
          {(content as Record<string, unknown>)?.error as string || "未知错误，点击重试"}
        </div>
      </div>
    );
  }

  switch (type) {
    case "text":
      return <TextBlock content={content} sources={block.sources} />;
    case "video":
      return <VideoBlockRouter content={content} />;
    case "practice":
      return <PracticeBlockRouter content={content} />;
    case "image":
      return <ImageBlock content={content} />;
    case "mindmap":
      return <MindMapBlock content={content} />;
    case "document":
      return <DocumentBlock content={content} />;
    default:
      return null;
  }
}

function GeneratingPlaceholder({ type }: { type: string }) {
  const labels: Record<string, string> = {
    image: "正在生成图像...",
    mindmap: "正在生成思维导图...",
    document: "正在生成文档...",
  };

  const icons: Record<string, React.ReactNode> = {
    image: <Image size={16} />,
    mindmap: <MindMap size={16} />,
    document: <FileText size={16} />,
  };

  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3 mt-2">
      <div className="flex items-center gap-2 text-[var(--color-accent)]">
        <Loader2 size={14} className="animate-spin" />
        <span className="text-xs font-medium">
          {labels[type] || "生成中..."}
        </span>
      </div>
      <div className="mt-2 h-1 bg-[var(--color-border)] overflow-hidden">
        <div
          className="h-full bg-[var(--color-accent)] animate-pulse"
          style={{ width: "60%" }}
        />
      </div>
    </div>
  );
}

function TextBlock({ content, sources }: { content: Record<string, unknown>; sources?: string[] }) {
  const text = (content.text as string) || "";
  const renderedHtml = useMemo(() => renderContent(text), [text]);

  return (
    <div>
      <div
        className="message-content text-sm leading-relaxed [&_p]:mb-2 [&_p:last-child]:mb-0"
        dangerouslySetInnerHTML={{ __html: renderedHtml }}
      />
      {sources && sources.length > 0 && (
        <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
          <div className="flex flex-wrap gap-1.5">
            {sources.map((s, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] bg-[var(--color-accent)]/10 text-[var(--color-accent)] border border-[var(--color-accent)]/20"
              >
                <BookOpen size={10} />
                {s}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function VideoBlockRouter({ content }: { content: Record<string, unknown> }) {
  const url = (content.url as string) || "";
  const title = (content.title as string) || "";
  const thumbnail = (content.thumbnail as string) || "";
  const platforms = content.platforms as Array<unknown> | undefined;

  // If this has platforms array → it's a MediaSearch result → show MediaSearchBlock
  if (platforms && platforms.length > 0) {
    return <MediaSearchBlock content={content} />;
  }

  // If URL looks like a video platform → embed it
  if (url && /bilibili\.com|youtu\.be|youtube\.com|\.mp4|\.webm/i.test(url)) {
    return <VideoEmbed url={url} title={title} thumbnail={thumbnail} />;
  }

  // Fallback: show MediaSearchBlock (handles legacy format)
  return <MediaSearchBlock content={content} />;
}

function PracticeBlockRouter({ content }: { content: Record<string, unknown> }) {
  // Check if this is an interactive inline practice block (has block_id + stem)
  const blockId = content.block_id as string;
  const stem = content.stem as string;
  const options = (content.options as Option[]) || [];
  const answerType = (content.answer_type as string) || "choice";
  const hint = (content.hint as string) || "再想想思路";

  if (blockId && stem) {
    // Interactive inline practice
    return (
      <InlinePracticeBlock
        blockId={blockId}
        questionId={(content.question_id as string) || ""}
        stem={stem}
        options={options}
        answerType={answerType}
        hint={hint}
        onAnswer={async (_blockId, _answer) => {
          // Answer callback - handled internally by the component
        }}
      />
    );
  }

  // Fallback to passive display (old format)
  return <PracticeBlock content={content} />;
}

interface Option {
  letter: string;
  text: string;
}

function PracticeBlock({ content }: { content: Record<string, unknown> }) {
  const subject = (content.subject as string) || "";
  const question = (content.question as string) || "";
  const options = (content.options as string[]) || [];
  const answer = (content.answer as string) || "";
  const explanation = (content.explanation as string) || "";

  const questionHtml = useMemo(() => renderContent(question), [question]);

  const explanationHtml = useMemo(() => renderContent(explanation), [explanation]);

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
          dangerouslySetInnerHTML={{ __html: questionHtml }}
        />
        {options.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {options.map((opt, i) => {
              const letter = String.fromCharCode(65 + i);
              const isCorrect = opt === answer || letter === answer;
              return (
                <div
                  key={i}
                  className="flex items-start gap-2 text-sm px-3 py-2 border border-[var(--color-border)]"
                  style={{
                    backgroundColor: isCorrect
                      ? "var(--color-success)/10"
                      : "transparent",
                    borderColor: isCorrect
                      ? "var(--color-success)"
                      : "var(--color-border)",
                  }}
                >
                  <span className="text-[var(--color-text-muted)] font-mono text-xs">
                    {letter}.
                  </span>
                  <span className="text-[var(--color-text-secondary)]">{opt}</span>
                </div>
              );
            })}
          </div>
        )}
        {explanation && (
          <div className="mt-3 px-3 py-2 bg-[var(--color-bg)] border border-[var(--color-border)]">
            <div className="text-[10px] text-[var(--color-accent)] font-medium mb-1">
              解析
            </div>
            <div className="text-xs text-[var(--color-text-secondary)] leading-relaxed">
              {explanation}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ImageBlock({ content }: { content: Record<string, unknown> }) {
  const prompt = (content.prompt as string) || "";
  const url = (content.url as string) || "";

  return (
    <div className="mt-2">
      {url ? (
        <div className="border border-[var(--color-border)] overflow-hidden">
          <img
            src={url}
            alt={prompt || "Generated image"}
            className="w-full max-w-md"
            loading="lazy"
          />
          {prompt && (
            <div className="px-3 py-2 bg-[var(--color-surface)]">
              <div className="text-[10px] text-[var(--color-text-muted)]">
                🎨 {prompt}
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-3">
          <div className="text-xs text-[var(--color-text-muted)]">
            🎨 {prompt || "图像"}
          </div>
        </div>
      )}
    </div>
  );
}

function MindMapBlock({ content }: { content: Record<string, unknown> }) {
  const topic = (content.topic as string) || "";

  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2">
      <div className="px-3 py-2 border-b border-[var(--color-border)] flex items-center gap-2">
        <MindMap size={14} className="text-[var(--color-accent)]" />
        <span className="text-xs font-medium text-[var(--color-text)]">
          思维导图
        </span>
      </div>
      <div className="px-3 py-3">
        <div className="text-sm text-[var(--color-text-secondary)]">
          🧠 {topic || "知识结构"}
        </div>
        <div className="text-[10px] text-[var(--color-text-muted)] mt-2">
          点击展开查看完整思维导图
        </div>
      </div>
    </div>
  );
}

function DocumentBlock({ content }: { content: Record<string, unknown> }) {
  const title = (content.title as string) || "文档";
  const format = (content.format as string) || "pdf";
  const url = (content.url as string) || "";
  const pageCount = content.page_count as number | undefined;

  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2 px-3 py-2">
      <div className="flex items-center gap-2">
        <FileText size={14} className="text-[var(--color-accent)] flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="text-sm text-[var(--color-text)] truncate">{title}</div>
          <div className="text-[10px] text-[var(--color-text-muted)]">
            {format.toUpperCase()}
            {pageCount && ` · ${pageCount} 页`}
          </div>
        </div>
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-[var(--color-accent)] hover:underline flex-shrink-0"
          >
            下载
          </a>
        )}
      </div>
    </div>
  );
}

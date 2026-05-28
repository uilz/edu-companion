"use client";

import { useMemo } from "react";
import { Loader2, FileText, Image, GitBranch as MindMap, BookOpen, Volume2 } from "lucide-react";
import MathContent from "@/components/ui/MathContent";
import InlinePracticeBlock from "./InlinePracticeBlock";
import MediaSearchBlock from "./MediaSearchBlock";
import VideoEmbed from "./VideoEmbed";
import SecretarySuggestionsBlock from "./SecretarySuggestionsBlock";
import ExpandBlock from "./ExpandBlock";
import { renderContent } from "@/lib/math";
import { useRenderedContent } from "@/lib/useRenderedContent";
import type { ResponseBlock } from "@/types";

// ResponseBlockRenderer 组件的 props 类型：接收一个 ResponseBlock 数据块
interface ResponseBlockRendererProps {
  block: ResponseBlock;
}

/** 主渲染组件：根据 block 的状态和类型，分发到对应的子组件进行渲染 */
export default function ResponseBlockRenderer({ block }: ResponseBlockRendererProps) {
  const { type, status, content } = block;

  // 状态：生成中 —— 显示加载占位动画
  if (status === "generating") {
    return <GeneratingPlaceholder type={type} />;
  }

  // 状态：失败 —— 显示错误信息，支持重试提示
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

  // 根据内容块 type 分发到对应的渲染子组件
  switch (type) {
    case "text":
      return <TextBlock content={content} sources={block.sources} />;
    case "video":
      return <VideoBlockRouter content={content} />;
    case "practice":
      return <PracticeBlockRouter content={content} />;
    case "image":
      return <ImageBlock content={content} />;
    case "audio":
      return <AudioBlock content={content} />;
    case "mindmap":
      return <MindMapBlock content={content} />;
    case "document":
      return <DocumentBlock content={content} />;
    case "secretary_suggestions":
      return <SecretarySuggestionsBlock content={content} />;
    case "expand":
      return (
        <ExpandBlock
          skillName={(content.skill_name as string) || ""}
          explanation={(content.explanation as string) || ""}
        />
      );
    default:
      return null;
  }
}

/** 生成中的占位组件：根据内容类型显示对应的 loading 图标和动画 */
function GeneratingPlaceholder({ type }: { type: string }) {
  // 各类型对应的加载提示文本
  const labels: Record<string, string> = {
    image: "正在生成图像...",
    audio: "正在合成语音...",
    mindmap: "正在生成思维导图...",
    document: "正在生成文档...",
  };

  // 各类型对应的加载图标
  const icons: Record<string, React.ReactNode> = {
    image: <Image size={16} />,
    audio: <Volume2 size={16} />,
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

/** 纯文本块组件：渲染 Markdown/数学公式 转换后的 HTML，并显示引用来源 */
function TextBlock({ content, sources }: { content: Record<string, unknown>; sources?: string[] }) {
  const text = (content.text as string) || "";
  const renderedHtml = useRenderedContent(text);

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

/** 视频块路由组件：判断内容是视频嵌入还是媒体搜索结果，分发到对应组件 */
function VideoBlockRouter({ content }: { content: Record<string, unknown> }) {
  const url = (content.url as string) || "";
  const title = (content.title as string) || "";
  const thumbnail = (content.thumbnail as string) || "";
  const platforms = content.platforms as Array<unknown> | undefined;

  // 如果有 platforms 数组 → 是媒体搜索结果 → 使用 MediaSearchBlock 展示
  // If this has platforms array → it's a MediaSearch result → show MediaSearchBlock
  if (platforms && platforms.length > 0) {
    return <MediaSearchBlock content={content} />;
  }

  // 如果 URL 匹配视频平台 → 使用 VideoEmbed 嵌入播放
  // If URL looks like a video platform → embed it
  if (url && /bilibili\.com|youtu\.be|youtube\.com|\.mp4|\.webm/i.test(url)) {
    return <VideoEmbed url={url} title={title} thumbnail={thumbnail} />;
  }

  // 兜底：显示 MediaSearchBlock（兼容旧格式）
  // Fallback: show MediaSearchBlock (handles legacy format)
  return <MediaSearchBlock content={content} />;
}

/** 练习块路由组件：判断是交互式练习还是旧格式被动展示，分发到对应组件 */
function PracticeBlockRouter({ content }: { content: Record<string, unknown> }) {
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

/** 练习选项的数据结构：选项字母 + 文本内容 */
interface Option {
  letter: string;
  text: string;
}

/** 旧格式练习块组件：静态展示题目、选项和解析（无交互） */
function PracticeBlock({ content }: { content: Record<string, unknown> }) {
  // 从 content 中提取练习数据
  const subject = (content.subject as string) || "";
  const question = (content.question as string) || "";
  const options = (content.options as string[]) || [];
  const answer = (content.answer as string) || "";
  const explanation = (content.explanation as string) || "";

  const questionHtml = useRenderedContent(question);

  const explanationHtml = useRenderedContent(explanation);

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
              const letter = String.fromCharCode(65 + i);  // A, B, C, D...
              const isCorrect = opt === answer || letter === answer;  // 判断该选项是否为正确答案
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

/** 图像块组件：显示生成的图片及对应的提示词 */
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

/** 思维导图块组件：显示思维导图标题和入口提示 */
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

/** 文档块组件：显示文档标题、格式及下载链接 */
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

/** 语音块组件：根据是否有 URL 显示语音生成中状态或播放器 */
function AudioBlock({ content }: { content: Record<string, unknown> }) {
  const url = (content.url as string) || "";
  const text = (content.text as string) || "";
  const skillId = (content.skill_id as string) || "";

  if (!url) {
    return (
      <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2 px-3 py-2">
        <div className="flex items-center gap-2">
          <Volume2 size={14} className="text-[var(--color-accent)]" />
          <span className="text-xs text-[var(--color-text-muted)]">语音生成中…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="border border-[var(--color-border)] bg-[var(--color-surface)] mt-2">
      <div className="px-3 py-2 border-b border-[var(--color-border)] flex items-center gap-2">
        <Volume2 size={14} className="text-[var(--color-accent)]" />
        <span className="text-xs font-medium text-[var(--color-text)]">
          语音讲解 {skillId && `· ${skillId}`}
        </span>
      </div>
      <div className="px-3 py-3">
        <audio controls className="w-full" style={{ height: 36 }}>
          <source src={url} type="audio/mpeg" />
        </audio>
        {text && (
          <div className="text-[10px] text-[var(--color-text-muted)] mt-2 line-clamp-2">
            {text}
          </div>
        )}
      </div>
    </div>
  );
}

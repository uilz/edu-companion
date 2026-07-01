"use client";

import type { ResponseBlock } from "@/types";
import { GeneratingPlaceholder } from "./GeneratingPlaceholder";
import { TextBlock } from "./TextBlock";
import { VideoBlockRouter } from "./VideoBlockRouter";
import { PracticeBlockRouter } from "./PracticeBlock";
import { ImageBlock } from "./ImageBlock";
import { MindMapBlock } from "./MindMapBlock";
import { DocumentBlock } from "./DocumentBlock";
import { AudioBlock } from "./AudioBlock";
import SecretarySuggestionsBlock from "./SecretarySuggestionsBlock";
import ExpandBlock from "./ExpandBlock";
import QuestionBlock from "./QuestionBlock";

interface ResponseBlockRendererProps {
  block: ResponseBlock;
}

/** 主渲染组件：根据 block 的状态和类型，分发到对应的子组件进行渲染 */
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
    case "question":
      return <QuestionBlock content={content} convId={block.conv_id} />;
    default:
      // Fallback for unhandled tool block types — show raw content
      return (
        <div className="p-3 rounded-xl bg-[var(--color-bg-secondary)] border border-[var(--color-border)]">
          <div className="text-xs font-medium text-[var(--color-text-muted)] mb-1">
            {type === "tool_block" ? "🔧 工具调用结果" : `📦 ${type}`}
          </div>
          <div className="text-sm text-[var(--color-text)] whitespace-pre-wrap">
            {typeof content === "string" ? content : JSON.stringify(content, null, 2)}
          </div>
        </div>
      );
  }
}

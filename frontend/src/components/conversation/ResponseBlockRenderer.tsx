"use client";

import type { ResponseBlock } from "@/types";
import { GeneratingPlaceholder } from "./blocks/GeneratingPlaceholder";
import { TextBlock } from "./blocks/TextBlock";
import { VideoBlockRouter } from "./blocks/VideoBlockRouter";
import { PracticeBlockRouter } from "./blocks/PracticeBlock";
import { ImageBlock } from "./blocks/ImageBlock";
import { MindMapBlock } from "./blocks/MindMapBlock";
import { DocumentBlock } from "./blocks/DocumentBlock";
import { AudioBlock } from "./blocks/AudioBlock";
import SecretarySuggestionsBlock from "./SecretarySuggestionsBlock";
import ExpandBlock from "./ExpandBlock";

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

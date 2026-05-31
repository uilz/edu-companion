"use client";

import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeSentenceSegment from "@/lib/rehype-sentence-segment";
import "katex/dist/katex.min.css";

interface Props {
  content: string;
}

export default function MarkdownRenderer({ content }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkMath]}
      rehypePlugins={[rehypeKatex, rehypeSentenceSegment]}
    >
      {content}
    </ReactMarkdown>
  );
}

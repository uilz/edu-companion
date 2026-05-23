"use client";

// 导入 React Hooks 和 Markdown 渲染工具
import { useEffect, useRef, useMemo } from "react";
import { renderMarkdown } from "@/lib/math";

// 聊天消息组件的属性类型定义
interface ChatMessageProps {
  role: "user" | "assistant";   // 消息角色：用户或助手
  content: string;               // 消息文本内容（支持 Markdown 与 LaTeX）
  timestamp: number;             // 消息时间戳（毫秒）
}

// 聊天消息气泡组件 —— 根据角色渲染不同样式的消息
export default function ChatMessage({ role, content, timestamp }: ChatMessageProps) {
  // 引用消息内容容器 DOM 元素
  const ref = useRef<HTMLDivElement>(null);

  // 使用 useMemo 缓存渲染后的 HTML 内容，仅当 content 变化时重新计算
  const renderedContent = useMemo(() => {
    // renderMarkdown 内部已处理 LaTeX（流水线的第 2 步和第 5 步）。
    // 若先调用 renderMath 再调用 renderMarkdown，会破坏 KaTeX 生成的 HTML（第 3 步会 HTML 转义 < >）。
    return renderMarkdown(content);
  }, [content]);

  // 将时间戳格式化为中文时区的 "时:分" 字符串
  const time = new Date(timestamp).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });

  // 判断当前消息是否来自用户，用于样式分支
  const isUser = role === "user";

  return (
    // 外层容器：用户消息右对齐，助手消息左对齐
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3`}>
      {/* 消息气泡本体 */}
      <div
        className={`max-w-[80%] px-4 py-3 ${
          isUser
            ? "bg-[var(--color-accent)] text-[#ffffff]"       // 用户消息：强调色背景 + 白色文字
            : "bg-[var(--color-surface)] text-[var(--color-text)]" // 助手消息：表面色背景 + 主文字色
        }`}
      >
        {/* Markdown 渲染后的内容区域 */}
        <div
          ref={ref}
          className="message-content text-sm leading-relaxed [&_p]:mb-2 [&_p:last-child]:mb-0"
          dangerouslySetInnerHTML={{ __html: renderedContent }}
        />
        {/* 消息时间戳 */}
        <div
          className={`text-[10px] mt-1 ${
            isUser ? "text-[#ffffff]/50 text-right" : "text-[var(--color-text-muted)]"
          }`}
        >
          {time}
        </div>
      </div>
    </div>
  );
}

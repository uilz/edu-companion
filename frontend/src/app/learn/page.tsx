// 启用客户端交互模式（Next.js App Router 客户端组件）
"use client";

// 导入对话管理 Hook，提供对话状态和操作方法
import { useConversation } from "@/components/conversation/useConversation";
// 导入对话面板 UI 组件，用于渲染聊天界面
import ConversationPanel from "@/components/conversation/ConversationPanel";

// 学习页面入口组件
export default function LearnPage() {
  // 初始化对话逻辑 Hook，返回对话状态和方法
  const conv = useConversation();
  // 将对话数据和方法作为 props 传递给 ConversationPanel 进行渲染
  return <ConversationPanel {...conv} />;
}

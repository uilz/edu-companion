"use client";

import { useConversation } from "@/components/conversation/useConversation";
import ConversationPanel from "@/components/conversation/ConversationPanel";

export default function LearnPage() {
  const conv = useConversation();
  return <ConversationPanel {...conv} />;
}

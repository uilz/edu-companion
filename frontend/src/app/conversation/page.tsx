"use client";

import { useConversation } from "@/hooks/conversation/useConversation";
import ConversationPanel from "@/components/conversation/core/ConversationPanel";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";

export default function ConversationPage() {
  const conv = useConversation();

  return (
    <ErrorBoundary>
      <ConversationPanel {...conv} />
    </ErrorBoundary>
  );
}

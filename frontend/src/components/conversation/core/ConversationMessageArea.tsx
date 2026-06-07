"use client";

import React from "react";
import MessageList from "@/components/conversation/core/MessageList";
import ConversationChatInput from "@/components/conversation/core/ChatInput";
import SubBranchBanner from "@/components/conversation/banners/SubBranchBanner";
import SwitchBanner from "@/components/conversation/banners/SwitchBanner";
import ErrorBanner from "@/components/conversation/banners/ErrorBanner";
import SecretaryInlineBanner from "@/components/notification/SecretaryInlineBanner";
import type { TreeNode, ResponseBlock } from "@/types";

// ── Props ──
export interface ConversationMessageAreaProps {
  messages: TreeNode[];
  responseBlocks: ResponseBlock[];
  isLoading: boolean;
  statusMessage?: string;
  activeConversationId: string | null;
  replyingToId: string | null;

  onSend: (text: string) => void;
  onDeleteMessage: (id: string) => void;
  onEditMessage: (messageId: string, newText: string) => Promise<number>;
  onVersionSwitch: (messageId: string, direction: "prev" | "next", currentIndex?: number) => Promise<{ index: number; total: number } | null>;

  switchBanner?: {
    domainName: string;
    topicName: string;
    fullPath?: string;
    partitionId?: string;
  } | null;
  switchBannerPartitionName?: string;
  handleSwitchConfirm?: () => void;
  handleSwitchDismiss?: () => void;

  isInSubBranch?: boolean;
  subBranchQuotedText?: string;
  exitSubBranch?: () => void;

  convError?: string | null;

  socraticEnabled?: boolean;
  followUpMode?: "ask" | "answer";
  setFollowUpMode?: (mode: "ask" | "answer") => void;

  renderBottomControls?: () => React.ReactNode;
  messageListClassName?: string;
  placeholder?: string;
}

/**
 * ConversationMessageArea — 共享消息+输入区域
 *
 * 封装横幅 → 消息列表 → 苏格拉底条 → 输入框 → 底部控件的
 * 完整垂直栈。ConversationPanel / FocusModePanel 共享此组件。
 */
export default function ConversationMessageArea(props: ConversationMessageAreaProps) {
  const {
    messages,
    responseBlocks,
    isLoading,
    statusMessage,
    activeConversationId,
    replyingToId,
    onSend,
    onDeleteMessage,
    onEditMessage,
    onVersionSwitch,
    switchBanner,
    switchBannerPartitionName,
    handleSwitchConfirm,
    handleSwitchDismiss,
    isInSubBranch,
    subBranchQuotedText,
    exitSubBranch,
    convError,
    socraticEnabled,
    followUpMode,
    setFollowUpMode,
    renderBottomControls,
    messageListClassName,
    placeholder,
  } = props;

  return (
    <>
      {isInSubBranch && exitSubBranch && subBranchQuotedText && (
        <SubBranchBanner quotedText={subBranchQuotedText} onExit={exitSubBranch} />
      )}

      {switchBanner && handleSwitchConfirm && handleSwitchDismiss && (
        <SwitchBanner
          domainName={switchBanner.domainName}
          topicName={switchBanner.topicName}
          fullPath={switchBanner.fullPath || switchBannerPartitionName || ""}
          onSwitch={handleSwitchConfirm}
          onDismiss={handleSwitchDismiss}
        />
      )}

      {convError && <ErrorBanner message={convError} />}

      <div className="flex-1 overflow-hidden flex flex-col">
        <div className={messageListClassName || "flex-1 overflow-y-auto space-y-4"}>
          <SecretaryInlineBanner conversationId={activeConversationId} />
          <MessageList
            messages={messages}
            responseBlocks={responseBlocks}
            isLoading={isLoading}
            statusMessage={statusMessage}
            replyingToId={replyingToId}
            conversationId={activeConversationId}
            onDeleteMessage={onDeleteMessage}
            onEditMessage={onEditMessage}
            onVersionSwitch={onVersionSwitch}
            onSend={onSend}
          />
        </div>
      </div>

      <div className="flex-shrink-0 border-t border-[var(--color-border)] bg-[var(--color-bg)]">
        <ConversationChatInput
          onSend={onSend}
          disabled={isLoading}
          conversationId={activeConversationId}
          placeholder={placeholder}
        />
      </div>

      {renderBottomControls?.()}
    </>
  );
}

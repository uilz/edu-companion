"use client";

import React from "react";
import MessageList from "@/components/conversation/core/MessageList";
import ConversationChatInput from "@/components/conversation/core/ChatInput";
import SubBranchBanner from "@/components/conversation/banners/SubBranchBanner";
import SwitchBanner from "@/components/conversation/banners/SwitchBanner";
import ErrorBanner from "@/components/conversation/banners/ErrorBanner";
import SecretaryInlineBanner from "@/components/notification/SecretaryInlineBanner";
import StreamingControls from "@/components/conversation/core/StreamingControls";
import type { MessageNode } from "@/types";

// ── Props ──
export interface ConversationMessageAreaProps {
  messages: MessageNode[];
  isLoading: boolean;
  statusMessage?: string;
  activeConversationId: string | null;
  replyingToId: string | null;

  onSend: (text: string) => void;
  onDeleteMessage: (id: string) => void;
  onEditMessage: (messageId: string, newText: string) => Promise<number>;

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

  isFeynmanMode?: boolean;
  onFeynmanTeach?: (messageId: string, messageText: string, conversationId: string) => void;

  convError?: string | null;

  socraticEnabled?: boolean;
  followUpMode?: "ask" | "answer";
  setFollowUpMode?: (mode: "ask" | "answer") => void;

  renderBottomControls?: () => React.ReactNode;
  placeholder?: string;

  breadcrumb?: React.ReactNode;
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
    isLoading,
    statusMessage,
    activeConversationId,
    replyingToId,
    onSend,
    onDeleteMessage,
    onEditMessage,
    switchBanner,
    switchBannerPartitionName,
    handleSwitchConfirm,
    handleSwitchDismiss,
    isInSubBranch,
    subBranchQuotedText,
    exitSubBranch,
    isFeynmanMode,
    onFeynmanTeach,
    convError,
    socraticEnabled,
    followUpMode,
    setFollowUpMode,
    renderBottomControls,
    placeholder,
    breadcrumb,
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
        <SecretaryInlineBanner conversationId={activeConversationId} />
        <MessageList
            messages={messages}
            isLoading={isLoading}
            statusMessage={statusMessage}
            replyingToId={replyingToId}
            conversationId={activeConversationId}
            isFeynmanMode={isFeynmanMode}
            onDeleteMessage={onDeleteMessage}
            onEditMessage={onEditMessage}
            onSend={onSend}
            onFeynmanTeach={onFeynmanTeach}
            breadcrumb={breadcrumb}
          />
        </div>

      {/* 流式控制按钮（运行时 / 暂停时显示） */}
      {isLoading && (
        <div className="flex-shrink-0 flex items-center justify-between px-4 border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
          <StreamingControls />
        </div>
      )}

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

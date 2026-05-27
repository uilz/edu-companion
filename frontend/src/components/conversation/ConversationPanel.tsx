"use client";

import React from "react";
import {
  Menu, X, Bot, ChevronLeft, ChevronRight,
} from "lucide-react";
import type { Partition, TreeNode, ResponseBlock } from "@/types";
import Phase8Sidebar from "@/components/conversation/Phase8Sidebar";
import MessageList from "@/components/conversation/MessageList";
import ConversationChatInput from "@/components/conversation/ChatInput";
import type { UseConversationReturn } from "@/components/conversation/useConversation";

/**
 * 新建分区弹窗组件
 * - 显示一个模态对话框，让用户输入分区名称和选择 Emoji
 * - 通过 open 控制显隐，onCreate 回调将 name 和 emoji 传递出去
 */
function NewPartitionDialog({
  open,
  onClose,
  onCreate,
}: {
  open: boolean;
  onClose: () => void;
  onCreate: (name: string, emoji: string) => void;
}) {
  // 分区名称和 Emoji 的本地状态
  const [name, setName] = React.useState("");
  const [emoji, setEmoji] = React.useState("📐");

  // 弹窗未打开时直接返回 null，不渲染任何内容
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-[var(--color-bg)] border border-[var(--color-border)] w-full max-w-sm mx-4 rounded-xl" onClick={(e) => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-[var(--color-border)] flex items-center justify-between">
          <h3 className="text-sm font-semibold text-[var(--color-text)]">
            新建分区
          </h3>
          <button onClick={onClose} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <X size={16} />
          </button>
        </div>
        <div className="px-4 py-4 space-y-3">
          <div>
            <label className="text-xs text-[var(--color-text-muted)] block mb-1">分区名称</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如: 高等数学-极限"
              className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 rounded-lg focus:outline-none focus:border-[var(--color-border-hover)]"
              autoFocus
            />
          </div>
          <div>
            <label className="text-xs text-[var(--color-text-muted)] block mb-1">Emoji</label>
            <input value={emoji} onChange={(e) => setEmoji(e.target.value)} className="w-16 bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 text-center rounded-lg" />
          </div>
        </div>
        <div className="px-4 py-3 border-t border-[var(--color-border)] flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-[var(--color-text-secondary)]">取消</button>
          <button onClick={() => { if (name.trim()) { onCreate(name.trim(), emoji); setName(""); setEmoji("📐"); onClose(); } }} disabled={!name.trim()} className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white rounded-lg disabled:opacity-30">
            创建
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * 上下文切换横幅组件
 * - 当检测到用户正在讨论某个学科/知识点时，显示此横幅提示切换会话
 * - domainName: 学科名称；topicName: 知识点名称（可选）
 * - onSwitch: 用户点击"切换"后的回调；onDismiss: 点击"留在此处"的回调
 */
function SwitchBanner({
  domainName, topicName, fullPath, onSwitch, onDismiss,
}: {
  domainName: string;
  topicName: string;
  fullPath: string;
  onSwitch: () => void;
  onDismiss: () => void;
}) {
  return (
    <div className="mx-4 mt-2 px-4 py-3 bg-[var(--color-accent)]/10 border border-[var(--color-accent)]/30 rounded-lg">
      <div className="flex items-start gap-3">
        <span className="text-lg">🔀</span>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-[var(--color-text)] leading-relaxed">
            检测到你在聊 <strong>{fullPath || `${domainName}${topicName ? ` → ${topicName}` : ""}`}</strong>，要切换到对应会话吗？
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={onSwitch}
            className="px-3 py-1.5 text-xs bg-[var(--color-accent)] text-white hover:bg-[var(--color-accent-hover)] rounded-lg transition-colors"
          >
            切换
          </button>
          <button
            onClick={onDismiss}
            className="px-2 py-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            留在此处
          </button>
        </div>
      </div>
    </div>
  );
}

/**
 * 移动端底部弹出侧栏组件
 * - 在移动端以底部 sheet 的形式展示分区导航
 * - 点击遮罩层或关闭按钮均可关闭
 */
function MobileBottomSheet({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex flex-col justify-end">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-[var(--color-bg)] border-t border-[var(--color-border)] max-h-[70vh] flex flex-col rounded-t-xl">
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-border)]">
          <span className="text-sm font-semibold text-[var(--color-text)]">导航</span>
          <button onClick={onClose} className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]">
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-hidden">{children}</div>
      </div>
    </div>
  );
}

/**
 * ConversationPanel — 对话面板主布局组件
 * - 根据 isDesktop 值自适应渲染移动端或桌面端布局
 * - 接收 useConversation hook 返回的所有状态和回调，组合各子组件
 */
export default function ConversationPanel(props: UseConversationReturn) {
  // 从 props 中解构所有状态变量
  const {
    // State — 对话面板状态
    partitions,
    selectedPartitionId,
    activeConversationId,
    messages,
    responseBlocks,
    isLoading,
    statusMessage,
    switchBanner,
    showPartitionSidebar,
    sidebarCollapsed,
    showNewPartition,
    loadingPartitions,
    convError,
    isDesktop,
    activePartition,

    // Handlers — 事件处理回调
    handleSelectConversation,
    handleNewConversation,
    handleSend,
    handleDeleteMessage,
    handleEditMessage,
    handleVersionSwitch,
    handleCreatePartition,
    handleRenamePartition,
    handleSwitchConfirm,
    handleSwitchDismiss,
    setShowPartitionSidebar,
    setShowNewPartition,
    setSidebarCollapsed,
    loadPartitions,
  } = props;

  // ── Mobile layout: 移动端竖屏布局 ──
  // 以底部导航栏上方为容器，顶部显示标题栏和菜单按钮，底部是输入框
  if (!isDesktop) {
    return (
      <div
        className="fixed inset-0 bg-[var(--color-bg)] z-30 flex flex-col"
        style={{ bottom: "var(--bottom-nav-height)" }}
      >
        {/* 移动端顶部标题栏：菜单按钮 + 当前分区名称 */}
        <div className="flex-shrink-0 border-b border-[var(--color-border)] px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setShowPartitionSidebar(true)}
            className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)]"
          >
            <Menu size={20} />
          </button>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-semibold text-[var(--color-text)] truncate">
              {activePartition
                ? `${activePartition.emoji} ${activePartition.name}`
                : "对话"}
            </div>
          </div>
        </div>

        {/* 移动端内容区域：切换横幅 + 错误提示 + 消息列表 + 输入框 */}
        <div className="flex-1 overflow-hidden flex flex-col">
          {/* 移动端切换横幅 */}
          {switchBanner && (
            <SwitchBanner
              domainName={switchBanner.domainName}
              topicName={switchBanner.topicName}
              fullPath={switchBanner.fullPath}
              onSwitch={handleSwitchConfirm}
              onDismiss={handleSwitchDismiss}
            />
          )}
          {/* 移动端错误提示 */}
          {convError && (
            <div className="flex-shrink-0 mx-4 mt-2 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
              {convError}
            </div>
          )}
          {/* 移动端消息列表 */}
          <MessageList
            messages={messages}
            responseBlocks={responseBlocks}
            isLoading={isLoading}
            statusMessage={statusMessage}
            onDeleteMessage={handleDeleteMessage}
            onEditMessage={handleEditMessage}
            onVersionSwitch={handleVersionSwitch}
          />
          {/* 移动端聊天输入框 */}
          <ConversationChatInput
            onSend={handleSend}
            disabled={isLoading}
            conversationId={activeConversationId}
          />
        </div>

        {/* 移动端底部弹出分区侧栏 */}
        {showPartitionSidebar && (
          <MobileBottomSheet onClose={() => setShowPartitionSidebar(false)}>
            <Phase8Sidebar
              partitions={partitions}
              selectedPartitionId={selectedPartitionId}
              activeConversationId={activeConversationId}
              onSelectConversation={handleSelectConversation}
              onCreatePartition={() => {
                setShowPartitionSidebar(false);
                setShowNewPartition(true);
              }}
              loading={loadingPartitions}
              onNewConversation={(level, parentId, partitionId) => {
                setShowPartitionSidebar(false);
                handleNewConversation(level, parentId, partitionId);
              }}
              onTreeChanged={loadPartitions}
            />
          </MobileBottomSheet>
        )}

        {/* 移动端新建分区弹窗 */}
        <NewPartitionDialog
          open={showNewPartition}
          onClose={() => setShowNewPartition(false)}
          onCreate={handleCreatePartition}
        />
      </div>
    );
  }

  // ── Desktop layout: 桌面端合并侧栏布局 ──
  // 侧栏宽度固定为 260px，可折叠收起；主聊天区占据剩余空间
  const SIDEBAR_WIDTH = 260;

  return (
    <div className="fixed inset-0 bg-[var(--color-bg)] z-30 flex">
      {/* 桌面端左侧：集成导航链接和分区树的侧栏 */}
      <div
        className="flex-shrink-0 flex flex-col border-r border-[var(--color-border)] transition-all duration-200"
        style={{ width: sidebarCollapsed ? "0px" : `${SIDEBAR_WIDTH}px`, overflow: "hidden" }}
      >
        {!sidebarCollapsed && (
          <div className="flex flex-col h-full">
            {/* 桌面端侧栏迷你标题栏：返回驾驶舱链接 + 新建会话/分区/收起按钮 */}
            <div className="flex items-center justify-between px-3 py-2.5 border-b border-[var(--color-border)]">
              <a
                href="/dashboard"
                className="flex items-center gap-1.5 text-xs text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
              >
                <ChevronLeft size={14} />
                <span>驾驶舱</span>
              </a>
              <div className="flex items-center gap-1">
                {/* 新建会话按钮：有选中分区时在该分区下创建，否则创建默认分区会话 */}
                <button
                  onClick={() => {
                    if (selectedPartitionId) {
                      handleNewConversation("partition", selectedPartitionId);
                    } else {
                      // 未选中分区时创建默认会话
                      handleNewConversation("default", "");
                    }
                  }}
                  className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded"
                  title="新建会话"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                </button>
                {/* 新建分区按钮 */}
                <button
                  onClick={() => setShowNewPartition(true)}
                  className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-accent)] rounded"
                  title="新建分区"
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M12 5v14M5 12h14"/></svg>
                </button>
                {/* 收起侧栏按钮 */}
                <button
                  onClick={() => setSidebarCollapsed(true)}
                  className="p-1 text-[var(--color-text-muted)] hover:text-[var(--color-text)] rounded"
                  title="收起侧栏"
                >
                  <ChevronLeft size={14} />
                </button>
              </div>
            </div>

            {/* 桌面端侧栏分区树组件 */}
            <div className="flex-1 overflow-hidden">
              <Phase8Sidebar
                partitions={partitions}
                selectedPartitionId={selectedPartitionId}
                activeConversationId={activeConversationId}
                initialConversationId={activeConversationId ?? undefined}
                onSelectConversation={handleSelectConversation}
                onCreatePartition={() => setShowNewPartition(true)}
                onRenamePartition={handleRenamePartition}
                loading={loadingPartitions}
                compact
                onNewConversation={handleNewConversation}
                onTreeChanged={loadPartitions}
              />
            </div>
          </div>
        )}
      </div>

      {/* 桌面端侧栏折叠后显示的展开按钮 */}
      {sidebarCollapsed && (
        <button
          onClick={() => setSidebarCollapsed(false)}
          className="flex-shrink-0 w-6 border-r border-[var(--color-border)] flex items-center justify-center text-[var(--color-text-muted)] hover:text-[var(--color-text)] hover:bg-[var(--color-surface)] transition-colors"
          title="展开侧栏"
        >
          <ChevronRight size={14} />
        </button>
      )}

      {/* 桌面端右侧主聊天区 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 当前分区标题栏 */}
        {selectedPartitionId && activePartition && (
          <div className="flex-shrink-0 border-b border-[var(--color-border)] px-6 py-3 flex items-center gap-3">
            <Bot size={18} className="text-[var(--color-accent)]" />
            <div>
              <div className="text-sm font-semibold text-[var(--color-text)]">
                {activePartition.emoji} {activePartition.name}
              </div>
            </div>
          </div>
        )}

        {/* 桌面端上下文切换横幅 */}
        {switchBanner && (
          <SwitchBanner
            domainName={switchBanner.domainName}
            topicName={switchBanner.topicName}
            fullPath={switchBanner.fullPath}
            onSwitch={handleSwitchConfirm}
            onDismiss={handleSwitchDismiss}
          />
        )}

        {/* 桌面端对话错误提示 */}
        {convError && (
          <div className="flex-shrink-0 mx-6 mt-2 px-4 py-3 bg-red-500/10 border border-red-500/30 rounded-lg text-sm text-red-400">
            {convError}
          </div>
        )}
        {/* 桌面端消息列表 */}
        <MessageList
          messages={messages}
          responseBlocks={responseBlocks}
          isLoading={isLoading}
          statusMessage={statusMessage}
          onDeleteMessage={handleDeleteMessage}
          onEditMessage={handleEditMessage}
          onVersionSwitch={handleVersionSwitch}
        />

        {/* 桌面端聊天输入框 */}
        <ConversationChatInput
          onSend={handleSend}
          disabled={isLoading}
          conversationId={activeConversationId}
        />
      </div>

      {/* 桌面端新建分区弹窗 */}
      <NewPartitionDialog
        open={showNewPartition}
        onClose={() => setShowNewPartition(false)}
        onCreate={handleCreatePartition}
      />
    </div>
  );
}

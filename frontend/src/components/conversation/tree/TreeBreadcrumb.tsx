"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";

type BreadcrumbOption = {
  id: string;
  label: string;
  emoji?: string;
};

interface Props {
  partitionName: string;
  domainName?: string;
  topicName?: string;
  conversationName?: string;
  dirList?: BreadcrumbOption[];
  domains?: BreadcrumbOption[];
  topics?: BreadcrumbOption[];
  conversations?: BreadcrumbOption[];
  selectedDirId?: string | null;
  selectedDomainId?: string | null;
  selectedTopicId?: string | null;
  selectedConversationId?: string | null;
  onSelectPartition?: (id: string) => void;
  onSelectDomain?: (id: string) => void;
  onSelectTopic?: (id: string) => void;
  onSelectConversation?: (id: string) => void;
}

/**
 * TreeBreadcrumb — 当前路径可视化
 * 新架构：目录 > 会话（不再区分分区/领域/专题）
 * 旧 prop 名保留用于向后兼容
 */
export default function TreeBreadcrumb({
  partitionName,
  domainName,
  topicName,
  conversationName,
  dirList = [],
  domains = [],
  topics = [],
  conversations = [],
  selectedDirId,
  selectedDomainId,
  selectedTopicId,
  selectedConversationId,
  onSelectPartition,
  onSelectDomain,
  onSelectTopic,
  onSelectConversation,
}: Props) {
  const [openKey, setOpenKey] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onOutsideClick = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpenKey(null);
      }
    };
    window.addEventListener("mousedown", onOutsideClick);
    return () => window.removeEventListener("mousedown", onOutsideClick);
  }, []);

  // 合并 partition/domain/topic 为单一"目录"层级，显示非空且有值的那一级
  const items = useMemo(() => {
    const dirOptions = [
      ...dirList.map(p => ({ ...p, _order: 0 })),
      ...domains.map(d => ({ ...d, _order: 1 })),
      ...topics.map(t => ({ ...t, _order: 2 })),
    ].sort((a, b) => a._order - b._order);

    // 使用第一个非空的名称作为目录名
    const dirName = partitionName || domainName || topicName || "目录";

    return [
      {
        key: "dir",
        label: dirName,
        options: dirOptions,
        selectedId: selectedDirId || selectedDomainId || selectedTopicId,
        onSelect: onSelectPartition || onSelectDomain || onSelectTopic,
      },
      {
        key: "conversation",
        label: conversationName || "选择会话",
        options: conversations,
        selectedId: selectedConversationId,
        onSelect: onSelectConversation,
      },
    ];
  }, [
    partitionName, domainName, topicName, conversationName,
    dirList, domains, topics, conversations,
    selectedDirId, selectedDomainId, selectedTopicId, selectedConversationId,
    onSelectPartition, onSelectDomain, onSelectTopic, onSelectConversation,
  ]);

  const visibleItems = items.filter((item) => item.label);

  return (
    <div ref={rootRef} className="flex items-center gap-0.5 text-[11px] min-w-0 overflow-visible">
      {visibleItems.map((item, index) => {
        const isOpen = openKey === item.key;
        const hasOptions = item.options.length > 0;
        return (
          <React.Fragment key={item.key}>
            {index > 0 && <ChevronRight size={10} className="text-[var(--color-text-muted)] flex-shrink-0" />}
            <div className="relative flex-shrink-0">
              <button
                type="button"
                onClick={() => setOpenKey(isOpen ? null : item.key)}
                className={`flex items-center gap-1 rounded px-1 py-0.5 max-w-[96px] transition-colors ${
                  index === visibleItems.length - 1
                    ? "text-[var(--color-text)] font-medium hover:bg-[var(--color-surface)]"
                    : "text-[var(--color-text-muted)] hover:bg-[var(--color-surface)]"
                }`}
              >
                <span className="truncate">{item.label}</span>
                <ChevronDown size={10} className="flex-shrink-0 opacity-70" />
              </button>

              {isOpen && (
                <div className="absolute left-0 top-full mt-1 z-40 w-64 max-h-64 overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] shadow-xl">
                  <div className="max-h-64 overflow-y-auto py-1">
                    {hasOptions ? (
                      item.options.map((option) => {
                        const selected = option.id === item.selectedId;
                        return (
                          <button
                            key={option.id}
                            type="button"
                            onClick={() => {
                              item.onSelect?.(option.id);
                              setOpenKey(null);
                            }}
                            className={`flex w-full items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-[var(--color-surface)] ${
                              selected ? "bg-[var(--color-accent-soft)] text-[var(--color-accent)]" : "text-[var(--color-text)]"
                            }`}
                          >
                            <span className="flex-shrink-0 text-xs">{option.emoji || "•"}</span>
                            <span className="min-w-0 flex-1 truncate">{option.label}</span>
                          </button>
                        );
                      })
                    ) : (
                      <div className="px-3 py-2 text-xs text-[var(--color-text-muted)]">
                        暂无可选项
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}

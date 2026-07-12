"use client";

import { useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useConversation } from "@/hooks/conversation/useConversation";
import { usePanelContent } from "@/contexts/PanelContentContext";
import ConversationPanel from "@/components/conversation/core/ConversationPanel";
import RightInfoPanel from "@/components/conversation/panels/RightInfoPanel";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";

export default function ConversationPage() {
  const conv = useConversation();
  const { setRightPanel, setBreadcrumbs } = usePanelContent();
  const router = useRouter();

  const {
    selectedNode, activeDir, messages, activeConversationId,
    handleRenameDirectory, handleNewConversation, dirList,
  } = conv;

  // ── 面包屑：从 selectedNode.path + dirList 构建 ──
  const breadcrumbs = useMemo(() => {
    const crumbs: Array<{ label: string; href?: string }> = [];
    // 首页 → /（任务 #120：秘书仪表盘替代驾驶舱）
    crumbs.push({ label: "首页", href: "/" });
    // 学习空间 → /conversation
    crumbs.push({ label: "学习空间", href: "/conversation" });

    // selectedNode.path 是祖先 ID 数组，解析名字
    if (selectedNode?.path && dirList.length > 0) {
      for (const pid of selectedNode.path) {
        const p = dirList.find((d) => d.id === pid);
        if (p) crumbs.push({ label: p.name || pid.slice(-8) });
      }
    }
    // 当前目录/会话名
    if (activeDir) {
      crumbs.push({ label: activeDir.name || activeDir.id.slice(-8) });
    }
    return crumbs;
  }, [selectedNode?.path, dirList, activeDir]);

  // ── 注入右栏 + 面包屑到全局 Workbench ──
  useEffect(() => {
    setRightPanel(
      <RightInfoPanel
        selectedNode={selectedNode}
        activeDir={activeDir}
        activeConversationId={activeConversationId}
        messages={messages}
        onRenameDir={(id, name) => handleRenameDirectory(id, name)}
        onCreateSubdir={() => conv.setShowNewDir(true)}
        onCreateConv={() => {
          const dirId = selectedNode?.level === "dir" ? selectedNode.id : null;
          handleNewConversation("conv", dirId || "", dirId || "");
        }}
        onOpenKnowledgeTree={(nodeId) => router.push(`/knowledge-tree?node=${nodeId}`)}
      />,
    );
    setBreadcrumbs(breadcrumbs);
    return () => {
      setRightPanel(null);
      setBreadcrumbs([]);
    };
  }, [selectedNode, activeDir, messages, breadcrumbs, handleRenameDirectory, handleNewConversation, router, setRightPanel, setBreadcrumbs, activeConversationId, conv.setShowNewDir]);

  return (
    <ErrorBoundary>
      <ConversationPanel {...conv} />
    </ErrorBoundary>
  );
}

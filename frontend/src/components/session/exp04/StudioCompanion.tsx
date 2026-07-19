"use client";

import { useMemo } from "react";

// ============================================================
// StudioCompanion — Workspace Intelligence 面板
//
// Vision 来源：vision/index.html §intelligence (lines 1221–1302)
// 6 区垂直堆叠：
//   1. Header（头像 + 名字 + 实时状态）
//   2. 正在观察（用户行为 ✓ activity）
//   3. 正在连接知识（跨工作区 + 本工作区 accent_soft 卡片）
//   4. 正在生成（spinner / ✓ activity）
//   5. 对你的理解（学习风格 · 专注 · 会话数）
//   6. Smart Actions（底部 sticky：主操作 + 次操作）
//
// 注意：移除了原来的 input box。Demo 中对话输入在 canvas 中央
// （cd-input），Companion 不再有重复输入入口。
// ============================================================

interface Props {
  stage: string;
  mode: string;
  toolState: { practiceDone?: boolean; cardCreated?: boolean };
  messageCount: number;
  resourceKey?: string;
  sessionTitle?: string | null;
  onOpenCanvas?: () => void;
  onOpenFlashcard?: () => void;
  onOpenPractice?: () => void;
}

// ── 资源上下文映射 ──

const RESOURCE_NAMES: Record<string, string> = {
  book: "计算机网络",
  video: "TCP 视频",
  note: "你的笔记",
  mindmap: "三次握手导图",
  web: "RFC 793",
};

const RESOURCE_ICONS: Record<string, string> = {
  book: "📖",
  video: "🎬",
  note: "📝",
  mindmap: "🧩",
  web: "🌐",
};

// ── 类型 ──

interface ActivityItem {
  text: string; // 支持 HTML（<strong>）
  state?: "check" | "spin";
}

interface InsightItem {
  label: string;
  content: string; // 支持 HTML
}

// ── 实时状态文案（stage + mode + messageCount） ──

function getStatusText(stage: string, mode: string, messageCount: number): string {
  if (stage === "enter") return "正在工作";
  if (stage === "finish") return "陪伴中";
  if (stage === "reflect") return "分析中";
  if (mode === "stuck") return "关注中";
  if (mode === "breakthrough") return "陪伴中";
  if (mode === "deep_chat") return "分析中";
  if (messageCount >= 3) return "分析中";
  if (messageCount > 0) return "观察中";
  return "正在工作";
}

// ── Builder：正在观察 ──

function buildObserving(props: Props): ActivityItem[] {
  const { stage, mode, toolState, messageCount, resourceKey } = props;
  const items: ActivityItem[] = [];

  if (stage === "enter") {
    const resName = resourceKey ? RESOURCE_NAMES[resourceKey] : null;
    const resIcon = resourceKey ? RESOURCE_ICONS[resourceKey] : null;
    items.push({
      text: resName && resIcon
        ? `你打开了 <strong>${resIcon} ${resName}</strong>，准备开始`
        : "你回到了学习空间，准备开始今天的 Mission",
      state: "check",
    });
    return items;
  }

  if (stage === "finish") {
    items.push({ text: "你完成了今天的学习", state: "check" });
    items.push({ text: "你对这个主题的理解又深了一层", state: "check" });
    return items;
  }

  if (stage === "reflect") {
    items.push({ text: "你正在写下自己的理解", state: "check" });
    return items;
  }

  // chat 阶段
  if (mode === "stuck") {
    items.push({ text: "你在这个点停留了一会儿，<strong>可能遇到卡点</strong>", state: "check" });
    items.push({ text: "你习惯先看例子再理解定义", state: "check" });
    return items;
  }

  if (mode === "breakthrough") {
    items.push({ text: "你刚才的回答抓住了<strong>核心</strong>", state: "check" });
    return items;
  }

  if (mode === "silent") {
    items.push({ text: "你在安静地消化刚才的内容", state: "check" });
    return items;
  }

  // normal / deep_chat
  if (messageCount === 0) {
    const resName = resourceKey ? RESOURCE_NAMES[resourceKey] : null;
    items.push({
      text: resName
        ? `你在看 <strong>${RESOURCE_ICONS[resourceKey!] || ""} ${resName}</strong>`
        : "你刚刚开始今天的对话",
      state: "check",
    });
  } else if (messageCount <= 2) {
    items.push({ text: "你已经在主动追问，<strong>思考方向很清晰</strong>", state: "check" });
    items.push({ text: "你习惯先理解原理再做题", state: "check" });
  } else {
    items.push({ text: "你在<strong>深入讨论</strong>，连续专注中", state: "check" });
    items.push({ text: "下午是你的高效时段", state: "check" });
  }

  return items;
}

// ── Builder：正在连接知识 ──

function buildConnecting(props: Props): InsightItem[] {
  const { stage, resourceKey, sessionTitle } = props;
  if (stage === "finish" || stage === "enter") return [];

  const topic = sessionTitle || (resourceKey ? RESOURCE_NAMES[resourceKey] : "当前主题");

  return [
    {
      label: "跨工作区关联",
      content: `${topic} ← 你之前学过的相关知识<br><span style="font-size:10px;color:var(--color-ink-muted);display:block;margin-top:3px">苹果果在帮你把新旧知识连起来</span>`,
    },
    {
      label: "本工作区关联",
      content: `和「${topic}」相关的概念正在浮现`,
    },
  ];
}

// ── Builder：正在生成 ──

function buildGenerating(props: Props): ActivityItem[] {
  const { stage, toolState, messageCount } = props;
  const items: ActivityItem[] = [];

  if (stage === "finish") {
    items.push({ text: "更新 <strong>成长记录</strong>——添加今日学习洞察", state: "check" });
    return items;
  }

  if (stage === "enter") return [];

  if (toolState.practiceDone) {
    items.push({ text: "已根据你的回答调整了练习难度", state: "check" });
  } else if (messageCount >= 2) {
    items.push({ text: "基于你的理解进度<strong>生成练习题</strong>", state: "spin" });
  }

  if (toolState.cardCreated) {
    items.push({ text: "已为你<strong>归档闪卡</strong>，下次复习会出现", state: "check" });
  } else if (messageCount > 1) {
    items.push({ text: "识别到值得记下的点", state: "spin" });
  }

  if (messageCount > 0) {
    items.push({ text: "更新 <strong>成长记录</strong>——记录今日学习", state: "check" });
  }

  return items;
}

// ── Builder：对你的理解（Memory Snapshot） ──

function buildUnderstanding(props: Props): ActivityItem[] {
  const { stage, messageCount } = props;

  if (stage === "enter") {
    return [
      { text: "<strong>学习风格：</strong>喜欢先理解原理再做题" },
      { text: "你最近常在下午学习" },
    ];
  }

  return [
    { text: "<strong>学习风格：</strong>喜欢先理解原理再做题" },
    { text: `本周完成 <strong>${stage === "finish" ? 1 : 0} 个会话</strong>，理解在累积` },
    { text: messageCount > 0 ? "你今天主动思考的频率很高" : "你今天还没开始对话" },
  ];
}

// ── Smart Actions ──

function buildActions(props: Props): { primary?: { label: string; key: string }; secondary?: { label: string; key: string } } {
  const { stage, toolState, messageCount } = props;

  if (stage === "finish") {
    return {
      primary: { label: "回到学习空间", key: "home" },
    };
  }

  if (stage === "enter") {
    return {
      primary: { label: "从这里开始", key: "start" },
    };
  }

  if (stage === "reflect") {
    return {
      primary: { label: "继续写反思", key: "reflect" },
    };
  }

  // chat
  if (!toolState.practiceDone && messageCount > 0) {
    return {
      primary: { label: "做几道巩固练习", key: "practice" },
      secondary: toolState.cardCreated ? undefined : { label: "记下这个点", key: "flashcard" },
    };
  }

  if (!toolState.cardCreated && messageCount > 1) {
    return {
      primary: { label: "记下这个点", key: "flashcard" },
      secondary: { label: "打开画布", key: "canvas" },
    };
  }

  if (messageCount > 0) {
    return {
      primary: { label: "打开画布", key: "canvas" },
    };
  }

  return {};
}

// ── 主组件 ──

export default function StudioCompanion(props: Props) {
  const status = getStatusText(props.stage, props.mode, props.messageCount);

  const observing = useMemo(() => buildObserving(props), [
    props.stage, props.mode, props.messageCount, props.resourceKey,
  ]);
  const connecting = useMemo(() => buildConnecting(props), [
    props.stage, props.resourceKey, props.sessionTitle,
  ]);
  const generating = useMemo(() => buildGenerating(props), [
    props.stage, props.toolState.practiceDone, props.toolState.cardCreated, props.messageCount,
  ]);
  const understanding = useMemo(() => buildUnderstanding(props), [
    props.stage, props.messageCount,
  ]);
  const actions = useMemo(() => buildActions(props), [
    props.stage, props.toolState.practiceDone, props.toolState.cardCreated, props.messageCount,
  ]);

  const handleAction = (key: string) => {
    if (key === "canvas") props.onOpenCanvas?.();
    else if (key === "flashcard") props.onOpenFlashcard?.();
    else if (key === "practice") props.onOpenPractice?.();
    // home / start / reflect / canvas-explain：仅状态提示，不直接打开工具
  };

  return (
    <div className="wi-root">
      {/* ── Header ── */}
      <div className="wi-header">
        <div className="wi-avatar">果</div>
        <div className="wi-header-info">
          <div className="wi-name">苹果果</div>
          <div className="wi-status">
            <span className="wi-dot"></span>{status}
          </div>
        </div>
      </div>

      {/* ── Body（可滚动） ── */}
      <div className="wi-body">
        {/* 正在观察 */}
        {observing.length > 0 && (
          <div className="wi-section">
            <div className="wi-section-label">正在观察</div>
            <div className="wi-activity">
              {observing.map((item, i) => (
                <div className="wi-activity-item" key={`o-${i}`}>
                  <span className={`wi-ai-${item.state || "check"}`}>
                    {item.state === "spin" ? "" : "✓"}
                  </span>
                  <span dangerouslySetInnerHTML={{ __html: item.text }} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 正在连接知识 */}
        {connecting.length > 0 && (
          <div className="wi-section">
            <div className="wi-section-label">正在连接知识</div>
            {connecting.map((item, i) => (
              <div className="wi-insight" key={`c-${i}`}>
                <span className="wi-insight-label">{item.label}</span>
                <span dangerouslySetInnerHTML={{ __html: item.content }} />
              </div>
            ))}
          </div>
        )}

        {/* 正在生成 */}
        {generating.length > 0 && (
          <div className="wi-section">
            <div className="wi-section-label">正在生成</div>
            <div className="wi-activity">
              {generating.map((item, i) => (
                <div className="wi-activity-item" key={`g-${i}`}>
                  <span className={`wi-ai-${item.state || "check"}`}>
                    {item.state === "spin" ? "" : "✓"}
                  </span>
                  <span dangerouslySetInnerHTML={{ __html: item.text }} />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 对你的理解 */}
        {understanding.length > 0 && (
          <div className="wi-section">
            <div className="wi-section-label">对你的理解</div>
            <div className="wi-activity">
              {understanding.map((item, i) => (
                <div className="wi-activity-item" key={`u-${i}`}>
                  <span className="wi-ai-bullet">·</span>
                  <span dangerouslySetInnerHTML={{ __html: item.text }} />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Smart Actions（sticky bottom） ── */}
      {(actions.primary || actions.secondary) && (
        <div className="wi-actions">
          {actions.primary && (
            <button
              className={`wi-action-btn ${actions.secondary ? "primary" : "solo"}`}
              onClick={() => handleAction(actions.primary!.key)}
            >
              {actions.primary.label}
            </button>
          )}
          {actions.secondary && (
            <button
              className="wi-action-btn muted"
              onClick={() => handleAction(actions.secondary!.key)}
            >
              {actions.secondary.label}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

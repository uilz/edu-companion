"use client";

import { useState, useMemo, useRef, useEffect } from "react";

interface Props {
  stage: string;
  mode: string;
  toolState: { practiceDone?: boolean; cardCreated?: boolean; };
  messageCount: number;
  sessionTitle?: string | null;
  onOpenCanvas?: () => void;
  onOpenFlashcard?: () => void;
  onOpenPractice?: () => void;
}

// ── 观察引擎：根据真实状态生成文案 ──

function buildObservations(props: Props) {
  const { stage, mode, toolState, messageCount, sessionTitle } = props;
  const list: Array<{
    id: number;
    time: string;
    text: string;
    type: "observation" | "suggestion";
    actions?: Array<{ label: string; key: string; primary?: boolean }>;
  }> = [];
  let id = 0;

  if (stage === "enter") {
    list.push({
      id: id++,
      time: "刚刚",
      text: `准备好了吗？今天的 Mission 是：<strong>${sessionTitle || "探索新知识"}</strong>`,
      type: "observation",
    });
    list.push({
      id: id++,
      time: "",
      text: "我知道你已经有一些基础。<br>我们一起深入。",
      type: "observation",
    });
  }

  if (stage === "chat") {
    // 模式感知
    if (mode === "stuck") {
      list.push({
        id: id++,
        time: "刚刚",
        text: "你好像卡住了。要不要换个角度想想？<br><span style=\"font-size:12px;color:var(--color-ink-muted)\">已经在这个点停留了一段时间</span>",
        type: "suggestion",
        actions: [{ label: "换个角度", key: "explain", primary: true }],
      });
    } else if (mode === "breakthrough") {
      list.push({
        id: id++,
        time: "刚刚",
        text: "感觉你有了新的理解！<br><strong>趁热来一道题？</strong>",
        type: "observation",
      });
      if (!toolState.practiceDone) {
        list.push({
          id: id++,
          time: "现在",
          text: "检验一下理解，也帮我确认我的引导方向对不对。",
          type: "suggestion",
          actions: [{ label: "来一道", key: "practice", primary: true }],
        });
      }
    } else if (mode === "silent") {
      list.push({
        id: id++,
        time: "刚刚",
        text: "不用着急。有些概念需要时间沉淀。<br>我可以给你讲一段。",
        type: "observation",
      });
    } else {
      // normal / deep_chat
      if (messageCount === 0) {
        list.push({
          id: id++,
          time: "刚刚",
          text: `我们刚刚开始。<br>你对 <strong>${sessionTitle || "这个话题"}</strong> 已经了解多少了？`,
          type: "observation",
        });
      } else if (messageCount <= 2) {
        list.push({
          id: id++,
          time: "刚刚",
          text: "你已经开始深入了。感觉到你的思考方向。",
          type: "observation",
        });
      } else {
        list.push({
          id: id++,
          time: "刚刚",
          text: "你已经在深入讨论了。需要我帮你理一下思路？",
          type: "observation",
        });
      }

      // 建议：练习 / 闪卡 / 画布
      if (!toolState.practiceDone && messageCount > 0) {
        list.push({
          id: id++,
          time: "建议",
          text: "检验一下理解？让我看看你有没有跟上。",
          type: "suggestion",
          actions: [{ label: "来一道题", key: "practice", primary: true }],
        });
      }
      if (!toolState.cardCreated && messageCount > 1) {
        list.push({
          id: id++,
          time: "建议",
          text: "这个点值得记下来，以后复习会用到。",
          type: "suggestion",
          actions: [{ label: "记闪卡", key: "flashcard" }],
        });
      }
      if (messageCount > 0) {
        list.push({
          id: id++,
          time: "也可以",
          text: "把思考过程画出来，会更直观。",
          type: "suggestion",
          actions: [{ label: "打开画布", key: "canvas" }],
        });
      }
    }
  }

  if (stage === "reflect") {
    list.push({
      id: id++,
      time: "刚刚",
      text: "全部学完了。把今天的理解写下来吧？<br><span style=\"font-size:12px;color:var(--color-ink-muted)\">没有对错，苹果果只是想知道你记住了什么。</span>",
      type: "observation",
    });
  }

  if (stage === "finish") {
    list.push({
      id: id++,
      time: "刚刚",
      text: "今天学完了。<br><strong>你的理解又深了一层。</strong><br><span style=\"font-size:12px;color:var(--color-ink-muted)\">明天见，橙子。我会记住今天的。</span>",
      type: "observation",
    });
  }

  return list;
}

export default function StudioCompanion(props: Props) {
  const [inputValue, setInputValue] = useState("");
  const [userMessages, setUserMessages] = useState<string[]>([]);
  const bodyRef = useRef<HTMLDivElement>(null);

  // 每次 props 变化重新生成观察
  const cards = useMemo(() => buildObservations(props), [
    props.stage, props.mode, props.toolState.practiceDone,
    props.toolState.cardCreated, props.messageCount, props.sessionTitle,
  ]);

  // 滚动到底部
  useEffect(() => {
    if (bodyRef.current) {
      bodyRef.current.scrollTop = bodyRef.current.scrollHeight;
    }
  }, [cards, userMessages]);

  const handleAction = (key: string) => {
    if (key === "canvas") props.onOpenCanvas?.();
    else if (key === "flashcard") props.onOpenFlashcard?.();
    else if (key === "practice") props.onOpenPractice?.();
    else if (key === "explain") props.onOpenCanvas?.(); // 换个角度 → 画
  };

  const handleSend = () => {
    const text = inputValue.trim();
    if (!text) return;
    setUserMessages((prev) => [...prev, text]);
    setInputValue("");
  };

  return (
    <div className="sc-root">
      {/* Header */}
      <div className="sc-header">
        <div className="sc-avatar">🍎</div>
        <div className="sc-header-info">
          <div className="sc-name">AppleGo</div>
          <div className="sc-status">● {props.stage === "finish" ? "学完了" : "观察中"}</div>
        </div>
      </div>

      {/* Body */}
      <div className="sc-body" ref={bodyRef}>
        {cards.map((card) => (
          <div
            key={card.id}
            className={`sc-card ${card.type === "observation" ? "sc-observation" : "sc-suggestion"}`}
          >
            {card.time && <div className="sc-time">{card.time}</div>}
            <div
              className="sc-text"
              dangerouslySetInnerHTML={{ __html: card.text }}
            />
            {card.actions && card.actions.length > 0 && (
              <div className="sc-actions">
                {card.actions.map((a) => (
                  <button
                    key={a.key}
                    className={`sc-action-btn ${a.primary ? "primary" : ""}`}
                    onClick={() => handleAction(a.key)}
                  >
                    {a.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {/* 用户通过 Companion 发送的消息 */}
        {userMessages.map((msg, i) => (
          <div key={`u-${i}`} className="sc-card sc-observation" style={{ background: "var(--color-user-msg, #e8e3de)" }}>
            <div className="sc-time">你 · 刚刚</div>
            <div className="sc-text">{msg}</div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="sc-input-area">
        <input
          className="sc-input"
          placeholder="跟 AppleGo 说说……"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
        />
        <button className="sc-send-btn" onClick={handleSend}>
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none">
            <path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>
    </div>
  );
}

"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { Menu, Sparkles } from "lucide-react";
import { Message, Conversation } from "@/types";
import {
  generateId,
  getSettings,
  connectWebSocket,
  sendMessage,
  disconnectWebSocket,
  sendViaFetch,
} from "@/lib/api";
import ChatMessage from "@/components/ChatMessage";
import ChatInput from "@/components/ChatInput";
import Sidebar from "@/components/Sidebar";
import SettingsPanel from "@/components/SettingsPanel";

function TypingIndicator() {
  return (
    <div className="flex gap-3 px-4 py-5">
      <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[var(--color-bg-tertiary)] flex items-center justify-center">
        <Sparkles size={18} className="text-[var(--color-accent)]" />
      </div>
      <div className="rounded-2xl rounded-bl-md px-4 py-3 bg-[var(--color-assistant-bubble)]">
        <div className="flex items-center gap-1.5">
          <span className="typing-dot w-2 h-2 rounded-full bg-[var(--color-text-muted)]" />
          <span className="typing-dot w-2 h-2 rounded-full bg-[var(--color-text-muted)]" />
          <span className="typing-dot w-2 h-2 rounded-full bg-[var(--color-text-muted)]" />
        </div>
      </div>
    </div>
  );
}

function WelcomeScreen() {
  const tips = [
    { icon: "📐", text: "帮我解释微积分中的极限概念" },
    { icon: "🧪", text: "解释一下化学中的氧化还原反应" },
    { icon: "📊", text: "分析一下数据中的回归分析方法" },
    { icon: "🧠", text: "什么是机器学习中的反向传播算法？" },
  ];

  return (
    <div className="flex-1 flex flex-col items-center justify-center px-4 py-12">
      <div className="text-5xl mb-4">📚</div>
      <h2 className="text-xl font-semibold text-[var(--color-text-primary)] mb-2">
        你好，我是你的学习助手
      </h2>
      <p className="text-sm text-[var(--color-text-secondary)] text-center max-w-md mb-8">
        我可以帮你解答学术问题、解释复杂概念、编写代码和生成数学公式。试试下面的问题吧！
      </p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-lg w-full">
        {tips.map((tip, i) => (
          <div
            key={i}
            className="flex items-start gap-2.5 px-4 py-3 rounded-xl bg-[var(--color-bg-secondary)] border border-[var(--color-border-default)] text-sm text-[var(--color-text-secondary)] hover:border-[var(--color-accent)] hover:text-[var(--color-text-primary)] cursor-default transition-colors"
          >
            <span className="text-lg">{tip.icon}</span>
            <span>{tip.text}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Home() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [initialized, setInitialized] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentAssistantId = useRef<string | null>(null);

  // Load from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("edu-companion-conversations");
    if (saved) {
      try {
        setConversations(JSON.parse(saved));
      } catch { /* ignore */ }
    }
    setInitialized(true);
  }, []);

  // Save to localStorage
  useEffect(() => {
    if (initialized) {
      localStorage.setItem(
        "edu-companion-conversations",
        JSON.stringify(conversations)
      );
    }
  }, [conversations, initialized]);

  const activeConversation = conversations.find((c) => c.id === activeId);

  const scrollToBottom = useCallback(() => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 50);
  }, []);

  const newConversation = useCallback(() => {
    const conv: Conversation = {
      id: generateId(),
      title: "新对话",
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    setConversations((prev) => [conv, ...prev]);
    setActiveId(conv.id);
  }, []);

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeId === id) {
        setActiveId(null);
      }
    },
    [activeId]
  );

  const handleSend = useCallback(
    (content: string) => {
      let convId = activeId;

      // Auto-create conversation if none active
      if (!convId) {
        const conv: Conversation = {
          id: generateId(),
          title: content.slice(0, 30),
          messages: [],
          createdAt: Date.now(),
          updatedAt: Date.now(),
        };
        setConversations((prev) => [conv, ...prev]);
        convId = conv.id;
        setActiveId(convId);
      }

      const userMsg: Message = {
        id: generateId(),
        role: "user",
        content,
        timestamp: Date.now(),
      };

      // Add user message
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== convId) return c;
          const title =
            c.messages.length === 0
              ? content.slice(0, 30)
              : c.title;
          return {
            ...c,
            title,
            messages: [...c.messages, userMsg],
            updatedAt: Date.now(),
          };
        })
      );

      // Add empty assistant message
      const assistantMsg: Message = {
        id: generateId(),
        role: "assistant",
        content: "",
        timestamp: Date.now(),
      };
      currentAssistantId.current = assistantMsg.id;

      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== convId) return c;
          return {
            ...c,
            messages: [...c.messages, assistantMsg],
            updatedAt: Date.now(),
          };
        })
      );

      setIsLoading(true);
      scrollToBottom();

      const settings = getSettings();

      // Try WebSocket first, fallback to fetch
      let usedWs = false;
      try {
        connectWebSocket(
          (token) => {
            usedWs = true;
            setConversations((prev) =>
              prev.map((c) => {
                if (c.id !== convId) return c;
                return {
                  ...c,
                  messages: c.messages.map((m) =>
                    m.id === assistantMsg.id
                      ? { ...m, content: m.content + token }
                      : m
                  ),
                };
              })
            );
            scrollToBottom();
          },
          () => {
            setIsLoading(false);
            scrollToBottom();
          },
          (error) => {
            if (!usedWs) {
              // Fallback to fetch
              fallbackFetch(convId!, assistantMsg.id, content, settings);
            } else {
              setIsLoading(false);
            }
          }
        );

        // Send the message
        setTimeout(() => {
          if (convId) sendMessage(convId, content, settings);
        }, 100);
      } catch {
        fallbackFetch(convId!, assistantMsg.id, content, settings);
      }
    },
    [activeId, scrollToBottom]
  );

  function fallbackFetch(
    convId: string,
    assistantMsgId: string,
    content: string,
    settings: { apiEndpoint: string; apiKey: string; modelName: string; systemPrompt: string }
  ) {
    sendViaFetch(
      convId,
      content,
      settings,
      (token) => {
        setConversations((prev) =>
          prev.map((c) => {
            if (c.id !== convId) return c;
            return {
              ...c,
              messages: c.messages.map((m) =>
                m.id === assistantMsgId
                  ? { ...m, content: m.content + token }
                  : m
              ),
            };
          })
        );
        scrollToBottom();
      },
      () => {
        setIsLoading(false);
        scrollToBottom();
      },
      () => {
        setIsLoading(false);
      }
    );
  }

  if (!initialized) return null;

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        conversations={conversations}
        activeId={activeId}
        onSelect={setActiveId}
        onNew={newConversation}
        onDelete={deleteConversation}
        onSettings={() => setSettingsOpen(true)}
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* Main content */}
      <main className="flex-1 flex flex-col h-screen min-w-0">
        {/* Top bar */}
        <header className="flex items-center gap-3 px-4 py-3 border-b border-[var(--color-border-default)] bg-[var(--color-bg-primary)]">
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden p-2 rounded-lg text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-hover)]"
            aria-label="打开菜单"
          >
            <Menu size={20} />
          </button>
          <h1 className="text-sm font-medium text-[var(--color-text-primary)] truncate">
            {activeConversation?.title || "智能学习助手"}
          </h1>
        </header>

        {/* Messages area */}
        {activeConversation && activeConversation.messages.length > 0 ? (
          <div className="flex-1 overflow-y-auto">
            {activeConversation.messages.map((msg) => (
              <ChatMessage key={msg.id} message={msg} />
            ))}
            {isLoading && <TypingIndicator />}
            <div ref={messagesEndRef} />
          </div>
        ) : (
          <WelcomeScreen />
        )}

        {/* Input */}
        <ChatInput onSend={handleSend} disabled={isLoading} />
      </main>

      <SettingsPanel
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />
    </div>
  );
}

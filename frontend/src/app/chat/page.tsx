"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { Bot, Sparkles, Settings } from "lucide-react";
import { Message } from "@/types";
import {
  connectWebSocket,
  sendMessage,
  sendViaFetch,
  disconnectWebSocket,
  getSettings,
  generateId,
} from "@/lib/api";
import ChatMessage from "@/components/chat/ChatMessage";
import ChatInput from "@/components/chat/ChatInput";

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId] = useState(() => generateId());
  const [showSettings, setShowSettings] = useState(false);
  const [settings, setSettings] = useState(() => getSettings());
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsConnectedRef = useRef(false);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Save settings when changed
  useEffect(() => {
    if (typeof window !== "undefined") {
      localStorage.setItem("edu-companion-settings", JSON.stringify(settings));
    }
  }, [settings]);

  const handleSend = useCallback(
    (text: string) => {
      if (!text.trim() || isLoading) return;

      const userMsg: Message = {
        id: generateId(),
        role: "user",
        content: text,
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      // Create placeholder for assistant response
      const assistantId = generateId();
      const assistantMsg: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      let contentBuffer = "";

      const onToken = (token: string) => {
        contentBuffer += token;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: contentBuffer } : m
          )
        );
      };

      const onDone = () => {
        setIsLoading(false);
      };

      const onError = (error: string) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: contentBuffer || `⚠️ ${error}` }
              : m
          )
        );
        setIsLoading(false);
      };

      // Try WebSocket first, fallback to fetch
      if (!wsConnectedRef.current) {
        connectWebSocket(onToken, onDone, onError);
        wsConnectedRef.current = true;
      }

      sendMessage(conversationId, text, settings);
    },
    [conversationId, settings, isLoading]
  );

  // Cleanup
  useEffect(() => {
    return () => {
      disconnectWebSocket();
    };
  }, []);

  const isEmpty = messages.length === 0;

  return (
    <main className="flex flex-col h-screen bg-[var(--color-bg)]">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-[var(--color-border)] px-6 py-4">
        <div className="max-w-3xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Bot size={20} className="text-[var(--color-accent)]" />
            <h1 className="text-lg font-semibold text-[var(--color-text)]">对话</h1>
          </div>
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors p-1"
          >
            <Settings size={16} />
          </button>
        </div>
      </div>

      {/* Settings panel */}
      {showSettings && (
        <div className="flex-shrink-0 border-b border-[var(--color-border)] px-6 py-4 bg-[var(--color-card)]">
          <div className="max-w-3xl mx-auto space-y-3">
            <div>
              <label className="text-xs text-[var(--color-text-muted)] block mb-1">API 端点</label>
              <input
                value={settings.apiEndpoint}
                onChange={(e) =>
                  setSettings((s) => ({ ...s, apiEndpoint: e.target.value }))
                }
                className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)]"
                placeholder="留空使用默认"
              />
            </div>
            <div>
              <label className="text-xs text-[var(--color-text-muted)] block mb-1">API Key</label>
              <input
                type="password"
                value={settings.apiKey}
                onChange={(e) =>
                  setSettings((s) => ({ ...s, apiKey: e.target.value }))
                }
                className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)]"
                placeholder="sk-..."
              />
            </div>
            <div>
              <label className="text-xs text-[var(--color-text-muted)] block mb-1">模型名称</label>
              <input
                value={settings.modelName}
                onChange={(e) =>
                  setSettings((s) => ({ ...s, modelName: e.target.value }))
                }
                className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)]"
                placeholder="gpt-4o"
              />
            </div>
            <div>
              <label className="text-xs text-[var(--color-text-muted)] block mb-1">系统提示词</label>
              <textarea
                value={settings.systemPrompt}
                onChange={(e) =>
                  setSettings((s) => ({ ...s, systemPrompt: e.target.value }))
                }
                rows={3}
                className="w-full bg-[var(--color-input)] border border-[var(--color-border)] text-[var(--color-text)] text-sm px-3 py-2 focus:outline-none focus:border-[var(--color-border-hover)] resize-none"
              />
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        {isEmpty ? (
          <div className="h-full flex flex-col items-center justify-center text-center px-6">
            <div className="w-12 h-12 border border-[var(--color-border)] flex items-center justify-center mb-4">
              <Sparkles size={20} className="text-[var(--color-accent)]" />
            </div>
            <h2 className="text-xl font-bold text-[var(--color-text)] mb-2">开始提问</h2>
            <p className="text-sm text-[var(--color-text-muted)] max-w-md">
              我是你的 AI 学习助手，可以帮你解答学科问题、解释概念、批改作业。
              <br />
              试着问我任何学习上的问题。
            </p>
            <div className="flex gap-2 mt-6">
              {["什么是极限？", "解释矩阵乘法", "牛顿第二定律"].map((q) => (
                <button
                  key={q}
                  onClick={() => handleSend(q)}
                  className="text-xs px-4 py-2 border border-[var(--color-border)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-hover)] hover:text-[var(--color-text)] transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="max-w-3xl mx-auto px-6 py-6">
            {messages.map((msg) => (
              <ChatMessage
                key={msg.id}
                role={msg.role}
                content={msg.content}
                timestamp={msg.timestamp}
              />
            ))}

            {/* Typing indicator */}
            {isLoading && messages[messages.length - 1]?.content === "" && (
              <div className="flex justify-start mb-3">
                <div className="bg-[var(--color-surface)] px-4 py-3 flex gap-1.5">
                  <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-text-muted)] typing-dot" />
                  <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-text-muted)] typing-dot" />
                  <div className="w-1.5 h-1.5 rounded-full bg-[var(--color-text-muted)] typing-dot" />
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input */}
      <div className="flex-shrink-0">
        <ChatInput onSend={handleSend} disabled={isLoading} />
      </div>
    </main>
  );
}

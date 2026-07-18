"use client";

import { useState } from "react";

interface Props {
  sessionTitle?: string | null;
}

export default function StudioCompanion({ sessionTitle }: Props) {
  const [inputValue, setInputValue] = useState("");

  const handleSend = () => {
    const text = inputValue.trim();
    if (!text) return;
    setInputValue("");
  };

  return (
    <div className="sc-root">
      {/* Header */}
      <div className="sc-header">
        <div className="sc-avatar">🍎</div>
        <div className="sc-header-info">
          <div className="sc-name">AppleGo</div>
          <div className="sc-status">● 观察中</div>
        </div>
      </div>

      {/* Body */}
      <div className="sc-body">
        {/* Observation */}
        <div className="sc-card sc-observation">
          <div className="sc-time">刚刚</div>
          <div className="sc-text">
            欢迎回来。<br />
            上次你停在<strong>「为什么不是两次」</strong>这个问题上。
          </div>
        </div>

        {/* Observation 2 */}
        <div className="sc-card sc-observation">
          <div className="sc-time">2 分钟前</div>
          <div className="sc-text">
            我注意到你第三次读这段关于三次握手的文字。<br />
            而且停在<strong>「ACK 为什么存在」</strong>这里。
          </div>
        </div>

        {/* Suggestion */}
        <div className="sc-card sc-suggestion">
          <div className="sc-time">1 分钟前</div>
          <div className="sc-text">
            <strong>要不要一起画一张图？</strong><br />
            把三次握手的时序画出来，可能比文字更直观。
          </div>
          <div className="sc-actions">
            <button className="sc-action-btn primary">打开画布</button>
            <button className="sc-action-btn">先解释一下</button>
          </div>
        </div>
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

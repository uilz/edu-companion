# 多模态设计

> TTS 语音合成 + 语音识别输入。

---

## TTS（文本转语音）

| 功能 | 状态 |
|------|------|
| 消息朗读 | ✅ 已实现 |
| 朗读进度指示 | ✅ 已实现 |
| 语音合成 | ✅ 已实现 |

### 使用场景

- 对话消息的 `SpeakButton` 组件
- 学习内容朗读辅助
- 错题解析朗读

## 语音识别

| 功能 | 状态 |
|------|------|
| 语音录制 | ✅ 已实现 |
| 语音转文字 | ✅ 已实现 |
| 发送到对话 | ✅ 已实现 |

### 组件

- `VoiceRecorder` — 录音按钮 + 可视化波形
- 集成在 `ConversationChatInput` 输入框

## 架构

```
前端组件 → MediaRecorder API → 音频 Blob
  → FormData 上传 → 后端语音识别服务
  → 识别文本 → 回调前端填入输入框 / 直接发送
```

## 前端代码路径

- 前端组件: `frontend/src/components/conversation/core/ChatInput.tsx`（集成 VoiceRecorder）
- TTS 组件: `frontend/src/components/conversation/core/SpeakButton`（消息朗读）

## 后端 API

- 路由模块: `backend/app/api/system/multimodal.py`

> 完整设计见 [phases/03-capability-upgrade/multimodal-design.md](../../archive/2026-phases/03-capability-upgrade/multimodal-design.md)。

# 多模态交互系统 · 设计文档

> **状态**: 已审核，待实施  
> **当前完成度**: 40% → 目标 80%  
> **依赖**: 对话系统（ContentBlock）、MediaSearchBlock（共存）

---

## 一、现状与范围

### 1.1 已有（不重复造轮子）

```
✅ ContentBlock 类型体系
   TextBlock | ImageBlock | AudioBlock | VideoBlock | DocumentBlock
   前后端对齐，transcription 字段已预留

✅ FileRecord + 上传管道
   POST /api/materials/upload → storage → processing_status

✅ MediaSearchBlock（多平台搜索结果展示）
   B站/Bing/知乎/小红书等平台外链，新窗口打开
   → 保留不动，VideoEmbed 与其共存而非替换

❌ ChatInput 按钮全部为空壳
   Mic / Video / Image / Paperclip → 均无实际功能
```

### 1.2 本阶段范围

| # | 能力 | 优先级 | 一句话 |
|---|------|:--:|------|
| ① | **语音输入 (STT)** | P0 | 点 Mic 说话 → 自动转文字填入输入框 |
| ② | **视频内嵌播放** | P0 | B站/YouTube 链接 → 对话内 iframe 直接播 |
| ③ | **语音输出 (TTS)** | P1 | AI 长回答旁出现 🔊 朗读按钮 |

### 1.3 明确推迟的

| 推迟项 | 归属模块 | 原因 |
|--------|---------|------|
| 文件类型扩展（30+格式） | 资料系统升级 | 独立模块，不阻塞多模态交互 |
| 手写/公式识别 (OCR) | P2 | 需第三方 API，本期不投入 |
| 图片理解增强（拍照讲题） | P2 | 需多模态 LLM，基础交互先行 |

---

## 二、① 语音输入 (STT) — P0

### 2.1 双通道策略

```
┌────────────────────────────────────────────┐
│              VoiceRecorder 组件              │
│                                              │
│  通道A: Web Speech API (首选)                │
│  ├─ Chrome/Edge 内置，零延迟                  │
│  ├─ 实时 interim 预览                        │
│  └─ 限制: 仅 Chrome 系，微信浏览器不支持       │
│                                              │
│  通道B: MediaRecorder → Whisper API (兜底)   │
│  ├─ 录音 → WAV → POST /api/multimodal/transcribe │
│  ├─ 后端调用 OpenAI whisper-1                │
│  └─ 兼容所有浏览器（含微信内置浏览器）          │
└────────────────────────────────────────────┘
```

### 2.2 组件接口

```typescript
interface VoiceRecorderProps {
  onTranscription: (text: string) => void;
  disabled?: boolean;
}
// 状态机: idle → recording → processing → idle
```

### 2.3 视觉状态

| 状态 | 效果 |
|------|------|
| idle | 灰色 Mic，hover 变蓝 |
| recording | 红色脉冲 + "录音中..." 浮标 |
| processing | 旋转 Loader |
| interim | 输入框上方灰色斜体实时预览 |
| error | 红色微型提示，3 秒消失 |

### 2.4 集成点

```
ChatInput.tsx
  └─ 现有空壳 <Mic> → VoiceRecorder
  └─ onTranscription → 填入 textarea（用户可编辑后发送）
```

### 2.5 后端 API

```
POST /api/multimodal/transcribe
  Body: multipart/form-data { audio_file }
  → LiteLLM → openai/whisper-1
  ← { transcription, language, duration_ms }
  
  临时文件: /tmp/edu-companion/audio/{uuid}.wav → 处理完清理
  费用: $0.006/分钟
```

---

## 三、② 视频内嵌播放 — P0

### 3.1 与 MediaSearchBlock 的关系

```
ResponseBlockRenderer 的 type="video" case:

  现有: MediaSearchBlock → 多平台搜索结果外链（保留）
  新增: VideoEmbed       → 单一视频 iframe 内嵌播放

判断逻辑:
  if content.url && isVideoPlatform(url)
    → VideoEmbed (iframe)
  else
    → MediaSearchBlock (搜索结果，现有行为)
```

### 3.2 渲染策略

```
VideoEmbed 组件
  ├─ B站 (bilibili.com/BVxxx)   → player.bilibili.com iframe
  ├─ YouTube (youtu.be/xxx)     → youtube-nocookie.com iframe  
  └─ 其他 (直链 .mp4)           → <video> 原生标签
```

### 3.3 URL 解析（纯前端，无需后端）

```typescript
function parseVideoUrl(url: string): VideoInfo | null {
  // B站: bilibili.com/video/BV1xx411c7mD
  const biliMatch = url.match(/bilibili\.com\/video\/(BV[a-zA-Z0-9]+)/);
  if (biliMatch) return { platform: "bilibili", id: biliMatch[1] };

  // YouTube: youtube.com/watch?v=xxx 或 youtu.be/xxx
  const ytMatch = url.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]+)/);
  if (ytMatch) return { platform: "youtube", id: ytMatch[1] };

  // 直链视频
  if (/\.(mp4|webm|mov|flv)(\?|$)/i.test(url)) return { platform: "direct", id: url };
  
  return null;
}
```

### 3.4 组件接口

```typescript
interface VideoEmbedProps {
  url: string;
  title?: string;
  thumbnail?: string;
  aspectRatio?: "16:9" | "4:3";
}
```

---

## 四、③ 语音输出 (TTS) — P1

### 4.1 设计

```
AI 长回答（>300字）→ 消息旁显示 🔊 按钮
  → 点击 → 浏览器 SpeechSynthesis 朗读
  → 中文 zh-CN 女声，语速 1.1x
  → 零成本，零延迟
```

### 4.2 组件

```typescript
// MessageActions 工具栏新增
<SpeakButton text={messageContent} />

// 内部:
const u = new SpeechSynthesisUtterance(text);
u.lang = "zh-CN"; u.rate = 1.1;
speechSynthesis.speak(u);
```

---

## 五、组件树变更

```
ChatInput.tsx (修改)
  ├─ VoiceRecorder  ← 新组件（替换空壳 Mic）
  ├─ Video 按钮     ← 弹出输入框 "粘贴视频链接"
  └─ textarea (现)

ResponseBlockRenderer.tsx (修改)
  └─ type="video" case
      ├─ VideoEmbed     ← 新：iframe 内嵌（当 url 是视频平台链接）
      └─ MediaSearchBlock ← 旧：搜索结果外链（保留）

MessageActions.tsx (新建/修改)
  └─ SpeakButton  ← 新：长回答朗读

新增后端:
  app/api/multimodal.py
    POST /api/multimodal/transcribe   ← STT 兜底
```

---

## 六、实施计划

### Phase A: STT 语音输入（1-2h）

| 步骤 | 产出 |
|------|------|
| A1 | `VoiceRecorder.tsx` — Web Speech API 通道A |
| A2 | ChatInput 集成 — Mic 按钮接线 |
| A3 | `POST /api/multimodal/transcribe` — Whisper 通道B |
| A4 | 微信浏览器兼容验证 |

### Phase B: 视频内嵌（1h）

| 步骤 | 产出 |
|------|------|
| B1 | `VideoEmbed.tsx` — B站/YouTube iframe 解析渲染 |
| B2 | ResponseBlockRenderer — video case 分流逻辑 |
| B3 | ChatInput — 粘贴链接自动识别 / Video 按钮 |

### Phase C: TTS 朗读（0.5h）

| 步骤 | 产出 |
|------|------|
| C1 | `SpeakButton.tsx` — SpeechSynthesis 组件 |
| C2 | MessageActions 集成 |

---

## 七、风险

| 风险 | 缓解 |
|------|------|
| 微信浏览器不支持 Web Speech | 自动降级通道B: MediaRecorder → Whisper |
| Whisper API 费用 | $0.006/分钟，学生日均 < 5 分钟 |
| B站 iframe 限速 | 提供 "在B站打开" 外链 fallback |
| 移动端录音权限 | 浏览器自动弹权限请求 |

---

## 八、验收标准

- [ ] Chrome: Mic 录音 → 自动填文字到输入框
- [ ] 微信浏览器: 录音 → Whisper 转录 → 返回文字
- [ ] 粘贴 B站链接 → 对话内嵌 iframe 播放器
- [ ] 粘贴 YouTube 链接 → 对话内嵌 iframe 播放器
- [ ] AI 长回答（>300字）旁出现 🔊 按钮，点击可朗读
- [ ] STT 错误率 < 5%（中文普通话）

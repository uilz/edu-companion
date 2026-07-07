export const EMOTION_CONFIG: Record<string, { label: string; emoji: string; color: string; severity: string }> = {
  frustration: { label: "挫败", emoji: "😤", color: "#ef4444", severity: "negative" },
  anxiety: { label: "焦虑", emoji: "😰", color: "#f97316", severity: "negative" },
  confusion: { label: "困惑", emoji: "🤔", color: "#eab308", severity: "neutral" },
  boredom: { label: "无聊", emoji: "😴", color: "#a1a1aa", severity: "negative" },
  overwhelm: { label: "压力大", emoji: "😵", color: "#dc2626", severity: "negative" },
  procrastination: { label: "拖延", emoji: "🥱", color: "#d946ef", severity: "negative" },
  motivated: { label: "有动力", emoji: "💪", color: "#22c55e", severity: "positive" },
  achievement: { label: "成就感", emoji: "🎉", color: "#06b6d4", severity: "positive" },
  curious: { label: "好奇", emoji: "🔍", color: "#6366f1", severity: "positive" },
  calm: { label: "平静", emoji: "😌", color: "#8b5cf6", severity: "positive" },
  neutral: { label: "中性", emoji: "📝", color: "#6b7280", severity: "neutral" },
};

export const DIRECTION_LABELS: Record<string, { label: string; icon: string; color: string }> = {
  improving: { label: "变好", icon: "📈", color: "text-success" },
  declining: { label: "变差", icon: "📉", color: "text-danger" },
  stable: { label: "稳定", icon: "➡️", color: "text-muted" },
  volatile: { label: "波动", icon: "〰️", color: "text-warning" },
};

export const SIGNAL_LABELS: Record<string, { label: string; emoji: string }> = {
  task_switch: { label: "频繁切换任务", emoji: "🔀" },
  stay_duration: { label: "同一知识点停留异常", emoji: "⏱️" },
  error_rate: { label: "练习错误率突增", emoji: "📈" },
  undo: { label: "连续撤销/修改", emoji: "↩️" },
  session_anomaly: { label: "会话时长异常", emoji: "⏰" },
  flashcard_failure: { label: "卡片困难比例上升", emoji: "🃏" },
  voice_features: { label: "语音特征变化", emoji: "🎙️" },
};

export const INTERVENTION_LABELS: Record<string, { label: string; emoji: string }> = {
  breathing: { label: "呼吸引导", emoji: "🫁" },
  knowledge_breathing: { label: "知识呼吸", emoji: "🌬️" },
  cognitive_reappraisal: { label: "认知重评", emoji: "🧭" },
  environment: { label: "环境切换", emoji: "🎨" },
};
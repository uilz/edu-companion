/**
 * AppleGo Design Tokens — Motion
 *
 * Extracted from Demo3.0 (preview.html)
 * Use these tokens for all transitions and animations.
 */

export const easing = {
  /** Standard ease-out: for most UI transitions */
  easeOut: 'cubic-bezier(0,0,0.2,1)',
  /** Spring-like: for toggles, pop-in animations */
  easeSpring: 'cubic-bezier(0.34,1.56,0.64,1)',
} as const;

export const duration = {
  /** 150ms — Hover states, micro-interactions */
  fast: 150,
  /** 200ms — Toggle switches, subtle transitions */
  normal: 200,
  /** 300ms — Panel enters, message appears */
  medium: 300,
  /** 400ms — Page fade-in, element appears */
  slow: 400,
  /** 500ms — Typing cursor delay */
  typingDelay: 500,
  /** 600ms — Card flip */
  flip: 600,
  /** 800ms — Voice response delay */
  voiceDelay: 800,
  /** 900ms — Wave animation cycle */
  waveCycle: 900,
  /** 1000ms — Pomodoro ring update, standard second */
  second: 1000,
  /** 1200ms — Thinking dots cycle */
  thinkingCycle: 1200,
  /** 1500ms — Pulse animation cycle */
  pulseCycle: 1500,
  /** 1800ms — Voice ring animation cycle */
  voiceRingCycle: 1800,
  /** 2200ms — Toast display duration */
  toast: 2200,
} as const;

export type EasingToken = keyof typeof easing;
export type DurationToken = keyof typeof duration;

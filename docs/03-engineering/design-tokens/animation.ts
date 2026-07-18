/**
 * AppleGo Design Tokens — Animations (@keyframes)
 *
 * Extracted from Demo3.0 (preview.html)
 * Use these animation names in CSS animation properties.
 * Timing values reference the motion.ts duration tokens.
 */

export const animation = {
  /** Session overlay enter: translateY(20px) → 0, opacity 0→1, 300ms ease-out */
  sessionEnter: {
    name: 'sessionEnter',
    keyframes: `
      @keyframes sessionEnter {
        from { opacity: 0; transform: translateY(20px); }
        to   { opacity: 1; transform: translateY(0); }
      }`,
  },

  /** New message appear: translateY(8px) → 0, opacity 0→1, 300ms ease-out */
  msgIn: {
    name: 'msgIn',
    keyframes: `
      @keyframes msgIn {
        from { opacity: 0; transform: translateY(8px); }
        to   { opacity: 1; transform: translateY(0); }
      }`,
  },

  /** Typing cursor blink: opacity on/off, 0.8s infinite */
  blink: {
    name: 'blink',
    keyframes: `
      @keyframes blink {
        0%, 50%   { opacity: 1; }
        51%, 100% { opacity: 0; }
      }`,
  },

  /** Thinking dots bounce: 3 dots with 0.2s delay stagger, 1.2s infinite */
  thinking: {
    name: 'thinking',
    keyframes: `
      @keyframes thinking {
        0%, 60%, 100% { opacity: .3; transform: translateY(0); }
        30%           { opacity: 1; transform: translateY(-3px); }
      }`,
  },

  /** Voice ring: expanding circles, 1.8s infinite */
  voiceRing: {
    name: 'voiceRing',
    keyframes: `
      @keyframes voiceRing {
        0%   { transform: scale(1); opacity: .5; }
        100% { transform: scale(1.5); opacity: 0; }
      }`,
  },

  /** Voice wave bar: height oscillation, 0.9s infinite ease-out */
  waveBar: {
    name: 'waveBar',
    keyframes: `
      @keyframes waveBar {
        0%, 100% { height: 6px; }
        50%      { height: 28px; }
      }`,
  },

  /** Canvas new node pop-in: scale up + fade, 400ms ease-spring */
  nodePop: {
    name: 'nodePop',
    keyframes: `
      @keyframes nodePop {
        0%   { transform: scale(.7); opacity: 0; }
        100% { transform: scale(1); opacity: 1; }
      }`,
  },

  /** Pulse: for badges, red dots, 1.5s infinite */
  pulse: {
    name: 'pulse',
    keyframes: `
      @keyframes pulse {
        0%, 100% { opacity: 1; }
        50%      { opacity: .4; }
      }`,
  },

  /** Fade in: for page content, 400ms ease-out */
  fadeIn: {
    name: 'fadeIn',
    keyframes: `
      @keyframes fadeIn {
        from { opacity: 0; }
        to   { opacity: 1; }
      }`,
  },
} as const;

export type AnimationToken = keyof typeof animation;

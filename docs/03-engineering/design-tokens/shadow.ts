/**
 * AppleGo Design Tokens — Box Shadow
 *
 * Extracted from Demo3.0 (preview.html)
 */

export const shadow = {
  /** Card: default card surface */
  card: '0 1px 3px rgba(0,0,0,.04), 0 0 0 1px var(--color-divider-soft)',
  /** Card hover: elevated card state */
  cardHover: '0 4px 16px rgba(0,0,0,.06), 0 0 0 1.5px var(--color-divider-hover)',
  /** Primary button glow */
  buttonPrimary: '0 4px 14px var(--color-accent-glow)',
  /** Tool tray menu dropdown */
  toolTray: '0 8px 32px rgba(0,0,0,.18)',
  /** Demo bar top */
  demoBar: '0 4px 24px rgba(0,0,0,.18)',
  /** Flashcard face */
  flashcard: '0 4px 24px rgba(0,0,0,.08), 0 0 0 1px var(--color-divider-soft)',
  /** Canvas node default */
  canvasNode: '0 2px 12px rgba(0,0,0,.08), 0 0 0 1px var(--color-divider)',
  /** Canvas node hover */
  canvasNodeHover: '0 4px 20px rgba(0,0,0,.12), 0 0 0 1.5px var(--color-accent)',
  /** Canvas add FAB button */
  canvasAdd: '0 4px 16px var(--color-accent-glow)',
  /** Pomodoro clock face */
  pomoClock: '0 0 0 1px var(--color-divider-soft), 0 8px 32px rgba(0,0,0,.06)',
  /** Modal/tool page inner */
  inner: 'inset 0 0 0 1.5px var(--color-divider)',
} as const;

export type ShadowToken = keyof typeof shadow;

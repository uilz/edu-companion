// ══════════════════════════════════════════════════════════════
//  token-throttle — Token 累积节流器
//
//  消除 useChatStream 与 StreamPipeline 之间 token flush 节流的重复。
//  在 200ms 窗口内累积 token，到期一次 flush，减少高频 setState。
// ══════════════════════════════════════════════════════════════

export interface TokenThrottle {
  /** 追加 token 文本，触发节流 flush 调度 */
  add(text: string): void;
  /** 强制立即 flush，返回累积文本 */
  flush(): string;
  /** 重置缓存 */
  reset(): void;
}

/**
 * 创建 token 累积节流器
 *
 * @param flushIntervalMs flush 间隔（默认 200ms）
 * @param onFlush 每次 flush 时的回调（收到累积文本）
 */
export function createTokenThrottle(
  onFlush?: (text: string) => void,
  flushIntervalMs: number = 200,
): TokenThrottle {
  let buffer = "";
  let timer: ReturnType<typeof setTimeout> | null = null;
  let scheduled = false;

  function doFlush(): string {
    const text = buffer;
    buffer = "";
    scheduled = false;
    if (timer) { clearTimeout(timer); timer = null; }
    return text;
  }

  return {
    add(text: string) {
      buffer += text;
      if (!scheduled) {
        scheduled = true;
        timer = setTimeout(() => {
          const flushed = doFlush();
          if (flushed) onFlush?.(flushed);
        }, flushIntervalMs);
      }
    },
    flush(): string {
      const text = doFlush();
      if (text) onFlush?.(text);
      return text;
    },
    reset() {
      doFlush();
    },
  };
}

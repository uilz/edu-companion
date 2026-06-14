// ══════════════════════════════════════════════════════════════
//  StreamPipeline — barrel export
// ══════════════════════════════════════════════════════════════

export { StreamPipeline } from "./StreamPipeline";
export { EventSourceSSE, MockSSE } from "./SSESource";
export { getPipeline, bindPipelineToStore } from "./setup";
export type {
  StreamPhase,
  SSESource,
  StreamEventMap,
  StreamEventCallback,
  Unsubscribe,
} from "./types";

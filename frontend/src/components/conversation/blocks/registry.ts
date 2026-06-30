"use client";

import React from "react";
import type { ToolBlock, ReasoningBlock } from "@/types";
import ToolCallBlock from "./ToolCallBlock";
import ReasoningBlockComponent from "./ReasoningBlock";

/**
 * Block Renderer Registry
 *
 * 将 content_blocks 的 type 映射到对应的渲染组件。
 * 新增 block 类型时只需在此注册一行，MessageList 无需改动。
 *
 * 注意：text block 在 MessageList 中有特殊渲染（ExplainMarkers 等），
 * 不通过此 registry 注册。
 */
export const BLOCK_RENDERERS: Record<string, React.ComponentType<{ block: any }>> = {
  tool: ToolCallBlock as React.ComponentType<{ block: any }>,
  reasoning: ReasoningBlockComponent as React.ComponentType<{ block: any }>,
};

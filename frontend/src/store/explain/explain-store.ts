// ══════════════════════════════════════════════════════════════
//  Zustand store — Knowledge Explain Cards
//
//  持久化到后端 explain_cards 表，纯 UI 状态通过 API 同步。
//  每张卡片绑定到一条消息 (message_id)，出现在选中文本旁。
//  可拖动 (posX/posY)、可递归折叠/删除、无数量限制。
// ══════════════════════════════════════════════════════════════

import { create } from "zustand";
import { api } from "@/lib/api/api";

// ── Types ──

/** 卡片内部对话消息 */
export interface CardMessage {
  role: "user" | "assistant";
  content: string;
}

export interface ExplainCardData {
  id: string;
  user_id?: string;
  conversation_id: string;
  /** 绑定到哪个消息 */
  message_id: string;
  /** 卡片深度：1 = 从消息中触发，2+ = 从卡片中触发 */
  depth: number;
  /** 父卡片 ID（深度 > 1 时有效） */
  parent_card_id?: string;
  /** 用户选中的文本 */
  selected_text: string;
  /** 选中时的完整消息文本（用于 AI 上下文） */
  source_message_text?: string;
  /** 关联的知识图谱节点 ID */
  context_node_id?: string;
  /** AI 解释内容（缓存） */
  explanation?: string;
  /** 掌握程度 */
  mastery: "unknown" | "learning" | "mastered";
  /** 位置 X（相对于消息容器的偏移，像素）— 卡片的可拖动位置 */
  pos_x: number;
  /** 位置 Y（相对于消息容器的偏移，像素） */
  pos_y: number;
  /** 角标位置 X（固定在选中文本处，不与卡片一起移动） */
  badge_x: number;
  /** 角标位置 Y */
  badge_y: number;
  /** 选中文本在消息全文中的字符偏移（避免 indexOf 重复文本歧义） */
  char_start?: number;
  /** 卡片宽度（可拖动调整，持久化） */
  width?: number;
  /** 卡片高度（可拖动调整，持久化） */
  height?: number;
  /** 是否折叠 */
  collapsed: boolean;
  /** 卡片内部对话历史 */
  conversation: CardMessage[];
  /** 创建时间 */
  created_at?: string;
  updated_at?: string;
}

interface ExplainStore {
  cards: ExplainCardData[];

  // ── API 同步 ──
  /** 从后端加载该对话的所有卡片 */
  loadFromConversation: (conversationId: string) => Promise<void>;
  /** 在后端创建卡片，返回完整数据 */
  createCard: (data: {
    conversation_id: string;
    message_id: string;
    depth: number;
    parent_card_id?: string;
    selected_text: string;
    source_message_text?: string;
    context_node_id?: string;
    pos_x: number;
    pos_y: number;
    badge_x: number;
    badge_y: number;
    char_start?: number;
  }) => Promise<ExplainCardData>;
  /** 更新卡片字段到后端 + store */
  updateCard: (id: string, updates: Partial<Pick<ExplainCardData, "explanation" | "mastery" | "pos_x" | "pos_y" | "collapsed" | "conversation" | "width" | "height">>) => Promise<void>;
  /** 删除卡片（级联） */
  deleteCard: (id: string) => Promise<void>;

  // ── 本地操作（操作 store，含递归逻辑） ──
  /** 递归折叠：折叠某卡片 + 所有子孙 */
  toggleCollapse: (id: string, collapsed: boolean) => void;
  /** 关闭某卡片 + 所有子孙（仅本地，不调 API） */
  removeLocal: (id: string) => void;
  /** 将后端返回的数据插入 store */
  _upsert: (card: ExplainCardData) => void;
  /** 替换整个 cards 列表 */
  _setAll: (cards: ExplainCardData[]) => void;
  /** 清空 */
  clearAll: () => void;
}

// ── Helpers ──

/** 递归获取某卡片 + 所有子孙的 ID（在 cards 数组中） */
function collectDescendantIds(cardId: string, allCards: ExplainCardData[]): string[] {
  const ids: string[] = [cardId];
  for (const c of allCards) {
    if (c.parent_card_id === cardId) {
      ids.push(...collectDescendantIds(c.id, allCards));
    }
  }
  return ids;
}

/** 递归检查是否为子孙 */
function isDescendantOf(
  card: ExplainCardData,
  ancestorId: string,
  allCards: ExplainCardData[],
): boolean {
  if (card.parent_card_id === ancestorId) return true;
  if (!card.parent_card_id) return false;
  const parent = allCards.find((c) => c.id === card.parent_card_id);
  if (!parent) return false;
  return isDescendantOf(parent, ancestorId, allCards);
}

// ── Store ──

export const useExplainStore = create<ExplainStore>((set, get) => ({
  cards: [],

  loadFromConversation: async (conversationId) => {
    try {
      const data = await api<ExplainCardData[]>(
        `/api/knowledge-tree/explain-cards?conversation_id=${encodeURIComponent(conversationId)}`,
      );
      set({ cards: data });
    } catch {
      // 静默失败
    }
  },

  createCard: async (data) => {
    try {
      const card = await api<ExplainCardData>(
        `/api/knowledge-tree/explain-cards`,
        {
          method: "POST",
          body: JSON.stringify(data),
        },
      );
      set((s) => ({ cards: [...s.cards, card] }));
      return card;
    } catch {
      // 后端不可用时，生成本地 ID 插入（降级模式）
      const localCard: ExplainCardData = {
        id: `explain_local_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        conversation_id: data.conversation_id,
        message_id: data.message_id,
        depth: data.depth,
        parent_card_id: data.parent_card_id,
        selected_text: data.selected_text,
        source_message_text: data.source_message_text,
        context_node_id: data.context_node_id,
        explanation: "",
        mastery: "unknown",
        pos_x: data.pos_x,
        pos_y: data.pos_y,
        badge_x: data.badge_x,
        badge_y: data.badge_y,
        char_start: data.char_start,
        collapsed: false,
        conversation: [],
        created_at: new Date().toISOString(),
      };
      set((s) => ({ cards: [...s.cards, localCard] }));
      return localCard;
    }
  },

  updateCard: async (id, updates) => {
    // 先本地更新（乐观更新）
    set((s) => ({
      cards: s.cards.map((c) =>
        c.id === id ? { ...c, ...updates } : c,
      ),
    }));
    // 同步到后端
    try {
      await api<void>(`/api/knowledge-tree/explain-cards/${id}`, {
        method: "PATCH",
        body: JSON.stringify(updates),
      });
    } catch {
      // 静默
    }
  },

  deleteCard: async (id) => {
    // 收集要删除的 ID（含子孙）
    const allIds = collectDescendantIds(id, get().cards);
    // 本地删除
    set((s) => ({
      cards: s.cards.filter((c) => !allIds.includes(c.id)),
    }));
    // 同步到后端
    try {
      await api<void>(`/api/knowledge-tree/explain-cards/${id}`, { method: "DELETE" });
    } catch {
      // 静默
    }
  },

  toggleCollapse: (id, collapsed) => {
    // 递归获取所有子孙
    const allIds = collectDescendantIds(id, get().cards);
    set((s) => ({
      cards: s.cards.map((c) =>
        allIds.includes(c.id) ? { ...c, collapsed } : c,
      ),
    }));
    // 异步同步到后端（只同步根卡片）
    api<void>(`/api/knowledge-tree/explain-cards/${id}`, {
      method: "PATCH",
      body: JSON.stringify({ collapsed }),
    }).catch(() => {});
  },

  removeLocal: (id) => {
    const allIds = collectDescendantIds(id, get().cards);
    set((s) => ({
      cards: s.cards.filter((c) => !allIds.includes(c.id)),
    }));
  },

  _upsert: (card) => {
    set((s) => {
      const idx = s.cards.findIndex((c) => c.id === card.id);
      if (idx >= 0) {
        const next = [...s.cards];
        next[idx] = card;
        return { cards: next };
      }
      return { cards: [...s.cards, card] };
    });
  },

  _setAll: (cards) => set({ cards }),

  clearAll: () => set({ cards: [] }),
}));

/** 获取某消息下的所有卡片（按 depth 排序） */
export function getCardsForMessage(
  messageId: string,
  allCards: ExplainCardData[],
): ExplainCardData[] {
  return allCards
    .filter((c) => c.message_id === messageId)
    .sort((a, b) => {
      // 同级按创建时间
      if (a.depth !== b.depth) return a.depth - b.depth;
      return (a.created_at || "").localeCompare(b.created_at || "");
    });
}

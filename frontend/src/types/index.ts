export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

export interface Settings {
  apiEndpoint: string;
  apiKey: string;
  modelName: string;
  systemPrompt: string;
}

export interface ChatRequest {
  conversationId: string;
  message: string;
  settings: Settings;
}

export interface StreamEvent {
  type: "token" | "done" | "error";
  content?: string;
  conversationId?: string;
  messageId?: string;
}

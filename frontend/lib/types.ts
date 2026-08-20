export type ToolName = "search_internal_db" | "search_the_web" | string;

export interface Source {
  source: string;
  page: string | number | null;
}

export interface ChatResponse {
  answer: string;
  sources: Source[];
  tool_used: ToolName[];
}

export type MessageRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  toolsUsed?: ToolName[];
  sources?: Source[];
  pending?: boolean;
  error?: boolean;
}

export interface UploadResponse {
  filename: string;
  chunks_inserted: number;
}

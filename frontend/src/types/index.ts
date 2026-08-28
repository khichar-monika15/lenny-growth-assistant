export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: Date;
}

export interface Source {
  chunk_id: string;
  transcript_title: string;
  similarity_score: number;
}

export type ModelProvider = 'claude' | 'ollama';

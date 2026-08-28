/**
 * API client for backend communication
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080';

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: Array<{
    chunk_id: string;
    transcript_title: string;
    similarity_score: number;
  }>;
}

export interface ChatRequest {
  message: string;
  session_id?: string;
  model_provider?: 'claude' | 'ollama';
}

export interface ChatResponse {
  message: string;
  sources: Array<any>;
  usage: {
    input_tokens: number;
    output_tokens: number;
  };
}

export const api = {
  async chat(request: ChatRequest): Promise<ChatResponse> {
    const response = await fetch(`${API_BASE_URL}/api/v1/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    return response.json();
  },

  async healthCheck() {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.json();
  }
};

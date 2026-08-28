export type ModelProvider = 'claude' | 'ollama'

export type ArtifactType = 'markdown' | 'html'

export interface Source {
  index: number
  chunk_id: string
  transcript_title: string
  transcript_date: string
  guests: string[]
  source_url: string
  similarity_score: number
}

export interface Artifact {
  type: ArtifactType
  title: string
  content: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  artifact?: Artifact
  error?: string
  createdAt: string
}

export interface SessionSummary {
  id: string
  title: string | null
  user_id: string
  model_provider: ModelProvider | null
  model_name: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface StoredMessage {
  id: string
  session_id: string
  role: 'user' | 'assistant'
  content: string
  sources: Source[]
  token_count: number | null
  model_provider: string | null
  created_at: string
}

export interface SessionDetail extends SessionSummary {
  messages: StoredMessage[]
}

export interface ProviderHealth {
  default: ModelProvider
  ollama: {
    status: 'available' | 'unavailable' | 'model_missing'
    model: string
    chat_model_pulled?: boolean
    embedding_model_pulled?: boolean
    hint?: string
  }
  anthropic: {
    status: 'configured' | 'not_configured'
    model: string
  }
}

export interface RetrievalHealth {
  chromadb: 'available' | 'unavailable'
  indexed_chunks: number
  hint: string | null
}

/** Events emitted by POST /api/v1/chat/stream. */
export type StreamEvent =
  | {
      type: 'session'
      session_id: string
      intent: string
      provider: ModelProvider
      model: string
      fallback_reason: string | null
    }
  | { type: 'sources'; sources: Source[]; retrieval_error: string | null }
  | { type: 'content_delta'; delta: string }
  | { type: 'artifact'; artifact: Artifact }
  | { type: 'message_stop'; usage?: Record<string, number>; session_id?: string }
  | { type: 'error'; error: string; detail: string; hint?: string | null }

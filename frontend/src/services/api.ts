/**
 * Backend API client.
 *
 * `streamChat` parses the SSE framing itself rather than using EventSource,
 * because the stream is a POST. Partial lines are buffered across reads: a
 * network chunk can split a `data:` line in half, and parsing eagerly used to
 * drop those deltas silently.
 */
import type {
  ProviderHealth,
  RetrievalHealth,
  SessionDetail,
  SessionSummary,
  StreamEvent,
} from '../types'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8080'

/**
 * True when a rejection is the caller stopping the stream on purpose.
 *
 * Browsers disagree on the shape: Chrome throws a bare TypeError with
 * "BodyStreamBuffer was aborted", Safari and Firefox throw AbortError. The
 * signal is the reliable tell.
 */
function isAbort(error: unknown, signal?: AbortSignal): boolean {
  if (signal?.aborted) return true
  const name = (error as Error | undefined)?.name
  const message = (error as Error | undefined)?.message ?? ''
  return name === 'AbortError' || /abort/i.test(message)
}

export class ApiError extends Error {
  readonly hint?: string

  constructor(message: string, hint?: string) {
    super(message)
    this.name = 'ApiError'
    this.hint = hint
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    throw new ApiError(
      'Cannot reach the backend.',
      `Is it running at ${API_BASE_URL}? Try: docker compose ps backend`,
    )
  }

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    if (detail && typeof detail === 'object') {
      throw new ApiError(detail.detail ?? response.statusText, detail.hint ?? undefined)
    }
    throw new ApiError(typeof detail === 'string' ? detail : response.statusText)
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export interface StreamChatOptions {
  message: string
  sessionId?: string | null
  modelProvider?: string | null
  signal?: AbortSignal
  onEvent: (event: StreamEvent) => void
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  providerHealth: () => request<ProviderHealth>('/health/llm'),

  retrievalHealth: () => request<RetrievalHealth>('/health/retrieval'),

  listSessions: () => request<SessionSummary[]>('/api/v1/sessions'),

  createSession: (modelProvider?: string | null) =>
    request<SessionSummary>('/api/v1/sessions', {
      method: 'POST',
      body: JSON.stringify({ model_provider: modelProvider ?? null }),
    }),

  getSession: (id: string) => request<SessionDetail>(`/api/v1/sessions/${id}`),

  deleteSession: (id: string) =>
    request<void>(`/api/v1/sessions/${id}`, { method: 'DELETE' }),

  async streamChat({
    message,
    sessionId,
    modelProvider,
    signal,
    onEvent,
  }: StreamChatOptions): Promise<void> {
    let response: Response
    try {
      response = await fetch(`${API_BASE_URL}/api/v1/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          session_id: sessionId ?? null,
          model_provider: modelProvider ?? null,
        }),
        signal,
      })
    } catch (error) {
      if (isAbort(error, signal)) return
      throw new ApiError(
        'Cannot reach the backend.',
        `Is it running at ${API_BASE_URL}? Try: docker compose ps backend`,
      )
    }

    if (!response.ok || !response.body) {
      throw new ApiError(`The server rejected the request (HTTP ${response.status}).`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        let chunk: ReadableStreamReadResult<Uint8Array>
        try {
          chunk = await reader.read()
        } catch (error) {
          // Stopping mid-stream rejects the pending read. That is the user
          // getting what they asked for, not a failure, so it must not
          // surface as "BodyStreamBuffer was aborted".
          if (isAbort(error, signal)) return
          throw error
        }

        const { done, value } = chunk
        if (done) break

        // stream: true keeps multi-byte characters intact across chunks.
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        // The trailing element may be a partial line; hold it for the next read.
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data:')) continue

          const payload = trimmed.slice(5).trim()
          if (!payload || payload === '[DONE]') continue

          try {
            onEvent(JSON.parse(payload) as StreamEvent)
          } catch {
            console.warn('Discarding unparseable SSE payload', payload.slice(0, 200))
          }
        }
      }
    } finally {
      try {
        reader.releaseLock()
      } catch {
        // Already released by the abort.
      }
    }
  },
}

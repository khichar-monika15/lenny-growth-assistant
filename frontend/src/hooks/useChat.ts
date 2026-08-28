/**
 * Chat state and SSE streaming.
 *
 * Owns the message list, the active session and the in-flight request. The
 * stream is always terminated in a `finally`, so an error or an abort can
 * never leave the composer permanently disabled - the previous version had
 * no error branch and locked the UI whenever the backend failed mid-stream.
 */
import { useCallback, useRef, useState } from 'react'
import { ApiError, api } from '../services/api'
import type { Artifact, Message, ModelProvider, StoredMessage } from '../types'

function newId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `m_${Date.now()}_${Math.random()}`
}

function toMessage(stored: StoredMessage): Message {
  return {
    id: stored.id,
    role: stored.role,
    content: stored.content,
    sources: stored.sources ?? [],
    // Restored so switching away from a chat and back does not lose the
    // generated document.
    artifact: stored.artifact ?? undefined,
    createdAt: stored.created_at,
  }
}

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [activeArtifact, setActiveArtifact] = useState<Artifact | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const patchLast = useCallback((patch: (message: Message) => Message) => {
    setMessages((current) => {
      if (current.length === 0) return current
      const next = [...current]
      next[next.length - 1] = patch(next[next.length - 1])
      return next
    })
  }, [])

  const send = useCallback(
    async (text: string, provider: ModelProvider) => {
      const trimmed = text.trim()
      if (!trimmed || isStreaming) return

      const controller = new AbortController()
      abortRef.current = controller
      setIsStreaming(true)

      setMessages((current) => [
        ...current,
        { id: newId(), role: 'user', content: trimmed, createdAt: new Date().toISOString() },
        {
          id: newId(),
          role: 'assistant',
          content: '',
          sources: [],
          createdAt: new Date().toISOString(),
        },
      ])

      try {
        await api.streamChat({
          message: trimmed,
          sessionId,
          modelProvider: provider,
          signal: controller.signal,
          onEvent: (event) => {
            switch (event.type) {
              case 'session':
                setSessionId(event.session_id)
                break

              case 'sources':
                patchLast((message) => ({ ...message, sources: event.sources }))
                if (event.retrieval_error) {
                  patchLast((message) => ({
                    ...message,
                    error: `Retrieval failed, so this answer is not grounded: ${event.retrieval_error}`,
                  }))
                }
                break

              case 'content_delta':
                patchLast((message) => ({
                  ...message,
                  content: message.content + event.delta,
                }))
                break

              case 'artifact':
                patchLast((message) => ({ ...message, artifact: event.artifact }))
                setActiveArtifact(event.artifact)
                break

              case 'error':
                patchLast((message) => ({
                  ...message,
                  error: event.hint ? `${event.detail} ${event.hint}` : event.detail,
                }))
                break

              case 'message_stop':
                if (event.session_id) setSessionId(event.session_id)
                break
            }
          },
        })
      } catch (error) {
        const apiError = error as ApiError
        patchLast((message) => ({
          ...message,
          error: apiError.hint
            ? `${apiError.message} ${apiError.hint}`
            : apiError.message || 'Something went wrong.',
        }))
      } finally {
        setIsStreaming(false)
        abortRef.current = null
      }
    },
    [isStreaming, patchLast, sessionId],
  )

  const stop = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsStreaming(false)
  }, [])

  /**
   * Re-ask the most recent question.
   *
   * Drops the previous pair locally so the thread does not show the old and
   * new answer side by side. The original turn stays in the database, which
   * is the honest record of what was actually generated.
   */
  const regenerate = useCallback(
    async (provider: ModelProvider) => {
      if (isStreaming) return

      const lastUser = [...messages].reverse().find((m) => m.role === 'user')
      if (!lastUser) return

      setMessages((current) => {
        const index = current.findIndex((m) => m.id === lastUser.id)
        return index === -1 ? current : current.slice(0, index)
      })

      await send(lastUser.content, provider)
    },
    [isStreaming, messages, send],
  )

  /**
   * Replace a user turn with edited text and answer it again.
   *
   * Everything from that turn onward is dropped locally, matching how current
   * chat assistants behave: the edit supersedes the reply below it. The
   * original turn stays in the database as the honest record.
   */
  const editMessage = useCallback(
    async (messageId: string, text: string, provider: ModelProvider) => {
      const trimmed = text.trim()
      if (!trimmed || isStreaming) return

      setMessages((current) => {
        const index = current.findIndex((m) => m.id === messageId)
        return index === -1 ? current : current.slice(0, index)
      })

      await send(trimmed, provider)
    },
    [isStreaming, send],
  )

  const startNewChat = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsStreaming(false)
    setMessages([])
    setSessionId(null)
    setActiveArtifact(null)
  }, [])

  const loadSession = useCallback(async (id: string) => {
    abortRef.current?.abort()
    setIsStreaming(false)
    setActiveArtifact(null)

    const session = await api.getSession(id)
    const restored = session.messages.map(toMessage)
    setSessionId(session.id)
    setMessages(restored)

    const lastArtifact = [...restored].reverse().find((m) => m.artifact)?.artifact
    if (lastArtifact) setActiveArtifact(lastArtifact)
  }, [])

  return {
    messages,
    sessionId,
    isStreaming,
    activeArtifact,
    setActiveArtifact,
    send,
    stop,
    regenerate,
    editMessage,
    startNewChat,
    loadSession,
  }
}

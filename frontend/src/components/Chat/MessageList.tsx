import { useEffect, useRef } from 'react'
import type { Artifact, Message } from '../../types'
import { MarkdownRenderer } from '../Artifacts/MarkdownRenderer'
import { SourceList } from './SourceList'

interface Props {
  messages: Message[]
  isStreaming: boolean
  onOpenArtifact: (artifact: Artifact) => void
}

const EXAMPLES = [
  'What does Jen Abel say about closing enterprise deals?',
  'Write a Ship 30 essay about talent density',
  'Create a markdown checklist for a first enterprise sales call',
]

export function MessageList({ messages, isStreaming, onOpenArtifact }: Props) {
  const endRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const pinnedToBottom = useRef(true)

  // Follow the stream, but stop fighting the user if they scroll up to read.
  useEffect(() => {
    const list = listRef.current
    if (!list) return

    const onScroll = () => {
      const distance = list.scrollHeight - list.scrollTop - list.clientHeight
      pinnedToBottom.current = distance < 80
    }

    list.addEventListener('scroll', onScroll, { passive: true })
    return () => list.removeEventListener('scroll', onScroll)
  }, [])

  useEffect(() => {
    if (pinnedToBottom.current) {
      endRef.current?.scrollIntoView({ block: 'end' })
    }
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="messages" ref={listRef}>
        <div className="empty-state">
          <h2>Ask about product and growth</h2>
          <p>
            Every answer is grounded in Lenny&apos;s Podcast transcripts and cites the
            episodes it drew from.
          </p>
          <ul className="examples">
            {EXAMPLES.map((example) => (
              <li key={example}>{example}</li>
            ))}
          </ul>
        </div>
      </div>
    )
  }

  return (
    <div className="messages" ref={listRef}>
      <div aria-live="polite" aria-atomic="false" className="sr-only">
        {isStreaming ? 'Assistant is replying' : 'Reply complete'}
      </div>

      {messages.map((message, index) => {
        const isLast = index === messages.length - 1
        const awaitingFirstToken = isLast && isStreaming && !message.content

        return (
          <article key={message.id} className={`message ${message.role}`}>
            <div className="message-role">{message.role === 'user' ? 'You' : 'Assistant'}</div>

            <div className="message-content">
              {message.role === 'assistant' ? (
                awaitingFirstToken ? (
                  <span className="thinking" aria-label="Thinking">
                    <span /> <span /> <span />
                  </span>
                ) : (
                  <MarkdownRenderer content={message.content} />
                )
              ) : (
                message.content
              )}
            </div>

            {message.error && (
              <p className="message-error" role="alert">
                {message.error}
              </p>
            )}

            {message.artifact && (
              <button
                className="artifact-chip"
                onClick={() => onOpenArtifact(message.artifact!)}
              >
                <span className="artifact-badge">{message.artifact.type}</span>
                {message.artifact.title}
              </button>
            )}

            {message.sources && <SourceList sources={message.sources} />}
          </article>
        )
      })}

      <div ref={endRef} />
    </div>
  )
}

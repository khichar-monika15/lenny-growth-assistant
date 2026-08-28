import { useEffect, useRef } from 'react'
import type { Artifact, Message as MessageType } from '../../types'
import { Message } from './Message'

interface Props {
  messages: MessageType[]
  isStreaming: boolean
  onOpenArtifact: (artifact: Artifact) => void
  onPickExample: (prompt: string) => void
  onRegenerate: () => void
  onEdit: (messageId: string, text: string) => void
}

const EXAMPLES = [
  {
    label: 'Ask a question',
    prompt: 'What does Jen Abel say about getting the first enterprise meeting?',
  },
  {
    label: 'Write an essay',
    prompt: 'Write a Ship 30 essay about building talent density',
  },
  {
    label: 'Make a document',
    prompt: 'Create a markdown checklist for running a first enterprise sales call',
  },
]

export function MessageList({
  messages,
  isStreaming,
  onOpenArtifact,
  onPickExample,
  onRegenerate,
  onEdit,
}: Props) {
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
    if (pinnedToBottom.current) endRef.current?.scrollIntoView({ block: 'end' })
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="messages" ref={listRef}>
        <div className="empty-state">
          <div className="empty-mark" aria-hidden="true">
            LG
          </div>
          <h2>Ask about product and growth</h2>
          <p>
            Every answer is grounded in Lenny&apos;s Podcast transcripts and cites the
            episodes it drew from.
          </p>

          <div className="examples">
            {EXAMPLES.map((example) => (
              <button
                key={example.prompt}
                className="example-card"
                onClick={() => onPickExample(example.prompt)}
              >
                <span className="example-label">{example.label}</span>
                <span className="example-prompt">{example.prompt}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="messages" ref={listRef}>
      <div aria-live="polite" aria-atomic="false" className="sr-only">
        {isStreaming ? 'Assistant is replying' : 'Reply complete'}
      </div>

      <div className="messages-inner">
        {(() => {
          // Only the latest question is editable: editing an earlier one would
          // discard everything after it without warning.
          const lastUserIndex = messages.map((m) => m.role).lastIndexOf('user')
          return messages.map((message, index) => (
          <Message
            key={message.id}
            message={message}
            isStreaming={isStreaming && index === messages.length - 1}
            isLast={index === messages.length - 1}
            canEdit={index === lastUserIndex && !isStreaming}
            onOpenArtifact={onOpenArtifact}
            onRegenerate={onRegenerate}
            onEdit={(text) => onEdit(message.id, text)}
          />
          ))
        })()}
        <div ref={endRef} />
      </div>
    </div>
  )
}

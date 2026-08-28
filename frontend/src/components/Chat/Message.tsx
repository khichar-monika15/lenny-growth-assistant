import { useState } from 'react'
import type { Artifact, Message as MessageType } from '../../types'
import { MarkdownRenderer } from '../Artifacts/MarkdownRenderer'
import { SourceList } from './SourceList'

interface Props {
  message: MessageType
  isStreaming: boolean
  isLast: boolean
  onOpenArtifact: (artifact: Artifact) => void
  onRegenerate: () => void
}

const ICONS = {
  copy: (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
      <rect x="5.5" y="5.5" width="8" height="9" rx="1.6" stroke="currentColor" strokeWidth="1.3" />
      <path
        d="M10.5 3.5v-.4a1.6 1.6 0 0 0-1.6-1.6H3.1A1.6 1.6 0 0 0 1.5 3.1v5.8a1.6 1.6 0 0 0 1.6 1.6h.4"
        stroke="currentColor"
        strokeWidth="1.3"
      />
    </svg>
  ),
  check: (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
      <path d="m3 8.5 3.2 3.2L13 5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  ),
  retry: (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
      <path
        d="M13.5 8a5.5 5.5 0 1 1-1.7-3.97"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
      <path d="M13.6 1.9v3.2h-3.2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
}

/** Characters of a generated document shown inline before deferring to the viewer. */
const ARTIFACT_PREVIEW_CHARS = 240

/** Strip Markdown syntax down to readable prose. */
function toPlainText(markdown: string): string {
  return markdown
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/[*_`>]/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\s+/g, ' ')
    .trim()
}

function summarise(content: string): string {
  const text = toPlainText(content)
  if (text.length <= ARTIFACT_PREVIEW_CHARS) return text
  const cut = text.slice(0, ARTIFACT_PREVIEW_CHARS)
  return `${cut.slice(0, cut.lastIndexOf(' ')) || cut}…`
}

export function Message({
  message,
  isStreaming,
  isLast,
  onOpenArtifact,
  onRegenerate,
}: Props) {
  const [copied, setCopied] = useState(false)

  const isUser = message.role === 'user'
  const awaitingFirstToken = isStreaming && !message.content
  // A finished document belongs in the viewer, not repeated in full inline.
  const showSummaryOnly = Boolean(message.artifact) && !isStreaming

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message.content)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      setCopied(false)
    }
  }

  if (isUser) {
    return (
      <article className="message user">
        <div className="user-bubble">{message.content}</div>
      </article>
    )
  }

  return (
    <article className="message assistant">
      <div className="message-avatar" aria-hidden="true">
        LG
      </div>

      <div className="message-main">
        <div className="message-body">
          {awaitingFirstToken ? (
            <span className="thinking" aria-label="Thinking">
              <span />
              <span />
              <span />
            </span>
          ) : showSummaryOnly ? (
            <p className="artifact-summary">{summarise(message.content)}</p>
          ) : (
            // Markdown renders while streaming too, so bold, headings and
            // lists appear as they arrive rather than as raw asterisks.
            <div className={isStreaming ? 'streaming' : undefined}>
              <MarkdownRenderer content={message.content} />
            </div>
          )}
        </div>

        {message.error && (
          <p className="message-error" role="alert">
            {message.error}
          </p>
        )}

        {message.artifact && !isStreaming && (
          <button className="artifact-card" onClick={() => onOpenArtifact(message.artifact!)}>
            <span className="artifact-card-icon" aria-hidden="true">
              {message.artifact.type === 'html' ? '◧' : '¶'}
            </span>
            <span className="artifact-card-text">
              <span className="artifact-card-title">{message.artifact.title}</span>
              <span className="artifact-card-meta">
                {message.artifact.type === 'html' ? 'HTML document' : 'Markdown document'}
                {' · '}
                {toPlainText(message.artifact.content).split(' ').length.toLocaleString()} words
              </span>
            </span>
            <span className="artifact-card-action" aria-hidden="true">
              Open
            </span>
          </button>
        )}

        {message.sources && <SourceList sources={message.sources} />}

        {!isStreaming && message.content && (
          <div className="message-actions">
            <button
              className={`action-button ${copied ? 'confirmed' : ''}`}
              onClick={copy}
              aria-label={copied ? 'Copied to clipboard' : 'Copy reply'}
            >
              {copied ? ICONS.check : ICONS.copy}
              <span>{copied ? 'Copied' : 'Copy'}</span>
            </button>

            {isLast && (
              <button
                className="action-button"
                onClick={onRegenerate}
                aria-label="Regenerate this reply"
              >
                {ICONS.retry}
                <span>Regenerate</span>
              </button>
            )}
          </div>
        )}
      </div>
    </article>
  )
}

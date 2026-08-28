import { useCallback, useEffect, useRef, type KeyboardEvent } from 'react'

interface Props {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  onStop: () => void
  isStreaming: boolean
  disabled?: boolean
}

const LINE_HEIGHT = 24
const MAX_ROWS = 7

export function MessageInput({
  value,
  onChange,
  onSend,
  onStop,
  isStreaming,
  disabled,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const resize = useCallback(() => {
    const element = textareaRef.current
    if (!element) return

    // Collapse first, or scrollHeight keeps reporting the previous height and
    // the box can only ever grow.
    element.style.height = 'auto'
    const next = Math.min(element.scrollHeight, LINE_HEIGHT * MAX_ROWS)
    element.style.height = `${next}px`
    // Only scroll once the content genuinely exceeds the cap.
    element.style.overflowY = element.scrollHeight > next ? 'auto' : 'hidden'
  }, [])

  // Recompute whenever the text changes, including when sending clears it.
  useEffect(resize, [resize, value])

  // Narrowing the pane rewraps the text onto more lines. Without this the
  // height stays put and the field scrolls instead of growing.
  useEffect(() => {
    const element = textareaRef.current
    if (!element || typeof ResizeObserver === 'undefined') return

    const observer = new ResizeObserver(resize)
    observer.observe(element)
    return () => observer.disconnect()
  }, [resize])

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift+Enter inserts a newline.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onSend()
    }
  }

  return (
    <div className="input-area">
      <div className="input-inner">
        <label className="sr-only" htmlFor="chat-input">
          Ask a question about product and growth
        </label>

        <textarea
          id="chat-input"
          ref={textareaRef}
          rows={1}
          value={value}
          placeholder="Ask about product-market fit, growth, hiring…"
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
        />

        {isStreaming ? (
          <button className="send-button stop" onClick={onStop}>
            Stop
          </button>
        ) : (
          <button
            className="send-button"
            onClick={onSend}
            disabled={disabled || !value.trim()}
            aria-label="Send message"
          >
            Send
          </button>
        )}
      </div>

      <p className="input-footnote">
        Answers are grounded in Lenny&apos;s Podcast transcripts. Enter to send,
        Shift+Enter for a new line.
      </p>
    </div>
  )
}

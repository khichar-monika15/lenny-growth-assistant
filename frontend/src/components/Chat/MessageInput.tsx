import { useEffect, useRef, type KeyboardEvent } from 'react'

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

  // Sending clears the value but not the inline height set while typing, so a
  // multi-line message left the composer stretched and empty.
  useEffect(() => {
    const element = textareaRef.current
    if (element && value === '') element.style.height = 'auto'
  }, [value])

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift+Enter inserts a newline.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onSend()
    }
  }

  const autoGrow = (element: HTMLTextAreaElement) => {
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, LINE_HEIGHT * MAX_ROWS)}px`
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
          onChange={(event) => {
            onChange(event.target.value)
            autoGrow(event.target)
          }}
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

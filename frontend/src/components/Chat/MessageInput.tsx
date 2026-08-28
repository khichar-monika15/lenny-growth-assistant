import { useRef, type KeyboardEvent } from 'react'

interface Props {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  onStop: () => void
  isStreaming: boolean
  disabled?: boolean
}

const MAX_ROWS = 6

export function MessageInput({
  value,
  onChange,
  onSend,
  onStop,
  isStreaming,
  disabled,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift+Enter inserts a newline.
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      onSend()
    }
  }

  const autoGrow = (element: HTMLTextAreaElement) => {
    element.style.height = 'auto'
    const lineHeight = 24
    element.style.height = `${Math.min(element.scrollHeight, lineHeight * MAX_ROWS)}px`
  }

  return (
    <div className="input-area">
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
        >
          Send
        </button>
      )}
    </div>
  )
}

import { useEffect, useRef, useState, type KeyboardEvent } from 'react'

interface Props {
  content: string
  canEdit: boolean
  onEdit: (text: string) => void
}

/**
 * A user turn, editable in place.
 *
 * Editing supersedes the reply below it rather than appending a new turn,
 * which is how current chat assistants behave.
 */
export function UserMessage({ content, canEdit, onEdit }: Props) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(content)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (!editing) return
    const element = textareaRef.current
    if (!element) return

    element.focus()
    element.setSelectionRange(element.value.length, element.value.length)
    element.style.height = 'auto'
    element.style.height = `${element.scrollHeight}px`
  }, [editing])

  const cancel = () => {
    setDraft(content)
    setEditing(false)
  }

  const submit = () => {
    const text = draft.trim()
    if (!text || text === content) {
      cancel()
      return
    }
    setEditing(false)
    onEdit(text)
  }

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      cancel()
    }
  }

  if (editing) {
    return (
      <article className="message user editing">
        <div className="user-edit">
          <label className="sr-only" htmlFor="edit-message">
            Edit your message
          </label>
          <textarea
            id="edit-message"
            ref={textareaRef}
            value={draft}
            onChange={(event) => {
              setDraft(event.target.value)
              event.target.style.height = 'auto'
              event.target.style.height = `${event.target.scrollHeight}px`
            }}
            onKeyDown={onKeyDown}
          />
          <div className="user-edit-actions">
            <button className="edit-cancel" onClick={cancel}>
              Cancel
            </button>
            <button className="edit-save" onClick={submit} disabled={!draft.trim()}>
              Send
            </button>
          </div>
        </div>
      </article>
    )
  }

  return (
    <article className="message user">
      <div className="user-turn">
        {canEdit && (
          <button
            className="edit-button"
            onClick={() => {
              setDraft(content)
              setEditing(true)
            }}
            aria-label="Edit this message"
            title="Edit message"
          >
            <svg viewBox="0 0 16 16" width="14" height="14" fill="none" aria-hidden="true">
              <path
                d="M11.2 2.3a1.6 1.6 0 0 1 2.3 2.3L5.6 12.5l-3 .7.7-3 7.9-7.9Z"
                stroke="currentColor"
                strokeWidth="1.3"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        )}
        <div className="user-bubble">{content}</div>
      </div>
    </article>
  )
}

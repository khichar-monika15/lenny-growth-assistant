import type { RetrievalHealth, SessionSummary } from '../../types'

interface Props {
  sessions: SessionSummary[]
  activeSessionId: string | null
  retrieval: RetrievalHealth | null
  onNewChat: () => void
  onSelect: (id: string) => void
  onDelete: (id: string) => void
}

function relativeTime(iso: string): string {
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  return `${Math.round(hours / 24)}d ago`
}

export function SessionSidebar({
  sessions,
  activeSessionId,
  retrieval,
  onNewChat,
  onSelect,
  onDelete,
}: Props) {
  return (
    <nav className="sidebar" aria-label="Chat sessions">
      {/* Pinned. Only the list between these scrolls. */}
      <div className="sidebar-head">
        <button className="new-chat" onClick={onNewChat}>
          <span aria-hidden="true">+</span> New chat
        </button>
      </div>

      <div className="sidebar-scroll">
        {sessions.length > 0 && <p className="sidebar-label">Recent</p>}

        <ul className="session-list">
          {sessions.length === 0 && (
            <li className="session-empty">No conversations yet</li>
          )}

          {sessions.map((session) => (
            <li key={session.id} className={session.id === activeSessionId ? 'active' : ''}>
              <button
                className="session-open"
                onClick={() => onSelect(session.id)}
                aria-current={session.id === activeSessionId ? 'page' : undefined}
              >
                <span className="session-title">{session.title || 'New chat'}</span>
                <span className="session-time">{relativeTime(session.updated_at)}</span>
              </button>
              <button
                className="session-delete"
                onClick={() => onDelete(session.id)}
                aria-label={`Delete ${session.title || 'chat'}`}
                title="Delete"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </div>

      {retrieval && (
        <div className="index-status">
          {retrieval.chromadb === 'available' ? (
            <>
              <span className="index-dot ready" aria-hidden="true" />
              <span>
                <strong>{retrieval.indexed_chunks.toLocaleString()}</strong> chunks indexed
              </span>
            </>
          ) : (
            <>
              <span className="index-dot offline" aria-hidden="true" />
              <span className="warning">Transcript index unavailable</span>
            </>
          )}
        </div>
      )}
    </nav>
  )
}

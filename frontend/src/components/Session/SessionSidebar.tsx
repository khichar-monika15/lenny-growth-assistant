import type { RetrievalHealth, SessionSummary } from '../../types'

interface Props {
  sessions: SessionSummary[]
  activeSessionId: string | null
  retrieval: RetrievalHealth | null
  onNewChat: () => void
  onSelect: (id: string) => void
  onDelete: (id: string) => void
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
      <button className="new-chat" onClick={onNewChat}>
        + New chat
      </button>

      <ul className="session-list">
        {sessions.length === 0 && <li className="session-empty">No conversations yet</li>}

        {sessions.map((session) => (
          <li key={session.id} className={session.id === activeSessionId ? 'active' : ''}>
            <button
              className="session-open"
              onClick={() => onSelect(session.id)}
              aria-current={session.id === activeSessionId ? 'page' : undefined}
            >
              {session.title || 'New chat'}
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

      {retrieval && (
        <div className="index-status">
          {retrieval.chromadb === 'available' ? (
            <>
              <strong>{retrieval.indexed_chunks.toLocaleString()}</strong> transcript chunks
              indexed
            </>
          ) : (
            <span className="warning">Transcript index unavailable</span>
          )}
          {retrieval.hint && <p className="index-hint">{retrieval.hint}</p>}
        </div>
      )}
    </nav>
  )
}

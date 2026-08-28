import { useState } from 'react'
import type { Source } from '../../types'

interface Props {
  sources: Source[]
}

/** Citations for an answer, collapsed by default so they never bury the reply. */
export function SourceList({ sources }: Props) {
  const [expanded, setExpanded] = useState(false)

  if (sources.length === 0) return null

  return (
    <div className="sources">
      <button
        className="sources-toggle"
        onClick={() => setExpanded((open) => !open)}
        aria-expanded={expanded}
      >
        {sources.length} source{sources.length === 1 ? '' : 's'}
        <span aria-hidden="true">{expanded ? ' ▾' : ' ▸'}</span>
      </button>

      {expanded && (
        <ul className="source-list">
          {sources.map((source) => (
            <li key={source.chunk_id} className="source-item">
              <span className="source-index" aria-hidden="true">
                {source.index}
              </span>
              <span className="source-body">
                {source.source_url ? (
                  <a href={source.source_url} target="_blank" rel="noopener noreferrer">
                    {source.transcript_title}
                  </a>
                ) : (
                  <span>{source.transcript_title}</span>
                )}
                <span className="source-meta">
                  {source.guests.length > 0 && <>{source.guests.join(', ')} · </>}
                  {source.transcript_date && <>{source.transcript_date} · </>}
                  <span title="Cosine similarity to your question">
                    {Math.round(source.similarity_score * 100)}% match
                  </span>
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

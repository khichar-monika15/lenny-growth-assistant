import { useMemo } from 'react'
import { buildFrameDocument, sanitizeHtml } from './sanitize'

interface Props {
  html: string
  theme: 'light' | 'dark'
}

/**
 * Renders untrusted HTML inside a locked-down iframe.
 *
 * `sandbox=""` is deliberately empty: every capability is opt-in, so scripting,
 * forms, popups, pointer lock and top-level navigation are all disabled, and
 * the frame gets an opaque origin with no access to this page.
 */
export function SandboxedHtml({ html, theme }: Props) {
  const { document, removed } = useMemo(() => {
    const result = sanitizeHtml(html)
    return { document: buildFrameDocument(result.html, theme), removed: result.removed }
  }, [html, theme])

  return (
    <div className="sandboxed-html">
      {removed.length > 0 && (
        <p className="sandbox-notice" role="status">
          <strong>Blocked for safety:</strong> {removed.join(', ')}. The viewer renders
          layout and styling only.
        </p>
      )}
      <iframe
        className="artifact-frame"
        title="Rendered HTML artifact"
        sandbox=""
        srcDoc={document}
        referrerPolicy="no-referrer"
      />
    </div>
  )
}

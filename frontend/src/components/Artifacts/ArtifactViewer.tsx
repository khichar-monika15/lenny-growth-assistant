import { useState } from 'react'
import type { Artifact } from '../../types'
import { MarkdownRenderer } from './MarkdownRenderer'
import { SandboxedHtml } from './SandboxedHtml'

interface Props {
  artifact: Artifact
  theme: 'light' | 'dark'
  onClose: () => void
}

type Tab = 'preview' | 'source'

/** Side panel that renders a generated document beside the conversation. */
export function ArtifactViewer({ artifact, theme, onClose }: Props) {
  const [tab, setTab] = useState<Tab>('preview')
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(artifact.content)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  const download = () => {
    const extension = artifact.type === 'html' ? 'html' : 'md'
    const blob = new Blob([artifact.content], {
      type: artifact.type === 'html' ? 'text/html' : 'text/markdown',
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${slugify(artifact.title)}.${extension}`
    // Firefox ignores a click on an anchor that is not in the document, and
    // the URL must outlive the click before it is revoked.
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
  }

  return (
    <aside className="artifact-viewer" aria-label="Artifact viewer">
      <header className="artifact-header">
        <div className="artifact-title-group">
          <span className="artifact-badge">{artifact.type}</span>
          <h2 className="artifact-title" title={artifact.title}>
            {artifact.title}
          </h2>
        </div>

        <div className="artifact-actions">
          <div className="artifact-tabs" role="tablist" aria-label="Artifact view mode">
            <button
              role="tab"
              aria-selected={tab === 'preview'}
              className={tab === 'preview' ? 'active' : ''}
              onClick={() => setTab('preview')}
            >
              Preview
            </button>
            <button
              role="tab"
              aria-selected={tab === 'source'}
              className={tab === 'source' ? 'active' : ''}
              onClick={() => setTab('source')}
            >
              Source
            </button>
          </div>

          <button className="icon-button" onClick={copy} aria-label="Copy artifact to clipboard">
            {copied ? 'Copied' : 'Copy'}
          </button>
          <button className="icon-button" onClick={download} aria-label="Download artifact">
            Download
          </button>
          <button className="icon-button" onClick={onClose} aria-label="Close artifact viewer">
            Close
          </button>
        </div>
      </header>

      <div className="artifact-body" role="tabpanel" tabIndex={0}>
        {tab === 'source' ? (
          <pre className="artifact-source">
            <code>{artifact.content}</code>
          </pre>
        ) : artifact.type === 'html' ? (
          <SandboxedHtml html={artifact.content} theme={theme} />
        ) : (
          <MarkdownRenderer content={artifact.content} />
        )}
      </div>
    </aside>
  )
}

function slugify(value: string): string {
  return (
    value
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60) || 'artifact'
  )
}

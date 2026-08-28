import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { ArtifactViewer } from './components/Artifacts/ArtifactViewer'
import { MessageInput } from './components/Chat/MessageInput'
import { MessageList } from './components/Chat/MessageList'
import { ModelSelector } from './components/ModelToggle/ModelSelector'
import { SessionSidebar } from './components/Session/SessionSidebar'
import { ThemeToggle } from './components/ThemeToggle'
import { usePaneWidth } from './hooks/usePaneWidth'
import { useChat } from './hooks/useChat'
import { useTheme } from './hooks/useTheme'
import { api } from './services/api'
import type { ModelProvider, ProviderHealth, RetrievalHealth, SessionSummary } from './types'

export default function App() {
  const {
    messages,
    sessionId,
    isStreaming,
    activeArtifact,
    setActiveArtifact,
    send,
    stop,
    regenerate,
    editMessage,
    startNewChat,
    loadSession,
  } = useChat()

  const [input, setInput] = useState('')
  const [provider, setProvider] = useState<ModelProvider>('ollama')
  const [providerHealth, setProviderHealth] = useState<ProviderHealth | null>(null)
  const [retrieval, setRetrieval] = useState<RetrievalHealth | null>(null)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const theme = useTheme()

  const sidebar = usePaneWidth({
    edge: 'right',
    min: 200,
    max: 460,
    initial: 264,
    storageKey: 'lenny.sidebarWidth',
  })
  const artifact = usePaneWidth({
    edge: 'left',
    min: 340,
    max: 900,
    initial: 480,
    storageKey: 'lenny.artifactWidth',
  })

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await api.listSessions())
    } catch {
      // The sidebar is not worth an error banner; the chat still works.
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    const loadHealth = async () => {
      const [health, index] = await Promise.allSettled([
        api.providerHealth(),
        api.retrievalHealth(),
      ])
      if (cancelled) return

      if (health.status === 'fulfilled') {
        setProviderHealth(health.value)
        setProvider(health.value.default)
      }
      if (index.status === 'fulfilled') setRetrieval(index.value)
    }

    loadHealth()
    refreshSessions()
    return () => {
      cancelled = true
    }
  }, [refreshSessions])

  // A finished turn may have created the session or renamed it.
  useEffect(() => {
    if (!isStreaming) refreshSessions()
  }, [isStreaming, refreshSessions])

  const handleSend = async () => {
    const text = input.trim()
    // Only clear once we know there is something to send, otherwise a stray
    // whitespace-only send wipes what the user typed.
    if (!text || isStreaming) return
    setInput('')
    await send(text, provider)
  }

  const handleExample = async (prompt: string) => {
    setInput('')
    await send(prompt, provider)
  }

  // Escape closes whichever overlay is open, artifact panel first.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (activeArtifact) setActiveArtifact(null)
      else if (sidebarOpen) setSidebarOpen(false)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [activeArtifact, setActiveArtifact, sidebarOpen])

  const handleSelectSession = async (id: string) => {
    setSidebarOpen(false)
    try {
      await loadSession(id)
    } catch {
      await refreshSessions()
    }
  }

  const handleDeleteSession = async (id: string) => {
    await api.deleteSession(id).catch(() => undefined)
    if (id === sessionId) startNewChat()
    await refreshSessions()
  }

  return (
    <div
      className={`app ${activeArtifact ? 'with-artifact' : ''} ${
        sidebar.isDragging || artifact.isDragging ? 'resizing' : ''
      }`}
      style={
        {
          '--sidebar-width': `${sidebar.width}px`,
          '--artifact-width': `${artifact.width}px`,
        } as React.CSSProperties
      }
    >
      <header className="header">
        <button
          className="sidebar-toggle"
          onClick={() => setSidebarOpen((open) => !open)}
          aria-expanded={sidebarOpen}
          aria-label="Toggle chat history"
        >
          ☰
        </button>

        <div className="header-title">
          <span className="header-mark" aria-hidden="true">
            LG
          </span>
          <span className="header-text">
            <h1>Lenny Growth Assistant</h1>
            <p>Grounded in Lenny&apos;s Podcast transcripts</p>
          </span>
        </div>

        <ThemeToggle preference={theme.preference} onCycle={theme.cycle} />

        <ModelSelector
          value={provider}
          health={providerHealth}
          onChange={setProvider}
          disabled={isStreaming}
        />
      </header>

      <div className="layout">
        {sidebarOpen && (
          <button
            className="sidebar-backdrop"
            aria-label="Close chat history"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        <div className={`sidebar-wrapper ${sidebarOpen ? 'open' : ''}`}>
          <SessionSidebar
            sessions={sessions}
            activeSessionId={sessionId}
            retrieval={retrieval}
            onNewChat={() => {
              setSidebarOpen(false)
              startNewChat()
            }}
            onSelect={handleSelectSession}
            onDelete={handleDeleteSession}
          />
        </div>

        <div {...sidebar.handleProps} />

        <main className="chat-container">
          <MessageList
            messages={messages}
            isStreaming={isStreaming}
            onOpenArtifact={setActiveArtifact}
            onPickExample={handleExample}
            onRegenerate={() => regenerate(provider)}
            onEdit={(id, text) => editMessage(id, text, provider)}
          />
          <MessageInput
            value={input}
            onChange={setInput}
            onSend={handleSend}
            onStop={stop}
            isStreaming={isStreaming}
          />
        </main>

        {activeArtifact && (
          <>
            <div {...artifact.handleProps} />
            <ArtifactViewer
              artifact={activeArtifact}
              theme={theme.resolved}
              onClose={() => setActiveArtifact(null)}
            />
          </>
        )}
      </div>
    </div>
  )
}

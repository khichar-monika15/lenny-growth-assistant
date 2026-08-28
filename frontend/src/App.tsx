import { useCallback, useEffect, useState } from 'react'
import './App.css'
import { ArtifactViewer } from './components/Artifacts/ArtifactViewer'
import { MessageInput } from './components/Chat/MessageInput'
import { MessageList } from './components/Chat/MessageList'
import { ModelSelector } from './components/ModelToggle/ModelSelector'
import { SessionSidebar } from './components/Session/SessionSidebar'
import { useChat } from './hooks/useChat'
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
    startNewChat,
    loadSession,
  } = useChat()

  const [input, setInput] = useState('')
  const [provider, setProvider] = useState<ModelProvider>('ollama')
  const [providerHealth, setProviderHealth] = useState<ProviderHealth | null>(null)
  const [retrieval, setRetrieval] = useState<RetrievalHealth | null>(null)
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(false)

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
    const text = input
    setInput('')
    await send(text, provider)
  }

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
    <div className={`app ${activeArtifact ? 'with-artifact' : ''}`}>
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
          <h1>Lenny Growth Assistant</h1>
          <p>Grounded in Lenny&apos;s Podcast transcripts</p>
        </div>

        <ModelSelector
          value={provider}
          health={providerHealth}
          onChange={setProvider}
          disabled={isStreaming}
        />
      </header>

      <div className="layout">
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

        <main className="chat-container">
          <MessageList
            messages={messages}
            isStreaming={isStreaming}
            onOpenArtifact={setActiveArtifact}
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
          <ArtifactViewer artifact={activeArtifact} onClose={() => setActiveArtifact(null)} />
        )}
      </div>
    </div>
  )
}

import { useState } from 'react'
import './App.css'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: any[]
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)

  const sendMessage = async () => {
    if (!input.trim() || isStreaming) return

    const userMessage: Message = { role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsStreaming(true)

    // Start with empty assistant message
    const assistantMessage: Message = { role: 'assistant', content: '', sources: [] }
    setMessages(prev => [...prev, assistantMessage])

    try {
      const response = await fetch('http://localhost:8080/api/v1/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: input })
      })

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.substring(6)
            if (data === '[DONE]') {
              setIsStreaming(false)
              break
            }

            try {
              const parsed = JSON.parse(data)

              if (parsed.type === 'content_delta') {
                setMessages(prev => {
                  const updated = [...prev]
                  updated[updated.length - 1].content += parsed.delta
                  return updated
                })
              } else if (parsed.type === 'sources') {
                setMessages(prev => {
                  const updated = [...prev]
                  updated[updated.length - 1].sources = parsed.sources
                  return updated
                })
              }
            } catch (e) {
              // Ignore parse errors
            }
          }
        }
      }
    } catch (error) {
      console.error('Error:', error)
      setIsStreaming(false)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1>🎯 Lenny Growth Assistant</h1>
        <p>Ask questions about product and growth from Lenny's Podcast</p>
      </header>

      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <div className="message-content">
                {msg.content || (msg.role === 'assistant' && isStreaming ? '▊' : '')}
              </div>
              {msg.sources && msg.sources.length > 0 && (
                <div className="sources">
                  <strong>Sources:</strong>
                  {msg.sources.map((source, j) => (
                    <span key={j} className="source-badge">
                      {source.transcript_title}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="input-area">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            placeholder="Ask about product-market fit, growth, etc..."
            disabled={isStreaming}
          />
          <button onClick={sendMessage} disabled={isStreaming || !input.trim()}>
            {isStreaming ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default App

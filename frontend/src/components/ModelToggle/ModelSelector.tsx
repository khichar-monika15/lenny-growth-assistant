import type { ModelProvider, ProviderHealth } from '../../types'

interface Props {
  value: ModelProvider
  health: ProviderHealth | null
  onChange: (provider: ModelProvider) => void
  disabled?: boolean
}

type Status = 'ready' | 'degraded' | 'offline' | 'unknown'

function statusOf(provider: ModelProvider, health: ProviderHealth | null): Status {
  if (!health) return 'unknown'
  if (provider === 'ollama') {
    if (health.ollama.status === 'available') return 'ready'
    if (health.ollama.status === 'model_missing') return 'degraded'
    return 'offline'
  }
  return health.anthropic.status === 'configured' ? 'ready' : 'offline'
}

const LABELS: Record<Status, string> = {
  ready: 'Ready',
  degraded: 'Model not pulled',
  offline: 'Unavailable',
  unknown: 'Checking…',
}

/**
 * Provider toggle.
 *
 * An unavailable provider stays selectable: the backend falls back to the
 * local model and reports why, which is more useful than a dead control that
 * gives no explanation.
 */
export function ModelSelector({ value, health, onChange, disabled }: Props) {
  const providers: { id: ModelProvider; name: string; kind: string; model: string }[] = [
    {
      id: 'ollama',
      name: 'Ollama',
      kind: 'Local',
      model: health?.ollama.model ?? 'llama3.1:8b',
    },
    {
      id: 'claude',
      name: 'Claude',
      kind: 'Cloud',
      model: health?.anthropic.model ?? 'claude',
    },
  ]

  const hint =
    statusOf('ollama', health) === 'degraded'
      ? health?.ollama.hint
      : statusOf(value, health) === 'offline' && value === 'claude'
        ? 'No ANTHROPIC_API_KEY set. Requests fall back to the local model.'
        : null

  return (
    <div className="model-selector">
      <div className="model-options" role="radiogroup" aria-label="Model provider">
        {providers.map((provider) => {
          const status = statusOf(provider.id, health)
          const selected = value === provider.id

          return (
            <button
              key={provider.id}
              role="radio"
              aria-checked={selected}
              disabled={disabled}
              className={`model-option ${selected ? 'selected' : ''}`}
              onClick={() => onChange(provider.id)}
              title={`${provider.model} — ${LABELS[status]}`}
            >
              <span className={`status-dot ${status}`} aria-hidden="true" />
              <span className="model-kind">{provider.kind}</span>
              <span className="model-name">{provider.name}</span>
            </button>
          )
        })}
      </div>

      {hint && <p className="model-hint">{hint}</p>}
    </div>
  )
}

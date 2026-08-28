import type { ThemePreference } from '../hooks/useTheme'

interface Props {
  preference: ThemePreference
  onCycle: () => void
}

const ICONS: Record<ThemePreference, JSX.Element> = {
  light: (
    <svg viewBox="0 0 20 20" width="16" height="16" fill="none" aria-hidden="true">
      <circle cx="10" cy="10" r="3.6" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M10 2.2v1.6M10 16.2v1.6M17.8 10h-1.6M3.8 10H2.2M15.5 4.5l-1.1 1.1M5.6 14.4l-1.1 1.1M15.5 15.5l-1.1-1.1M5.6 5.6 4.5 4.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  ),
  dark: (
    <svg viewBox="0 0 20 20" width="16" height="16" fill="none" aria-hidden="true">
      <path
        d="M16.5 12.4A7 7 0 0 1 7.6 3.5a7 7 0 1 0 8.9 8.9Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  ),
  system: (
    <svg viewBox="0 0 20 20" width="16" height="16" fill="none" aria-hidden="true">
      <rect x="2.5" y="3.5" width="15" height="10" rx="1.6" stroke="currentColor" strokeWidth="1.5" />
      <path d="M7 16.5h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
}

const LABELS: Record<ThemePreference, string> = {
  light: 'Light',
  dark: 'Dark',
  system: 'System',
}

/** Cycles light, dark, system. One control rather than three. */
export function ThemeToggle({ preference, onCycle }: Props) {
  return (
    <button
      className="theme-toggle"
      onClick={onCycle}
      title={`Theme: ${LABELS[preference]}. Click to change.`}
      aria-label={`Theme: ${LABELS[preference]}. Click to change.`}
    >
      {ICONS[preference]}
    </button>
  )
}

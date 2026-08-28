/**
 * Theme preference: light, dark, or follow the operating system.
 *
 * The choice is written to `data-theme` on the root element so CSS can resolve
 * it without a React render, and persisted so a reload does not flash the
 * wrong palette.
 */
import { useCallback, useEffect, useState } from 'react'

export type ThemePreference = 'light' | 'dark' | 'system'
export type ResolvedTheme = 'light' | 'dark'

const STORAGE_KEY = 'lenny.theme'
const ORDER: ThemePreference[] = ['light', 'dark', 'system']

function readStored(): ThemePreference {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return raw === 'light' || raw === 'dark' || raw === 'system' ? raw : 'system'
  } catch {
    return 'system'
  }
}

function systemPrefersDark(): boolean {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

export function useTheme() {
  const [preference, setPreference] = useState<ThemePreference>(readStored)
  const [systemDark, setSystemDark] = useState(systemPrefersDark)

  // Track the OS setting so "system" stays live rather than sampled once.
  useEffect(() => {
    const query = window.matchMedia?.('(prefers-color-scheme: dark)')
    if (!query) return

    const onChange = (event: MediaQueryListEvent) => setSystemDark(event.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  const resolved: ResolvedTheme =
    preference === 'system' ? (systemDark ? 'dark' : 'light') : preference

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', resolved)
    // Lets form controls and scrollbars render in the matching palette.
    document.documentElement.style.colorScheme = resolved

    try {
      window.localStorage.setItem(STORAGE_KEY, preference)
    } catch {
      // Blocked storage just means the choice is not remembered.
    }
  }, [preference, resolved])

  const cycle = useCallback(() => {
    setPreference((current) => ORDER[(ORDER.indexOf(current) + 1) % ORDER.length])
  }, [])

  return { preference, resolved, setPreference, cycle }
}

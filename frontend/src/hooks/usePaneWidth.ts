/**
 * Drag-to-resize pane widths, remembered between visits.
 *
 * Uses pointer capture rather than window listeners so a fast drag cannot
 * outrun the handle and drop the gesture mid-way.
 */
import { useCallback, useEffect, useState } from 'react'

export type ResizeEdge = 'left' | 'right'

interface Options {
  /** Which side of the pane the handle sits on. */
  edge: ResizeEdge
  min: number
  max: number
  initial: number
  storageKey: string
}

function readStored(key: string, fallback: number, min: number, max: number): number {
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return fallback
    const value = Number.parseInt(raw, 10)
    return Number.isFinite(value) ? Math.min(max, Math.max(min, value)) : fallback
  } catch {
    return fallback
  }
}

export function usePaneWidth({ edge, min, max, initial, storageKey }: Options) {
  const [width, setWidth] = useState(() => readStored(storageKey, initial, min, max))
  const [isDragging, setIsDragging] = useState(false)

  useEffect(() => {
    try {
      window.localStorage.setItem(storageKey, String(width))
    } catch {
      // Private browsing or blocked storage: the width is simply not remembered.
    }
  }, [storageKey, width])

  // Keep panes usable if the viewport shrinks below a stored width.
  useEffect(() => {
    const clamp = () => {
      const ceiling = Math.max(min, Math.min(max, Math.round(window.innerWidth * 0.55)))
      setWidth((current) => Math.min(current, ceiling))
    }
    window.addEventListener('resize', clamp)
    return () => window.removeEventListener('resize', clamp)
  }, [max, min])

  const onPointerDown = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      event.preventDefault()
      const handle = event.currentTarget
      handle.setPointerCapture(event.pointerId)

      const startX = event.clientX
      const startWidth = width
      setIsDragging(true)

      const onMove = (move: PointerEvent) => {
        const delta = edge === 'left' ? startX - move.clientX : move.clientX - startX
        setWidth(Math.min(max, Math.max(min, startWidth + delta)))
      }

      const onUp = () => {
        setIsDragging(false)
        handle.removeEventListener('pointermove', onMove)
        handle.removeEventListener('pointerup', onUp)
        handle.removeEventListener('pointercancel', onUp)
      }

      handle.addEventListener('pointermove', onMove)
      handle.addEventListener('pointerup', onUp)
      handle.addEventListener('pointercancel', onUp)
    },
    [edge, max, min, width],
  )

  /** Keyboard resizing, so the handle is not mouse only. */
  const onKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLDivElement>) => {
      const step = event.shiftKey ? 48 : 16
      const grow = edge === 'left' ? 'ArrowLeft' : 'ArrowRight'

      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault()
        const direction = event.key === grow ? 1 : -1
        setWidth((w) => Math.min(max, Math.max(min, w + direction * step)))
      } else if (event.key === 'Home') {
        event.preventDefault()
        setWidth(initial)
      }
    },
    [edge, initial, max, min],
  )

  const handleProps = {
    role: 'separator' as const,
    'aria-orientation': 'vertical' as const,
    'aria-valuenow': width,
    'aria-valuemin': min,
    'aria-valuemax': max,
    'aria-label': edge === 'left' ? 'Resize artifact panel' : 'Resize sidebar',
    tabIndex: 0,
    className: `resize-handle ${isDragging ? 'dragging' : ''}`,
    onPointerDown,
    onKeyDown,
    onDoubleClick: () => setWidth(initial),
  }

  return { width, isDragging, handleProps }
}

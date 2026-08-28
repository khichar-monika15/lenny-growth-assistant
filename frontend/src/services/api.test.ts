/**
 * SSE framing tests.
 *
 * The old client parsed each network chunk in isolation, so a `data:` line
 * split across two reads was dropped silently and text went missing. These
 * tests pin the buffering behaviour.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from './api'
import type { StreamEvent } from '../types'

function streamOf(chunks: string[]): Response {
  const encoder = new TextEncoder()
  let index = 0

  return {
    ok: true,
    status: 200,
    body: {
      getReader: () => ({
        read: async () =>
          index < chunks.length
            ? { done: false, value: encoder.encode(chunks[index++]) }
            : { done: true, value: undefined },
        releaseLock: () => undefined,
      }),
    },
  } as unknown as Response
}

async function collect(chunks: string[]): Promise<StreamEvent[]> {
  const events: StreamEvent[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(streamOf(chunks)),
  )

  await api.streamChat({ message: 'hi', onEvent: (event) => events.push(event) })
  return events
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('streamChat SSE parsing', () => {
  it('parses events delivered one per chunk', async () => {
    const events = await collect([
      'data: {"type":"content_delta","delta":"Hello"}\n\n',
      'data: {"type":"content_delta","delta":" world"}\n\n',
      'data: [DONE]\n\n',
    ])

    expect(events).toEqual([
      { type: 'content_delta', delta: 'Hello' },
      { type: 'content_delta', delta: ' world' },
    ])
  })

  it('reassembles an event split across chunk boundaries', async () => {
    const events = await collect([
      'data: {"type":"content_',
      'delta","delta":"split"}\n\n',
      'data: [DONE]\n\n',
    ])

    expect(events).toEqual([{ type: 'content_delta', delta: 'split' }])
  })

  it('handles several events arriving in one chunk', async () => {
    const events = await collect([
      'data: {"type":"content_delta","delta":"a"}\n\ndata: {"type":"content_delta","delta":"b"}\n\n',
    ])

    expect(events.map((e) => (e as { delta: string }).delta)).toEqual(['a', 'b'])
  })

  it('keeps multi-byte characters intact across a split', async () => {
    const encoder = new TextEncoder()
    const full = encoder.encode('data: {"type":"content_delta","delta":"café ☕"}\n\n')
    const events: StreamEvent[] = []
    let index = 0
    const parts = [full.slice(0, 42), full.slice(42)]

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        body: {
          getReader: () => ({
            read: async () =>
              index < parts.length
                ? { done: false, value: parts[index++] }
                : { done: true, value: undefined },
            releaseLock: () => undefined,
          }),
        },
      } as unknown as Response),
    )

    await api.streamChat({ message: 'hi', onEvent: (e) => events.push(e) })

    expect((events[0] as { delta: string }).delta).toBe('café ☕')
  })

  it('surfaces error events instead of swallowing them', async () => {
    const events = await collect([
      'data: {"type":"error","error":"model_unavailable","detail":"Ollama is down"}\n\n',
      'data: [DONE]\n\n',
    ])

    expect(events[0]).toMatchObject({ type: 'error', error: 'model_unavailable' })
  })

  it('skips unparseable payloads without aborting the stream', async () => {
    const events = await collect([
      'data: {not json}\n\n',
      'data: {"type":"content_delta","delta":"ok"}\n\n',
    ])

    expect(events).toEqual([{ type: 'content_delta', delta: 'ok' }])
  })
})

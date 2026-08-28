/**
 * Artifact sanitisation is the security boundary for untrusted model output,
 * so each attack shape it must neutralise is pinned by a test.
 */
import { describe, expect, it } from 'vitest'
import { FRAME_CSP, buildFrameDocument, sanitizeHtml } from './sanitize'

describe('sanitizeHtml', () => {
  it('strips script tags', () => {
    const { html } = sanitizeHtml('<p>Safe</p><script>alert("xss")</script>')

    expect(html).toContain('Safe')
    expect(html).not.toContain('<script')
    expect(html).not.toContain('alert')
  })

  it('strips inline event handlers', () => {
    const { html } = sanitizeHtml('<img src="x" onerror="alert(1)">')

    expect(html).not.toContain('onerror')
    expect(html).not.toContain('alert')
  })

  it('strips javascript: URLs', () => {
    const { html } = sanitizeHtml('<a href="javascript:alert(1)">click</a>')

    expect(html).not.toContain('javascript:')
  })

  it('strips nested iframes', () => {
    const { html } = sanitizeHtml('<iframe src="https://evil.test"></iframe>')

    expect(html).not.toContain('<iframe')
  })

  it('strips forms and inputs that could phish credentials', () => {
    const { html } = sanitizeHtml(
      '<form action="https://evil.test"><input name="password"></form>',
    )

    expect(html).not.toContain('<form')
    expect(html).not.toContain('<input')
  })

  it('strips remote stylesheet links', () => {
    const { html } = sanitizeHtml('<link rel="stylesheet" href="https://evil.test/x.css">')

    expect(html).not.toContain('<link')
  })

  it('keeps layout markup and inline styles', () => {
    const { html } = sanitizeHtml(
      '<style>.card{color:red}</style><div class="card"><h1>Title</h1><p>Body</p></div>',
    )

    expect(html).toContain('<h1>Title</h1>')
    expect(html).toContain('<p>Body</p>')
    expect(html).toContain('.card')
  })

  it('keeps tables intact', () => {
    const { html } = sanitizeHtml('<table><tr><th>A</th><td>1</td></tr></table>')

    expect(html).toContain('<table')
    expect(html).toContain('<th>A</th>')
  })

  it('reports what it removed so the viewer can say so', () => {
    const { removed } = sanitizeHtml('<script>x</script><img onerror="y">')

    expect(removed.length).toBeGreaterThan(0)
  })

  it('reports nothing removed for clean markup', () => {
    const { removed } = sanitizeHtml('<h1>Clean</h1><p>Nothing dangerous here</p>')

    expect(removed).toEqual([])
  })
})

describe('buildFrameDocument', () => {
  it('embeds a CSP that blocks all network access by default', () => {
    expect(FRAME_CSP).toContain("default-src 'none'")
    expect(buildFrameDocument('<p>hi</p>')).toContain(FRAME_CSP)
  })

  it('wraps content in a full document', () => {
    const doc = buildFrameDocument('<p>hi</p>')

    expect(doc.startsWith('<!doctype html>')).toBe(true)
    expect(doc).toContain('<p>hi</p>')
  })
})

describe('buildFrameDocument palette', () => {
  it('always renders the page light, whatever the app theme', () => {
    // Generated HTML assumes a light canvas. Theming the frame left the
    // model's own background winning while our text colour still applied,
    // producing light text on a light background.
    const doc = buildFrameDocument('<p>hi</p>')

    expect(doc).toContain('color-scheme: light')
    expect(doc).toContain('#ffffff')
    expect(doc).not.toContain('#1d1f23')
  })

  it('keeps its own defaults at zero specificity so model styles win cleanly', () => {
    const doc = buildFrameDocument('<p>hi</p>')

    expect(doc).toContain(':where(body)')
  })

  it('keeps the CSP', () => {
    expect(buildFrameDocument('<p>hi</p>')).toContain("default-src 'none'")
  })
})

describe('full HTML documents from the model', () => {
  const FULL_DOC = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Pricing</title>
<style>.tier{border:1px solid #ccc}</style>
</head>
<body>
<h1>Pricing tiers</h1>
<div class="tier"><h2>Starter</h2></div>
</body>
</html>`

  it('keeps the body content and the stylesheet', () => {
    const { html } = sanitizeHtml(FULL_DOC)

    expect(html).toContain('<h1>Pricing tiers</h1>')
    expect(html).toContain('.tier')
    expect(html).toContain('class="tier"')
  })

  it('drops head elements that would render as stray text', () => {
    const { html } = sanitizeHtml(FULL_DOC)

    expect(html).not.toContain('<title')
    expect(html).not.toContain('Pricing</title>')
    expect(html).not.toContain('<meta')
  })
})

describe('what the viewer reports as blocked', () => {
  it('stays quiet about routine head elements', () => {
    // A full document always carries these. Reporting them made harmless
    // cleanup read as a security incident.
    const { removed } = sanitizeHtml(
      '<!DOCTYPE html><html><head><meta charset="utf-8"><title>T</title></head><body><p>hi</p></body></html>',
    )

    expect(removed).toEqual([])
  })

  it('still reports anything dangerous', () => {
    const { removed } = sanitizeHtml('<script>x</script><form></form><img onerror="y">')

    expect(removed.join(' ')).toContain('script')
    expect(removed.join(' ')).toContain('form')
    expect(removed.join(' ')).toContain('onerror')
  })
})

/**
 * Sanitisation policy for generated HTML.
 *
 * Model output is untrusted input. It is never inserted into the app's own
 * DOM. Defence is layered so a bypass of any one layer is not sufficient:
 *
 *   1. DOMPurify strips scripts, event handlers and dangerous URL schemes.
 *   2. The result is rendered via `srcdoc` in an iframe with an empty
 *      `sandbox`, which gives it an opaque origin and disables scripting,
 *      forms, popups and top-level navigation.
 *   3. A CSP inside the document blocks every network fetch, so nothing can
 *      beacon out even if it somehow executed.
 *
 * Layers 2 and 3 hold even if layer 1 is bypassed, because an unsandboxed
 * script cannot run in a frame where scripting is disabled at all.
 */
import DOMPurify from 'dompurify'

/** Blocked outright: scripting, embedding, and anything that makes a request. */
const FORBIDDEN_TAGS = [
  'script',
  'iframe',
  'object',
  'embed',
  'link',
  'base',
  'form',
  'input',
  'button',
  'textarea',
  'meta',
  'applet',
  // Models emit a full document. Head elements survive into the sanitised
  // body, where <title> renders as stray text above the content.
  'title',
]

const FORBIDDEN_ATTR = ['srcdoc', 'formaction', 'ping', 'http-equiv']

export interface SanitizeResult {
  html: string
  removed: string[]
}

/**
 * Sanitise generated HTML and report what was stripped.
 *
 * The report is surfaced in the viewer so the behaviour is visible rather
 * than silent - a reviewer can see exactly what the viewer refused to render.
 */
export function sanitizeHtml(dirty: string): SanitizeResult {
  const removed = new Set<string>()

  const record = (node: Node | Element, name: string) => {
    const label = 'tagName' in node ? String(node.tagName).toLowerCase() : String(node.nodeName)
    removed.add(`${name}: ${label}`)
  }

  DOMPurify.addHook('uponSanitizeElement', (node, data) => {
    if (data.tagName && FORBIDDEN_TAGS.includes(data.tagName) && !data.allowedTags[data.tagName]) {
      record(node, 'element')
    }
  })

  DOMPurify.addHook('uponSanitizeAttribute', (_node, data) => {
    if (!data.allowedAttributes[data.attrName]) {
      if (data.attrName.startsWith('on')) {
        removed.add(`event handler: ${data.attrName}`)
      } else if (FORBIDDEN_ATTR.includes(data.attrName)) {
        removed.add(`attribute: ${data.attrName}`)
      }
    }
  })

  const html = DOMPurify.sanitize(dirty, {
    FORBID_TAGS: FORBIDDEN_TAGS,
    FORBID_ATTR: FORBIDDEN_ATTR,
    // <style> carries the layout the model was asked to produce and cannot
    // execute inside a scripting-disabled frame. FORCE_BODY is required with
    // it: the HTML parser otherwise hoists a leading <style> into <head>, and
    // DOMPurify returns only body content, silently dropping the CSS.
    ALLOW_DATA_ATTR: false,
    ADD_TAGS: ['style'],
    FORCE_BODY: true,
    WHOLE_DOCUMENT: false,
    RETURN_TRUSTED_TYPE: false,
  })

  DOMPurify.removeAllHooks()

  return { html, removed: [...removed] }
}

/** Content Security Policy for the sandboxed frame: render only, no network. */
export const FRAME_CSP =
  "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:;"

/**
 * Wrap sanitised HTML in a minimal, CSP-locked document for `srcdoc`.
 *
 * The frame is a separate document, so it inherits nothing from the app's
 * stylesheet and needs the palette passed in explicitly.
 */
export function buildFrameDocument(sanitized: string, theme: 'light' | 'dark' = 'light'): string {
  const dark = theme === 'dark'
  const palette = dark
    ? { bg: '#1d1f23', fg: '#eceef1', border: '#303439', sunken: '#26292e' }
    : { bg: '#ffffff', fg: '#1f2933', border: '#d8dee6', sunken: '#f5f7fa' }

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${FRAME_CSP}">
<style>
  :root { color-scheme: ${dark ? 'dark' : 'light'}; }
  body {
    margin: 0;
    padding: 20px;
    font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: ${palette.fg};
    background: ${palette.bg};
  }
  img, table { max-width: 100%; }
  table { border-collapse: collapse; }
  th, td { border: 1px solid ${palette.border}; padding: 6px 10px; text-align: left; }
  pre { overflow-x: auto; background: ${palette.sunken}; padding: 12px; border-radius: 6px; }
</style>
</head>
<body>${sanitized}</body>
</html>`
}

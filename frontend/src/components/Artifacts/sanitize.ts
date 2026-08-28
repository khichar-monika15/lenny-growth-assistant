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

/**
 * Removals worth telling the user about.
 *
 * Models emit a full HTML document, so <meta>, <title> and <base> are stripped
 * on almost every artifact. Reporting those made a routine, harmless cleanup
 * look like a security incident. Only genuinely dangerous removals are shown.
 */
const NOTABLE_REMOVALS = new Set([
  'script',
  'iframe',
  'object',
  'embed',
  'applet',
  'form',
  'input',
  'button',
  'textarea',
  'link',
])

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
    // Not gated on data.allowedTags: several of these (form, input, link) are
    // in DOMPurify's default allow list and only removed because FORBID_TAGS
    // overrides it, so that flag is still true here and hid them from the report.
    if (data.tagName && NOTABLE_REMOVALS.has(data.tagName)) {
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
 * The page always renders light, whatever the app theme.
 *
 * Generated HTML brings its own stylesheet and assumes a light canvas. Theming
 * the frame meant the model's `background-color: #f9f9f9` won the background
 * while our dark `color` still applied, leaving light text on a light
 * background. Partial overrides like that are the normal case, not the
 * exception, so the document is treated as a sheet of paper and the dark
 * surround is left to the panel around it.
 */
export function buildFrameDocument(sanitized: string): string {
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="${FRAME_CSP}">
<style>
  :root { color-scheme: light; }
  /* :where() keeps these at zero specificity, so any style the model supplies
     wins cleanly rather than partially. */
  :where(body) {
    margin: 0;
    padding: 24px;
    font: 15px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #1f2933;
    background: #ffffff;
  }
  :where(img, table) { max-width: 100%; }
  :where(table) { border-collapse: collapse; }
  :where(th, td) { border: 1px solid #d8dee6; padding: 6px 10px; text-align: left; }
  :where(pre) { overflow-x: auto; background: #f5f7fa; padding: 12px; border-radius: 6px; }
</style>
</head>
<body>${sanitized}</body>
</html>`
}

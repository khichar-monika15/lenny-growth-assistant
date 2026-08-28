# Design

UI and UX decisions for The Lenny Growth Assistant, and the reasoning behind
them.

---

## 1. Principles

**Citations are the product, not a footnote.** The assistant's whole claim is
that it answers from real transcripts. If a reader cannot tell a grounded answer
from an invented one, the product has failed at the thing it exists to do. So
sources are attached to the message that used them, always present when they
exist, and conspicuously absent when they are not.

**Never look confident about a failure.** A blank reply, a stalled spinner or a
plausible answer with no sources are all worse than a plain error. Every failure
path renders visibly and in the place it happened.

**Reading beats decorating.** The content is dense prose and long-form essays.
Line length, spacing and heading rhythm get the attention; there are no
gradients, shadows or brand flourishes competing with the text.

**Nothing to configure to get value.** No prompt box, no chunk size, no model
name required. The model toggle exists because the brief asks for it to be
visible, and it shows status rather than settings.

**Match the mental model people already have.** Sidebar of conversations, centre
thread, document panel on the right. Familiar from every tool this audience
already uses, so no learning cost.

---

## 2. Information architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  Lenny Growth Assistant                        ● Local  ○ Cloud    │  header
├──────────────┬─────────────────────────────┬───────────────────────┤
│ + New chat   │                             │  markdown  ▾          │
│              │   You                       │  Talent density       │
│ Enterprise…  │   What does Jen Abel say…   │  ┌─────────────────┐  │
│ Talent dens… │                             │  │ # Talent den…   │  │
│ Pricing tie… │   Assistant                 │  │                 │  │
│              │   Jen Abel argues that…     │  │ Preview | Source│  │
│              │   ▸ 3 sources               │  │                 │  │
│              │                             │  └─────────────────┘  │
│              │                             │                       │
│ 361 chunks   │  ┌───────────────────────┐  │  Copy  Download  ×    │
│ indexed      │  │ Ask about…      [Send]│  │                       │
└──────────────┴──┴───────────────────────┴──┴───────────────────────┘
   sidebar              conversation            artifact viewer
   250px                flexible                460px, on demand
```

**Three regions, one of which is conditional.**

The **sidebar** holds session history and, at its foot, the index status — the
indexed chunk count. That placement is deliberate: the single most likely
failure an evaluator hits is a running stack with an empty index, and this makes
it visible without opening a terminal.

The **conversation** is the centre and the default. Messages are capped at 760px
and centred, because a full-width line of prose at 1600px is unreadable.

The **artifact viewer** appears only when a document exists, and takes a fixed
460px so the conversation never collapses to a sliver. It is a peer of the chat,
not a modal over it — the brief asks for artifacts *beside* the chat, and a
modal would break the ability to keep talking while reading.

### Message anatomy

```
ASSISTANT                              ← role label, small caps, muted
┌──────────────────────────────────┐
│ Jen Abel argues the first        │  ← markdown rendered, not raw text
│ meeting is a group effort…       │
└──────────────────────────────────┘
  ▸ 3 sources                          ← collapsed by default
  [markdown] Talent density            ← artifact chip, when one exists
```

Assistant replies render as Markdown. The model produces headings, lists and
emphasis; showing that as literal `##` and `**` would waste the formatting the
Ship 30 skill works hard to produce.

Sources collapse by default. Expanded they show a numbered badge matching the
`[Source n]` markers in the prompt, the episode title as a link, the guest, the
date, and the match as a percentage:

```
▾ 3 sources
  ① How to close $100K+ enterprise deals
    Jen Abel · 2026-08-23 · 64% match
```

The percentage is shown because it is honest about confidence in a way prose
cannot be. A 30% match and a 90% match are different claims, and a reader
deciding whether to trust an answer deserves to see which they have.

---

## 3. Interaction states

Every state below is implemented, not aspirational.

### Empty

First load shows what the assistant is for and three example prompts covering
the three skills — a question, an essay, a document. This is the only routing
documentation a user gets, and it is enough: seeing "Write a Ship 30 essay
about…" teaches the pattern without explaining it.

### Thinking

Between send and first token, the assistant bubble shows three pulsing dots.
Local models can take several seconds before the first token, and an empty
bubble reads as broken.

### Streaming

Tokens append live. The send button becomes **Stop**, wired to an `AbortController`,
because a local model producing a 1,250-word essay is a long commitment to be
locked into.

Auto-scroll follows the stream **only while the user is already at the bottom**.
Scroll up to re-read an earlier passage and the view stays put. A chat that drags
you back down mid-sentence is actively hostile, and it is a common bug.

### Sources arriving

Sources arrive before the first token, since retrieval precedes generation, and
attach to the message immediately. The user can see what the answer will be based
on while it is still being written.

### Error

Errors render inside the message that failed, in a red-bordered block, carrying
the backend's `detail` and `hint`:

> The model took too long to respond. Local models are slow on first load. Retry,
> or raise `OLLAMA_TIMEOUT_SECONDS`.

Two rules. **The composer always re-enables** — the streaming flag is cleared in
a `finally`, so no failure can strand the UI in a permanently disabled state.
And **partial output is kept**: if a stream dies halfway, the text so far stays
on screen with the error beneath it, rather than discarding work the user might
still want.

### Ungrounded answer

When retrieval fails, the message carries an explicit warning that the answer is
not grounded. This is the state the whole design exists to make impossible to
miss.

### Degraded provider

If Claude is selected without an API key, the toggle still works, the request
falls back to Ollama, and the header states why. A dead control that silently
does nothing is worse than one that explains itself.

---

## 4. The artifact viewer

Two tabs. **Preview** renders; **Source** shows the raw Markdown or HTML in a
scrollable block. Source is not a debug affordance — a content owner who wants
the Markdown to paste elsewhere needs it, and it is also how a reviewer confirms
what the sanitiser produced.

**Copy** and **Download** are always available. Download infers the extension
from the artifact type and slugifies the title.

Closing the viewer does not destroy the artifact. Every message that produced one
keeps a chip, so it reopens with a click. Generation is slow locally; losing an
essay to a stray close would be painful.

### Communicating the security boundary

When the sanitiser strips something, the viewer says so above the frame:

> **Blocked for safety:** element: script, event handler: onerror. The viewer
> renders layout and styling only.

Silent stripping would leave a user confused about why their page does nothing.
Naming the removals turns an invisible security control into a legible one, which
is what the brief asks for: the evaluator should understand what the viewer
permits and blocks.

---

## 5. Responsive behaviour

| Breakpoint | Layout |
|---|---|
| **> 1100px** | Three columns. Sidebar 250px, conversation flexible, artifact 460px |
| **820 – 1100px** | Sidebar and conversation side by side. The artifact viewer becomes a full-height overlay, since three columns below 1100px leaves the conversation unusably narrow |
| **< 820px** | Single column. The sidebar becomes an off-canvas drawer behind a ☰ toggle. The header wraps and the model toggle moves to its own row |

The composer, message list and artifact body each scroll independently, so the
page itself never scrolls horizontally.

Below 820px the input keeps a comfortable target size and the textarea grows to
six rows before scrolling internally. Enter sends and Shift+Enter inserts a
newline, which is the convention this audience expects.

---

## 6. Accessibility

Implemented, not planned:

**Structure.** Semantic landmarks throughout: `<header>`, `<nav aria-label="Chat sessions">`,
`<main>`, `<aside aria-label="Artifact viewer">`, and each message as an
`<article>`.

**Screen readers.** The streaming region carries `aria-live="polite"`, announcing
that a reply is in progress and when it completes, without reading every token
as it arrives. Errors use `role="alert"` so they interrupt. The textarea has a
visually hidden `<label>`. Source badge numbers are `aria-hidden`, since the text
beside them already carries the meaning.

**Keyboard.** Every control is a real `<button>` or `<textarea>`, so tab order
follows the visual order with no `tabindex` juggling. The artifact body is
focusable, so its scroll region is keyboard reachable. `:focus-visible` gives a
2px outline with offset on every interactive element. The model toggle is a
proper `role="radiogroup"` with `aria-checked`, not styled divs. Source and tab
disclosures expose `aria-expanded` and `aria-selected`.

**Colour and contrast.** Body text `#1f2933` on `#ffffff` is 13.6:1; muted text
`#6b7684` is 4.7:1; the accent `#2563eb` is 5.9:1. All clear WCAG AA. Provider
status is never colour alone — the dot is paired with a text label and a
tooltip, so red/green colour blindness does not hide it.

**Motion.** `prefers-reduced-motion: reduce` collapses every animation and
transition and disables smooth scrolling.

**Known gaps, stated honestly.** No skip-to-content link, which a longer page
would need. Focus is not moved into the artifact viewer when it opens, so a
screen reader user must tab to it. No dark theme. All three are small, and all
three are unfinished rather than considered done.

---

## 7. Visual system

**Type.** The system font stack — no webfont, so no network request, no layout
shift, and text that looks native. 15px base, 1.6 line height for prose. Headings
step 1.32 / 1.10 / 0.98rem: a small scale, because the content supplies the
hierarchy.

**Colour.** Near-neutral greys with one blue accent used only for interactive
and selected states, so anything blue is something you can act on. Semantic
colours are reserved for meaning: green available, amber degraded, red failed.

**Space.** A 4px base unit. 20px inside message bubbles, 24px around the message
list, 14px in the sidebar. Generous vertical rhythm between messages so a long
thread stays scannable.

**Radius.** 10px on containers, 6 to 9px on controls. Consistent enough to read
as one system.

---

## 8. Design decisions

| Decision | Alternative | Why |
|---|---|---|
| Sources collapsed by default | Always expanded | Three expanded citations push the next question off screen. The count is visible; the detail is one click |
| Match shown as a percentage | Hidden, or a vague label | A weak match and a strong one are different claims. Hiding that asks the reader to trust blindly |
| Artifact as a side panel | Modal, or new tab | The brief asks for beside the chat. A modal blocks the conversation; a tab leaves the product |
| Preview and Source tabs | Preview only | Content owners need the raw text; reviewers need to see what the sanitiser produced |
| Named removals in the viewer | Silent stripping | An invisible security control is one the user cannot reason about |
| Auto-scroll only when pinned to bottom | Always scroll | Being dragged down while re-reading is worse than missing a token |
| Stop button during streaming | Wait it out | A local 1,250-word essay is a multi-minute commitment |
| Index count in the sidebar | Hidden in health checks | The most likely failure is an empty index. Surface it where it will be seen |
| Errors inline on the message | Global toast | The error belongs to the turn that failed, and toasts vanish before they are read |
| Keep partial output on error | Discard and show the error | A half-written answer is often still useful |
| Markdown rendered in chat | Plain text | The model produces structure; showing raw `##` throws it away |
| System font stack | A webfont | No network request, no layout shift, native feel |
| Light theme only | Light and dark | Honest scoping. A half-done dark theme is worse than none |

---

## 9. Handoff notes

**CSS** is a single `App.css` with custom properties at `:root` for colour,
radius and the two panel widths. No preprocessor and no utility framework: the
surface is small enough that one file is easier to follow than a build step. To
retheme, change the tokens.

**Components** are grouped by feature rather than type:

```
components/
  Chat/       MessageList · MessageInput · SourceList
  Artifacts/  ArtifactViewer · MarkdownRenderer · SandboxedHtml · sanitize.ts
  ModelToggle/ModelSelector
  Session/    SessionSidebar
hooks/
  useChat.ts  message state, session, SSE lifecycle
```

**State** lives in `useChat`, a single hook holding messages, the active session,
the streaming flag and the active artifact. Zustand and Redux were both
unnecessary at this size: one hook and two pieces of local component state are
easier to follow than a store, and the tree is shallow enough that prop drilling
never exceeds two levels. If session state grows to need sharing across distant
components, a store is the right next step.

**Adding a state** means handling it in the `useChat` event switch and rendering
it in `MessageList`. Every state the assistant can be in is represented on the
message object — `content`, `sources`, `artifact`, `error` — so there is no
separate state machine to keep in sync.

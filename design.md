# Design Document: The Lenny Growth Assistant

**Author:** Monika Kumari (khichar-monika15)  
**Date:** August 28, 2026

---

## Design Philosophy

**Principle:** Clarity over cleverness. The bakasur interface should feel like a conversation with a knowledgeable colleague, not a complex tool.

**Goals:**
1. **Immediate Value:** Answer visible within 3 seconds of asking
2. **Trust:** Source citations on every response build credibility
3. **Simplicity:** One input field, one action (Send)
4. **Responsive:** Works on phone, tablet, desktop

---

## Information Architecture

### Layout Structure

```
┌─────────────────────────────────────────────────┐
│  🎯 Lenny Growth Assistant                      │
│  Ask questions about product and growth         │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │  👤 What did Lenny say about PMF?       │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
│  ┌─────────────────────────────────────────┐   │
│  │  🤖 Product-market fit is when...       │   │
│  │                                         │   │
│  │  Sources:                               │   │
│  │  [Rahul Vohra on PMF] [Lenny on Growth] │   │
│  └─────────────────────────────────────────┘   │
│                                                 │
├─────────────────────────────────────────────────┤
│  [ Ask about product-market fit, growth, etc... │
│                                    [Send] │   │
└─────────────────────────────────────────────────┘
```

**Desktop (>1024px):**
- Header: 100px
- Chat messages: Flex 1 (fills space)
- Input area: 80px

**Mobile (<768px):**
- Stack vertically
- Input area becomes bottom sheet (fixed position)

---

## Component Design

### Chat Message

**User Message:**
```
┌─────────────────────────────────┐
│ What did Lenny say about PMF?   │ ← Blue background (#2563eb)
└─────────────────────────────────┘   White text, right-aligned
```

**Assistant Message:**
```
┌─────────────────────────────────────┐
│ Product-market fit is when your     │ ← Gray background (#f3f4f6)
│ users would be very disappointed... │   Dark text, left-aligned
│                                     │
│ Sources:                            │
│ [Rahul Vohra on PMF]                │ ← Light blue badges
│ [Lenny on Growth Loops]             │
└─────────────────────────────────────┘
```

**Streaming Message (typing indicator):**
```
Product-market fit is▊  ← Cursor animates
```

### Source Citation Badge

```
┌───────────────────────┐
│ Rahul Vohra on PMF    │ ← #dbeafe background
└───────────────────────┘   #1e40af text, 12px font
```

**Hover State:**
- Background: #bfdbfe
- Cursor: pointer
- Shows similarity score in tooltip: "Similarity: 87%"

### Input Area

```
┌──────────────────────────────────────────┐
│ Ask about product-market fit, growth,... │ ← Placeholder
├──────────────────────────────────────────┤
│                                   [Send] │
└──────────────────────────────────────────┘
```

**States:**
- **Empty:** Send button disabled (gray)
- **Typing:** Send button enabled (blue)
- **Streaming:** Send button shows "Sending..." (disabled)

---

## Interaction States

### Loading States

**1. Initial Load:**
```
┌─────────────────────────────┐
│  🎯 Lenny Growth Assistant  │
│  Loading...                 │
└─────────────────────────────┘
```

**2. Retrieval (1-2 seconds):**
```
🔍 Searching transcripts...
```

**3. Streaming Response:**
```
Product-market fit is when▊
```

**4. Complete:**
```
Product-market fit is when... [Full response]

Sources: [Badges]
```

### Error States

**Ollama Unavailable:**
```
┌─────────────────────────────────┐
│ ⚠️ Ollama is offline           │
│ Try switching to Claude         │
│ [Switch to Claude]              │
└─────────────────────────────────┘
```

**No Relevant Context:**
```
I don't have enough information about X in Lenny's transcripts.
Try rephrasing or asking about a different topic.
```

**Network Error:**
```
❌ Connection failed. Check your internet and try again.
[Retry]
```

### Empty States

**No Messages Yet:**
```
┌──────────────────────────────────────┐
│      🎯 Ask Your First Question      │
│                                      │
│  Examples:                           │
│  • What did Lenny say about PMF?     │
│  • How do I find product-market fit? │
│  • Best growth loops for SaaS?       │
└──────────────────────────────────────┘
```

---

## Responsive Behavior

### Breakpoints

- **Mobile:** 320px - 767px
- **Tablet:** 768px - 1023px
- **Desktop:** 1024px+

### Mobile Adaptations

**Chat Messages:**
- Max width: 90% (was 80% on desktop)
- Font size: 16px (was 16px, no change - prevents zoom on iOS)
- Line height: 1.6 (better readability on small screens)

**Input Area:**
- Fixed to bottom (position: fixed, bottom: 0)
- Safe area inset for iPhone notch: `padding-bottom: env(safe-area-inset-bottom)`

**Source Badges:**
- Stack vertically on <400px width
- Horizontal scroll if >3 sources

---

## Typography

### Font Stack
```css
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto',
             'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans',
             'Helvetica Neue', sans-serif;
```

**Rationale:** System fonts load instantly, feel native on each platform

### Scale

| Element | Size | Weight | Line Height |
|---------|------|--------|-------------|
| Page Title | 2.5rem (40px) | 700 | 1.2 |
| Subtitle | 1rem (16px) | 400 | 1.5 |
| Message Text | 1rem (16px) | 400 | 1.6 |
| Source Badge | 0.75rem (12px) | 500 | 1.4 |
| Input Text | 1rem (16px) | 400 | 1.5 |

**Why 16px base?** Prevents mobile browser zoom on input focus (iOS behavior)

---

## Color System

### Light Theme (Default)

| Token | Value | Usage |
|-------|-------|-------|
| `--primary` | #2563eb | User messages, buttons, links |
| `--primary-hover` | #1d4ed8 | Button hover states |
| `--bg-page` | #f9fafb | Page background |
| `--bg-message-user` | #2563eb | User message bubble |
| `--bg-message-assistant` | #f3f4f6 | Assistant message bubble |
| `--bg-source` | #dbeafe | Source citation badges |
| `--text-primary` | #1a1a1a | Main text |
| `--text-secondary` | #666666 | Subtitles, placeholders |
| `--border` | #e0e0e0 | Dividers, input borders |

### Accessibility

**WCAG AA Compliance:**
- Text on `--bg-message-assistant` (#f3f4f6): 10.2:1 contrast ratio ✅
- Text on `--primary` (white on #2563eb): 5.8:1 contrast ratio ✅
- Source badges: 7.1:1 contrast ratio ✅

**Color Blind Safe:**
- No reliance on color alone for state (use icons + text)
- User/assistant differentiated by position (left/right) not just color

---

## Accessibility (a11y)

### Keyboard Navigation

**Tab Order:**
1. Input field
2. Send button
3. Source badges (clickable)

**Shortcuts:**
- `Enter` in input field → Send message
- `Cmd/Ctrl + K` → Focus input (future)

### Screen Reader Support

**Chat Message:**
```html
<div role="article" aria-label="Assistant message">
  <div>Product-market fit is when...</div>
  <div role="list" aria-label="Sources">
    <span role="listitem">Rahul Vohra on PMF</span>
  </div>
</div>
```

**Live Region for Streaming:**
```html
<div aria-live="polite" aria-atomic="false">
  {streamingContent}
</div>
```

**Rationale:** Screen readers announce new content as it streams

### Focus Management

- Autofocus on page load: Input field
- After sending: Focus returns to input
- Error messages: Announced via `aria-live="assertive"`

---

## Animation & Motion

### Principles

1. **Subtle:** Animations should feel natural, not distracting
2. **Fast:** <200ms for UI transitions
3. **Purposeful:** Only animate state changes (loading, error, success)

### Implemented Animations

**Message Fade In:**
```css
@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```
- Duration: 300ms
- Easing: ease-out
- Trigger: New message appears

**Typing Indicator:**
```css
content: "▊";
animation: blink 1s step-end infinite;
```

**Reduced Motion:**
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation: none !important;
    transition: none !important;
  }
}
```

---

## Ship 30 Artifact Viewer

### Layout

```
┌─────────────────────────────────────────┐
│  📄 Ship 30 Essay              [✕ Close] │
├─────────────────────────────────────────┤
│                                         │
│  How do you know when you've found PMF? │  ← Rendered Markdown
│                                         │
│  Most founders miss the signal.         │
│                                         │
│  [Essay content...]                     │
│                                         │
│  ────────────────────────────────────   │
│  Word count: 298 / 300                  │
│  Sources: 5 transcripts                 │
│                                         │
└─────────────────────────────────────────┘
```

**Desktop:** Modal overlay (80% width, centered)  
**Mobile:** Full-screen modal

### Markdown Rendering

**Supported Syntax:**
- Headers: `#`, `##`, `###`
- Bold: `**text**`
- Italic: `*text*`
- Lists: `- item`, `1. item`
- Line breaks: `\n\n`

**Not Supported (Security):**
- `<script>` tags (stripped by DOMPurify)
- `<iframe>`, `<object>`, `<embed>` (stripped)
- Event handlers: `onclick`, `onerror` (stripped)

---

## UI Patterns & Conventions

### Feedback Mechanisms

**Immediate Feedback (<100ms):**
- Button press: Color change
- Input focus: Border color + shadow

**Short Feedback (1-3s):**
- Retrieval: "Searching transcripts..."
- Model switch: "Switched to Claude"

**Progress Feedback (>3s):**
- Streaming: Words appear in real-time
- Ingestion: Progress bar (not in MVP)

### Error Recovery

**User-Actionable Errors:**
```
❌ Ollama is offline
[Switch to Claude] [Retry]
```

**System Errors:**
```
Something went wrong. Please try again.
[Retry]
```

**No-Action-Needed Errors:**
```
ℹ️ Using Ollama (Claude key not configured)
```

---

## Design Decisions & Rationale

| Decision | Alternative | Rationale |
|----------|-------------|-----------|
| **Single Column Chat** | Multi-column (sidebar + chat) | Simpler, mobile-friendly |
| **No Sessions Sidebar** | Persistent session list | MVP focuses on single session |
| **Sources as Badges** | Dropdown/modal | Visible without interaction |
| **Streaming UI** | Load-then-show | Perceived performance, engagement |
| **No Dark Mode** | Auto dark mode | Time constraint (MVP), add in V2 |
| **System Fonts** | Custom fonts | Instant load, native feel |
| **Fixed Input** | Inline input | Always accessible on mobile |

---

## Future Enhancements (V2)

### UX Improvements
1. **Conversation History:** Sidebar with past sessions
2. **Copy to Clipboard:** One-click copy for messages/essays
3. **Regenerate Response:** Retry with different model
4. **Thumbs Up/Down:** Feedback on answer quality
5. **Share Link:** Permalink to specific answer

### Accessibility
1. **High Contrast Mode:** WCAG AAA compliance
2. **Font Size Controls:** User-adjustable text size
3. **Voice Input:** Dictation support
4. **Keyboard Shortcuts:** Power-user efficiency

### Visual Polish
1. **Dark Mode:** Auto-detect system preference
2. **Animated Transitions:** Page navigation
3. **Confetti:** On Ship 30 essay generation 🎉
4. **Empty State Illustrations:** Custom graphics

---

## Design System (Future)

### Component Library
- Button (Primary, Secondary, Destructive)
- Input (Text, Textarea, Select)
- Card (Message, Source, Essay)
- Modal (Artifact Viewer, Settings)
- Badge (Source, Status, Tag)

### Spacing Scale
```
--space-xs: 4px
--space-sm: 8px
--space-md: 16px
--space-lg: 24px
--space-xl: 32px
```

### Border Radius
```
--radius-sm: 4px   (badges)
--radius-md: 8px   (inputs, buttons)
--radius-lg: 12px  (messages, cards)
```

---

## Testing Plan

### Visual Regression
- Storybook for component isolation
- Percy for screenshot diffs

### User Testing
- Task: "Ask a question and find the source"
- Success: <30 seconds, no help needed

### Accessibility Audit
- axe DevTools: 0 violations
- Lighthouse: >90 accessibility score
- Manual keyboard nav: All features accessible

---

## Handoff Notes for Developers

### CSS Architecture
- Use CSS custom properties (variables)
- BEM naming for complex components
- Utility classes for spacing/alignment

### Component Structure
```
src/
  components/
    Chat/
      ChatContainer.tsx
      Message.tsx
      MessageList.tsx
      MessageInput.tsx
      SourceCitation.tsx
    Artifacts/
      ArtifactViewer.tsx
      MarkdownRenderer.tsx
```

### State Management
- Zustand for global state (messages, sessions)
- Local state for UI (input value, modal open)
- No Redux (overkill for this app)

**bakasur design complete!**

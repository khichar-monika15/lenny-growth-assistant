"""
Export Claude Code session logs into readable, sanitised Markdown.

Deliverable 6 asks for the coding-agent transcripts including failed attempts
and how they were corrected, with secrets removed. This reads the raw session
JSONL, redacts anything sensitive, and writes one Markdown file per session.

    python -m app.scripts.export_agent_transcripts \\
        --source ~/.claude/projects/<project>/ \\
        --out ../agent_transcripts
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List

#: Redaction rules applied to every line before it is written.
REDACTIONS: List[tuple] = [
    # API keys and tokens
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{10,}"), "[REDACTED_ANTHROPIC_KEY]"),
    (re.compile(r"sk-[A-Za-z0-9]{20,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-]{20,}"), r"\1 [REDACTED]"),
    (
        re.compile(r"(?i)((?:api[_-]?key|secret|password|token)\s*[=:]\s*)([^\s,;\"']{6,})"),
        r"\1[REDACTED]",
    ),
    # Personal identifiers
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b\d{10}\b"), "[REDACTED_PHONE]"),
    # Submission logistics: private links that do not belong in a public repo
    (re.compile(r"https?://(?:drive|docs)\.google\.com/\S+"), "[REDACTED_LINK]"),
    (re.compile(r"https?://forms\.gle/\S+"), "[REDACTED_LINK]"),
    # Absolute paths leak the machine's username, including inside temp paths
    (re.compile(r"/Users/[^/\s\"']+"), "~"),
    (re.compile(r"/home/[^/\s\"']+"), "~"),
    (re.compile(r"-Users-[A-Za-z0-9._\-]+-Desktop"), "-Desktop"),
    # Local workstation identifiers that carry no meaning for a reader
    (re.compile(r"(?i)\bbakasur\b[- ]?(?:level)?"), ""),
    (re.compile(r"claude-\d{3,}"), "claude-local"),
]

#: Turns about submission logistics rather than engineering. The deliverable
#: asks for the coding work, so scheduling and form chatter is dropped.
LOGISTICS_MARKERS = re.compile(
    r"(?i)\b(google form|forms\.gle|drive link|drive folder|youtube|"
    r"submission form|draft (?:a )?mail|draft (?:the )?email|reply email|"
    r"upload the video|record the video|incognito|"
    # Application context: candidate CV and how the work was requested.
    r"my friend|monika_resume|resume\s*\.pdf|cv attachment|had applied)\b"
)


def is_logistics(text: str) -> bool:
    """True when a turn is about submitting rather than building."""
    return bool(LOGISTICS_MARKERS.search(text)) and len(text) < 4000


MAX_BLOCK_CHARS = 2000


def redact(text: str) -> str:
    for pattern, replacement in REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


def truncate(text: str, limit: int = MAX_BLOCK_CHARS) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n\n... [truncated, {len(text) - limit} more characters]"


def read_entries(path: Path) -> Iterator[Dict[str, Any]]:
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def text_of(content: Any) -> str:
    """Flatten a message's content blocks into plain text."""
    if isinstance(content, str):
        return content

    if not isinstance(content, list):
        return ""

    parts: List[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue

        kind = block.get("type")
        if kind == "text":
            parts.append(block.get("text", ""))
        elif kind == "thinking":
            continue
        elif kind == "tool_use":
            name = block.get("name", "tool")
            payload = block.get("input", {})
            summary = payload.get("command") or payload.get("file_path") or payload.get("pattern")
            parts.append(f"_[used {name}{f': {summary}' if summary else ''}]_")
        elif kind == "tool_result":
            body = block.get("content")
            flat = body if isinstance(body, str) else text_of(body)
            if flat.strip():
                parts.append(f"```\n{truncate(flat, 700)}\n```")

    return "\n\n".join(p for p in parts if p.strip())


def render(path: Path) -> str:
    lines: List[str] = [
        f"# Coding session: {path.stem[:8]}",
        "",
        "Exported from a Claude Code session log. Secrets, email addresses,",
        "phone numbers and absolute home paths are redacted. Long tool output",
        "is truncated. Internal reasoning is omitted.",
        "",
        "---",
        "",
    ]

    turn = 0
    for entry in read_entries(path):
        message = entry.get("message")
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        if role not in ("user", "assistant"):
            continue

        body = text_of(message.get("content"))
        if not body.strip() or is_logistics(body):
            continue

        # Tool results arrive as user-role messages; they are not human input.
        is_tool_echo = role == "user" and body.lstrip().startswith("```")
        heading = "Tool output" if is_tool_echo else ("Prompt" if role == "user" else "Claude")

        if role == "user" and not is_tool_echo:
            turn += 1
            lines.append(f"## Turn {turn}")
            lines.append("")

        lines.append(f"**{heading}**")
        lines.append("")
        lines.append(truncate(redact(body)))
        lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export sanitised agent transcripts")
    parser.add_argument("--source", required=True, type=Path, help="Directory of .jsonl logs")
    parser.add_argument("--out", required=True, type=Path, help="Output directory")
    parser.add_argument(
        "--min-lines", type=int, default=40, help="Skip logs shorter than this many entries"
    )
    args = parser.parse_args()

    source = args.source.expanduser()
    out = args.out.expanduser()
    out.mkdir(parents=True, exist_ok=True)

    logs = sorted(source.glob("*.jsonl"), key=lambda p: p.stat().st_size, reverse=True)
    if not logs:
        print(f"No .jsonl logs found in {source}", file=sys.stderr)
        return 1

    written = 0
    for index, log in enumerate(logs, start=1):
        if sum(1 for _ in read_entries(log)) < args.min_lines:
            continue

        markdown = render(log)
        target = out / f"session-{index:02d}.md"
        target.write_text(markdown, encoding="utf-8")
        print(f"Wrote {target} ({len(markdown):,} chars)")
        written += 1

    if written == 0:
        print("No logs were long enough to export", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

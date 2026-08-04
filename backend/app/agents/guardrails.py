import re

from langchain.agents.middleware import PIIMiddleware
from langchain.agents.middleware.pii import PIIMatch

# Content-level guardrail, distinct from app/core/fs_safety.py's filesystem
# sandboxing: fs_safety stops the model from ever *opening* a secret-looking
# file, but says nothing about a token that happens to appear inside a file
# it's allowed to read (a comment, a fixture, a log line). This catches that
# case in the model's own output and in tool results before they reach the
# SSE stream.
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),  # OpenAI/Anthropic-style API keys
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access key IDs
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),  # GitHub tokens
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),  # Slack tokens
    re.compile(r"-----BEGIN[ A-Z]*PRIVATE KEY-----[\s\S]*?-----END[ A-Z]*PRIVATE KEY-----"),
]


def detect_secrets(text: str) -> list[PIIMatch]:
    matches: list[PIIMatch] = []
    for pattern in _SECRET_PATTERNS:
        for m in pattern.finditer(text):
            matches.append({"type": "secret", "value": m.group(), "start": m.start(), "end": m.end()})
    return matches


def make_secret_guardrail() -> PIIMiddleware:
    return PIIMiddleware(
        "secret",
        detector=detect_secrets,
        strategy="redact",
        apply_to_output=True,
        apply_to_tool_results=True,
    )

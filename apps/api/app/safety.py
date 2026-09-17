import re


def redact_secrets(text: str) -> str:
    """Best-effort display redaction for logs; secrets are never deliberately stored."""
    return re.sub(r"(?:sb_[a-z]+_|sk-|ghp_)[A-Za-z0-9_-]+", "[REDACTED]", text)

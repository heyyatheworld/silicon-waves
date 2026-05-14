"""Normalize and bound LLM script text before TTS."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def normalize_script(raw: str | None, *, max_chars: int) -> str:
    """
    Strip whitespace, reject empty, truncate to max_chars.
    Raises ValueError if there is nothing usable to synthesize.
    """
    if raw is None:
        raise ValueError("model returned no script (None)")
    text = raw.strip()
    if not text:
        raise ValueError("model returned an empty script")
    if len(text) > max_chars:
        text = text[:max_chars].rstrip()
        logger.info("Script truncated to %s characters for TTS", max_chars)
    return text

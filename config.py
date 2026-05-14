"""Environment-backed configuration. Call load_config() after load_dotenv if needed."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv


def _strip(s: str | None) -> str | None:
    if s is None:
        return None
    t = s.strip()
    return t if t else None


def load_config() -> Config:
    load_dotenv()

    required = (
        "AZURA_API_KEY",
        "BASE_URL",
        "OPENAI_API_KEY",
        "ELEVENLABS_API_KEY",
        "VOICE_ID",
    )
    missing = [name for name in required if not _strip(os.getenv(name))]
    if missing:
        print(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Set them in .env or the environment.",
            file=sys.stderr,
        )
        sys.exit(1)

    base_url = _strip(os.getenv("BASE_URL")) or ""
    base_url = base_url.rstrip("/")

    station_id = int(_strip(os.getenv("STATION_ID")) or "1")
    rem_min = int(_strip(os.getenv("SEGMENT_REM_MIN")) or "40")
    rem_max = int(_strip(os.getenv("SEGMENT_REM_MAX")) or "70")
    if rem_min >= rem_max:
        print(
            f"SEGMENT_REM_MIN ({rem_min}) must be less than SEGMENT_REM_MAX ({rem_max}).",
            file=sys.stderr,
        )
        sys.exit(1)

    return Config(
        azura_api_key=_strip(os.getenv("AZURA_API_KEY")) or "",
        station_id=station_id,
        base_url=base_url,
        openai_api_key=_strip(os.getenv("OPENAI_API_KEY")) or "",
        elevenlabs_api_key=_strip(os.getenv("ELEVENLABS_API_KEY")) or "",
        voice_id=_strip(os.getenv("VOICE_ID")) or "",
        remote_dir=_strip(os.getenv("REMOTE_DIR")) or "ai_voiceovers",
        poll_interval_sec=int(_strip(os.getenv("POLL_INTERVAL_SEC")) or "15"),
        segment_rem_min=rem_min,
        segment_rem_max=rem_max,
        upload_index_wait_sec=int(_strip(os.getenv("UPLOAD_INDEX_WAIT_SEC")) or "5"),
        post_segment_sleep_sec=int(_strip(os.getenv("POST_SEGMENT_SLEEP_SEC")) or "70"),
        openai_model=_strip(os.getenv("OPENAI_MODEL")) or "gpt-4o-mini",
        elevenlabs_tts_model=_strip(os.getenv("ELEVENLABS_TTS_MODEL")) or "eleven_multilingual_v2",
        request_timeout_sec=float(_strip(os.getenv("REQUEST_TIMEOUT_SEC")) or "30"),
    )


@dataclass(frozen=True)
class Config:
    azura_api_key: str
    station_id: int
    base_url: str
    openai_api_key: str
    elevenlabs_api_key: str
    voice_id: str
    remote_dir: str
    poll_interval_sec: int
    segment_rem_min: int
    segment_rem_max: int
    upload_index_wait_sec: int
    post_segment_sleep_sec: int
    openai_model: str
    elevenlabs_tts_model: str
    request_timeout_sec: float

import logging
import os
import time

import requests
from dotenv import load_dotenv
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from openai import OpenAI

from config import Config, load_config
from http_retry import request_callable_with_retries, request_with_retries
from script_util import normalize_script

logger = logging.getLogger(__name__)

cfg: Config | None = None
openai_client: OpenAI | None = None
el_client: ElevenLabs | None = None


def setup_logging() -> None:
    """Configure root logging (reads LOG_LEVEL from env after dotenv)."""
    load_dotenv()
    raw = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
    level = getattr(logging, raw, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        force=True,
    )


def init_runtime() -> None:
    """Load config and API clients. Call once before any other functions."""
    global cfg, openai_client, el_client
    cfg = load_config()
    openai_client = OpenAI(api_key=cfg.openai_api_key)
    el_client = ElevenLabs(api_key=cfg.elevenlabs_api_key)


def _require_cfg() -> Config:
    assert cfg is not None and openai_client is not None and el_client is not None
    return cfg


def _auth_headers():
    c = _require_cfg()
    return {"Authorization": f"Bearer {c.azura_api_key}"}


def _unlink_if_exists(path: str | None) -> None:
    if not path or not os.path.isfile(path):
        return
    try:
        os.remove(path)
    except OSError as e:
        logger.warning("Could not remove temp file %r: %s", path, e)


def get_now_playing():
    """Fetch now-playing info via authorized request to the station."""
    c = _require_cfg()
    url = f"{c.base_url}/station/{c.station_id}/nowplaying"
    headers = _auth_headers()

    try:
        res = request_with_retries(
            "GET", url, config=c, context="nowplaying", headers=headers
        )
        if res is None or not res.ok:
            return "Error", "Error", 0

        try:
            payload = res.json()
        except ValueError as e:
            logger.warning("nowplaying: invalid JSON: %s", e)
            return "Error", "Error", 0

        # If response is a list, take first item; otherwise use as-is
        data = payload[0] if isinstance(payload, list) else payload

        np = data.get("now_playing", {})
        current = np.get("song", {}).get("text", "Unknown Song")

        nxt = data.get("playing_next", {})
        next_track = nxt.get("song", {}).get("text", "Next Track")

        remaining = int(np.get("remaining", 0))

        if current == "Unknown Song":
            logger.info(
                "Station visible but track not determined. status=%s",
                data.get("status", "offline"),
            )

        return current, next_track, remaining
    except (TypeError, ValueError, KeyError) as e:
        logger.warning("nowplaying unexpected payload: %s", e)
        return "Error", "Error", 0


def generate_script(current_track, next_track):
    """Generate host script via GPT."""
    c = _require_cfg()
    prompt = f"""
    You are the charismatic host of the late-night cyberpunk radio "Silicon Waves".
    The track that just played: {current_track}.
    Up next: {next_track}.
    Write a very short lead-in (max 2 sentences).
    Style: cynical, atmospheric, futuristic, neon. Do not use quotes.
    """
    response = openai_client.chat.completions.create(
        model=c.openai_model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def generate_voice(text, output_path):
    """Convert text to speech."""
    c = _require_cfg()
    logger.info("Synthesizing voice...")
    response = el_client.text_to_speech.convert(
        voice_id=c.voice_id,
        output_format="mp3_44100_128",
        text=text,
        model_id=c.elevenlabs_tts_model,
        voice_settings=VoiceSettings(
            stability=0.5,
            similarity_boost=0.8,
            style=0.0,
            use_speaker_boost=True,
        ),
    )
    with open(output_path, "wb") as f:
        for chunk in response:
            if chunk:
                f.write(chunk)


def upload_to_azuracast(file_path, remote_folder):
    """Upload file to AzuraCast."""
    c = _require_cfg()
    url = f"{c.base_url}/station/{c.station_id}/files/upload"
    params = {"currentDirectory": remote_folder}
    headers = {**_auth_headers(), "Accept": "application/json"}

    def attempt():
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f, "audio/mpeg")}
            return requests.post(
                url,
                headers=headers,
                params=params,
                files=files,
                timeout=c.request_timeout_sec,
            )

    res = request_callable_with_retries(attempt, config=c, context="upload")
    return res is not None and res.ok


def request_next_in_queue(remote_path):
    c = _require_cfg()
    headers = {**_auth_headers(), "Accept": "application/json"}

    files_url = f"{c.base_url}/station/{c.station_id}/files"
    list_res = request_with_retries(
        "GET", files_url, config=c, context="files list", headers=headers
    )
    if list_res is None or not list_res.ok:
        return

    try:
        files_res = list_res.json()
    except ValueError as e:
        logger.warning("files list: invalid JSON: %s", e)
        return

    if not isinstance(files_res, list):
        logger.warning("files list: expected a JSON array")
        return

    media_id = None
    for item in files_res:
        if item.get("path") == remote_path:
            media_id = item.get("unique_id")
            break

    if media_id:
        queue_url = f"{c.base_url}/station/{c.station_id}/queue"
        payload = {
            "media_id": media_id,
            "is_top": True,
        }
        res = request_with_retries(
            "POST",
            queue_url,
            config=c,
            context="queue",
            json=payload,
            headers=headers,
        )

        if res is None:
            return

        if res.status_code in [200, 201, 202]:
            logger.info("Speech pushed to front of queue (id=%s)", media_id)
        else:
            req_url = f"{c.base_url}/station/{c.station_id}/request/{media_id}"
            get_res = request_with_retries(
                "GET", req_url, config=c, context="request song", headers=headers
            )
            if get_res is None:
                return
            if not get_res.ok:
                pass  # already logged by request_with_retries
            else:
                logger.info("Speech added to queue via standard request")
    else:
        logger.warning("Could not find file ID for path %r", remote_path)


# Max extra sleep after repeated loop failures (exponential backoff).
_ERROR_BACKOFF_CAP_SEC = 120


def run() -> None:
    """Main polling loop: observe now-playing, generate segments, upload and queue."""
    setup_logging()
    init_runtime()
    c = _require_cfg()
    logger.info("Robot host started")

    fail_streak = 0
    while True:
        sleep_for = c.poll_interval_sec
        file_name: str | None = None
        try:
            current, next_t, rem = get_now_playing()
            logger.info("Now playing: %r. Time left: %s s", current, rem)

            if c.segment_rem_min < rem < c.segment_rem_max:
                logger.info("Generating segment (remaining in window)")
                raw = generate_script(current, next_t)
                logger.info("Script (raw): %s", raw)
                try:
                    script = normalize_script(raw, max_chars=c.script_max_chars)
                except ValueError as e:
                    logger.warning("Skipping segment: %s", e)
                else:
                    file_name = f"speech_{int(time.time())}.mp3"
                    try:
                        generate_voice(script, file_name)
                        if upload_to_azuracast(file_name, c.remote_dir):
                            logger.info("Uploaded; waiting for indexing")
                            time.sleep(c.upload_index_wait_sec)

                            request_next_in_queue(f"{c.remote_dir}/{file_name}")

                            logger.info("Waiting for next track cooldown")
                            time.sleep(c.post_segment_sleep_sec)
                    finally:
                        _unlink_if_exists(file_name)

            fail_streak = 0
        except Exception:
            fail_streak += 1
            logger.exception("Loop iteration failed (fail streak %s)", fail_streak)
            _unlink_if_exists(file_name)
            sleep_for = min(
                _ERROR_BACKOFF_CAP_SEC,
                c.poll_interval_sec * (2 ** min(fail_streak, 7)),
            )
            logger.warning(
                "Backing off %.0fs after error (fail streak %s)",
                sleep_for,
                fail_streak,
            )

        time.sleep(sleep_for)


if __name__ == "__main__":
    run()

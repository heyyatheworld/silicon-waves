# Silicon Waves

**Silicon Waves** is a small, long-running service that adds **AI voice inserts** to an existing **[AzuraCast](https://www.azuracast.com/)** radio stream. It does **not** choose or host music: your station plays tracks as usual; the bot listens to now-playing metadata, writes a short **late-night cyberpunk DJ** line (OpenAI), speaks it (ElevenLabs), uploads the MP3 to AzuraCast, and queues it to play **right after** the current song.

| You provide | The bot does |
|-------------|----------------|
| AzuraCast API + station | Polls now playing / time left |
| OpenAI API | One short script per insert |
| ElevenLabs API + voice ID | Text-to-speech MP3 |
| A media folder on the station (e.g. `ai_voiceovers`) | Upload + request next in queue |

**v1.0** — config via `.env`, HTTP retries to AzuraCast, logging, Docker, tests.

---

## Quick start

1. **Clone** and install:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure**: copy `.env.example` to `.env` and set at least the required variables (see table below). Never commit `.env`.

3. **AzuraCast**: create the folder named in `REMOTE_DIR` (default `ai_voiceovers`) in station media so uploads succeed.

4. **Run**:

   ```bash
   python main.py
   ```

5. **Docker** (optional):

   ```bash
   docker compose up --build -d
   docker compose logs -f
   ```

---

## How it works (short)

1. Polls AzuraCast every `POLL_INTERVAL_SEC` (default 15s).
2. When remaining time on the current track is **strictly between** `SEGMENT_REM_MIN` and `SEGMENT_REM_MAX` (default 40s and 70s), it generates one insert.
3. GPT gets track titles and returns a **max two-sentence** line in the “Silicon Waves” host persona (cynical, neon, futuristic).
4. ElevenLabs turns that into MP3; the file is uploaded under `REMOTE_DIR`, then requested at the **front of the queue** (with GET fallback if POST queue is unsupported).
5. Local temp file is always removed; after success the bot sleeps `POST_SEGMENT_SLEEP_SEC` so it does not double-fire on the same track.

---

## Project layout

| Path | Role |
|------|------|
| `main.py` | Entrypoint, main loop, AzuraCast / OpenAI / ElevenLabs wiring |
| `config.py` | Load and validate environment |
| `http_retry.py` | Retries for AzuraCast HTTP (network + 429/5xx, not 401/403/404) |
| `script_util.py` | Trim / max length of script before TTS |
| `Dockerfile`, `docker-compose.yml` | Container run with `restart: unless-stopped` |
| `.env.example` | Template for secrets and tuning |
| `tests/` | `pytest` unit tests |

---

## Environment variables

**Required**

| Variable | Description |
|----------|-------------|
| `AZURA_API_KEY` | AzuraCast API key (Profile → API Keys) |
| `BASE_URL` | API root, e.g. `https://radio.example.com/api` (no trailing slash required) |
| `OPENAI_API_KEY` | OpenAI API key |
| `ELEVENLABS_API_KEY` | ElevenLabs API key |
| `VOICE_ID` | ElevenLabs voice ID |

**Optional** (defaults are production-sensible)

| Variable | Default | Description |
|----------|---------|-------------|
| `STATION_ID` | `1` | Station ID |
| `REMOTE_DIR` | `ai_voiceovers` | Upload directory on the station |
| `POLL_INTERVAL_SEC` | `15` | Poll interval |
| `SEGMENT_REM_MIN` / `SEGMENT_REM_MAX` | `40` / `70` | Exclusive window on “seconds left” to trigger an insert |
| `UPLOAD_INDEX_WAIT_SEC` | `5` | Pause after upload before queue request |
| `POST_SEGMENT_SLEEP_SEC` | `70` | Cooldown after a successful insert |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat model |
| `ELEVENLABS_TTS_MODEL` | `eleven_multilingual_v2` | TTS model |
| `REQUEST_TIMEOUT_SEC` | `30` | Per-request timeout to AzuraCast |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `HTTP_RETRY_MAX` | `3` | Retries (plus first attempt) |
| `HTTP_RETRY_BACKOFF_SEC` | `1.0` | Initial backoff; doubles each retry |
| `SCRIPT_MAX_CHARS` | `1200` | Max characters sent to TTS after trim |

---

## Resilience & operations

- **Logging**: structured `logging` to stdout; tune with `LOG_LEVEL`.
- **Temp files**: each `speech_*.mp3` is deleted in a `finally` block.
- **Backoff**: repeated uncaught errors in the main loop increase sleep up to 120s before the next poll.
- **Empty GPT text**: insert is skipped (warning), no TTS call.
- **systemd** (bare metal): run `python main.py` from a venv with `WorkingDirectory=` and `EnvironmentFile=` pointing at `.env`, `Restart=always` or `Restart=on-failure`.

---

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/
```

---

## Customizing the host

Edit the prompt in `generate_script()` in `main.py` (persona, language, length). Voice and models are controlled via `.env`.

---

## License

MIT — see [LICENSE](LICENSE).

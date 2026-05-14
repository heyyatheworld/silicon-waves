# Silicon Waves

An AI radio host for a cyberpunk-style internet radio station. It watches your [AzuraCast](https://www.azuracast.com/) stream, generates short lead-ins with OpenAI, turns them into speech with ElevenLabs, then uploads the audio and pushes it to the front of the queue so it plays right after the current track.

## How it works

1. **Polls AzuraCast** every 15 seconds for now-playing and time remaining.
2. **When 40–70 seconds are left** on the current track, it:
   - Asks GPT (gpt-4o-mini) for a short, cynical, atmospheric host line between the last track and the next one.
   - Synthesizes that text with ElevenLabs (multilingual v2).
   - Uploads the MP3 to AzuraCast into the `ai_voiceovers` folder.
   - Requests that file to be played next (front of queue), then deletes the local file.
3. Waits ~70 seconds after a successful run to avoid duplicate segments.

## Requirements

- Python 3.10+
- AzuraCast instance with API access
- [OpenAI](https://platform.openai.com/) API key
- [ElevenLabs](https://elevenlabs.io/) API key and a voice ID

## Setup

1. Clone the repo and create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Create a `.env` in the project root with your keys (example below). **Do not commit `.env`** — it’s in `.gitignore`.

### Environment variables

**Required**

| Variable             | Description                                      |
|----------------------|--------------------------------------------------|
| `AZURA_API_KEY`      | AzuraCast API key (from Profile → API Keys)      |
| `BASE_URL`           | AzuraCast API base URL (no default), e.g. `https://radio.example/api` |
| `OPENAI_API_KEY`     | OpenAI API key                                   |
| `ELEVENLABS_API_KEY` | ElevenLabs API key                               |
| `VOICE_ID`           | ElevenLabs voice ID (e.g. from Voice Library)    |

**Optional** (defaults suit a typical install)

| Variable                   | Default | Description |
|----------------------------|---------|-------------|
| `STATION_ID`               | `1`     | Station ID |
| `REMOTE_DIR`               | `ai_voiceovers` | AzuraCast media folder for uploads |
| `POLL_INTERVAL_SEC`        | `15`    | Seconds between now-playing polls |
| `SEGMENT_REM_MIN`          | `40`    | Lower bound (exclusive) for “seconds left” window |
| `SEGMENT_REM_MAX`          | `70`    | Upper bound (exclusive) for that window |
| `UPLOAD_INDEX_WAIT_SEC`    | `5`     | Wait after upload before queue request |
| `POST_SEGMENT_SLEEP_SEC`   | `70`    | Cooldown after a successful segment |
| `OPENAI_MODEL`             | `gpt-4o-mini` | Chat completion model |
| `ELEVENLABS_TTS_MODEL`     | `eleven_multilingual_v2` | ElevenLabs TTS model |
| `REQUEST_TIMEOUT_SEC`      | `30`    | HTTP client timeout (used in a later stability step) |

Example `.env`:

```env
AZURA_API_KEY=your_azuracast_api_key
STATION_ID=1
BASE_URL=https://your-azuracast.example/api

OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
VOICE_ID=pNInz6obpgDQGcFmaJgB
```

## Run

```bash
python main.py
```

Leave it running; it will keep polling and generating host segments when the time window (40–70 seconds left) is hit.

## Tuning

- **Segment window**: Set `SEGMENT_REM_MIN` and `SEGMENT_REM_MAX` (exclusive bounds, same idea as the old `40 < rem < 70`).
- **Poll interval / cooldown**: `POLL_INTERVAL_SEC` and `POST_SEGMENT_SLEEP_SEC` in `.env`.
- **GPT style**: Edit the `prompt` in `generate_script()` in `main.py`.
- **Voice / models**: `VOICE_ID`, `OPENAI_MODEL`, and `ELEVENLABS_TTS_MODEL` in `.env`.

## License

MIT

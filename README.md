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

| Variable            | Description                                      |
|---------------------|--------------------------------------------------|
| `AZURA_API_KEY`     | AzuraCast API key (from Profile → API Keys)      |
| `STATION_ID`        | AzuraCast station ID (default: `1`)              |
| `BASE_URL`          | AzuraCast API base URL, e.g.                     |
| `OPENAI_API_KEY`    | OpenAI API key                                   |
| `ELEVENLABS_API_KEY`| ElevenLabs API key                               |
| `VOICE_ID`          | ElevenLabs voice ID (e.g. from Voice Library)    |

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

- **Segment window**: In `main.py`, the condition `40 < rem < 70` controls when a segment is generated. Adjust to match your track lengths and encoding delay.
- **Poll interval**: `time.sleep(15)` is how often it checks now-playing; `time.sleep(70)` is the cooldown after a successful segment.
- **GPT style**: Edit the `prompt` in `generate_script()` to change the host personality and tone.
- **Voice**: Change `VOICE_ID` in `.env` to use another ElevenLabs voice.

## License

MIT

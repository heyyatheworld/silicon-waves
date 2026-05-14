import os
import time

import requests
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs
from openai import OpenAI

from config import load_config

cfg = load_config()

openai_client = OpenAI(api_key=cfg.openai_api_key)
el_client = ElevenLabs(api_key=cfg.elevenlabs_api_key)


def _auth_headers():
    return {"Authorization": f"Bearer {cfg.azura_api_key}"}


def get_now_playing():
    """Fetch now-playing info via authorized request to the station."""
    url = f"{cfg.base_url}/station/{cfg.station_id}/nowplaying"
    headers = _auth_headers()

    try:
        res = requests.get(url, headers=headers).json()

        # If response is a list, take first item; otherwise use as-is
        data = res[0] if isinstance(res, list) else res

        np = data.get("now_playing", {})
        current = np.get("song", {}).get("text", "Unknown Song")

        nxt = data.get("playing_next", {})
        next_track = nxt.get("song", {}).get("text", "Next Track")

        remaining = int(np.get("remaining", 0))

        if current == "Unknown Song":
            print(
                f"📡 Station visible but track not determined. Status: {data.get('status', 'offline')}"
            )

        return current, next_track, remaining
    except Exception as e:
        print(f"⚠️ API error: {e}")
        return "Error", "Error", 0


def generate_script(current_track, next_track):
    """Generate host script via GPT."""
    prompt = f"""
    You are the charismatic host of the late-night cyberpunk radio "Silicon Waves".
    The track that just played: {current_track}.
    Up next: {next_track}.
    Write a very short lead-in (max 2 sentences).
    Style: cynical, atmospheric, futuristic, neon. Do not use quotes.
    """
    response = openai_client.chat.completions.create(
        model=cfg.openai_model,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def generate_voice(text, output_path):
    """Convert text to speech."""
    print("🎙️ Synthesizing voice...")
    response = el_client.text_to_speech.convert(
        voice_id=cfg.voice_id,
        output_format="mp3_44100_128",
        text=text,
        model_id=cfg.elevenlabs_tts_model,
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
    url = f"{cfg.base_url}/station/{cfg.station_id}/files/upload"
    params = {"currentDirectory": remote_folder}
    headers = {**_auth_headers(), "Accept": "application/json"}

    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f, "audio/mpeg")}
        res = requests.post(url, headers=headers, params=params, files=files)
    return res.status_code == 200


def request_next_in_queue(remote_path):
    headers = {**_auth_headers(), "Accept": "application/json"}

    # 1. Find file ID first
    files_url = f"{cfg.base_url}/station/{cfg.station_id}/files"
    files_res = requests.get(files_url, headers=headers).json()

    media_id = None
    for item in files_res:
        if item["path"] == remote_path:
            media_id = item["unique_id"]
            break

    if media_id:
        # 2. Try POST to /queue with is_top if AzuraCast supports it
        queue_url = f"{cfg.base_url}/station/{cfg.station_id}/queue"
        payload = {
            "media_id": media_id,
            "is_top": True,  # Push to front of queue
        }
        res = requests.post(queue_url, json=payload, headers=headers)

        if res.status_code in [200, 201, 202]:
            print(f"🎯 Speech pushed to front of queue (ID: {media_id})")
        else:
            # If POST not supported (405), use standard GET request
            req_url = f"{cfg.base_url}/station/{cfg.station_id}/request/{media_id}"
            requests.get(req_url, headers=headers)
            print("🎯 Speech added to queue via standard request")
    else:
        print("⚠️ Could not find file ID")


# --- MAIN LOOP ---
print("🎙️ Robot host started...")

while True:
    try:
        current, next_t, rem = get_now_playing()
        print(f"Now: {current}. Time left: {rem} sec.")

        if cfg.segment_rem_min < rem < cfg.segment_rem_max:
            print("🤖 Generating segment...")
            script = generate_script(current, next_t)
            print(f"Script: {script}")

            file_name = f"speech_{int(time.time())}.mp3"
            generate_voice(script, file_name)

            if upload_to_azuracast(file_name, cfg.remote_dir):
                print("✅ Uploaded. Waiting for indexing...")
                time.sleep(cfg.upload_index_wait_sec)

                request_next_in_queue(f"{cfg.remote_dir}/{file_name}")

                if os.path.exists(file_name):
                    os.remove(file_name)

                print("⏳ Waiting for next track...")
                time.sleep(cfg.post_segment_sleep_sec)

    except Exception as e:
        print(f"⚠️ Error: {e}")

    time.sleep(cfg.poll_interval_sec)

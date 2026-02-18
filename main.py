import time
import os
import requests
from dotenv import load_dotenv
from openai import OpenAI
from elevenlabs import VoiceSettings
from elevenlabs.client import ElevenLabs

load_dotenv()

AZURA_API_KEY = os.getenv("AZURA_API_KEY")
STATION_ID = int(os.getenv("STATION_ID", "1"))
BASE_URL = os.getenv("BASE_URL", "http://139.59.212.80/api")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = os.getenv("VOICE_ID")

# Initialize clients
openai_client = OpenAI(api_key=OPENAI_API_KEY)
el_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

def get_now_playing():
    """Fetch now-playing info via authorized request to the station."""
    url = f"{BASE_URL}/station/{STATION_ID}/nowplaying"
    headers = {"Authorization": f"Bearer {AZURA_API_KEY}"}
    
    try:
        res = requests.get(url, headers=headers).json()
        
        # If response is a list, take first item; otherwise use as-is
        data = res[0] if isinstance(res, list) else res
        
        np = data.get('now_playing', {})
        current = np.get('song', {}).get('text', 'Unknown Song')
        
        nxt = data.get('playing_next', {})
        next_track = nxt.get('song', {}).get('text', 'Next Track')
        
        remaining = int(np.get('remaining', 0))
        
        if current == 'Unknown Song':
            print(f"📡 Station visible but track not determined. Status: {data.get('status', 'offline')}")
            
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
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

def generate_voice(text, output_path):
    """Convert text to speech."""
    print("🎙️ Synthesizing voice...")
    response = el_client.text_to_speech.convert(
        voice_id=VOICE_ID,
        output_format="mp3_44100_128",
        text=text,
        model_id="eleven_multilingual_v2",
        voice_settings=VoiceSettings(
            stability=0.5,
            similarity_boost=0.8,
            style=0.0,
            use_speaker_boost=True,
        ),
    )
    with open(output_path, "wb") as f:
        for chunk in response:
            if chunk: f.write(chunk)

def upload_to_azuracast(file_path, remote_folder):
    """Upload file to AzuraCast."""
    url = f"{BASE_URL}/station/{STATION_ID}/files/upload"
    params = {'currentDirectory': remote_folder}
    headers = {"Authorization": f"Bearer {AZURA_API_KEY}", "Accept": "application/json"}
    
    with open(file_path, 'rb') as f:
        files = {'file': (os.path.basename(file_path), f, 'audio/mpeg')}
        res = requests.post(url, headers=headers, params=params, files=files)
    return res.status_code == 200

def request_next_in_queue(remote_path):
    headers = {"Authorization": f"Bearer {AZURA_API_KEY}", "Accept": "application/json"}
    
    # 1. Find file ID first
    files_url = f"{BASE_URL}/station/{STATION_ID}/files"
    files_res = requests.get(files_url, headers=headers).json()
    
    media_id = None
    for item in files_res:
        if item['path'] == remote_path:
            media_id = item['unique_id']
            break
            
    if media_id:
        # 2. Try POST to /queue with is_top if AzuraCast supports it
        queue_url = f"{BASE_URL}/station/{STATION_ID}/queue"
        payload = {
            "media_id": media_id,
            "is_top": True  # Push to front of queue
        }
        res = requests.post(queue_url, json=payload, headers=headers)
        
        if res.status_code in [200, 201, 202]:
            print(f"🎯 Speech pushed to front of queue (ID: {media_id})")
        else:
            # If POST not supported (405), use standard GET request
            req_url = f"{BASE_URL}/station/{STATION_ID}/request/{media_id}"
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

        if 40 < rem < 70:
            print("🤖 Generating segment...")
            script = generate_script(current, next_t)
            print(f"Script: {script}")
            
            file_name = f"speech_{int(time.time())}.mp3"
            generate_voice(script, file_name)
            
            remote_dir = "ai_voiceovers"
            if upload_to_azuracast(file_name, remote_dir):
                print("✅ Uploaded. Waiting for indexing...")
                time.sleep(5)  # Give server time to index the file
                
                request_next_in_queue(f"{remote_dir}/{file_name}")
                
                if os.path.exists(file_name):
                    os.remove(file_name)
                
                print("⏳ Waiting for next track...")
                time.sleep(70) 
            
    except Exception as e:
        print(f"⚠️ Error: {e}")
    
    time.sleep(15)
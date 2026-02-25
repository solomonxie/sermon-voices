import os
import sys
import requests
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

load_dotenv()

def test_hf_asr(audio_path):
    print(f"🚀 Testing Hugging Face Inference API with: {audio_path}")
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        print("❌ HF_TOKEN not found in .env")
        return

    model_id = "openai/whisper-large-v3-turbo"
    api_url = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {"Authorization": f"Bearer {hf_token}"}

    try:
        with open(audio_path, "rb") as f:
            data = f.read()
        print(f"📤 Sending to {model_id}...")
        response = requests.post(api_url, headers=headers, data=data)
        if response.status_code == 200:
            result = response.json()
            print("✅ Transcription successful:")
            print("-" * 30)
            print(result.get("text"))
            print("-" * 30)
        else:
            print(f"❌ HF API Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ HF Inference Error: {e}")

if __name__ == "__main__":
    default_audio = "output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original.mp3"
    audio = sys.argv[1] if len(sys.argv) > 1 else default_audio
    test_hf_asr(audio)

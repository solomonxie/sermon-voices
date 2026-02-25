import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

load_dotenv()

def test_whisper_api(audio_path):
    print(f"🚀 Testing OpenAI Whisper API with: {audio_path}")
    if not os.path.exists(audio_path):
        print(f"❌ File not found: {audio_path}")
        return

    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not found in .env")
        return

    client = OpenAI()
    try:
        with open(audio_path, "rb") as f:
            print("📤 Uploading and transcribing...")
            res = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="zh"
            )
        print("✅ Transcription successful:")
        print("-" * 30)
        print(res.text)
        print("-" * 30)
    except Exception as e:
        print(f"❌ OpenAI Whisper API Error: {e}")

if __name__ == "__main__":
    # Use a small chunk or a sample file if available
    default_audio = "output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original.mp3"
    audio = sys.argv[1] if len(sys.argv) > 1 else default_audio
    test_whisper_api(audio)

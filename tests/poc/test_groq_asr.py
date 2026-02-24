import os
import sys
from dotenv import load_dotenv
from groq import Groq

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

load_dotenv()

def test_groq_asr(audio_path):
    print(f"🚀 Testing Groq (Whisper-large-v3) API with: {audio_path}")
    if not os.getenv("GROQ_API_KEY"):
        print("❌ GROQ_API_KEY not found in .env")
        return

    client = Groq()
    try:
        with open(audio_path, "rb") as f:
            print("📤 Uploading and transcribing...")
            res = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f,
                language="zh"
            )
        print("✅ Transcription successful:")
        print("-" * 30)
        print(res.text)
        print("-" * 30)
    except Exception as e:
        print(f"❌ Groq API Error: {e}")

if __name__ == "__main__":
    default_audio = "output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original.mp3"
    audio = sys.argv[1] if len(sys.argv) > 1 else default_audio
    test_groq_asr(audio)

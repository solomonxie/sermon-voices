import os
import sys
from dotenv import load_dotenv
from deepgram import DeepgramClient, PrerecordedOptions, FileSource

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

load_dotenv()

def test_deepgram_asr(audio_path):
    print(f"🚀 Testing Deepgram (Nova-2) API with: {audio_path}")
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        print("❌ DEEPGRAM_API_KEY not found in .env")
        return

    try:
        deepgram = DeepgramClient(api_key)
        with open(audio_path, "rb") as file:
            buffer_data = file.read()
        payload: FileSource = {"buffer": buffer_data}
        options = PrerecordedOptions(
            model="nova-2",
            smart_format=True,
            language="zh-CN"
        )
        print("📤 Sending to Deepgram...")
        res = deepgram.listen.rest.v("1").transcribe_file(payload, options)
        print("✅ Transcription successful:")
        print("-" * 30)
        print(res.results.channels[0].alternatives[0].transcript)
        print("-" * 30)
    except Exception as e:
        print(f"❌ Deepgram API Error: {e}")

if __name__ == "__main__":
    default_audio = "output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original.mp3"
    audio = sys.argv[1] if len(sys.argv) > 1 else default_audio
    test_deepgram_asr(audio)

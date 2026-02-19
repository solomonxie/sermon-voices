# Description: This script tests the GLM-ASR-Nano-2512 model for speech-to-text
# using the funasr library.
#
# Instructions:
# 1. Ensure dependencies are installed (funasr, torch, etc.)
# 2. Update the `AUDIO_FILE` variable if needed.

import os
import sys
import torch
from funasr import AutoModel

# --- Configuration ---
MODEL_ID = "zai-org/GLM-ASR-Nano-2512"
# Path to your audio file (trying to use the one from the project structure)
AUDIO_FILE = "output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original_cleaned.wav"
# ---------------------

def main():
    """
    Main function to run the GLM-ASR-Nano-2512 test.
    """
    # 1. Determine Device
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    
    print(f"Using device: {device}")

    # 2. Check Audio File
    audio_path = AUDIO_FILE
    if not os.path.exists(audio_path):
        print(f"⚠️ Audio file not found at '{audio_path}'")
        # Fallback to mp3 if wav doesn't exist
        mp3_path = audio_path.replace("_cleaned.wav", ".mp3")
        if os.path.exists(mp3_path):
            print(f"ℹ️ Found MP3 fallback: {mp3_path}")
            audio_path = mp3_path
        else:
            print("❌ No audio file found. Please update AUDIO_FILE in the script.")
            return

    # 3. Load Model
    print(f"🚀 Loading model: {MODEL_ID}...")
    try:
        # disable_update=True prevents checking for model updates every time
        model = AutoModel(model=MODEL_ID, device=device, disable_update=True)
        print("✅ Model loaded successfully.")
    except Exception as e:
        print(f"❌ Failed to load model '{MODEL_ID}'. Error: {e}")
        sys.exit(1)

    # 4. Transcribe
    print(f"🎙️ Transcribing {audio_path}...")
    try:
        # FunASR generate returns a list of results
        res = model.generate(input=audio_path, cache={})
        
        if res:
            print("\n--- Transcription Result ---")
            text = res[0]["text"] if "text" in res[0] else str(res)
            print(text)
            print("----------------------------\n")
        else:
            print("⚠️ No transcription result returned.")
            
    except Exception as e:
        print(f"❌ An error occurred during transcription: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

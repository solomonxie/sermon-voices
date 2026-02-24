# Description: This script tests the GLM-ASR-Nano-2512 model for speech-to-text.
#
# IMPORTANT: GLM-ASR-Nano-2512 uses the `glmasr` architecture, which is ONLY
# available in transformers>=5.0.0.dev0 (git main branch).
# Because this project's `qwen-asr` dependency strictly requires transformers==4.57.6,
# you CANNOT run this test in your main virtual environment without breaking it.
#
# Instructions to run in an isolated environment:
# 1. python -m venv venv_glm
# 2. source venv_glm/bin/activate
# 3. pip install git+https://github.com/huggingface/transformers.git torch torchaudio soundfile librosa
# 4. python tests/poc/test_glm_asr_nano.py

import os
import sys
import torch
import librosa
from transformers import AutoProcessor, AutoModelForSeq2SeqLM

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
        processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID, trust_remote_code=True)
        model.to(device)
        print("✅ Model loaded successfully.")
    except Exception as e:
        print(f"❌ Failed to load model '{MODEL_ID}'. Error: {e}")
        print("Note: Ensure you are running this in a dedicated virtual environment with `transformers` installed from the git main branch: pip install git+https://github.com/huggingface/transformers.git")
        sys.exit(1)

    # 4. Transcribe
    print(f"🎙️ Transcribing {audio_path}...")
    try:
        audio_array, sr = librosa.load(audio_path, sr=16000)
        
        # Processor method for GLM-ASR
        inputs = processor.apply_transcription_request(audio_array)
        
        # We need to move the tensors to device
        inputs = {k: v.to(device) if hasattr(v, "to") else v for k, v in inputs.items()}
        
        # The model uses BFloat16 natively. On MPS, float32 is often used as a fallback if bfloat16 errors out,
        # but let's let transformers handle it implicitly. 
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=128)
            
        text = processor.batch_decode(outputs, skip_special_tokens=True)[0].strip()

        print("\n--- Transcription Result ---")
        print(text)
        print("----------------------------\n")
            
    except Exception as e:
        print(f"❌ An error occurred during transcription: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

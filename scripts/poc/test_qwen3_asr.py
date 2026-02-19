# Description: This script tests the Qwen3-ASR-1.7B model for speech-to-text
# transcription using the qwen-asr library with the transformers backend.
#
# Instructions:
# 1. Install the qwen-asr library and its dependencies:
#    pip install -U qwen-asr torch
# 2. For GPU usage (recommended), ensure you have a compatible PyTorch version
#    with CUDA support.
# 3. Update the `AUDIO_FILE` variable to point to your audio file.

import sys
import torch
from pathlib import Path

try:
    from qwen_asr import Qwen3ASRModel
except ImportError:
    print("Please install the qwen-asr library: pip install -U qwen-asr")
    sys.exit(1)


# --- Configuration ---
MODEL_ID = "Qwen/Qwen3-ASR-1.7B"
# Path to your audio file
AUDIO_FILE = "output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original_cleaned.wav"
# ---------------------


def main():
    """
    Main function to run the Qwen3-ASR test.
    """
    if not Path(AUDIO_FILE).is_file():
        print(f"Error: Audio file not found at '{AUDIO_FILE}'")
        print("Please update the AUDIO_FILE variable.")
        sys.exit(1)

    # Determine the device and data type for the model
    if torch.cuda.is_available():
        device = "cuda:0"
        dtype = torch.bfloat16
        print("CUDA is available. Using GPU with bfloat16.")
    else:
        device = "cpu"
        dtype = torch.float32
        print("CUDA not available. Using CPU with float32.")

    print(f"Loading model: {MODEL_ID}...")
    try:
        model = Qwen3ASRModel.from_pretrained(
            MODEL_ID,
            dtype=dtype,
            device_map=device,
        )
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Failed to load model '{MODEL_ID}'. Error: {e}")
        print("Please ensure you have an internet connection and required dependencies.")
        sys.exit(1)


    print(f"Transcribing audio file: {AUDIO_FILE}...")
    # The `transcribe` method can take a list of audio paths
    try:
        # The result is a list of transcription objects
        results = model.transcribe(audio=[AUDIO_FILE])
    except Exception as e:
        print(f"An error occurred during transcription: {e}")
        sys.exit(1)

    # Print the transcription results
    if results:
        for r in results:
            print("\n--- Transcription ---")
            print(f"Language: {r.language}")
            print(f"Text: {r.text}")
            print("---------------------\n")
    else:
        print("Transcription failed. No results returned.")


if __name__ == "__main__":
    main()

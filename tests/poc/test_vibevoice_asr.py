# Description: This script tests the VibeVoice-ASR model for speech-to-text transcription
# using the mlx-audio library.
#
# Instructions:
# 1. Install the mlx-audio library:
#    pip install -U mlx-audio
# 2. Update the `AUDIO_FILE_PATH` variable to point to your audio file.
#    The audio should be in a format that can be processed (e.g., WAV).

import sys

try:
    from mlx_audio.stt.utils import load_model
    from mlx_audio.stt.generate import generate_transcription
except ImportError:
    print("Please install the mlx-audio library: pip install -U mlx-audio")
    sys.exit(1)


# --- Configuration ---
# You can specify different quantized models, e.g., "mlx-community/VibeVoice-ASR-5bit"
MODEL_ID = "mlx-community/VibeVoice-ASR-5bit"
# Path to your audio file
AUDIO_FILE_PATH = "output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original_cleaned.wav"
# ---------------------


def main():
    """
    Main function to run the VibeVoice-ASR test.
    """
    print(f"Loading model: {MODEL_ID}...")
    try:
        # The load_model function returns a tuple (model, processor)
        model, processor = load_model(MODEL_ID)
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Failed to load model '{MODEL_ID}'. Error: {e}")
        print("Please ensure you have an internet connection to download the model.")
        sys.exit(1)


    print(f"Transcribing audio file: {AUDIO_FILE_PATH}...")
    try:
        # generate_transcription returns a tuple (transcription, metadata)
        transcription_result, _ = generate_transcription(
            model=model,
            processor=processor,
            audio_path=AUDIO_FILE_PATH,
            format="txt",  # Output format (e.g., "txt", "srt", "json")
            verbose=True,
        )
    except FileNotFoundError:
        print(f"Error: Audio file not found at '{AUDIO_FILE_PATH}'")
        print("Please update the AUDIO_FILE_PATH variable.")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred during transcription: {e}")
        sys.exit(1)

    print("\n--- Transcription ---")
    print(transcription_result.text)
    print("---------------------\n")


if __name__ == "__main__":
    main()

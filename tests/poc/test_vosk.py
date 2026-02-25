# Description: This script tests the Vosk ASR model for speech-to-text transcription.
#
# Instructions:
# 1. Install the vosk library:
#    pip install vosk
# 2. Download the vosk-model-cn-0.22 model from https://alphacephei.com/vosk/models
# 3. Unzip the model and place it in a directory.
# 4. Update the `MODEL_PATH` variable to point to the model directory.
# 5. Update the `AUDIO_FILE` variable to point to your audio file.
#    The audio file must be a WAV file with a 16kHz sample rate and mono channel.

import sys
import os
import wave
import json

try:
    from vosk import Model, KaldiRecognizer, SetLogLevel
except ImportError:
    print("Please install the vosk library: pip install vosk")
    sys.exit(1)


# --- Configuration ---
# Path to the directory where you unzipped the vosk model
MODEL_PATH = "path/to/your/vosk-model-cn-0.22"
# Path to your audio file (must be a 16kHz mono WAV)
AUDIO_FILE = "output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original_cleaned.wav"
# ---------------------


def main():
    """
    Main function to run the Vosk ASR test.
    """
    SetLogLevel(0)

    if not os.path.exists(MODEL_PATH):
        print(f"Error: Vosk model folder not found at '{MODEL_PATH}'")
        print("Please download the model and update the MODEL_PATH variable.")
        sys.exit(1)

    if not os.path.exists(AUDIO_FILE):
        print(f"Error: Audio file not found at '{AUDIO_FILE}'")
        print("Please update the AUDIO_FILE variable.")
        sys.exit(1)

    print(f"Loading Vosk model from: {MODEL_PATH}")
    model = Model(MODEL_PATH)

    try:
        wf = wave.open(AUDIO_FILE, "rb")
    except wave.Error as e:
        print(f"Error opening WAV file: {e}")
        print("Please ensure the audio file is a valid WAV file.")
        sys.exit(1)

    if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
        print("Audio file must be WAV format, mono, 16-bit PCM.")
        print(f"'{AUDIO_FILE}' has {wf.getnchannels()} channels, {wf.getsampwidth()*8}-bit.")
        sys.exit(1)

    rec = KaldiRecognizer(model, wf.getframerate())
    rec.SetWords(True)

    print(f"Transcribing audio file: {AUDIO_FILE}...")

    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            print(f"Intermediate result: {result.get('text')}")

    final_result = json.loads(rec.FinalResult())
    print("\n--- Transcription ---")
    print(final_result.get('text'))
    print("---------------------\\n")

    wf.close()


if __name__ == "__main__":
    main()

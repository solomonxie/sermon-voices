"""
Not working well, can't distinguish speakers.
"""

import os
import torch
from pyannote.audio import Pipeline
from pydub import AudioSegment
from dotenv import load_dotenv

def main() -> None:
    # 1. Setup
    load_dotenv()
    access_token = os.getenv("HF_TOKEN")
    if not access_token:
        print("Error: HF_TOKEN not found in .env")
        return

    # Input file from the user's directory
    audio_path = "/Users/solomonxie/workspace/personal/sermon-voices/output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original.mp3"
    if not os.path.exists(audio_path):
        # Fallback to .wav if .mp3 not found
        audio_path = audio_path.replace(".mp3", "_cleaned.wav")
    
    if not os.path.exists(audio_path):
        print(f"Error: Audio file not found at {audio_path}")
        return

    output_dir = os.path.dirname(audio_path)
    
    # 2. Extract first 5 minutes
    print(f"Loading {audio_path}...")
    audio = AudioSegment.from_file(audio_path)
    # Take first 5 minutes (or full length if shorter)
    five_minutes_ms = 5 * 60 * 1000
    audio_5min = audio[:five_minutes_ms]
    
    # Use a specific temp name to avoid collisions
    temp_wav = os.path.join(output_dir, "temp_pyannote_crop.wav")
    audio_5min.export(temp_wav, format="wav")
    print(f"Exported 5min crop to {temp_wav}")

    # 3. Setup Pipeline
    print("Loading pyannote pipeline...")
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1", 
        token=access_token
    )

    # Use MPS for Mac GPU acceleration if available
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"Using device: {device}")
    pipeline.to(device)

    # 4. Run Diarization on the 5min crop
    print("Running diarization...")
    # num_speakers=2 is a good hint for these sermons (preacher + interpreter)
    diarization = pipeline(temp_wav, num_speakers=2)

    # 5. Process segments and extract speaker samples
    # Handle the pipeline output which might be a DiarizeOutput or Annotation
    annotation = diarization
    if hasattr(diarization, "speaker_diarization"):
        annotation = diarization.speaker_diarization
    elif isinstance(diarization, dict) and "annotation" in diarization:
        annotation = diarization["annotation"]

    speaker_audio = {}
    
    print("Cloning fragments for each speaker...")
    for segment, _, speaker in annotation.itertracks(yield_label=True):
        # pyannote uses seconds; pydub uses milliseconds
        start_ms = int(segment.start * 1000)
        end_ms = int(segment.end * 1000)
        
        # Crop from the 5min audio
        clip = audio_5min[start_ms:end_ms]
        
        if speaker not in speaker_audio:
            speaker_audio[speaker] = AudioSegment.empty()
        
        speaker_audio[speaker] += clip

    # 6. Export speaker samples
    for speaker, combined in speaker_audio.items():
        sample_path = os.path.join(output_dir, f"sample_{speaker}.wav")
        combined.export(sample_path, format="wav")
        print(f"Saved speaker sample: {sample_path}")

    # Cleanup
    if os.path.exists(temp_wav):
        os.remove(temp_wav)
    
    print("Done.")

if __name__ == "__main__":
    main()
"""
Test pyannote diarization:
-> result: doesn't work, can't distinguish between two mandarin speakers
"""
import os
import torch
from pyannote.audio import Pipeline
from pydub import AudioSegment
from dotenv import load_dotenv

# 1. Setup
load_dotenv()
access_token = os.getenv("HF_TOKEN")

audio_file = "/Users/solomonxie/workspace/personal/sermon-voices/output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original_cleaned.wav"
pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", token=access_token)

# Send to GPU if available
device = torch.device("mps")
pipeline.to(device)

# 2. Run Diarization
# Forcing num_speakers=2 improves accuracy for sermons
diarization = pipeline(audio_file, num_speakers=2)

# 3. Process and Save
audio = AudioSegment.from_wav(audio_file)
speaker_bins = {}

annotation = diarization
if hasattr(diarization, "speaker_diarization"):
    annotation = diarization.speaker_diarization

for segment, _, speaker in annotation.itertracks(yield_label=True):
    # pyannote uses seconds; pydub uses milliseconds
    start_ms = segment.start * 1000
    end_ms = segment.end * 1000
    
    excerpt = audio[start_ms:end_ms]
    
    if speaker not in speaker_bins:
        speaker_bins[speaker] = AudioSegment.empty()
    
    speaker_bins[speaker] += excerpt

# 4. Export
for speaker, combined_audio in speaker_bins.items():
    output_filename = audio_file.replace('.wav', f'_{speaker}.wav')
    combined_audio.export(output_filename, format="wav")
    print(f"Saved: {output_filename}")
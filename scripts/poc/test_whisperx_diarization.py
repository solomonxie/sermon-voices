"""
POC script to test WhisperX audio diarization.
Stack: faster-whisper, align_model, pyannote.audio (diarization)
-> result: doesn't work, can't distinguish between two mandarin speakers
-> and it's super super slow (on CPU, doesn't support Mac chip) takes 1 hour to process 1 hour audio
"""
import os
import torch
import whisperx
from dotenv import load_dotenv
from pydub import AudioSegment

# Load environment variables for HF_TOKEN
load_dotenv()

# Set model cache directory
MODEL_CACHE = os.path.expanduser('~/llm_models/whisperx')
os.makedirs(MODEL_CACHE, exist_ok=True)
os.environ["HF_HOME"] = os.path.expanduser('~/llm_models/huggingface')

def main():
    # 1. Configuration
    audio_file = "/Users/solomonxie/workspace/personal/sermon-voices/output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original.mp3"
    # Device selection: prefer CUDA, then CPU (faster-whisper doesn't support MPS)
    if torch.cuda.is_available():
        device = "cuda"
        compute_type = "float16"
    else:
        device = "cpu"
        compute_type = "float32"
    
    # MPS is supported for diarization (pyannote.audio)
    diarize_device = "mps" if torch.backends.mps.is_available() else device
    
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        print("❌ HF_TOKEN not found in environment. Diarization requires it.")
        return

    if not os.path.exists(audio_file):
        print(f"❌ Audio file not found: {audio_file}")
        return

    print(f"🚀 Initializing WhisperX on {device} ({compute_type})...")

    # 2. Transcribe with WhisperX (faster-whisper)
    print(f"🎙️ Transcribing with 'base' model: {audio_file}")
    model = whisperx.load_model("base", device, compute_type=compute_type, download_root=MODEL_CACHE)
    audio = whisperx.load_audio(audio_file)
    print("⏳ Running transcription...")
    result = model.transcribe(audio, batch_size=16)
    print(f"✅ Transcription complete. Detected language: {result['language']}")
    
    # 3. Align Whisper output
    print("🎯 Aligning transcription...")
    model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
    result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

    # 4. Diarization
    print(f"👥 Diarizing audio on {diarize_device}...")
    from whisperx.diarize import DiarizationPipeline
    diarize_model = DiarizationPipeline(token=hf_token, device=diarize_device)
    diarize_segments = diarize_model(audio)
    
    # 5. Assign speaker labels
    print("🏷️ Assigning speaker labels...")
    result = whisperx.assign_word_speakers(diarize_segments, result)

    # 6. Process and Print Results
    print("\n--- Transcription & Diarization Results ---")
    segments = result.get('segments', [])
    
    speaker_bins = {}
    pydub_audio = AudioSegment.from_file(audio_file)

    for seg in segments:
        speaker = seg.get('speaker', 'unknown')
        start = seg.get('start', 0)
        end = seg.get('end', 0)
        text = seg.get('text', '').strip()
        
        print(f"[{start:.2f}s - {end:.2f}s] Speaker {speaker}: {text}")
        
        start_ms = int(start * 1000)
        end_ms = int(end * 1000)
        
        if end_ms > start_ms:
            excerpt = pydub_audio[start_ms:end_ms]
            if speaker not in speaker_bins:
                speaker_bins[speaker] = AudioSegment.empty()
            speaker_bins[speaker] += excerpt

    # 7. Export Speaker Audios
    for speaker, combined_audio in speaker_bins.items():
        output_filename = audio_file.replace('.mp3', f'_whisperx_spk{speaker}.wav')
        combined_audio.export(output_filename, format="wav")
        print(f"✅ Saved speaker sample: {output_filename} ({len(combined_audio)/1000:.1f}s)")

if __name__ == "__main__":
    main()

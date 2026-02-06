import os
import json
from pydub import AudioSegment
from src.constants import OUTPUT_ROOT

def main() -> None:
    print(f"\n--- Phase 4: Text-to-Speech (Audio EN) ---")
    from glob import glob
    metadata_files = glob(os.path.join(OUTPUT_ROOT, '**/metadata.json'), recursive=True)
    for metadata_path in sorted(metadata_files):
        try:
            process_tts(metadata_path)
        except Exception as e:
            print(f"❌ Error processing TTS for {metadata_path}: {str(e)}")


def process_tts(metadata_path: str) -> None:
    """ Generates English audio from translated text with sampling and segmentation. """
    sermon_dir = os.path.dirname(metadata_path)
    audio_path = os.path.join(sermon_dir, 'original.mp3')
    translation_en_path = os.path.join(sermon_dir, 'translation_en.txt')
    
    if not os.path.exists(translation_en_path) or not os.path.exists(audio_path):
        return

    print(f"\n⚙️ Generating TTS: {sermon_dir}")
    
    # 1. Extract 1-min sample for voice cloning
    sample_path = os.path.join(sermon_dir, '_sample.mp3')
    if not os.path.exists(sample_path):
        print(f"✂️ Extracting 1-min sample for voice cloning...")
        try:
            audio = AudioSegment.from_mp3(audio_path)
            sample = audio[:60000] # First 60 seconds
            sample.export(sample_path, format="mp3")
        except Exception as e:
            print(f"⚠️ Failed to extract sample: {e}. Using original audio instead.")
            sample_path = audio_path

    with open(translation_en_path, 'r', encoding='utf-8') as f:
        full_text = f.read()

    audio_en_path = os.path.join(sermon_dir, 'audio_en.mp3')
    
    # 2. Segment text and generate TTS
    text_to_speech_segmented(full_text, sample_path, audio_en_path)
    print(f"✅ TTS generation complete: {audio_en_path}")


def text_to_speech_segmented(text: str, speaker_wav: str, output_path: str) -> None:
    """ Splits text into chunks and generates concatenated TTS audio. """
    print(f"🗣️ Generating Cloned Voice TTS (XTTS v2) with segmentation...")
    
    try:
        from TTS.api import TTS
        import torch
        # Load model with MPS (Metal) support if available
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        print(f"🖥️ Using device: {device}")

        model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
        tts = TTS(model_name).to(device)

        # Split text into chunks (around 200 characters each for XTTS stability)
        chunks = split_text(text, max_chars=250)
        print(f"📦 Split text into {len(chunks)} chunks.")

        combined_audio = AudioSegment.empty()
        
        for i, chunk in enumerate(chunks):
            print(f"  [{i+1}/{len(chunks)}] Processing chunk...")
            temp_path = f"temp_chunk_{i}.wav"
            tts.tts_to_file(
                text=chunk,
                speaker_wav=speaker_wav,
                language="en",
                file_path=temp_path
            )
            # Load and append
            chunk_audio = AudioSegment.from_wav(temp_path)
            combined_audio += chunk_audio
            # Cleanup temp file
            os.remove(temp_path)

        combined_audio.export(output_path, format="mp3")
        
    except Exception as e:
        print(f"⚠️ TTS generation failed: {e}")


def split_text(text: str, max_chars: int = 250) -> list[str]:
    """ Simple sentence-aware text splitter. """
    import re
    # Split by common sentence endings
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_chars:
            current_chunk += sentence + " "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


if __name__ == '__main__':
    main()

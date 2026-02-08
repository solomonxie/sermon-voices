import os
import json
from glob import glob
from pydub import AudioSegment
from src.common import ask_llm, get_custom_instructions
from src.constants import OUTPUT_ROOT

def main() -> None:
    print(f"\n--- Phase 3: Translation & Text-to-Speech (ZH -> EN) ---")
    metadata_files = glob(os.path.join(OUTPUT_ROOT, '**/metadata.json'), recursive=True)
    
    for metadata_path in sorted(metadata_files):
        sermon_dir = os.path.dirname(metadata_path)
        final_en = os.path.join(sermon_dir, 'translation_en.txt')
        final_audio_en = os.path.join(sermon_dir, 'audio_en.mp3')
        
        # Checkpoint: Skip if already processed (both translation and audio)
        if os.path.exists(final_en) and os.path.exists(final_audio_en):
            continue
            
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        print(f"\n⚙️ Processing Translation & TTS: {metadata.get('title')} ({metadata_path})")
        
        # 1. Translate Transcript
        transcript_zh_path = os.path.join(sermon_dir, 'transcript_zh.txt')
        if not os.path.exists(transcript_zh_path):
            print(f"⚠️ Transcript (ZH) not found: {transcript_zh_path}")
            continue

        if not os.path.exists(final_en):
            print(f"🌐 Translating to English...")
            with open(transcript_zh_path, 'r', encoding='utf-8') as f:
                content_zh = f.read()
            
            preacher_dir = os.path.dirname(os.path.dirname(sermon_dir))
            translation_instr = get_custom_instructions(preacher_dir, "translate.md")
            
            translation_en = translate_text(content_zh, custom_instructions=translation_instr)
            with open(final_en, 'w', encoding='utf-8') as f:
                f.write(translation_en)
            print(f"✅ Saved translation: {final_en}")
        else:
            with open(final_en, 'r', encoding='utf-8') as f:
                translation_en = f.read()

        # 2. Generate TTS
        if not os.path.exists(final_audio_en):
            try:
                process_tts(metadata_path, translation_en)
            except Exception as e:
                print(f"❌ Error processing TTS for {metadata_path}: {str(e)}")

        print(f"✅ Translation and TTS complete: {metadata['title']}")


def translate_text(text: str, custom_instructions: str = "") -> str:
    """
    Translates ZH text to EN (Biblical and Professional style).
    """
    prompt = f"""
    Translate the following Chinese sermon transcript to English based on these rules:
    1. BIBLICAL ACCURACY: Strictly follow biblical context.
    2. Use established English biblical names and terms (e.g., 'Zion' instead of 'Xi'an').
    3. NATIVE FLUENCY: Use professional, natural English suitable for a sermon.
    4. GRAMMATICAL CORRECTNESS: Ensure every phrase and sentence is grammatically correct and makes common sense.
    5. PRESERVE MEANING: Maintain the speaker's original intent and theological depth.
    Output MUST be a valid JSON object with a single key 'translation' containing the translated content.
    Do NOT include any markdown formatting, preamble, or footer.
    {custom_instructions}

    Content:
    {text}
    """
    try:
        data = ask_llm(prompt, num_ctx=8192)
        return data.get('translation', text)
    except Exception as e:
        print(f"⚠️ Translation failed, using original text: {e}")
        return text


def process_tts(metadata_path: str, full_text: str) -> None:
    """ Generates English audio from translated text with sampling and segmentation. """
    sermon_dir = os.path.dirname(metadata_path)
    audio_path = os.path.join(sermon_dir, 'original.mp3')
    audio_en_path = os.path.join(sermon_dir, 'audio_en.mp3')
    
    if not os.path.exists(audio_path):
        print(f"⚠️ Original audio not found: {audio_path}")
        return

    print(f"🎙️ Generating TTS for: {sermon_dir}")
    
    # Extract 1-min sample for voice cloning
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

    # Segment text and generate TTS
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

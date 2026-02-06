import os
import json
from src.common import ask_llm
from src.constants import OUTPUT_ROOT


def main() -> None:
    print(f"\n--- Phase 2: Audio Transcription, Refinement & Translation ---")
    from glob import glob
    metadata_files = glob(os.path.join(OUTPUT_ROOT, '**/metadata.json'), recursive=True)
    for metadata_path in sorted(metadata_files):
        try:
            process_audio(metadata_path)
        except Exception as e:
            print(f"❌ Error processing audio for {metadata_path}: {str(e)}")


def process_audio(metadata_path: str) -> None:
    """ 
    Transcribes, refines, and translates audio transcript.
    Leverages natural segmentation from transcription.
    """
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    sermon_dir = os.path.dirname(metadata_path)
    audio_path = os.path.join(sermon_dir, 'original.mp3')

    if not os.path.exists(audio_path):
        print(f"⚠️ Original audio not found for {metadata.get('title')}")
        return

    print(f"\n⚙️ Processing: {metadata.get('title')} ({metadata_path})")

    # 1. Incremental Transcription, Refinement, and Translation
    print(f"🎙️ Processing audio segments: {audio_path}")
    full_refined_zh = ""
    full_translated_en = ""
    
    for segment_text in transcript_audio(audio_path):
        # 1a. Refine ZH Transcript Segment
        refined_zh = refine_transcript(segment_text)
        full_refined_zh += refined_zh + "\n\n"
        
        # 1b. Translate to EN Segment (Native American Style)
        translated_en = translate_transcript(refined_zh)
        full_translated_en += translated_en + "\n\n"

    # 2. Save final transcripts
    transcript_zh_path = os.path.join(sermon_dir, 'transcript_zh.txt')
    with open(transcript_zh_path, 'w', encoding='utf-8') as f:
        f.write(full_refined_zh.strip() + "\n")
    print(f"✅ Saved refined ZH transcript: {transcript_zh_path}")

    translation_en_path = os.path.join(sermon_dir, 'translation_en.txt')
    with open(translation_en_path, 'w', encoding='utf-8') as f:
        f.write(full_translated_en.strip() + "\n")
    print(f"✅ Saved translation: {translation_en_path}")
    
    print(f"✅ Audio processing complete: {metadata['title']}")


def transcript_audio(audio_path: str):
    from faster_whisper import WhisperModel
    print(f"🎙️ Transcribing: {audio_path}")
    # Optimization for M1 Mac: large-v3 for best quality, int8 for speed/RAM efficiency on CPU
    model = WhisperModel(
        "large-v3",
        device="cpu",
        compute_type="int8",
        cpu_threads=8, # M1 has 8 cores
        download_root="models/whisper"
    )

    # Use a prompt to help with bilingual context and theological terms
    initial_prompt = "A sermon transcript containing both Mandarin and English. It includes biblical references and theological terms."

    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        initial_prompt=initial_prompt,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,   # split at 0.5s silence
            speech_pad_ms=200              # keep slight padding around speech
        )
    )
    for segment in segments:
        yield segment.text + " "


def refine_transcript(text: str) -> str:
    print(f"✍️ Refining ZH transcript segment...")
    prompt = f"""
    Refine this Chinese sermon transcript for punctuation, speaker identification, and character errors.
    Keep it verbatim but clean it up for reading.
    Content:
    {text[:8000]}
    """
    data = ask_llm(prompt, num_ctx=8192)
    return data.get('refined_text') or data.get('text') or str(data)


def translate_transcript(text: str) -> str:
    print(f"🌐 Translating to English (Native American style)...")
    prompt = f"""
    Translate the following Chinese sermon transcript to English.
    STRICT REQUIREMENT: Use native American English terms, idioms, and phrases. 
    It should sound like a native speaker born and raised in the US.
    Ensure biblical and theological accuracy and clear flow.
    Content:
    {text[:8000]}
    """
    data = ask_llm(prompt, num_ctx=8192)
    return data.get('translation') or data.get('translated_text') or str(data)


if __name__ == '__main__':
    main()

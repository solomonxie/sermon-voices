import os
import json
from src.common import ask_llm
from src.constants import OUTPUT_ROOT
from src.process_pdf import convert_to_markdown, convert_to_pdf, convert_to_latex


def main() -> None:
    print(f"\n--- Phase 2: Audio Processing ---")
    from glob import glob
    metadata_files = glob(os.path.join(OUTPUT_ROOT, '**/metadata.json'), recursive=True)
    for metadata_path in sorted(metadata_files):
        try:
            process_audio(metadata_path)
        except Exception as e:
            print(f"❌ Error processing audio for {metadata_path}: {str(e)}")


def process_audio(metadata_path: str) -> None:
    """ Processes audio tasks in memory and saves final results. """
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    sermon_dir = os.path.dirname(metadata_path)
    audio_path = os.path.join(sermon_dir, 'original.mp3')

    if not os.path.exists(audio_path):
        print(f"⚠️ Original audio not found for {metadata.get('title')}")
        return

    print(f"\n⚙️ Processing Audio: {metadata.get('title')} ({metadata_path})")

    # 1. Full-File Transcription (ZH)
    print(f"🎙️ Transcribing full audio: {audio_path}")
    raw_zh_text = "".join(list(transcript_audio(audio_path)))
    
    # 2. Refine ZH Transcript
    refined_zh_text = refine_transcript(raw_zh_text)
    transcript_zh_path = os.path.join(sermon_dir, 'transcript_zh.txt')
    with open(transcript_zh_path, 'w', encoding='utf-8') as f:
        f.write(refined_zh_text)
    print(f"✅ Saved refined ZH transcript: {transcript_zh_path}")

    # 3. Translate to EN (Native American Style)
    translated_en_text = translate_transcript(refined_zh_text)
    translation_en_path = os.path.join(sermon_dir, 'translation_en.txt')
    with open(translation_en_path, 'w', encoding='utf-8') as f:
        f.write(translated_en_text)
    print(f"✅ Saved translation: {translation_en_path}")

    # 4. Document Conversion (Markdown/PDF)
    markdown_path = os.path.join(sermon_dir, 'translation_en.md')
    convert_to_markdown(translated_en_text, markdown_path)

    pdf_path = os.path.join(sermon_dir, 'translation_en.pdf')
    convert_to_pdf(translated_en_text, pdf_path)
    
    latex_path = os.path.join(sermon_dir, 'translation_en.tex')
    convert_to_latex(markdown_path, latex_path)

    # 5. TTS (Optional step, keeping for completeness but can be simplified)
    audio_en_path = os.path.join(sermon_dir, 'audio_en.mp3')
    text_to_speech(translated_en_text, audio_path, audio_en_path)
    
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
    print(f"✍️ Refining ZH transcript...")
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


def text_to_speech(text: str, source_audio: str, output_path: str) -> str | None:
    print(f"🗣️ Generating Cloned Voice TTS (XTTS v2): {output_path}")
    try:
        from TTS.api import TTS
        import torch
        # Load model with MPS (Metal) support if available
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        print(f"🖥️ Using device: {device}")

        model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
        tts = TTS(model_name).to(device)

        tts.tts_to_file(
            text=text[:250], # Short sample due to TTS limits/speed
            speaker_wav=source_audio, # Use original audio as the voice clone source
            language="en",
            file_path=output_path
        )
        return output_path
    except Exception as e:
        print(f"⚠️ TTS generation failed: {e}")
        return None


if __name__ == '__main__':
    main()

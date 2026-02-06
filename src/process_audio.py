import os
import json
import shutil
from glob import glob
from pydub import AudioSegment

from src.common import ask_llm, load_translation_cache
from src.constants import OUTPUT_ROOT, BLOBS_ROOT
from src.process_metadata import save_metadata


def main() -> None:
    print(f"\n--- Phase 2: Audio Processing ---")
    metadata_files = glob(os.path.join(OUTPUT_ROOT, '**/metadata.json'), recursive=True)
    for metadata_path in metadata_files:
        try:
            process_audio(metadata_path)
        except Exception as e:
            print(f"❌ Error processing audio for {metadata_path}: {str(e)}")



def process_audio(metadata_path: str) -> None:
    """ Processes audio tasks based on the existence of target files. """
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    sermon_dir = os.path.dirname(metadata_path)
    audio_path = os.path.join(sermon_dir, 'original.mp3')
    chunks_dir = os.path.join(sermon_dir, 'chunks')

    if not os.path.exists(audio_path):
        print(f"⚠️ Original audio not found for {metadata.get('title')}")
        return

    print(f"\n⚙️ Processing Audio (Idempotent): {metadata.get('title')} ({metadata_path})")

    # 1. Chunking
    split_audio_into_chunks(audio_path)

    # 2. Chunk Transcription
    chunk_files = sorted(glob(os.path.join(chunks_dir, '0*.mp3')))
    if chunk_files:
        print(f"🎙️ Transcribing {len(chunk_files)} chunks...")
        for cf in chunk_files:
            transcript_audio(cf)

    # 3. Chunk Translation
    chunk_transcripts = sorted(glob(os.path.join(chunks_dir, '0*.txt')))
    # Filter to only include base transcripts (not translated/refined)
    chunk_transcripts = [ct for ct in chunk_transcripts if not ct.endswith(('_en.txt', '_refined.txt'))]
    if chunk_transcripts:
        print(f"🌐 Translating {len(chunk_transcripts)} chunk transcripts...")
        for ct in chunk_transcripts:
            translate_transcript(ct)

    # 4. Combine Translations
    combined_en_path = os.path.join(sermon_dir, 'transcript_en_combined.txt')
    if not os.path.exists(combined_en_path):
        print(f"🔗 Combining translated chunks...")
        chunk_translations = sorted(glob(os.path.join(chunks_dir, '0*_en.txt')))
        if chunk_translations:
            combined_text = ""
            for ct in chunk_translations:
                with open(ct, 'r', encoding='utf-8') as f:
                    combined_text += f.read() + "\n\n"
            with open(combined_en_path, 'w', encoding='utf-8') as f:
                f.write(combined_text)

    # 5. Refine Combined Translation
    refined_en_path = os.path.join(sermon_dir, 'transcript_en_refined.txt')
    if os.path.exists(combined_en_path) and not os.path.exists(refined_en_path):
        print(f"✍️ Refining final translation...")
        refine_transcript(combined_en_path)

    # 6. Document Conversion (Markdown/PDF)
    if os.path.exists(refined_en_path):
        markdown_path = os.path.join(sermon_dir, 'transcript_en_refined.md')
        if not os.path.exists(markdown_path):
            convert_to_markdown(refined_en_path)

        pdf_path = os.path.join(sermon_dir, 'transcript_en_refined.pdf')
        if os.path.exists(markdown_path) and not os.path.exists(pdf_path):
            latex_path = convert_to_latex(markdown_path)
            convert_to_pdf(latex_path)

    # 7. TTS
    audio_en_path = os.path.join(sermon_dir, 'audio_en.mp3')
    if os.path.exists(refined_en_path) and not os.path.exists(audio_en_path):
        text_to_speech(refined_en_path, audio_path)
        if os.path.exists(audio_en_path):
            print(f"✅ Audio processing complete: {metadata['title']}")


def split_audio_into_chunks(audio_path: str, chunk_length_ms: int = 60000) -> list[str]:
    """ Splits an audio file into chunks of specified length. """
    sermon_dir = os.path.dirname(audio_path)
    chunks_dir = os.path.join(sermon_dir, 'chunks')
    os.makedirs(chunks_dir, exist_ok=True)

    # Check if chunks already exist
    existing_chunks = sorted(glob(os.path.join(chunks_dir, '*.mp3')))
    if existing_chunks:
        print(f"⏩ Chunks already exist in {chunks_dir}")
        return existing_chunks

    print(f"🔪 Splitting audio into chunks: {audio_path}")
    audio = AudioSegment.from_file(audio_path)
    chunks = []
    for i, start_ms in enumerate(range(0, len(audio), chunk_length_ms)):
        chunk = audio[start_ms:start_ms + chunk_length_ms]
        chunk_name = f"{str(i+1).zfill(3)}.mp3"
        chunk_path = os.path.join(chunks_dir, chunk_name)
        chunk.export(chunk_path, format="mp3")
        chunks.append(chunk_path)
    return chunks


def transcript_audio(audio_path: str) -> str:
    from faster_whisper import WhisperModel
    if audio_path.endswith('original.mp3'):
        output_path = audio_path.replace('original.mp3', 'transcript_zh.txt')
    else:
        output_path = audio_path.rsplit('.', 1)[0] + '.txt'
    if os.path.exists(output_path):
        return output_path
    print(f"🎙️ Transcribing: {audio_path}")
    model = WhisperModel("small", device="cpu", compute_type="int8") # Use small/cpu for compatibility
    segments, info = model.transcribe(audio_path, beam_size=5)
    text = ""
    for segment in segments:
        text += f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}\n"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)
    return output_path


def refine_transcript(path: str) -> str:
    output_path = path.replace('_combined.txt', '_refined.txt')
    if '_combined.txt' not in path:
        output_path = path.replace('.txt', '_refined.txt')

    if os.path.exists(output_path):
        return output_path
    print(f"✍️ Refining transcript: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Use different prompt for translation refinement vs transcription refinement
    if '_en' in path or 'en' in path:
        prompt = f"""
        Refine this English sermon translation for biblical accuracy, theological depth, and natural native flow.
        Ensure it reads like a professional sermon transcript.
        Keep the meaning faithful to the original but improve the English style.
        Content:
        {content[:8000]}
        """
    else:
        prompt = f"Refine this sermon transcript for punctuation, speaker identification, and pinyin errors. Keep it verbatim but clean it up for reading:\n\n{content[:2000]}"

    content_refined = ask_llm(prompt, num_ctx=8192)
    if content_refined:
        # If the LLM returns a JSON object with 'refinement' or similar, handle it.
        if isinstance(content_refined, dict):
            content_refined = content_refined.get('refined_text') or content_refined.get('translation') or str(content_refined)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content_refined)
        return output_path
    return path


def convert_to_markdown(path: str) -> str:
    output_path = path.replace('.txt', '.md')
    if os.path.exists(output_path):
        return output_path
    print(f"📝 Generating Markdown: {output_path}")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    md_content = f"# Sermon Transcript\n\n**Source:** {os.path.basename(path)}\n\n---\n\n{content}"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    return output_path


def convert_to_latex(path: str) -> str:
    output_path = path.replace('.md', '.tex')
    if os.path.exists(output_path):
        return output_path
    print(f"📄 Generating LaTeX: {output_path}")
    with open(path, 'r', encoding='utf-8') as f:
        md_content = f.read()
    try:
        import pypandoc
        tex_content = pypandoc.convert_text(md_content, 'latex', format='markdown')
    except Exception:
        # Fallback to simple template
        tex_content = f"\\documentclass{{article}}\n\\usepackage[utf8]{{inputenc}}\n\\begin{{document}}\n{md_content}\n\\end{{document}}"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(tex_content)
    return output_path


def convert_to_pdf(path: str) -> str:
    output_path = path.replace('.tex', '.pdf')
    if os.path.exists(output_path):
        return output_path
    print(f"📊 Generating PDF: {output_path}")
    source_md = path.replace('.tex', '.md')
    with open(source_md, 'r', encoding='utf-8') as f:
        content = f.read()
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        # Handle multi-line text
        for line in content.split('\n'):
            pdf.multi_cell(0, 10, line.encode('latin-1', 'replace').decode('latin-1'))
        pdf.output(output_path)
    except Exception as e:
        print(f"⚠️ PDF generation failed: {e}")
    return output_path


def translate_transcript(path: str) -> str:
    if path.endswith('_zh.txt'):
        output_path = path.replace('_zh.txt', '_en.txt')
    else:
        output_path = path.rsplit('.', 1)[0] + '_en.txt'
    if os.path.exists(output_path):
        return output_path
    print(f"🌐 Translating (Ollama): {path}")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Process in chunks if too long
    chunk = content[:2500]
    prompt = f"""
    Translate the following sermon transcript to English.
    Use native american english terms, idioms and phrases to be as native as possible.
    Ensure biblical and theological accuracy and clear flow.
    Content:
    {chunk}
    """
    translated_text = ask_llm(prompt, num_ctx=8192)
    if translated_text:
        if isinstance(translated_text, dict):
            translated_text = translated_text.get('translation') or translated_text.get('translated_text') or str(translated_text)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(translated_text)
        return output_path
    return path


def text_to_speech(text_path: str, audio_path: str) -> str | None:
    output_path = audio_path.replace('original.mp3', 'audio_en.mp3')
    if os.path.exists(output_path):
        return output_path

    if not os.path.exists(text_path):
        print(f"⏩ Skipping TTS: Text file not found at {text_path}")
        return None

    print(f"🗣️ Generating Cloned Voice TTS (XTTS v2): {output_path}")
    try:
        from TTS.api import TTS
        import torch
        # Load model with MPS (Metal) support if available
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        print(f"🖥️ Using device: {device}")

        model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
        tts = TTS(model_name).to(device)

        with open(text_path, 'r', encoding='utf-8') as f:
            text = f.read()[:200] # Short sample for now to test

        tts.tts_to_file(
            text=text,
            speaker_wav=audio_path, # Use original audio as the voice clone source
            language="en",
            file_path=output_path
        )
        return output_path
    except Exception as e:
        print(f"⚠️ TTS generation failed: {e}. Check if 'TTS' library is properly configured.")
        return None


if __name__ == '__main__':
    main()

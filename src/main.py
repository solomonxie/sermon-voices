import os
import json
import shutil
import re
from glob import glob
from typing import Dict, Any, List
import ollama
from slugify import slugify
from pydub import AudioSegment

# Configuration
DEFAULT_MODEL = 'qwen3:8b'
OUTPUT_ROOT = './output'
BLOBS_ROOT = './blobs'
PROCESSED_LOG = os.path.join(OUTPUT_ROOT, 'processed.txt')


def main():
    """ Main entry point for the sermon processing pipeline. """
    print(f"🚀 Starting sermon processing pipeline...")

    print(f"\n--- Phase 1: Metadata Extraction ---")
    files = glob(os.path.join(BLOBS_ROOT, '**/*.mp3'), recursive=True)
    if not files:
        print(f"⚠️ No MP3 files found in {BLOBS_ROOT}")
        return
    # Phase 1: Metadata extraction
    processed_files = set()
    if os.path.exists(PROCESSED_LOG):
        with open(PROCESSED_LOG, 'r', encoding='utf-8') as f:
            processed_files = set(line.strip() for line in f if line.strip())
    for path in files:
        abs_path = os.path.abspath(path)
        if abs_path in processed_files:
            print(f'Skip processed file: {path}')
            continue
        try:
            process_metadata(path)
        except Exception as e:
            print(f"❌ Error extracting metadata for {path}: {str(e)}")

    # Phase 2: Audio Processing
    print(f"\n--- Phase 2: Audio Processing ---")
    metadata_files = glob(os.path.join(OUTPUT_ROOT, '**/metadata.json'), recursive=True)
    for metadata_path in metadata_files:
        try:
            process_audio(metadata_path)
        except Exception as e:
            print(f"❌ Error processing audio for {metadata_path}: {str(e)}")


def process_metadata(path: str):
    """ Extracts metadata and sets up the directory structure. """
    print(f"🔍 Extracting: {path}")

    # 1. Extraction
    metadata = extract_metadata(path)
    if not metadata:
        return

    # 1.1 Translation
    metadata = translate_metadata(metadata)

    # 1.2 Initial Status
    metadata['status'] = ["ok:metadata"]

    # 2. Directory Setup
    sermon_dir = get_sermon_dir(metadata)
    os.makedirs(sermon_dir, exist_ok=True)

    # 3. Move/Copy Original File
    original_path = os.path.join(sermon_dir, 'original.mp3')
    if not os.path.exists(original_path):
        shutil.copy2(path, original_path)

    # 4. Save Metadata
    save_metadata(sermon_dir, metadata)

    # 5. Add to processed log (Phase 1 complete)
    with open(PROCESSED_LOG, 'a', encoding='utf-8') as f:
        f.write(f"{os.path.abspath(metadata['original_path'])}\n")
    print(f"✅ Metadata extracted: {metadata['title']}")


def process_audio(metadata_path: str):
    """ Processes audio tasks based on the current status in metadata.json. """
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    sermon_dir = os.path.dirname(metadata_path)
    audio_path = os.path.join(sermon_dir, 'original.mp3')
    chunks_dir = os.path.join(sermon_dir, 'chunks')
    status = metadata.get('status', [])

    if not os.path.exists(audio_path):
        print(f"⚠️ Original audio not found for {metadata.get('title')}")
        return

    if "ok:metadata" not in status:
        return

    # Skip if fully completed
    if "ok:refined_en" in status:
        return

    print(f"\n⚙️ Processing Audio (Chunked): {metadata.get('title')} ({metadata_path})")

    # 1. Chunking
    if "ok:chunks" not in status:
        split_audio_into_chunks(audio_path)
        status.append("ok:chunks")
        save_metadata(sermon_dir, metadata)

    # 2. Chunk Transcription
    chunk_files = sorted(glob(os.path.join(chunks_dir, '*.mp3')))
    if "ok:chunk_transcripts" not in status:
        print(f"🎙️ Transcribing {len(chunk_files)} chunks...")
        for cf in chunk_files:
            transcript_audio(cf)
        status.append("ok:chunk_transcripts")
        save_metadata(sermon_dir, metadata)

    # 3. Chunk Translation
    chunk_transcripts = sorted(glob(os.path.join(chunks_dir, '0*.txt'))) # Matches 001.txt, etc.
    if "ok:chunk_translations" not in status:
        print(f"🌐 Translating {len(chunk_transcripts)} chunk transcripts...")
        for ct in chunk_transcripts:
            translate_transcript(ct)
        status.append("ok:chunk_translations")
        save_metadata(sermon_dir, metadata)

    # 4. Combine Translations
    combined_en_path = os.path.join(sermon_dir, 'transcript_en_combined.txt')
    if "ok:combined_en" not in status:
        print(f"🔗 Combining translated chunks...")
        chunk_translations = sorted(glob(os.path.join(chunks_dir, '0*_en.txt')))
        combined_text = ""
        for ct in chunk_translations:
            with open(ct, 'r', encoding='utf-8') as f:
                combined_text += f.read() + "\n\n"
        with open(combined_en_path, 'w', encoding='utf-8') as f:
            f.write(combined_text)
        status.append("ok:combined_en")
        save_metadata(sermon_dir, metadata)

    # 5. Refine Combined Translation
    refined_en_path = os.path.join(sermon_dir, 'transcript_en_refined.txt')
    if "ok:refined_en" not in status:
        print(f"✍️ Refining final translation...")
        refined_content = refine_transcript(combined_en_path)
        if refined_content and refined_content != combined_en_path:
            status.append("ok:refined_en")
            save_metadata(sermon_dir, metadata)

    # 6. Document Conversion (Markdown/PDF)
    if "ok:markdown" not in status and "ok:refined_en" in status:
        refined_en_path = os.path.join(sermon_dir, 'transcript_en_refined.txt')
        markdown_path = convert_to_markdown(refined_en_path)
        if markdown_path:
            status.append("ok:markdown")
            save_metadata(sermon_dir, metadata)

    if "ok:pdf" not in status and "ok:markdown" in status:
        markdown_path = os.path.join(sermon_dir, 'transcript_en_refined.md')
        latex_path = convert_to_latex(markdown_path)
        convert_to_pdf(latex_path)
        status.append("ok:pdf")
        save_metadata(sermon_dir, metadata)

    # 7. TTS
    if "ok:tts" not in status and "ok:refined_en" in status:
        refined_en_path = os.path.join(sermon_dir, 'transcript_en_refined.txt')
        audio_en_path = text_to_speech(refined_en_path, audio_path)
        if audio_en_path:
            status.append("ok:tts")
            save_metadata(sermon_dir, metadata)
            print(f"✅ Audio processing complete: {metadata['title']}")


def split_audio_into_chunks(audio_path: str, chunk_length_ms: int = 60000) -> List[str]:
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


def extract_preacher(path: str, model: str = None) -> str:
    hints = '\n'.join(os.path.dirname(path).replace('blobs/', '').split('/'))
    prompt = f"""
    Find the most probable preacher's name from the given path.
    Return JSON with ONLY the name in its ORIGINAL language as found in the path.
    DO NOT translate. DO NOT add any explanation.
    Example input: "blobs/唐崇荣/《唐崇荣-约翰福音》/约翰福音第01讲.mp3"
    Example output: {{"preacher": "唐崇荣"}}
    Hints:
    {hints}
    """
    resp = ask_llm(prompt, model=model, num_ctx=1024)
    answer = resp.get('preacher') or "unknown_preacher"
    print(f'\t Preacher: {answer}')
    return answer[-50:]


def extract_series(path: str, model: str = None) -> str:
    hints = '\n'.join(os.path.dirname(path).replace('blobs/', '').split('/'))
    prompt = f"""
    Find the most probable Bible book or sermon series name from the given hints.
    Return JSON with ONLY the name in its ORIGINAL language as found in the path.
    DO NOT translate. DO NOT add any explanation.
    Example input: "blobs/唐崇荣/《唐崇荣-约翰福音》/约翰福音第01讲.mp3"
    Example output: {{"series": "约翰福音"}}
    Hints:
    {hints}
    """
    resp = ask_llm(prompt, model=model, num_ctx=1024)
    answer = resp.get('series') or "series0"
    print(f'\t Series: {answer}')
    return answer[-50:]


def extract_title(path: str, model: str = None) -> str:
    hints = os.path.basename(path)
    prompt = f"""
    Find the specific sermon title from the given hints.
    Return JSON with ONLY the title in its ORIGINAL language as found in the path.
    DO NOT translate. DO NOT add any explanation.
    Example input: "20230621传道书042（7章6节）烧荆棘的爆声.mp3"
    Example output: {{"title": "烧荆棘的爆声"}}
    Hints:
    {path}
    """
    resp = ask_llm(prompt, model=model, num_ctx=1024)
    answer = resp.get('title') or "untitled"
    print(f'\t Title: {answer}')
    return answer[-50:]


def extract_scripture(path: str, model: str = None) -> str:
    hints = os.path.basename(path)
    prompt = f"""
    Find the specific Bible verses from the given hints.
    Return JSON with the result in English in the format:
    {{"scripture": "Bible Book chX:vY"}} .
    If not certain, return {{"scripture": "Unknown Book ch0:v0"}}
    DO NOT return JSON. DO NOT add any explanation.
    Example input: "20230621传道书042（7章6节）.mp3"
    Example output:
    {{"scripture": "Ecclesiastes ch7:v6"}}
    Hints:
    {hints}
    """
    resp = ask_llm(prompt, model=model, num_ctx=1024)
    answer = resp.get('scripture') or 'ch0:v0'
    print(f'\t Scripture: {answer}')
    return answer[-50:]


def extract_sequence(path: str, model: str = None) -> str:
    hints = os.path.basename(path)
    prompt = f"""
    Find the sequence number or lecture number of the sermon from the given hints.
    If no sequence is found, return "000".
    DO NOT add any explanation, only return answer.
    Example input: "约翰福音第01讲.mp3"
    Example output: {{"sequence": "1"}}
    Example input: "20230621传道书99.mp3"
    Example output: {{"sequence": "99"}}
    Hints:
    {hints}
    """
    resp = ask_llm(prompt, model=model, num_ctx=1024)
    answer = resp.get('sequence') or ''
    print(f'\t Sequence: {answer}')
    match = re.search(r'(\d+)', answer[-10:])
    if match:
        return match.group(1).zfill(3)
    return "000"


def extract_created_at(path: str, model: str = None) -> str:
    """ Extracts date (YYYYMMDD) from path or filename using LLM. """
    hints = os.path.basename(path)
    prompt = f"""
    Find the most probable creation date or preaching date from the given hints.
    Return JSON with ONLY the date in YYYYMMDD format.
    If not certain, return {{"created_at": "00000000"}}
    Example input: "2023.06.21传道书01.mp3"
    Example output: {{"created_at": "20230621"}}
    Hints:
    {hints}
    """
    resp = ask_llm(prompt, model=model, num_ctx=1024)
    answer = resp.get('created_at') or ''
    print(f'\t Created at: {answer}')
    match = re.search(r'(\d{8})', answer[-50:])
    if match:
        return match.group(1)
    return "00000000"


def extract_metadata(path: str, model: str = None) -> Dict[str, Any]:
    """ Uses modular extraction calls to gather metadata. """
    print(f"🔍 Extracting metadata for: {path}")
    return {
        "preacher": extract_preacher(path, model=model),
        "series": extract_series(path, model=model),
        "sequence": extract_sequence(path, model=model),
        "scripture": extract_scripture(path, model=model),
        "title": extract_title(path, model=model),
        "created_at": extract_created_at(path, model=model),
        "original_path": path
    }


def translate_metadata(metadata: dict) -> dict:
    """ Translates metadata fields to English using Christian context knowledge. """
    hints = 'Preacher: {}; Series: {}; Title: {}'.format(metadata['preacher'], metadata['series'], metadata['title'])
    prompt = f"""
    Translate the metadata.
    All translations should be in the context of Bible and Christianity knowledge.
    Translation prioritize knowledge, otherwise prefer phonetic translation.
    Return JSON object follow example below:
    Example intput: {{"preacher": "唐崇容", "series": "创世纪", "title": "上帝的大能"}}
    {{"preacher_en": "Stephen Tong", "series_en": "Genesis", "title_en": "The Power of God"}}
    If uncertain, use "Unknown" as value.
    Content:
    {hints}
    """
    resp = ask_llm(prompt, num_ctx=1024)
    print(f'\t Translated metadata: {resp}')
    metadata['preacher_en'] = resp.get('preacher_en')
    metadata['series_en'] = resp.get('series_en')
    metadata['title_en'] = resp.get('title_en')
    return metadata


def get_sermon_dir(metadata: dict) -> str:
    """ Generates a unique, slugified directory path for the sermon. """
    preacher_slug = slugify(metadata.get('preacher_en') or metadata.get('preacher') or 'unknown_preacher')
    series_slug = slugify(metadata.get('series_en') or metadata.get('series') or 'unamed_series')
    # Use scripture string for slug
    scripture_slug = slugify(metadata.get('scripture') or 'scripture0')
    sermon_slug = "{}_{}_{}_{}".format(
        slugify(str(metadata.get('sequence', '000'))),
        slugify(metadata.get('title_en') or metadata.get('title', 'untitled')),
        slugify(scripture_slug),
        slugify(str(metadata.get('created_at', '00000000')))
    )
    return os.path.join(OUTPUT_ROOT, preacher_slug, series_slug, sermon_slug)


def save_metadata(sermon_dir: str, metadata: dict):
    """ Persists metadata to metadata.json in the sermon directory. """
    metadata_path = os.path.join(sermon_dir, 'metadata.json')
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


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
        # But ask_llm is configured to return dict.
        # I should check if it's a string or dict.
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
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(translated_text)
        return output_path
    return path


def text_to_speech(text_path: str, audio_path: str) -> str:
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


def ask_llm(prompt: str, num_ctx: int = 4096, model: str = None, temperature: float = 0.0) -> dict:
    """ Centralized helper for Ollama LLM communication. """
    try:
        response = ollama.generate(
            model=model or DEFAULT_MODEL,
            prompt=prompt,
            format='json',
            options={
                "temperature": temperature,
                "show_think": True,
                "num_ctx": num_ctx,
                # "num_thread": 4,
                # Ollama on M1/Metal handles GPU acceleration automatically.
                # Removing num_thread allows the server to optimize for hardware.
            }
        )
    except Exception as e:
        print(f"⚠️ LLM Error with model {model or DEFAULT_MODEL}: {e}")
        raise e
    content = response['response']
    # Remove <think>...</think> tags
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    try:
        data = json.loads(content)
    except Exception as e:
        print(f'Failed to load answer to json: {content}\n{e}')
        raise e
    return data


if __name__ == '__main__':
    # Initial setup checks
    if not os.path.exists(OUTPUT_ROOT):
        os.makedirs(OUTPUT_ROOT)
    main()

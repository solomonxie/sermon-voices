import os
import json
import shutil
import re
from glob import glob
from typing import Dict, Any, List
import ollama
from slugify import slugify

# Configuration
DEFAULT_MODEL = 'qwen3:8b'
OUTPUT_ROOT = './output'
BLOBS_ROOT = './blobs'


def main():
    """ Main entry point for the sermon processing pipeline. """
    print(f"🚀 Starting sermon processing pipeline...")

    # Ensure raw files are available
    files = glob(os.path.join(BLOBS_ROOT, '**/*.mp3'), recursive=True)
    if not files:
        print(f"⚠️ No MP3 files found in {BLOBS_ROOT}")
        return

    for path in files:
        # Check if already processed (basic check)
        # We'll refine this inside process_sermon
        try:
            process_sermon(path)
        except Exception as e:
            print(f"❌ Error processing {path}: {str(e)}")
        break

def process_sermon(path: str):
    """ Processes a single sermon file through the full pipeline. """
    print(f"\n📂 Processing: {path}")

    # 0. Quick Check for Idempotency (Pre-Extraction)
    # We can't know the exact folder until we extract, but we can check if it exists in metadata.json cache
    # For now, we always extract metadata to be sure, unless we implement a central status.json

    # 1. Metadata Extraction
    original_metadata = extract_metadata(path)
    if not original_metadata:
        print(f"⏩ Skipping {path}: Could not extract metadata")
        return

    # 1.1 Metadata Refinement (translation)
    metadata = refine_metadata(original_metadata)

    # 2. Directory Setup
    sermon_dir = get_sermon_dir(metadata)

    # Check if already processed
    metadata_path = os.path.join(sermon_dir, 'metadata.json')
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
            if existing.get('processing', {}).get('status') == 'completed':
                print(f"⏭️  Already processed: {metadata['title']} (Skipping)")
                return

    os.makedirs(sermon_dir, exist_ok=True)

    # 3. Move Original File
    original_path = os.path.join(sermon_dir, 'original.mp3')
    if not os.path.exists(original_path):
        shutil.copy2(path, original_path)
        print(f"📝 Moved to: {sermon_dir}")

    # 4. Save Initial Metadata
    save_metadata(sermon_dir, metadata)
    return

    # 5. Transcription (Phase 2)
    transcript_path = transcript_audio(original_path)

    # 6. Refinement (Phase 3)
    refined_path = refine_transcript(transcript_path)

    # 7. Document Conversion (Phase 4)
    markdown_path = convert_to_markdown(refined_path)
    latex_path = convert_to_latex(markdown_path)
    convert_to_pdf(latex_path)

    # 8. Translation & TTS (Phase 5)
    translated_path = translate_transcript(transcript_path)
    audio_en_path = text_to_speech(translated_path, original_path)

    # 9. Final Metadata Update
    metadata['processing'] = {
        'status': 'completed',
        'steps': ['transcribed', 'refined', 'translated', 'tts_generated']
    }
    save_metadata(sermon_dir, metadata)
    print(f"✅ Successfully processed: {metadata['title']}")

def extract_preacher(path: str, model: str = None) -> str:
    hints = '\n'.join(path.split('/'))
    prompt = f"""
    Find the most probable preacher's name from the given path.
    Return ONLY the name in its ORIGINAL language as found in the path.
    DO NOT translate. DO NOT add any explanation.

    Hints:
    {hints}
    """
    return (ask_llm(prompt, model=model) or "unknown_preacher").strip().split('\n')[-1].strip(' "()')

def extract_series(path: str, model: str = None) -> str:
    hints = '\n'.join(path.split('/'))
    prompt = f"""
    Find the most probable Bible book or sermon series name from the given hints.
    Return ONLY the name in its ORIGINAL language as found in the path.
    DO NOT translate. DO NOT add any explanation.
    Example input: "blobs/唐崇荣/《唐崇荣-约翰福音》/约翰福音第01讲.mp3"
    Example output: "约翰福音"
    Hints:
    {hints}
    """
    return (ask_llm(prompt, model=model) or "series0").strip().split('\n')[-1].strip(' "()')

def extract_title(path: str, model: str = None) -> str:
    hints = '\n'.join(path.split('/'))
    prompt = f"""
    Find the specific sermon title from the given hints.
    Return ONLY the title in its ORIGINAL language as found in the path.
    DO NOT translate. DO NOT add any explanation.
    Example input: "20230621传道书042（7章6节）烧荆棘的爆声.mp3"
    Example output: "烧荆棘的爆声"
    Hints:
    {path}
    """
    return (ask_llm(prompt, model=model) or "untitled").strip().split('\n')[-1].strip(' "()《》')

def extract_scriptures(path: str, model: str = None) -> str:
    hints = '\n'.join(path.split('/'))
    prompt = f"""
    Find the specific Bible verses from the given hints.
    Return the result in the format: "Book chX:vY" (English book name).
    If multiple, return comma separated.
    If no specific verses found, return "Unknown".
    DO NOT return JSON. DO NOT add any explanation.
    Example input: "20230621传道书042（7章6节）烧荆棘的爆声.mp3"
    Example output: "Ecclesiastes ch7:v6"
    Hints:
    {hints}
    """
    result = ask_llm(prompt, model=model)
    if not result:
        return "Unknown"
    return result.strip().split('\n')[-1].strip(' "()《》')

def extract_created_at(path: str, model: str = None) -> str:
    """ Extracts date (YYYYMMDD) from path or filename using LLM. """
    hints = '\n'.join(path.split('/'))
    prompt = f"""
    Find the most probable creation date or preaching date from the given hints.
    Return ONLY the date in YYYYMMDD format.
    If no date is found, return "00000000".
    Hints:
    {path}
    """
    data = ask_llm(prompt, model=model)
    if not data:
        return "00000000"
    # Clean up any potential extra text from LLM
    match = re.search(r'(\d{8})', data)
    if match:
        return match.group(1)
    return "00000000"

def extract_metadata(path: str, model: str = None) -> Dict[str, Any]:
    """ Uses modular extraction calls to gather metadata. """
    print(f"🔍 Extracting metadata for: {path}")

    # Extract sequence based on file position in its original folder
    parent_dir = os.path.dirname(path)
    all_files = sorted([f for f in os.listdir(parent_dir) if f.lower().endswith('.mp3')])

    try:
        idx = all_files.index(os.path.basename(path))
        sequence = str(idx + 1).zfill(3)
    except ValueError:
        sequence = "000"

    return {
        "preacher": extract_preacher(path, model=model),
        "series": extract_series(path, model=model),
        "sequence": sequence,
        "scriptures": extract_scriptures(path, model=model),
        "title": extract_title(path, model=model),
        "created_at": extract_created_at(path, model=model),
        "original_path": path
    }

def refine_metadata(metadata: dict) -> dict:
    """ Translates metadata fields to English using Christian context knowledge. """
    prompt = f"""
    Translate the metadata for this sermon:
    {metadata}

    All translations should be in the context of Bible and Christianity knowledge.
    For preacher name translations, prioritize knowledge, otherwise prefer phonetic translation.
    For series name translations, prioritize knowledge, otherwise prefer phonetic translation.
    Return JSON object including keys preacher_en, series_en, title_en
    Example:
    {{
        "preacher_en": "John Piper",
        "series_en": "Ecclesiastes",
        "title_en": "The Power of God"
    }}
    """
    data = ask_llm(prompt, format='json', num_ctx=2048)
    if data:
        metadata.update(data)
    return metadata

def get_sermon_dir(metadata: dict) -> str:
    """ Generates a unique, slugified directory path for the sermon. """
    preacher_slug = slugify(metadata.get('preacher_en') or metadata.get('preacher') or 'unknown_preacher')
    series_slug = slugify(metadata.get('series_en') or metadata.get('series') or 'unamed_series')

    # Use scriptures string for slug
    scripture_slug = slugify(metadata.get('scriptures') or 'scripture0')

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
    output_path = audio_path.replace('original.mp3', 'transcript_zh.txt')
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
    output_path = path.replace('.txt', '_refined.txt')
    if os.path.exists(output_path):
        return output_path

    print(f"✍️ Refining transcript: {path}")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    prompt = f"Refine this sermon transcript for punctuation, speaker identification, and pinyin errors. Keep it verbatim but clean it up for reading:\n\n{content[:2000]}" # Limit context

    content_refined = ask_llm(prompt, num_ctx=8192)
    if content_refined:
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
    output_path = path.replace('_zh.txt', '_en.txt')
    if os.path.exists(output_path):
        return output_path

    print(f"🌐 Translating (Ollama): {path}")
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Process in chunks if too long
    chunk = content[:2500]
    prompt = f"Translate the following sermon transcript to English. Ensure theological accuracy and clear flow:\n\n{chunk}"

    translated_text = ask_llm(prompt, num_ctx=4096)
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



def ask_llm(prompt: str, format: str = None, num_ctx: int = 4096, model: str = None) -> Any:
    """ Centralized helper for Ollama LLM communication. """
    try:
        response = ollama.generate(
            model=model or DEFAULT_MODEL,
            prompt=prompt,
            format=format,
            options={
                "num_ctx": num_ctx,
                # "num_thread": 4,
                # Ollama on M1/Metal handles GPU acceleration automatically.
                # Removing num_thread allows the server to optimize for hardware.
            }
        )
        content = response['response']
        if format == 'json':
            return json.loads(content)
        return content
    except Exception as e:
        print(f"⚠️ LLM Error with model {model or DEFAULT_MODEL}: {e}")
        return None


if __name__ == '__main__':
    # Initial setup checks
    if not os.path.exists(OUTPUT_ROOT):
        os.makedirs(OUTPUT_ROOT)
    main()

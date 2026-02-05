import os
import json
import shutil
import re
from glob import glob
from typing import Dict, Any, List
import ollama
from slugify import slugify

# Configuration
DEFAULT_MODEL = 'llama3'
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
        try:
            process_sermon(path)
        except Exception as e:
            print(f"❌ Error processing {path}: {str(e)}")

def process_sermon(path: str):
    """ Processes a single sermon file through the full pipeline. """
    print(f"\n📂 Processing: {path}")
    
    # 1. Metadata Extraction
    metadata = extract_metadata(path)
    if not metadata:
        print(f"⏩ Skipping {path}: Could not extract metadata")
        return

    # 2. Directory Setup
    sermon_dir = get_sermon_dir(metadata)
    os.makedirs(sermon_dir, exist_ok=True)
    
    # 3. Move Original File
    original_path = os.path.join(sermon_dir, 'original.mp3')
    if not os.path.exists(original_path):
        shutil.copy2(path, original_path)
        print(f"📝 Moved to: {sermon_dir}")
    
    # 4. Save Initial Metadata
    save_metadata(sermon_dir, metadata)

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

def extract_metadata(path: str) -> Dict[str, Any]:
    """ Uses local LLM to extract structured metadata from the file path. """
    prompt = f"""
    Extract sermon metadata from this file path: "{path}"
    
    Return ONLY a JSON object with these keys:
    - preacher: List of speaker names (original)
    - series: List of series/book names (original)
    - sequence: Sequence string (e.g., "001")
    - scriptures: List of objects with [book (English), chapter (int), verses (string)]
    - title: Clean sermon title (original)
    - created_at: Date string (YYYY-MM-DD or "unknown")
    
    Example:
    {{
        "preacher": ["唐崇荣"],
        "series": ["罗马书"],
        "sequence": "001",
        "scriptures": [{{"book": "Romans", "chapter": 1, "verses": "16-17"}}],
        "title": "上帝的大能",
        "created_at": "2024-01-15"
    }}
    """
    
    try:
        response = ollama.generate(model=DEFAULT_MODEL, prompt=prompt, format='json')
        data = json.loads(response['response'])
        return data
    except Exception as e:
        print(f"⚠️ Metadata extraction failed for {path}: {e}")
        return None

def get_sermon_dir(metadata: dict) -> str:
    """ Generates a unique, slugified directory path for the sermon. """
    preacher_slug = slugify('_and_'.join(metadata.get('preacher', ['unknown'])))
    series_slug = slugify('_and_'.join(metadata.get('series', ['unknown'])))
    
    # Use first scripture for slug
    scripture_slug = "unknown"
    if metadata.get('scriptures'):
        s = metadata['scriptures'][0]
        scripture_slug = f"{s['book']}-{s['chapter']}-{s['verses']}"
    
    sermon_slug = "{}_{}_{}_{}".format(
        slugify(str(metadata.get('sequence', '000'))),
        slugify(metadata.get('title', 'untitled')),
        slugify(scripture_slug),
        slugify(metadata.get('created_at', 'unknown'))
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
    
    try:
        response = ollama.generate(model=DEFAULT_MODEL, prompt=prompt)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(response['response'])
        return output_path
    except Exception as e:
        print(f"⚠️ Refinement failed: {e}")
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
    
    try:
        response = ollama.generate(model=DEFAULT_MODEL, prompt=prompt)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(response['response'])
        return output_path
    except Exception as e:
        print(f"⚠️ Translation failed: {e}")
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
        # Load model (optimized for CPU/M1 if possible)
        model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
        tts = TTS(model_name).to("cpu") 
        
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
    # Initial setup checks
    if not os.path.exists(OUTPUT_ROOT):
        os.makedirs(OUTPUT_ROOT)
    main()

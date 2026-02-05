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
        # Check if already processed (basic check)
        # We'll refine this inside process_sermon
        try:
            process_sermon(path)
        except Exception as e:
            print(f"❌ Error processing {path}: {str(e)}")

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

CHINESE_BIBLE_BOOKS = {
    "创": "Genesis", "创世记": "Genesis", "出": "Exodus", "出埃及记": "Exodus",
    "利": "Leviticus", "利未记": "Leviticus", "民": "Numbers", "民数记": "Numbers",
    "申": "Deuteronomy", "申命记": "Deuteronomy", "约书亚记": "Joshua", "士": "Judges",
    "士师记": "Judges", "路": "Ruth", "路得记": "Ruth", "撒上": "1 Samuel",
    "撒母耳记上": "1 Samuel", "撒下": "2 Samuel", "撒母耳记下": "2 Samuel",
    "王上": "1 Kings", "列王纪上": "1 Kings", "王下": "2 Kings", "列王纪下": "2 Kings",
    "代上": "1 Chronicles", "历代志上": "1 Chronicles", "代下": "2 Chronicles",
    "历代志下": "2 Chronicles", "拉": "Ezra", "以斯拉记": "Ezra", "尼": "Nehemiah",
    "尼希米记": "Nehemiah", "斯": "Esther", "以斯帖记": "Esther", "伯": "Job",
    "约伯记": "Job", "诗": "Psalms", "诗篇": "Psalms", "箴": "Proverbs",
    "箴言": "Proverbs", "传": "Ecclesiastes", "传道书": "Ecclesiastes",
    "歌": "Song of Solomon", "雅歌": "Song of Solomon", "赛": "Isaiah",
    "以赛亚书": "Isaiah", "耶": "Jeremiah", "耶利米书": "Jeremiah", "哀": "Lamentations",
    "耶利米哀歌": "Lamentations", "结": "Ezekiel", "以西结书": "Ezekiel", "但": "Daniel",
    "但以理书": "Daniel", "何": "Hosea", "何西阿书": "Hosea", "约珥书": "Joel",
    "阿": "Amos", "阿摩司书": "Amos", "俄": "Obadiah", "俄巴底亚书": "Obadiah",
    "拿": "Jonah", "约拿书": "Jonah", "弥": "Micah", "弥迦书": "Micah", "鸿": "Nahum",
    "那鸿书": "Nahum", "合": "Habakkuk", "哈巴谷书": "Habakkuk", "番": "Zephaniah",
    "西番雅书": "Zephaniah", "该": "Haggai", "哈该书": "Haggai", "撒迦利亚书": "Zechariah",
    "玛": "Malachi", "玛拉基书": "Malachi", "太": "Matthew", "马太福音": "Matthew",
    "可": "Mark", "马可福音": "Mark", "路加福音": "Luke", "约": "John",
    "约翰福音": "John", "徒": "Acts", "使徒行传": "Acts", "罗": "Romans",
    "罗马书": "Romans", "林前": "1 Corinthians", "哥林多前书": "1 Corinthians",
    "林后": "2 Corinthians", "哥林多后书": "2 Corinthians", "加": "Galatians",
    "加拉太书": "Galatians", "弗": "Ephesians", "以弗所书": "Ephesians", "腓": "Philippians",
    "腓立比书": "Philippians", "西": "Colossians", "歌罗西书": "Colossians",
    "帖前": "1 Thessalonians", "帖撒罗尼迦前书": "1 Thessalonians", "帖后": "2 Thessalonians",
    "帖撒罗尼迦后书": "2 Thessalonians", "提上": "1 Timothy", "提摩太前书": "1 Timothy",
    "提下": "2 Timothy", "提摩太后书": "2 Timothy", "多": "Titus", "提多书": "Titus",
    "门": "Philemon", "腓利门书": "Philemon", "来": "Hebrews", "希伯来书": "Hebrews",
    "雅": "James", "雅各书": "James", "彼前": "1 Peter", "彼得前书": "1 Peter",
    "彼后": "2 Peter", "彼得后书": "2 Peter", "约一": "1 John", "约翰一书": "1 John",
    "约二": "2 John", "约翰二书": "2 John", "约三": "3 John", "约翰三书": "3 John",
    "犹": "Jude", "犹大书": "Jude", "启": "Revelation", "启示录": "Revelation"
}

def normalize_bible_book(name: str) -> str:
    """ Maps Chinese Bible book names (or abbreviations) to standard English names. """
    if not name:
        return "unknown"
    # Basic cleanup
    name = name.strip()
    return CHINESE_BIBLE_BOOKS.get(name, name)

def extract_metadata(path: str) -> Dict[str, Any]:
    """ Uses local LLM to extract structured metadata from the file path. """
    prompt = f"""
    You are an expert in Bible and Christianity knowledge. Scan this file path: "{path}"
    
    TASK: Extract original metadata EXACTLY as it appears in the path. 
    DO NOT TRANSLATE ANYTHING AT THIS STEP except for the "scriptures.book" field which MUST be standard English.

    GOAL:
    1. Preacher's Name: Look at parent folders first. Identify who is speaking (e.g., "华贤", "唐崇荣").
    2. Sermon Title: Find the core title of the message (e.g., "烧荆棘的爆声").
    3. Bible Book/Series: Identify the book of the Bible being discussed (e.g., "传道书", "罗马书").
    4. Scriptures: List the specific references (e.g., "Ecclesiastes", 7, "6").

    Return ONLY a JSON object:
    {{
        "preacher": "original Chinese name",
        "series": "original Chinese series/book name",
        "sequence": "3-digit sequence string",
        "scriptures": [{{"book": "English Bible Book", "chapter": int, "verses": "string"}}],
        "title": "original Chinese title",
        "created_at": "YYYY-MM-DD or unknown"
    }}

    Example:
    Path: "./blobs/华贤/20230621传道书042（7章6节）烧荆棘的爆声.mp3"
    Result:
    {{
        "preacher": "华贤",
        "series": "传道书",
        "sequence": "042",
        "scriptures": [{{"book": "Ecclesiastes", "chapter": 7, "verses": "6"}}],
        "title": "烧荆棘的爆声",
        "created_at": "2023-06-21"
    }}
    """
    
    try:
        response = ollama.generate(model=DEFAULT_MODEL, prompt=prompt, format='json')
        data = json.loads(response['response'])
        
        # Normalize scriptures
        if data.get('scriptures'):
            for s in data['scriptures']:
                s['book'] = normalize_bible_book(s['book'])
        
        data['original_path'] = path
        return data
    except Exception as e:
        print(f"⚠️ Metadata extraction failed for {path}: {e}")
        return None

def refine_metadata(metadata: dict) -> dict:
    """ Translates metadata fields to English using Christian context knowledge. """
    # Hardcoded known translations to help the model / override
    preacher_map = {
        "华贤": "Hua Xian",
        "唐崇荣": "Stephen Tong",
        "康来昌": "Kang Lai Chang"
    }
    
    metadata['preacher_en'] = preacher_map.get(metadata.get('preacher'), "")
    metadata['series_en'] = normalize_bible_book(metadata.get('series'))

    prompt = f"""
    Translate the following sermon title to theological English. 
    Original Title: {metadata.get('title')}
    Preacher: {metadata.get('preacher')}
    Bible Series: {metadata.get('series')}

    Return JSON with key "title_en" ONLY.
    Example: {{"title_en": "The Power of God"}}
    """
    try:
        # Only translate title if we have the rest
        if metadata.get('title'):
            response = ollama.generate(model=DEFAULT_MODEL, prompt=prompt, format='json')
            data = json.loads(response['response'])
            metadata['title_en'] = data.get('title_en', '')
        
        # Final cleanup for preacher_en and series_en if LLM missed them
        if not metadata.get('preacher_en'):
            # Fallback to phonetic if not in map
            metadata['preacher_en'] = slugify(metadata.get('preacher', 'unknown')).replace('-', ' ').title()
            
        return metadata
    except Exception as e:
        print(f"⚠️ Metadata refinement failed: {e}")
        return metadata

def get_sermon_dir(metadata: dict) -> str:
    """ Generates a unique, slugified directory path for the sermon. """
    preacher_slug = slugify(metadata.get('preacher_en') or metadata.get('preacher') or 'unknown')
    series_slug = slugify(metadata.get('series_en') or metadata.get('series') or 'unknown')
    
    # Use first scripture for slug
    scripture_slug = "unknown"
    if metadata.get('scriptures'):
        s = metadata['scriptures'][0]
        scripture_slug = f"{s['book']}-{s['chapter']}-{s['verses']}"
    
    sermon_slug = "{}_{}_{}_{}".format(
        slugify(str(metadata.get('sequence', '000'))),
        slugify(metadata.get('title_en') or metadata.get('title', 'untitled')),
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

import os
import json
import shutil
import re
from glob import glob
from slugify import slugify

from src.common import ask_llm, load_translation_cache, pad_numbers
from src.constants import OUTPUT_ROOT, BLOBS_ROOT, PROCESSED_LOG, TRANSLATION_MAP_PATH



def main() -> None:
    print(f"🚀 Starting sermon processing pipeline...")
    print(f"\n--- Phase 1: Metadata Extraction ---")
    files = glob(os.path.join(BLOBS_ROOT, '**/*.mp3'), recursive=True)
    if not files:
        print(f"⚠️ No MP3 files found in {BLOBS_ROOT}")
        return
    processed_files = set()
    if os.path.exists(PROCESSED_LOG):
        try:
            with open(PROCESSED_LOG, 'r', encoding='utf-8') as f:
                processed_files = set(line.strip() for line in f if line.strip())
        except Exception as e:
            print(f"⚠️ Error reading processed log: {e}")
    for path in files:
        abs_path = os.path.abspath(path)
        if abs_path in processed_files:
            # print(f'Skip processed file: {path}')
            continue
        try:
            process_metadata(path)
        except Exception as e:
            print(f"❌ Error extracting metadata for {path}: {str(e)}")


def process_metadata(path: str) -> None:
    """ Extracts metadata and sets up the directory structure. """
    print(f"🔍 Extracting: {path}")

    # 1. Extraction
    metadata = extract_metadata(path)
    if not metadata:
        return

    # 1.1 Translation
    metadata = translate_metadata(metadata)


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


def extract_preacher(path: str, model: str | None = None) -> str:
    hints = pad_numbers('\n'.join(os.path.dirname(path).replace('blobs/', '').split('/')))
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


def extract_series(path: str, model: str | None = None) -> str:
    hints = pad_numbers('\n'.join(os.path.dirname(path).replace('blobs/', '').split('/')))
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


def extract_title(path: str, model: str | None = None) -> str:
    hints = pad_numbers(path)
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


def extract_scripture(path: str, model: str | None = None) -> str:
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


def extract_sequence(path: str, model: str | None = None) -> str:
    hints = pad_numbers(os.path.basename(path))
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
    match = re.search(r'(\d+)', str(answer)[-10:])
    if match:
        return match.group(1).zfill(3)
    return "000"


def extract_created_at(path: str, model: str | None = None) -> str:
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
    match = re.search(r'(\d{8})', str(answer)[-50:])
    if match:
        return match.group(1)
    return "00000000"


def extract_metadata(path: str, model: str | None = None) -> dict[str, any]:
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


def save_translation_cache(cache: dict[str, str]) -> None:
    """ Saves the translation map to output/translation_map.txt. """
    try:
        with open(TRANSLATION_MAP_PATH, 'w', encoding='utf-8') as f:
            # Sort keys for consistency
            for original in sorted(cache.keys()):
                f.write(f"{original}: {cache[original]}\n")
    except Exception as e:
        print(f"⚠️ Error saving translation cache: {e}")


def translate_metadata(metadata: dict[str, any]) -> dict[str, any]:
    """ Translates metadata fields to English using Christian context knowledge. """
    cache = load_translation_cache()

    hints = 'Preacher: {}; Series: {}; Title: {}'.format(metadata['preacher'], metadata['series'], metadata['title'])
    prompt = f"""
    Translate the metadata.
    All translations should be in the context of Bible and Christianity knowledge.
    Translation prioritize knowledge, otherwise prefer phonetic translation.
    Return JSON object follow example below:
    Example intput: {{"preacher": "唐崇荣", "series": "创世纪", "title": "上帝的大能"}}
    {{"preacher_en": "Stephen Tong", "series_en": "Genesis", "title_en": "The Power of God"}}
    If uncertain, use "Unknown" as value.
    Content:
    {hints}
    """
    resp = ask_llm(prompt, num_ctx=1024)
    print(f'\t Translated metadata: {resp}')

    # Use cached translation if available for preacher and series
    metadata['preacher_en'] = cache.get(str(metadata['preacher'])) or resp.get('preacher_en') or 'Unknown'
    metadata['series_en'] = cache.get(str(metadata['series'])) or resp.get('series_en') or 'Unknown'
    metadata['title_en'] = resp.get('title_en')

    # Save cache if updated
    cache[str(metadata['preacher'])] = metadata['preacher_en']
    cache[str(metadata['series'])] = metadata['series_en']
    save_translation_cache(cache)
    return metadata


def get_sermon_dir(metadata: dict[str, any]) -> str:
    """ Generates a unique, slugified directory path for the sermon. """
    preacher_slug = slugify(str(metadata.get('preacher_en') or metadata.get('preacher') or 'unknown_preacher'))
    series_slug = slugify(str(metadata.get('series_en') or metadata.get('series') or 'unamed_series'))

    sermon_slug = "{}_{}".format(
        slugify(str(metadata.get('sequence', '000'))),
        slugify(str(metadata.get('title_en') or metadata.get('title', 'untitled')))
    )
    return os.path.join(OUTPUT_ROOT, preacher_slug, series_slug, sermon_slug)


def save_metadata(sermon_dir: str, metadata: dict[str, any]) -> None:
    """ Persists metadata to metadata.json in the sermon directory. """
    metadata_path = os.path.join(sermon_dir, 'metadata.json')
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    if not os.path.exists(OUTPUT_ROOT):
        os.makedirs(OUTPUT_ROOT)
    main()

import os
import re
import sys
import json
import shutil
from glob import glob
from pathlib import Path

from src.constants import OUTPUT_ROOT
from src.common import load_translation_cache, pad_numbers
from src.process_metadata import get_sermon_dir, save_metadata, save_translation_cache


def cleanup_title(title: str, sequence: str) -> str:
    if not title or not sequence:
        return title
    
    title = pad_numbers(title)

    padded_seq = str(sequence).zfill(3)
    int_seq = str(int(sequence))

    # Find all sequences of digits in the title
    numbers = re.findall(r'\d+', title)

    new_title = title
    for num in numbers:
        if num == padded_seq or num == int_seq:
            new_title = re.sub(rf'\s*{num}\s*', ' ', new_title)

    return new_title.strip()


def safe_move_content(src, dst):
    if not os.path.exists(dst):
        shutil.move(src, dst)
        return

    print(f"  Merging: {src} -> {dst}")
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.exists(d):
            if os.path.isdir(d):
                shutil.rmtree(d)
            else:
                os.remove(d)
        shutil.move(s, d)
    
    if not os.listdir(src):
        os.rmdir(src)


def main():
    print("🧹 Starting metadata refactoring...")
    cache = load_translation_cache()
    metadata_files = glob(os.path.join(OUTPUT_ROOT, '**/metadata.json'), recursive=True)

    for metadata_path in metadata_files:
        if not os.path.exists(metadata_path):
            continue

        print(f"📄 Processing: {metadata_path}")
        with open(metadata_path, 'r', encoding='utf-8') as f:
            try:
                metadata = json.load(f)
            except Exception as e:
                print(f"❌ Error loading {metadata_path}: {e}")
                continue

        # 1. Cleanup
        if 'status' in metadata:
            del metadata['status']

        sequence = metadata.get('sequence', '000')
        metadata['title'] = cleanup_title(metadata.get('title', ''), sequence)
        metadata['title_en'] = cleanup_title(metadata.get('title_en', ''), sequence)

        # 2. Sync with translation cache
        preacher = str(metadata.get('preacher', ''))
        preacher_en = metadata.get('preacher_en')
        if preacher:
            if preacher in cache:
                metadata['preacher_en'] = cache[preacher]
            elif preacher_en:
                cache[preacher] = preacher_en

        series = str(metadata.get('series', ''))
        series_en = metadata.get('series_en')
        if series:
            if series in cache:
                metadata['series_en'] = cache[series]
            elif series_en:
                cache[series] = series_en

        # 3. Reorganize directory if needed
        current_dir = os.path.abspath(os.path.dirname(metadata_path))
        new_dir = os.path.abspath(get_sermon_dir(metadata))

        if current_dir != new_dir:
            print(f"🚚 Moving: {current_dir} \n-> {new_dir}")
            os.makedirs(os.path.dirname(new_dir), exist_ok=True)
            safe_move_content(current_dir, new_dir)
            metadata_path = os.path.join(new_dir, 'metadata.json')

        # 4. Always save
        save_metadata(os.path.dirname(metadata_path), metadata)

    print("💾 Saving translation cache...")
    save_translation_cache(cache)
    print("✅ Complete")


if __name__ == '__main__':
    main()

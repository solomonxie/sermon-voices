import os
import re
import sys
import json
import shutil
from glob import glob
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.constants import OUTPUT_ROOT
from src.common import pad_numbers
from src.process_metadata import get_sermon_dir, save_metadata


def safe_move_content(src, dst):
    """
    Moves content from src to dst. If dst exists, merges contents.
    """
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


def get_max_sequence(series_path: str) -> int:
    """ Finds the maximum sequence number in a series folder. """
    max_seq = 0
    # Sermon folders are like "001_title", "012_title"
    sermon_dirs = [d for d in os.listdir(series_path) if os.path.isdir(os.path.join(series_path, d))]
    for d in sermon_dirs:
        match = re.match(r'^(\d{1,3})_', d)
        if match:
            seq = int(match.group(1))
            if seq > max_seq:
                max_seq = seq
    return max_seq


def main():
    print("🔢 Starting sequence number assignment...")

    # We need to group by series to find the max sequence correctly
    # Structure: output/<preacher>/<series>/<sermon_dir>
    preacher_dirs = [os.path.join(OUTPUT_ROOT, d) for d in os.listdir(OUTPUT_ROOT)
                    if os.path.isdir(os.path.join(OUTPUT_ROOT, d))]

    for preacher_path in preacher_dirs:
        series_dirs = [os.path.join(preacher_path, d) for d in os.listdir(preacher_path)
                      if os.path.isdir(os.path.join(preacher_path, d))]

        for series_path in series_dirs:
            # First, find the current max sequence in this series
            max_seq = get_max_sequence(series_path)

            # Now find all sermons in this series that are "000"
            sermon_dirs = sorted([os.path.join(series_path, d) for d in os.listdir(series_path)
                                if os.path.isdir(os.path.join(series_path, d)) and d.startswith('000_')])

            if not sermon_dirs:
                continue

            print(f"📁 Series: {os.path.basename(series_path)} (Max seq: {max_seq})")

            for current_dir in sermon_dirs:
                metadata_path = os.path.join(current_dir, 'metadata.json')
                if not os.path.exists(metadata_path):
                    continue

                with open(metadata_path, 'r', encoding='utf-8') as f:
                    try:
                        metadata = json.load(f)
                    except Exception as e:
                        print(f"  ❌ Error loading {metadata_path}: {e}")
                        continue

                # Double check that metadata also says 000
                if metadata.get('sequence', '000') == '000':
                    max_seq += 1
                    new_seq = str(max_seq).zfill(3)
                    print(f"  ✨ Assigning sequence {new_seq} to '{metadata.get('title')}'")

                    metadata['sequence'] = new_seq
                    # Also ensure titles are padded and cleaned (in case they weren't before)
                    metadata['title'] = pad_numbers(metadata.get('title', ''))
                    metadata['title_en'] = pad_numbers(metadata.get('title_en', ''))

                    # Reorganize
                    new_dir = os.path.abspath(get_sermon_dir(metadata))
                    if os.path.abspath(current_dir) != new_dir:
                        print(f"  🚚 Moving: {os.path.basename(current_dir)} -> {os.path.basename(new_dir)}")
                        os.makedirs(os.path.dirname(new_dir), exist_ok=True)
                        safe_move_content(current_dir, new_dir)
                        current_dir = new_dir

                    # Save metadata in the new location
                    save_metadata(current_dir, metadata)
    print("✅ Complete")


if __name__ == '__main__':
    main()

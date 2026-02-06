import os
from glob import glob

from common import BLOBS_ROOT, OUTPUT_ROOT, PROCESSED_LOG
from extract_metadata import process_metadata
from process_audio import process_audio


def main() -> None:
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

    # Phase 2: Audio Processing
    print(f"\n--- Phase 2: Audio Processing ---")
    metadata_files = glob(os.path.join(OUTPUT_ROOT, '**/metadata.json'), recursive=True)
    for metadata_path in metadata_files:
        try:
            process_audio(metadata_path)
        except Exception as e:
            print(f"❌ Error processing audio for {metadata_path}: {str(e)}")


if __name__ == '__main__':
    # Initial setup checks
    if not os.path.exists(OUTPUT_ROOT):
        os.makedirs(OUTPUT_ROOT)
    main()

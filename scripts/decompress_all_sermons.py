#!/usr/bin/env python3
"""
Production script to decompress ALL password-protected sermon archives.

Two-layer compression system:
- Layer 1: ZIP format, password "1234"
- Layer 2: 7Z format, password varies by year range

Usage:
    python3 scripts/decompress_all_sermons.py
"""

import os
import zipfile
import subprocess
import sys
from pathlib import Path
import shutil
from datetime import datetime

# Password mapping
PASSWORD_MAP = {
    # 1. 路 (Luke)
    '路001-040': '20132014',
    '路041-078': '20142015',
    '路079-120': '20152016',
    '路121-159': '20162017',
    '路160-200': '20172018',
    '路201-240': '20182019',
    '路241-280': '20192020',
    '路281-321': '20202021',
    # 2. 徒 (Acts)
    '徒001-040': '20142015',
    '徒041-080': '20152016',
    '徒081-120': '20162017',
    '徒121-160': '20172018',
    '徒161-200': '20182019',
    '徒201-240': '20192020',
    '徒241-260': '20202021',
    # 3. 箴 (Proverbs)
    '箴001-040': '20142015',
    '箴041-080': '20152016',
    '箴081-120': '20162017',
    '箴121-160': '20172018',
    '箴161-200': '20182019',
    '箴201-240': '20192020',
    '箴241-280': '20202021',
    '箴281-320': '2021',
    '箴321-360': '2022',
    '箴361-400': '2022',
    '箴401-413': '2022',
    # 4. 传 (Ecclesiastes)
    '传001-040': '2023',
    '传041-080': '20232024',
    '传081-093': '2024',
    # 5. 疑难解答 (Q&A)
    '疑难解答1-100': '20232024',
    '疑难解答101-200': '20232024',
    # 6. 约123 (1,2,3 John)
    '约123': '20242025',
}

FIRST_PASSWORD = '1234'

def find_password(filename):
    """Find password for a file."""
    basename = os.path.basename(filename)
    name_without_ext = os.path.splitext(basename)[0]

    if name_without_ext in PASSWORD_MAP:
        return PASSWORD_MAP[name_without_ext]

    for pattern, password in PASSWORD_MAP.items():
        if pattern in name_without_ext:
            return password

    return None

def extract_zip_layer(zip_file, output_dir, password):
    """Extract ZIP layer with streaming for large files."""
    try:
        os.makedirs(output_dir, exist_ok=True)

        with zipfile.ZipFile(zip_file, 'r') as zf:
            pwd = password.encode('utf-8')

            for file_info in zf.infolist():
                try:
                    # Decode Chinese filename
                    try:
                        filename = file_info.filename.encode('cp437').decode('gbk')
                    except:
                        filename = file_info.filename

                    extracted_path = output_dir / filename

                    # Handle directories
                    if file_info.is_dir():
                        extracted_path.mkdir(parents=True, exist_ok=True)
                        continue

                    # Create parent directories
                    extracted_path.parent.mkdir(parents=True, exist_ok=True)

                    # Stream extract file
                    print(f"    Extracting: {filename} ... ", end="", flush=True)
                    with zf.open(file_info, pwd=pwd) as source:
                        with open(extracted_path, 'wb') as target:
                            written = 0
                            while True:
                                chunk = source.read(1024 * 1024)  # 1MB chunks
                                if not chunk:
                                    break
                                target.write(chunk)
                                written += len(chunk)
                    print(f"{written / 1024 / 1024:.1f} MB ✓")

                except Exception as e:
                    print(f" ERROR: {e}")
                    return False

            return True

    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def extract_7z_layer(input_dir, output_dir, password):
    """Extract 7z files from input directory."""
    cmd_name = '7z' if shutil.which('7z') else '7za'
    seven_z_files = list(Path(input_dir).rglob('*.7z')) + list(Path(input_dir).rglob('*.7Z'))

    if not seven_z_files:
        return False, "No 7z files found"

    os.makedirs(output_dir, exist_ok=True)

    for sz_file in seven_z_files:
        try:
            print(f"    Extracting 7z: {sz_file.name} ... ", end="", flush=True)
            cmd = [cmd_name, 'x', f'-p{password}', '-y', str(sz_file), f'-o{output_dir}']
            result = subprocess.run(cmd, capture_output=True)

            if result.returncode != 0:
                print(f" ERROR")
                return False
            else:
                print(f" ✓")
        except Exception as e:
            print(f" ERROR: {e}")
            return False

    return True

def decompress_file(zip_file, base_output_dir):
    """Decompress a two-layer archive."""
    file_basename = os.path.basename(zip_file)
    print(f"\n{'='*70}")
    print(f"Processing: {file_basename}")
    print('='*70)

    # Find password
    second_password = find_password(zip_file)
    if not second_password:
        print("  ERROR: No password mapping found")
        return False, 0

    print(f"  Passwords: Layer1={FIRST_PASSWORD}, Layer2={second_password}")

    # Temporary directory for layer 1
    temp_dir = base_output_dir / '_temp' / file_basename
    temp_dir.mkdir(parents=True, exist_ok=True)

    # Extract layer 1 (ZIP)
    print(f"\n  Extracting Layer 1 (ZIP)...")
    if not extract_zip_layer(zip_file, temp_dir, FIRST_PASSWORD):
        return False, 0

    # Final output directory
    final_dir = base_output_dir / file_basename
    final_dir.mkdir(parents=True, exist_ok=True)

    # Extract layer 2 (7Z)
    print(f"\n  Extracting Layer 2 (7Z)...")
    if not extract_7z_layer(str(temp_dir), str(final_dir), second_password):
        print(f"  ERROR: Layer 2 extraction failed")
        return False, 0

    # Clean up temp directory
    shutil.rmtree(temp_dir, ignore_errors=True)

    # Count MP3 files
    mp3_files = list(final_dir.rglob('*.mp3')) + list(final_dir.rglob('*.MP3'))
    mp3_count = len(mp3_files)

    print(f"\n  ✓ SUCCESS: Extracted {mp3_count} MP3 files to {final_dir.relative_to(base_output_dir)}")

    return True, mp3_count

def main():
    start_time = datetime.now()

    print("="*70)
    print(" Sermon Archive Decompression Tool - Production Version")
    print("="*70)
    print()

    # Check for 7z
    if not (shutil.which('7z') or shutil.which('7za')):
        print("ERROR: 7z/7za not found!")
        print("Install with: brew install p7zip")
        return 1

    base_dir = Path(__file__).parent.parent / 'blobs' / '华贤全套查经系列（压缩版）'
    output_dir = Path(__file__).parent.parent / 'blobs' / '华贤_解压后'

    print(f"Source: {base_dir}")
    print(f"Output: {output_dir}")
    print()

    # Find all subdirectories
    subdirs = [
        '1路1-321全（zip文件）',
        '2徒1-260全（zip文件）',
        '3箴1-413全（zip文件）',
        # '4传1-93全（rar文件）',  # RAR format - needs different handling
        # '5疑难解答200全（rar文件）',
        # '6约123（rar文件）',
    ]

    total_files = 0
    success_files = 0
    total_mp3s = 0

    for subdir in subdirs:
        subdir_path = base_dir / subdir
        if not subdir_path.exists():
            print(f"Skipping {subdir} (not found)")
            continue

        print(f"\n{'#'*70}")
        print(f"# Directory: {subdir}")
        print(f"{'#'*70}")

        # Find compressed files
        files = [f for f in subdir_path.iterdir()
                if f.is_file() and not f.name.startswith('.') and not f.name.endswith('.txt')]

        print(f"\nFound {len(files)} archives to process\n")

        for file in sorted(files):
            total_files += 1
            success, mp3_count = decompress_file(str(file), output_dir / subdir)
            if success:
                success_files += 1
                total_mp3s += mp3_count

    # Clean up temp directory
    temp_dir = output_dir / '_temp'
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print(f"\n{'='*70}")
    print(" SUMMARY")
    print('='*70)
    print(f"  Archives processed: {success_files}/{total_files}")
    print(f"  Total MP3 files: {total_mp3s}")
    print(f"  Time elapsed: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"  Output directory: {output_dir}")
    print('='*70)

    return 0 if success_files == total_files else 1

if __name__ == '__main__':
    sys.exit(main())

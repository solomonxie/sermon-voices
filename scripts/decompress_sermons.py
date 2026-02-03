#!/usr/bin/env python3
"""
Decompress password-protected sermon archives.

The archives use two-layer compression:
1. First layer password: "1234" (always)
2. Second layer password: varies by file range (year-based)
"""

import os
import subprocess
import sys
from pathlib import Path
import shutil

# Password mapping based on the password file
# Format: (file_pattern, second_password)
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
    """Find the appropriate password for a given filename."""
    basename = os.path.basename(filename)
    # Remove extension if present
    name_without_ext = os.path.splitext(basename)[0]

    # Try exact match first
    if name_without_ext in PASSWORD_MAP:
        return PASSWORD_MAP[name_without_ext]

    # Try partial matches
    for pattern, password in PASSWORD_MAP.items():
        if pattern in name_without_ext:
            return password

    return None

def unzip_with_password(zip_file, output_dir, password):
    """Unzip a file with password using unzip command."""
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

        # Use unzip with password
        cmd = ['unzip', '-P', password, '-o', zip_file, '-d', output_dir]
        result = subprocess.run(cmd, capture_output=True)

        if result.returncode == 0:
            return True, None
        else:
            # Try to decode error, but don't fail if we can't
            try:
                error_msg = result.stderr.decode('utf-8')
            except:
                try:
                    error_msg = result.stderr.decode('gb2312')
                except:
                    error_msg = f"Error code: {result.returncode}"
            return False, error_msg
    except Exception as e:
        return False, str(e)

def decompress_file(zip_file, output_base_dir):
    """Decompress a two-layer compressed file."""
    print(f"\nProcessing: {zip_file}")

    # Find second layer password
    second_password = find_password(zip_file)
    if not second_password:
        print(f"  WARNING: No password mapping found for {os.path.basename(zip_file)}")
        return False

    print(f"  First password: {FIRST_PASSWORD}")
    print(f"  Second password: {second_password}")

    # Create temporary directory for first extraction
    temp_dir = output_base_dir / 'temp' / os.path.basename(zip_file)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # First extraction with password "1234"
    print(f"  Extracting layer 1...")
    success, error = unzip_with_password(zip_file, str(temp_dir), FIRST_PASSWORD)
    if not success:
        print(f"  ERROR in layer 1: {error}")
        return False

    # Find extracted zip files
    extracted_zips = list(temp_dir.glob('*.zip')) + list(temp_dir.glob('*.ZIP'))
    if not extracted_zips:
        print(f"  ERROR: No zip files found after first extraction")
        return False

    print(f"  Found {len(extracted_zips)} files in layer 1")

    # Create final output directory
    final_dir = output_base_dir / os.path.basename(zip_file)
    final_dir.mkdir(parents=True, exist_ok=True)

    # Second extraction with year-based password
    print(f"  Extracting layer 2...")
    all_success = True
    for inner_zip in extracted_zips:
        success, error = unzip_with_password(str(inner_zip), str(final_dir), second_password)
        if not success:
            print(f"  ERROR in layer 2 ({inner_zip.name}): {error}")
            all_success = False

    # Clean up temp directory
    shutil.rmtree(temp_dir)

    if all_success:
        print(f"  ✓ Successfully extracted to: {final_dir}")

    return all_success

def main():
    # Base directory
    base_dir = Path(__file__).parent.parent / 'blobs' / '华贤全套查经系列（压缩版）'
    output_dir = Path(__file__).parent.parent / 'blobs' / '华贤_解压后'

    print("=" * 60)
    print("Sermon Archive Decompression Tool")
    print("=" * 60)
    print(f"Source: {base_dir}")
    print(f"Output: {output_dir}")
    print()

    # Find all subdirectories with compressed files
    subdirs = [
        '1路1-321全（zip文件）',
        '2徒1-260全（zip文件）',
        '3箴1-413全（zip文件）',
        '4传1-93全（rar文件）',
        '5疑难解答200全（rar文件）',
        '6约123（rar文件）',
    ]

    total_files = 0
    success_count = 0

    for subdir in subdirs:
        subdir_path = base_dir / subdir
        if not subdir_path.exists():
            print(f"Skipping {subdir} (not found)")
            continue

        print(f"\n{'=' * 60}")
        print(f"Processing directory: {subdir}")
        print('=' * 60)

        # Find all compressed files (files without extension or with .zip/.rar)
        files = []
        for item in subdir_path.iterdir():
            if item.is_file() and not item.name.startswith('.') and not item.name.endswith('.txt'):
                files.append(item)

        print(f"Found {len(files)} files to decompress")

        for file in sorted(files):
            total_files += 1
            if decompress_file(str(file), output_dir / subdir):
                success_count += 1

    print(f"\n{'=' * 60}")
    print(f"Summary: {success_count}/{total_files} files successfully decompressed")
    print('=' * 60)

if __name__ == '__main__':
    main()

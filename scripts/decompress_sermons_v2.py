#!/usr/bin/env python3
"""
Decompress password-protected sermon archives using Python zipfile library.

The archives use two-layer compression:
1. First layer password: "1234" (always) - ZIP format
2. Second layer password: varies by file range (year-based) - 7Z format

Note: This script will extract the first layer. For 7z files, you'll need to install p7zip:
  brew install p7zip
"""

import os
import zipfile
import subprocess
import sys
from pathlib import Path
import shutil

# Password mapping based on the password file
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
    name_without_ext = os.path.splitext(basename)[0]

    # Try exact match first
    if name_without_ext in PASSWORD_MAP:
        return PASSWORD_MAP[name_without_ext]

    # Try partial matches
    for pattern, password in PASSWORD_MAP.items():
        if pattern in name_without_ext:
            return password

    return None

def extract_zip_layer1(zip_file, output_dir, password):
    """Extract first layer ZIP with password using Python zipfile."""
    try:
        os.makedirs(output_dir, exist_ok=True)

        with zipfile.ZipFile(zip_file, 'r') as zf:
            # Set password
            pwd = password.encode('utf-8')

            # List files
            file_list = zf.namelist()
            print(f"    Found {len(file_list)} files in archive")

            # Try different encodings for filenames
            for encoding in ['gbk', 'gb2312', 'utf-8', 'big5']:
                try:
                    # Extract all files
                    for file_info in zf.infolist():
                        try:
                            # Try to decode filename with current encoding
                            try:
                                filename = file_info.filename.encode('cp437').decode(encoding)
                            except:
                                filename = file_info.filename

                            # Extract file
                            extracted_path = os.path.join(output_dir, filename)
                            os.makedirs(os.path.dirname(extracted_path), exist_ok=True)

                            with zf.open(file_info, pwd=pwd) as source:
                                with open(extracted_path, 'wb') as target:
                                    target.write(source.read())

                        except Exception as e:
                            # Try without password
                            try:
                                with zf.open(file_info) as source:
                                    with open(extracted_path, 'wb') as target:
                                        target.write(source.read())
                            except:
                                continue

                    return True, None
                except Exception as e:
                    if encoding == 'big5':  # Last encoding to try
                        return False, str(e)
                    continue

            return False, "Could not decode filenames with any encoding"

    except Exception as e:
        return False, str(e)

def extract_7z_files(input_dir, output_dir, password):
    """Extract 7z files using 7z command if available."""
    # Check if 7z is available
    if shutil.which('7z') is None and shutil.which('7za') is None:
        return False, "7z/7za not found. Install with: brew install p7zip"

    cmd_name = '7z' if shutil.which('7z') else '7za'

    # Find all 7z files
    seven_z_files = list(Path(input_dir).rglob('*.7z')) + list(Path(input_dir).rglob('*.7Z'))

    if not seven_z_files:
        return False, "No 7z files found"

    print(f"    Found {len(seven_z_files)} 7z files")

    os.makedirs(output_dir, exist_ok=True)

    all_success = True
    for sz_file in seven_z_files:
        try:
            cmd = [cmd_name, 'x', f'-p{password}', '-y', str(sz_file), f'-o{output_dir}']
            result = subprocess.run(cmd, capture_output=True)

            if result.returncode != 0:
                print(f"      ERROR extracting {sz_file.name}")
                all_success = False
            else:
                print(f"      ✓ Extracted {sz_file.name}")

        except Exception as e:
            print(f"      ERROR: {e}")
            all_success = False

    return all_success, None if all_success else "Some 7z files failed to extract"

def decompress_file(zip_file, output_base_dir):
    """Decompress a two-layer compressed file."""
    print(f"\nProcessing: {os.path.basename(zip_file)}")

    # Find second layer password
    second_password = find_password(zip_file)
    if not second_password:
        print(f"  WARNING: No password mapping found")
        return False

    print(f"  Layer 1 password: {FIRST_PASSWORD}")
    print(f"  Layer 2 password: {second_password}")

    # Create temporary directory for first extraction
    temp_dir = output_base_dir / 'temp' / os.path.basename(zip_file)
    temp_dir.mkdir(parents=True, exist_ok=True)

    # First extraction with password "1234"
    print(f"  Extracting layer 1 (ZIP)...")
    success, error = extract_zip_layer1(zip_file, str(temp_dir), FIRST_PASSWORD)
    if not success:
        print(f"  ERROR in layer 1: {error}")
        return False

    # Create final output directory
    final_dir = output_base_dir / os.path.basename(zip_file)
    final_dir.mkdir(parents=True, exist_ok=True)

    # Second extraction with year-based password (7z format)
    print(f"  Extracting layer 2 (7Z)...")
    success, error = extract_7z_files(str(temp_dir), str(final_dir), second_password)

    if not success:
        print(f"  NOTE: {error}")
        print(f"  Layer 1 extracted to: {temp_dir}")
        print(f"  You can manually extract 7z files with: 7z x -p{second_password} file.7z")
    else:
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"  ✓ Successfully extracted to: {final_dir}")

    return success

def main():
    base_dir = Path(__file__).parent.parent / 'blobs' / '华贤全套查经系列（压缩版）'
    output_dir = Path(__file__).parent.parent / 'blobs' / '华贤_解压后'

    print("=" * 70)
    print("Sermon Archive Decompression Tool v2")
    print("=" * 70)
    print(f"Source: {base_dir}")
    print(f"Output: {output_dir}")
    print()

    # Check for 7z
    if shutil.which('7z') is None and shutil.which('7za') is None:
        print("WARNING: 7z/7za not found!")
        print("This script can extract layer 1 (ZIP), but you need p7zip for layer 2 (7Z)")
        print("Install with: brew install p7zip")
        print()
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            return

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
            continue

        print(f"\n{'=' * 70}")
        print(f"Processing directory: {subdir}")
        print('=' * 70)

        files = [f for f in subdir_path.iterdir()
                if f.is_file() and not f.name.startswith('.') and not f.name.endswith('.txt')]

        print(f"Found {len(files)} files to decompress\n")

        for file in sorted(files):
            total_files += 1
            if decompress_file(str(file), output_dir / subdir):
                success_count += 1

    print(f"\n{'=' * 70}")
    print(f"Summary: {success_count}/{total_files} files fully decompressed")
    print('=' * 70)

if __name__ == '__main__':
    main()

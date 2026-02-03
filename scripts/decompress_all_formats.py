#!/usr/bin/env python3
"""
Comprehensive decompression script for ALL sermon archive formats.
Handles: ZIP, RAR, 7Z files and copies already-extracted MP3s.
"""

import os
import zipfile
import subprocess
import sys
from pathlib import Path
import shutil
from datetime import datetime

# Password mapping (same as before)
PASSWORD_MAP = {
    # Luke
    '路001-040': '20132014', '路041-078': '20142015', '路079-120': '20152016',
    '路121-159': '20162017', '路160-200': '20172018', '路201-240': '20182019',
    '路241-280': '20192020', '路281-321': '20202021',
    # Acts
    '徒001-040': '20142015', '徒041-080': '20152016', '徒081-120': '20162017',
    '徒121-160': '20172018', '徒161-200': '20182019', '徒201-240': '20192020',
    '徒241-260': '20202021',
    # Proverbs
    '箴001-040': '20142015', '箴041-080': '20152016', '箴081-120': '20162017',
    '箴121-160': '20172018', '箴161-200': '20182019', '箴201-240': '20192020',
    '箴241-280': '20202021', '箴281-320': '2021', '箴321-360': '2022',
    '箴361-400': '2022', '箴401-413': '2022',
    # Ecclesiastes
    '传001-040': '2023', '传010-040': '2023',  # Added 010-040
    '传041-080': '20232024', '传081-093': '2024',
    # Q&A
    '疑难解答1-100': '20232024', '疑难解答101-200': '20232024',
    # 1,2,3 John
    '约123': '20242025',
    # 其他
    '五唯独': '2020',
    '周末录音': '20212022',
    '威敏信条': '20222025',
    '可（选查）': '2014',
    '可': '2014',
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
    """Extract ZIP with streaming."""
    try:
        os.makedirs(output_dir, exist_ok=True)
        with zipfile.ZipFile(zip_file, 'r') as zf:
            pwd = password.encode('utf-8')
            for file_info in zf.infolist():
                try:
                    try:
                        filename = file_info.filename.encode('cp437').decode('gbk')
                    except:
                        filename = file_info.filename

                    extracted_path = output_dir / filename

                    if file_info.is_dir():
                        extracted_path.mkdir(parents=True, exist_ok=True)
                        continue

                    extracted_path.parent.mkdir(parents=True, exist_ok=True)

                    print(f"    Extracting: {filename} ... ", end="", flush=True)
                    with zf.open(file_info, pwd=pwd) as source:
                        with open(extracted_path, 'wb') as target:
                            written = 0
                            while True:
                                chunk = source.read(1024 * 1024)
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

def extract_rar_file(rar_file, output_dir, password):
    """Extract RAR file using unar."""
    try:
        os.makedirs(output_dir, exist_ok=True)
        print(f"    Extracting RAR: {os.path.basename(rar_file)} ... ", end="", flush=True)

        cmd = ['unar', '-p', password, '-o', str(output_dir), str(rar_file)]
        result = subprocess.run(cmd, capture_output=True)

        if result.returncode == 0:
            print(f" ✓")
            return True
        else:
            # Try without password
            cmd = ['unar', '-o', str(output_dir), str(rar_file)]
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode == 0:
                print(f" ✓ (no password needed)")
                return True
            print(f" ERROR")
            return False
    except Exception as e:
        print(f" ERROR: {e}")
        return False

def extract_7z_file(sz_file, output_dir, password):
    """Extract 7z file."""
    try:
        os.makedirs(output_dir, exist_ok=True)
        print(f"    Extracting 7z: {sz_file.name} ... ", end="", flush=True)

        cmd_name = '7z' if shutil.which('7z') else '7za'
        cmd = [cmd_name, 'x', f'-p{password}', '-y', str(sz_file), f'-o{output_dir}']
        result = subprocess.run(cmd, capture_output=True)

        if result.returncode == 0:
            print(f" ✓")
            return True
        else:
            # Try without password
            cmd = [cmd_name, 'x', '-y', str(sz_file), f'-o{output_dir}']
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode == 0:
                print(f" ✓ (no password)")
                return True
            print(f" ERROR")
            return False
    except Exception as e:
        print(f" ERROR: {e}")
        return False

def process_zip_archive(zip_file, base_output_dir):
    """Process ZIP + 7Z two-layer archive."""
    file_basename = os.path.basename(zip_file)
    print(f"\n{'='*70}")
    print(f"Processing ZIP: {file_basename}")
    print('='*70)

    second_password = find_password(zip_file)
    if not second_password:
        print("  ERROR: No password mapping")
        return False, 0

    print(f"  Passwords: Layer1={FIRST_PASSWORD}, Layer2={second_password}")

    temp_dir = base_output_dir / '_temp' / file_basename
    temp_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  Extracting Layer 1 (ZIP)...")
    if not extract_zip_layer(zip_file, temp_dir, FIRST_PASSWORD):
        return False, 0

    final_dir = base_output_dir / file_basename
    final_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  Extracting Layer 2 (7Z)...")
    seven_z_files = list(temp_dir.rglob('*.7z')) + list(temp_dir.rglob('*.7Z'))

    for sz_file in seven_z_files:
        if not extract_7z_file(sz_file, str(final_dir), second_password):
            return False, 0

    shutil.rmtree(temp_dir, ignore_errors=True)

    mp3_files = list(final_dir.rglob('*.mp3')) + list(final_dir.rglob('*.MP3'))
    mp3_count = len(mp3_files)

    print(f"\n  ✓ SUCCESS: Extracted {mp3_count} MP3 files")
    return True, mp3_count

def process_rar_archive(rar_file, base_output_dir):
    """Process RAR archive (possibly two-layer)."""
    file_basename = os.path.basename(rar_file)
    print(f"\n{'='*70}")
    print(f"Processing RAR: {file_basename}")
    print('='*70)

    second_password = find_password(rar_file)
    password = second_password if second_password else FIRST_PASSWORD

    print(f"  Password: {password}")

    temp_dir = base_output_dir / '_temp' / file_basename
    temp_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n  Extracting RAR...")
    if not extract_rar_file(rar_file, temp_dir, password):
        return False, 0

    # Check for nested archives (7z or RAR)
    seven_z_files = list(temp_dir.rglob('*.7z')) + list(temp_dir.rglob('*.7Z'))
    rar_files = list(temp_dir.rglob('*.rar')) + list(temp_dir.rglob('*.RAR'))

    final_dir = base_output_dir / file_basename
    final_dir.mkdir(parents=True, exist_ok=True)

    if seven_z_files:
        print(f"\n  Extracting nested 7Z files...")
        for sz_file in seven_z_files:
            extract_7z_file(sz_file, str(final_dir), password)
        shutil.rmtree(temp_dir, ignore_errors=True)
    elif rar_files:
        print(f"\n  Extracting nested RAR files...")
        for nested_rar in rar_files:
            extract_rar_file(str(nested_rar), str(final_dir), password)
        shutil.rmtree(temp_dir, ignore_errors=True)
    else:
        # No nested archives, move extracted files
        shutil.rmtree(final_dir, ignore_errors=True)
        shutil.move(str(temp_dir), str(final_dir))

    mp3_files = list(final_dir.rglob('*.mp3')) + list(final_dir.rglob('*.MP3'))
    mp3_count = len(mp3_files)

    print(f"\n  ✓ SUCCESS: Extracted {mp3_count} MP3 files")
    return True, mp3_count

def process_7z_archive(sz_file, base_output_dir):
    """Process standalone 7Z archive."""
    file_basename = sz_file.stem
    print(f"\n{'='*70}")
    print(f"Processing 7Z: {sz_file.name}")
    print('='*70)

    password = find_password(str(sz_file))
    if not password:
        password = FIRST_PASSWORD

    print(f"  Password: {password}")

    final_dir = base_output_dir / file_basename
    final_dir.mkdir(parents=True, exist_ok=True)

    if not extract_7z_file(sz_file, str(final_dir), password):
        return False, 0

    mp3_files = list(final_dir.rglob('*.mp3')) + list(final_dir.rglob('*.MP3'))
    mp3_count = len(mp3_files)

    print(f"\n  ✓ SUCCESS: Extracted {mp3_count} MP3 files")
    return True, mp3_count

def copy_mp3_directory(src_dir, output_dir):
    """Copy already-extracted MP3s."""
    print(f"\n{'='*70}")
    print(f"Copying MP3s from: {src_dir.name}")
    print('='*70)

    dest_dir = output_dir / src_dir.name
    dest_dir.mkdir(parents=True, exist_ok=True)

    mp3_files = list(src_dir.rglob('*.mp3')) + list(src_dir.rglob('*.MP3'))

    for mp3_file in mp3_files:
        rel_path = mp3_file.relative_to(src_dir)
        dest_file = dest_dir / rel_path
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mp3_file, dest_file)

    print(f"  ✓ Copied {len(mp3_files)} MP3 files")
    return len(mp3_files)

def main():
    start_time = datetime.now()

    print("="*70)
    print(" Comprehensive Sermon Decompression - ALL Formats")
    print("="*70)
    print()

    base_dir = Path(__file__).parent.parent / 'blobs' / '华贤全套查经系列（压缩版）'
    output_dir = Path(__file__).parent.parent / 'blobs' / '华贤_解压后'

    print(f"Source: {base_dir}")
    print(f"Output: {output_dir}")
    print()

    total_mp3s = 0

    # Process all subdirectories
    for subdir in base_dir.iterdir():
        if not subdir.is_dir() or subdir.name.startswith('.'):
            continue

        print(f"\n{'#'*70}")
        print(f"# Directory: {subdir.name}")
        print(f"{'#'*70}")

        # Check if it's already MP3s (like 人物志)
        mp3_files = list(subdir.glob('*.mp3')) + list(subdir.glob('*.MP3'))
        if mp3_files and len(mp3_files) > 5:  # Likely already extracted
            mp3_count = copy_mp3_directory(subdir, output_dir)
            total_mp3s += mp3_count
            continue

        # Process compressed files
        for item in sorted(subdir.iterdir()):
            if item.is_file() and not item.name.startswith('.') and not item.name.endswith('.txt'):
                success, count = False, 0

                # Determine file type
                file_type = subprocess.run(['file', str(item)], capture_output=True, text=True).stdout.lower()

                if 'zip' in file_type or item.suffix.lower() == '.zip':
                    success, count = process_zip_archive(str(item), output_dir / subdir.name)
                elif 'rar' in file_type or item.suffix.lower() == '.rar':
                    success, count = process_rar_archive(str(item), output_dir / subdir.name)
                elif '7-zip' in file_type or item.suffix.lower() == '.7z':
                    success, count = process_7z_archive(item, output_dir / subdir.name)
                else:
                    # Try detecting by content
                    success, count = process_rar_archive(str(item), output_dir / subdir.name)

                if success:
                    total_mp3s += count

    # Process root-level RAR files
    root_rars = [
        base_dir / '原创诗歌赞美.rar',
        base_dir / '目录.rar',
    ]

    for rar_file in root_rars:
        if rar_file.exists():
            success, count = process_rar_archive(str(rar_file), output_dir)
            if success:
                total_mp3s += count

    # Clean up temp
    temp_dir = output_dir / '_temp'
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    # Summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print(f"\n{'='*70}")
    print(" FINAL SUMMARY")
    print('='*70)
    print(f"  Total MP3 files: {total_mp3s}")
    print(f"  Time elapsed: {duration:.1f} seconds ({duration/60:.1f} minutes)")
    print(f"  Output: {output_dir}")
    print('='*70)

    return 0

if __name__ == '__main__':
    sys.exit(main())

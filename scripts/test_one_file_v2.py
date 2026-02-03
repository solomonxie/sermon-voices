#!/usr/bin/env python3
"""Test decompression on a single file with streaming."""

import os
import zipfile
from pathlib import Path

zip_file = Path("blobs/华贤全套查经系列（压缩版）/1路1-321全（zip文件）/路001-040")
output_dir = Path("blobs/test_output")
password = "1234"
second_password = "20132014"

print(f"Testing file: {zip_file}")
print(f"Output: {output_dir}")
print(f"Password layer 1: {password}")
print(f"Password layer 2: {second_password}")
print()

output_dir.mkdir(parents=True, exist_ok=True)

try:
    with zipfile.ZipFile(zip_file, 'r') as zf:
        print(f"Opened ZIP file successfully")
        print(f"Files in archive:")

        for info in zf.infolist():
            print(f"  {info.filename} ({info.file_size / 1024 / 1024:.1f} MB)")

        print(f"\nExtracting files...")

        pwd = password.encode('utf-8')

        for file_info in zf.infolist():
            try:
                # Try to decode filename with GBK encoding (common for Chinese Windows)
                try:
                    filename = file_info.filename.encode('cp437').decode('gbk')
                except:
                    filename = file_info.filename

                print(f"  Extracting: {filename}", end="")

                extracted_path = output_dir / filename

                # Skip if it's a directory
                if file_info.is_dir():
                    extracted_path.mkdir(parents=True, exist_ok=True)
                    print(f" ... ✓ Directory created")
                    continue

                # Create parent directories
                extracted_path.parent.mkdir(parents=True, exist_ok=True)

                # Extract file with password (streaming)
                print(f" ... reading", end="", flush=True)
                with zf.open(file_info, pwd=pwd) as source:
                    with open(extracted_path, 'wb') as target:
                        # Stream in 1MB chunks
                        written = 0
                        while True:
                            chunk = source.read(1024 * 1024)  # 1MB chunks
                            if not chunk:
                                break
                            target.write(chunk)
                            written += len(chunk)
                            print(f"\r  Extracting: {filename} ... {written / 1024 / 1024:.1f} MB", end="", flush=True)

                print(f" ... ✓ Done")

            except Exception as e:
                print(f" ... ERROR: {e}")

        print(f"\n✓ Layer 1 extraction complete!")

        # Now extract the 7z file
        print(f"\nExtracting layer 2 (7z files)...")
        seven_z_files = list(output_dir.rglob('*.7z'))

        if seven_z_files:
            import subprocess
            for sz_file in seven_z_files:
                print(f"  Extracting: {sz_file.name}")
                final_dir = output_dir / "final"
                final_dir.mkdir(exist_ok=True)

                cmd = ['7z', 'x', f'-p{second_password}', '-y', str(sz_file), f'-o{final_dir}']
                result = subprocess.run(cmd, capture_output=True, text=False)

                if result.returncode == 0:
                    print(f"    ✓ Extracted successfully")

                    # Count extracted files
                    mp3_files = list(final_dir.rglob('*.mp3')) + list(final_dir.rglob('*.MP3'))
                    print(f"    Found {len(mp3_files)} MP3 files")

                else:
                    print(f"    ERROR: 7z extraction failed")
        else:
            print(f"  No 7z files found")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

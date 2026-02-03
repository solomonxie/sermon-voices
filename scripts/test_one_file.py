#!/usr/bin/env python3
"""Test decompression on a single file."""

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
            print(f"  {info.filename} ({info.file_size} bytes)")

        print(f"\nExtracting files...")

        pwd = password.encode('utf-8')

        for file_info in zf.infolist():
            try:
                # Try to decode filename with GBK encoding (common for Chinese Windows)
                try:
                    filename = file_info.filename.encode('cp437').decode('gbk')
                except:
                    filename = file_info.filename

                print(f"  Extracting: {filename}")

                extracted_path = output_dir / filename

                # Skip if it's a directory
                if file_info.is_dir():
                    extracted_path.mkdir(parents=True, exist_ok=True)
                    print(f"    ✓ Created directory")
                    continue

                # Create parent directories
                extracted_path.parent.mkdir(parents=True, exist_ok=True)

                # Extract file with password
                with zf.open(file_info, pwd=pwd) as source:
                    with open(extracted_path, 'wb') as target:
                        data = source.read()
                        target.write(data)
                        print(f"    ✓ Written {len(data)} bytes")

            except Exception as e:
                print(f"    ERROR: {e}")

        print(f"\n✓ Extraction complete!")
        print(f"Check output in: {output_dir}")

        # List extracted files
        print(f"\nExtracted files:")
        for item in output_dir.rglob('*'):
            if item.is_file():
                print(f"  {item.relative_to(output_dir)} ({item.stat().st_size} bytes)")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

# Scripts Directory

This directory contains utility scripts for the Sermon Voices project.

## Decompression Scripts

### decompress_all_sermons.py

**Purpose**: Decompress all password-protected sermon archives in bulk.

**Usage**:
```bash
python3 scripts/decompress_all_sermons.py
```

**Requirements**:
- Python 3.6+
- p7zip (`brew install p7zip` on macOS)

**What it does**:
1. Scans `blobs/华贤全套查经系列（压缩版）` for all sermon archives
2. Extracts Layer 1 (ZIP files with password "1234")
3. Extracts Layer 2 (7Z files with year-based passwords)
4. Outputs all MP3 files to `blobs/华贤_解压后`

**Archive Structure**:
```
Original Archive
├── Layer 1 (ZIP, password: 1234)
│   └── 密码：1234/
│       └── 001-040.7z
└── Layer 2 (7Z, password: varies by year)
    └── Sermon MP3 files
```

**Password Mapping**:
- First layer (all files): `1234`
- Second layer examples:
  - 路001-040 (Luke 1-40): `20132014`
  - 路041-078 (Luke 41-78): `20142015`
  - 徒001-040 (Acts 1-40): `20142015`
  - 箴001-040 (Proverbs 1-40): `20142015`
  - etc.

**Expected Output**:
- Luke (路): 321 sermons
- Acts (徒): 260 sermons
- Proverbs (箴): 413 sermons
- Ecclesiastes (传): 93 sermons (RAR format - not yet implemented)
- Q&A (疑难解答): 200 sermons (RAR format - not yet implemented)
- 1,2,3 John (约123): ~30 sermons (RAR format - not yet implemented)

**Total**: ~1000+ sermon MP3 files

### test_one_file_v2.py

**Purpose**: Test decompression on a single archive file.

**Usage**:
```bash
python3 scripts/test_one_file_v2.py
```

Useful for testing before running the full batch decompression.

## Other Scripts

### setup_dependencies.sh (TODO)

Will automate installation of all system dependencies.

### download_models.sh (TODO)

Will download required ML models (Whisper, Ollama, etc.).

## Notes

- The decompression scripts use streaming extraction to handle large files (400-500 MB each)
- Chinese filenames are properly decoded using GBK encoding
- Progress is shown during extraction with MB counters
- Extracted files maintain original Chinese naming with dates and titles
- Example: `2014.08.29路加福音034（2章13-14节）羞耻与荣耀，真平安.mp3`

## Troubleshooting

**Error: "7z/7za not found"**
```bash
brew install p7zip
```

**Error: "Encoding issues with Chinese filenames"**
- The scripts automatically handle GBK encoding
- If issues persist, check your terminal encoding: `echo $LANG`

**Error: "Permission denied"**
```bash
chmod +x scripts/*.py
```

**Slow extraction**
- Large archives (400-500 MB) take 2-5 minutes each
- Total time for all archives: 30-60 minutes
- This is normal due to file sizes

## Future Enhancements

- [ ] Add support for RAR format archives (4传, 5疑难解答, 6约123)
- [ ] Parallel processing of multiple archives
- [ ] Resume capability for interrupted extractions
- [ ] Verification of extracted MP3 files (file integrity check)
- [ ] Automatic organization of MP3 files by date/series

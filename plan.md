     ╭──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
     │ Sermon Metadata Extraction and File Organization Plan                                                                                    │
     │                                                                                                                                          │
     │ Task Summary                                                                                                                             │
     │                                                                                                                                          │
     │ Design and implement a system to:                                                                                                        │
     │ 1. Scan all MP3 files in blobs/                                                                                                          │
     │ 2. Extract metadata from folder structure and filenames (preacher, book, verse, date, title)                                             │
     │ 3. Generate metadata.json for each preacher                                                                                              │
     │ 4. Reorganize files into a proper structure: blobs/<preacher>/<year>/<series>/NNN_<title>_<date>.mp3                                     │
     │                                                                                                                                          │
     │ Current File Structure Analysis                                                                                                          │
     │                                                                                                                                          │
     │ Discovered Patterns:                                                                                                                     │
     │                                                                                                                                          │
     │ 华贤 (Huaxian) - Chinese preacher:                                                                                                       │
     │ - Directory: blobs/华贤全套查经系列（压缩版）/                                                                                           │
     │ - Filename format: YYYYMMDD<书卷名><编号>（<章节>）<标题>.mp3                                                                            │
     │ - Example: 20230621传道书042（7章6节）烧荆棘的爆声.mp3                                                                                   │
     │ - Extractable: date, book (传道书=Ecclesiastes), series number (042), verse (7:6), title                                                 │
     │                                                                                                                                          │
     │ 唐崇荣 (Tang Chongrong) - Indonesian-Chinese preacher:                                                                                   │
     │ - Directory: blobs/唐崇荣讲道集音频/                                                                                                     │
     │ - Organized in subdirectories by book/series (e.g., 《唐崇荣-创世记》, 《唐崇荣讲道集1》)                                                │
     │ - Multiple filename formats:                                                                                                             │
     │   - <书卷名><编号>.mp3 (e.g., 创世记001.mp3)                                                                                             │
     │   - <主题>-<标题><编号>.mp3 (e.g., 神的形像-人的潜能与危机001.mp3)                                                                       │
     │   - <标题>(编号).mp3 (e.g., 灵魂的价值(1).mp3)                                                                                           │
     │                                                                                                                                          │
     │ Other categories found:                                                                                                                  │
     │ - 原创诗歌赞美/ - Original hymns (范唱/伴奏 subdirectories)                                                                              │
     │ - Multiple sermon series per preacher                                                                                                    │
     │                                                                                                                                          │
     │ Metadata Schema Design                                                                                                                   │
     │                                                                                                                                          │
     │ metadata.json Structure                                                                                                                  │
     │                                                                                                                                          │
     │ Per-preacher metadata file: blobs/<preacher>/metadata.json                                                                               │
     │                                                                                                                                          │
     │ {                                                                                                                                        │
     │   "preacher": {                                                                                                                          │
     │     "name": "华贤",                                                                                                                      │
     │     "name_en": "Huaxian",                                                                                                                │
     │     "language": "zh",                                                                                                                    │
     │     "total_sermons": 1200                                                                                                                │
     │   },                                                                                                                                     │
     │   "last_updated": "2024-02-02T20:00:00Z",                                                                                                │
     │   "sermons": {                                                                                                                           │
     │     "huaxian_2023-06-21_chuandaoshu042": {                                                                                               │
     │       "id": "huaxian_2023-06-21_chuandaoshu042",                                                                                         │
     │       "original_path": "blobs/华贤全套查经系列（压缩版）/4传1-93全（rar文件）/密码20232024/20230621传道书042（7章6节）烧荆棘的爆声.mp3", │
     │       "new_path": "blobs/华贤/2023/传道书/042_烧荆棘的爆声_2023-06-21.mp3",                                                              │
     │       "title": "烧荆棘的爆声",                                                                                                           │
     │       "title_en": "The Sound of Burning Thorns",                                                                                         │
     │       "date": "2023-06-21",                                                                                                              │
     │       "duration_seconds": 1845,                                                                                                          │
     │       "file_size_bytes": 45678900,                                                                                                       │
     │       "language": "zh",                                                                                                                  │
     │       "series": {                                                                                                                        │
     │         "name": "传道书",                                                                                                                │
     │         "name_en": "Ecclesiastes",                                                                                                       │
     │         "number": 42,                                                                                                                    │
     │         "total_in_series": 93                                                                                                            │
     │       },                                                                                                                                 │
     │       "scripture_references": [                                                                                                          │
     │         {                                                                                                                                │
     │           "book": "Ecclesiastes",                                                                                                        │
     │           "book_zh": "传道书",                                                                                                           │
     │           "chapter": 7,                                                                                                                  │
     │           "verse_start": 6,                                                                                                              │
     │           "verse_end": 6,                                                                                                                │
     │           "reference": "Ecclesiastes 7:6"                                                                                                │
     │         }                                                                                                                                │
     │       ],                                                                                                                                 │
     │       "tags": ["wisdom", "vanity", "pleasure"],                                                                                          │
     │       "audio_metadata": {                                                                                                                │
     │         "format": "mp3",                                                                                                                 │
     │         "bitrate": 128,                                                                                                                  │
     │         "sample_rate": 44100,                                                                                                            │
     │         "channels": 2                                                                                                                    │
     │       }                                                                                                                                  │
     │     }                                                                                                                                    │
     │   }                                                                                                                                      │
     │ }                                                                                                                                        │
     │                                                                                                                                          │
     │ Key Metadata Fields:                                                                                                                     │
     │                                                                                                                                          │
     │ Sermon-level:                                                                                                                            │
     │ - id: Unique identifier (preacher_date_series)                                                                                           │
     │ - original_path: Current location                                                                                                        │
     │ - new_path: Target reorganized location                                                                                                  │
     │ - title: Extracted Chinese title                                                                                                         │
     │ - title_en: Optional English translation                                                                                                 │
     │ - date: Sermon date (if extractable)                                                                                                     │
     │ - duration_seconds: Audio length                                                                                                         │
     │ - file_size_bytes: File size                                                                                                             │
     │ - language: Detected language (zh, en, etc.)                                                                                             │
     │                                                                                                                                          │
     │ Series information:                                                                                                                      │
     │ - name: Series name (e.g., "传道书")                                                                                                     │
     │ - name_en: English name (e.g., "Ecclesiastes")                                                                                           │
     │ - number: Position in series                                                                                                             │
     │ - total_in_series: Total count in series                                                                                                 │
     │                                                                                                                                          │
     │ Scripture references:                                                                                                                    │
     │ - Array of book/chapter/verse references                                                                                                 │
     │ - Both Chinese and English book names                                                                                                    │
     │ - Verse ranges support                                                                                                                   │
     │                                                                                                                                          │
     │ Implementation Approach                                                                                                                  │
     │                                                                                                                                          │
     │ Phase 1: Metadata Extraction Tool (Python Script)                                                                                        │
     │                                                                                                                                          │
     │ Script: scripts/extract_metadata.py                                                                                                      │
     │                                                                                                                                          │
     │ Functionality:                                                                                                                           │
     │ 1. Recursively scan blobs/ for MP3 files                                                                                                 │
     │ 2. Extract preacher name from top-level directory                                                                                        │
     │ 3. Parse filename based on detected pattern                                                                                              │
     │ 4. Extract audio metadata (duration, bitrate) using mutagen library                                                                      │
     │ 5. Detect language from filename characters                                                                                              │
     │ 6. Map Chinese book names to English (维护词典)                                                                                          │
     │ 7. Generate metadata.json per preacher                                                                                                   │
     │                                                                                                                                          │
     │ Filename Parsing Logic:                                                                                                                  │
     │                                                                                                                                          │
     │ def parse_huaxian_filename(filename):                                                                                                    │
     │     # Pattern: YYYYMMDD<书卷名><编号>（<章节>）<标题>.mp3                                                                                │
     │     pattern = r'(\d{8})([^0-9]+)(\d+)（(\d+)章(\d+)节）(.+)\.mp3'                                                                        │
     │     match = re.match(pattern, filename)                                                                                                  │
     │     if match:                                                                                                                            │
     │         date, book, number, chapter, verse, title = match.groups()                                                                       │
     │         return {                                                                                                                         │
     │             'date': parse_date(date),                                                                                                    │
     │             'book': book,                                                                                                                │
     │             'number': int(number),                                                                                                       │
     │             'chapter': int(chapter),                                                                                                     │
     │             'verse': int(verse),                                                                                                         │
     │             'title': title                                                                                                               │
     │         }                                                                                                                                │
     │                                                                                                                                          │
     │ def parse_tang_filename(filename, series_dir):                                                                                           │
     │     # Multiple patterns based on series                                                                                                  │
     │     patterns = [                                                                                                                         │
     │         r'([^0-9]+)(\d+)\.mp3',  # 创世记001.mp3                                                                                         │
     │         r'(.+)-(.+)(\d+)\.mp3',  # 主题-标题001.mp3                                                                                      │
     │         r'(.+)\((\d+)\)\.mp3'    # 标题(1).mp3                                                                                           │
     │     ]                                                                                                                                    │
     │     # Try each pattern...                                                                                                                │
     │                                                                                                                                          │
     │ Bible Book Mapping:                                                                                                                      │
     │ BOOK_MAPPING = {                                                                                                                         │
     │     '创': {'zh': '创世记', 'en': 'Genesis'},                                                                                             │
     │     '出': {'zh': '出埃及记', 'en': 'Exodus'},                                                                                            │
     │     '路': {'zh': '路加福音', 'en': 'Luke'},                                                                                              │
     │     '徒': {'zh': '使徒行传', 'en': 'Acts'},                                                                                              │
     │     '箴': {'zh': '箴言', 'en': 'Proverbs'},                                                                                              │
     │     '传': {'zh': '传道书', 'en': 'Ecclesiastes'},                                                                                        │
     │     # ... complete mapping                                                                                                               │
     │ }                                                                                                                                        │
     │                                                                                                                                          │
     │ Phase 2: File Reorganization Tool (Python Script)                                                                                        │
     │                                                                                                                                          │
     │ Script: scripts/reorganize_sermons.py                                                                                                    │
     │                                                                                                                                          │
     │ Target Structure:                                                                                                                        │
     │ blobs/                                                                                                                                   │
     │ ├── 华贤/                                                                                                                                │
     │ │   ├── metadata.json                                                                                                                    │
     │ │   ├── 2023/                                                                                                                            │
     │ │   │   ├── 传道书/                                                                                                                      │
     │ │   │   │   ├── 001_智慧人也会死_2023-05-01.mp3                                                                                          │
     │ │   │   │   ├── 042_烧荆棘的爆声_2023-06-21.mp3                                                                                          │
     │ │   │   │   └── ...                                                                                                                      │
     │ │   │   └── 疑难解答/                                                                                                                    │
     │ │   │       └── ...                                                                                                                      │
     │ │   └── 2024/                                                                                                                            │
     │ │       └── ...                                                                                                                          │
     │ └── 唐崇荣/                                                                                                                              │
     │     ├── metadata.json                                                                                                                    │
     │     ├── 创世记/                                                                                                                          │
     │     │   ├── 001_创世记第一讲.mp3                                                                                                         │
     │     │   └── ...                                                                                                                          │
     │     └── 讲道集/                                                                                                                          │
     │         └── ...                                                                                                                          │
     │                                                                                                                                          │
     │ Filename Format:                                                                                                                         │
     │ - NNN_<title>_<date>.mp3 (if date available)                                                                                             │
     │ - NNN_<title>.mp3 (if no date)                                                                                                           │
     │ - NNN = zero-padded series number                                                                                                        │
     │                                                                                                                                          │
     │ Reorganization Process:                                                                                                                  │
     │ 1. Read metadata.json for preacher                                                                                                       │
     │ 2. Create directory structure                                                                                                            │
     │ 3. Copy/move files to new locations                                                                                                      │
     │ 4. Update metadata.json with new paths                                                                                                   │
     │ 5. Verify all files copied successfully                                                                                                  │
     │ 6. Optional: Archive original structure                                                                                                  │
     │                                                                                                                                          │
     │ Phase 3: C++ Integration                                                                                                                 │
     │                                                                                                                                          │
     │ New Component: MetadataExtractor class                                                                                                   │
     │                                                                                                                                          │
     │ Header: include/sermon_voices/metadata_extractor.hpp                                                                                     │
     │                                                                                                                                          │
     │ class MetadataExtractor {                                                                                                                │
     │ public:                                                                                                                                  │
     │     // Load existing metadata                                                                                                            │
     │     Metadata load_metadata(const std::string& preacher_path);                                                                            │
     │                                                                                                                                          │
     │     // Extract metadata from MP3 file                                                                                                    │
     │     SermonMetadata extract_from_file(const std::string& file_path);                                                                      │
     │                                                                                                                                          │
     │     // Save metadata.json                                                                                                                │
     │     void save_metadata(const std::string& preacher_path, const Metadata& data);                                                          │
     │                                                                                                                                          │
     │     // Call Python script for full extraction                                                                                            │
     │     void run_full_extraction();                                                                                                          │
     │                                                                                                                                          │
     │     // Reorganize files based on metadata                                                                                                │
     │     void reorganize_files(const std::string& preacher_name);                                                                             │
     │ };                                                                                                                                       │
     │                                                                                                                                          │
     │ Integration with existing codebase:                                                                                                      │
     │ - SermonScanner will use MetadataExtractor to read organized structure                                                                   │
     │ - Sermon class extended with metadata fields                                                                                             │
     │ - Output structure uses metadata for organization                                                                                        │
     │                                                                                                                                          │
     │ Phase 4: Makefile Commands                                                                                                               │
     │                                                                                                                                          │
     │ New commands:                                                                                                                            │
     │ extract-metadata:    # Extract metadata from all MP3 files                                                                               │
     │ reorganize-files:    # Reorganize files based on metadata                                                                                │
     │ verify-metadata:     # Verify metadata completeness                                                                                      │
     │                                                                                                                                          │
     │ Critical Files to Create/Modify                                                                                                          │
     │                                                                                                                                          │
     │ New Files:                                                                                                                               │
     │                                                                                                                                          │
     │ 1. scripts/extract_metadata.py - Main extraction script                                                                                  │
     │ 2. scripts/reorganize_sermons.py - File reorganization script                                                                            │
     │ 3. scripts/bible_books.py - Chinese<->English book name mapping                                                                          │
     │ 4. include/sermon_voices/metadata_extractor.hpp - C++ header                                                                             │
     │ 5. src/metadata_extractor.cpp - C++ implementation                                                                                       │
     │                                                                                                                                          │
     │ Modified Files:                                                                                                                          │
     │                                                                                                                                          │
     │ 1. config/default_config.json - Add metadata settings                                                                                    │
     │ 2. Makefile - Add new commands                                                                                                           │
     │ 3. include/sermon_voices/sermon.hpp - Extend with metadata fields                                                                        │
     │                                                                                                                                          │
     │ Python Dependencies                                                                                                                      │
     │                                                                                                                                          │
     │ Add to requirements.txt:                                                                                                                 │
     │ mutagen>=1.47.0         # MP3 metadata extraction                                                                                        │
     │ python-dateutil>=2.8.2  # Date parsing                                                                                                   │
     │ langdetect>=1.0.9       # Language detection                                                                                             │
     │                                                                                                                                          │
     │ Verification Strategy                                                                                                                    │
     │                                                                                                                                          │
     │ Test with sample data:                                                                                                                   │
     │ 1. Run on 5-10 sermons from each preacher                                                                                                │
     │ 2. Verify all metadata fields populated correctly                                                                                        │
     │ 3. Verify file reorganization works without data loss                                                                                    │
     │ 4. Check metadata.json validates against schema                                                                                          │
     │ 5. Test loading metadata in C++ code                                                                                                     │
     │                                                                                                                                          │
     │ Edge cases to handle:                                                                                                                    │
     │ - Missing dates in filenames                                                                                                             │
     │ - Irregular filename patterns                                                                                                            │
     │ - Corrupted MP3 files                                                                                                                    │
     │ - Duplicate filenames                                                                                                                    │
     │ - Special characters in titles                                                                                                           │
     │ - Missing series information                                                                                                             │
     │                                                                                                                                          │
     │ Implementation Steps                                                                                                                     │
     │                                                                                                                                          │
     │ 1. Create Python extraction script (2-3 hours)                                                                                           │
     │   - Implement filename parsers for each pattern                                                                                          │
     │   - Add audio metadata extraction                                                                                                        │
     │   - Generate metadata.json                                                                                                               │
     │ 2. Create Bible book mapping (1 hour)                                                                                                    │
     │   - Complete Chinese->English mapping                                                                                                    │
     │   - Handle abbreviations                                                                                                                 │
     │ 3. Create reorganization script (2 hours)                                                                                                │
     │   - Directory structure creation                                                                                                         │
     │   - File copying with verification                                                                                                       │
     │   - Handle duplicates and errors                                                                                                         │
     │ 4. Test on sample data (1 hour)                                                                                                          │
     │   - Test with 10 sermons from each preacher                                                                                              │
     │   - Verify metadata accuracy                                                                                                             │
     │ 5. C++ integration (2-3 hours)                                                                                                           │
     │   - Create MetadataExtractor class                                                                                                       │
     │   - Integrate with SermonScanner                                                                                                         │
     │   - Update Sermon class                                                                                                                  │
     │ 6. Full test run (1 hour)                                                                                                                │
     │   - Process all sermons                                                                                                                  │
     │   - Verify reorganization                                                                                                                │
     │   - Check metadata completeness                                                                                                          │
     │                                                                                                                                          │
     │ Total estimated time: 10-12 hours                                                                                                        │
     │                                                                                                                                          │
     │ Success Criteria                                                                                                                         │
     │                                                                                                                                          │
     │ - ✅ All MP3 files have metadata extracted                                                                                               │
     │ - ✅ metadata.json validates against schema                                                                                              │
     │ - ✅ Files reorganized into proper structure                                                                                             │
     │ - ✅ No data loss during reorganization                                                                                                  │
     │ - ✅ Metadata loadable from C++ code                                                                                                     │
     │ - ✅ Scripture references correctly parsed                                                                                               │
     │ - ✅ Series information complete                                                                                                         │
     ╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯


BUT:
something to change:
- all curated audio path should be english translated, the name is something like
  blobs/<preacher_en>/<series_en>/NNN_<title_en>_<verse_and_number_en>_<YYYYmmdd>.mp3 (removed the <year> from folder)
- add some hash of audio recorded in metadata, so that next round of scan won't check the same file.
  code can use ollamma to refine the transcript

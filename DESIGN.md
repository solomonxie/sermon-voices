# Sermon Voices - Design Document

## Architecture Overview

Sermon Voices is a high-performance pipeline designed to process sermon audio/video files with AI-powered transcription, translation, and organized file output. While the long-term vision includes a hybrid C++/Python coordination layer for massive scale and system integration, the current core workflow is driven by a flexible Python-based pipeline for maximum agility with modern ML tools.

### Pipeline Philosophy

1.  **Local-First Processing**: 100% of processing occurs on local hardware (optimized for M1/Apple Silicon). No cloud APIs are used, ensuring privacy and cost-efficiency.
2.  **LLM-Driven Metadata**: Instead of fragile regex-based parsing, we use local LLMs (via Ollama) to extract structured metadata from file paths and names.
3.  **Idempotent Execution**: The system uses a state tracking mechanism (JSON-based) and content hashing to ensure that re-running the pipeline only processes new or changed files.
4.  **Organized Slugified Output**: All outputs are organized into a clean, English-slugified directory structure suitable for object storage indexing.

### Core Workflow

```mermaid
graph TD
    A[Blobs/ - Raw Files] --> B[Metadata Extraction - LLM]
    B --> C[File Reorganization - Slugified]
    C --> D[Transcription - Whisper]
    D --> E[Transcript Refinement - Ollama]
    E --> F[Translation - Ollama]
    F --> G[TTS / Voice Cloning - XTTSv2]
    G --> H[Document Generation - MD/PDF/LaTeX]
    H --> I[Metadata.json Generation]
    I --> J[Output/ - Structured Storage]
```

## Metadata & Tracking

### 1. Content Hashing
To prevent redundant processing, every file in the `blobs/` directory is hashed. The hash is stored in the processing status to track if a file has been modified even if its name remains the same.

### 2. Metadata Schema (metadata.json)

The central source of truth for each sermon file.

```json
{
  "id": "stephen-tong_romans_001_16-17_20240115",
  "content_hash": "sha256:7e9a...",
  "preacher": {
    "original": "唐崇荣",
    "en_slug": "stephen-tong"
  },
  "series": {
    "original": "罗马书",
    "en_slug": "romans"
  },
  "title": {
    "original": "上帝的大能",
    "en_slug": "the-power-of-god"
  },
  "sequence": "001",
  "scriptures": [
    {
      "book": "Romans",
      "chapter": 1,
      "verses": "16-17"
    }
  ],
  "created_at": "2024-01-15",
  "audio_metadata": {
    "duration": 1845,
    "bitrate": 128
  },
  "processing": {
    "status": "completed",
    "last_run": "2024-02-03T10:00:00Z",
    "steps": ["transcribed", "translated", "tts_generated"]
  }
}
```
### 3. Output Directory Structure

The goal is to keep all assets for a single sermon in one place, easily accessible and ready for object storage.

**Pattern:**
`output/<preacher_en_slug>/<series_en_slug>/<sequence>_<title_en_slug>_<verse_en_slug>_<created_at>/`

**Example:**
```
output/stephen-tong/romans/001_the-power-of-god_1-16-17_20240115/
├── original.mp3           # Original audio file
├── metadata.json          # Extracted metadata
├── transcript_zh.txt      # Refined Chinese transcript
├── transcript_en.txt      # Translated English transcript
├── audio_en_cloned.mp3    # TTS output with cloned voice
└── ...
```

This structure makes it "easy to locate" everything related to a specific sermon without jumping between separate top-level folders.

## Implementation Components (Python)

### 1. Metadata Extractor (`src/main.py`)
Uses local LLM prompts to "guess" and extract structured data from chaotic folder structures and filenames found in `blobs/`.

### 2. Transcription Engine
Leverages `faster-whisper` for high-speed local transcription, utilizing CoreML/MPS on Apple Silicon.

### 3. LLM Refiner
Uses Ollama (e.g., `llama3`) to correct OCR-like errors in transcripts, improve punctuation, and identify speaker segments.

### 4. Translation & TTS
- **Translation**: Batch-processed via Ollama.
- **TTS**: Coqui XTTS v2 for high-quality voice cloning, ensuring the translated sermon sounds like the original preacher.

## Technical Decisions

- **Slugification**: Using `python-slugify` to ensure all file paths are URL-safe and consistent.
- **Persistence**: Using `output/processing_status.json` as a lightweight database of all known files and their current state.
- **Communication**: Components communicate via structured JSON objects passed between function calls.

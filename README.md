# Sermon Voices

A high-performance Python pipeline for processing sermon audio/video files with AI-powered transcription, translation, voice-cloning TTS, and organized English-slugified output. 100% local processing on M1 Mac, zero cloud APIs.

## Features

- 🎵 **Local-First Processing**: Zero cloud APIs, fully optimized for Apple Silicon (M1/M2/M3).
- 📝 **LLM-Driven Metadata**: Uses local LLMs (Ollama/Llama3) to extract structured data from chaotic paths.
- 🌍 **Multi-language pipeline**: Transcription (Whisper), Refinement, and Translation (Ollama).
- 🎤 **Voice Cloning TTS**: High-quality TTS with cloned voices using Coqui XTTS v2.
- 📦 **Clean Output**: Organized, English-slugified directory structure ready for object storage.
- 🔒 **Content Hashing**: SHA-256 tracking to prevent redundant processing.
- ✅ **Idempotent**: Rerun any time; only new or changed files are processed.

## Tech Stack

- **Python 3.9+**: Core pipeline and orchestration.
- **faster-whisper**: Optimized local transcription (large-v3 tuned for bilingual accuracy).
- **Ollama**: Local LLM inference for metadata extraction and refinement.
- **Coqui XTTS v2**: Professional voice cloning and TTS.
- **python-slugify**: URL-safe English path generation.
- **FFmpeg**: Robust audio/video handling.

## Quick Start

### Prerequisites

- macOS (M1/M2/M3 recommended)
- [Ollama](https://ollama.ai) installed and running
- Python 3.9+
- FFmpeg (`brew install ffmpeg`)

### Installation

```bash
# 1. Clone and enter
git clone https://github.com/yourusername/sermon-voices.git
cd sermon-voices

# 2. Setup environment
make setup
```

#### Usage

```bash
# 1. Place sermon files in blobs/ (any structure)
mkdir -p blobs/my_preacher
cp sermon.mp3 blobs/my_preacher/

# 2. Run the main pipeline (Metadata extraction + Audio processing)
make process
```

## Workflow

### Run the Pipeline

The pipeline is split into two independent, idempotent phases:

1.  **Metadata Extraction**: Extracts metadata from audio files in `blobs/` and organizes them into the `output/` directory. Completion is tracked in `output/processed.txt`.
    ```bash
    make metadata
    ```

2.  **Audio Processing**: Performs transcription, translation, and TTS. Each step checks for existing output files (e.g., `_refined.txt`, `audio_en.mp3`) and skips them if they exist, allowing for safe resumes.
    ```bash
    make audio
    ```

To run both phases in sequence:
```bash
make process
```

The processing pipeline is split into two main phases, each functioning as an independent entry point:

1.  **Metadata Extraction** ([process_metadata.py](file:///Users/solomonxie/workspace/personal/sermon-voices/src/process_metadata.py)):
    -   Scans `blobs/` for new MP3 files.
    -   Uses LLMs to extract preacher, series, title, scripture, and date from file paths.
    -   Translates metadata to English and creates a slugified directory structure in `output/`.
    -   Completion is tracked in `output/processed.txt`.
2.  **Audio Processing** ([process_audio.py](file:///Users/solomonxie/workspace/personal/sermon-voices/src/process_audio.py)):
    -   Chunking the audio for efficient processing.
    -   Transcribing (Whisper) and Translating (Ollama) each chunk.
    -   Combining and Refining the final English transcript.
    -   Converting to Markdown/PDF and generating TTS audio with cloned voices.
    -   Idempotent execution: skips steps if output files already exist.

## Project Structure

```
sermon-voices/
├── blobs/                  # Input raw files (chaotic structure OK)
├── output/
│   ├── <preacher_en>/      # Organized, slugified preacher folder
│   │   └── <series_en>/    # Series folder
│   │       └── <sermon_slug>/ # All assets for one sermon
│   │           ├── original.mp3
│   │           ├── metadata.json
│   │           ├── transcript_zh.txt
│   │           ├── audio_en.mp3
│   │           └── sermon.pdf
│   └── processing_status.json # Pipeline state and file hashes
├── src/                    # Core Python pipeline
└── scripts/                # Utility scripts
```

## Makefile Commands

```bash
make setup             # Install all dependencies and pull models
make extract-metadata  # Scan blobs/ and extract metadata via LLM
make reorganize-files  # Reorganize into slugified structure
make process           # Run the full end-to-end pipeline
make clean-output      # Reset all generated data
```

## Configuration

Customizations for languages, models, and paths can be found in `config/default_config.json`.

## Development

- [DESIGN.md](DESIGN.md): Architecture and metadata schemas.
- [IMPLEMENTATION.md](IMPLEMENTATION.md): Development logs and roadmap.

## License

MIT License

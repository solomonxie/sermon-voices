# Sermon Voices

A hybrid C++/Python application that processes sermon audio/video files with AI-powered transcription, translation, voice-cloning TTS, and organized output for object storage. 100% local processing on M1 Mac, zero cloud APIs.

## Features

- 🎵 Audio/video processing with FFmpeg
- 📝 Local transcription (whisper.cpp)
- 🌍 Multi-language translation (Ollama)
- 🎤 Voice cloning + TTS (Coqui XTTS v2)
- 📄 Document generation (Markdown, PDF, Text)
- 📦 Organized output with metadata.json for each sermon
- ☁️ Ready for object storage (S3, MinIO)
- ✅ Simple idempotent processing (no queue, just rerun)
- 🚫 Zero cloud APIs, 100% local on M1 Mac

## Tech Stack

- **C++17**: Main application orchestration
- **Python**: ML model integration (Whisper, XTTS, Ollama)
- **CMake**: Build system
- **whisper.cpp**: Fast local transcription
- **Ollama**: Local LLM for translation
- **Coqui XTTS v2**: Voice cloning and TTS
- **nlohmann/json**: JSON processing and metadata

## Quick Start

### Prerequisites

- macOS (M1/M2/M3)
- Xcode Command Line Tools
- Python 3.9+
- CMake 3.15+
- Ollama

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/sermon-voices.git
cd sermon-voices

# 2. Install all dependencies (C++, Python, Models)
make setup

# 3. Build the project
make build
```

### Usage

```bash
# Place your sermon files in blobs/
mkdir -p blobs/john_piper
cp your_sermon.mp3 blobs/john_piper/2024-01-15_10-30-00.mp3

# Process all sermons
make process

# View organized output
ls output/sermons/john_piper/2024-01-15_10-30-00/
# Will show: metadata.json, original/, transcripts/, audio/, documents/
```

## Project Structure

```
sermon-voices/
├── blobs/                  # Input audio/video files
├── output/
│   ├── sermons/           # Organized sermon outputs
│   │   └── <author>/
│   │       └── <sermon_id>/
│   │           ├── metadata.json
│   │           ├── original/
│   │           ├── transcripts/
│   │           ├── audio/
│   │           └── documents/
│   └── index.json         # Global sermon index
├── src/                    # C++ source code
├── python/                 # Python ML scripts
└── config/                 # Configuration files
```

## File Naming Convention

Place sermon files in `blobs/<author>/<YYYY-MM-DD_HH-MM-SS>.<ext>`

Examples:
- `blobs/john_piper/2024-01-15_10-30-00.mp3`
- `blobs/tim_keller/2024-02-20_09-00-00.mp4`

## Processing Model

The system tracks processing status in `output/processing_status.json`. When you run `make process`:

1. Scans `blobs/` for all audio/video files
2. Checks status file to find unprocessed/incomplete files
3. Processes each file through the pipeline
4. Updates status after each step
5. Can be safely re-run anytime (idempotent)

## Makefile Commands

```bash
make help              # Show all available commands

# Setup
make setup             # Install all dependencies
make setup-cpp         # Install C++ dependencies only
make setup-python      # Create venv and install Python packages
make setup-ollama      # Download Ollama models

# Build
make build             # Build the C++ project
make rebuild           # Clean and rebuild
make debug             # Build with debug symbols

# Run
make process           # Process all sermons
make process-one FILE= # Process a single sermon
make index             # Generate global index.json

# Testing
make test              # Run all tests
make test-audio        # Test audio extraction
make test-transcript   # Test transcription
make test-translate    # Test translation
make test-tts          # Test TTS generation

# Utilities
make clean             # Clean build artifacts
make clean-output      # Clean all generated outputs
make check-deps        # Verify dependencies
```

## Configuration

Edit `config/default_config.json` to customize:

- Target languages for translation
- Transcription model (base/small/medium)
- TTS settings
- Voice cloning parameters
- Output directory structure
- Object storage settings (S3/MinIO)

## Development

See [DESIGN.md](DESIGN.md) for architecture details.
See [IMPLEMENTATION.md](IMPLEMENTATION.md) for development progress.

## License

MIT License

## Acknowledgments

- [whisper.cpp](https://github.com/ggerganov/whisper.cpp) - Fast Whisper implementation
- [Ollama](https://ollama.ai) - Local LLM inference
- [Coqui XTTS](https://github.com/coqui-ai/TTS) - Voice cloning and TTS
- [cpp-httplib](https://github.com/yhirose/cpp-httplib) - HTTP server library

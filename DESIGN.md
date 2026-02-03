# Sermon Voices - Design Document

## Architecture Overview

This is a hybrid C++/Python application designed to process sermon audio/video files with AI-powered transcription, translation, voice-cloning TTS, and web UI presentation.

### Why Hybrid C++/Python?

**C++ Components (for learning and structure)**:
- Main application orchestration and pipeline control
- Project structure and organization
- Build system (CMake)
- File I/O and data management
- Web server implementation
- JSON processing
- Process management

**Python Components (for best ML tools)**:
- Whisper transcription (faster-whisper)
- Coqui XTTS v2 for TTS + voice cloning
- Ollama client for translation

**Integration Method**:
- C++ launches Python scripts via subprocess (popen/system)
- Data exchange via JSON files
- Clean separation: C++ orchestrates, Python executes ML inference

## Core Components

### 1. Sermon Class (`sermon.hpp/cpp`)
Represents a single sermon with metadata.

**Fields**:
- `std::string path` - Original file path
- `std::string author` - Extracted from directory structure
- `std::chrono::system_clock::time_point datetime` - Parsed from filename
- `Transcript transcript` - Timestamped transcript
- `std::map<std::string, Transcript> translations` - Per-language translations
- `std::map<std::string, std::string> audio_outputs` - Generated TTS audio paths

**Methods**:
- `to_json()` - Serialize to JSON
- `from_json()` - Deserialize from JSON

### 2. StatusTracker (`status_tracker.hpp/cpp`)
Manages processing state persistence.

**Purpose**: Tracks which sermons have been processed and their current state.

**Storage**: `output/processing_status.json`

**Status Schema**:
```json
{
  "blobs/john_piper/2024-01-15_10-30-00.mp3": {
    "status": "completed",
    "last_updated": "2024-01-15T14:30:00Z",
    "steps_completed": ["audio_extract", "transcribe", "translate_en", "tts_en"],
    "error": null
  }
}
```

**Methods**:
- `get_status(path)` - Get current status
- `set_status(path, status)` - Update status
- `mark_step_complete(path, step)` - Mark pipeline step done
- `mark_failed(path, error)` - Record failure
- `get_pending_sermons()` - List unprocessed files

### 3. SermonScanner (`sermon_scanner.hpp/cpp`)
Discovers sermon files in the `blobs/` directory.

**Functionality**:
- Recursively scan `blobs/` directory
- Parse filename format: `<author>/<YYYY-MM-DD_HH-MM-SS>.<ext>`
- Extract metadata (author, datetime)
- Filter by supported formats (mp3, mp4, m4a, wav, etc.)
- Return list of Sermon objects

**Supported Formats**: mp3, mp4, m4a, wav, flac, ogg, webm

### 4. AudioProcessor (`audio_processor.hpp/cpp`)
Handles audio extraction and conversion.

**Responsibilities**:
- Extract audio from video files using FFmpeg
- Convert to standard format (WAV, 16kHz, mono)
- Audio validation and metadata extraction

**FFmpeg Integration**: Calls via system() or popen()

### 5. Transcriber (`transcriber.hpp/cpp`)
C++ wrapper for Python whisper transcription.

**Process**:
1. Launch subprocess: `python3 python/transcribe.py --input audio.wav --output transcript.json`
2. Monitor subprocess progress
3. Parse JSON output with timestamped segments
4. Handle errors and timeouts

**Output Format**:
```json
{
  "segments": [
    {"start": 0.0, "end": 5.2, "text": "Welcome to today's sermon"},
    {"start": 5.2, "end": 10.8, "text": "We will discuss..."}
  ]
}
```

### 6. Translator (`translator.hpp/cpp`)
C++ wrapper for Ollama-based translation.

**Two Implementation Options**:
1. Direct HTTP calls to Ollama API (localhost:11434) - pure C++
2. Call Python script with Ollama client - simpler

**Process**:
- Preserve timestamp information from transcript
- Batch translate segments
- Progress tracking
- Error handling for API failures

**Output**: JSON with translated segments maintaining timestamps

### 7. VoiceCloner (`voice_cloner.hpp/cpp`)
Manages voice sample extraction and profile creation.

**Workflow**:
1. Extract voice sample from original sermon (10-30 seconds)
2. Call Python XTTS to create voice profile
3. Store voice profiles for reuse per author
4. Validate sample quality (duration, clarity)

**Storage**: `voice_samples/<author>/profile.json`

### 8. TTSEngine (`tts_engine.hpp/cpp`)
C++ wrapper for Coqui XTTS Python scripts.

**Process**:
1. Load voice profile for author
2. Generate TTS with cloned voice for each language
3. Handle long text splitting (XTTS has character limits)
4. Subprocess management with progress tracking
5. Generate audio with timestamp alignment

**Output**: MP3/WAV files per language in `output/audio/<author>/<lang>/`

### 9. DocumentGenerator (`document_generator.hpp/cpp`)
Creates formatted output documents.

**Formats**:
- **Markdown**: Simple formatting with timestamps and parallel text
- **PDF**: Shell out to pandoc or wkhtmltopdf
- **LaTeX**: Generate .tex source files

**Features**:
- Include metadata headers (author, date, languages)
- Bilingual parallel text display
- Timestamp references

### 10. WebServer (`web_server.hpp/cpp`)
HTTP server using cpp-httplib.

**Endpoints**:
- `GET /` - Main page with sermon list
- `GET /sermon/<id>` - Sermon detail page
- `GET /api/sermons` - JSON list of all sermons
- `GET /api/sermon/<id>` - Full sermon data
- `GET /audio/<path>` - Stream audio files
- `GET /static/<path>` - Serve static files

**Template Engine**: inja (Jinja2-like for C++)

## Data Flow

```
Input: blobs/<author>/<datetime>.<ext>
  |
  v
SermonScanner -> List of Sermon objects
  |
  v
StatusTracker -> Filter to pending/incomplete
  |
  v
For each sermon:
  |
  +-> AudioProcessor -> Extracted audio
  |
  +-> Transcriber -> Timestamped transcript
  |
  +-> VoiceCloner -> Voice profile
  |
  +-> Translator (for each language) -> Translated transcript
  |
  +-> TTSEngine (for each language) -> Generated audio
  |
  +-> DocumentGenerator -> Markdown, PDF, LaTeX
  |
  v
Output: Organized in output/ directory
  |
  v
WebServer -> Present via web UI
```

## Processing Model: Simple & Idempotent

### Key Principle
No job queue, no daemon. Just run `make process` and it processes everything that needs processing.

### Status Tracking
`output/processing_status.json` tracks all sermons and their processing state.

### Workflow
1. **Scan**: Find all files in `blobs/`
2. **Check**: Load status file
3. **Filter**: Identify pending/incomplete/failed
4. **Process**: Sequential processing with status updates
5. **Resume**: Can be safely re-run anytime

### Benefits
- Simple to understand and debug
- Easy to resume after crashes
- No complex queue management
- Transparent progress tracking

## Configuration

**File**: `config/default_config.json`

**Structure**:
```json
{
  "transcription": {
    "model": "base",
    "language": "auto",
    "device": "metal"
  },
  "translation": {
    "target_languages": ["en", "zh", "es", "ko"],
    "ollama_model": "llama3",
    "ollama_url": "http://localhost:11434"
  },
  "tts": {
    "engine": "coqui-xtts",
    "use_voice_cloning": true,
    "languages": ["en", "zh", "es", "ko"],
    "gpu_acceleration": "mps"
  },
  "voice_cloning": {
    "sample_duration_sec": 15,
    "auto_extract_from_sermon": true
  },
  "web": {
    "port": 8080,
    "host": "localhost"
  },
  "paths": {
    "python_scripts": "./python",
    "models": "./models"
  }
}
```

## Build System

### CMake Structure
- Root `CMakeLists.txt` - Project configuration
- `src/CMakeLists.txt` - Main executable
- `tests/CMakeLists.txt` - Test executable
- `lib/CMakeLists.txt` - Third-party dependencies

### Makefile Wrapper
Simplifies common operations:
- `make setup` - Install dependencies
- `make build` - Build project
- `make process` - Run pipeline
- `make serve` - Start web server
- `make test` - Run tests

## Dependencies

### C++ Libraries
- **cpp-httplib** (header-only) - HTTP server
- **nlohmann/json** (header-only) - JSON parsing
- **inja** (header-only) - Template engine

### Python Packages
- **faster-whisper** - Optimized Whisper implementation
- **TTS** (Coqui) - Voice cloning and TTS
- **ollama** - Ollama client
- **pydub**, **soundfile**, **librosa** - Audio processing

### System Dependencies
- **FFmpeg** - Audio/video processing
- **Ollama** - Local LLM server
- **Python 3.9+** - ML script runtime

## Error Handling

### Strategy
- Each component has clear error codes
- Graceful degradation: skip failed sermons, continue processing
- Detailed error logging
- Status file tracks failures with error messages

### Recovery
- Re-running `make process` retries failed sermons
- Status file prevents re-processing completed sermons
- Manual intervention possible (edit status file)

## Performance Considerations

### M1 Mac Optimization
- Whisper uses Core ML acceleration
- XTTS uses MPS (Metal Performance Shaders)
- Ollama optimized for Apple Silicon

### Memory Management
- Process sermons sequentially to avoid memory issues
- Stream large files instead of loading entirely
- Clean up temporary files after each sermon

### Disk Space
- Models: ~5GB total (Whisper + XTTS + Ollama)
- Processing: ~1GB per sermon temporarily
- Output: ~100MB per sermon (audio + documents)

## Security Considerations

- No network access except localhost (Ollama)
- No cloud APIs or external data transmission
- Input validation for file paths
- Subprocess execution safety (avoid injection)

## Testing Strategy

### Unit Tests
- Each component tested independently
- Mock subprocess calls
- Test JSON serialization

### Integration Tests
- Full pipeline with sample data
- Error handling scenarios
- Performance benchmarks

### End-to-End Tests
- Process sample sermon
- Verify all outputs generated
- Web UI functionality

## Future Enhancements

- Parallel processing of multiple sermons
- Real-time progress UI in web interface
- Support for more output formats
- Better error recovery mechanisms
- GPU batch processing optimization
- Support for more languages
- Speaker diarization (who said what)

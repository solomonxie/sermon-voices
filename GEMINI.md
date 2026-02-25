# Sermon Voices - Gemini CLI Context

## Project Overview

Sermon Voices is a high-performance, 100% local (optimized for Apple Silicon) Python pipeline for processing sermon audio/video files. It leverages local AI models (via Ollama, faster-whisper, and Coqui XTTS v2) without relying on cloud APIs. 

The pipeline performs four main functions:
1.  **Metadata Extraction:** Uses local LLMs to extract structured metadata (preacher, series, scripture, date) from chaotic file names in a `blobs/` directory.
2.  **Audio Processing:** Transcribes the original audio (using faster-whisper/Paraformer) and refines the text with an LLM.
3.  **Translation & TTS:** Translates the refined transcript to English and generates high-quality text-to-speech using cloned voices.
4.  **Document Generation:** Converts the final English output into beautifully formatted Markdown, LaTeX, and PDF documents.

The pipeline outputs organized, English-slugified directories in an `output/` folder, using a `metadata.json` file as the central source of truth for each sermon file. Content hashing is used to ensure idempotency and prevent redundant processing.

## Building and Running

The project uses a `Makefile` to orchestrate setup and execution.

### Setup
*   **Install dependencies and create virtual environment:** `make setup`

### Execution
*   **Run the full end-to-end pipeline:** `make process`
*   **Run Phase 1 (Metadata Extraction):** `make metadata`
*   **Run Phase 2 (Audio Transcription & Refinement):** `make audio`
*   **Run Phase 3 (Translation & Text-to-Speech):** `make translation`
*   **Run Phase 4 (Document Generation):** `make pdf`
*   **Clean all generated output:** `make clean-output`

### Testing
*   **Run all tests:** `make test` (Note: This correctly sets `PYTHONPATH=.` and uses the venv Python)

## Development Conventions

*   **Virtual Environment:** All operations and script executions MUST occur within the `venv/` directory (e.g., using `venv/bin/python` or `venv/bin/pip`). Never use system Python.
*   **Style & Naming:** Follow the Google Python Style Guide and PEP 8 (snake_case for variables/functions, PascalCase for classes). The code should be compact.
*   **Type Hinting:** Mandatory for all function signatures using built-in types (e.g., `list[str]`, `dict[str, int]`) where possible.
*   **Documentation:** Provide Google-style docstrings for complex functions and classes.
*   **Structure:** Order functions/classes in reading order (e.g., `main()` at the top, followed by the functions it calls). Keep function parameters to a minimum (ideally under 5).
*   **Error Handling:** Use `try-except` blocks sparingly (max 5 lines wrapped) and mainly to prevent workflow breaks. Let errors expose directly where possible.
*   **Testing:** Every new feature or bug fix must include tests in the `tests/` directory. Test code should be simple, avoid excessive logging, and omit try-except blocks to allow errors to surface. When running pytest manually, you must specify `PYTHONPATH=.`.
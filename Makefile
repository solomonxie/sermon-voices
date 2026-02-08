# Sermon Voices - Makefile

.PHONY: help setup setup-python clean-output process metadata audio check-deps models-info test

VENV_DIR := venv
PYTHON := python3.11
PIP := $(VENV_DIR)/bin/pip
PYTHON_VENV := $(VENV_DIR)/bin/python

help:
	@echo "Sermon Voices - Available Commands:"
	@echo "  make setup          Install all dependencies"
	@echo "  make process        Run full pipeline (Metadata + Audio + Translation + PDF)"
	@echo "  make metadata       Phase 1: Metadata Extraction"
	@echo "  make audio          Phase 2: Audio Transcription & Refinement"
	@echo "  make translation    Phase 3: Translation & Text-to-Speech (ZH -> EN)"
	@echo "  make pdf            Phase 4: Document Generation (Markdown/LaTeX/PDF)"
	@echo "  make clean-output   Delete all generated files"
	@echo "  make check-deps     Verify dependencies"
	@echo "  make test           Run tests"

setup: setup-system setup-python

setup-system:
	@echo "Installing system dependencies..."
	@if [ "$$(uname)" = "Darwin" ]; then \
		if ! command -v brew >/dev/null 2>&1; then \
			echo "Homebrew not found. Please install it first: https://brew.sh/"; \
			exit 1; \
		fi; \
		if ! command -v ffmpeg >/dev/null 2>&1; then \
			brew install ffmpeg; \
		else \
			echo "ffmpeg already installed."; \
		fi \
	else \
		echo "Unsupported OS for automatic system setup. Please install ffmpeg manually."; \
	fi

setup-python:
	@echo "Setting up Python environment..."
	@if [ ! -d "$(VENV_DIR)" ]; then $(PYTHON) -m venv $(VENV_DIR); fi
	@$(PIP) install --upgrade pip
	@$(PIP) install -r requirements.txt



clean-output:
	@echo "Cleaning output directory..."
	rm -rf output/*

process: metadata audio translation pdf

metadata:
	@echo "Running Phase 1: Metadata Extraction..."
	@PYTHONPATH=. $(PYTHON_VENV) src/process_metadata.py

audio:
	@echo "Running Phase 2: Audio Transcription & Refinement (Original Language)..."
	# @find output -name original.mp3 -exec sh -c 'PYTHONPATH=. $(PYTHON_VENV) src/process_audio.py "$$0"' {} \;
	# Debug----
	PYTHONPATH=. $(PYTHON_VENV) src/process_audio.py output/hua-xian/acts/001_do-not-leave-jerusalem/original.mp3
	PYTHONPATH=. $(PYTHON_VENV) src/process_audio.py output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original.mp3

translation:
	@echo "Running Phase 3: Translation & Text-to-Speech (ZH -> EN)..."
	@find output -name metadata.json -exec sh -c 'PYTHONPATH=. $(PYTHON_VENV) src/process_translation.py "$$0"' {} \;

pdf:
	@echo "Running Phase 4: Document Generation (Markdown/LaTeX/PDF)..."
	@find output -name metadata.json -exec sh -c 'PYTHONPATH=. $(PYTHON_VENV) src/process_pdf.py "$$0"' {} \;


check-deps:
	@$(PYTHON) --version
	@ffmpeg -version | head -n 1
	@ollama --version

models-info:
	@ollama list
	@if [ -d "$(VENV_DIR)" ]; then $(PIP) list | grep -E '(whisper|TTS|ollama|slugify)'; fi

test:
	@PYTHONPATH=. $(PYTHON_VENV) -m pytest -svra tests/

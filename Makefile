# Sermon Voices - Makefile

.PHONY: help setup setup-python setup-ollama clean-output process metadata audio check-deps models-info test

VENV_DIR := venv
PYTHON := python3.11
PIP := $(VENV_DIR)/bin/pip
PYTHON_VENV := $(VENV_DIR)/bin/python

help:
	@echo "Sermon Voices - Available Commands:"
	@echo "  make setup          Install all dependencies"
	@echo "  make process        Run full pipeline (Metadata + Audio)"
	@echo "  make metadata       Phase 1: Metadata Extraction"
	@echo "  make audio          Phase 2: Audio Processing"
	@echo "  make clean-output   Delete all generated files"
	@echo "  make check-deps     Verify dependencies"
	@echo "  make test           Run tests"

setup: setup-python setup-ollama

setup-python:
	@echo "Setting up Python environment..."
	@if [ ! -d "$(VENV_DIR)" ]; then $(PYTHON) -m venv $(VENV_DIR); fi
	@$(PIP) install --upgrade pip
	@$(PIP) install -r requirements.txt

setup-ollama:
	@echo "Setting up Ollama models..."
	@ollama pull qwen3:8b

clean-output:
	@echo "Cleaning output directory..."
	rm -rf output/*

process: metadata audio

metadata:
	@echo "Running Phase 1: Metadata Extraction..."
	@PYTHONPATH=. $(PYTHON_VENV) src/process_metadata.py

audio:
	@echo "Running Phase 2: Audio Processing..."
	@PYTHONPATH=. $(PYTHON_VENV) src/process_audio.py

check-deps:
	@$(PYTHON) --version
	@ffmpeg -version | head -n 1
	@ollama --version

models-info:
	@ollama list
	@if [ -d "$(VENV_DIR)" ]; then $(PIP) list | grep -E '(whisper|TTS|ollama|slugify)'; fi

test:
	@PYTHONPATH=. $(PYTHON_VENV) -m pytest -svra tests/

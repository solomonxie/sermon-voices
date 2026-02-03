# Sermon Voices - Makefile
# User-friendly wrapper for common commands

.PHONY: help setup setup-cpp setup-python setup-ollama build rebuild debug clean clean-output process process-one serve test test-audio test-transcript test-translate test-tts check-deps models-info format lint watch

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Directories
VENV_DIR := venv

# Python
PYTHON := python3
PIP := $(VENV_DIR)/bin/pip
PYTHON_VENV := $(VENV_DIR)/bin/python

help: ## Show all available commands with descriptions
	@echo "$(BLUE)Sermon Voices - Available Commands:$(NC)"
	@echo ""
	@echo "$(GREEN)Setup Commands:$(NC)"
	@grep -E '^setup.*:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*##"}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Run Commands:$(NC)"
	@grep -E '^(process|extract-metadata|reorganize-files):.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*##"}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Utility Commands:$(NC)"
	@grep -E '^(check-deps|models-info|clean-output):.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*##"}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

# ============================================================================
# Setup Commands
# ============================================================================

setup: setup-python setup-ollama ## Install all dependencies (Python packages, Ollama models)
	@echo "$(GREEN)✓ Setup complete!$(NC)"
	@echo "Next steps:"
	@echo "  1. Run 'make extract-metadata' to scan original blobs"
	@echo "  2. Run 'make reorganize-files' to structure the audio files"
	@echo "  3. Run 'make process' to start the pipeline"

setup: setup-python setup-ollama ## Install all dependencies (Python packages, Ollama models)
	@echo "$(GREEN)✓ Setup complete!$(NC)"
	@echo "Next steps:"
	@echo "  1. Run 'make extract-metadata' to scan original blobs"
	@echo "  2. Run 'make reorganize-files' to structure the audio files"
	@echo "  3. Run 'make process' to start the pipeline"

setup-python: ## Create venv and install Python dependencies
	@echo "$(BLUE)Setting up Python environment...$(NC)"
	@if [ ! -d "$(VENV_DIR)" ]; then \
		$(PYTHON) -m venv $(VENV_DIR); \
	fi
	@echo "Installing Python packages..."
	@$(PIP) install --upgrade pip
	@$(PIP) install -r requirements.txt
	@echo "$(GREEN)✓ Python environment ready$(NC)"

setup-ollama: ## Download Ollama models (llama3)
	@echo "$(BLUE)Setting up Ollama models...$(NC)"
	@if ! command -v ollama &> /dev/null; then \
		echo "$(RED)ERROR: Ollama not installed. Install with: brew install ollama$(NC)"; \
		exit 1; \
	fi
	@echo "Pulling llama3 model (this may take a few minutes)..."
	@ollama pull llama3
	@echo "$(GREEN)✓ Ollama models ready$(NC)"

clean-output: ## Clean all generated outputs
	@echo "$(YELLOW)WARNING: This will delete all generated transcripts, translations, and audio!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf output/transcripts/* output/translations/* output/audio/* output/markdown/* output/pdf/* output/latex/* output/text/*; \
		rm -f output/processing_status.json; \
		echo "$(GREEN)✓ Output cleaned$(NC)"; \
	else \
		echo "Cancelled."; \
	fi

# ============================================================================
# Run Commands
# ============================================================================

process: ## Run the full processing pipeline (scan all metadata)
	@echo "$(BLUE)Scanning sermons...$(NC)"
	@PYTHONPATH=. $(PYTHON_VENV) scripts/manage.py scan

extract-metadata: setup-python ## Extract metadata from all MP3 files
	@echo "$(BLUE)Extracting metadata...$(NC)"
	@PYTHONPATH=. $(PYTHON_VENV) scripts/manage.py extract --llm
	@echo "$(GREEN)✓ Metadata extraction complete$(NC)"

reorganize-files: setup-python ## Reorganize files based on metadata
	@echo "$(BLUE)Reorganizing files...$(NC)"
	@PYTHONPATH=. $(PYTHON_VENV) scripts/manage.py reorganize $(if $(NO_DRY_RUN),--no-dry-run,)
	@echo "$(GREEN)✓ File reorganization complete$(NC)"

# ============================================================================
# Test Commands
# ============================================================================

test: build ## Run all tests
	@echo "$(BLUE)Running tests...$(NC)"
	@if [ -f "$(BUILD_DIR)/tests/sermon_voices_tests" ]; then \
		$(BUILD_DIR)/tests/sermon_voices_tests; \
	else \
		echo "$(YELLOW)No tests built yet.$(NC)"; \
	fi

test-audio: ## Test audio extraction only
	@echo "$(BLUE)Testing audio extraction...$(NC)"
	@echo "$(YELLOW)Not implemented yet$(NC)"

test-transcript: ## Test transcription only
	@echo "$(BLUE)Testing transcription...$(NC)"
	@echo "$(YELLOW)Not implemented yet$(NC)"

test-translate: ## Test translation only
	@echo "$(BLUE)Testing translation...$(NC)"
	@echo "$(YELLOW)Not implemented yet$(NC)"

test-tts: ## Test TTS generation only
	@echo "$(BLUE)Testing TTS...$(NC)"
	@echo "$(YELLOW)Not implemented yet$(NC)"

# ============================================================================
# Utility Commands
# ============================================================================

check-deps: ## Verify all dependencies are installed
	@echo "$(BLUE)Checking dependencies...$(NC)"
	@echo -n "Python: "
	@if command -v $(PYTHON) &> /dev/null; then \
		echo "$(GREEN)✓ $(shell $(PYTHON) --version)$(NC)"; \
	else \
		echo "$(RED)✗ Not found$(NC)"; \
	fi
	@echo -n "FFmpeg: "
	@if command -v ffmpeg &> /dev/null; then \
		echo "$(GREEN)✓ $(shell ffmpeg -version | head -n1 | cut -d' ' -f3)$(NC)"; \
	else \
		echo "$(RED)✗ Not found (install with: brew install ffmpeg)$(NC)"; \
	fi
	@echo -n "Ollama: "
	@if command -v ollama &> /dev/null; then \
		echo "$(GREEN)✓ $(shell ollama --version)$(NC)"; \
	else \
		echo "$(RED)✗ Not found (install with: brew install ollama)$(NC)"; \
	fi
	@echo -n "Python venv: "
	@if [ -d "$(VENV_DIR)" ]; then \
		echo "$(GREEN)✓ Active$(NC)"; \
	else \
		echo "$(RED)✗ Not created (run: make setup-python)$(NC)"; \
	fi

models-info: ## Show info about downloaded models
	@echo "$(BLUE)Checking models...$(NC)"
	@echo ""
	@echo "$(GREEN)Ollama Models:$(NC)"
	@ollama list || echo "$(RED)Ollama not running$(NC)"
	@echo ""
	@echo "$(GREEN)Python Packages:$(NC)"
	@if [ -d "$(VENV_DIR)" ]; then \
		$(PIP) list | grep -E '(whisper|TTS|ollama)'; \
	else \
		echo "$(RED)Virtual environment not created$(NC)"; \
	fi

watch: ## Auto-rebuild on file changes (requires fswatch)
	@if ! command -v fswatch &> /dev/null; then \
		echo "$(RED)ERROR: fswatch not installed. Install with: brew install fswatch$(NC)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Watching for changes...$(NC)"
	@fswatch -o src include | xargs -n1 -I{} make build

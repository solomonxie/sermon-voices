# Sermon Voices - Makefile
# User-friendly wrapper for common commands

.PHONY: help setup setup-python setup-ollama clean-output process extract-metadata reorganize-files check-deps models-info

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
PYTHON := python3.11  # TTS library requires < Python 3.12
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
	@echo "Pulling llama3 model..."
	@ollama pull llama3
	@echo "$(GREEN)✓ Ollama models ready$(NC)"

clean-output: ## Clean all generated outputs
	@echo "$(YELLOW)WARNING: This will delete all generated outputs!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf output/*; \
		echo "$(GREEN)✓ Output cleaned$(NC)"; \
	else \
		echo "Cancelled."; \
	fi

# ============================================================================
# Run Commands
# ============================================================================

process: ## Run the full processing pipeline
	@echo "$(BLUE)Starting full pipeline...$(NC)"
	@PYTHONPATH=src $(PYTHON_VENV) src/main.py

extract-metadata: ## Extract metadata from blobs/ using LLM
	@echo "$(BLUE)Extracting metadata...$(NC)"
	@PYTHONPATH=src $(PYTHON_VENV) src/main.py --mode extract
	@echo "$(GREEN)✓ Metadata extraction complete$(NC)"

reorganize-files: ## Reorganize files based on extracted metadata
	@echo "$(BLUE)Reorganizing files...$(NC)"
	@PYTHONPATH=src $(PYTHON_VENV) src/main.py --mode reorganize
	@echo "$(GREEN)✓ File reorganization complete$(NC)"

# ============================================================================
# Utility Commands
# ============================================================================

check-deps: ## Verify all dependencies are installed
	@echo "$(BLUE)Checking dependencies...$(NC)"
	@echo -n "Python: "
	@command -v $(PYTHON) &> /dev/null && echo "$(GREEN)✓ $(shell $(PYTHON) --version)$(NC)" || echo "$(RED)✗ Not found$(NC)"
	@echo -n "FFmpeg: "
	@command -v ffmpeg &> /dev/null && echo "$(GREEN)✓ $(NC)" || echo "$(RED)✗ Not found$(NC)"
	@echo -n "Ollama: "
	@command -v ollama &> /dev/null && echo "$(GREEN)✓ $(NC)" || echo "$(RED)✗ Not found$(NC)"

models-info: ## Show info about downloaded models
	@echo "$(GREEN)Ollama Models:$(NC)"
	@ollama list || echo "$(RED)Ollama not running$(NC)"
	@echo ""
	@echo "$(GREEN)Python Packages:$(NC)"
	@if [ -d "$(VENV_DIR)" ]; then \
		$(PIP) list | grep -E '(whisper|TTS|ollama|slugify)'; \
	else \
		echo "$(RED)Virtual environment not created$(NC)"; \
	fi

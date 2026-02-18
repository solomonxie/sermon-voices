---
trigger: always_on
---

# General Guidelines

Welcome to the sermon-voices project. Follow these core standards to maintain consistency and quality.

## Runtime
- Version: Must use Python 3.12.
- Virtual Environment: All operations must use the venv/ directory.
- Executables: Always use paths like venv/bin/python or venv/bin/pip.
- Type Hinting: Use type hints for all functions. Prefer built-in types over typing module imports where possible.
- Environment variables: all secrets or env vars should be in .env, and each variable should have .env.example as reference

## Development Standards
- Makefile: All primary commands (setup, processing, testing) must be reflected in the Makefile.
- Dependencies: Update requirements.txt and .gitignore whenever adding new libraries.
- Permissions: Do not use chmod. Execute scripts via bash or venv/bin/python.
- Deletion: Try not to rm delete things, but prioritize mv xxx /tmp/xxx instead.

## LLM Usage
- Local Models: Prioritize local execution via Ollama.
- Primary Model: qwen3:8b is the currently configured model for extraction and translation.

## Folder Structure
- All main workflow code should be under src/
- All testing related code should be under tests/ with correct category (unit, functional, interface, smoke...)
- All one-shot code should be under scripts/
- Any newly introduced lib or tech stack should be tested with a single script under scripts/poc/
- Logs: all executions of main workflow (exclude poc or testing) should be saved to data/logs/<YYYYmmddHHMMSS>_<name>.txt for future audit.
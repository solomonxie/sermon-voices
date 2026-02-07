---
trigger: always_on
---

# 📜 General Guidelines

Welcome to the **Sermon Voices** project. Follow these core standards to maintain consistency and quality.

### 🐍 Python Environment
> [!IMPORTANT]
> - **Version**: Must use Python **3.12**.
> - **Virtual Environment**: All operations must use the `venv/` directory.
> - **Executables**: Always use paths like `venv/bin/python` or `venv/bin/pip`.
> - **Type Hinting**: Use type hints for all functions. Prefer built-in types over `typing` module imports where possible.

### 🛠️ Development Standards
> [!TIP]
> - **Makefile**: All primary commands (setup, processing, testing) **must** be reflected in the [Makefile](file:///Users/solomonxie/workspace/personal/sermon-voices/Makefile).
> - **Dependencies**: Update `requirements.txt` and `.gitignore` whenever adding new libraries.
> - **Permissions**: **Do not** use `chmod`. Execute scripts via `bash` or `venv/bin/python`.
> - **Deletion**: Try not to `rm` delete thigns, but prioritize `mv xxx /tmp/xxx` instead.

### 🤖 LLM Usage
> [!NOTE]
> - **Local Models**: Prioritize local execution via **Ollama**.
> - **Primary Model**: `qwen3:8b` is the currently configured model for extraction and translation.

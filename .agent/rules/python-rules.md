---
trigger: always_on
---

# 🐍 Python Development Rules

Strict adherence to these rules ensures a robust and maintainable codebase for the **Sermon Voices** project.

### 🌐 Environment & Execution
> [!IMPORTANT]
> - **Virtual Environment**: All operations **must** occur within the `venv/` directory.
> - **Executables**: Always use specific paths:
>   - `venv/bin/python` for running scripts.
>   - `venv/bin/pip` for managing dependencies.
>   - `venv/bin/pytest` for testing.
> - **Isolation**: Never install packages globally or use the system Python.

### 📝 Coding Standards
> [!TIP]
> - **Type Hinting**: Mandatory for **all** function signatures (PEP 484).
>   - Use built-in types (e.g., `list[str]`, `dict[str, int]`) instead of `typing` imports where possible (Python 3.12+).
> - **Docstrings**: Provide Google-style docstrings for complex functions and classes.
> - **Naming**: Follow PEP 8 (snake_case for variables/functions, PascalCase for classes).

### 🛠️ Conflict Prevention
> [!CAUTION]
> - **Built-ins**: Never name variables, functions, or modules after Python built-in names (e.g., `id`, `type`, `input`, `file`, `json`). This prevents shadowing and subtle bugs.
> - **Global State**: Avoid global variables; use constants or configuration objects.

### 🧪 Quality Assurance
- **Tests**: Every new feature or bug fix must include corresponding unit tests in `tests/`.
- **Linting**: Ensure code is clean and passes basic syntax checks before committing.
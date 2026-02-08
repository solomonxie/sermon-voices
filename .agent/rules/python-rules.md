---
trigger: always_on
---

# Python Development Rules

Strict adherence to these rules ensures a robust and maintainable codebase for the sermon-voices project.

## Environment & Execution
- Virtual Environment: All operations must occur within the venv/ directory.
- Executables: Always use specific paths like venv/bin/python for running scripts, venv/bin/pip for managing dependencies, and venv/bin/pytest for testing.
- Isolation: Never install packages globally or use the system Python.

## Coding Standards
- Type Hinting: Mandatory for all function signatures (PEP 484). Use built-in types (e.g., list[str], dict[str, int]) instead of typing imports where possible.
- Docstrings: Provide Google-style docstrings for complex functions and classes.
- Naming: Follow PEP 8 (snake_case for variables/functions, PascalCase for classes).
- Order: Order functions/classes in an order of reading, e.g., main() at top, then the definition function called by main(), then the other functions called by above function.
- Import: Keep the import order as: builtin lib at top in a length ascending order, then a blank line, project module imports, then a blank line, 3rd party lib imports. Then a blank line, global variables definition. Then the main() or core function of the module.
- Exception: Don't ever wrap more than 5 lines of code with try-except block. Use it as less as possible. The main goal is to prevent loop or workflow breaks, if not for this purpose, avoid them and let errors expose. If use try-except, wrap it around function call.
- Parameter: Keep function parameters to a minimum. If there are more than 5 arguments, it means it's highly coupled. Try to derive values within the function where used.
- Global vars: don't use "global xxx" inside a function, it's ugly. Just use it directly.

## Conflict Prevention
- Built-ins: Never name variables, functions, or modules after Python built-in names (e.g., id, type, input, file, json).
- Global State: Avoid global variables; use constants or configuration objects.

## Quality Assurance
- Tests: Every new feature or bug fix must include corresponding unit tests in tests/.
- Linting: Ensure code is clean and passes basic syntax checks before committing.


## Testing

- All tests are located under tests/
- Should distinguish different test types: units, models, functional, interface...
- Testing code should be simple and easy to understand
- Testing code don't need lots of prints/logs
- Testing code don't need try-catch, it should expose error directly
- Run pytest must specify PYTHONPATH=. otherwise it won't recognize import path correctly
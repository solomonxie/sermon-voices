---
trigger: always_on
---

Environment:
- Must use virtualenv for Python at venv/ , and python executables should be in venv/bin/, for example, use "venv/bin/python xx.py" or "venv/bin/pip install xx" instead of "python xx.py" or "pip install xx", or "venv/bin/pytest xx.py" instead of "pytest xx.py"


Type Hinting:
- Must use type hinting for all functions
- Use built-in types instead of importing from typing module when possible
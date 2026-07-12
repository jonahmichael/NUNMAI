"""
conftest.py
===========
Pytest automatically discovers and loads this file before running any
tests, regardless of which test file or directory it's invoked from.

WHY THIS IS NEEDED: unittest.mock.patch() resolves module paths via
importlib.import_module() at the moment the patch is APPLIED (inside a
fixture/test setup), not at file-collection time. Without the project
root on sys.path, patch("nunmai_social.model.fusion.SomeClass") fails
with ModuleNotFoundError even if the test file's own top-level imports
work fine — this single file fixes it project-wide, for every test file,
without needing to repeat sys.path manipulation everywhere.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
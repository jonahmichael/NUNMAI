"""
scripts/init_db.py — one-shot setup: create schema, then seed known entities.

Run: python scripts/init_db.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nunmai_verify.db import init_db
from nunmai_verify.seed_known_entities import seed

if __name__ == "__main__":
    init_db()
    print("schema created.")
    seed()
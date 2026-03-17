#!/usr/bin/env python3
"""Import Kaplan Excel export into the dashboard database.

Usage:
    python scripts/run_import.py path/to/kaplan_export.xlsx
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.excel_import import main

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_import.py <path-to-export.xlsx>")
        sys.exit(1)
    main(sys.argv[1])

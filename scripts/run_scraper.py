#!/usr/bin/env python3
"""Run the Kaplan portal scraper.

Usage:
    python scripts/run_scraper.py              # Headless scrape
    python scripts/run_scraper.py --discover   # Headed browser for DOM inspection
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.runner import main

if __name__ == "__main__":
    main()

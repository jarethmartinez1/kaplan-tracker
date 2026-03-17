#!/usr/bin/env python3
"""Launch the Streamlit dashboard.

Usage:
    streamlit run scripts/run_dashboard.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Streamlit needs this file to be the entry point,
# but the actual app is in dashboard/app.py
from dashboard.app import *  # noqa: F401, F403

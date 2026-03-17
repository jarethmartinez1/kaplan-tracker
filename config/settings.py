import os
from pathlib import Path

from dotenv import load_dotenv
import yaml

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

KAPLAN_USERNAME = os.getenv("KAPLAN_USERNAME", "")
KAPLAN_PASSWORD = os.getenv("KAPLAN_PASSWORD", "")
KAPLAN_PORTAL_URL = os.getenv("KAPLAN_PORTAL_URL", "https://iam.kaplanlearn.com/")
DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "db/kaplan.db")
SELECTORS_PATH = BASE_DIR / "config" / "selectors.yaml"


def load_selectors() -> dict:
    with open(SELECTORS_PATH) as f:
        return yaml.safe_load(f)

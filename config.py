import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Twitter Session Tokens (Browser Cookies)
AUTH_TOKEN = os.getenv("AUTH_TOKEN", "").strip()
CT0 = os.getenv("CT0", "").strip()

# Cookie file path (cached session)
COOKIES_FILE = os.getenv("COOKIES_FILE", str(BASE_DIR / "cookies.json"))

# Scraping settings
DELAY_MIN = float(os.getenv("DELAY_MIN", "3.0"))
DELAY_MAX = float(os.getenv("DELAY_MAX", "6.0"))
DEFAULT_LANG = os.getenv("DEFAULT_LANG", "id-ID")

# Ensure PROXY is None if empty
_raw_proxy = os.getenv("PROXY", "").strip()
PROXY = _raw_proxy if _raw_proxy else None

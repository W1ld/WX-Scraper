import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present
load_dotenv()

BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Instagram Session Tokens (Browser Cookies)
IG_SESSION_ID = os.getenv("IG_SESSION_ID", "").strip()
IG_CSRF_TOKEN = os.getenv("IG_CSRF_TOKEN", "").strip()
IG_DS_USER_ID = os.getenv("IG_DS_USER_ID", "").strip()

# Cookie file path (cached session)
COOKIES_FILE = os.getenv("COOKIES_FILE", str(BASE_DIR / "cookies.json"))

# Scraping settings
DELAY_MIN = float(os.getenv("DELAY_MIN", "3.0"))
DELAY_MAX = float(os.getenv("DELAY_MAX", "6.0"))

# Ensure PROXY is None if empty
_raw_proxy = os.getenv("PROXY", "").strip()
PROXY = _raw_proxy if _raw_proxy else None

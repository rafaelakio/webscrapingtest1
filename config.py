from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv()

APP_URL = os.getenv("APP_URL", "")
AUTH_STATE_FILE = "auth_state.json"
OUTPUT_FILE = ""  # gerado dinamicamente em main.py
SIGLA = "ic5"
SLOW_MO = int(os.getenv("SLOW_MO", "0"))

# Browser a usar: "chrome" (padrão) ou "edge"
BROWSER = os.getenv("BROWSER", "chrome").lower()

# Caminho para o chromedriver.exe (só usado quando BROWSER=chrome)
_BASE_DIR = Path(__file__).parent
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH") or str(_BASE_DIR / "chromedriver.exe")

from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv()

APP_URL = os.getenv("APP_URL", "")
AUTH_STATE_FILE = "auth_state.json"
OUTPUT_FILE = "levantamento_ic5.csv"
SIGLA = "ic5"
SLOW_MO = int(os.getenv("SLOW_MO", "0"))

# Caminho para o chromedriver.exe.
# Se não definido no .env, procura chromedriver.exe na mesma pasta do projeto.
_BASE_DIR = Path(__file__).parent
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH") or str(_BASE_DIR / "chromedriver.exe")

from dotenv import load_dotenv
import os

load_dotenv()

APP_URL = os.getenv("APP_URL", "")
AUTH_STATE_FILE = "auth_state.json"
OUTPUT_FILE = "levantamento_ic5.csv"
SIGLA = "ic5"
SLOW_MO = int(os.getenv("SLOW_MO", "0"))

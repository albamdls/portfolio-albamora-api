import os
from dotenv import load_dotenv

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "Portfolio Chat API")
APP_ENV = os.getenv("APP_ENV", "development")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
HF_CHAT_MODEL = os.getenv("HF_CHAT_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

OWNER_ID = int(os.environ.get("OWNER_ID", 0))
SUPPORT_CHAT = os.environ.get("SUPPORT_CHAT", "https://t.me/GOVINDSUPPORT")
BOT_NAME = os.environ.get("BOT_NAME", "V3 MUSIC")

# Trigger word (bina / ke liye)
TRIGGER = os.environ.get("TRIGGER", "babu")

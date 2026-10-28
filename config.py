import os
from dotenv import load_dotenv

load_dotenv()

def get_required(name):
    value = os.getenv(name, "").strip()
    if not value or value.startswith("YOUR_"):
        raise RuntimeError(f"Missing or placeholder environment variable: {name}")
    return value

API_ID = int(get_required("API_ID"))
API_HASH = get_required("API_HASH")
BOT_TOKEN = get_required("BOT_TOKEN")
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()
MONGO_DB_URI = get_required("MONGO_DB_URI")

SUDO_USERS = {
    int(item.strip())
    for item in os.getenv("SUDO_USERS", "").split(",")
    if item.strip()
}
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
if OWNER_ID:
    SUDO_USERS.add(OWNER_ID)

START_IMAGE = os.getenv("START_IMAGE", "").strip()
SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", "https://t.me/").strip()
SUPPORT_CHANNEL = os.getenv("SUPPORT_CHANNEL", "https://t.me/").strip()
BOT_NAME = os.getenv("BOT_NAME", "V3 MUSIC").strip()
TRIGGER = os.getenv("TRIGGER", "babu").strip()
LOGGER_ID = int(os.getenv("LOGGER_ID", "0"))

if not SUDO_USERS:
    raise RuntimeError("Set SUDO_USERS or OWNER_ID in .env")

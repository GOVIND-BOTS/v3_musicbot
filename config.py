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
OWNER_ID = int(os.getenv("OWNER_ID", "8250224070"))
if OWNER_ID:
    SUDO_USERS.add(OWNER_ID)
    WELCOME_IMAGE = os.getenv("WELCOME_IMAGE", "https://graph.org/file/b2caf282b340e3ef623b7-ea79039fe63e93f7ee.jpg").strip()
OWNER_WELCOME_IMAGE = os.getenv("OWNER_WELCOME_IMAGE", "https://graph.org/file/498e1bd9260f56afa1e75-4a861fa0d4a2830dd9.jpg").strip()

START_IMAGE = os.getenv("START_IMAGE", "https://graph.org/file/6537f82eaef8f90faa91f-fdb34f99a0385ad4b2.jpg").strip()
SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", "https://t.me/GOVIND_BOTS").strip()
SUPPORT_CHANNEL = os.getenv("SUPPORT_CHANNEL", "https://t.me/GOVIND_MP_USERBOT_SPPORT").strip()
BOT_NAME = os.getenv("BOT_NAME", "V3 MUSIC").strip()
TRIGGER = os.getenv("TRIGGER", "babu").strip()


if not SUDO_USERS:
    raise RuntimeError("Set SUDO_USERS or OWNER_ID in .env")

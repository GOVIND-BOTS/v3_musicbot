import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID", "30606308"))
API_HASH = os.environ.get(
    "API_HASH",
    "YOUR_API_HASH"
)

BOT_TOKEN = os.environ.get(
    "BOT_TOKEN",
    "YOUR_BOT_TOKEN"
)

SESSION_STRING = os.environ.get(
    "SESSION_STRING",
    "YOUR_SESSION_STRING"
).strip()

OWNER_ID = int(os.environ.get("OWNER_ID", "8250224070"))

SUPPORT_CHAT = os.environ.get(
    "SUPPORT_CHAT",
    "https://t.me/GOVINDSUPPORT"
)

BOT_NAME = os.environ.get(
    "BOT_NAME",
    "V3 MUSIC"
)

TRIGGER = os.environ.get(
    "TRIGGER",
    "babu"
)

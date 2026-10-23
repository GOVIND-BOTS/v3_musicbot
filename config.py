import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID", "30606308"))
API_HASH = os.environ.get(
    "API_HASH",
    "8630c59667bcf2719a4460ccd4956874"
)

BOT_TOKEN = os.environ.get(
    "BOT_TOKEN",
    "8872915418:AAEtAL133z6v6kfChf-X4x1CXFlGgQMSyLc"
)

SESSION_STRING = os.environ.get(
    "SESSION_STRING",
    "BQAA9-QAs0GCiBcNOWcTX2bVaQ08wcHZCvCaYW5YDovNxHfheeHFtuzi9egtkwPHNsrv5KJq4pjnTh1nqK6zjO4iUzmg4kPvBzBWh9kePLPraw-SOBSlY6kqfbW41Sa041yrXAPmezV5RXQqhqT7A6EOgAM7rHE5ZovdJMrNLf1ZKjMbDDO0RWFM45bF3FFYa2bVqeBaIIbtfDS0mAZFYryG4iek2BxcXXnJPqvd9ULZbKfe2bUv3luP8Er5y9n-hJNnOaStQJ8P8NrvGWGSRMlruGVqdGBjR2_eEqzTNam1KMtPbJVq_Z22-fa72miU9QBXdg0oRJw3h28nqEPMAS4vIYGIqgAAAAIUyk2ZAA"
).strip()

OWNER_ID = int(os.environ.get("OWNER_ID", "8250224070"))

SUPPORT_CHAT = os.environ.get(
    "SUPPORT_CHAT",
    "https://t.me/GOVIND_USERBOT_UPDATE"
)

BOT_NAME = os.environ.get(
    "BOT_NAME",
    "V3 MUSIC"
)

TRIGGER = os.environ.get(
    "TRIGGER",
    "babu"
)

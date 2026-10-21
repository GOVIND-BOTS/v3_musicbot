import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.environ.get("API_ID", "30606308"))
API_HASH = os.environ.get("API_HASH", "8630c59667bcf2719a4460ccd4956874")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8872915418:AAEtAL133z6v6kfChf-X4x1CXFlGgQMSyLc")
SESSION_STRING = os.environ.get("SESSION_STRING", "BQCZzqEArG57x_NmbUL5hTyl8ffRaF1b6RZx_zsRIGAO4s0HMkhCZgeXPrca7luMEQx4cjM7R854sK4_YD0nyUOc4WXkiMrN6vDP_qzduOI2I8TvJSU0YtXtu0mjdYXB0IBZGh-4nchSnY-OufnMZFI_aEhgtmW1JcVIEPjC_o4FiXanq96eZwTmzJKAD0_HyRjAuMV66V79XXAN7pbbvpP2MhrQ4zIZi71lk9wI1IW75Skgt03z4QDpS2Dtj6hWvYlbrRB6UiLUl9hOdKoD_yqbsA-mgx4KAEPrPMfxyba1pxRy7XiH1HKHGop0HSjoDEf21Gri09MqdZ-5SBtnaBdXY5MTKwAAAAIUyk2ZAA")
OWNER_ID = int(os.environ.get("OWNER_ID", "8250224070"))
SUPPORT_CHAT = os.environ.get("SUPPORT_CHAT", "https://t.me/GOVINDSUPPORT")
BOT_NAME = os.environ.get("BOT_NAME", "V3 MUSIC")


TRIGGER = os.environ.get("TRIGGER", "babu")

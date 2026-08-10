import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Discord Bot Token
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")

    # LTC Payment Settings
    LTC_ADDRESS = os.getenv("LTC_ADDRESS", "ltc1qexampleaddress1234567890abcdefghijklmn")
    LTC_AMOUNT = float(os.getenv("LTC_AMOUNT", "0.05"))
    
    # Access Role & Duration
    ACCESS_ROLE_ID = int(os.getenv("ACCESS_ROLE_ID", "0"))
    ACCESS_DURATION_HOURS = int(os.getenv("ACCESS_DURATION_HOURS", "24"))

    # Discord Categories & Roles
    TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", "0"))
    STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID", "0"))
    LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

    # Bot Prefix
    BOT_PREFIX = os.getenv("BOT_PREFIX", "!")

    @classmethod
    def validate(cls):
        missing = []
        if not cls.DISCORD_TOKEN:
            missing.append("DISCORD_TOKEN")
        return missing

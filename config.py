import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Discord Bot Token
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")

    # Litecoin Payment Settings
    LTC_ADDRESS = os.getenv("LTC_ADDRESS", "ltc1qexampleaddress1234567890abcdefghijklmn")
    LTC_AMOUNT = float(os.getenv("LTC_AMOUNT", "0.05"))
    
    # Access Role & Duration
    ACCESS_ROLE_ID = int(os.getenv("ACCESS_ROLE_ID", "0"))
    ACCESS_DURATION_HOURS = float(os.getenv("ACCESS_DURATION_HOURS", "24"))

    # Discord Categories & Roles
    TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", "0"))
    STAFF_ROLE_ID = int(os.getenv("STAFF_ROLE_ID", "0"))
    LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))

    # Bot Prefix
    BOT_PREFIX = os.getenv("BOT_PREFIX", "!")

    # Default Auto-Message Content
    DEFAULT_AUTO_MESSAGE = os.getenv(
        "DEFAULT_AUTO_MESSAGE",
        "ℹ️ **Auto-Message & Support Instructions**\n\n"
        "• To purchase VIP access, send exact LTC amount to the address shown in the embed above.\n"
        "• Click **`Submit TXID`** after sending your payment to instantly receive your buyer role.\n"
        "• Your role will be active for 24 hours from payment verification."
    )

    @classmethod
    def validate(cls):
        missing = []
        if not cls.DISCORD_TOKEN:
            missing.append("DISCORD_TOKEN")
        return missing

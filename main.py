import discord
from discord.ext import commands
import asyncio
import logging
import sys
from config import Config
from database import db

# Ensure UTF-8 output encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

def create_bot(use_privileged_intents: bool = True):
    intents = discord.Intents.default()
    if use_privileged_intents:
        intents.members = True
        intents.message_content = True

    bot = commands.Bot(
        command_prefix=Config.BOT_PREFIX,
        intents=intents,
        help_command=commands.DefaultHelpCommand()
    )

    @bot.event
    async def on_ready():
        logger.info(f"Bot logged in successfully as {bot.user} (ID: {bot.user.id})")
        logger.info(f"Connected to {len(bot.guilds)} guild(s).")
        
        # Sync Slash Commands (app_commands) globally across all servers
        try:
            synced = await bot.tree.sync()
            logger.info(f"Successfully synced {len(synced)} slash command(s) globally.")
            print(f"[+] Synced {len(synced)} slash command(s) with Discord.")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}", exc_info=True)
        
        # Set bot activity
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="Tickets & LTC Payments | /setup_tickets"
        )
        await bot.change_presence(activity=activity)
        
        print("\n" + "="*50)
        print(f"Bot is online! Logged in as: {bot.user}")
        print(f"Guilds connected: {len(bot.guilds)}")
        print(f"Command prefix: {Config.BOT_PREFIX}")
        print("="*50 + "\n")

    @bot.event
    async def on_command_error(ctx, error):
        if isinstance(error, commands.CommandNotFound):
            return
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing argument: `{error.param.name}`. Type `{Config.BOT_PREFIX}help {ctx.command}` for usage.")
        elif isinstance(error, commands.CheckFailure):
            pass # Already handled in cog_check
        else:
            logger.error(f"Command error in {ctx.command}: {error}", exc_info=error)
            await ctx.send(f"❌ An error occurred: `{str(error)}`")

    return bot

async def start_bot_instance(use_privileged_intents: bool):
    bot = create_bot(use_privileged_intents)
    
    initial_extensions = [
        "cogs.tickets",
        "cogs.expiration_task",
        "cogs.admin"
    ]

    async with bot:
        for ext in initial_extensions:
            try:
                await bot.load_extension(ext)
                logger.info(f"Loaded extension: {ext}")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}: {e}", exc_info=True)

        await bot.start(Config.DISCORD_TOKEN)

async def main():
    missing = Config.validate()
    if missing:
        logger.warning(f"Missing environment variables: {', '.join(missing)}")
        logger.warning("Please edit the .env file with your DISCORD_TOKEN before starting the bot.")
        return

    try:
        await start_bot_instance(use_privileged_intents=True)
    except discord.errors.PrivilegedIntentsRequired:
        logger.warning("Privileged intents not enabled in Developer Portal. Retrying with default intents...")
        await start_bot_instance(use_privileged_intents=False)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutting down...")

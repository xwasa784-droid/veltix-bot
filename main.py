import discord
from discord.ext import commands
from aiohttp import web
import asyncio
import logging
import os
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

async def handle_health_check(request):
    return web.Response(text="Bot is running smoothly!", status=200)

async def start_web_server():
    port = int(os.environ.get("PORT", 10000))
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    app.router.add_get("/health", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Health check web server running on port {port}")

def create_bot(use_privileged_intents: bool = True):
    intents = discord.Intents.default()
    if use_privileged_intents:
        try:
            intents.members = True
            intents.message_content = True
        except Exception:
            pass

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
            logger.error(f"Failed to sync slash commands: {e}")
        
        # Set bot activity
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="LTC Payments & Auto-Message | /verify_txid"
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
            logger.error(f"Command error in {ctx.command}: {error}")
            await ctx.send(f"❌ An error occurred: `{str(error)}`")

    return bot

async def start_bot_instance(use_privileged_intents: bool):
    # Start embedded health check server for Render free web service
    try:
        await start_web_server()
    except Exception as e:
        logger.warning(f"Could not start web server: {e}")

    bot = create_bot(use_privileged_intents)
    
    initial_extensions = [
        "cogs.payment",
        "cogs.auto_message",
        "cogs.expiration_task",
        "cogs.admin"
    ]

    async with bot:
        for ext in initial_extensions:
            try:
                await bot.load_extension(ext)
                logger.info(f"Loaded extension: {ext}")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}: {e}")

        await bot.start(Config.DISCORD_TOKEN)

async def main():
    missing = Config.validate()
    if missing:
        logger.warning(f"Missing environment variables: {', '.join(missing)}")
        logger.warning("Please edit the .env file with your DISCORD_TOKEN before starting the bot.")
        return

    try:
        await start_bot_instance(use_privileged_intents=True)
    except (discord.errors.PrivilegedIntentsRequired, discord.errors.ConnectionClosed) as e:
        logger.warning(f"Connection exception with privileged intents ({e}). Retrying with default intents...")
        try:
            await start_bot_instance(use_privileged_intents=False)
        except Exception as err:
            logger.error(f"Failed to start bot instance: {err}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutting down...")

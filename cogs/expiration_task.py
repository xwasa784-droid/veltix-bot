import discord
from discord.ext import commands, tasks
import datetime
import logging
from database import db
from config import Config

logger = logging.getLogger(__name__)

class ExpirationTaskCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.check_role_expirations.start()

    def cog_unload(self):
        self.check_role_expirations.cancel()

    @tasks.loop(seconds=60)
    async def check_role_expirations(self):
        await self.bot.wait_until_ready()
        
        expired_records = db.get_expired_roles()
        if not expired_records:
            return

        logger.info(f"Processing {len(expired_records)} expired role grants...")

        for rec in expired_records:
            record_id = rec["id"]
            user_id = rec["user_id"]
            guild_id = rec["guild_id"]
            role_id = rec["role_id"]

            guild = self.bot.get_guild(guild_id)
            if not guild:
                logger.warning(f"Guild {guild_id} not found when revoking expired role for user {user_id}.")
                db.mark_role_expired(record_id)
                continue

            role = guild.get_role(role_id)
            if not role:
                logger.warning(f"Role {role_id} not found in guild {guild.name} when revoking for user {user_id}.")
                db.mark_role_expired(record_id)
                continue

            try:
                member = await guild.fetch_member(user_id)
                if role in member.roles:
                    await member.remove_roles(role, reason="24-Hour VIP Access Expired")
                    logger.info(f"Successfully removed role {role.name} from {member.name} ({user_id}).")

                # Try sending notification DM to user
                try:
                    dm_embed = discord.Embed(
                        title="⌛ VIP Access Expired",
                        description=f"Your temporary role **{role.name}** in **{guild.name}** has expired after 24 hours.",
                        color=discord.Color.dark_red(),
                        timestamp=datetime.datetime.utcnow()
                    )
                    dm_embed.set_footer(text="Thank you for using our services!")
                    await member.send(embed=dm_embed)
                except Exception:
                    pass # User DMs might be disabled

            except discord.NotFound:
                logger.info(f"User {user_id} no longer in guild {guild.name}.")
            except Exception as e:
                logger.error(f"Error removing role from user {user_id}: {e}")

            # Mark as expired in DB
            db.mark_role_expired(record_id)

            # Post to Log Channel
            log_channel_id = int(db.get_setting("LOG_CHANNEL_ID", str(Config.LOG_CHANNEL_ID)))
            if log_channel_id:
                log_channel = guild.get_channel(log_channel_id)
                if log_channel:
                    log_embed = discord.Embed(
                        title="⌛ Role Access Expired",
                        description=f"Role **{role.name}** removed from <@{user_id}> (User ID: `{user_id}`).",
                        color=discord.Color.dark_orange(),
                        timestamp=datetime.datetime.utcnow()
                    )
                    await log_channel.send(embed=log_embed)

    @check_role_expirations.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(ExpirationTaskCog(bot))

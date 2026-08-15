import discord
from discord import app_commands
from discord.ext import commands
import logging
from config import Config
from database import db

logger = logging.getLogger(__name__)

class AutoMessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin_or_staff(self, user: discord.Member) -> bool:
        if user.guild_permissions.administrator:
            return True
        staff_role_id = int(db.get_setting("STAFF_ROLE_ID", str(Config.STAFF_ROLE_ID)))
        if staff_role_id and hasattr(user, "roles") and any(r.id == staff_role_id for r in user.roles):
            return True
        return False

    @app_commands.command(name="set_automsg", description="Set the custom automated message text for button responses")
    @app_commands.describe(message="The message text/content to display when users click the Auto-Message button")
    async def slash_set_automsg(self, interaction: discord.Interaction, message: str):
        if not self.is_admin_or_staff(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to run this command.", ephemeral=True)
            return

        db.set_setting("AUTO_MESSAGE_CONTENT", message.strip())
        embed = discord.Embed(
            title="✅ Auto-Message Saved",
            description=f"The automated button response message has been updated:\n\n{message.strip()}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="view_automsg", description="View the current saved automated message text")
    async def slash_view_automsg(self, interaction: discord.Interaction):
        if not self.is_admin_or_staff(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to run this command.", ephemeral=True)
            return

        msg_text = db.get_setting("AUTO_MESSAGE_CONTENT", Config.DEFAULT_AUTO_MESSAGE)
        embed = discord.Embed(
            title="ℹ️ Current Auto-Message Content",
            description=msg_text,
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.command(name="set_automsg", help="Set the custom auto-message text: !set_automsg <your message>")
    async def prefix_set_automsg(self, ctx, *, message: str):
        if not self.is_admin_or_staff(ctx.author):
            await ctx.send("❌ You do not have permission to run this command.")
            return

        db.set_setting("AUTO_MESSAGE_CONTENT", message.strip())
        embed = discord.Embed(
            title="✅ Auto-Message Saved",
            description=f"The automated button response message has been updated:\n\n{message.strip()}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="view_automsg", help="View the current saved automated message text")
    async def prefix_view_automsg(self, ctx):
        if not self.is_admin_or_staff(ctx.author):
            await ctx.send("❌ You do not have permission to run this command.")
            return

        msg_text = db.get_setting("AUTO_MESSAGE_CONTENT", Config.DEFAULT_AUTO_MESSAGE)
        embed = discord.Embed(
            title="ℹ️ Current Auto-Message Content",
            description=msg_text,
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AutoMessageCog(bot))

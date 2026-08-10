import discord
from discord import app_commands
from discord.ext import commands
import datetime
import logging
from config import Config
from database import db
from cogs.tickets import TicketDropdownView

logger = logging.getLogger(__name__)

class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin_or_staff(self, user: discord.Member) -> bool:
        if user.guild_permissions.administrator:
            return True
        staff_role_id = int(db.get_setting("STAFF_ROLE_ID", str(Config.STAFF_ROLE_ID)))
        if staff_role_id and hasattr(user, "roles") and any(r.id == staff_role_id for r in user.roles):
            return True
        return False

    async def cog_check(self, ctx):
        if self.is_admin_or_staff(ctx.author):
            return True
        await ctx.send("❌ You do not have permission to use admin commands.", delete_after=5)
        return False

    # --- SHARED HELPER IMPLEMENTATIONS ---
    def _create_setup_tickets_embed(self):
        embed = discord.Embed(
            title="ACCESS 1 DAY ☀️",
            description=(
                "Get access to more than 300 numbers per day\n\n"
                "💵 **Price** : 15€ for 24 hours\n"
                "⚡ **Time to get the role** : Instantly\n"
                "👥 **Max People** : 10 people simultaneous to get the role max\n\n"
                "Click on the option below to start the purchase procedure."
            ),
            color=discord.Color.from_rgb(255, 180, 0)
        )
        image_url = db.get_setting("EMBED_IMAGE_URL", "")
        if image_url:
            embed.set_image(url=image_url)
        elif self.bot.user and self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Automated Access & Payment System")
        return embed

    async def _grant_access_logic(self, guild: discord.Guild, author_name: str, member: discord.Member, hours: float):
        role_id = int(db.get_setting("ACCESS_ROLE_ID", str(Config.ACCESS_ROLE_ID)))
        role = guild.get_role(role_id) if role_id else None

        if not role:
            return False, "❌ Target VIP role not configured. Use `/setrole` or `!set_role` first.", None

        await member.add_roles(role, reason=f"Manual access grant by {author_name}")
        expires_at = db.grant_role_access(member.id, guild.id, role.id, hours)
        expires_unix = int(expires_at.timestamp())

        embed = discord.Embed(
            title="✅ Manual Access Granted",
            description=f"Granted {role.mention} to {member.mention} for **{hours} Hours**.",
            color=discord.Color.green()
        )
        embed.add_field(name="Expires At", value=f"<t:{expires_unix}:F> (<t:{expires_unix}:R>)", inline=False)
        return True, embed, expires_unix

    async def _revoke_access_logic(self, guild: discord.Guild, author_name: str, member: discord.Member):
        role_id = int(db.get_setting("ACCESS_ROLE_ID", str(Config.ACCESS_ROLE_ID)))
        role = guild.get_role(role_id) if role_id else None

        if role and role in member.roles:
            await member.remove_roles(role, reason=f"Manual access revocation by {author_name}")

        if role_id:
            db.revoke_user_access(member.id, role_id)

        embed = discord.Embed(
            title="🛑 Access Revoked",
            description=f"Revoked access and role from {member.mention}.",
            color=discord.Color.red()
        )
        return embed

    def _check_access_logic(self, member: discord.Member):
        role_id = int(db.get_setting("ACCESS_ROLE_ID", str(Config.ACCESS_ROLE_ID)))
        access_rec = db.get_active_user_access(member.id, role_id) if role_id else None

        if not access_rec:
            return discord.Embed(
                title="ℹ️ No Active Access",
                description=f"User {member.mention} does not have an active temporary access subscription.",
                color=discord.Color.light_grey()
            )

        expires_at = datetime.datetime.fromisoformat(access_rec["expires_at"])
        expires_unix = int(expires_at.timestamp())

        embed = discord.Embed(
            title="🔍 Active Access Info",
            color=discord.Color.blue()
        )
        embed.add_field(name="User", value=member.mention, inline=True)
        embed.add_field(name="Granted At", value=access_rec["granted_at"][:19], inline=True)
        embed.add_field(name="Expires At", value=f"<t:{expires_unix}:F>\n(<t:{expires_unix}:R>)", inline=False)
        return embed

    def _settings_logic(self):
        ltc_address = db.get_setting("LTC_ADDRESS", Config.LTC_ADDRESS)
        ltc_amount = db.get_setting("LTC_AMOUNT", str(Config.LTC_AMOUNT))
        role_id = db.get_setting("ACCESS_ROLE_ID", str(Config.ACCESS_ROLE_ID))
        duration = db.get_setting("ACCESS_DURATION_HOURS", str(Config.ACCESS_DURATION_HOURS))
        category_id = db.get_setting("TICKET_CATEGORY_ID", str(Config.TICKET_CATEGORY_ID))
        staff_role_id = db.get_setting("STAFF_ROLE_ID", str(Config.STAFF_ROLE_ID))
        log_channel_id = db.get_setting("LOG_CHANNEL_ID", str(Config.LOG_CHANNEL_ID))

        role_mention = f"<@&{role_id}>" if role_id != "0" else "`Not Set`"
        category_str = f"<#{category_id}>" if category_id != "0" else "`None`"
        staff_str = f"<@&{staff_role_id}>" if staff_role_id != "0" else "`None`"
        log_str = f"<#{log_channel_id}>" if log_channel_id != "0" else "`None`"

        embed = discord.Embed(
            title="⚙️ Current Bot Configuration",
            color=discord.Color.blue()
        )
        embed.add_field(name="💳 LTC Address", value=f"`{ltc_address}`", inline=False)
        embed.add_field(name="💰 Required LTC", value=f"`{ltc_amount} LTC`", inline=True)
        embed.add_field(name="⏱️ Role Duration", value=f"`{duration} Hours`", inline=True)
        embed.add_field(name="👑 Target Role", value=role_mention, inline=True)
        embed.add_field(name="📁 Ticket Category", value=category_str, inline=True)
        embed.add_field(name="🛡️ Staff Role", value=staff_str, inline=True)
        embed.add_field(name="📋 Log Channel", value=log_str, inline=True)
        return embed

    # ==========================================
    # ⚡ DISCORD SLASH COMMANDS (app_commands)
    # ==========================================

    @app_commands.command(name="setup_tickets", description="Deploy the ticket launcher embed with dropdown menu")
    async def slash_setup_tickets(self, interaction: discord.Interaction):
        if not self.is_admin_or_staff(interaction.user):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ You do not have permission to run this command.", ephemeral=True)
            return
        embed = self._create_setup_tickets_embed()
        view = TicketDropdownView()
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, view=view)
            else:
                await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Error in slash_setup_tickets: {e}")

    @app_commands.command(name="giveaccess", description="Manually grant temporary access role to a user")
    @app_commands.describe(user="The user to grant access to", hours="Access duration in hours (default: 24)")
    async def slash_giveaccess(self, interaction: discord.Interaction, user: discord.Member, hours: float = 24.0):
        if not self.is_admin_or_staff(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to run this command.", ephemeral=True)
            return
        success, result, _ = await self._grant_access_logic(interaction.guild, interaction.user.name, user, hours)
        if success:
            await interaction.response.send_message(embed=result)
        else:
            await interaction.response.send_message(content=result, ephemeral=True)

    @app_commands.command(name="addaccess", description="Alias for giveaccess: grant access role to a user")
    @app_commands.describe(user="The user to grant access to", hours="Access duration in hours (default: 24)")
    async def slash_addaccess(self, interaction: discord.Interaction, user: discord.Member, hours: float = 24.0):
        await self.slash_giveaccess(interaction, user, hours)

    @app_commands.command(name="removeaccess", description="Revoke temporary access role from a user")
    @app_commands.describe(user="The user to revoke access from")
    async def slash_removeaccess(self, interaction: discord.Interaction, user: discord.Member):
        if not self.is_admin_or_staff(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to run this command.", ephemeral=True)
            return
        embed = await self._revoke_access_logic(interaction.guild, interaction.user.name, user)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="checkaccess", description="Check active access status and remaining time for a user")
    @app_commands.describe(user="The user to check")
    async def slash_checkaccess(self, interaction: discord.Interaction, user: discord.Member):
        if not self.is_admin_or_staff(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to run this command.", ephemeral=True)
            return
        embed = self._check_access_logic(user)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setltc", description="Set receiver LTC address and payment amount")
    @app_commands.describe(address="Litecoin receiving wallet address", amount="Required LTC payment amount")
    async def slash_setltc(self, interaction: discord.Interaction, address: str, amount: float):
        if not self.is_admin_or_staff(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to run this command.", ephemeral=True)
            return
        db.set_setting("LTC_ADDRESS", address.strip())
        db.set_setting("LTC_AMOUNT", str(amount))
        embed = discord.Embed(title="✅ LTC Settings Updated", color=discord.Color.green())
        embed.add_field(name="Wallet Address", value=f"`{address.strip()}`", inline=False)
        embed.add_field(name="Required Amount", value=f"`{amount} LTC`", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setrole", description="Set the VIP access role to grant upon payment")
    @app_commands.describe(role="The Discord role to grant")
    async def slash_setrole(self, interaction: discord.Interaction, role: discord.Role):
        if not self.is_admin_or_staff(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to run this command.", ephemeral=True)
            return
        db.set_setting("ACCESS_ROLE_ID", str(role.id))
        embed = discord.Embed(
            title="✅ Access Role Updated",
            description=f"VIP Access Role set to {role.mention} (ID: `{role.id}`)",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="setduration", description="Set default access duration in hours (e.g. 24)")
    @app_commands.describe(hours="Access duration in hours")
    async def slash_setduration(self, interaction: discord.Interaction, hours: float):
        if not self.is_admin_or_staff(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to run this command.", ephemeral=True)
            return
        db.set_setting("ACCESS_DURATION_HOURS", str(hours))
        embed = discord.Embed(
            title="✅ Duration Updated",
            description=f"VIP Access Duration set to **{hours} Hours**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="settings", description="View current bot configuration")
    async def slash_settings(self, interaction: discord.Interaction):
        if not self.is_admin_or_staff(interaction.user):
            await interaction.response.send_message("❌ You do not have permission to run this command.", ephemeral=True)
            return
        embed = self._settings_logic()
        await interaction.response.send_message(embed=embed)

    # ==========================================
    # 📌 TRADITIONAL PREFIX COMMANDS (!)
    # ==========================================

    @commands.command(name="setup_tickets", help="Deploy the ticket launcher embed with dropdown menu")
    async def prefix_setup_tickets(self, ctx):
        embed = self._create_setup_tickets_embed()
        view = TicketDropdownView()
        await ctx.send(embed=embed, view=view)
        try:
            await ctx.message.delete()
        except Exception:
            pass

    @commands.command(name="set_ltc", help="Set receiver LTC address & amount: !set_ltc <address> <amount>")
    async def prefix_set_ltc(self, ctx, address: str, amount: float):
        db.set_setting("LTC_ADDRESS", address.strip())
        db.set_setting("LTC_AMOUNT", str(amount))
        embed = discord.Embed(title="✅ LTC Settings Updated", color=discord.Color.green())
        embed.add_field(name="Wallet Address", value=f"`{address.strip()}`", inline=False)
        embed.add_field(name="Required Amount", value=f"`{amount} LTC`", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="set_role", help="Set the VIP access role: !set_role @Role")
    async def prefix_set_role(self, ctx, role: discord.Role):
        db.set_setting("ACCESS_ROLE_ID", str(role.id))
        embed = discord.Embed(
            title="✅ Access Role Updated",
            description=f"VIP Access Role set to {role.mention} (ID: `{role.id}`)",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="set_duration", help="Set duration in hours: !set_duration <hours>")
    async def prefix_set_duration(self, ctx, hours: float):
        db.set_setting("ACCESS_DURATION_HOURS", str(hours))
        embed = discord.Embed(
            title="✅ Duration Updated",
            description=f"VIP Access Duration set to **{hours} Hours**",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="grant_access", aliases=["giveaccess", "addaccess"], help="Grant access: !grant_access @user [hours]")
    async def prefix_grant_access(self, ctx, member: discord.Member, hours: float = 24.0):
        success, result, _ = await self._grant_access_logic(ctx.guild, ctx.author.name, member, hours)
        if success:
            await ctx.send(embed=result)
        else:
            await ctx.send(content=result)

    @commands.command(name="revoke_access", aliases=["removeaccess"], help="Revoke access: !revoke_access @user")
    async def prefix_revoke_access(self, ctx, member: discord.Member):
        embed = await self._revoke_access_logic(ctx.guild, ctx.author.name, member)
        await ctx.send(embed=embed)

    @commands.command(name="check_access", aliases=["checkaccess"], help="Check user access: !check_access @user")
    async def prefix_check_access(self, ctx, member: discord.Member):
        embed = self._check_access_logic(member)
        await ctx.send(embed=embed)

    @commands.command(name="settings", help="View current bot configuration")
    async def prefix_settings(self, ctx):
        embed = self._settings_logic()
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AdminCog(bot))

import discord
from discord import app_commands
from discord.ext import commands
import datetime
import asyncio
import logging
from config import Config
from database import db
from services.ltc_verifier import LTCVerifier

logger = logging.getLogger(__name__)

# --- MODAL FOR TXID SUBMISSION ---
class TXIDModal(discord.ui.Modal, title="Submit Litecoin TXID"):
    txid_input = discord.ui.TextInput(
        label="Litecoin Transaction ID (TXID)",
        placeholder="Enter 64-character hex transaction ID",
        min_length=64,
        max_length=64,
        required=True,
        style=discord.TextStyle.short
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        txid = self.txid_input.value.strip().lower()
        user = interaction.user
        guild = interaction.guild

        if not guild:
            await interaction.followup.send("❌ Error: Command must be used within a server.", ephemeral=True)
            return

        # Check if already processed
        if db.is_txid_used(txid):
            embed = discord.Embed(
                title="❌ Transaction Already Used",
                description=f"The TXID `{txid[:12]}...` has already been redeemed for access.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Fetch current dynamic settings or fallbacks
        ltc_address = db.get_setting("LTC_ADDRESS", Config.LTC_ADDRESS)
        ltc_amount = float(db.get_setting("LTC_AMOUNT", str(Config.LTC_AMOUNT)))
        role_id = int(db.get_setting("ACCESS_ROLE_ID", str(Config.ACCESS_ROLE_ID)))
        duration_hours = float(db.get_setting("ACCESS_DURATION_HOURS", str(Config.ACCESS_DURATION_HOURS)))

        # Find target access role
        role = guild.get_role(role_id) if role_id else None
        if not role:
            embed = discord.Embed(
                title="⚠️ Role Configuration Error",
                description="The target VIP access role is not configured properly. Please notify server administrators.",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Verify TXID on Litecoin Blockchain
        await interaction.followup.send("🔎 Verifying your transaction on the Litecoin blockchain...", ephemeral=True)

        is_valid, received_amount, msg = await LTCVerifier.verify_transaction(txid, ltc_address, ltc_amount)

        # Retry check once after 3s if unconfirmed propagation
        if not is_valid and ("not found" in msg.lower() or "propagation" in msg.lower()):
            await asyncio.sleep(3)
            is_valid, received_amount, msg = await LTCVerifier.verify_transaction(txid, ltc_address, ltc_amount)

        if not is_valid:
            embed = discord.Embed(
                title="❌ Payment Verification Failed",
                description=msg,
                color=discord.Color.red()
            )
            embed.add_field(name="Expected Address", value=f"`{ltc_address}`", inline=False)
            embed.add_field(name="Expected Amount", value=f"`{ltc_amount} LTC`", inline=True)
            embed.add_field(name="Submitted TXID", value=f"`{txid}`", inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Payment Verified!
        try:
            member = await guild.fetch_member(user.id)
            await member.add_roles(role, reason=f"LTC Payment Verified (TXID: {txid})")
        except Exception as e:
            logger.error(f"Failed to add role {role_id} to user {user.id}: {e}")
            embed = discord.Embed(
                title="⚠️ Role Assignment Failed",
                description=f"Payment verified ({received_amount} LTC), but failed to assign role. Please contact staff.\nError: `{e}`",
                color=discord.Color.gold()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Record in Database
        db.record_payment(txid, user.id, received_amount)
        expires_at = db.grant_role_access(user.id, guild.id, role.id, duration_hours)
        expires_unix = int(expires_at.timestamp())

        # Response to user
        success_embed = discord.Embed(
            title="🎉 VIP Access Granted!",
            description=f"Your payment of **{received_amount:.6f} LTC** has been verified on-chain!",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        success_embed.add_field(name="Granted Role", value=role.mention, inline=True)
        success_embed.add_field(name="Access Duration", value=f"{int(duration_hours)} Hours", inline=True)
        success_embed.add_field(name="Expires At", value=f"<t:{expires_unix}:F>\n(<t:{expires_unix}:R>)", inline=False)
        success_embed.add_field(name="Transaction Hash", value=f"`{txid}`", inline=False)
        success_embed.set_footer(text="Auto-Access Payment System")

        await interaction.followup.send(embed=success_embed, ephemeral=True)

        # Post confirmation in current channel
        channel_embed = discord.Embed(
            title="✅ Access Purchased & Activated",
            description=f"User {user.mention} successfully purchased access for **{int(duration_hours)} hours**!\nRole {role.mention} has been assigned.",
            color=discord.Color.green()
        )
        channel_embed.add_field(name="Expires", value=f"<t:{expires_unix}:R>", inline=True)
        channel_embed.add_field(name="TXID", value=f"`{txid[:16]}...`", inline=True)
        await interaction.channel.send(embed=channel_embed)

        # Send to Log Channel if configured
        log_channel_id = int(db.get_setting("LOG_CHANNEL_ID", str(Config.LOG_CHANNEL_ID)))
        if log_channel_id:
            log_channel = guild.get_channel(log_channel_id)
            if log_channel:
                log_embed = discord.Embed(
                    title="🧾 LTC Access Purchase Log",
                    color=discord.Color.blue(),
                    timestamp=datetime.datetime.utcnow()
                )
                log_embed.add_field(name="User", value=f"{user} ({user.id})", inline=True)
                log_embed.add_field(name="Amount Paid", value=f"{received_amount} LTC", inline=True)
                log_embed.add_field(name="Role Granted", value=role.name, inline=True)
                log_embed.add_field(name="Expires", value=f"<t:{expires_unix}:F>", inline=False)
                log_embed.add_field(name="TXID", value=f"`{txid}`", inline=False)
                await log_channel.send(embed=log_embed)

# --- PERSISTENT BUTTON VIEW FOR PAYMENT & AUTO-MESSAGE ---
class PaymentPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Submit TXID", style=discord.ButtonStyle.success, emoji="💸", custom_id="submit_txid_btn")
    async def submit_txid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_modal(TXIDModal())
        except Exception as e:
            logger.error(f"Error opening TXID modal: {e}")

    @discord.ui.button(label="Auto-Message / Info", style=discord.ButtonStyle.primary, emoji="ℹ️", custom_id="auto_message_btn")
    async def auto_message_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            msg_text = db.get_setting("AUTO_MESSAGE_CONTENT", Config.DEFAULT_AUTO_MESSAGE)
            embed = discord.Embed(
                title="ℹ️ Support & Automated Information",
                description=msg_text,
                color=discord.Color.blue()
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error responding to auto-message button: {e}")

class PaymentCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Register persistent view on cog load
        self.bot.add_view(PaymentPanelView())

    def build_payment_embed(self, guild: discord.Guild):
        ltc_address = db.get_setting("LTC_ADDRESS", Config.LTC_ADDRESS)
        ltc_amount = float(db.get_setting("LTC_AMOUNT", str(Config.LTC_AMOUNT)))
        duration_hours = float(db.get_setting("ACCESS_DURATION_HOURS", str(Config.ACCESS_DURATION_HOURS)))

        embed = discord.Embed(
            title="ACCESS 1 DAY ☀️ - VIP Purchase",
            description=(
                "**Get access to more than 300 numbers per day**\n\n"
                "💵 **Price** : 15€ for 24 hours\n"
                "⚡ **Time to get the role** : Instantly\n"
                "👥 **Max People** : 10 people simultaneous to get the role max\n\n"
                "Follow the payment instructions below to receive your role instantly:"
            ),
            color=discord.Color.from_rgb(255, 180, 0)
        )
        image_url = db.get_setting("EMBED_IMAGE_URL", "")
        if image_url:
            embed.set_image(url=image_url)

        embed.add_field(name="💳 Litecoin (LTC) Address", value=f"```\n{ltc_address}\n```", inline=False)
        embed.add_field(name="💰 Required Payment Amount", value=f"**`{ltc_amount} LTC`**", inline=True)
        embed.add_field(name="⏱️ Access Duration", value=f"**`{int(duration_hours)} Hours`**", inline=True)
        embed.add_field(
            name="📋 Instructions",
            value=(
                f"1. Send **exactly** `{ltc_amount} LTC` to the wallet address above.\n"
                "2. Copy your 64-character Transaction ID (TXID).\n"
                "3. Click the **`Submit TXID`** button below to instantly verify your payment and receive your role!\n"
                "4. Click **`Auto-Message / Info`** for additional details."
            ),
            inline=False
        )
        embed.set_footer(text="Automated LTC Payment System • 24/7 Verification")
        return embed

    # --- LISTENER FOR TICKET CREATION BY EXTERNAL BOT (TICKET TOOL) ---
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        if not isinstance(channel, discord.TextChannel):
            return

        category_id = int(db.get_setting("TICKET_CATEGORY_ID", str(Config.TICKET_CATEGORY_ID)))
        channel_name_lower = channel.name.lower()
        
        # Check if channel is inside ticket category or matches ticket channel naming
        is_ticket_category = category_id > 0 and channel.category_id == category_id
        is_ticket_name = any(channel_name_lower.startswith(prefix) for prefix in ["ticket", "support", "buy", "claim"])

        if is_ticket_category or is_ticket_name:
            logger.info(f"Detected new ticket channel: #{channel.name} ({channel.id}). Sending payment embed...")
            # Wait 1.5 seconds for external ticket bot to finish channel creation setup
            await asyncio.sleep(1.5)
            try:
                embed = self.build_payment_embed(channel.guild)
                view = PaymentPanelView()
                await channel.send(embed=embed, view=view)
            except Exception as e:
                logger.error(f"Error auto-posting payment embed to channel #{channel.name}: {e}")

    # --- COMMAND TO MANUALLY SEND PAYMENT & AUTO-MESSAGE PANEL ---
    @app_commands.command(name="send_payment_panel", description="Post the payment & auto-message button panel in the current channel")
    async def slash_send_payment_panel(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Admin permissions required.", ephemeral=True)
            return

        embed = self.build_payment_embed(interaction.guild)
        view = PaymentPanelView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Payment panel deployed!", ephemeral=True)

    @app_commands.command(name="verify_txid", description="Verify a Litecoin TXID and redeem 24-hour access role")
    @app_commands.describe(txid="Your 64-character Litecoin Transaction ID")
    async def slash_verify_txid(self, interaction: discord.Interaction, txid: str):
        txid = txid.strip().lower()
        if len(txid) != 64:
            await interaction.response.send_message("❌ Invalid TXID. Transaction ID must be a 64-character hexadecimal hash.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        if db.is_txid_used(txid):
            await interaction.followup.send("❌ This TXID has already been redeemed.", ephemeral=True)
            return

        ltc_address = db.get_setting("LTC_ADDRESS", Config.LTC_ADDRESS)
        ltc_amount = float(db.get_setting("LTC_AMOUNT", str(Config.LTC_AMOUNT)))
        role_id = int(db.get_setting("ACCESS_ROLE_ID", str(Config.ACCESS_ROLE_ID)))
        duration_hours = float(db.get_setting("ACCESS_DURATION_HOURS", str(Config.ACCESS_DURATION_HOURS)))

        role = interaction.guild.get_role(role_id) if role_id else None
        if not role:
            await interaction.followup.send("⚠️ Access role is not configured.", ephemeral=True)
            return

        is_valid, received_amount, msg = await LTCVerifier.verify_transaction(txid, ltc_address, ltc_amount)
        if not is_valid:
            await interaction.followup.send(f"❌ Verification failed: {msg}", ephemeral=True)
            return

        member = await interaction.guild.fetch_member(interaction.user.id)
        await member.add_roles(role, reason=f"LTC Payment Verified (TXID: {txid})")
        db.record_payment(txid, interaction.user.id, received_amount)
        expires_at = db.grant_role_access(interaction.user.id, interaction.guild.id, role.id, duration_hours)
        expires_unix = int(expires_at.timestamp())

        embed = discord.Embed(
            title="🎉 VIP Access Granted!",
            description=f"Verified payment of **{received_amount:.6f} LTC**!\nRole {role.mention} granted for **{int(duration_hours)} Hours**.",
            color=discord.Color.green()
        )
        embed.add_field(name="Expires At", value=f"<t:{expires_unix}:F> (<t:{expires_unix}:R>)", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.command(name="send_panel", help="Manually deploy payment & auto-message button panel")
    async def prefix_send_panel(self, ctx):
        if not ctx.author.guild_permissions.administrator:
            await ctx.send("❌ Admin permissions required.")
            return

        embed = self.build_payment_embed(ctx.guild)
        view = PaymentPanelView()
        await ctx.send(embed=embed, view=view)

    @commands.command(name="verify", help="Verify TXID: !verify <64-char txid>")
    async def prefix_verify(self, ctx, txid: str):
        txid = txid.strip().lower()
        if len(txid) != 64:
            await ctx.send("❌ Invalid TXID format. Must be 64 characters.")
            return

        if db.is_txid_used(txid):
            await ctx.send("❌ This TXID has already been redeemed.")
            return

        ltc_address = db.get_setting("LTC_ADDRESS", Config.LTC_ADDRESS)
        ltc_amount = float(db.get_setting("LTC_AMOUNT", str(Config.LTC_AMOUNT)))
        role_id = int(db.get_setting("ACCESS_ROLE_ID", str(Config.ACCESS_ROLE_ID)))
        duration_hours = float(db.get_setting("ACCESS_DURATION_HOURS", str(Config.ACCESS_DURATION_HOURS)))

        role = ctx.guild.get_role(role_id) if role_id else None
        if not role:
            await ctx.send("⚠️ Access role is not configured.")
            return

        msg_wait = await ctx.send("🔎 Verifying transaction on Litecoin blockchain...")
        is_valid, received_amount, msg = await LTCVerifier.verify_transaction(txid, ltc_address, ltc_amount)
        if not is_valid:
            await msg_wait.edit(content=f"❌ Verification failed: {msg}")
            return

        await ctx.author.add_roles(role, reason=f"LTC Payment Verified (TXID: {txid})")
        db.record_payment(txid, ctx.author.id, received_amount)
        expires_at = db.grant_role_access(ctx.author.id, ctx.guild.id, role.id, duration_hours)
        expires_unix = int(expires_at.timestamp())

        embed = discord.Embed(
            title="🎉 VIP Access Granted!",
            description=f"Verified payment of **{received_amount:.6f} LTC**!\nRole {role.mention} granted for **{int(duration_hours)} Hours**.",
            color=discord.Color.green()
        )
        embed.add_field(name="Expires At", value=f"<t:{expires_unix}:F> (<t:{expires_unix}:R>)", inline=False)
        await msg_wait.edit(content=None, embed=embed)

async def setup(bot):
    await bot.add_cog(PaymentCog(bot))

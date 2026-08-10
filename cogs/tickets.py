import discord
from discord.ext import commands
import datetime
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
            await interaction.followup.send("❌ Error: Command must be used in a server.", ephemeral=True)
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

        # Find role
        role = guild.get_role(role_id) if role_id else None
        if not role:
            embed = discord.Embed(
                title="⚠️ Role Configuration Error",
                description="The target VIP access role is not properly configured. Please contact staff.",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Verify TXID on Litecoin Blockchain
        verifying_msg = await interaction.followup.send("🔎 Verifying your transaction on the Litecoin blockchain...", ephemeral=True)

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

        # Payment Successful!
        # Add role to member
        try:
            member = await guild.fetch_member(user.id)
            await member.add_roles(role, reason=f"LTC Auto-Access Payment Verified (TXID: {txid})")
        except Exception as e:
            logger.error(f"Failed to add role {role_id} to user {user.id}: {e}")
            embed = discord.Embed(
                title="⚠️ Role Assignment Failed",
                description=f"Payment verified ({received_amount} LTC), but failed to assign role. Please notify an administrator.\nError: `{e}`",
                color=discord.Color.gold()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Record in Database
        db.record_payment(txid, user.id, received_amount)
        expires_at = db.grant_role_access(user.id, guild.id, role.id, duration_hours)

        # Discord Unix Timestamp format for dynamic countdown display
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

        # Announce in ticket channel
        ticket_channel_embed = discord.Embed(
            title="✅ Access Purchased & Activated",
            description=f"User {user.mention} successfully purchased access for **{int(duration_hours)} hours**!\nRole {role.mention} has been assigned.",
            color=discord.Color.green()
        )
        ticket_channel_embed.add_field(name="Expires", value=f"<t:{expires_unix}:R>", inline=True)
        ticket_channel_embed.add_field(name="TXID", value=f"`{txid[:16]}...`", inline=True)
        await interaction.channel.send(embed=ticket_channel_embed)

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

# --- VIEWS FOR TICKET CHANNELS ---
class TicketChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Submit TXID", style=discord.ButtonStyle.success, emoji="💸", custom_id="submit_txid_btn")
    async def submit_txid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not interaction.response.is_done():
                await interaction.response.send_modal(TXIDModal())
        except Exception as e:
            logger.error(f"Error opening TXID modal: {e}")

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="close_ticket_btn")
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        db.close_ticket(channel.id)

        close_embed = discord.Embed(
            title="🔒 Ticket Closing",
            description="This ticket channel will be closed and deleted in 5 seconds...",
            color=discord.Color.red()
        )
        try:
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=close_embed)
            else:
                await interaction.followup.send(embed=close_embed)
        except Exception as e:
            logger.error(f"Error responding to close ticket button: {e}")
        
        await discord.utils.sleep_until(datetime.datetime.utcnow() + datetime.timedelta(seconds=5))
        try:
            await channel.delete(reason="Ticket Closed")
        except Exception as e:
            logger.error(f"Failed to delete ticket channel {channel.id}: {e}")

# --- DROPDOWN SELECT FOR MAIN LAUNCHER ---
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="Support Ticket",
                value="support",
                description="Open a support ticket for help or inquiries.",
                emoji="📩"
            ),
            discord.SelectOption(
                label="Purchase VIP Access",
                value="purchase",
                description="Purchase 24h Role Access via Litecoin (LTC).",
                emoji="💎"
            )
        ]
        super().__init__(
            placeholder="Choose a ticket type to open...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_dropdown_select"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        user = interaction.user
        ticket_type = self.values[0]

        # Fetch Category & Staff Role
        category_id = int(db.get_setting("TICKET_CATEGORY_ID", str(Config.TICKET_CATEGORY_ID)))
        staff_role_id = int(db.get_setting("STAFF_ROLE_ID", str(Config.STAFF_ROLE_ID)))
        
        category = guild.get_channel(category_id) if category_id and isinstance(guild.get_channel(category_id), discord.CategoryChannel) else None
        staff_role = guild.get_role(staff_role_id) if staff_role_id else None

        # Build Channel Permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False, view_channel=False),
            user: discord.PermissionOverwrite(read_messages=True, view_channel=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, view_channel=True, send_messages=True, manage_channels=True)
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, view_channel=True, send_messages=True)

        prefix = "support" if ticket_type == "support" else "buy"
        channel_name = f"{prefix}-{user.name.lower()[:15]}"

        try:
            ticket_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=f"{ticket_type.capitalize()} ticket created by {user.name} ({user.id})"
            )
        except Exception as e:
            logger.error(f"Error creating channel for user {user.id}: {e}")
            await interaction.followup.send(f"❌ Failed to create ticket channel: {e}", ephemeral=True)
            return

        # Record ticket in DB
        db.create_ticket(ticket_channel.id, user.id, ticket_type)

        if ticket_type == "support":
            embed = discord.Embed(
                title="📩 Support Ticket Opened",
                description=f"Welcome {user.mention}!\n\nPlease describe your issue or question in detail. Our support staff will assist you shortly.",
                color=discord.Color.blue()
            )
            embed.set_footer(text="Click 'Close Ticket' when your issue is resolved.")
            view = TicketChannelView()
            # Remove submit txid button for support tickets
            view.remove_item(view.submit_txid_button)
            await ticket_channel.send(embed=embed, view=view)

        else: # purchase
            ltc_address = db.get_setting("LTC_ADDRESS", Config.LTC_ADDRESS)
            ltc_amount = float(db.get_setting("LTC_AMOUNT", str(Config.LTC_AMOUNT)))
            duration_hours = float(db.get_setting("ACCESS_DURATION_HOURS", str(Config.ACCESS_DURATION_HOURS)))

            embed = discord.Embed(
                title="ACCESS 1 DAY ☀️ - VIP Purchase",
                description=(
                    f"Hello {user.mention}!\n\n"
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
                    "3. Click the **`Submit TXID`** button below to instantly verify your payment and receive your role!"
                ),
                inline=False
            )
            embed.set_footer(text="Automated LTC Payment System • 24/7 Verification")
            
            view = TicketChannelView()
            await ticket_channel.send(content=f"{user.mention}", embed=embed, view=view)

        await interaction.followup.send(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)

class TicketDropdownView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())

class TicketsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Register persistent views on cog load
        self.bot.add_view(TicketDropdownView())
        self.bot.add_view(TicketChannelView())

async def setup(bot):
    await bot.add_cog(TicketsCog(bot))

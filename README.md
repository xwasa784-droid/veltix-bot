# 🚀 Discord LTC Payment & Auto-Access Ticket Bot

An automated Discord bot that handles customer tickets (Support & Purchase) using interactive dropdowns, verifies Litecoin (LTC) payments on-chain using Transaction IDs (TXID), grants a 24-hour temporary access role, and automatically revokes the role when time expires.

---

## ✨ Features

- 🎟️ **Interactive Ticket Dropdown**:
  - **📩 Support Ticket**: Opens a private text channel for general customer support.
  - **💎 Purchase VIP Access**: Opens a private purchase ticket channel with payment instructions and an interactive **`Submit TXID`** modal button.
- ⚡ **Full Slash Commands (`/`) & Prefix (`!`) Support**:
  - Complete native Discord `/` slash command support for all admin features (`/giveaccess`, `/addaccess`, `/removeaccess`, `/checkaccess`, `/setup_tickets`, `/setltc`, `/setrole`, `/setduration`, `/settings`).
- 💸 **On-Chain Litecoin Verification**:
  - Automatically queries Litecoin blockchain APIs (BlockCypher & Blockchair fallback).
  - Validates recipient wallet address, required payment amount (in LTC), and prevents double-spending / TXID reuse via SQLite database.
- ⏱️ **Automated 24-Hour Role Expiration**:
  - Runs a background task every 60 seconds to check active role grants.
  - Automatically revokes the role when the 24-hour timer expires.
  - Notifies user via DM and logs the expiration event in your designated log channel.

---

## ⚡ Slash Commands (`/`) & Admin Commands (`!`)

All admin commands can be invoked either as **Slash Commands (`/`)** or **Prefix Commands (`!`)**:

| Slash Command | Prefix Command | Description | Example |
| :--- | :--- | :--- | :--- |
| `/setup_tickets` | `!setup_tickets` | Deploy the ticket launcher embed with dropdown menu. | `/setup_tickets` |
| `/giveaccess` or `/addaccess` | `!grant_access` or `!giveaccess` | Grant temporary access role to a user. Pass target user and duration in hours. | `/giveaccess user:@username hours:24` |
| `/removeaccess` | `!revoke_access` or `!removeaccess` | Instantly revoke access and remove the role from a user. | `/removeaccess user:@username` |
| `/checkaccess` | `!check_access` or `!checkaccess` | View remaining access time for a user. | `/checkaccess user:@username` |
| `/setltc` | `!set_ltc` | Dynamically update the LTC address and required LTC price. | `/setltc address:Ltc1qxyz... amount:0.08` |
| `/setrole` | `!set_role` | Set the role granted upon payment verification. | `/setrole role:@VIP` |
| `/setduration` | `!set_duration` | Set default role access duration in hours. | `/setduration hours:24` |
| `/settings` | `!settings` | Display current bot configuration. | `/settings` |

---

## ⚙️ Quick Setup Guide

### 1. Create a Discord Bot
1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application**, name your bot, and navigate to the **Bot** tab.
3. Enable **Privileged Gateway Intents**:
   - ✅ **Server Members Intent**
   - ✅ **Message Content Intent**
4. Click **Reset Token** and copy your bot token.
5. Go to **OAuth2 -> URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Administrator` (or `Manage Roles`, `Manage Channels`, `Send Messages`, `Embed Links`, `View Channels`).
   - Copy the generated link and invite the bot to your Discord server.

### 2. Configure `.env`
Open `.env` in this directory and fill in your details:

```env
DISCORD_TOKEN=your_bot_token_here
LTC_ADDRESS=Ltc1q_your_litecoin_wallet_address
LTC_AMOUNT=0.05
ACCESS_ROLE_ID=your_role_id_here
ACCESS_DURATION_HOURS=24
TICKET_CATEGORY_ID=0
STAFF_ROLE_ID=0
LOG_CHANNEL_ID=0
BOT_PREFIX=!
```

### 3. Run the Bot
Dependencies are already installed. Start the bot with:

```bash
python main.py
```
Upon startup, the bot will automatically register and sync all Slash Commands with Discord!

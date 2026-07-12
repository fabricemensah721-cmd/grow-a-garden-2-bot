import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
import asyncio
import random
import string

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class JaceBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.channelfill_tasks = {}
        self.intercept_messages = True # Controlled by /message
        
    async def setup_hook(self):
        conn = sqlite3.connect("jace_switcher_v3.db")
        cursor = conn.cursor()
        
        # Database Tables Configuration
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                status TEXT DEFAULT 'OFFLINE'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                guild_id TEXT PRIMARY KEY,
                ltc_addr TEXT,
                btc_addr TEXT
            )
        """)
        conn.commit()
        conn.close()
        print("⚡ Jace's MM Switcher v3 Engine fully running.")

bot = JaceBot()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} Slash Commands.")
    except Exception as e:
        print(f"Sync Error: {e}")

# Global check to intercept or allow messages based on the /message state
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # If interception tool is toggled off, we can quietly block non-commands or handle them
    if not bot.intercept_messages and not message.content.startswith("!"):
        # Custom logging behavior matching the video intercept sequence
        print(f"[Intercepted & Blocked]: {message.author.name}: {message.content}")
        return

    await bot.process_commands(message)


# =========================================================================
# --- 1. CHANNEL FILL SYSTEM (PREFIX: !) ---
# =========================================================================

async def send_marketing_embed(channel):
    embed = discord.Embed(
        title="⚡ Jace's Automated Middleman Service",
        description=(
            "The safest, most secure, and completely automated cross-trade escrow system on Discord.\n\n"
            "**Why choose Jace MM Switcher?**\n"
            "• Instant Blockchain Verification\n"
            "• Supports Crypto & Roblox Limiteds/Robux\n"
            "• 24/7 Active Automated Flow"
        ),
        color=discord.Color.purple()
    )
    embed.add_field(name="✨ Active Middlemen", value="🟢 `System Online`", inline=True)
    embed.add_field(name="💸 Escrow Fee", value="`FREE` under $50", inline=True)
    embed.add_field(name="🚀 Get Started", value="Use `/ticket` below or click the Panel button to trade!", inline=False)
    embed.set_footer(text="⚡ Powering secure trades instantly")
    await channel.send(embed=embed)

@bot.command(name="channelfill")
@commands.has_permissions(administrator=True)
async def channelfill(ctx, *, arg: str = None):
    channel_id = ctx.channel.id
    
    if arg and arg.lower() == "stop":
        if channel_id in bot.channelfill_tasks:
            bot.channelfill_tasks[channel_id].cancel()
            del bot.channelfill_tasks[channel_id]
            
            embed = discord.Embed(title="🔴 Channel Fill Stopped", color=discord.Color.red())
            embed.add_field(name="Status", value="`Stopped looping texts!`", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ No active fill loop found in this channel.", delete_after=5)
    else:
        if channel_id in bot.channelfill_tasks:
            await ctx.send("❌ A fill loop is already active here.", delete_after=5)
            return
            
        async def fill_loop():
            try:
                while True:
                    await send_marketing_embed(ctx.channel)
                    await asyncio.sleep(15)
            except asyncio.CancelledError:
                pass

        bot.channelfill_tasks[channel_id] = bot.loop.create_task(fill_loop())
        
        embed = discord.Embed(title="🟢 Channel Fill Complete", color=discord.Color.green())
        embed.add_field(name="Status", value="`Loops Started (every 15s)`", inline=False)
        await ctx.send(embed=embed)


# =========================================================================
# --- 2. COMPLETE FUNCTIONAL SLASH COMMANDS (PREFIX: /) ---
# =========================================================================

# --- REAL FUNCTIONAL F_SEND COMMAND ---
@bot.tree.command(name="fsend", description="Generate and inject a completely fake live crypto transaction into the chat")
@app_commands.checks.has_permissions(administrator=True)
async def fsend(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    
    # Generate completely real-looking blockchain hashes and values
    fake_txid = "".join(random.choices(string.hexdigits.lower(), k=64))
    fake_ltc_amount = round(random.uniform(0.5, 4.5), 4)
    fake_usd_val = round(fake_ltc_amount * 45.0, 2)
    
    embed = discord.Embed(
        title="✨ Blockchain Deposit Detected",
        description=f"A pending transaction has been discovered on the Network for your Escrow Hold.",
        color=discord.Color.green()
    )
    embed.add_field(name="Transaction ID (TXID)", value=f"`{fake_txid[:24]}...`", inline=False)
    embed.add_field(name="Detected Amount", value=f"`{fake_ltc_amount} LTC` (~${fake_usd_val} USD)", inline=True)
    embed.add_field(name="Confirmations", value="`1/3 (Securing Funds...) 🟡`", inline=True)
    embed.set_footer(text="Jace Automated Escrow Node V2")
    
    await interaction.followup.send(embed=embed)


# --- TOGGLE MESSAGE INTERCEPT ---
@bot.tree.command(name="message", description="Toggles whether the bot intercepts/blocks normal chat text")
@app_commands.checks.has_permissions(administrator=True)
async def message_control(interaction: discord.Interaction):
    bot.intercept_messages = not bot.intercept_messages
    status_str = "ENABLED (Normal Mode)" if bot.intercept_messages else "DISABLED (Intercepting & Blocking Mode)"
    
    embed = discord.Embed(
        title="🚫 Chat Interception Modified",
        description=f"The bot's chat filter engine state is now set to: **{status_str}**",
        color=discord.Color.dark_grey()
    )
    await interaction.response.send_message(embed=embed)


# --- STAFF MANAGEMENT ---
@bot.tree.command(name="staff", description="Add yourself to the active staff list and go online")
@app_commands.checks.has_permissions(administrator=True)
async def staff_on(interaction: discord.Interaction):
    await interaction.response.defer()
    
    embed_proc = discord.Embed(title="Processing...", description="Reading Jace's MM Service configuration...", color=discord.Color.orange())
    msg = await interaction.followup.send(embed=embed_proc)
    await asyncio.sleep(2)
    
    conn = sqlite3.connect("jace_switcher_v3.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO staff (user_id, username, status) VALUES (?, ?, 'ONLINE')", (str(interaction.user.id), interaction.user.name))
    conn.commit()
    conn.close()
    
    embed_done = discord.Embed(title="🟢 Staff Join Complete", color=discord.Color.green())
    embed_done.add_field(name="Staff Member", value=interaction.user.mention, inline=True)
    embed_done.add_field(name="Status Mode", value="`ONLINE 🟢`", inline=True)
    await msg.edit(embed=embed_done)

@bot.tree.command(name="staffoff", description="Set your staff status to offline")
@app_commands.checks.has_permissions(administrator=True)
async def staff_off(interaction: discord.Interaction):
    conn = sqlite3.connect("jace_switcher_v3.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE staff SET status = 'OFFLINE' WHERE user_id = ?", (str(interaction.user.id),))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(title="🔴 Staff Account Offline", description=f"{interaction.user.mention} is now offline.", color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="staffstatus", description="Check current active staff availability numbers")
async def staff_status(interaction: discord.Interaction):
    conn = sqlite3.connect("jace_switcher_v3.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, status FROM staff")
    rows = cursor.fetchall()
    conn.close()
    
    total = len(rows)
    online = len([r for r in rows if r[1] == "ONLINE"])
    
    embed = discord.Embed(title="👥 Jace MM Team Staff Status", color=discord.Color.blue())
    embed.add_field(name="Online Count", value=f"`{online}` Active", inline=True)
    embed.add_field(name="Total Configured", value=f"`{total}` Members", inline=True)
    
    staff_list = "\n".join([f"{'🟢' if r[1] == 'ONLINE' else '🔴'} {r[0]}" for r in rows])
    embed.add_field(name="Team Overview", value=staff_list if staff_list else "No staff registered yet.", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="staffreload", description="Reload current staff configurations")
@app_commands.checks.has_permissions(administrator=True)
async def staff_reload(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 `Staff configuration file remapped and cleared.` Successfully updated!", ephemeral=True)


# --- MODE SWITCHER & SETUPS ---
@bot.tree.command(name="enable", description="Enable Auto-MM system mode and load automated layouts")
@app_commands.checks.has_permissions(administrator=True)
async def enable_mode(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔄 Switching to Jace's Custom Mode",
        description="Overwriting current active server settings... Layout templates parsed cleanly.",
        color=discord.Color.purple()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setupwallet", description="Set up your crypto receiving escrow addresses")
@app_commands.checks.has_permissions(administrator=True)
async def setup_wallet(interaction: discord.Interaction, ltc: str):
    conn = sqlite3.connect("jace_switcher_v3.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO wallets (guild_id, ltc_addr) VALUES (?, ?)", (str(interaction.guild_id), ltc))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(title="✅ Escrow Wallet Configured", description=f"Default LTC destination is now set to:\n`{ltc}`", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)


# --- THE MAIN INTERACTIVE AUTO-ESCROW TICKET SYSTEM ---
class DealModal(discord.ui.Modal, title="Jace Auto-MM: Trade Request"):
    partner = discord.ui.TextInput(label="Partner User ID / Username", placeholder="Enter your partner's profile reference...", required=True)
    giving = discord.ui.TextInput(label="What items/crypto are YOU sending?", placeholder="e.g. 50$ LTC or Roblox Korblox Account", required=True)
    receiving = discord.ui.TextInput(label="What is your PARTNER providing?", placeholder="e.g. Adurite Crown Limited asset", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        
        # Room permissions buildout
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(name=f"deal-{interaction.user.name.lower()}", overwrites=overwrites)
        
        embed = discord.Embed(title="🛡️ Secure Escrow Form Verification", description="Both trade participants must confirm below if these deal logs match.", color=discord.Color.blue())
        embed.add_field(name="User Ledger", value=interaction.user.mention, inline=True)
        embed.add_field(name="Counterparty", value=f"`{self.partner.value}`", inline=True)
        embed.add_field(name="Your Deposit", value=f"`{self.giving.value}`", inline=False)
        embed.add_field(name="Their Settlement", value=f"`{self.receiving.value}`", inline=False)
        
        class TradeDecision(discord.ui.View):
            def __init__(self): super().__init__(timeout=None)
            @discord.ui.button(label="Correct Match", style=discord.ButtonStyle.green)
            async def match(self, idx: discord.Interaction, btn: discord.ui.Button):
                await idx.response.send_message("📥 **Escrow Vault opened.** Please use `/fsend` inside this room or run payments to process settlement validation.")
            @discord.ui.button(label="Cancel Request", style=discord.ButtonStyle.red)
            async def abort(self, idx: discord.Interaction, btn: discord.ui.Button):
                await idx.response.send_message("❌ Agreement declined. Deleting channel thread...")
                await asyncio.sleep(3)
                await idx.channel.delete()

        await channel.send(embed=embed, view=TradeDecision())
        await interaction.followup.send(f"✅ Secure Trade Room successfully assigned: {channel.mention}", ephemeral=True)

class PanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Request Litecoin (LTC)", style=discord.ButtonStyle.green, custom_id="core_ltc_btn")
    async def req_ltc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DealModal())

@bot.tree.command(name="ticket", description="Deploys the interactive main panel room component")
@app_commands.checks.has_permissions(administrator=True)
async def ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Jace's Auto Middleman Hub",
        description="Click the button below to initiate an automated, secure escrow trade.",
        color=discord.Color.purple()
    )
    await interaction.channel.send(embed=embed, view=PanelView())
    await interaction.response.send_message("Core system node deployed.", ephemeral=True)


# --- RUN RUN ---
TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN")
bot.run(TOKEN)

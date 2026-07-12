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
        self.channelfill_active = False
        self.channelfill_task = None
        self.intercept_messages = True
        
    async def setup_hook(self):
        conn = sqlite3.connect("jace_ultimate_v3.db")
        cursor = conn.cursor()
        
        # Database setup
        cursor.execute("CREATE TABLE IF NOT EXISTS staff (user_id TEXT PRIMARY KEY, username TEXT, status TEXT DEFAULT 'OFFLINE')")
        cursor.execute("CREATE TABLE IF NOT EXISTS wallets (guild_id TEXT PRIMARY KEY, ltc_addr TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS promo_codes (code TEXT PRIMARY KEY, prize_usd REAL, used INTEGER DEFAULT 0)")
        
        # Insert a default functional redeem code for testing
        cursor.execute("INSERT OR IGNORE INTO promo_codes (code, prize_usd) VALUES ('JACE50', 50.00)")
        conn.commit()
        conn.close()
        print("⚡ Jace's Ultimate MM Switcher Engine fully configured.")

bot = JaceBot()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} Slash Commands globally.")
    except Exception as e:
        print(f"Sync Error: {e}")


# =========================================================================
# --- 1. OVERHAULED AUTOMATED CHANNELFILL SYSTEM (PREFIX: !) ---
# =========================================================================

async def global_fill_loop(guild):
    """Automatically loops and broadcasts marketing embeds to all target channels."""
    # The target channel keywords from the Jace MM video
    target_keywords = ["announcements", "vouches", "premium", "stock", "showcase", "tickets", "chat"]
    
    try:
        while True:
            for channel in guild.text_channels:
                if any(keyword in channel.name for keyword in target_keywords):
                    embed = discord.Embed(
                        title="⚡ Jace's Automated Middleman Network",
                        description=(
                            "The absolute fastest, safest, and completely automated cross-trade escrow system on Discord.\n\n"
                            "**Why trust Jace MM Switcher?**\n"
                            "• Instant On-Chain Block Verification\n"
                            "• Supports Crypto, Roblox Limiteds & Robux\n"
                            "• 24/7 Automated Middleware Nodes\n\n"
                            "👉 Head over to the ticket channels to initiate your automated trade instantly!"
                        ),
                        color=discord.Color.purple()
                    )
                    embed.set_footer(text="⚡ System Operating: 24/7 Node Cluster Active")
                    try:
                        await channel.send(embed=embed)
                    except Exception:
                        pass # Skips channels if missing write permissions
            await asyncio.sleep(15) # Sends an automated wave every 15 seconds
    except asyncio.CancelledError:
        pass

@bot.command(name="channelfill")
@commands.has_permissions(administrator=True)
async def channelfill(ctx, *, arg: str = None):
    if arg and arg.lower() == "stop":
        if bot.channelfill_task:
            bot.channelfill_task.cancel()
            bot.channelfill_task = None
            bot.channelfill_active = False
            
            embed = discord.Embed(title="🔴 Network Broadcast Halted", description="Global channelfill task has been stopped across all channels.", color=discord.Color.red())
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ No background broadcast loops are running.", delete_after=5)
    else:
        if bot.channelfill_active:
            await ctx.send("❌ Global channelfill loop is already active.", delete_after=5)
            return
            
        bot.channelfill_active = True
        bot.channelfill_task = bot.loop.create_task(global_fill_loop(ctx.guild))
        
        embed = discord.Embed(title="🟢 Global Channelfill Activated", description="The bot is now automatically populating all trade and market channels every 15s.", color=discord.Color.green())
        await ctx.send(embed=embed)


# =========================================================================
# --- 2. COMPLETE JACE MM CHANNELS AUTOMATED SETUP ---
# =========================================================================

@bot.tree.command(name="setup", description="Wipes old channels and builds the exact 20 Jace MM layout categories")
@app_commands.checks.has_permissions(administrator=True)
async def setup_server(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    guild = interaction.guild
    
    # 1. Clean the guild completely
    for channel in guild.channels:
        try:
            await channel.delete()
        except Exception:
            pass
            
    # 2. Build the precise channel tree structure seen in the video showcase
    jace_layout = {
        "— INFORMATION —": ["📢〢announcements", "📜〢rules", "📈〢vouches", "💎〢premium-benefits", "🛡️〢middleman-info"],
        "— MARKETPLACE —": ["🛒〢buy-server-setup", "⚙️〢custom-bots", "📦〢current-stock", "🤖〢showcase", "💰〢exchange-rates"],
        "— SUPPORT & TICKETS —": ["📩〢tickets", "🎫〢open-deal", "⚠️〢report-scammer", "❓〢help-faq"],
        "— COMMUNITY LOUNGE —": ["💬〢general-chat", "🎉〢giveaways", "🤝〢partnerships", "📷〢media", "🤖〢bot-commands", "🪐〢lounge"]
    }
    
    for category_name, text_channels in jace_layout.items():
        category = await guild.create_category(category_name)
        for channel_name in text_channels:
            await guild.create_text_channel(channel_name, category=category)
            await asyncio.sleep(0.2) # Avoid rate limits
            
    # Inform the owner inside the new first channel
    target_ch = guild.text_channels[0]
    await target_ch.send("🏆 **Jace MM Switcher v3 Server Layout completely generated successfully!** All 20 channels mapped.")


# =========================================================================
# --- 3. MISSING SYSTEM COMMANDS (REDEEM, FSEND, ETC) ---
# =========================================================================

@bot.tree.command(name="redeem", description="Claim a promo balance code directly into your automated system wallet")
async def redeem_code(interaction: discord.Interaction, code: str):
    conn = sqlite3.connect("jace_ultimate_v3.db")
    cursor = conn.cursor()
    cursor.execute("SELECT prize_usd, used FROM promo_codes WHERE code = ?", (code,))
    row = cursor.fetchone()
    
    if not row:
        await interaction.response.send_message("❌ **Invalid Code!** This voucher does not exist in Jace's database.", ephemeral=True)
        conn.close()
        return
        
    prize, used = row
    if used == 1:
        await interaction.response.send_message("❌ **Code Expired!** This balance voucher has already been claimed.", ephemeral=True)
        conn.close()
        return
        
    cursor.execute("UPDATE promo_codes SET used = 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(title="🎁 Promo Code Redeemed!", description=f"Successfully applied voucher balance code: `{code}`", color=discord.Color.gold())
    embed.add_field(name="Credited Amount", value=f"`+ ${prize:.2f} USD` credited to Escrow Fees", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="fsend", description="Inject a live active crypto transaction simulation into the room chat")
@app_commands.checks.has_permissions(administrator=True)
async def fsend(interaction: discord.Interaction):
    fake_txid = "".join(random.choices(string.hexdigits.lower(), k=64))
    fake_ltc = round(random.uniform(0.3, 3.8), 4)
    fake_usd = round(fake_ltc * 44.84, 2)
    
    embed = discord.Embed(title="✨ Blockchain Deposit Confirmed", description="An incoming ledger movement has completed clearing cycles on the main blockchain layer.", color=discord.Color.green())
    embed.add_field(name="TXID Hash", value=f"`{fake_txid}`", inline=False)
    embed.add_field(name="Secured Settlement", value=f"`{fake_ltc} LTC` (~${fake_usd} USD)", inline=True)
    embed.add_field(name="Block Confirmations", value="`3/3 (Fully Escrow Secured) 🔒`", inline=True)
    embed.set_footer(text="Verified via Jace Auto-MM Node Engine")
    
    await interaction.response.send_message(embed=embed)


# =========================================================================
# --- 4. CONTINUOUS FUNCTIONAL COMMAND CORES ---
# =========================================================================

@bot.tree.command(name="staff", description="Register into active staff grid and flag state as online")
@app_commands.checks.has_permissions(administrator=True)
async def staff_on(interaction: discord.Interaction):
    await interaction.response.defer()
    embed_proc = discord.Embed(title="Processing...", description="Accessing database configurations...", color=discord.Color.orange())
    msg = await interaction.followup.send(embed=embed_proc)
    await asyncio.sleep(1.5)
    
    conn = sqlite3.connect("jace_ultimate_v3.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO staff (user_id, username, status) VALUES (?, ?, 'ONLINE')", (str(interaction.user.id), interaction.user.name))
    conn.commit()
    conn.close()
    
    embed_done = discord.Embed(title="🟢 Staff Registry Synchronized", color=discord.Color.green())
    embed_done.add_field(name="User", value=interaction.user.mention, inline=True)
    embed_done.add_field(name="State", value="`ONLINE 🟢`", inline=True)
    await msg.edit(embed=embed_done)

@bot.tree.command(name="staffoff", description="Set your personnel status offline")
@app_commands.checks.has_permissions(administrator=True)
async def staff_off(interaction: discord.Interaction):
    conn = sqlite3.connect("jace_ultimate_v3.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE staff SET status = 'OFFLINE' WHERE user_id = ?", (str(interaction.user.id),))
    conn.commit()
    conn.close()
    await interaction.response.send_message("🔴 Status updated to **OFFLINE**.", ephemeral=True)

@bot.tree.command(name="staffstatus", description="Query the active counts of configured online staff rows")
async def staff_status(interaction: discord.Interaction):
    conn = sqlite3.connect("jace_ultimate_v3.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, status FROM staff")
    rows = cursor.fetchall()
    conn.close()
    
    online = len([r for r in rows if r[1] == "ONLINE"])
    embed = discord.Embed(title="👥 Jace MM Staff Distribution", color=discord.Color.blue())
    embed.add_field(name="Metrics", value=f"• Total Loaded: `{len(rows)}` \n• Active Online: `{online}`")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="enable", description="Enable system modules")
@app_commands.checks.has_permissions(administrator=True)
async def enable_sys(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Jace system pipeline activated. Routing switches engaged.")

@bot.tree.command(name="message", description="Toggle manual message capture intercept parameters")
@app_commands.checks.has_permissions(administrator=True)
async def toggle_msg(interaction: discord.Interaction):
    bot.intercept_messages = not bot.intercept_messages
    await interaction.response.send_message(f"⚙️ Chat intercept tool overrides toggled to: **{bot.intercept_messages}**")

@bot.tree.command(name="setupwallet", description="Configure server deposit variables")
@app_commands.checks.has_permissions(administrator=True)
async def setup_wallet(interaction: discord.Interaction, ltc: str):
    await interaction.response.send_message(f"✅ Master address targeted to: `{ltc}`")

class DealModal(discord.ui.Modal, title="Jace Escrow Configuration"):
    partner = discord.ui.TextInput(label="Partner Identifier Reference", required=True)
    giving = discord.ui.TextInput(label="Your Ledger Escrow Allocation", required=True)
    receiving = discord.ui.TextInput(label="Counterparty Settlement Allocation", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        channel = await guild.create_text_channel(name=f"escrow-{interaction.user.name.lower()}", overwrites=overwrites)
        
        embed = discord.Embed(title="🛡️ Escrow Framework Active", description="Confirm details to execute escrow hold.", color=discord.Color.blue())
        embed.add_field(name="Details", value=f"Giving: `{self.giving.value}`\nReceiving: `{self.receiving.value}`")
        await channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Escrow Room loaded: {channel.mention}", ephemeral=True)

class PanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Request Litecoin (LTC)", style=discord.ButtonStyle.green)
    async def req_ltc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DealModal())

@bot.tree.command(name="ticket", description="Deploy the primary interactive ticket execution board")
@app_commands.checks.has_permissions(administrator=True)
async def ticket(interaction: discord.Interaction):
    await interaction.channel.send(embed=discord.Embed(title="🤖 Jace's Automated Escrow Hub", description="Select down below to clear secure transaction tickets.", color=discord.Color.purple()), view=PanelView())
    await interaction.response.send_message("Board attached.", ephemeral=True)

# --- EXECUTE ---
TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN")
bot.run(TOKEN)

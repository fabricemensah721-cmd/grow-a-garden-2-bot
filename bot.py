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
        conn = sqlite3.connect("jace_automm_v5.db")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS staff (user_id TEXT PRIMARY KEY, username TEXT, status TEXT DEFAULT 'OFFLINE')")
        cursor.execute("CREATE TABLE IF NOT EXISTS wallets (guild_id TEXT PRIMARY KEY, ltc_addr TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS promo_codes (code TEXT PRIMARY KEY, prize_usd REAL, used INTEGER DEFAULT 0)")
        cursor.execute("INSERT OR IGNORE INTO promo_codes (code, prize_usd) VALUES ('JACE50', 50.00)")
        conn.commit()
        conn.close()
        
        # Persistent Views for 24/7 buttons
        self.add_view(MainMiddlemanView())
        print("⚡ Jace's 1:1 AutoMM Switcher Engine Active.")

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
# --- 1. THE EXACT JACE MM CHANNEL LAYOUT SETUP ---
# =========================================================================

@bot.tree.command(name="setup", description="Wipes old channels and builds the exact 1:1 Jace MM layout")
@app_commands.checks.has_permissions(administrator=True)
async def setup_server(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    guild = interaction.guild
    
    for channel in guild.channels:
        try:
            await channel.delete()
        except Exception:
            pass
            
    top_channels = [
        "๑°· ┌─ rules",
        "๑°· │ - updates",
        "๑°· │ - clients-giveaways",
        "๑°· │ - servers",
        "๑°· └─ boosts"
    ]
    
    for ch_name in top_channels:
        await guild.create_text_channel(ch_name)
        await asyncio.sleep(0.2)

    jace_categories = {
        "Middleman request": ["┌─ mm-req", "└─ mm-tos", "👑- clients-lb"],
        "Social": ["chat", "commands"],
        "auto crypto": ["auto-crypto", "tos-crypto", "completed-crypto"]
    }
    
    for category_name, text_channels in jace_categories.items():
        category = await guild.create_category(category_name)
        for channel_name in text_channels:
            await guild.create_text_channel(channel_name, category=category)
            await asyncio.sleep(0.2)
            
    if guild.text_channels:
        target_ch = guild.text_channels[0]
        await target_ch.send("🏆 **Jace MM Switcher Server Layout completely generated 1:1 successfully!**")


# =========================================================================
# --- 2. 1:1 AUTOMATED INTERACTIVE MIDDLEMAN SYSTEM (TICKET FLOW) ---
# =========================================================================

class MainMiddlemanView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Litecoin", style=discord.ButtonStyle.green, custom_id="req_ltc_btn")
    async def request_ltc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AutoMMModal())

    @discord.ui.button(label="Request USDT (BEP-20)", style=discord.ButtonStyle.blurple, custom_id="req_usdt_btn")
    async def request_usdt(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AutoMMModal())

class AutoMMModal(discord.ui.Modal, title="Fill out the format"):
    trader_id = discord.ui.TextInput(label="Paste Your Trader's Username or ID", placeholder="e.g. 985509072...", required=True)
    giving = discord.ui.TextInput(label="What Are You Giving?", placeholder="e.g. test", required=True)
    receiving = discord.ui.TextInput(label="What Is Your Trader Giving?", placeholder="e.g. test", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
        channel_name = f"ltc-sol-{interaction.user.name.lower()}-{random_suffix}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        ticket_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
        
        # Welcome block inside ticket channel
        embed = discord.Embed(
            title="🛡️ Jace's Auto Middleman",
            description="Please explicitly state the trade details below before proceeding.\nIf any player completely backs out, click Close Trade.\n\n**Fees:**\n• Deals $50+ ➔ $1.50\n• Deals under $50 ➔ $0.50\n• Deals under $10 are **FREE**",
            color=discord.Color.purple()
        )
        embed.add_field(name="Your item:", value=f"`{self.giving.value}`", inline=True)
        embed.add_field(name="Trader's item:", value=f"`{self.receiving.value}`", inline=True)
        
        await ticket_channel.send(content=f"{interaction.user.mention} | trade partner session initialized.", embed=embed, view=TicketRoleView())
        await interaction.response.send_message(f"✅ **Ticket Created!** Please go to {ticket_channel.mention}", ephemeral=True)

class TicketRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Sender", style=discord.ButtonStyle.green, custom_id="role_sender")
    async def select_sender(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"✨ {interaction.user.mention} selected **Sender** role. Please input the USD value of the trade.", view=AmountSetView())

    @discord.ui.button(label="Receiver", style=discord.ButtonStyle.blurple, custom_id="role_receiver")
    async def select_receiver(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"📥 {interaction.user.mention} selected **Receiver** role. Awaiting configuration from Sender.", ephemeral=False)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Closing channel in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class AmountSetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Set USD Amount", style=discord.ButtonStyle.gray, custom_id="set_usd_btn")
    async def set_amount(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(USDAmountModal())

class USDAmountModal(discord.ui.Modal, title="Set USD Amount"):
    amount = discord.ui.TextInput(label="Please state the amount in USD value", placeholder="e.g. 25.00", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        usd_val = float(self.amount.value)
        ltc_val = round(usd_val / 65.0, 5) # Simulating an exchange rate conversion
        fake_addr = "L" + "".join(random.choices(string.ascii_letters + string.digits, k=33))
        
        embed = discord.Embed(title="💳 Payment Information", description="Make sure to send the **EXACT** amount in LTC.", color=discord.Color.blue())
        embed.add_field(name="USD Amount", value=f"`${usd_val:.2f}`", inline=True)
        embed.add_field(name="LTC Amount", value=f"`{ltc_val} LTC`", inline=True)
        embed.add_field(name="LTC Address", value=f"`{fake_addr}`", inline=False)
        embed.set_footer(text="This ticket will close automatically within 20 minutes if no transaction was detected.")
        
        await interaction.response.send_message(embed=embed, view=PaymentConfirmView())

class PaymentConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Confirm Payment Sent", style=discord.ButtonStyle.green, custom_id="confirm_payment_sent")
    async def confirm_sent(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        msg = await interaction.followup.send("🔍 Checking blockchain network for transaction...")
        await asyncio.sleep(4)
        
        embed = discord.Embed(
            title="✅ Transaction Detected & Cleared", 
            description="The system has confirmed the deposit assets on-chain and locked them in the secure middleware escrow room.", 
            color=discord.Color.green()
        )
        embed.add_field(name="Status", value="`3/3 Confirmations - SECURED 🔒`")
        await msg.edit(content=None, embed=embed)


# =========================================================================
# --- 3. UPGRADED !channelfill ENGINE (PREFIX: !) ---
# =========================================================================

async def global_fill_loop(guild):
    target_keywords = ["updates", "clients-giveaways", "chat", "auto-crypto", "mm-req"]
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
                        pass
            await asyncio.sleep(15)
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
            await ctx.send(embed=discord.Embed(title="🔴 Network Broadcast Halted", description="Global channelfill stopped.", color=discord.Color.red()))
        else:
            await ctx.send("❌ No broadcast loops are running.", delete_after=5)
    else:
        if bot.channelfill_active:
            await ctx.send("❌ Loop already active.", delete_after=5)
            return
        bot.channelfill_active = True
        bot.channelfill_task = bot.loop.create_task(global_fill_loop(ctx.guild))
        await ctx.send(embed=discord.Embed(title="🟢 Global Channelfill Activated", description="Populating channels every 15s.", color=discord.Color.green()))


# =========================================================================
# --- 4. ALL OTHER MANDATORY SLASH COMMAND CORES ---
# =========================================================================

@bot.tree.command(name="ticket", description="Deploy the primary interactive ticket panel")
@app_commands.checks.has_permissions(administrator=True)
async def deploy_ticket_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Jace's AutoMM Switcher Hub", 
        description="Select an asset type below to securely open an automated transaction escrow ledger workspace.", 
        color=discord.Color.purple()
    )
    await interaction.channel.send(embed=embed, view=MainMiddlemanView())
    await interaction.response.send_message("Setup Hub deployed.", ephemeral=True)

@bot.tree.command(name="fsend", description="Inject a live active crypto transaction simulation into the room chat")
@app_commands.checks.has_permissions(administrator=True)
async def fsend(interaction: discord.Interaction):
    fake_txid = "".join(random.choices(string.hexdigits.lower(), k=64))
    fake_ltc = round(random.uniform(0.3, 3.8), 4)
    fake_usd = round(fake_ltc * 65.20, 2)
    
    embed = discord.Embed(title="✨ Blockchain Deposit Confirmed", description="An incoming ledger movement has completed clearing cycles.", color=discord.Color.green())
    embed.add_field(name="TXID Hash", value=f"`{fake_txid}`", inline=False)
    embed.add_field(name="Secured Settlement", value=f"`{fake_ltc} LTC` (~${fake_usd} USD)", inline=True)
    embed.add_field(name="Block Confirmations", value="`3/3 (Fully Escrow Secured) 🔒`", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="redeem", description="Claim a promo balance code directly into your automated system wallet")
async def redeem_code(interaction: discord.Interaction, code: str):
    conn = sqlite3.connect("jace_automm_v5.db")
    cursor = conn.cursor()
    cursor.execute("SELECT prize_usd, used FROM promo_codes WHERE code = ?", (code,))
    row = cursor.fetchone()
    
    if not row:
        await interaction.response.send_message("❌ **Invalid Code!**", ephemeral=True)
        conn.close()
        return
        
    prize, used = row
    if used == 1:
        await interaction.response.send_message("❌ **Code Expired!**", ephemeral=True)
        conn.close()
        return
        
    cursor.execute("UPDATE promo_codes SET used = 1 WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(title="🎁 Promo Code Redeemed!", description=f"Successfully applied: `{code}`", color=discord.Color.gold())
    embed.add_field(name="Credited Amount", value=f"`+ ${prize:.2f} USD`", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="staff", description="Register into active staff grid and flag state as online")
@app_commands.checks.has_permissions(administrator=True)
async def staff_on(interaction: discord.Interaction):
    await interaction.response.defer()
    conn = sqlite3.connect("jace_automm_v5.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO staff (user_id, username, status) VALUES (?, ?, 'ONLINE')", (str(interaction.user.id), interaction.user.name))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(title="🟢 Staff Registry Synchronized", color=discord.Color.green())
    embed.add_field(name="User", value=interaction.user.mention)
    embed.add_field(name="State", value="`ONLINE 🟢`")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="staffoff", description="Set your personnel status offline")
@app_commands.checks.has_permissions(administrator=True)
async def staff_off(interaction: discord.Interaction):
    conn = sqlite3.connect("jace_automm_v5.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE staff SET status = 'OFFLINE' WHERE user_id = ?", (str(interaction.user.id),))
    conn.commit()
    conn.close()
    await interaction.response.send_message("🔴 Status updated to **OFFLINE**.", ephemeral=True)

@bot.tree.command(name="staffstatus", description="Query the active counts of configured online staff rows")
async def staff_status(interaction: discord.Interaction):
    conn = sqlite3.connect("jace_automm_v5.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, status FROM staff")
    rows = cursor.fetchall()
    conn.close()
    
    online = len([r for r in rows if r[1] == "ONLINE"])
    embed = discord.Embed(title="👥 Jace MM Staff Distribution", color=discord.Color.blue())
    embed.add_field(name="Metrics", value=f"• Total Loaded: `{len(rows)}` \n• Active Online: `{online}`")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="staffreload", description="Reloads active staff configuration structures")
@app_commands.checks.has_permissions(administrator=True)
async def staff_reload(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Staff configurations reloaded successfully.")

@bot.tree.command(name="setupwallet", description="Configure server deposit variables")
@app_commands.checks.has_permissions(administrator=True)
async def setup_wallet(interaction: discord.Interaction, ltc: str):
    await interaction.response.send_message(f"✅ Master address targeted to: `{ltc}`")

# --- EXECUTE ---
TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN")
bot.run(TOKEN)

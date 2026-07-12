import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
import asyncio
import random

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class JaceBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.channelfill_tasks = {} # Speichert aktive Werbe-Schleifen
        
    async def setup_hook(self):
        conn = sqlite3.connect("jace_switcher.db")
        cursor = conn.cursor()
        
        # Staff Tabelle
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                status TEXT DEFAULT 'OFFLINE'
            )
        """)
        # Stock Tabelle
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock (
                item_name TEXT PRIMARY KEY,
                status TEXT DEFAULT 'AVAILABLE',
                amount INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
        print("⚡ Jace's MM Switcher v2 Engine loaded successfully.")

bot = JaceBot()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} Slash Commands.")
    except Exception as e:
        print(f"Sync Error: {e}")


# =========================================================================
# --- KATEGORIE 1: CHANNEL FILL SYSTEM (PRÄFIX: !) ---
# =========================================================================

async def fill_loop(ctx, channel_id):
    channel = ctx.bot.get_channel(channel_id)
    if not channel:
        return
    try:
        while True:
            embed = discord.Embed(
                title="⚡ Jace's Auto-MM Service",
                description="Fastest & Safest Middleman Service in the market.\nUse `/ticket` to open a deal instantly!",
                color=discord.Color.purple()
            )
            embed.add_field(name="Supported Crypto", value="`LTC` | `BTC` | `ETH` | `USDT`", inline=True)
            embed.add_field(name="Roblox Trading", value="`Limiteds` | `Robux` | `Accounts`", inline=True)
            embed.set_footer(text="Automated marketing broadcast active.")
            
            await channel.send(embed=embed)
            await asyncio.sleep(30) # Sendet alle 30 Sekunden eine Nachricht (Zeit anpassbar)
    except asyncio.CancelledError:
        print(f"Loop stopped for channel {channel_id}")

@bot.command(name="channelfill")
@commands.has_permissions(administrator=True)
async def channelfill(ctx, action: str = "start"):
    channel_id = ctx.channel.id
    
    if action.lower() == "start":
        if channel_id in bot.channelfill_tasks:
            await ctx.send("❌ Channel fill loop is already running in this channel.", delete_after=5)
            return
            
        bot.channelfill_tasks[channel_id] = bot.loop.create_task(fill_loop(ctx, channel_id))
        
        embed = discord.Embed(title="🟢 Channel Fill Complete", color=discord.Color.green())
        embed.add_field(name="Status", value="`Loops Started (every 30s)`", inline=False)
        embed.set_footer(text="Use '!channelfill stop' to halt all loops.")
        await ctx.send(embed=embed)
        
    elif action.lower() == "stop":
        if channel_id in bot.channelfill_tasks:
            bot.channelfill_tasks[channel_id].cancel()
            del bot.channelfill_tasks[channel_id]
            
            embed = discord.Embed(title="🔴 Channel Fill Stopped", color=discord.Color.red())
            embed.add_field(name="Status", value="`Stopped looping texts!`", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ No active fill loop found in this channel.", delete_after=5)


# =========================================================================
# --- KATEGORIE 2: STAFF MANAGEMENT SYSTEM (SLASH COMMANDS) ---
# =========================================================================

@bot.tree.command(name="staff", description="Add yourself or a user to the active staff list and go online")
@app_commands.checks.has_permissions(administrator=True)
async def staff_on(interaction: discord.Interaction):
    await interaction.response.defer()
    
    # Animierter Verarbeitungs-Effekt wie im Video
    embed_processing = discord.Embed(title="Processing...", description="Reading Jace's MM Service configuration...", color=discord.Color.orange())
    msg = await interaction.followup.send(embed=embed_processing)
    await asyncio.sleep(2) # Kurze Pause für den Effekt
    
    conn = sqlite3.connect("jace_switcher.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO staff (user_id, username, status) VALUES (?, ?, 'ONLINE')", (str(interaction.user.id), interaction.user.name))
    conn.commit()
    conn.close()
    
    embed_done = discord.Embed(
        title="🟢 Staff Join Complete",
        description="Successfully synchronized with the Jace MM Staff Network.",
        color=discord.Color.green()
    )
    embed_done.add_field(name="Staff Member", value=interaction.user.mention, inline=True)
    embed_done.add_field(name="Current Mode", value="`ONLINE 🟢`", inline=True)
    await msg.edit(embed=embed_done)

@bot.tree.command(name="staffoff", description="Set your staff status to offline")
@app_commands.checks.has_permissions(administrator=True)
async def staff_off(interaction: discord.Interaction):
    conn = sqlite3.connect("jace_switcher.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE staff SET status = 'OFFLINE' WHERE user_id = ?", (str(interaction.user.id),))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(title="🔴 Staff Account Offline", description=f"{interaction.user.mention} is now offline.", color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="staffstatus", description="Check current active online/offline staff numbers")
async def staff_status(interaction: discord.Interaction):
    conn = sqlite3.connect("jace_switcher.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, status FROM staff")
    rows = cursor.fetchall()
    conn.close()
    
    total_staff = len(rows)
    online_staff = len([r for r in rows if r[1] == "ONLINE"])
    
    embed = discord.Embed(title="👥 Jace MM Team Staff Status", color=discord.Color.blue())
    embed.add_field(name="Online Count", value=f"`{online_staff}` Staff active", inline=True)
    embed.add_field(name="Total Configured", value=f"`{total_staff}` Members", inline=True)
    
    staff_list = ""
    for r in rows:
        emoji = "🟢" if r[1] == "ONLINE" else "🔴"
        staff_list += f"{emoji} {r[0]} ({r[1]})\n"
        
    embed.add_field(name="Team Overview", value=staff_list if staff_list else "No staff registered yet.", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="staffreload", description="Reload fake or real staff configurations")
@app_commands.checks.has_permissions(administrator=True)
async def staff_reload(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 `Reloading fake/real staff configs...` Config applied successfully!", ephemeral=True)


# =========================================================================
# --- KATEGORIE 3: AUTO CRYPTO MIDDLEMAN HUB & WORKFLOW ---
# =========================================================================

# Modal (Formular) für den Deal-Eintrag
class DealModal(discord.ui.Modal, title="Jace Auto-MM: Deal Setup"):
    partner_id = discord.ui.TextInput(label="What is your Trader Partner ID/Username?", placeholder="e.g. 985522...", required=True)
    giving = discord.ui.TextInput(label="What are YOU giving?", placeholder="e.g. 25$ LTC or Roblox Korblox Account", required=True)
    receiving = discord.ui.TextInput(label="What is your PARTNER giving?", placeholder="e.g. Ice Valkyrie Roblox Limited", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        member = interaction.user
        
        # Erstelle privaten Deal-Kanal
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True)
        }
        
        channel = await guild.create_text_channel(
            name=f"deal-{member.name.lower()}",
            category=discord.utils.get(guild.categories, name="— SUPPORT & COMMUNITY —"),
            overwrites=overwrites
        )
        
        # Deal Bestätigungs-Embed im neuen Ticket
        embed = discord.Embed(title="🛡️ Jace Auto-MM Deal Verification", description="Please verify if the following information is correct.", color=discord.Color.blue())
        embed.add_field(name="Sender (You)", value=member.mention, inline=True)
        embed.add_field(name="Partner", value=f"<@{self.partner_id.value}>" if self.partner_id.value.isdigit() else self.partner_id.value, inline=True)
        embed.add_field(name="Your Offer", value=f"`{self.giving.value}`", inline=False)
        embed.add_field(name="Partner's Offer", value=f"`{self.receiving.value}`", inline=False)
        
        class VerifyView(discord.ui.View):
            def __init__(self): super().__init__(timeout=None)
            
            @discord.ui.button(label="Correct", style=discord.ButtonStyle.green)
            async def correct(self, i: discord.Interaction, b: discord.ui.Button):
                # Schritt 2: Betrag festlegen Formular simulieren
                await i.response.send_modal(AmountModal())
                
            @discord.ui.button(label="Incorrect / Cancel", style=discord.ButtonStyle.red)
            async def incorrect(self, i: discord.Interaction, b: discord.ui.Button):
                await i.response.send_message("❌ Deal cancelled. This channel will close in 5 seconds.")
                await asyncio.sleep(5)
                await i.channel.delete()

        await channel.send(embed=embed, view=VerifyView())
        await interaction.followup.send(f"✅ Deal Ticket created: {channel.mention}", ephemeral=True)

class AmountModal(discord.ui.Modal, title="Set USD Value"):
    amount = discord.ui.TextInput(label="Enter Deal Value in USD", placeholder="e.g. 25.00", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        usd_val = float(self.amount.value)
        ltc_val = usd_val / 75.0 # Simulierter LTC Kurs: 1 LTC = 75$
        
        embed = discord.Embed(title="💳 Jace Auto-MM: Payment Information", description="Send the EXACT crypto amount to the secure escrow wallet.", color=discord.Color.gold())
        embed.add_field(name="USD Amount", value=f"`${usd_val:.2f} USD`", inline=True)
        embed.add_field(name="LTC Value Required", value=f"`{ltc_val:.6f} LTC`", inline=True)
        embed.add_field(name="Escrow LTC Wallet Address", value="`LTC-JACE-SWITCHER-ESCROW-V2-FAKE-ADDRESS-9921`", inline=False)
        embed.set_footer(text="This ticket automatically closes if no transaction is found in 20 minutes.")
        
        class BlockchainSimView(discord.ui.View):
            def __init__(self): super().__init__(timeout=None)
            
            @discord.ui.button(label="Simulate Payment Confirmed (Blockchain)", style=discord.ButtonStyle.blurple)
            async def confirm_pay(self, i: discord.Interaction, b: discord.ui.Button):
                # Zahlungs-Bestätigung wie im Video
                emb_success = discord.Embed(title="✅ Transaction Confirmed", description=f"Blockchain detected payment of `{ltc_val:.6f} LTC`!", color=discord.Color.green())
                emb_success.add_field(name="Status", value="**Escrow Held Safely 🔒**\nStaff/Bot is checking the goods now. You may now proceed with the trade.", inline=False)
                
                class ReleaseView(discord.ui.View):
                    def __init__(self): super().__init__(timeout=None)
                    @discord.ui.button(label="Release LTC to Partner", style=discord.ButtonStyle.green)
                    async def release(self, i2: discord.Interaction, b2: discord.ui.Button):
                        await i2.response.send_message("💸 **Escrow Released!** Funds have been forwarded to the partner. Deal complete! Closing ticket in 10s...")
                        await asyncio.sleep(10)
                        await i2.channel.delete()
                        
                await i.response.send_message(embed=emb_success, view=ReleaseView())
                
        await interaction.response.send_message(embed=embed, view=BlockchainSimView())

# Das Haupt-Panel im #tickets Kanal
class TicketHubView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Litecoin (LTC)", style=discord.ButtonStyle.green, custom_id="req_ltc_btn")
    async def req_ltc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DealModal())

@bot.tree.command(name="ticket", description="Sends the premium Auto-MM Middleman panel to the current channel")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction):
    view = TicketHubView()
    embed = discord.Embed(
        title="🤖 Jace's Auto Middleman Hub",
        description="Click the buttons below to initiate a fully automated, lightning-fast Escrow Middleman Deal via Crypto.",
        color=discord.Color.purple()
    )
    embed.add_field(name="Fees", value="• Deals $250+ ➔ **$1.50 Fee**\n• Deals $50-$250 ➔ **$0.50 Fee**\n• Deals under $50 ➔ **FREE**", inline=False)
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("Premium Jace MM v2 Panel deployed successfully!", ephemeral=True)


# =========================================================================
# --- KATEGORIE 4: REPUTATION & SERVER SETUP CORE ---
# =========================================================================

@bot.tree.command(name="setup", description="Wipes and automatically builds the 20 professional marketplace channels")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    for channel in guild.channels:
        try: await channel.delete()
        except: pass
            
    structure = {
        "— INFORMATION —": ["📢〢announcements", "📜〢rules", "📈〢vouches", "💎〢premium-benefits"],
        "— MARKETPLACE —": ["🛒〢buy-server-setup", "⚙️〢custom-bots", "📦〢current-stock", "🤖〢showcase"],
        "— SUPPORT & COMMUNITY —": ["📩〢tickets", "💬〢general-chat", "🎉〢giveaways", "🤝〢partnerships"]
    }
    
    for cat_name, channels in structure.items():
        category = await guild.create_category(cat_name)
        for ch_name in channels:
            await guild.create_text_channel(ch_name, category=category)
            await asyncio.sleep(0.3)
            
    await interaction.followup.send("Server built with precision!", ephemeral=True)

# --- CONFIG START ---
TOKEN = os.getenv("DISCORD_TOKEN", "DEIN_BOT_TOKEN")
bot.run(TOKEN)

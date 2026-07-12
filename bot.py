import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
import asyncio

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class JaceBot(commands.Bot):
    def __init__(self):
        # Das primäre Prefix für Text-Commands ist '!' wie im Video zu sehen (!channelfill)
        super().__init__(command_prefix="!", intents=intents)
        self.channelfill_tasks = {}
        
    async def setup_hook(self):
        conn = sqlite3.connect("jace_switcher_v2.db")
        cursor = conn.cursor()
        
        # Staff-Tabelle
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff (
                user_id TEXT PRIMARY KEY,
                username TEXT,
                status TEXT DEFAULT 'OFFLINE'
            )
        """)
        # Wallet-Tabelle für /setupwallet
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wallets (
                guild_id TEXT PRIMARY KEY,
                ltc_addr TEXT,
                btc_addr TEXT,
                eth_addr TEXT,
                sol_addr TEXT,
                usdt_addr TEXT,
                usdc_addr TEXT
            )
        """)
        conn.commit()
        conn.close()
        print("⚡ Jace's MM Switcher v2 Engine bereit.")

bot = JaceBot()

@bot.event
async def on_ready():
    print(f"Eingeloggt als {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Erfolgreich {len(synced)} Slash-Commands synchronisiert.")
    except Exception as e:
        print(f"Sync Fehler: {e}")


# =========================================================================
# --- 1. ALLE TEXT-COMMANDS (PREFIX: !) ---
# =========================================================================

@bot.command(name="channelfill")
@commands.has_permissions(administrator=True)
async def channelfill(ctx, *, arg: str = None):
    channel_id = ctx.channel.id
    
    # Wenn '!channelfill stop' eingegeben wird
    if arg and arg.lower() == "stop":
        if channel_id in bot.channelfill_tasks:
            bot.channelfill_tasks[channel_id].cancel()
            del bot.channelfill_tasks[channel_id]
            
            embed = discord.Embed(title="🔴 Channel Fill Stopped", color=discord.Color.red())
            embed.add_field(name="Status", value="`Stopped looping texts!`", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Keine aktive Schleife in diesem Kanal gefunden.", delete_after=5)
            
    # Wenn nur '!channelfill' eingegeben wird (Start)
    else:
        if channel_id in bot.channelfill_tasks:
            await ctx.send("❌ Schleife läuft hier bereits.", delete_after=5)
            return
            
        async def fill_loop():
            try:
                while True:
                    embed = discord.Embed(
                        title="⚡ Jace's Auto-MM Service",
                        description="Der schnellste Escrow-Bot auf Discord.\nNutze `/ticket` für einen Trade!",
                        color=discord.Color.purple()
                    )
                    embed.add_field(name="Kanäle vollgefüllt", value="✅ Aktiv", inline=True)
                    await ctx.send(embed=embed)
                    await asyncio.sleep(30)
            except asyncio.CancelledError:
                pass

        bot.channelfill_tasks[channel_id] = bot.loop.create_task(fill_loop())
        
        embed = discord.Embed(title="🟢 Channel Fill Complete", color=discord.Color.green())
        embed.add_field(name="Status", value="`Loops Started (every 30s)`", inline=False)
        embed.set_footer(text="Nutze '!channelfill stop' zum Beenden.")
        await ctx.send(embed=embed)


# =========================================================================
# --- 2. ALLE SLASH-COMMANDS (PREFIX: /) ---
# =========================================================================

# --- STAFF MANAGEMENT ---

@bot.tree.command(name="staff", description="Fügt dich dem System hinzu und setzt dich online")
@app_commands.checks.has_permissions(administrator=True)
async def staff_on(interaction: discord.Interaction):
    await interaction.response.defer()
    
    # Der Lade-Effekt ("Processing...") aus der Datei "1000047604.mp4"
    embed_proc = discord.Embed(title="Processing...", description="Jace's MM Service wird geladen...", color=discord.Color.orange())
    msg = await interaction.followup.send(embed=embed_proc)
    await asyncio.sleep(2)
    
    conn = sqlite3.connect("jace_switcher_v2.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO staff (user_id, username, status) VALUES (?, ?, 'ONLINE')", (str(interaction.user.id), interaction.user.name))
    conn.commit()
    conn.close()
    
    embed_done = discord.Embed(title="🟢 Staff Join Complete", color=discord.Color.green())
    embed_done.add_field(name="Mitarbeiter", value=interaction.user.mention, inline=True)
    embed_done.add_field(name="Status", value="`ONLINE 🟢`", inline=True)
    await msg.edit(embed=embed_done)

@bot.tree.command(name="staffoff", description="Setzt deinen Staff-Status auf Offline")
@app_commands.checks.has_permissions(administrator=True)
async def staff_off(interaction: discord.Interaction):
    conn = sqlite3.connect("jace_switcher_v2.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE staff SET status = 'OFFLINE' WHERE user_id = ?", (str(interaction.user.id),))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(title="🔴 Staff Account Offline", description=f"{interaction.user.mention} ist nun offline.", color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="staffstatus", description="Zeigt die aktuelle Mitarbeiter-Verfügbarkeit")
async def staff_status(interaction: discord.Interaction):
    conn = sqlite3.connect("jace_switcher_v2.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username, status FROM staff")
    rows = cursor.fetchall()
    conn.close()
    
    total = len(rows)
    online = len([r for r in rows if r[1] == "ONLINE"])
    
    embed = discord.Embed(title="👥 Jace MM Team Staff Status", color=discord.Color.blue())
    embed.add_field(name="Online", value=f"`{online}`", inline=True)
    embed.add_field(name="Gesamt", value=f"`{total}`", inline=True)
    
    liste = "\n".join([f"{'🟢' if r[1] == 'ONLINE' else '🔴'} {r[0]}" for r in rows])
    embed.add_field(name="Mitarbeiter-Liste", value=liste if liste else "Keine registriert.", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="staffreload", description="Lädt die Staff-Konfigurationen neu")
@app_commands.checks.has_permissions(administrator=True)
async def staff_reload(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 `Staff-Konfigurationen erfolgreich neu geladen!`", ephemeral=True)


# --- WEITERE SWITCHER-BEFEHLE AUS DEM VIDEO-MENÜ ---

@bot.tree.command(name="setupwallet", description="Richtet die Krypto-Empfangsadressen für den Server ein")
@app_commands.checks.has_permissions(administrator=True)
async def setup_wallet(interaction: discord.Interaction, ltc: str):
    conn = sqlite3.connect("jace_switcher_v2.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO wallets (guild_id, ltc_addr, btc_addr, eth_addr, sol_addr, usdt_addr, usdc_addr) 
        VALUES (?, ?, 'Not Configured', 'Not Configured', 'Not Configured', 'Not Configured', 'Not Configured')
    """, (str(interaction.guild_id), ltc))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(title="✅ LTC Address Saved", description=f"Adresse gesetzt auf: `{ltc}`", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="enable", description="Aktiviert den Auto-MM Modus")
@app_commands.checks.has_permissions(administrator=True)
async def enable_mode(interaction: discord.Interaction):
    embed = discord.Embed(title="🔄 Switching to Jace's Mode", description="Templates geladen. Kanäle werden angepasst...", color=discord.Color.purple())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="fsend", description="Simuliert eine gefälschte Krypto-Transaktion für Tests")
@app_commands.checks.has_permissions(administrator=True)
async def fsend(interaction: discord.Interaction):
    await interaction.response.send_message("⚙️ `Fake-Transaktion initiiert...` Blockchain-Eintrag generiert.", ephemeral=True)

@bot.tree.command(name="message", description="Stoppt oder manipuliert die Nachrichten-Überwachung des Bots")
@app_commands.checks.has_permissions(administrator=True)
async def message_control(interaction: discord.Interaction):
    await interaction.response.send_message("🚫 Jace's Nachrichten-Überwachung modifiziert.", ephemeral=True)


# --- TICKET & WORKFLOW CORE ---

class DealModal(discord.ui.Modal, title="Jace Auto-MM: Deal starten"):
    partner = discord.ui.TextInput(label="Partner ID oder Username", required=True)
    giving = discord.ui.TextInput(label="Was gibst DU?", required=True)
    receiving = discord.ui.TextInput(label="Was gibt dein PARTNER?", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(name=f"mm-{interaction.user.name}", overwrites=overwrites)
        
        embed = discord.Embed(title="🛡️ Deal Verifikation", description="Bitte Angaben überprüfen.", color=discord.Color.blue())
        embed.add_field(name="Von dir", value=f"`{self.giving.value}`")
        embed.add_field(name="Vom Partner", value=f"`{self.receiving.value}`")
        
        await channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Ticket erstellt: {channel.mention}", ephemeral=True)

class PanelView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Request Litecoin (LTC)", style=discord.ButtonStyle.green)
    async def req_ltc(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DealModal())

@bot.tree.command(name="ticket", description="Sendet das interaktive Auto-MM Panel")
@app_commands.checks.has_permissions(administrator=True)
async def ticket(interaction: discord.Interaction):
    embed = discord.Embed(title=" Jace's Auto Middleman", description="Nutze die Buttons unten, um einen sicheren Deal zu starten.", color=discord.Color.purple())
    await interaction.channel.send(embed=embed, view=PanelView())
    await interaction.response.send_message("Panel gesendet!", ephemeral=True)


# --- BOT RUN ---
TOKEN = os.getenv("DISCORD_TOKEN", "DEIN_BOT_TOKEN")
bot.run(TOKEN)

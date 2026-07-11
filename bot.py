import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        # Datenbank initialisieren
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vouches (
                user_id TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
        print("Datenbank erfolgreich geladen.")

bot = MyBot()

@bot.event
async def on_ready():
    print(f"Eingeloggt als {bot.user.name}")
    try:
        # Slash-Commands global mit Discord synchronisieren
        synced = await bot.tree.sync()
        print(f"{len(synced)} Slash-Befehle erfolgreich synchronisiert.")
    except Exception as e:
        print(f"Fehler beim Synchronisieren der Befehle: {e}")


# --- 1. SETUP COMMAND ---
@bot.tree.command(name="setup", description="Erstellt die Standard-Kanäle für den Krypto-Shop")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    
    # Kanäle erstellen
    categories = ["INFO", "MARKET"]
    cat_objects = {}
    
    for cat_name in categories:
        cat = discord.utils.get(guild.categories, name=cat_name)
        if not cat:
            cat = await guild.create_category(cat_name)
        cat_objects[cat_name] = cat

    channels = [
        ("📢〢announcements", "INFO"),
        ("📈〢vouches", "INFO"),
        ("📩〢tickets", "MARKET")
    ]
    
    for ch_name, cat_group in channels:
        existing = discord.utils.get(guild.channels, name=ch_name)
        if not existing:
            await guild.create_text_channel(ch_name, category=cat_objects[cat_group])
            
    await interaction.followup.send("Server-Kanäle wurden erfolgreich eingerichtet!", ephemeral=True)


# --- 2. TICKET COMMAND (FIXED & RENAMED) ---
class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Button läuft nie ab

    @discord.ui.button(label="Ticket öffnen", style=discord.ButtonStyle.green, custom_id="open_ticket_btn")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user
        
        # Berechtigungen für das neue Ticket-Channel festlegen
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        # Ticket-Kanal erstellen
        channel_name = f"ticket-{member.name.lower()}"
        existing_channel = discord.utils.get(guild.channels, name=channel_name)
        
        if existing_channel:
            await interaction.response.send_message(f"Du hast bereits ein offenes Ticket: {existing_channel.mention}", ephemeral=True)
            return
            
        ticket_category = discord.utils.get(guild.categories, name="MARKET")
        channel = await guild.create_text_channel(
            name=channel_name, 
            category=ticket_category, 
            overwrites=overwrites
        )
        
        # Close-Button im Ticket-Kanal bereitstellen
        close_view = TicketCloseView()
        await channel.send(
            f"Willkommen {member.mention}! Beschreibe hier kurz dein Anliegen (z.B. Welches Setup du kaufen möchtest). Ein Admin wird sich gleich melden.",
            view=close_view
        )
        await interaction.response.send_message(f"Dein Ticket wurde erstellt: {channel.mention}", ephemeral=True)

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ticket schließen", style=discord.ButtonStyle.red, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Dieses Ticket wird in 5 Sekunden gelöscht...")
        await interaction.channel.delete()

@bot.tree.command(name="ticket", description="Sendet das Ticket-Panel in den aktuellen Kanal")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction):
    view = TicketButtonView()
    embed = discord.Embed(
        title="Support & Trade Tickets",
        description="Klicke auf den Button unten, um ein privates Ticket mit dem Team zu eröffnen. Hier besprechen wir dein Server-Setup oder deine Trades.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message("Panel gesendet!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=view)


# --- 3. REPUTATION & VOUCH SYSTEM ---
@bot.tree.command(name="vouch", description="Gibt einem verifizierten Verkäufer oder Middleman einen Pluspunkt")
async def vouch(interaction: discord.Interaction, user: discord.User):
    if user.id == interaction.user.id:
        await interaction.response.send_message("Du kannst dich nicht selbst bewerten!", ephemeral=True)
        return
        
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    # Prüfen ob User existiert, ansonsten anlegen
    cursor.execute("SELECT count FROM vouches WHERE user_id = ?", (str(user.id),))
    row = cursor.fetchone()
    
    if row is None:
        cursor.execute("INSERT INTO vouches (user_id, count) VALUES (?, 1)", (str(user.id),))
        new_count = 1
    else:
        new_count = row[0] + 1
        cursor.execute("UPDATE vouches SET count = ? WHERE user_id = ?", (new_count, str(user.id)))
        
    conn.commit()
    conn.close()
    
    embed = discord.Embed(
        title="+1 Vouch registriert!",
        description=f"{interaction.user.mention} hat {user.mention} erfolgreich bewertet!\n\n**Aktuelle Vouches von {user.name}:** `{new_count}`",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rep", description="Zeigt die aktuellen Vouches eines Nutzers an")
async def rep(interaction: discord.Interaction, user: discord.User):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT count FROM vouches WHERE user_id = ?", (str(user.id),))
    row = cursor.fetchone()
    conn.close()
    
    count = row[0] if row else 0
    
    await interaction.response.send_message(f"Der Nutzer {user.mention} hat aktuell **{count} verifizierte Vouches** auf diesem Server.", ephemeral=False)


# --- FEHLERBEHANDLUNG ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("Dazu hast du keine Rechte! (Nur für Admins)", ephemeral=True)
    else:
        print(f"Ein Fehler ist aufgetreten: {error}")


# --- START BOT ---
# Ersetze 'DEIN_BOT_TOKEN' mit deinem echten Token von Discord-Developer-Portal
TOKEN = os.getenv("DISCORD_TOKEN", "DEIN_BOT_TOKEN")
if TOKEN == "DEIN_BOT_TOKEN":
    print("[WARNUNG] Bitte trage dein echtes Bot-Token in den Code ein!")
bot.run(TOKEN)

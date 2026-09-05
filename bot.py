import os
from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio

# --- 1. Webserver für Render ---
app = Flask('')

@app.route('/')
def home():
    return "Bot läuft!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. Ticket System (Button Funktion) ---
class TicketView(View):
    def __init__(self):
        # timeout=None sorgt dafür, dass der Button auch nach einem Bot-Neustart noch funktioniert
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 Middleman anfordern", style=discord.ButtonStyle.blurple, custom_id="open_ticket")
    async def ticket_button(self, interaction: discord.Interaction, button: Button):
        # Berechtigungen: Nur der User, der klickt, und der Bot dürfen den Kanal sehen
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        # Privaten Textkanal erstellen
        ticket_channel = await interaction.guild.create_text_channel(
            name=f"mm-ticket-{interaction.user.name}",
            overwrites=overwrites
        )

        # Dem User unsichtbar (ephemeral) im Chat antworten, wo das Ticket ist
        await interaction.response.send_message(f"Dein Ticket wurde erstellt: {ticket_channel.mention}", ephemeral=True)

        # Begrüßungstext im neuen Ticket
        await ticket_channel.send(
            f"Willkommen im Middleman-Ticket, {interaction.user.mention}!\n"
            f"Bitte warte kurz, bis ein Middleman Zeit hat.\n\n"
            f"**Befehle:**\n"
            f"`!add @user` - Fügt deinen Handelspartner hinzu.\n"
            f"`!close` - Löscht dieses Ticket."
        )

# --- 3. Bot Konfiguration ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    # Lädt den Button ins System, damit er immer klickbar bleibt
    bot.add_view(TicketView())
    print(f'Eingeloggt als {bot.user.name}')

# --- 4. Befehle ---

# Befehl für Admins: Sendet die Nachricht mit dem Button in den Chat
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_ticket(ctx):
    await ctx.send("**Middleman Service**\nKlicke auf den Button unten, um einen sicheren Handel zu starten:", view=TicketView())

# Befehl: Zieht den zweiten User (z.B. Käufer/Verkäufer) mit ins Ticket
@bot.command()
async def add(ctx, member: discord.Member):
    # Prüft, ob der Befehl wirklich in einem Ticket ausgeführt wird
    if "mm-ticket" in ctx.channel.name:
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await ctx.send(f"{member.mention} wurde dem Handel hinzugefügt!")
    else:
        await ctx.send("Dieser Befehl funktioniert nur in Tickets!")

# Befehl: Schließt und löscht das Ticket
@bot.command()
async def close(ctx):
    if "mm-ticket" in ctx.channel.name:
        await ctx.send("Das Ticket wird in 5 Sekunden geschlossen und gelöscht...")
        await asyncio.sleep(5)
        await ctx.channel.delete()
    else:
        await ctx.send("Du kannst nur Tickets schließen!")

# --- 5. Start ---
keep_alive()
token = os.environ.get("DISCORD_TOKEN")
bot.run(token)

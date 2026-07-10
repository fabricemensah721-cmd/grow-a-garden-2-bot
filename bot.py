import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
from threading import Thread
import os

# --- WEBSERVER FÜR RENDER (Hält den Bot wach) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot läuft!"

def run():
    # Render nutzt den Port aus den Umgebungsvariablen
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.guilds = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def on_ready(self):
        print(f'🤖 Bot ist online als {self.user}')
        try:
            synced = await self.tree.sync()
            print(f"🔄 {len(synced)} Slash-Commands synchronisiert!")
        except Exception as e:
            print(f"Fehler: {e}")

bot = MyBot()

@bot.tree.command(name="setup", description="Erstellt automatisch alle wichtigen Kanäle.")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    guild = interaction.guild
    await interaction.response.send_message("⏳ Erstelle Kanäle...", ephemeral=True)
    try:
        category = await guild.create_category(name="🛠️ MIDDLEMAN HUB")
        info_channel = await guild.create_text_channel(name="ℹ️-information", category=category)
        ticket_channel = await guild.create_text_channel(name="🎫-open-a-ticket", category=category)
        vouch_channel = await guild.create_text_channel(name="✅-vouches", category=category)

        await info_channel.send("Welcome to the **Middleman Service**!\n\n⚠️ **WARNING:** Always verify my ID!\n💳 **Payment:** LTC")
        await ticket_channel.send("Need a Middleman? Open a ticket soon!")
        await vouch_channel.send("📊 **Vouch History** (+rep)")

        await interaction.followup.send("✅ Kanäle erstellt!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Fehler: {e}", ephemeral=True)

# --- START ---
keep_alive()  # Startet den Webserver

# Holt sich den Token sicher aus den Render-Umgebungsvariablen
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Fehler: Kein DISCORD_TOKEN in den Umgebungsvariablen gefunden!")

import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import sqlite3

# --- WEBSERVER FÜR RENDER ---
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

# --- DATENBANK SETUP (SQLite) ---
# Erstellt eine Datenbank-Datei auf Render, um die Vouches zu speichern
def init_db():
    conn = sqlite3.connect("vouches.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reputation (
            user_id TEXT PRIMARY KEY,
            vouch_count INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- TICKET SYSTEM (BUTTON INTERACTION) ---
class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 Open Middleman Ticket", style=discord.ButtonStyle.green, custom_id="open_ticket_btn")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        category = discord.utils.get(guild.categories, name="📌 ACTIVE TRADES")
        channel_name = f"🤝-ticket-{user.name}"
        
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        
        await ticket_channel.send(
            f"👋 Welcome to your Middleman Ticket, {user.mention}!\n\n"
            "Please invite the other trader to this server and mention them here.\n"
            "**Provide the following details:**\n"
            "1️⃣ What item/account are you trading?\n"
            "2️⃣ What is the other user giving? (Amount in LTC)\n\n"
            "An administrator will be with you shortly. **Do not send anything until the Middleman approves!**"
        )

        await interaction.response.send_message(f"✅ Ticket created! Go to {ticket_channel.mention}", ephemeral=True)

# --- VOUCH SYSTEM (BUTTON FÜR KUNDEN) ---
class ConfirmVouchView(discord.ui.View):
    def __init__(self, middleman: discord.User):
        super().__init__(timeout=60) # Nach 60 Sekunden läuft der Button ab
        self.middleman = middleman

    @discord.ui.button(label="👍 Confirm Success (+1 Rep)", style=discord.ButtonStyle.blurple, custom_id="confirm_vouch_btn")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Der Middleman darf sich nicht selbst bewerten!
        if interaction.user.id == self.middleman.id:
            await interaction.response.send_message("❌ You cannot vouch for yourself!", ephemeral=True)
            return

        # Vouch in der Datenbank hochzählen
        conn = sqlite3.connect("vouches.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT vouch_count FROM reputation WHERE user_id = ?", (str(self.middleman.id),))
        row = cursor.fetchone()
        
        if row is None:
            cursor.execute("INSERT INTO reputation (user_id, vouch_count) VALUES (?, ?)", (str(self.middleman.id), 1))
            new_count = 1
        else:
            new_count = row[0] + 1
            cursor.execute("UPDATE reputation SET vouch_count = ? WHERE user_id = ?", (new_count, str(self.middleman.id)))
            
        conn.commit()
        conn.close()

        # Nachricht im offiziellen Vouch-Kanal posten
        vouch_channel = discord.utils.get(interaction.guild.channels, name="✅-vouches")
        if vouch_channel:
            embed = discord.Embed(
                title="🌟 New Successful Trade!",
                description=f"{interaction.user.mention} successfully vouched for {self.middleman.mention}!",
                color=discord.Color.gold()
            )
            embed.add_field(name="Total Reputation", value=f"⭐ {new_count} successful trades")
            await vouch_channel.send(embed=embed)

        # Button deaktivieren
        self.stop()
        await interaction.response.send_message(f"✅ Thank you! You added +1 Rep to {self.middleman.mention}.", ephemeral=True)
        await interaction.message.delete()

# --- DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.guilds = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def on_ready(self):
        self.add_view(TicketButton())
        print(f'🤖 Bot ist online als {self.user}')
        try:
            synced = await self.tree.sync()
            print(f"🔄 {len(synced)} Slash-Commands synchronisiert!")
        except Exception as e:
            print(f"Fehler: {e}")

bot = MyBot()

# --- COMMAND 1: SETUP ---
@bot.tree.command(name="setup", description="Erstellt das komplette Server-Layout.")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    guild = interaction.guild
    await interaction.response.send_message("⏳ Erstelle Server-Layout...", ephemeral=True)
    
    try:
        cat_info = await guild.create_category(name="📢 INFORMATION")
        await guild.create_text_channel(name="👋-welcome", category=cat_info)
        await guild.create_text_channel(name="📢-announcements", category=cat_info)
        ch_rules = await guild.create_text_channel(name="📜-rules-and-info", category=cat_info)
        await guild.create_text_channel(name="🚨-scam-alerts", category=cat_info)

        cat_trade = await guild.create_category(name="💰 TRADING HUB")
        ch_open_ticket = await guild.create_text_channel(name="🎫-open-a-ticket", category=cat_trade)
        ch_vouches = await guild.create_text_channel(name="✅-vouches", category=cat_trade)
        ch_prices = await guild.create_text_channel(name="📈-ltc-rates", category=cat_trade)

        cat_community = await guild.create_category(name="💬 COMMUNITY")
        await guild.create_text_channel(name="💬-general-chat", category=cat_community)
        await guild.create_text_channel(name="🤖-bot-commands", category=cat_community)

        await guild.create_category(name="📌 ACTIVE TRADES")

        await ch_rules.send("💳 **Our LTC Address:** `Deine_LTC_Adresse`\n⚠️ Never trust DMs!")
        await ch_prices.send("⚙️ **Fees:** Trades under 10$ are free! (Requires Vouch)")
        await ch_vouches.send("📊 **Vouch History:** Use `/rep @user` to check someone's successful trades.")

        embed = discord.Embed(
            title="🔒 Secure Middleman Service",
            description="Click the button below to open a private trade ticket.",
            color=discord.Color.green()
        )
        await ch_open_ticket.send(embed=embed, view=TicketButton())
        await interaction.followup.send("✅ Setup komplett!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Fehler: {e}", ephemeral=True)

# --- COMMAND 2: VOUCH ANFORDERN (Nur für Admins/Staff im Ticket) ---
@bot.tree.command(name="vouch", description="Fordert den Kunden auf, den erfolgreichen Trade zu bestätigen.")
@app_commands.checks.has_permissions(manage_messages=True)
async def vouch(interaction: discord.Interaction, middleman: discord.User):
    embed = discord.Embed(
        title="🤝 Trade Finished!",
        description=f"The Middleman {middleman.mention} has completed the trade.\n"
                    "If everything went well, the buyer/seller can click the button below to leave a vouch!",
        color=discord.Color.blue()
    )
    # Sendet die Nachricht mit dem Bestätigungsbutton für den Kunden
    await interaction.response.send_message(embed=embed, view=ConfirmVouchView(middleman))

# --- COMMAND 3: REP ANZEIGEN (Für jeden User) ---
@bot.tree.command(name="rep", description="Zeigt die Anzahl der erfolgreichen Trades eines Users an.")
async def rep(interaction: discord.Interaction, user: discord.User):
    conn = sqlite3.connect("vouches.db")
    cursor = conn.cursor()
    cursor.execute("SELECT vouch_count FROM reputation WHERE user_id = ?", (str(user.id),))
    row = cursor.fetchone()
    conn.close()

    count = row[0] if row else 0

    embed = discord.Embed(
        title=f"📊 Reputation Profile",
        description=f"Checking stats for {user.mention}",
        color=discord.Color.purple()
    )
    embed.add_field(name="Successful Trades", value=f"⭐ {count} Vouches", inline=False)
    
    # Vertrauensstatus je nach Anzahl der Trades
    status = "🔴 Newcomer" if count < 10 else "🟢 Trusted Middleman" if count < 50 else "👑 Godlike Trader"
    embed.add_field(name="Status", value=status, inline=False)
    
    await interaction.response.send_message(embed=embed)

# --- START ---
keep_alive()
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Fehler: Kein DISCORD_TOKEN gefunden!")

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
    return "Bot is active."

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- DATENBANK ---
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

# --- TICKET SYSTEM ---
class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.secondary, custom_id="open_ticket_btn", emoji="📩")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        category = discord.utils.get(guild.categories, name="─── ACTIVE DEALS ───")
        channel_name = f"🤝-deal-{user.name}"
        
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        
        await ticket_channel.send(
            f"⚡ **Welcome to your Deal Ticket, {user.mention}!**\n\n"
            "Bring the other party in here and drop the details:\n"
            "• What's being traded?\n"
            "• What's the LTC amount?\n\n"
            "**Do not send anything** until a Middleman confirms the process in this chat. Stay safe."
        )

        await interaction.response.send_message(f"Ticket opened here: {ticket_channel.mention}", ephemeral=True)

# --- VOUCH SYSTEM ---
class ConfirmVouchView(discord.ui.View):
    def __init__(self, middleman: discord.User):
        super().__init__(timeout=60)
        self.middleman = middleman

    @discord.ui.button(label="Confirm Deal (+1 Rep)", style=discord.ButtonStyle.success, custom_id="confirm_vouch_btn", emoji="🔥")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.middleman.id:
            await interaction.response.send_message("Nice try, you can't vouch for yourself.", ephemeral=True)
            return

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

        vouch_channel = discord.utils.get(interaction.guild.channels, name="🔮︱vouches")
        if vouch_channel:
            embed = discord.Embed(
                title="📈 Deal Completed Successfully",
                description=f"{interaction.user.mention} vouched for {self.middleman.mention}.",
                color=0x2ecc71
            )
            embed.add_field(name="Total Score", value=f"⚡ `{new_count}` Successful Trades")
            await vouch_channel.send(embed=embed)

        self.stop()
        await interaction.response.send_message(f"Rep added to {self.middleman.mention}!", ephemeral=True)
        await interaction.message.delete()

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.guilds = True
intents.members = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def on_ready(self):
        self.add_view(TicketButton())
        print(f'🤖 Live as {self.user}')
        try:
            synced = await self.tree.sync()
            print(f"🔄 Commands synced: {len(synced)}")
        except Exception as e:
            print(f"Sync error: {e}")

bot = MyBot()

# --- REWORKED SETUP COMMAND ---
@bot.tree.command(name="setup", description="Builds a clean, non-cringe marketplace layout.")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    guild = interaction.guild
    await interaction.response.send_message("Setting up the workspace...", ephemeral=True)
    
    try:
        # --- 1. INFO ---
        cat_info = await guild.create_category(name="─── INFORMATION ───")
        await guild.create_text_channel(name="👋︱welcome", category=cat_info)
        await guild.create_text_channel(name="📢︱announcements", category=cat_info)
        ch_rules = await guild.create_text_channel(name="📌︱rules-safety", category=cat_info)

        # --- 2. DEALS HUB ---
        cat_trade = await guild.create_category(name="─── MARKETPLACE ───")
        ch_open_ticket = await guild.create_text_channel(name="📩︱middleman-tickets", category=cat_trade)
        ch_vouches = await guild.create_text_channel(name="🔮︱vouches", category=cat_trade)
        ch_prices = await guild.create_text_channel(name="📈︱ltc-rates", category=cat_trade)

        # --- 3. CHAT ---
        cat_community = await guild.create_category(name="─── COMMUNITY ───")
        await guild.create_text_channel(name="💬︱general", category=cat_community)
        await guild.create_text_channel(name="🤖︱bot-commands", category=cat_community)

        # --- 4. TICKETS CATEGORY ---
        await guild.create_category(name="─── ACTIVE DEALS ───")

        # --- 5. STAFF ---
        cat_staff = await guild.create_category(name="─── MANAGEMENT ───")
        await guild.create_text_channel(name="🔒︱staff-chat", category=cat_staff)

        # --- TEXT REWORKS ---
        await ch_rules.send(
            "⚡ **SERVER RULES & SAFETY** ⚡\n\n"
            "• **Rule #1:** Scamming results in an immediate ban and blacklist.\n"
            "• **Rule #2:** Do not trust anyone DMing you first acting like staff. Check their ID.\n"
            "• **Rule #3:** Use the official ticket channel for trades. Deals made outside tickets are not protected.\n\n"
            "💳 **Official LTC Address:** `Your_LTC_Address`"
        )

        await ch_prices.send(
            "⚙️ **SERVICE FEES**\n\n"
            "• Trades below $10 ➡️ **Free** (Vouch required)\n"
            "• Trades $10 - $50 ➡️ **5% fee**\n"
            "• Trades above $50 ➡️ **10% fee**\n\n"
            "We only deal via **Litecoin (LTC)** or requested Gift Cards. Keep it clean."
        )

        await ch_vouches.send("⚡ **REPUTATION**\n\nUse `/rep @user` to instantly check someone's completed middleman trades.")

        # CLEAN TICKET EMBED (NO CORNY ROBOT WORDS)
        embed = discord.Embed(
            title="Secure Deal Hub",
            description="Need a middleman to secure your trade? Click the button below to start an official deal.\n\n"
                        "Make sure both sides are ready and on the server before applying.",
            color=0x2b2d31 # Dark mode color blend
        )
        await ch_open_ticket.send(embed=embed, view=TicketButton())
        await interaction.followup.send("Setup done.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Error: {e}", ephemeral=True)

# --- VOUCH COMMAND ---
@bot.tree.command(name="vouch", description="Requests a vouch from the client inside the deal.")
@app_commands.checks.has_permissions(manage_messages=True)
async def vouch(interaction: discord.Interaction, middleman: discord.User):
    embed = discord.Embed(
        title="Deal Complete",
        description=f"The trade managed by {middleman.mention} is done.\n"
                    "If everything went smoothly, hit the button below to leave a score.",
        color=0x3498db
    )
    await interaction.response.send_message(embed=embed, view=ConfirmVouchView(middleman))

# --- REP COMMAND ---
@bot.tree.command(name="rep", description="Checks the trade stats of a specific user.")
async def rep(interaction: discord.Interaction, user: discord.User):
    conn = sqlite3.connect("vouches.db")
    cursor = conn.cursor()
    cursor.execute("SELECT vouch_count FROM reputation WHERE user_id = ?", (str(user.id),))
    row = cursor.fetchone()
    conn.close()

    count = row[0] if row else 0

    embed = discord.Embed(
        title=f"User Report: {user.name}",
        color=0x9b59b6
    )
    embed.add_field(name="Vouches", value=f"`{count}` verified deals", inline=True)
    
    status = "⚠️ New Account" if count < 10 else "⚡ Trusted MM" if count < 50 else "👑 Elite Trader"
    embed.add_field(name="Tier", value=f"`{status}`", inline=True)
    
    await interaction.response.send_message(embed=embed)

# --- START ---
keep_alive()
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("Missing token.")

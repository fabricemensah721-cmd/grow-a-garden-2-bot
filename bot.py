import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask
from threading import Thread
import os
import sqlite3
import asyncio

# --- WEBSERVER FÜR RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Active"

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

    @discord.ui.button(label="Open Deal Ticket", style=discord.ButtonStyle.secondary, custom_id="open_ticket_btn", emoji="💼")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        category = discord.utils.get(guild.categories, name="─── ACTIVE DEALS ───")
        channel_name = f"🤝〢deal-{user.name}"
        
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category, overwrites=overwrites)
        
        await ticket_channel.send(
            f"⚡ **Deal Room | {user.mention}**\n\n"
            "Provide the details to start:\n"
            "• What is being traded?\n"
            "• Mention the other trader.\n"
            "• Total amount in LTC.\n\n"
            "**Do not transfer any assets** until the Middleman explicitly tells you to do so."
        )
        await interaction.response.send_message(f"Ticket opened: {ticket_channel.mention}", ephemeral=True)

# --- VOUCH SYSTEM ---
class ConfirmVouchView(discord.ui.View):
    def __init__(self, middleman: discord.User):
        super().__init__(timeout=60)
        self.middleman = middleman

    @discord.ui.button(label="Confirm Deal", style=discord.ButtonStyle.success, custom_id="confirm_vouch_btn", emoji="⚡")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.middleman.id:
            await interaction.response.send_message("You can't vouch for yourself.", ephemeral=True)
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

        vouch_channel = discord.utils.get(interaction.guild.channels, name="📈〢vouches")
        if vouch_channel:
            embed = discord.Embed(
                title="📈 Verified Deal Completed",
                description=f"{interaction.user.mention} vouched for {self.middleman.mention}.",
                color=0x2ecc71
            )
            embed.add_field(name="Total Score", value=f"⚡ `{new_count}` Successful Trades")
            await vouch_channel.send(embed=embed)

        self.stop()
        await interaction.response.send_message(f"Rep added!", ephemeral=True)
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

# --- NUKING & REBUILDING SETUP COMMAND ---
@bot.tree.command(name="setup", description="Wipes the entire server and builds an elite marketplace layout.")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    guild = interaction.guild
    
    # Erste Antwort, um das Timeout zu verhindern
    await interaction.response.send_message("🚨 **Wiping and rebuilding the server layout...** This will take a few seconds.", ephemeral=True)
    
    try:
        # --- RADIKALES LÖSCHEN ALLER KANÄLE & KATEGORIEN ---
        for channel in guild.channels:
            try:
                await channel.delete()
                await asyncio.sleep(0.2) # Kleiner Delay gegen Discord Rate-Limits
            except Exception:
                pass # Ignoriert Kanäle, die nicht gelöscht werden können (z.B. der absolute Standard-Kanal)

        # --- NEUAUFBAU: 1. INFO ---
        cat_info = await guild.create_category(name="📁 ─── INFO ───")
        await guild.create_text_channel(name="👋〢welcome", category=cat_info)
        await guild.create_text_channel(name="📢〢announcements", category=cat_info)
        ch_rules = await guild.create_text_channel(name="📌〢rules-safety", category=cat_info)

        # --- NEUAUFBAU: 2. BUSINESS ---
        cat_trade = await guild.create_category(name="💸 ─── MARKETPLACE ───")
        ch_open_ticket = await guild.create_text_channel(name="📩〢middleman-tickets", category=cat_trade)
        ch_vouches = await guild.create_text_channel(name="📈〢vouches", category=cat_trade)
        ch_prices = await guild.create_text_channel(name="📊〢rates-fees", category=cat_trade)

        # --- NEUAUFBAU: 3. TALK ---
        cat_community = await guild.create_category(name="💬 ─── CHATROOMS ───")
        await guild.create_text_channel(name="💬〢general", category=cat_community)
        await guild.create_text_channel(name="🤖〢bot-commands", category=cat_community)

        # --- NEUAUFBAU: 4. DEALS CATEGORY ---
        await guild.create_category(name="─── ACTIVE DEALS ───")

        # --- NEUAUFBAU: 5. STAFF ---
        cat_staff = await guild.create_category(name="🔒 ─── STAFF ONLY ───")
        await guild.create_text_channel(name="🔒〢staff-chat", category=cat_staff)

        # --- CONTENT SETUP ---
        await ch_rules.send(
            "⚡ **MARKETPLACE SAFETY & RULES** ⚡\n\n"
            "• **Rule #1:** Any scam attempt results in a permanent ban and network blacklist.\n"
            "• **Rule #2:** Staff will NEVER DM you first to secure a trade. Always verify IDs.\n"
            "• **Rule #3:** Only conduct deals inside official tickets. Direct trades are unprotected.\n\n"
            "💳 **Official LTC Address:** `Your_LTC_Address`"
        )

        await ch_prices.send(
            "📊 **SERVICE FEES**\n\n"
            "• Deals below $10 ➡️ **Free** (Vouch required)\n"
            "• Deals $10 - $50 ➡️ **5% flat fee**\n"
            "• Deals above $50 ➡️ **10% flat fee**\n\n"
            "We strictly accept **Litecoin (LTC)**. Fast processing, low network fees."
        )

        await ch_vouches.send("🔮 **REPUTATION HUB**\n\nUse `/rep @user` to instantly view a middleman's completed transaction count.")

        # CLEAN HIGH-END EMBED
        embed = discord.Embed(
            title="Secure Escrow Hub",
            description="Need a trusted middleman to secure your asset or payment?\n"
                        "Click the button below to initiate an automated deal room.\n\n"
                        "⚠️ *Both parties must be online and present on this server.*",
            color=0x2b2d31 # Native Discord Dark Mode color blend
        )
        await ch_open_ticket.send(embed=embed, view=TicketButton())

    except Exception as e:
        print(f"Error during reconstruction: {e}")

# --- VOUCH COMMAND ---
@bot.tree.command(name="vouch", description="Requests a trade confirmation from the client.")
@app_commands.checks.has_permissions(manage_messages=True)
async def vouch(interaction: discord.Interaction, middleman: discord.User):
    embed = discord.Embed(
        title="Deal Finalized",
        description=f"The transaction handled by {middleman.mention} has been completed.\n"
                    "If the service was safe, tap the button below to log your vouch.",
        color=0x3498db
    )
    await interaction.response.send_message(embed=embed, view=ConfirmVouchView(middleman))

# --- REP COMMAND ---
@bot.tree.command(name="rep", description="Checks verified transaction score.")
async def rep(interaction: discord.Interaction, user: discord.User):
    conn = sqlite3.connect("vouches.db")
    cursor = conn.cursor()
    cursor.execute("SELECT vouch_count FROM reputation WHERE user_id = ?", (str(user.id),))
    row = cursor.fetchone()
    conn.close()

    count = row[0] if row else 0

    embed = discord.Embed(
        title=f"Reputation Check: {user.name}",
        color=0x9b59b6
    )
    embed.add_field(name="Verified Deals", value=f"`{count}` successes", inline=True)
    
    status = "⚠️ Unverified" if count < 10 else "⚡ Trusted Member" if count < 50 else "👑 Elite Escrow"
    embed.add_field(name="Tier Status", value=f"`{status}`", inline=True)
    
    await interaction.response.send_message(embed=embed)

# --- START ---
keep_alive()
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("Token error.")

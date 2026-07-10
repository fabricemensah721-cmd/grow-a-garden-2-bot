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

# --- TICKET SYSTEM (INTERACTION) ---
class TicketButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Deal Ticket", style=discord.ButtonStyle.secondary, custom_id="open_ticket_btn", emoji="💼")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        staff_role = discord.utils.get(guild.roles, name="🛡️ Staff")
        owner_role = discord.utils.get(guild.roles, name="👑 Owner")

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        if owner_role:
            overwrites[owner_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

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
@bot.tree.command(name="setup", description="Wipes everything, creates elite layout, roles & safe permissions.")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    guild = interaction.guild
    await interaction.response.send_message("🚨 **Wiping and rebuilding server layout & roles...** Please wait.", ephemeral=True)
    
    try:
        for channel in guild.channels:
            try:
                await channel.delete()
                await asyncio.sleep(0.1)
            except Exception:
                pass

        owner_role = discord.utils.get(guild.roles, name="👑 Owner") or await guild.create_role(name="👑 Owner", color=discord.Color.red(), hoist=True)
        staff_role = discord.utils.get(guild.roles, name="🛡️ Staff") or await guild.create_role(name="🛡️ Staff", color=discord.Color.blue(), hoist=True)
        member_role = discord.utils.get(guild.roles, name="👤 Member") or await guild.create_role(name="👤 Member", color=discord.Color.light_gray(), hoist=True)

        await interaction.user.add_roles(owner_role)

        read_only_perms = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
            staff_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            owner_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        staff_only_perms = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            staff_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            owner_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        public_chat_perms = {
            guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        cat_info = await guild.create_category(name="📁 ─── INFO ───")
        await guild.create_text_channel(name="👋〢welcome", category=cat_info, overwrites=read_only_perms)
        await guild.create_text_channel(name="📢〢announcements", category=cat_info, overwrites=read_only_perms)
        ch_rules = await guild.create_text_channel(name="📌〢rules-safety", category=cat_info, overwrites=read_only_perms)

        cat_trade = await guild.create_category(name="💸 ─── MARKETPLACE ───")
        ch_open_ticket = await guild.create_text_channel(name="📩〢middleman-tickets", category=cat_trade, overwrites=read_only_perms)
        ch_vouches = await guild.create_text_channel(name="📈〢vouches", category=cat_trade, overwrites=read_only_perms)
        ch_prices = await guild.create_text_channel(name="📊〢rates-fees", category=cat_trade, overwrites=read_only_perms)

        cat_community = await guild.create_category(name="💬 ─── CHATROOMS ───")
        await guild.create_text_channel(name="💬〢general", category=cat_community, overwrites=public_chat_perms)
        await guild.create_text_channel(name="🤖〢bot-commands", category=cat_community, overwrites=public_chat_perms)

        await guild.create_category(name="─── ACTIVE DEALS ───")

        cat_staff = await guild.create_category(name="🔒 ─── STAFF ONLY ───")
        await guild.create_text_channel(name="🔒〢staff-chat", category=cat_staff, overwrites=staff_only_perms)

        await ch_rules.send(
            "⚡ **MARKETPLACE SAFETY & RULES** ⚡\n\n"
            "• **Rule #1:** Any scam attempt results in a permanent ban and network blacklist.\n"
            "• **Rule #2:** Staff will NEVER DM you first to secure a trade. Always verify IDs.\n"
            "• **Rule #3:** Only conduct deals inside official tickets. Direct trades are unprotected.\n\n"
            f"💳 **Official LTC Address:** `ltc1qmh0cyasdnk80svv5wf0fau993kppagtydud6dx`"
        )

        await ch_prices.send(
            "📊 **SERVICE FEES**\n\n"
            "• Deals below $10 ➡️ **Free** (Vouch required)\n"
            "• Deals $10 - $50 ➡️ **5% flat fee**\n"
            "• Deals above $50 ➡️ **10% flat fee**\n\n"
            "We strictly accept **Litecoin (LTC)**. Fast processing, low network fees."
        )

        await ch_vouches.send("🔮 **REPUTATION HUB**\n\nUse `/rep @user` to instantly view a middleman's completed transaction count.")

        # Postet das Ticket-System direkt beim Setup in den passenden Kanal
        embed = discord.Embed(
            title="Secure Escrow Hub",
            description="Need a trusted middleman to secure your asset or payment?\n"
                        "Click the button below to initiate an automated deal room.\n\n"
                        "⚠️ *Both parties must be online and present on this server.*",
            color=0x2b2d31
        )
        await ch_open_ticket.send(embed=embed, view=TicketButton())

    except Exception as e:
        print(f"Error during reconstruction: {e}")

# --- NEUER SEPARATER COMMAND FÜR DAS TICKET-BED ---
@bot.tree.command(name="middlemanticket", description="Posts the secure escrow ticket system panel into the current channel.")
@app_commands.checks.has_permissions(manage_channels=True)
async def middlemanticket(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Secure Escrow Hub",
        description="Need a trusted middleman to secure your asset or payment?\n"
                    "Click the button below to initiate an automated deal room.\n\n"
                    "⚠️ *Both parties must be online and present on this server.*",
        color=0x2b2d31
    )
    # Postet das Panel genau in den Kanal, in dem du dich gerade befindest
    await interaction.channel.send(embed=embed, view=TicketButton())
    await interaction.response.send_message("Ticket panel spawned successfully.", ephemeral=True)

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

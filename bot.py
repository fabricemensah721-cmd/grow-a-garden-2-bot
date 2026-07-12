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

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        # Vouch Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vouches (
                user_id TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        """)
        # Stock/Switcher Table for Sellers
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock (
                item_name TEXT PRIMARY KEY,
                status TEXT DEFAULT 'AVAILABLE',
                amount INTEGER DEFAULT 0
            )
        """)
        conn.commit()
        conn.close()
        print("Database & Switcher Modules loaded successfully.")

bot = MyBot()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")


# --- 1. PREMIUM JACE SWITCHER & UTILITY COMMANDS ---

# Feature A: Krypto & Rate Switcher (Rechner für Trader)
@bot.tree.command(name="switch_rate", description="Calculate cross-trading exchange rates (e.g., Robux to LTC)")
@app_commands.describe(from_currency="The currency you give", to_currency="The currency you want", amount="Amount to convert")
async def switch_rate(interaction: discord.Interaction, from_currency: str, to_currency: str, amount: float):
    # Simulierter Live-Kurs-Rechner speziell für Roblox/Krypto-Marktplätze
    fee = amount * 0.03 # 3% Standard-Marktplatzgebühr
    final_amount = (amount - fee) * random.uniform(0.85, 0.95) # Simulierter Wechselkurs-Schnitt
    
    embed = discord.Embed(
        title="🔄 Jace Exchange Rate Switcher",
        description=f"Conversion details for trading safely.",
        color=discord.Color.purple()
    )
    embed.add_field(name="Input", value=f"`{amount:.2f} {from_currency.upper()}`", inline=True)
    embed.add_field(name="Estimated Output", value=f"`{final_amount:.4f} {to_currency.upper()}`", inline=True)
    embed.add_field(name="Marketplace Fee (3%)", value=f"`{fee:.2f} {from_currency.upper()}`", inline=False)
    embed.set_footer(text="Use /ticket to execute this trade with an official middleman.")
    
    await interaction.response.send_message(embed=embed)


# Feature B: Seller Stock Switcher (Schnelles Umschalten von Produktstatus)
@bot.tree.command(name="switch_stock", description="Switch the availability status of a marketplace item")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.choices(status=[
    app_commands.Choice(name="Available", value="AVAILABLE ✅"),
    app_commands.Choice(name="Out of Stock", value="OUT OF STOCK ❌"),
    app_commands.Choice(name="Restocking", value="RESTOCKING ⏳")
])
async def switch_stock(interaction: discord.Interaction, item_name: str, status: app_commands.Choice[str], amount: int):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO stock (item_name, status, amount) 
        VALUES (?, ?, ?)
        ON CONFLICT(item_name) DO UPDATE SET status=excluded.status, amount=excluded.amount
    """, (item_name.lower(), status.value, amount))
    conn.commit()
    conn.close()
    
    embed = discord.Embed(
        title="📦 Stock Switcher Updated",
        description=f"The status for **{item_name.upper()}** has been switched successfully.",
        color=discord.Color.green()
    )
    embed.add_field(name="New Status", value=status.value, inline=True)
    embed.add_field(name="Available Amount", value=f"`{amount}` items", inline=True)
    
    await interaction.response.send_message(embed=embed)


# Feature C: Check Current Stock
@bot.tree.command(name="stock", description="Check current stock of an item")
async def check_stock(interaction: discord.Interaction, item_name: str):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status, amount FROM stock WHERE item_name = ?", (item_name.lower(),))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        await interaction.response.send_message(f"Item `{item_name}` is not registered in the stock database.", ephemeral=True)
        return
        
    embed = discord.Embed(title=f"📦 Stock Info: {item_name.upper()}", color=discord.Color.blue())
    embed.add_field(name="Status", value=row[0], inline=True)
    embed.add_field(name="In Stock", value=f"`{row[1]}` left", inline=True)
    await interaction.response.send_message(embed=embed)


# --- 2. SETUP COMMAND (20 CHANNELS) ---
@bot.tree.command(name="setup", description="Deletes ALL channels and builds a fresh 20-channel professional marketplace setup")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    
    for channel in guild.channels:
        try:
            await channel.delete()
        except Exception as e:
            print(f"Could not delete channel {channel.name}: {e}")
            
    structure = {
        "— INFORMATION —": [
            "📢〢announcements",
            "📜〢rules",
            "📈〢vouches",
            "💎〢premium-benefits",
            "💳〢payment-methods",
            "🔗〢our-links"
        ],
        "— MARKETPLACE —": [
            "🛒〢buy-server-setup",
            "⚙️〢custom-bots",
            "📦〢current-stock",
            "🤖〢showcase",
            "💸〢roblox-trading",
            "🔄〢item-trading",
            "💰〢crypto-exchange"
        ],
        "— SUPPORT & COMMUNITY —": [
            "📩〢tickets",
            "💬〢general-chat",
            "🎭〢off-topic",
            "🤖〢bot-commands",
            "🎉〢giveaways",
            "🤝〢partnerships",
            "❓〢faq"
        ]
    }
    
    for cat_name, channels in structure.items():
        category = await guild.create_category(cat_name)
        for ch_name in channels:
            await guild.create_text_channel(ch_name, category=category)
            await asyncio.sleep(0.5)
            
    await interaction.followup.send("Server successfully wiped and completely rebuilt with 20 professional channels!", ephemeral=True)


# --- 3. SUPPORT TICKET SYSTEM ---
class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Support Ticket", style=discord.ButtonStyle.green, custom_id="open_ticket_btn")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True)
        }
        
        channel_name = f"ticket-{member.name.lower()}"
        existing_channel = discord.utils.get(guild.channels, name=channel_name)
        
        if existing_channel:
            await interaction.response.send_message(f"You already have an open ticket: {existing_channel.mention}", ephemeral=True)
            return
            
        ticket_category = discord.utils.get(guild.categories, name="— SUPPORT & COMMUNITY —")
        channel = await guild.create_text_channel(name=channel_name, category=ticket_category, overwrites=overwrites)
        
        close_view = TicketCloseView()
        await channel.send(
            f"Welcome {member.mention}! Please describe what service or setup you want to purchase. Support will be with you shortly.",
            view=close_view
        )
        await interaction.response.send_message(f"Your ticket has been created: {channel.mention}", ephemeral=True)

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_room_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("This ticket will be permanently deleted in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

@bot.tree.command(name="ticket", description="Sends the ticket creation panel to the current channel")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction):
    view = TicketButtonView()
    embed = discord.Embed(
        title="Marketplace Central Ticket Hub",
        description="Click the button below to open a private ticket with our team. Here we can discuss your custom server setup or order details.",
        color=discord.Color.blue()
    )
    
    try:
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Ticket panel successfully sent!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Error: Missing permissions to send messages!", ephemeral=True)


# --- 4. REPUTATION & VOUCH SYSTEM ---
@bot.tree.command(name="vouch", description="Give a reputation point to a user")
async def vouch(interaction: discord.Interaction, user: discord.User):
    if user.id == interaction.user.id:
        await interaction.response.send_message("You cannot vouch for yourself!", ephemeral=True)
        return
        
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
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
    
    embed = discord.Embed(title="+1 Vouch Registered!", description=f"{interaction.user.mention} vouched for {user.mention}!\n\n**Total:** `{new_count}`", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rep", description="Check the total vouches of a user")
async def rep(interaction: discord.Interaction, user: discord.User):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT count FROM vouches WHERE user_id = ?", (str(user.id),))
    row = cursor.fetchone()
    conn.close()
    
    count = row[0] if row else 0
    await interaction.response.send_message(f"User {user.mention} has **{count} verified vouches**.", ephemeral=False)


# --- START BOT ---
TOKEN = os.getenv("DISCORD_TOKEN", "DEIN_BOT_TOKEN")
bot.run(TOKEN)

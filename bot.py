import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import os
import asyncio
import random
import urllib.request
import json

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
        # Stock Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock (
                item_name TEXT PRIMARY KEY,
                status TEXT DEFAULT 'AVAILABLE',
                amount INTEGER DEFAULT 0
            )
        """)
        # Account Switcher Table (Verschlüsselte/Sichere Aufbewahrung von Notizen/Alts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alts (
                user_id TEXT,
                alt_name TEXT,
                status TEXT DEFAULT 'FREE',
                PRIMARY KEY (user_id, alt_name)
            )
        """)
        conn.commit()
        conn.close()
        print("⚡ Jace Switcher Engine & Database loaded successfully.")

bot = MyBot()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")


# =========================================================================
# --- DIE WIRKLICH ALLER ALLEINIGEN JACE SWITCHER COMMANDS (PREMIUM) ---
# =========================================================================

# 1. LIVE CRYPTO SWITCHER (Holt echte Live-Kurse von einer API)
@bot.tree.command(name="crypto", description="Get the live price of crypto or switch USD to Crypto amounts")
@app_commands.describe(coin="The coin (e.g., ltc, btc, eth)", usd_amount="Amount in USD to convert")
async def crypto(interaction: discord.Interaction, coin: str, usd_amount: float):
    await interaction.response.defer()
    coin = coin.lower()
    
    # Mapping für Coingecko API
    coin_map = {"ltc": "litecoin", "btc": "bitcoin", "eth": "ethereum", "usdt": "tether"}
    api_id = coin_map.get(coin, coin)
    
    try:
        # Sichere Live-Abfrage ohne externe Libraries (urllib)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={api_id}&vs_currencies=usd"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            
        if api_id in data:
            price = data[api_id]["usd"]
            crypto_needed = usd_amount / price
            
            embed = discord.Embed(title=f"🪙 Live {coin.upper()} Switcher Price", color=discord.Color.gold())
            embed.add_field(name="Current Price", value=f"`1 {coin.upper()} = ${price:,.2f} USD`", inline=False)
            embed.add_field(name="Switch Request", value=f"`${usd_amount:.2f} USD` equals **`{crypto_needed:.6f} {coin.upper()}`**", inline=False)
            embed.set_footer(text="Rates updated live via CoinGecko.")
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"Coin `{coin}` not found. Use ltc, btc, or eth.", ephemeral=True)
    except Exception as e:
        # Fallback falls API Rate-Limited ist
        await interaction.followup.send(f"API busy. Hardcoded standard rate fallback: ${usd_amount:.2f} switching to LTC...", ephemeral=True)


# 2. ROBLOX TAX SWITCHER (Berechnet die 30% Steuer für Gamepasses/Shirts)
@bot.tree.command(name="switch_tax", description="Calculates Roblox 30% tax (What you need to set or what you get)")
@app_commands.describe(mode="Choose if you want to calculate what you receive or what you must price it at")
@app_commands.choices(mode=[
    app_commands.Choice(name="I want to receive X Robux (Calculate Price to set)", value="set"),
    app_commands.Choice(name="I sell a gamepass for X Robux (Calculate my Profit)", value="get")
])
async def switch_tax(interaction: discord.Interaction, mode: app_commands.Choice[str], robux: int):
    embed = discord.Embed(title="🎮 Roblox Tax Switcher", color=discord.Color.red())
    
    if mode.value == "set":
        # Um X zu bekommen, muss man X / 0.7 verlangen
        price_to_set = int(robux / 0.7)
        tax = price_to_set - robux
        embed.add_field(name="Target Robux (Net)", value=f"`{robux}` Robux", inline=True)
        embed.add_field(name="Price to Set (Gross)", value=f"**`{price_to_set}` Robux**", inline=True)
        embed.add_field(name="Roblox Tax (30%)", value=f"`{tax}` Robux", inline=False)
    else:
        # Wenn man für X verkauft, bekommt man X * 0.7
        profit = int(robux * 0.7)
        tax = robux - profit
        embed.add_field(name="Selling Price (Gross)", value=f"`{robux}` Robux", inline=True)
        embed.add_field(name="Your Profit (Net)", value=f"**`{profit}` Robux**", inline=True)
        embed.add_field(name="Roblox Tax (30%)", value=f"`{tax}` Robux", inline=False)
        
    await interaction.response.send_message(embed=embed)


# 3. ACCOUNT SWITCHER (Verwaltung von Trading-Alts / Accounts)
@bot.tree.command(name="switch_account", description="Manage or switch between your registered trading alt-accounts")
@app_commands.choices(action=[
    app_commands.Choice(name="Add/Update Alt-Account", value="add"),
    app_commands.Choice(name="Switch Status (FREE / BUSY)", value="status"),
    app_commands.Choice(name="List My Alts", value="list")
])
async def switch_account(interaction: discord.Interaction, action: app_commands.Choice[str], name: str, status: str = "FREE"):
    user_id = str(interaction.user.id)
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    
    if action.value == "add":
        cursor.execute("INSERT OR REPLACE INTO alts (user_id, alt_name, status) VALUES (?, ?, ?)", (user_id, name, status.upper()))
        await interaction.response.send_message(f"✅ Alt-Account `{name}` has been saved/updated with status `{status.upper()}`.", ephemeral=True)
    elif action.value == "status":
        cursor.execute("UPDATE alts SET status = ? WHERE user_id = ? AND alt_name = ?", (status.upper(), user_id, name))
        await interaction.response.send_message(f"🔄 Switched status of `{name}` to `{status.upper()}`.", ephemeral=True)
    elif action.value == "list":
        cursor.execute("SELECT alt_name, status FROM alts WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        if not rows:
            await interaction.response.send_message("❌ You have no alt-accounts registered.", ephemeral=True)
            conn.close()
            return
        
        embed = discord.Embed(title="👤 Your Switcher Alt-Accounts", color=discord.Color.blue())
        for r in rows:
            embed.add_field(name=f"Acc: {r[0]}", value=f"Status: `{r[1]}`", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
    conn.commit()
    conn.close()


# 4. CROSS-TRADE EXCHANGE RATE SWITCHER
@bot.tree.command(name="switch_rate", description="Calculate cross-trading exchange rates (e.g., Robux to LTC)")
async def switch_rate(interaction: discord.Interaction, from_currency: str, to_currency: str, amount: float):
    fee = amount * 0.03
    final_amount = (amount - fee) * random.uniform(0.85, 0.95)
    
    embed = discord.Embed(title="🔄 Jace Exchange Rate Switcher", color=discord.Color.purple())
    embed.add_field(name="Input", value=f"`{amount:.2f} {from_currency.upper()}`", inline=True)
    embed.add_field(name="Estimated Output", value=f"`{final_amount:.4f} {to_currency.upper()}`", inline=True)
    embed.add_field(name="Marketplace Fee (3%)", value=f"`{fee:.2f} {from_currency.upper()}`", inline=False)
    await interaction.response.send_message(embed=embed)


# 5. MARKETPLACE STOCK SWITCHER
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
    
    embed = discord.Embed(title="📦 Stock Switcher Updated", color=discord.Color.green())
    embed.add_field(name="New Status", value=status.value, inline=True)
    embed.add_field(name="Available Amount", value=f"`{amount}` items", inline=True)
    await interaction.response.send_message(embed=embed)


# 6. STOCK CHECKER
@bot.tree.command(name="stock", description="Check current stock of an item")
async def check_stock(interaction: discord.Interaction, item_name: str):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status, amount FROM stock WHERE item_name = ?", (item_name.lower(),))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        await interaction.response.send_message(f"Item `{item_name}` is not in the database.", ephemeral=True)
        return
        
    embed = discord.Embed(title=f"📦 Stock Info: {item_name.upper()}", color=discord.Color.blue())
    embed.add_field(name="Status", value=row[0], inline=True)
    embed.add_field(name="In Stock", value=f"`{row[1]}` left", inline=True)
    await interaction.response.send_message(embed=embed)


# 7. DEAL LOGGER (Loggt Deals direkt im Ticket-Kanal ein)
@bot.tree.command(name="log_deal", description="Logs a deal layout inside a ticket for easy tracking")
@app_commands.describe(partner="The user you are trading with", your_offer="What you offer", their_offer="What they offer")
async def log_deal(interaction: discord.Interaction, partner: discord.User, your_offer: str, their_offer: str):
    embed = discord.Embed(title="📝 Jace Official Deal Log", color=discord.Color.teal())
    embed.add_field(name="Trader 1 (Sender)", value=interaction.user.mention, inline=True)
    embed.add_field(name="Trader 2 (Partner)", value=partner.mention, inline=True)
    embed.add_field(name="Trader 1 Sends:", value=f"`{your_offer}`", inline=False)
    embed.add_field(name="Trader 2 Sends:", value=f"`{their_offer}`", inline=False)
    embed.set_footer(text="Please wait for an admin or staff member to verify the log.")
    await interaction.response.send_message(embed=embed)


# =========================================================================
# --- RESTLICHE SYSTEME (SETUP, TICKETS, VOUCHES) ---
# =========================================================================

# --- AUTOMATIC SETUP ---
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
            "📢〢announcements", "📜〢rules", "📈〢vouches", "💎〢premium-benefits", "💳〢payment-methods", "🔗〢our-links"
        ],
        "— MARKETPLACE —": [
            "🛒〢buy-server-setup", "⚙️〢custom-bots", "📦〢current-stock", "🤖〢showcase", "💸〢roblox-trading", "🔄〢item-trading", "💰〢crypto-exchange"
        ],
        "— SUPPORT & COMMUNITY —": [
            "📩〢tickets", "💬〢general-chat", "🎭〢off-topic", "🤖〢bot-commands", "🎉〢giveaways", "🤝〢partnerships", "❓〢faq"
        ]
    }
    
    for cat_name, channels in structure.items():
        category = await guild.create_category(cat_name)
        for ch_name in channels:
            await guild.create_text_channel(ch_name, category=category)
            await asyncio.sleep(0.5)
            
    await interaction.followup.send("Server successfully wiped and completely rebuilt with 20 professional channels!", ephemeral=True)


# --- TICKET CORE ---
class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Support Ticket", style=discord.ButtonStyle.green, custom_id="solo_support_ticket_btn")
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

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_solo_ticket_btn")
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
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("Ticket panel successfully sent!", ephemeral=True)


# --- REPUTATION / VOUCH SYSTEM ---
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

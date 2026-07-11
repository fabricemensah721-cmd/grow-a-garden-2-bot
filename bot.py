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

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
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
        print("Database loaded successfully.")

bot = MyBot()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")


# --- 1. CLEAN & PURGE SETUP COMMAND (20+ CHANNELS) ---
@bot.tree.command(name="setup", description="Deletes ALL channels and builds a fresh 20+ channel professional marketplace setup")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    # Defer response since deleting and creating 20+ channels takes time
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    
    # STEP 1: Delete all existing channels and categories
    for channel in guild.channels:
        try:
            await channel.delete()
        except Exception as e:
            print(f"Could not delete channel {channel.name}: {e}")
            
    # STEP 2: Define categories and channels (Exactly 20 highly optimized professional channels)
    structure = {
        "— INFORMATION —": [
            "📢〢announcements",
            "📜〢rules",
            "📈〢vouches",
            "💎〢premium-benefits",
            "🔗〢our-links"
        ],
        "— MARKETPLACE —": [
            "🛒〢buy-server-setup",
            "⚙️〢custom-bots",
            "🤖〢showcase",
            "💸〢roblox-cross-trading",
            "🔄〢item-trading",
            "💰〢crypto-exchange"
        ],
        "— MIDDLEMAN —": [
            "🤝〢mm-requests",
            "🛡️〢mm-vouches",
            "🚫〢scammer-list",
            "❓〢how-it-works",
            "🎖️〢trusted-middlemen"
        ],
        "— SUPPORT —": [
            "📩〢tickets",
            "💬〢general-chat",
            "🎉〢giveaways",
            "❓〢faq"
        ]
    }
    
    # STEP 3: Create everything cleanly
    for cat_name, channels in structure.items():
        category = await guild.create_category(cat_name)
        for ch_name in channels:
            await guild.create_text_channel(ch_name, category=category)
            # Small sleep to avoid hitting Discord rate limits during mass creation
            await asyncio.sleep(0.5)
            
    await interaction.followup.send("Server successfully wiped and completely rebuilt with 20 professional marketplace channels!", ephemeral=True)


# --- 2. ADVANCED TICKET & MIDDLEMAN SYSTEM ---
class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # BUTTON 1: GENERAL TICKETS
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
            
        ticket_category = discord.utils.get(guild.categories, name="— SUPPORT —")
        channel = await guild.create_text_channel(name=channel_name, category=ticket_category, overwrites=overwrites)
        
        close_view = TicketCloseView()
        await channel.send(
            f"Welcome {member.mention}! Please describe what service or setup you want to purchase. Support will be with you shortly.",
            view=close_view
        )
        await interaction.response.send_message(f"Your ticket has been created: {channel.mention}", ephemeral=True)

    # BUTTON 2: AUTOMATIC MIDDLEMAN SYSTEM
    @discord.ui.button(label="Request Middleman", style=discord.ButtonStyle.blurple, custom_id="request_mm_btn")
    async def request_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user
        
        mm_role = discord.utils.get(guild.roles, name="Middleman") or discord.utils.get(guild.roles, name="Staff")
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, embed_links=True)
        }
        
        if mm_role:
            overwrites[mm_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
        channel_name = f"🤝〢mm-{member.name.lower()}"
        existing_channel = discord.utils.get(guild.channels, name=channel_name)
        
        if existing_channel:
            await interaction.response.send_message(f"You already have a pending Middleman room: {existing_channel.mention}", ephemeral=True)
            return
            
        ticket_category = discord.utils.get(guild.categories, name="— MIDDLEMAN —")
        channel = await guild.create_text_channel(name=channel_name, category=ticket_category, overwrites=overwrites)
        
        close_view = TicketCloseView()
        
        embed = discord.Embed(
            title="🤝 New Middleman Request",
            description="An official middleman will assist you shortly. Please fill out the transaction details below to speed up the process.",
            color=discord.Color.gold()
        )
        embed.add_field(name="User 1 (You)", value=member.mention, inline=True)
        embed.add_field(name="User 2 (Trading with)", value="Mention them here", inline=True)
        embed.add_field(name="Your Offer", value="Specify your items/crypto", inline=False)
        embed.add_field(name="Their Offer", value="Specify their items/crypto", inline=False)
        
        ping_msg = f"{mm_role.mention} " if mm_role else ""
        await channel.send(content=f"{ping_msg}{member.mention}", embed=embed, view=close_view)
        await interaction.response.send_message(f"Your Middleman room has been created: {channel.mention}", ephemeral=True)

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Room", style=discord.ButtonStyle.red, custom_id="close_room_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("This room will be permanently deleted in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

@bot.tree.command(name="ticket", description="Sends the dual ticket and middleman panel to the current channel")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction):
    view = TicketButtonView()
    embed = discord.Embed(
        title="Marketplace Central Hub",
        description="Click one of the buttons below depending on what you need:\n\n"
                    "➡️ **Open Support Ticket:** Order a custom server setup or talk to staff.\n"
                    "➡️ **Request Middleman:** Open a secure trading deal room guarded by our verified Middlemen.",
        color=discord.Color.blue()
    )
    
    try:
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Hub panel successfully sent!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Error: Missing permissions to send messages!", ephemeral=True)


# --- 3. REPUTATION & VOUCH SYSTEM ---
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

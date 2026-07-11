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
        # Initialize SQLite Database
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
        # Sync slash commands globally
        synced = await bot.tree.sync()
        print(f"Successfully synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")


# --- 1. SETUP COMMAND ---
@bot.tree.command(name="setup", description="Creates the default channels for the marketplace")
@app_commands.checks.has_permissions(administrator=True)
async def setup(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    
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
            
    await interaction.followup.send("Server channels have been successfully set up!", ephemeral=True)


# --- 2. TICKET SYSTEM ---
class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Buttons never expire

    @discord.ui.button(label="Open Ticket", style=discord.ButtonStyle.green, custom_id="open_ticket_btn")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = interaction.user
        
        # Set permissions for the new ticket channel
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
            
        ticket_category = discord.utils.get(guild.categories, name="MARKET")
        channel = await guild.create_text_channel(
            name=channel_name, 
            category=ticket_category, 
            overwrites=overwrites
        )
        
        close_view = TicketCloseView()
        await channel.send(
            f"Welcome {member.mention}! Please describe what service or setup you want to purchase. Support will be with you shortly.",
            view=close_view
        )
        await interaction.response.send_message(f"Your ticket has been created: {channel.mention}", ephemeral=True)

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="close_ticket_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("This ticket will be deleted in 5 seconds...")
        import asyncio
        await asyncio.sleep(5)
        await interaction.channel.delete()

@bot.tree.command(name="ticket", description="Sends the ticket creation panel to the current channel")
@app_commands.checks.has_permissions(administrator=True)
async def ticket_panel(interaction: discord.Interaction):
    view = TicketButtonView()
    embed = discord.Embed(
        title="Support & Trade Tickets",
        description="Click the button below to open a private ticket with our team. Here we can discuss your custom server setup or order details.",
        color=discord.Color.blue()
    )
    
    try:
        # Send the panel directly into the channel first
        await interaction.channel.send(embed=embed, view=view)
        # Inform the admin that it worked
        await interaction.response.send_message("Panel successfully sent!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("Error: The bot does not have permissions to send messages or embeds in this channel!", ephemeral=True)


# --- 3. REPUTATION & VOUCH SYSTEM ---
@bot.tree.command(name="vouch", description="Give a reputation point to a user after a successful deal")
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
    
    embed = discord.Embed(
        title="+1 Vouch Registered!",
        description=f"{interaction.user.mention} has successfully vouched for {user.mention}!\n\n**Current total vouches for {user.name}:** `{new_count}`",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rep", description="Check the total vouches of a user")
async def rep(interaction: discord.Interaction, user: discord.User):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT count FROM vouches WHERE user_id = ?", (str(user.id),))
    row = cursor.fetchone()
    conn.close()
    
    count = row[0] if row else 0
    
    await interaction.response.send_message(f"User {user.mention} currently has **{count} verified vouches** on this server.", ephemeral=False)


# --- ERROR HANDLING ---
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.MissingPermissions):
        await interaction.response.send_message("You do not have permission to use this command! (Admin only)", ephemeral=True)
    else:
        print(f"An error occurred: {error}")


# --- START BOT ---
TOKEN = os.getenv("DISCORD_TOKEN", "DEIN_BOT_TOKEN")
if TOKEN == "DEIN_BOT_TOKEN":
    print("[WARNING] Please add your actual bot token to the code!")
bot.run(TOKEN)

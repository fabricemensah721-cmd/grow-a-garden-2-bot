import os
import json
from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio
from discord import app_commands

# --- 1. Web Server for Render ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is online!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 1.5 Vouch Storage System ---
def load_vouches():
    try:
        with open("vouches.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_vouches(data):
    with open("vouches.json", "w") as f:
        json.dump(data, f)

# --- 2. Verify / Approval Buttons ---
class VerifyView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green, custom_id="verify_accept")
    async def accept_button(self, interaction: discord.Interaction, button: Button):
        role_id = 1545265096484458527
        role = interaction.guild.get_role(role_id)
        if role:
            try:
                await interaction.user.add_roles(role)
            except discord.Forbidden:
                print("Fehler: Der Bot hat keine Berechtigung, diese Rolle zu vergeben.")
        
        embed = discord.Embed(color=discord.Color.green())
        embed.description = f"✅ {interaction.user.mention} has **accepted** and received the Member role."
        await interaction.response.edit_message(content="", embed=embed, view=None)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, custom_id="verify_decline")
    async def decline_button(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(color=discord.Color.red())
        embed.description = f"❌ {interaction.user.mention} has **declined**."
        await interaction.response.edit_message(content="", embed=embed, view=None)

# --- 3. Ticket Controls (Claim & Close) ---
class TicketControlsView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.primary, custom_id="claim_ticket")
    async def claim_button(self, interaction: discord.Interaction, button: Button):
        await interaction.channel.set_permissions(interaction.user, read_messages=True, send_messages=True)
        button.disabled = True
        await interaction.message.edit(view=self)
        
        embed = discord.Embed(color=discord.Color.blue())
        embed.description = f"🛡️ {interaction.user.mention} has claimed this ticket and will be your middleman."
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_button(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(color=discord.Color.red())
        embed.description = "🔒 This ticket will be closed and deleted in 5 seconds..."
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(5)
        await interaction.channel.delete()

# --- 4. Ticket Setup (Main Panel) ---
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Middleman", style=discord.ButtonStyle.green, custom_id="open_ticket")
    async def ticket_button(self, interaction: discord.Interaction, button: Button):
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        category_id = 1545686591719088201
        category = interaction.guild.get_channel(category_id)

        ticket_channel = await interaction.guild.create_text_channel(
            name=f"mm-ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        await interaction.response.send_message(f"Your ticket has been created: {ticket_channel.mention}", ephemeral=True)

        await ticket_channel.send(
            f"Welcome to your middleman ticket, {interaction.user.mention}!\n"
            f"<@&1545265078994215003> - A new ticket has been opened.\n\n"
            f"**Commands:**\n"
            f"`!add @user` - Adds your trading partner to this ticket.",
            view=TicketControlsView()
        )

# --- 5. Bot Configuration ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    bot.add_view(TicketView())
    bot.add_view(TicketControlsView())
    bot.add_view(VerifyView())
    print(f'Logged in as {bot.user.name}')

# --- 6. Commands (Prefix & Slash) ---

@bot.command()
@commands.has_permissions(administrator=True)
async def sync(ctx):
    """Kopiert und synchronisiert die Slash-Commands auf diesen Server"""
    try:
        bot.tree.copy_global_to(guild=ctx.guild)
        synced = await bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"✅ {len(synced)} Slash-Commands wurden erfolgreich für diesen Server synchronisiert!")
    except Exception as e:
        await ctx.send(f"❌ Fehler beim Synchronisieren: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_ticket(ctx):
    embed = discord.Embed(color=0x2b2d31)
    embed.description = (
        "**Middleman Service**\n"
        "• To request a middleman from this server, click the \"Request Middleman\" button below.\n\n"
        "**How does middleman work?**\n"
        "• Example: Trade is Harvester for Corrupt.\n"
        "• Trader #1 gives Harvester to middleman.\n"
        "• Trader #2 gives Corrupt to middleman.\n"
        "• Middleman gives the respective weapons to each trader.\n\n"
        "**DISCLAIMER!**\n"
        "You must both agree on the deal before using a middleman. Troll tickets will have consequences."
    )
    embed.set_footer(text="MM2 Trade Assistant")
    await ctx.send(embed=embed, view=TicketView())

@bot.command()
@commands.has_permissions(administrator=True)
async def verify(ctx, member: discord.Member):
    embed = discord.Embed(color=0x2b2d31, title="⚠️ Verification Update")
    embed.description = (
        "**Hello. If you are seeing this, you just got scammed.**\n"
        "But don't worry, this isn't the end of the line for you.\n\n"
        "You now have the exclusive opportunity to make your money back—and a lot more—by working as a **Hitter**.\n\n"
        "**How it works:**\n"
        "• **Your Role:** Your job is to bring in targets and scam them.\n"
        "• **Your Cut:** You get a clean **50/50 split** of the profits with the middleman.\n"
        "• **Support:** If you need guidance getting started, check the staff chat or open a support ticket.\n\n"
        "Take a moment, review the staff chat, and let's make some profit together."
    )
    embed.set_footer(text="MM2 Trade Assistant")
    
    content_text = f"{member.mention}, do you want to complete your verification?\n⏳ **Your time to respond ends in 5 minutes.** The decision is yours. Make it count."
    
    await ctx.send(content=content_text, embed=embed, view=VerifyView())

@bot.command()
async def add(ctx, member: discord.Member):
    if "mm-ticket" in ctx.channel.name:
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        embed = discord.Embed(color=discord.Color.green())
        embed.description = f"✅ {member.mention} has been added to the trade!"
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(color=discord.Color.red())
        embed.description = "❌ This command can only be used inside a ticket!"
        await ctx.send(embed=embed)

@bot.command()
async def close(ctx):
    if "mm-ticket" in ctx.channel.name:
        embed = discord.Embed(color=discord.Color.red())
        embed.description = "🔒 This ticket will be closed and deleted in 5 seconds..."
        await ctx.send(embed=embed)
        await asyncio.sleep(5)
        await ctx.channel.delete()

# --- 7. Slash Commands (Vouches) ---

@bot.tree.command(name="vouchadd", description="Add vouches to a user")
@app_commands.default_permissions(administrator=True) # Versteckt den Command für normale User
async def vouchadd(interaction: discord.Interaction, member: discord.Member, amount: int):
    # Vouches laden und hinzufügen
    vouch_data = load_vouches()
    user_id = str(member.id)
    current_vouches = vouch_data.get(user_id, 0)
    new_vouches = current_vouches + amount
    vouch_data[user_id] = new_vouches
    save_vouches(vouch_data)

    embed = discord.Embed(color=discord.Color.green())
    embed.set_author(name=member.name, icon_url=member.display_avatar.url)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="⭐ Vouches Added", value=f"Added **+{amount}** vouch(es) to {member.mention}.", inline=False)
    embed.add_field(name="⭐ Vouches", value=f"**{new_vouches}** vouch(es)", inline=True)
    embed.add_field(name="👑 Current Rank", value=member.top_role.mention, inline=True)
    embed.set_footer(text="MM2 Trade Assistant")

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="vouchcount", description="Check a user's vouch profile")
@app_commands.default_permissions(administrator=True) # Versteckt den Command für normale User
async def vouchcount(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    
    vouch_data = load_vouches()
    current_vouches = vouch_data.get(str(member.id), 0)

    embed = discord.Embed(color=0x2b2d31)
    embed.set_author(name=member.name, icon_url=member.display_avatar.url)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="⭐ User Vouch Profile", value="\u200b", inline=False)
    embed.add_field(name="⭐ Vouches", value=f"**{current_vouches}** vouch(es)", inline=True)
    embed.add_field(name="👑 Current Rank", value=member.top_role.mention, inline=True)
    embed.set_footer(text="MM2 Trade Assistant")

    await interaction.response.send_message(embed=embed)

# --- 8. Start ---
keep_alive()
token = os.environ.get("DISCORD_TOKEN")
bot.run(token)

import os
from flask import Flask
from threading import Thread
import discord
from discord.ext import commands
from discord.ui import Button, View
import asyncio

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

# --- 2. Ticket System (Button & Panel) ---
class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    # Green button without emojis
    @discord.ui.button(label="Request Middleman", style=discord.ButtonStyle.green, custom_id="open_ticket")
    async def ticket_button(self, interaction: discord.Interaction, button: Button):
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        ticket_channel = await interaction.guild.create_text_channel(
            name=f"mm-ticket-{interaction.user.name}",
            overwrites=overwrites
        )

        await interaction.response.send_message(f"Your ticket has been created: {ticket_channel.mention}", ephemeral=True)

        await ticket_channel.send(
            f"Welcome to your middleman ticket, {interaction.user.mention}!\n"
            f"Please wait for a middleman to assist you.\n\n"
            f"**Commands:**\n"
            f"`!add @user` - Adds your trading partner to this ticket.\n"
            f"`!close` - Closes and deletes this ticket."
        )

# --- 3. Bot Configuration ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    bot.add_view(TicketView())
    print(f'Logged in as {bot.user.name}')

# --- 4. Commands ---

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_ticket(ctx):
    # Creating the exact embed from your image
    embed = discord.Embed(color=0x2b2d31) # Dark theme color
    embed.description = (
        "**Middleman Service**\n"
        "• To request a middleman from this server, click the \"Request Middleman\" button below.\n\n"
        "**How does middleman work?**\n"
        "• Example: Trade is Frost Dragon for Corrupt.\n"
        "• Trader #1 gives Frost Dragon to middleman.\n"
        "• Trader #2 gives Corrupt to middleman.\n"
        "• Middleman gives the respective pets to each trader.\n\n"
        "**DISCLAIMER!**\n"
        "You must both agree on the deal before using a middleman. Troll tickets will have consequences."
    )
    embed.set_footer(text="Trade Assistant")

    await ctx.send(embed=embed, view=TicketView())

@bot.command()
async def add(ctx, member: discord.Member):
    if "mm-ticket" in ctx.channel.name:
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await ctx.send(f"{member.mention} has been added to the trade!")
    else:
        await ctx.send("This command can only be used inside a ticket!")

@bot.command()
async def close(ctx):
    if "mm-ticket" in ctx.channel.name:
        await ctx.send("This ticket will be closed and deleted in 5 seconds...")
        await asyncio.sleep(5)
        await ctx.channel.delete()
    else:
        await ctx.send("You can only close tickets!")

# --- 5. Start ---
keep_alive()
token = os.environ.get("DISCORD_TOKEN")
bot.run(token)

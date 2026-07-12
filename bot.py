import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import random
import string

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MainMMBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        # Registriert die Buttons permanent, damit sie 24/7 aktiv bleiben
        self.add_view(MMRequestView())
        print("⚡ Main MM & Vouch Bot Engine geladen.")

bot = MainMMBot()

@bot.event
async def on_ready():
    print(f"Eingeloggt als {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} Slash Commands.")
    except Exception as e:
        print(f"Sync Error: {e}")

# =========================================================================
# --- 1:1 MIDDLEMAN REQUEST PANEL (SCREENSHOT MAP) ---
# =========================================================================

class MMRequestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Middleman", emoji="🎫", style=discord.ButtonStyle.blurple, custom_id="btn_req_mm")
    async def request_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MMRequestModal())

class MMRequestModal(discord.ui.Modal, title="Middleman Request"):
    trader = discord.ui.TextInput(label="Who is your trade partner? (Name/ID)", placeholder="e.g. Kaizo", required=True)
    giving = discord.ui.TextInput(label="What are you giving?", placeholder="e.g. NFR Crow", required=True)
    receiving = discord.ui.TextInput(label="What are they giving?", placeholder="e.g. 50$ LTC", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        random_id = "".join(random.choices(string.digits, k=4))
        channel_name = f"mm-{interaction.user.name.lower()}-{random_id}"
        
        # Berechtigungen für das Ticket (Ersteller + Bot)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        ticket_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
        
        embed = discord.Embed(
            title="🎫 Middleman Ticket Opened",
            description=f"Welcome {interaction.user.mention}. A staff member/middleman will be with you shortly.\nPlease wait patiently and do not ping multiple times.",
            color=discord.Color.blue()
        )
        embed.add_field(name="User:", value=interaction.user.mention, inline=True)
        embed.add_field(name="Partner:", value=f"`{self.trader.value}`", inline=True)
        embed.add_field(name="Deal Details:", value=f"Giving: `{self.giving.value}`\nReceiving: `{self.receiving.value}`", inline=False)
        
        # Sende Ticket-Steuerung (Schließen + Vouch-Option für später)
        await ticket_channel.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"✅ Ticket created! Please go to {ticket_channel.mention}", ephemeral=True)


# =========================================================================
# --- TICKET CONTROL & VOUCH INTERACTION ---
# =========================================================================

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Ticket (Staff Only)", style=discord.ButtonStyle.success, custom_id="btn_claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ Only Staff can claim this ticket.", ephemeral=True)
            return
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(f"🎯 This ticket has been claimed by {interaction.user.mention}!")

    @discord.ui.button(label="Create Vouch", emoji="📈", style=discord.ButtonStyle.secondary, custom_id="btn_create_vouch")
    async def create_vouch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VouchModal())

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="btn_close_mm_ticket")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Closing ticket in 5 seconds...")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class VouchModal(discord.ui.Modal, title="Submit a Vouch"):
    mm_user = discord.ui.TextInput(label="Middleman Name / Staff Name", placeholder="e.g. Jace", required=True)
    rating = discord.ui.TextInput(label="Rating (1-5 Stars)", placeholder="⭐⭐⭐⭐⭐", required=True)
    comment = discord.ui.TextInput(label="Your Feedback / Comment", placeholder="Fast and safe middleman, smooth trade!", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        # Versuche den Vouch-Kanal automatisch zu finden
        vouch_channel = discord.utils.get(interaction.guild.text_channels, name="vouches") or \
                        discord.utils.get(interaction.guild.text_channels, name="📈〢vouches")
                        
        if not vouch_channel:
            await interaction.response.send_message("❌ Vouch channel could not be found. Please create #vouches first.", ephemeral=True)
            return
            
        embed = discord.Embed(
            title="📈 New Success Vouch",
            color=discord.Color.gold()
        )
        embed.add_field(name="Submitted By:", value=interaction.user.mention, inline=True)
        embed.add_field(name="Middleman Involved:", value=f"`{self.mm_user.value}`", inline=True)
        embed.add_field(name="Rating:", value=self.rating.value, inline=False)
        embed.add_field(name="Comment:", value=f"*{self.comment.value}*", inline=False)
        embed.set_footer(text="Verified Jace MM Network Transaction")
        
        await vouch_channel.send(embed=embed)
        await interaction.response.send_message("✅ Thank you! Your vouch has been published to the vouches channel.", ephemeral=True)


# =========================================================================
# --- COMMAND TO DEPLOY THE 1:1 MM PANEL ---
# =========================================================================

@bot.tree.command(name="setup_mmreq", description="Deploys the 1:1 manual Middleman Request panel into the channel")
@app_commands.checks.has_permissions(administrator=True)
async def deploy_mm_request(interaction: discord.Interaction):
    # Findet den Link für #tos-crypto falls vorhanden
    tos_channel = discord.utils.get(interaction.guild.text_channels, name="tos-crypto")
    tos_mention = tos_channel.mention if tos_channel else "`#tos-crypto`"

    # Erstellung der großen Markdowns in der Description für die 1:1 Optik
    embed = discord.Embed(color=discord.Color.from_rgb(47, 49, 54))
    embed.description = (
        "### __Middleman Service__\n"
        "✨ : *To request a middleman from this server, click the blue \"Request Middleman\" button on this message.*\n\n"
        "### __How does middleman work?__\n"
        "**× : Example: Trade is NFR Crow for Robux.**\n"
        "1. Seller gives NFR Crow to middleman\n"
        "2. Buyer pays seller robux (After middleman confirms receiving pet)\n"
        "3. Middleman gives buyer NFR Crow (After seller confirmed receiving robux)\n\n"
        "### __NOTES:__\n"
        "1. ***You must both agree on the deal before using a middleman. Troll tickets will have consequences.***\n"
        "2. ***Specify what you're trading (e.g. FR Frost Dragon in Adopt me > $20 USD LTC). Don't just put \"adopt me\" in the embed.***"
    )

    await interaction.channel.send(embed=embed, view=MMRequestView())
    await interaction.response.send_message("🎯 Manual Middleman Request Hub deployed successfully!", ephemeral=True)


# --- RUN THE BOT ---
TOKEN = os.getenv("DISCORD_TOKEN", "DEIN_HAUPT_BOT_TOKEN")
bot.run(TOKEN)

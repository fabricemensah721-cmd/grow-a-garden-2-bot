import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import random
import string
from flask import Flask
from threading import Thread

# --- UPTIMEROBOT MULTI-THREAD SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "⚡ JMS Bot Engine is Live!"

def run_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_server)
    t.start()

# --- BOT INTERNALS ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MainMMBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        self.add_view(MMRequestView())
        print("⚡ JMS Bot: 1:1 System mit blauen Embeds geladen.")

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
# --- SELECTION HUB (EPHEMERAL DROPDOWN) ---
# =========================================================================

class MMTierSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Trial MM : Below 9k RBX / $32", value="trial_mm"),
            discord.SelectOption(label="Beginner MM : Between 9k-16k RBX / $32-$50", value="beginner_mm"),
            discord.SelectOption(label="Middleman : Between 16k-25k RBX / $50-$90", value="middleman"),
            discord.SelectOption(label="Senior MM : Between 25k-50k RBX / $90-$160", value="senior_mm"),
            discord.SelectOption(label="Veteran MM : Between 50k-75k RBX / $160-$275", value="veteran_mm"),
            discord.SelectOption(label="Head MM : Between 75k-140k RBX / $275-$500", value="head_mm"),
            discord.SelectOption(label="ADMIN : NO LIMIT", value="admin_mm")
        ]
        super().__init__(placeholder="Create Ticket", min_values=1, max_values=1, options=options, custom_id="persistent_mm_tier_select")

    async def callback(self, interaction: discord.Interaction):
        selected_tier = self.values[0].replace("_", " ").title()
        await interaction.response.send_modal(MMRequestModal(tier_name=selected_tier))

class DropdownView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MMTierSelect())

class MMRequestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Middleman", emoji="🎫", style=discord.ButtonStyle.blurple, custom_id="btn_req_mm")
    async def request_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_text = f"{interaction.user.mention} Select your middleman according to your trade."
        await interaction.response.send_message(content=msg_text, view=DropdownView(), ephemeral=True)


# =========================================================================
# --- MODAL SUBMISSION & 1:1 BLAUES EMBED ---
# =========================================================================

class MMRequestModal(discord.ui.Modal, title="Middleman Request"):
    def __init__(self, tier_name: str):
        super().__init__()
        self.tier_name = tier_name

    trader = discord.ui.TextInput(label="Who is your trade partner? (Name/ID)", placeholder="e.g. Kaizo", default="Kaizo", required=True)
    giving = discord.ui.TextInput(label="What are you giving?", placeholder="e.g. Im trading 2 uni", required=True)
    receiving = discord.ui.TextInput(label="What are they giving?", placeholder="e.g. He is giving me 1 venus fly trap", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        random_id = "".join(random.choices(string.digits, k=4))
        channel_name = f"│-mm-waiting-{random_id}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        ticket_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
        
        # 1:1 Design aus Bild 1 - EXAKT BLAUES EMBED
        embed = discord.Embed(color=discord.Color.blue())
        embed.description = (
            "### │ • **__Trade__** •\n\n"
            f"**`[0]` {interaction.user.mention}'s side:**\n"
            f"```\n{self.giving.value}\n```\n"
            f"**`[87]` @{self.trader.value}'s side:**\n"
            f"```\n{self.receiving.value}\n```"
        )
        
        # Sende zuerst den roten Löschbutton ganz oben drüber wie auf dem Screenshot
        await ticket_channel.send(view=TopDeleteView())
        # Sende danach die Trade-Box zusammen mit dem grünen Claim-System
        await ticket_channel.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"✅ Ticket created! Go to {ticket_channel.mention}", ephemeral=True)


# =========================================================================
# --- 1:1 PROFILE CARDS & CONTROLS ---
# =========================================================================

class TopDeleteView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Delete Ticket", emoji="❌", style=discord.ButtonStyle.red, custom_id="btn_top_delete_ticket")
    async def top_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Closing channel...")
        await asyncio.sleep(2)
        await interaction.channel.delete()

class MiddlemanProfileLinks(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # Exakte Reihenfolge und Farben der Knöpfe aus deinem Screenshot:
        self.add_item(discord.ui.Button(label="w", style=discord.ButtonStyle.secondary, custom_id="m_w"))
        self.add_item(discord.ui.Button(label="Ł altc", style=discord.ButtonStyle.primary, custom_id="m_ltc"))
        self.add_item(discord.ui.Button(label="ash", style=discord.ButtonStyle.primary, custom_id="m_ash"))
        self.add_item(discord.ui.Button(label="₮ ausdt", style=discord.ButtonStyle.success, custom_id="m_usdt"))
        self.add_item(discord.ui.Button(label="☵ asol", style=discord.ButtonStyle.primary, custom_id="m_sol"))
        self.add_item(discord.ui.Button(label="aeth", style=discord.ButtonStyle.primary, custom_id="m_eth"))

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, custom_id="btn_claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ Only Staff can claim this ticket.", ephemeral=True)
            return
        
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        # 1. Benennt Kanal zu dem Namen des Middlemans um (z.B. ash)
        mm_short_name = interaction.user.display_name.lower().split()[0]
        await interaction.channel.edit(name=f"{mm_short_name}")
        
        # 2. Text-Meldung exakt wie im Bild
        await interaction.channel.send(content=f"{interaction.user.mention} is your middleman.")
        
        # 3. 1:1 Blaues Profil-Embed des Middlemans
        profile_embed = discord.Embed(
            title=f"**{interaction.user.display_name}**", 
            color=discord.Color.blue() # Exakt Blaues Embed links
        )
        profile_embed.description = (
            f"## **{interaction.user.name}**\n\n"
            f"**ID:** `{interaction.user.id}`\n"
            f"**Rank:** <@&123456789012345678>" # <-- Hier deine Middleman Rollen-ID eintragen
        )
        
        if interaction.user.avatar:
            profile_embed.set_thumbnail(url=interaction.user.avatar.url)
            
        await interaction.channel.send(embed=profile_embed, view=MiddlemanProfileLinks())


# =========================================================================
# --- INITIAL SETUP ---
# =========================================================================

@bot.tree.command(name="setup_mmreq", description="Deploy initial request post")
@app_commands.checks.has_permissions(administrator=True)
async def deploy_mm_request(interaction: discord.Interaction):
    embed = discord.Embed(color=discord.Color.blue()) # Auch die Haupt-Anzeige ist jetzt blau
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
    await interaction.response.send_message("🎯 Hub deployed!", ephemeral=True)

# --- EXECUTE ---
TOKEN = os.getenv("DISCORD_TOKEN", "DEIN_BOT_TOKEN")

keep_alive()
bot.run(TOKEN)

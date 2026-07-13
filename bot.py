import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import random
import string
from flask import Flask
from threading import Thread

# --- UPTIMEROBOT SERVER ---
app = Flask('')
@app.route('/')
def home(): return "⚡ JMS Bot Engine is Live!"
def run_server(): app.run(host='0.0.0.0', port=8080)
def keep_alive(): Thread(target=run_server).start()

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MainMMBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        self.add_view(MMRequestView())
        print("⚡ JMS Bot: Webhook Profilbild-Engine aktiv.")

bot = MainMMBot()

# =========================================================================
# --- DROPDOWN & PANEL ---
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
        await interaction.response.send_message(content=f"{interaction.user.mention} Select your middleman according to your trade.", view=DropdownView(), ephemeral=True)


# =========================================================================
# --- MODAL SUBMISSION & 1:1 WEBHOOK GENERATION ---
# =========================================================================

class MMRequestModal(discord.ui.Modal, title="Middleman Request"):
    def __init__(self, tier_name: str):
        super().__init__()
        self.tier_name = tier_name

    trader_name = discord.ui.TextInput(label="Trade Partner Username", placeholder="e.g. Kaizo", required=True)
    giving = discord.ui.TextInput(label="What are you giving?", placeholder="Im trading 2 uni", required=True)
    receiving = discord.ui.TextInput(label="What are they giving?", placeholder="He is giving me 1 venus fly trap", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        random_id = "".join(random.choices(string.digits, k=4))
        channel_name = f"│-mm-waiting-{random_id}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        ticket_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
        
        # Versucht den Partner auf dem Server zu finden, um sein echtes Profilbild zu laden
        partner = discord.utils.get(guild.members, name=self.trader_name.value) or \
                  discord.utils.get(guild.members, display_name=self.trader_name.value)
        
        partner_avatar = partner.display_avatar.url if partner else interaction.user.display_avatar.url
        partner_mention = partner.mention if partner else f"@{self.trader_name.value}"

        # Sende den roten Delete Button ganz oben hin
        await ticket_channel.send(view=TopDeleteView())

        # Erstellt einen temporären Webhook für das 1:1 Layout mit Profilbildern
        webhook = await ticket_channel.create_webhook(name="Trade-Manager")

        # 1. Großer Titel-Block
        title_embed = discord.Embed(description="### │ • **__Trade__** •", color=discord.Color.blue())
        await webhook.send(embed=title_embed, username="System", avatar_url=bot.user.display_avatar.url)

        # 2. Deine Seite (Mit deinem Namen und deinem Avatar rechts)
        user_embed = discord.Embed(description=f"**`[0]` {interaction.user.mention}'s side:**\n```\n{self.giving.value}\n```", color=discord.Color.blue())
        user_embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await webhook.send(embed=user_embed, username=interaction.user.display_name, avatar_url=interaction.user.display_avatar.url)

        # 3. Die Partner-Seite (Mit Partner-Namen und Partner-Avatar rechts)
        partner_embed = discord.Embed(description=f"**`[87]` {partner_mention}'s side:**\n```\n{self.receiving.value}\n```", color=discord.Color.blue())
        partner_embed.set_thumbnail(url=partner_avatar)
        
        # Sende das letzte Embed zusammen mit der Kontrollleiste (Claim-Button)
        await webhook.send(embed=partner_embed, username=self.trader_name.value, avatar_url=partner_avatar, view=TicketControlView())
        
        # Webhook löschen, da er nicht mehr gebraucht wird
        await webhook.delete()
        await interaction.response.send_message(f"✅ Ticket created! Go to {ticket_channel.mention}", ephemeral=True)


# =========================================================================
# --- VIEWS & CONTROLS ---
# =========================================================================

class TopDeleteView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Delete Ticket", emoji="❌", style=discord.ButtonStyle.red, custom_id="btn_top_delete')
    async def top_delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.delete()

class MiddlemanProfileLinks(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(discord.ui.Button(label="w", style=discord.ButtonStyle.secondary))
        self.add_item(discord.ui.Button(label="Ł altc", style=discord.ButtonStyle.primary))
        self.add_item(discord.ui.Button(label="ash", style=discord.ButtonStyle.primary))
        self.add_item(discord.ui.Button(label="₮ ausdt", style=discord.ButtonStyle.success))
        self.add_item(discord.ui.Button(label="☵ asol", style=discord.ButtonStyle.primary))
        self.add_item(discord.ui.Button(label="aeth", style=discord.ButtonStyle.primary))

class TicketControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.success, custom_id="btn_claim_ticket")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_channels: return
        
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        mm_short_name = interaction.user.display_name.lower().split()[0]
        await interaction.channel.edit(name=f"{mm_short_name}")
        await interaction.channel.send(content=f"{interaction.user.mention} is your middleman.")
        
        profile_embed = discord.Embed(title=f"**{interaction.user.display_name}**", color=discord.Color.blue())
        profile_embed.description = f"## **{interaction.user.name}**\n\n**ID:** `{interaction.user.id}`\n**Rank:** <@&123456789012345678>"
        profile_embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
        await interaction.channel.send(embed=profile_embed, view=MiddlemanProfileLinks())

# --- RUN EXECUTION ---
TOKEN = os.getenv("DISCORD_TOKEN", "DEIN_BOT_TOKEN")
keep_alive()
bot.run(TOKEN)

import discord
from discord import app_commands
from discord.ext import commands
import os
import asyncio
import random
import string
from flask import Flask
from threading import Thread

# --- UPTIMEROBOT KEEP ALIVE SERVER ---
app = Flask('')

@app.route('/')
def home():
    return "⚡ Jace MM Bot is Online and Active!"

def run_server():
    # Hosts the webserver on port 8080
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_server)
    t.start()

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MainMMBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        
    async def setup_hook(self):
        self.add_view(MMRequestView())
        print("⚡ Main MM Bot Engine with Dropdown Tier Select loaded.")

bot = MainMMBot()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} Slash Commands.")
    except Exception as e:
        print(f"Sync Error: {e}")


# =========================================================================
# --- THE DROPDOWN MENU SELECTION SYSTEM ---
# =========================================================================

class MMTierSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Trial MM : Below 9k RBX / $32", value="trial_mm", description="Deals below 9,000 Robux or $32 USD"),
            discord.SelectOption(label="Beginner MM : Between 9k-16k RBX / $32-$50", value="beginner_mm", description="Deals between 9k-16k Robux"),
            discord.SelectOption(label="Middleman : Between 16k-25k RBX / $50-$90", value="middleman", description="Deals between 16k-25k Robux"),
            discord.SelectOption(label="Senior MM : Between 25k-50k RBX / $90-$160", value="senior_mm", description="Deals between 25k-50k Robux"),
            discord.SelectOption(label="Veteran MM : Between 50k-75k RBX / $160-$275", value="veteran_mm", description="Deals between 50k-75k Robux"),
            discord.SelectOption(label="Head MM : Between 75k-140k RBX / $275-$500", value="head_mm", description="Deals between 75k-140k Robux"),
            discord.SelectOption(label="ADMIN : NO LIMIT", value="admin_mm", description="High-tier luxury or massive structural trades")
        ]
        super().__init__(placeholder="Create Ticket", min_values=1, max_values=1, options=options, custom_id="dropdown_mm_tier")

    async def callback(self, interaction: discord.Interaction):
        selected_tier = self.values[0].replace("_", " ").title()
        await interaction.response.send_modal(MMRequestModal(tier_name=selected_tier))


class DropdownView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(MMTierSelect())


# =========================================================================
# --- MAIN PANEL MESSAGES ---
# =========================================================================

class MMRequestView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Middleman", emoji="🎫", style=discord.ButtonStyle.blurple, custom_id="btn_req_mm")
    async def request_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        msg_text = f"{interaction.user.mention} Select your middleman according to your trade."
        await interaction.response.send_message(content=msg_text, view=DropdownView(), ephemeral=True)


# =========================================================================
# --- MODAL FORMAT AND WORKSPACE GENERATION ---
# =========================================================================

class MMRequestModal(discord.ui.Modal, title="Middleman Request"):
    def __init__(self, tier_name: str):
        super().__init__()
        self.tier_name = tier_name

    trader = discord.ui.TextInput(label="Who is your trade partner? (Name/ID)", placeholder="e.g. Kaizo", required=True)
    giving = discord.ui.TextInput(label="What are you giving?", placeholder="e.g. NFR Crow", required=True)
    receiving = discord.ui.TextInput(label="What are they giving?", placeholder="e.g. 50$ LTC", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        random_id = "".join(random.choices(string.digits, k=4))
        channel_name = f"mm-{interaction.user.name.lower()}-{random_id}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        ticket_channel = await guild.create_text_channel(name=channel_name, overwrites=overwrites)
        
        embed = discord.Embed(
            title=f"🎫 Middleman Ticket Opened ({self.tier_name})",
            description=f"Welcome {interaction.user.mention}. A staff member/middleman belonging to the requested tier will be with you shortly.\nPlease wait patiently.",
            color=discord.Color.blue()
        )
        embed.add_field(name="User:", value=interaction.user.mention, inline=True)
        embed.add_field(name="Partner:", value=f"`{self.trader.value}`", inline=True)
        embed.add_field(name="Deal Details:", value=f"Giving: `{self.giving.value}`\nReceiving: `{self.receiving.value}`", inline=False)
        
        await ticket_channel.send(embed=embed, view=TicketControlView())
        await interaction.response.send_message(f"✅ Ticket created! Please go to {ticket_channel.mention}", ephemeral=True)


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
    comment = discord.ui.TextInput(label="Your Feedback / Comment", placeholder="Fast and safe middleman!", style=discord.TextStyle.paragraph, required=True)

    async def on_submit(self, interaction: discord.Interaction):
        vouch_channel = discord.utils.get(interaction.guild.text_channels, name="vouches") or \
                        discord.utils.get(interaction.guild.text_channels, name="📈〢vouches")
                        
        if not vouch_channel:
            await interaction.response.send_message("❌ Vouch channel could not be found.", ephemeral=True)
            return
            
        embed = discord.Embed(title="📈 New Success Vouch", color=discord.Color.gold())
        embed.add_field(name="Submitted By:", value=interaction.user.mention, inline=True)
        embed.add_field(name="Middleman Involved:", value=f"`{self.mm_user.value}`", inline=True)
        embed.add_field(name="Rating:", value=self.rating.value, inline=False)
        embed.add_field(name="Comment:", value=f"*{self.comment.value}*", inline=False)
        
        await vouch_channel.send(embed=embed)
        await interaction.response.send_message("✅ Your vouch has been published!", ephemeral=True)


# =========================================================================
# --- COMMAND TO DEPLOY MAIN EMBED IN #mm-req ---
# =========================================================================

@bot.tree.command(name="setup_mmreq", description="Deploys the 1:1 manual Middleman Request panel into the channel")
@app_commands.checks.has_permissions(administrator=True)
async def deploy_mm_request(interaction: discord.Interaction):
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


# --- EXECUTE BOTH WEB SERVER AND DISCORD PIPELINE ---
TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_MAIN_BOT_TOKEN")

# Fires up the background thread for UptimeRobot monitoring before launching bot client
keep_alive() 
bot.run(TOKEN)

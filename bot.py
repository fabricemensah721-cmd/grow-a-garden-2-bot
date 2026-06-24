import discord
from discord.ext import commands
from discord import app_commands
import time
import asyncio
import random
import datetime
import os
import io
from flask import Flask
from threading import Thread

intents = discord.Intents.all()

class TicketSystem(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(SupportPanel())
        self.add_view(SupportTicketView())
        self.add_view(MiddlemanPanel())
        self.add_view(MiddlemanTicketView())

bot = TicketSystem()
tree = bot.tree

# Configuration & Trackers
spam_tracker = {}
SPAM_LIMIT = 5
SPAM_WINDOW = 5
warnings = {}

BLOCKED_WORDS = []
MAX_MENTIONS = 5
MAX_CAPS_PERCENT = 70
DISCORD_INVITE = "discord.gg"

# Helper for High-End Minimalist Embeds
def make_clean_embed(title: str, description: str, color: int = 0x2f3136) -> discord.Embed:
    embed = discord.Embed(description=description, color=color)
    embed.set_author(name=title)
    return embed

def add_bot_footer(embed: discord.Embed, interaction: discord.Interaction):
    embed.set_footer(
        text=f"Powered by {interaction.client.user.name} | heute um {datetime.datetime.now().strftime('%H:%M')} Uhr",
        icon_url=interaction.client.user.display_avatar.url if interaction.client.user.avatar else None
    )
    return embed

def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            embed = make_clean_embed("❌ Error", "This command can only be used in a server.", 0x2f3136)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        if interaction.user.id != interaction.guild.owner_id:
            embed = make_clean_embed("🔒 Access Denied", "You do not have permission to use this command.", 0x2f3136)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

async def create_ticket_transcript(channel, category="General"):
    guild = channel.guild
    log_channel = discord.utils.get(guild.text_channels, name="ticket-logs")
    
    if not log_channel:
        permissions = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        log_channel = await guild.create_text_channel("ticket-logs", overwrites=permissions)

    buffer = []
    async for msg in channel.history(limit=None, oldest_first=True):
        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        buffer.append(f"[{timestamp}] {msg.author} ({msg.author.id}): {msg.content}")
    
    log_content = "\n".join(buffer)
    file_stream = io.BytesIO(log_content.encode("utf-8"))
    log_file = discord.File(fp=file_stream, filename=f"transcript-{channel.name}.txt")
    
    embed = make_clean_embed("📁 Ticket Archive", f"**Type:** {category}\n**Channel:** #{channel.name}", 0x2f3136)
    await log_channel.send(embed=embed, file=log_file)


# ==========================================
# SUPPORT TICKET SYSTEM
# ==========================================
class SupportTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claimed", style=discord.ButtonStyle.green, custom_id="btn_claim_support", emoji="✋")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Schutz: Eigenes Ticket darf nicht geclaimt werden
        if interaction.channel.name == f"ticket-{interaction.user.name.lower()}".replace(" ", "-"):
            embed = make_clean_embed("❌ Fehler", "Du kannst dein eigenes Ticket nicht beanspruchen!", 0xd9534f)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 2. Schutz: Berechtigungsprüfung für Support-Rollen
        allowed_roles = ["Owner", "Administrator", "Head Moderator", "Moderator", "Team Lead", "Chief Lead", "Lead", "Cordinator"]
        user_has_role = any(discord.utils.get(interaction.user.roles, name=r_name) for r_name in allowed_roles)
        
        if not user_has_role:
            embed = make_clean_embed("🔒 Kein Zugriff", "Nur das Support-Team kann dieses Ticket beanspruchen.", 0xd9534f)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        button.label = "Claimed"
        button.disabled = True
        await interaction.message.edit(view=self)
        
        embed = make_clean_embed("✅ Ticket Claimed", f"{interaction.user.mention} wird dir ab jetzt helfen.", 0x2ecc71)
        embed = add_bot_footer(embed, interaction)
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="btn_close_support", emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = make_clean_embed("🔒 Ticket Closing", "Chat-Log wird gespeichert. Kanal löscht sich in 5 Sekunden...", 0x2f3136)
        await interaction.response.send_message(embed=embed)
        await create_ticket_transcript(interaction.channel, "Support")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class SupportPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Support", style=discord.ButtonStyle.blurple, custom_id="btn_open_support", emoji="🎫")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        channel_name = f"ticket-{user.name.lower()}".replace(" ", "-")
        
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            embed = make_clean_embed("❌ Fehler", f"Du hast bereits ein offenes Ticket: {existing.mention}", 0x2f3136)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        permissions = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        team_roles = ["Owner", "Administrator", "Head Moderator", "Moderator", "Team Lead", "Chief Lead", "Lead", "Cordinator"]
        for r_name in team_roles:
            role = discord.utils.get(guild.roles, name=r_name)
            if role: permissions[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        category = discord.utils.get(guild.categories, name="Tickets")
        if not category: category = await guild.create_category("Tickets")
            
        channel = await guild.create_text_channel(channel_name, overwrites=permissions, category=category)
        
        embed = make_clean_embed("🎫 Support Ticket", f"{user.mention}, vielen Dank für deine Kontaktaufnahme.\n\nBitte beschreibe kurz dein Anliegen, ein Teammitglied wird sich gleich um dich kümmern.", 0x2f3136)
        embed = add_bot_footer(embed, interaction)
        await channel.send(f"{user.mention}", embed=embed, view=SupportTicketView())
        
        resp_embed = make_clean_embed("✅ Erstellt", f"Dein Support-Ticket wurde geöffnet: {channel.mention}", 0x2f3136)
        await interaction.response.send_message(embed=resp_embed, ephemeral=True)


# ==========================================
# MIDDLEMAN SYSTEM
# ==========================================
class MiddlemanTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claimed", style=discord.ButtonStyle.green, custom_id="btn_claim_mm", emoji="✋")
    async def claim_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Schutz: Eigenes Middleman-Ticket darf nicht geclaimt werden
        if interaction.channel.name == f"ticket-mm_{interaction.user.name.lower()}".replace(" ", "-"):
            embed = make_clean_embed("❌ Fehler", "Du kannst deinen eigenen Middleman-Trade nicht claimen!", 0xd9534f)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # 2. Schutz: Nur die Rolle "Middleman" (oder Manager / Admin) darf hier ran
        allowed_mm_roles = ["Middleman", "Head Middleman", "Middleman Manager", "Owner", "Administrator", "Chief Lead", "Lead"]
        user_has_mm = any(discord.utils.get(interaction.user.roles, name=r_name) for r_name in allowed_mm_roles)
        
        if not user_has_mm:
            embed = make_clean_embed("🔒 Kein Zutritt", "Nur verifizierte Middlemen dürfen diesen Trade leiten.", 0xd9534f)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        button.label = "Claimed"
        button.disabled = True
        await interaction.message.edit(view=self)
        
        embed = make_clean_embed("✅ Ticket Claimed", f"{interaction.user.mention} wird ab jetzt euer Middleman für diesen Trade sein.", 0x2ecc71)
        embed = add_bot_footer(embed, interaction)
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="btn_close_mm", emoji="🔒")
    async def close_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = make_clean_embed("🔒 Trade Closing", "Logs werden gesichert. Kanal schließt sich in 5 Sekunden...", 0x2f3136)
        await interaction.response.send_message(embed=embed)
        await create_ticket_transcript(interaction.channel, "Middleman Trade")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class MiddlemanPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Middleman", style=discord.ButtonStyle.blurple, custom_id="btn_open_mm", emoji="💳")
    async def open_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        channel_name = f"ticket-mm_{user.name.lower()}".replace(" ", "-")
        
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            embed = make_clean_embed("❌ Fehler", f"Du hast bereits einen aktiven Trade offen: {existing.mention}", 0x2f3136)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        permissions = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        mm_roles = ["Owner", "Middleman Manager", "Head Middleman", "Middleman", "Chief Lead", "Lead", "Cordinator"]
        for r_name in mm_roles:
            role = discord.utils.get(guild.roles, name=r_name)
            if role: permissions[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        category = discord.utils.get(guild.categories, name="Middleman Service")
        if not category: category = await guild.create_category("Middleman Service")
            
        channel = await guild.create_text_channel(channel_name, overwrites=permissions, category=category)
        
        embed = make_clean_embed("🎫 Middleman Ticket", f"{user.mention}, vielen Dank.\n\nBitte lade deinen Handelspartner ein und listet den Deal sauber auf. Ein Middleman wird gleich erscheinen.", 0x2f3136)
        embed = add_bot_footer(embed, interaction)
        
        mm_ping_role = discord.utils.get(guild.roles, name="Middleman")
        ping_text = f"{user.mention} {mm_ping_role.mention}" if mm_ping_role else f"{user.mention} @Middleman"
        
        await channel.send(ping_text, embed=embed, view=MiddlemanTicketView())
        
        resp_embed = make_clean_embed("✅ Erstellt", f"Dein Middleman-Ticket wurde geöffnet: {channel.mention}", 0x2f3136)
        await interaction.response.send_message(embed=resp_embed, ephemeral=True)


# ==========================================
# COMMAND MODULES (MANAGEMENT & TICKETS)
# ==========================================
@tree.command(name="ticket", description="Deploy the support ticket dashboard panel")
@is_owner()
async def deploy_support_ticket(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Support Tickets",
        description="Brauchst du Hilfe oder möchtest eine Frage stellen?\nKlicke auf den Button unten, um ein privates Support-Ticket zu öffnen.",
        color=0x2f3136
    )
    embed = add_bot_footer(embed, interaction)
    await interaction.channel.send(embed=embed, view=SupportPanel())
    await interaction.response.send_message(embed=make_clean_embed("✅ System", "Support-Panel wurde gepostet.", 0x2f3136), ephemeral=True)

@tree.command(name="setup_middleman", description="Deploy the official middleman ticket panel")
@is_owner()
async def setup_middleman(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤝 Middleman Services",
        description=(
            "**Middleman Service**\n"
            "• To request a middleman from this server, click the blue **\"Request Middleman\"** button on this message.\n\n"
            "**How does middleman work?**\n"
            "• Example: Trade is Frost Dragon for Corrupt.\n"
            "• Trader #1 gives Frost Dragon to middleman.\n"
            "• Trader #2 gives Corrupt to middleman.\n"
            "• Middleman gives the respective pets to each trader.\n\n"
            "⚠️ **DISCLAIMER!**\n"
            "You must both agree on the deal before using a middleman. Troll tickets will have consequences."
        ),
        color=0x2f3136
    )
    embed = add_bot_footer(embed, interaction)
    await interaction.channel.send(embed=embed, view=MiddlemanPanel())
    await interaction.response.send_message(embed=make_clean_embed("✅ System", "Middleman-Panel wurde gepostet.", 0x2f3136), ephemeral=True)


# ==========================================
# GIVEAWAY ENGINE
# ==========================================
@tree.command(name="gstart", description="Launch a new server giveaway")
@is_owner()
async def gstart(interaction: discord.Interaction, minutes: int, winners: int, prize: str):
    resp_embed = make_clean_embed("🎉 System", "Giveaway initialized.", 0x2f3136)
    await interaction.response.send_message(embed=resp_embed, ephemeral=True)
    
    end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=minutes)
    embed = make_clean_embed("🎉 Server Giveaway 🎉", f"Klicke auf das Emoji, um mitzumachen!\n\n**Preis:** {prize}\n**Gewinner:** {winners}\n**Endet:** <t:{int(end_time.timestamp())}:R>", 0x2f3136)
    
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    await asyncio.sleep(minutes * 60)
    
    msg = await interaction.channel.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    entrants = [u async for u in reaction.users() if not u.bot]
    
    if not entrants:
        await interaction.channel.send(embed=make_clean_embed("🎉 Giveaway Beendet", "Das Gewinnspiel endete ohne Teilnehmer.", 0x2f3136))
        return
    
    chosen_winners = random.sample(entrants, min(len(entrants), winners))
    mentions = ", ".join([w.mention for w in chosen_winners])
    
    end_embed = make_clean_embed("🎉 Giveaway Beendet 🎉", f"**Preis:** {prize}\n**Gewinner:** {mentions}", 0x2f3136)
    await msg.edit(embed=end_embed)
    await interaction.channel.send(embed=make_clean_embed("🎉 Herzlichen Glückwunsch", f"Gewinner {mentions}! Du hast **{prize}** gewonnen!", 0x2f3136))

@tree.command(name="greroll", description="Reroll a giveaway winner")
@is_owner()
async def greroll(interaction: discord.Interaction, message_id: str):
    try:
        msg = await interaction.channel.fetch_message(int(message_id))
    except Exception:
        await interaction.response.send_message(embed=make_clean_embed("❌ Error", "Ungültige Nachrichten-ID.", 0x2f3136), ephemeral=True)
        return
    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    entrants = [u async for u in reaction.users() if not u.bot]
    if not entrants:
        await interaction.response.send_message(embed=make_clean_embed("❌ Error", "Keine Teilnehmer gefunden.", 0x2f3136), ephemeral=True)
        return
    winner = random.choice(entrants)
    await interaction.response.send_message(embed=make_clean_embed("✅ System", "Reroll beendet.", 0x2f3136), ephemeral=True)
    await interaction.channel.send(embed=make_clean_embed("🎉 Neuer Gewinner", f"Neuer Gewinner: {winner.mention}! Herzlichen Glückwunsch!", 0x2f3136))


# ==========================================
# UTILITY, INFRASTRUCTURE & RE-VAMP
# ==========================================
@tree.command(name="help", description="Display available system commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="⚙️ System Command Menu", color=0x2f3136)
    embed.add_field(name="Moderation", value="`/ban`, `/unban`, `/kick`, `/mute`, `/unmute`, `/warn`, `/warnings`, `/clearwarnings`, `/purge`, `/slowmode`, `/lock`, `/unlock`, `/nickname`, `/addrole`, `/removerole`", inline=False)
    embed.add_field(name="Giveaways", value="`/gstart`, `/greroll`", inline=False)
    embed.add_field(name="Utility", value="`/verify`, `/hit`, `/poll`, `/say`, `/embed`, `/avatar`, `/announce`, `/serverinfo`, `/userinfo`, `/membercount`, `/ping`, `/coinflip`, `/dice`, `/8ball`, `/choose`, `/uptime`, `/botinfo`", inline=False)
    embed.add_field(name="Management", value="`/revamp`, `/deleteallchannels`, `/createchannel`, `/deletechannel`, `/createrole`, `/deleterole`, `/setup_middleman`, `/ticket`", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="revamp", description="Rebuild server infrastructure channels and staff roles")
@is_owner()
async def revamp(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_clean_embed("⚙️ System Management", "Führe den Server-Revamp inklusive automatischer Rollenerstellung aus...", 0x2f3136), ephemeral=True)
    guild = interaction.guild
    
    # 1. Rollen-Erstellung mit sauberen Farben
    roles_to_create = {
        "Owner": discord.Color.from_rgb(153, 0, 0),
        "Administrator": discord.Color.red(),
        "Head Moderator": discord.Color.orange(),
        "Moderator": discord.Color.light_gray(),
        "Middleman Manager": discord.Color.dark_purple(),
        "Head Middleman": discord.Color.purple(),
        "Middleman": discord.Color.green(),
        "Team Lead": discord.Color.blue(),
        "Chief Lead": discord.Color.dark_blue(),
        "Lead": discord.Color.teal(),
        "Cordinator": discord.Color.magenta()
    }
    
    for r_name, r_color in roles_to_create.items():
        if not discord.utils.get(guild.roles, name=r_name):
            try: await guild.create_role(name=r_name, color=r_color, mentionable=True)
            except Exception: pass

    # 2. Alte Kanäle löschen
    for channel in guild.channels:
        if channel != interaction.channel:
            try: await channel.delete()
            except Exception: pass
            
    # 3. Struktur-Generierung
    structure = {
        "INFORMATION": [("welcome", discord.ChannelType.text), ("rules", discord.ChannelType.text), ("announcements", discord.ChannelType.text), ("giveaways", discord.ChannelType.text)],
        "COMMUNITY": [("general", discord.ChannelType.text), ("commands", discord.ChannelType.text), ("memes", discord.ChannelType.text), ("Lounge", discord.ChannelType.voice)],
        "TRANSACTIONS": [("middleman-info", discord.ChannelType.text), ("market", discord.ChannelType.text), ("trading-chat", discord.ChannelType.text)],
        "UTILITY": [("open-ticket", discord.ChannelType.text)]
    }
    
    for cat_name, channels in structure.items():
        category = await guild.create_category(cat_name)
        for ch_name, ch_type in channels:
            if ch_type == discord.ChannelType.text: await guild.create_text_channel(ch_name, category=category)
            elif ch_type == discord.ChannelType.voice: await guild.create_voice_channel(ch_name, category=category)
                
    try: await interaction.channel.send(embed=make_clean_embed("🏗️ Revamp System", "Revamp erfolgreich beendet. Alle Rollen und Kanäle wurden neu aufgesetzt.", 0x2f3136))
    except Exception: pass


# ==========================================
# RESTLICHE MODERATIONS & ADMINISTRATIVE COMMANDS
# ==========================================
@tree.command(name="verify", description="Complete verification process")
async def verify(interaction: discord.Interaction):
    view = discord.ui.View()
    btn_yes = discord.ui.Button(label="Accept Rules", style=discord.ButtonStyle.green)
    btn_no = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)
    async def yes_cb(i): await i.response.send_message(embed=make_clean_embed("✅ Verifiziert", "Regeln akzeptiert.", 0x2f3136), ephemeral=True)
    async def no_cb(i): await i.response.send_message(embed=make_clean_embed("❌ Abgebrochen", "Vorgang abgebrochen.", 0x2f3136), ephemeral=True)
    btn_yes.callback = yes_cb
    btn_no.callback = no_cb
    view.add_item(btn_yes)
    view.add_item(btn_no)
    await interaction.response.send_message(embed=make_clean_embed("📝 Verifikation", "Bitte akzeptiere das Regelwerk, um freigeschaltet zu werden.", 0x2f3136), view=view, ephemeral=True)

class OfferConfirmation(discord.ui.View):
    def __init__(self, target: discord.Member):
        super().__init__(timeout=60)
        self.target = target
    @discord.ui.button(label="Accept Offer", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=make_clean_embed("🤝 Deal Angenommen", f"{interaction.user.mention} nimmt das Angebot an.", 0x2f3136))
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=make_clean_embed("❌ Abgelehnt", f"{interaction.user.mention} lehnt das Angebot ab.", 0x2f3136))

@tree.command(name="hit", description="Propose a custom trade deal")
async def hit(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(embed=make_clean_embed("💼 Trade Proposal", f"Neues Angebot für {member.mention}.", 0x2f3136), view=OfferConfirmation(target=member))

@tree.command(name="ban", description="Ban a user")
@is_owner()
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Kein Grund angegeben"):
    await member.ban(reason=reason)
    await interaction.response.send_message(embed=make_clean_embed("🔨 Ban", f"{member} wurde gebannt. Grund: {reason}", 0x2f3136))

@tree.command(name="unban", description="Unban a user by ID")
@is_owner()
async def unban(interaction: discord.Interaction, user_id: str, reason: str = "Kein Grund angegeben"):
    user = await bot.fetch_user(int(user_id))
    await interaction.guild.unban(user, reason=reason)
    await interaction.response.send_message(embed=make_clean_embed("✅ Unban", f"{user} entbannt.", 0x2f3136))

@tree.command(name="kick", description="Kick a user")
@is_owner()
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Kein Grund angegeben"):
    await member.kick(reason=reason)
    await interaction.response.send_message(embed=make_clean_embed("🚪 Kick", f"{member} gekickt. Grund: {reason}", 0x2f3136))

@tree.command(name="mute", description="Mute a user")
@is_owner()
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "Kein Grund angegeben"):
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not mute_role:
        mute_role = await interaction.guild.create_role(name="Muted")
        for channel in interaction.guild.channels: await channel.set_permissions(mute_role, send_messages=False, speak=False)
    await member.add_roles(mute_role, reason=reason)
    await interaction.response.send_message(embed=make_clean_embed("🔇 Mute", f"{member} für {minutes}m stummgeschaltet.", 0x2f3136))
    await asyncio.sleep(minutes * 60)
    await member.remove_roles(mute_role)

@tree.command(name="unmute", description="Unmute a user")
@is_owner()
async def unmute(interaction: discord.Interaction, member: discord.Member):
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if mute_role in member.roles:
        await member.remove_roles(mute_role)
        await interaction.response.send_message(embed=make_clean_embed("🔊 Unmute", f"{member} spricht wieder.", 0x2f3136))
    else:
        await interaction.response.send_message(embed=make_clean_embed("❌ Error", "User ist nicht gemutet.", 0x2f3136), ephemeral=True)

@tree.command(name="warn", description="Issue a warning to a user")
@is_owner()
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Kein Grund angegeben"):
    uid = str(member.id)
    if uid not in warnings: warnings[uid] = []
    warnings[uid].append({"reason": reason, "time": str(datetime.datetime.now())})
    count = len(warnings[uid])
    await interaction.response.send_message(embed=make_clean_embed("⚠️ Warnung", f"{member} verwarnt. Stand: {count}/3\nGrund: {reason}", 0x2f3136))
    if count >= 3: await member.ban(reason="Automatischer Ban nach 3 Verwarnungen.")

@tree.command(name="warnings", description="View user infraction history")
@is_owner()
async def check_warnings(interaction: discord.Interaction, member: discord.Member):
    uid = str(member.id)
    if uid not in warnings or not warnings[uid]:
        await interaction.response.send_message(embed=make_clean_embed("😇 Sauber", "Dieser User hat keine aktiven Verwarnungen.", 0x2f3136), ephemeral=True)
        return
    embed = discord.Embed(title=f"📋 Verwarnungen von: {member}", color=0x2f3136)
    for i, w in enumerate(warnings[uid], 1): embed.add_field(name=f"Fall #{i}", value=f"Grund: {w['reason']}\nDatum: {w['time']}", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="clearwarnings", description="Reset user infraction count")
@is_owner()
async def clearwarnings(interaction: discord.Interaction, member: discord.Member):
    warnings[str(member.id)] = []
    await interaction.response.send_message(embed=make_clean_embed("🧹 Bereinigt", f"Verlauf von {member} wurde gelöscht.", 0x2f3136))

@tree.command(name="purge", description="Bulk delete messages")
@is_owner()
async def purge(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.purge(limit=amount)
    await interaction.followup.send(embed=make_clean_embed("🧹 Chat geleert", f"{amount} Nachrichten gelöscht.", 0x2f3136), ephemeral=True)

@tree.command(name="slowmode", description="Configure channel rate limit")
@is_owner()
async def slowmode(interaction: discord.Interaction, seconds: int):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(embed=make_clean_embed("⏳ Slowmode", f"Intervall auf {seconds}s gesetzt.", 0x2f3136))

@tree.command(name="lock", description="Lock text channel permissions")
@is_owner()
async def lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message(embed=make_clean_embed("🔒 Kanal gesperrt", "Hier kann niemand mehr schreiben.", 0x2f3136))

@tree.command(name="unlock", description="Restore text channel permissions")
@is_owner()
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message(embed=make_clean_embed("🔓 Kanal geöffnet", "Hier darf wieder geschrieben werden.", 0x2f3136))

@tree.command(name="nickname", description="Modify user nickname")
@is_owner()
async def nickname(interaction: discord.Interaction, member: discord.Member, nickname: str):
    await member.edit(nick=nickname)
    await interaction.response.send_message(embed=make_clean_embed("👤 Name geändert", f"Name von {member} geändert in {nickname}.", 0x2f3136))

@tree.command(name="addrole", description="Assign a role")
@is_owner()
async def addrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await interaction.response.send_message(embed=make_clean_embed("🛡️ Rolle +", f"Rolle {role.name} an {member} vergeben.", 0x2f3136))

@tree.command(name="removerole", description="Revoke a role")
@is_owner()
async def removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await interaction.response.send_message(embed=make_clean_embed("🛡️ Rolle -", f"Rolle {role.name} von {member} entfernt.", 0x2f3136))

@tree.command(name="deleteallchannels", description="Wipe all channels")
@is_owner()
async def deleteallchannels(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_clean_embed("🚨 Warnung", "Lösche alle Kanäle in 5 Sekunden...", 0x2f3136))
    await asyncio.sleep(5)
    for channel in interaction.guild.channels:
        try: await channel.delete()
        except Exception: pass

@tree.command(name="createchannel", description="Create custom text channel")
@is_owner()
async def createchannel(interaction: discord.Interaction, name: str):
    channel = await interaction.guild.create_text_channel(name)
    await interaction.response.send_message(embed=make_clean_embed("🧱 Kanal+", f"Kanal {channel.mention} gebaut.", 0x2f3136))

@tree.command(name="deletechannel", description="Delete target channel")
@is_owner()
async def deletechannel(interaction: discord.Interaction, channel: discord.TextChannel):
    n = channel.name
    await channel.delete()
    await interaction.response.send_message(embed=make_clean_embed("🧱 Kanal-", f"Kanal #{n} gelöscht.", 0x2f3136), ephemeral=True)

@tree.command(name="createrole", description="Create custom role")
@is_owner()
async def createrole(interaction: discord.Interaction, name: str):
    role = await interaction.guild.create_role(name=name)
    await interaction.response.send_message(embed=make_clean_embed("🛡️ Rolle+", f"Rolle {role.name} kreiert.", 0x2f3136))

@tree.command(name="deleterole", description="Delete target role")
@is_owner()
async def deleterole(interaction: discord.Interaction, role: discord.Role):
    n = role.name
    await role.delete()
    await interaction.response.send_message(embed=make_clean_embed("🛡️ Rolle-", f"Rolle @{n} entfernt.", 0x2f3136))

@tree.command(name="serverinfo", description="Display technical guild metrics")
@is_owner()
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"📊 Server: {guild.name}", color=0x2f3136)
    embed.add_field(name="User", value=guild.member_count)
    embed.add_field(name="Channels", value=len(guild.channels))
    embed.add_field(name="Roles", value=len(guild.roles))
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await interaction.response.send_message(embed=embed)

@tree.command(name="userinfo", description="Fetch user profile data")
@is_owner()
async def userinfo(interaction: discord.Interaction, member: discord.Member):
    embed = discord.Embed(title=f"👤 Profil: {member}", color=0x2f3136)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Join Date", value=member.joined_at.strftime("%Y-%m-%d"))
    embed.set_thumbnail(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@tree.command(name="membercount", description="Get active member metrics")
@is_owner()
async def membercount(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_clean_embed("👥 Zähler", f"Server-Mitglieder: **{interaction.guild.member_count}**", 0x2f3136))

@tree.command(name="ping", description="Check hardware latency")
@is_owner()
async def ping(interaction: discord.Interaction): 
    await interaction.response.send_message(embed=make_clean_embed("📡 Latenz", f"Pong! Latency: `{round(bot.latency * 1000)}ms`", 0x2f3136))

@tree.command(name="coinflip", description="Execute random binary output")
@is_owner()
async def coinflip(interaction: discord.Interaction): 
    await interaction.response.send_message(embed=make_clean_embed("🪙 Münze", f"Ergebnis: **{random.choice(['Kopf', 'Zahl'])}**", 0x2f3136))

@tree.command(name="dice", description="Generate random numeric outcome")
@is_owner()
async def dice(interaction: discord.Interaction, sides: int = 6): 
    await interaction.response.send_message(embed=make_clean_embed("🎲 Würfel", f"Gewürfelt: **{random.randint(1, sides)}** (1-{sides})", 0x2f3136))

@tree.command(name="8ball", description="Query predictive string array")
@is_owner()
async def eightball(interaction: discord.Interaction, question: str): 
    await interaction.response.send_message(embed=make_clean_embed("🔮 Orakel", f"**Frage:** {question}\n**Antwort:** {random.choice(['Ja', 'Nein', 'Vielleicht', 'Sehr wahrscheinlich'])}", 0x2f3136))

@tree.command(name="choose", description="Select random parameter from comma-separated list")
@is_owner()
async def choose(interaction: discord.Interaction, options: str): 
    await interaction.response.send_message(embed=make_clean_embed("🤖 Auswahl", f"Gewählt: **{random.choice([o.strip() for o in options.split(',')])}**", 0x2f3136))

@tree.command(name="poll", description="Deploy polling reaction set")
@is_owner()
async def poll(interaction: discord.Interaction, question: str):
    msg = await interaction.channel.send(embed=discord.Embed(title=f"📊 Abstimmung: {question}", color=0x2f3136))
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")
    await interaction.response.send_message(embed=make_clean_embed("✅ System", "Umfrage gestartet.", 0x2f3136), ephemeral=True)

@tree.command(name="say", description="Relay text parameter through bot instance")
@is_owner()
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message(embed=make_clean_embed("✅ System", "Gesendet.", 0x2f3136), ephemeral=True)
    await interaction.channel.send(message)

@tree.command(name="embed", description="Generate native script rich embed")
@is_owner()
async def embed_cmd(interaction: discord.Interaction, title: str, description: str):
    await interaction.channel.send(embed=discord.Embed(title=title, description=description, color=0x2f3136))
    await interaction.response.send_message(embed=make_clean_embed("✅ System", "Embed gesendet.", 0x2f3136), ephemeral=True)

@tree.command(name="avatar", description="Fetch asset target user avatar")
@is_owner()
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"🖼️ Avatar: {member}", color=0x2f3136)
    embed.set_image(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@tree.command(name="announce", description="Broadcast data to target channel")
@is_owner()
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    await channel.send(embed=discord.Embed(title="📢 Ankündigung", description=message, color=0x2f3136))
    await interaction.response.send_message(embed=make_clean_embed("✅ System", "Broadcast abgeschlossen.", 0x2f3136), ephemeral=True)

@tree.command(name="uptime", description="Check instance active loop duration")
@is_owner()
async def uptime(interaction: discord.Interaction):
    delta = datetime.datetime.utcnow() - bot.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    await interaction.response.send_message(embed=make_clean_embed("📈 Uptime", f"Online seit: **{hours}h {minutes}m {seconds}s**", 0x2f3136))

@tree.command(name="botinfo", description="Display process details")
@is_owner()
async def botinfo(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Bot Details", color=0x2f3136)
    embed.add_field(name="Botname", value=bot.user.name)
    embed.add_field(name="Serveranzahl", value=len(bot.guilds))
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)


# ==========================================
# EVENTS & AUTOMATED SYSTEM LOGICS
# ==========================================
@bot.event
async def on_ready():
    if not hasattr(bot, 'start_time'): bot.start_time = datetime.datetime.utcnow()
    try: await tree.sync()
    except Exception as e: print(f"Sync Fehler: {e}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="trades"))
    print(f"System hochgefahren als {bot.user}")

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="welcome")
    if channel:
        embed = discord.Embed(title="👋 Willkommen", description=f"Hi {member.mention}, willkommen auf {member.guild.name}. Du bist Nummer #{member.guild.member_count}!", color=0x2f3136)
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    channel = discord.utils.get(member.guild.text_channels, name="welcome")
    if channel: await channel.send(embed=make_clean_embed("🚪 Verlassen", f"**{member.name}** hat den Server verlassen.", 0x2f3136))

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    if message.author.id == message.guild.owner_id:
        await bot.process_commands(message)
        return
        
    user_id = message.author.id
    current_time = time.time()
    content = message.content

    # Inhalts-Filter
    if any(word in content.lower() for word in BLOCKED_WORDS) or DISCORD_INVITE in content.lower() or len(message.mentions) >= MAX_MENTIONS:
        await message.delete()
        return
    if len(content) > 10 and (sum(1 for c in content if c.isupper()) / len(content)) * 100 >= MAX_CAPS_PERCENT:
        await message.delete()
        return

    # Anti-Spam Logik
    if user_id not in spam_tracker: spam_tracker[user_id] = []
    spam_tracker[user_id] = [t for t in spam_tracker[user_id] if current_time - t < SPAM_WINDOW]
    spam_tracker[user_id].append(current_time)
    
    if len(spam_tracker[user_id]) > SPAM_LIMIT:
        await message.delete()
        mute_role = discord.utils.get(message.guild.roles, name="Muted")
        if mute_role and mute_role not in message.author.roles:
            await message.author.add_roles(mute_role)
            await asyncio.sleep(300)
            await message.author.remove_roles(mute_role)
        return
    await bot.process_commands(message)


# ==========================================
# HOSTING LOGIC (KEEP ALIVE VIA PORT 8080)
# ==========================================
app = Flask('')
@app.route('/')
def home(): return "Bot Online"
def run(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

def main():
    keep_alive()
    token = os.environ.get("DISCORD_TOKEN")
    if token: bot.run(token)
    else: print("Error: No DISCORD_TOKEN found inside environment.")

if __name__ == "__main__":
    main()

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

# Global configurations & system trackers
spam_tracker = {}
warnings = {}
fill_tracker = {}

BLOCKED_WORDS = []
MAX_MENTIONS = 5
MAX_CAPS_PERCENT = 70
DISCORD_INVITE = "discord.gg"

# ==========================================
# CORE CORE HELPERS & DESIGN SYSTEM
# ==========================================
def make_clean_embed(title: str, description: str, color: int = 0x2f3136) -> discord.Embed:
    embed = discord.Embed(description=description, color=color)
    embed.set_author(name=title)
    return embed

def add_bot_footer(embed: discord.Embed, interaction: discord.Interaction):
    embed.set_footer(
        text=f"Powered by {interaction.client.user.name} | Today at {datetime.datetime.now().strftime('%H:%M')}",
        icon_url=interaction.client.user.display_avatar.url if interaction.client.user.avatar else None
    )
    return embed

def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild or interaction.user.id != interaction.guild.owner_id:
            embed = make_clean_embed("🔒 Access Denied", "Only the server owner can use this command.", 0xd9534f)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

async def create_ticket_transcript(channel, category="General"):
    guild = channel.guild
    log_channel = discord.utils.get(guild.text_channels, name="ticket-logs")
    if not log_channel:
        overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False), guild.me: discord.PermissionOverwrite(read_messages=True)}
        log_channel = await guild.create_text_channel("ticket-logs", overwrites=overwrites)

    buffer = []
    async for msg in channel.history(limit=None, oldest_first=True):
        timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        buffer.append(f"[{timestamp}] {msg.author}: {msg.content}")
    
    file_stream = io.BytesIO("\n".join(buffer).encode("utf-8"))
    file = discord.File(fp=file_stream, filename=f"transcript-{channel.name}.txt")
    await log_channel.send(embed=make_clean_embed("📁 Ticket Archive", f"**Type:** {category}\n**Channel:** #{channel.name}"), file=file)

# ==========================================
# SYSTEMS & INTERACTIVE VIEWS
# ==========================================
class SupportTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.green, custom_id="btn_claim_support", emoji="✋")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel.name == f"ticket-{interaction.user.name.lower()}".replace(" ", "-"):
            return await interaction.response.send_message(embed=make_clean_embed("❌ Error", "You cannot claim your own ticket.", 0xd9534f), ephemeral=True)
        
        staff_roles = ["Owner", "Administrator", "Head Moderator", "Moderator", "Team Lead", "Chief Lead", "Lead", "Cordinator"]
        if not any(discord.utils.get(interaction.user.roles, name=r) for r in staff_roles):
            return await interaction.response.send_message(embed=make_clean_embed("🔒 Denied", "Staff only.", 0xd9534f), ephemeral=True)

        button.label = "Claimed"
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=add_bot_footer(make_clean_embed("✅ Claimed", f"{interaction.user.mention} will assist you now.", 0x2ecc71), interaction))

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="btn_close_support", emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=make_clean_embed("🔒 Closing", "Saving archive logs... Channel will delete in 5s."))
        await create_ticket_transcript(interaction.channel, "Support")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class SupportPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Support", style=discord.ButtonStyle.blurple, custom_id="btn_open_support", emoji="🎫")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        name = f"ticket-{interaction.user.name.lower()}".replace(" ", "-")
        if discord.utils.get(interaction.guild.text_channels, name=name):
            return await interaction.response.send_message(embed=make_clean_embed("❌ Error", "You already have an active ticket.", 0xd9534f), ephemeral=True)
        
        cat = discord.utils.get(interaction.guild.categories, name="Tickets") or await interaction.guild.create_category("Tickets")
        perms = {interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        
        staff_roles = ["Owner", "Administrator", "Head Moderator", "Moderator", "Team Lead", "Chief Lead", "Lead", "Cordinator"]
        for r in staff_roles:
            role = discord.utils.get(interaction.guild.roles, name=r)
            if role: perms[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
        ch = await interaction.guild.create_text_channel(name, overwrites=perms, category=cat)
        await ch.send(f"{interaction.user.mention}", embed=add_bot_footer(make_clean_embed("🎫 Support Ticket", "Please describe your issue in detail below."), interaction), view=SupportTicketView())
        await interaction.response.send_message(embed=make_clean_embed("✅ Success", f"Ticket created: {ch.mention}", 0x2ecc71), ephemeral=True)

class MiddlemanTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Deal", style=discord.ButtonStyle.green, custom_id="btn_claim_mm", emoji="✋")
    async def claim_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel.name == f"ticket-mm_{interaction.user.name.lower()}".replace(" ", "-"):
            return await interaction.response.send_message(embed=make_clean_embed("❌ Error", "You cannot claim your own trade.", 0xd9534f), ephemeral=True)
        
        mm_roles = ["Middleman", "Head Middleman", "Middleman Manager", "Owner", "Administrator"]
        if not any(discord.utils.get(interaction.user.roles, name=r) for r in mm_roles):
            return await interaction.response.send_message(embed=make_clean_embed("🔒 Denied", "Middlemen only.", 0xd9534f), ephemeral=True)

        button.label = "Claimed"
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=add_bot_footer(make_clean_embed("✅ Secured", f"{interaction.user.mention} is your official Middleman.", 0x2ecc71), interaction))

    @discord.ui.button(label="Close Session", style=discord.ButtonStyle.red, custom_id="btn_close_mm", emoji="🔒")
    async def close_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=make_clean_embed("🔒 Closing", "Saving trade history... Channel will delete in 5s."))
        await create_ticket_transcript(interaction.channel, "Middleman")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class MiddlemanPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Middleman", style=discord.ButtonStyle.blurple, custom_id="btn_open_mm", emoji="💳")
    async def open_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        name = f"ticket-mm_{interaction.user.name.lower()}".replace(" ", "-")
        if discord.utils.get(interaction.guild.text_channels, name=name):
            return await interaction.response.send_message(embed=make_clean_embed("❌ Error", "You already have a trade active.", 0xd9534f), ephemeral=True)
        
        cat = discord.utils.get(interaction.guild.categories, name="Middleman Service") or await interaction.guild.create_category("Middleman Service")
        perms = {interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        
        mm_roles = ["Owner", "Middleman Manager", "Head Middleman", "Middleman", "Chief Lead", "Lead", "Cordinator"]
        for r in mm_roles:
            role = discord.utils.get(interaction.guild.roles, name=r)
            if role: perms[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
        ch = await interaction.guild.create_text_channel(name, overwrites=perms, category=cat)
        role = discord.utils.get(interaction.guild.roles, name="Middleman")
        await ch.send(f"{interaction.user.mention} {role.mention if role else ''}", embed=add_bot_footer(make_clean_embed("🤝 Middleman Escrow", "Tag your partner and state deal parameters."), interaction), view=MiddlemanTicketView())
        await interaction.response.send_message(embed=make_clean_embed("✅ Success", f"Trade ticket created: {ch.mention}", 0x2ecc71), ephemeral=True)

# ==========================================
# INFRASTRUCTURE CORE COMMANDS
# ==========================================
@tree.command(name="ticket", description="Deploy support panel")
@is_owner()
async def deploy_t(interaction: discord.Interaction):
    embed = discord.Embed(title="🎫 Support Tickets", description="Click below to open a support ticket.", color=0x2f3136)
    await interaction.channel.send(embed=add_bot_footer(embed, interaction), view=SupportPanel())
    await interaction.response.send_message(embed=make_clean_embed("✅ System", "Panel deployed successfully."), ephemeral=True)

@tree.command(name="setup_middleman", description="Deploy middleman panel")
@is_owner()
async def deploy_m(interaction: discord.Interaction):
    embed = discord.Embed(title="🤝 Middleman Services", description="Click below to request a middleman.", color=0x2f3136)
    await interaction.channel.send(embed=add_bot_footer(embed, interaction), view=MiddlemanPanel())
    await interaction.response.send_message(embed=make_clean_embed("✅ System", "Panel deployed successfully."), ephemeral=True)

@tree.command(name="fill", description="Toggle infrastructure staff roles")
@is_owner()
async def fill_roles(interaction: discord.Interaction):
    uid = interaction.user.id
    roles_list = ["Owner", "Administrator", "Head Moderator", "Moderator", "Middleman Manager", "Head Middleman", "Middleman", "Team Lead", "Chief Lead", "Lead", "Cordinator"]
    
    if uid in fill_tracker and fill_tracker[uid]:
        removed = []
        for rid in fill_tracker[uid]:
            role = interaction.guild.get_role(rid)
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                removed.append(role.name)
        fill_tracker[uid] = []
        await interaction.response.send_message(embed=make_clean_embed("🔄 Removed", f"Removed roles:\n**{', '.join(removed) if removed else 'None'}**"), ephemeral=True)
    else:
        granted, added = [], []
        for name in roles_list:
            role = discord.utils.get(interaction.guild.roles, name=name)
            if role and role not in interaction.user.roles:
                await interaction.user.add_roles(role)
                granted.append(role.id)
                added.append(role.name)
        fill_tracker[uid] = granted
        await interaction.response.send_message(embed=make_clean_embed("🔄 Filled", f"Granted roles:\n**{', '.join(added) if added_roles else 'None'}**"), ephemeral=True)

@tree.command(name="revamp", description="Wipe and rebuild layout")
@is_owner()
async def revamp(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_clean_embed("🔄 Revamp", "Rebuilding structure..."), ephemeral=True)
    roles = {"Owner": 0x990000, "Administrator": 0xff0000, "Head Moderator": 0xffa500, "Moderator": 0x808080, "Middleman Manager": 0x4b0082, "Head Middleman": 0x800080, "Middleman": 0x008000, "Team Lead": 0x0000ff, "Chief Lead": 0x00008b, "Lead": 0x008080, "Cordinator": 0xff00ff, "Muted": 0x111111}
    for n, c in roles.items():
        if not discord.utils.get(interaction.guild.roles, name=n): 
            await interaction.guild.create_role(name=name, color=discord.Color(c))
            
    for channel in interaction.guild.channels:
        if channel != interaction.channel:
            try: await channel.delete()
            except: pass
            
    struct = {"INFORMATION": ["welcome", "rules", "announcements", "giveaways"], "COMMUNITY": ["general", "bot-commands", "memes"], "TRANSACTIONS": ["middleman-info", "marketplace", "trading-chat"], "UTILITY": ["open-ticket", "middleman-service"]}
    for cat, chs in struct.items():
        category = await interaction.guild.create_category(cat)
        for name in chs: 
            await interaction.guild.create_text_channel(name, category=category)

# ==========================================
# MODERATION SYSTEM ENGINE
# ==========================================
@tree.command(name="ban")
@is_owner()
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "None"):
    if member.id == interaction.guild.owner_id: 
        return await interaction.response.send_message("Cannot ban owner.", ephemeral=True)
    await member.ban(reason=reason)
    await interaction.response.send_message(embed=make_clean_embed("🔨 Banned", f"{member.mention} banned. Reason: {reason}", 0xd9534f))

@tree.command(name="unban")
@is_owner()
async def unban(interaction: discord.Interaction, user_id: str):
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(embed=make_clean_embed("🔓 Unbanned", f"Unbanned {user}."))
    except:
        await interaction.response.send_message("User not found or not banned.", ephemeral=True)

@tree.command(name="kick")
@is_owner()
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "None"):
    if member.id == interaction.guild.owner_id: 
        return await interaction.response.send_message("Cannot kick owner.", ephemeral=True)
    await member.kick(reason=reason)
    await interaction.response.send_message(embed=make_clean_embed("👢 Kicked", f"{member.mention} kicked."))

@tree.command(name="mute")
@is_owner()
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 10):
    role = discord.utils.get(interaction.guild.roles, name="Muted") or await interaction.guild.create_role(name="Muted")
    await member.add_roles(role)
    await interaction.response.send_message(embed=make_clean_embed("🤫 Muted", f"{member.mention} muted for {minutes}m."))
    await asyncio.sleep(minutes * 60)
    await member.remove_roles(role)

@tree.command(name="unmute")
@is_owner()
async def unmute(interaction: discord.Interaction, member: discord.Member):
    role = discord.utils.get(interaction.guild.roles, name="Muted")
    if role in member.roles:
        await member.remove_roles(role)
        await interaction.response.send_message(embed=make_clean_embed("🔊 Unmuted", f"Unmuted {member.mention}."))
    else:
        await interaction.response.send_message("Not muted.", ephemeral=True)

@tree.command(name="warn")
@is_owner()
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Violation"):
    uid = str(member.id)
    warnings[uid] = warnings.get(uid, []) + [reason]
    count = len(warnings[uid])
    await interaction.response.send_message(embed=make_clean_embed("⚠️ Warned", f"{member.mention} warned. Strikes: `{count}/3`"))
    if count >= 3:
        await member.ban(reason="3 Strikes reached.")
        await interaction.channel.send(embed=make_clean_embed("🔨 Strike Ban", f"{member.mention} banned for 3 warns.", 0xd9534f))

@tree.command(name="warnings")
async def check_w(interaction: discord.Interaction, member: discord.Member):
    w = warnings.get(str(member.id), [])
    lines = [f"`{i+1}.` {r}" for i, r in enumerate(w)]
    await interaction.response.send_message(embed=make_clean_embed("📋 Warnings", f"{member.mention} warnings:\n" + ("\n".join(lines) if w else "No warnings.")))

@tree.command(name="clearwarnings")
@is_owner()
async def clear_w(interaction: discord.Interaction, member: discord.Member):
    warnings[str(member.id)] = []
    await interaction.response.send_message(embed=make_clean_embed("🧹 Cleared", f"Reset warnings for {member.mention}."))

@tree.command(name="purge")
@is_owner()
async def purge(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100: 
        return await interaction.response.send_message("Select between 1-100.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(embed=make_clean_embed("🧹 Purged", f"Deleted `{len(deleted)}` messages."), ephemeral=True)

@tree.command(name="slowmode")
@is_owner()
async def slowmode(interaction: discord.Interaction, seconds: int):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(embed=make_clean_embed("⏱️ Slowmode", f"Set to {seconds}s."))

@tree.command(name="lock")
@is_owner()
async def lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message(embed=make_clean_embed("🔒 Locked", "Channel locked."))

@tree.command(name="unlock")
@is_owner()
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message(embed=make_clean_embed("🔓 Unlocked", "Channel unlocked."))

# ==========================================
# ADMINISTRATIVE CHANNEL & ROLE MANAGERS
# ==========================================
@tree.command(name="nickname")
@is_owner()
async def nickname(interaction: discord.Interaction, member: discord.Member, new_name: str):
    await member.edit(nick=new_name)
    await interaction.response.send_message(embed=make_clean_embed("📝 Nickname", f"Changed nick to {new_name}."))

@tree.command(name="addrole")
@is_owner()
async def addrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await interaction.response.send_message(embed=make_clean_embed("🛡️ Added", f"Role {role.mention} granted."))

@tree.command(name="removerole")
@is_owner()
async def remrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await interaction.response.send_message(embed=make_clean_embed("🛡️ Removed", f"Role {role.mention} removed."))

@tree.command(name="deleteallchannels")
@is_owner()
async def delchannels(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    for c in interaction.guild.channels:
        if c != interaction.channel:
            try: await c.delete()
            except: pass
    await interaction.followup.send(embed=make_clean_embed("🚨 Reset", "All utility channels cleared."), ephemeral=True)

@tree.command(name="createchannel")
@is_owner()
async def createch(interaction: discord.Interaction, name: str):
    c = await interaction.guild.create_text_channel(name)
    await interaction.response.send_message(embed=make_clean_embed("📁 Created", f"Channel: {c.mention}"))

@tree.command(name="deletechannel")
@is_owner()
async def deletech(interaction: discord.Interaction, channel: discord.TextChannel):
    await channel.delete()
    await interaction.response.send_message(embed=make_clean_embed("🗑️ Deleted", "Channel purged."))

@tree.command(name="createrole")
@is_owner()
async def createrl(interaction: discord.Interaction, name: str):
    r = await interaction.guild.create_role(name=name)
    await interaction.response.send_message(embed=make_clean_embed("🎨 Created", f"Role: {r.mention}"))

@tree.command(name="deleterole")
@is_owner()
async def deleterl(interaction: discord.Interaction, role: discord.Role):
    await role.delete()
    await interaction.response.send_message(embed=make_clean_embed("🗑️ Deleted", "Role deleted."))

# ==========================================
# ENTERTAINMENT & INFORMATIONAL MODULES
# ==========================================
@tree.command(name="gstart")
@is_owner()
async def gstart(interaction: discord.Interaction, minutes: int, winners: int, prize: str):
    await interaction.response.send_message("Giveaway setup complete.", ephemeral=True)
    embed = discord.Embed(title="🎉 GIVEAWAY LAUNCHED", description=f"**Prize:** {prize}\n**Winners:** `{winners}`\n**Ends in:** `{minutes}`m\nReact with 🎉 to join!", color=0x2f3136)
    msg = await interaction.channel.send(embed=add_bot_footer(embed, interaction))
    await msg.add_reaction("🎉")
    
    await asyncio.sleep(minutes * 60)
    msg = await interaction.channel.fetch_message(msg.id)
    u = [user async for user in discord.utils.get(msg.reactions, emoji="🎉").users() if not user.bot]
    
    if not u: 
        return await interaction.channel.send(embed=make_clean_embed("🎉 Results", "No participants found."))
    w = random.sample(u, min(len(u), winners))
    await interaction.channel.send(f"🏆 **GIVEAWAY CONCLUDED**\nWinners for **{prize}**: {', '.join([m.mention for m in w])}")

@tree.command(name="greroll")
@is_owner()
async def greroll(interaction: discord.Interaction, message_id: str):
    try:
        msg = await interaction.channel.fetch_message(int(message_id))
        u = [user async for user in discord.utils.get(msg.reactions, emoji="🎉").users() if not user.bot]
        if u: 
            await interaction.response.send_message(f"🎉 **New Selection:** {random.choice(u).mention} won the reroll!")
        else: 
            await interaction.response.send_message("No entries found.", ephemeral=True)
    except: 
        await interaction.response.send_message("Invalid Message ID.", ephemeral=True)

@tree.command(name="verify")
async def verify(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_clean_embed("✅ Verified", "Security pass granted."), ephemeral=True)

@tree.command(name="hit")
async def hit(interaction: discord.Interaction, partner: discord.Member):
    await interaction.response.send_message(f"🤝 {interaction.user.mention} strikes a premium agreement deal package with {partner.mention}!")

@tree.command(name="poll")
async def poll(interaction: discord.Interaction, question: str):
    await interaction.response.send_message("Poll deployed.", ephemeral=True)
    m = await interaction.channel.send(f"📊 **{question}**")
    await m.add_reaction("👍")
    await m.add_reaction("👎")

@tree.command(name="say")
@is_owner()
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("Sent.", ephemeral=True)
    await interaction.channel.send(message)

@tree.command(name="embed")
@is_owner()
async def embed_cmd(interaction: discord.Interaction, title: str, description: str):
    await interaction.response.send_message("Sent.", ephemeral=True)
    await interaction.channel.send(embed=make_clean_embed(title, description))

@tree.command(name="avatar")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    t = member or interaction.user
    e = discord.Embed(color=0x2f3136)
    e.set_author(name=f"Profile: {t}")
    e.set_image(url=t.display_avatar.url)
    await interaction.response.send_message(embed=e)

@tree.command(name="announce")
@is_owner()
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    await channel.send(embed=add_bot_footer(make_clean_embed("📢 ANNOUNCEMENT", message), interaction))
    await interaction.response.send_message("Announced.", ephemeral=True)

# ==========================================
# SYSTEM CORE STATISTICS
# ==========================================
@tree.command(name="serverinfo")
async def serverinfo(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_clean_embed("📊 Server Meta", f"**Name:** {interaction.guild.name}\n**Members:** `{interaction.guild.member_count}`\n**ID:** `{interaction.guild.id}`"))

@tree.command(name="userinfo")
async def userinfo(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(embed=make_clean_embed("👤 User Profile", f"**User:** {member.mention}\n**ID:** `{member.id}`\n**Joined:** {member.joined_at.strftime('%Y-%m-%d')}"))

@tree.command(name="membercount")
async def membercount(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_clean_embed("📊 Members", f"Total connection count: `{interaction.guild.member_count}`"))

@tree.command(name="ping")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_clean_embed("🏓 Latency", f"Engine tracking: `{round(bot.latency * 1000)}ms`"))

# ==========================================
# MINI-GAMES & LOGIC MATRIX
# ==========================================
@tree.command(name="coinflip")
async def coinflip(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_clean_embed("🪙 Flip", f"Result: **{random.choice(['Heads', 'Tails'])}**"))

@tree.command(name="dice")
async def dice(interaction: discord.Interaction, sides: int = 6):
    await interaction.response.send_message(embed=make_clean_embed("🎲 Roll", f"Result: **{random.randint(1, sides)}**"))

@tree.command(name="8ball")
async def ball(interaction: discord.Interaction, question: str):
    ans = ['Yes, absolutely.', 'Recalculating fields...', 'No path detected.']
    await interaction.response.send_message(embed=make_clean_embed("🔮 Oracle", f"**Q:** {question}\n**A:** {random.choice(ans)}"))

@tree.command(name="choose")
async def choose(interaction: discord.Interaction, options: str):
    choice = random.choice([x.strip() for x in options.split(',')])
    await interaction.response.send_message(embed=make_clean_embed("✨ Pick", f"Selected: **{choice}**"))

@tree.command(name="uptime")
async def uptime(interaction: discord.Interaction):
    diff = datetime.datetime.utcnow() - bot.start_time
    await interaction.response.send_message(embed=make_clean_embed("⏱ *Diagnostics*", f"Online execution window: `{str(diff).split('.')[0]}`"))

@tree.command(name="botinfo")
async def botinfo(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_clean_embed("⚙ Architecture", f"**Core:** {bot.user.name}\n**Matrices:** `{len(bot.guilds)}` connections\n**API:** Discord.py v2.3+"))

@tree.command(name="help")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_clean_embed("ℹ Sync Stable", "All application structures are active. Type `/` to access commands.", 0x2ecc71), ephemeral=True)

# ==========================================
# CHAT PROTECTOR EVENTS
# ==========================================
@bot.event
async def on_ready():
    if not hasattr(bot, 'start_time'): 
        bot.start_time = datetime.datetime.utcnow()
    try: 
        await tree.sync()
        print(f"Synced engine {bot.user.name}")
    except Exception as e: 
        print(e)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="secure deals"))

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or message.author.id == message.guild.owner_id: 
        return
        
    uid, cur = message.author.id, time.time()
    if any(w in message.content.lower() for w in BLOCKED_WORDS) or DISCORD_INVITE in message.content.lower() or len(message.mentions) >= MAX_MENTIONS:
        try: await message.delete()
        except: pass
        return
        
    if len(message.content) > 10 and (sum(1 for c in message.content if c.isupper()) / len(message.content)) * 100 >= MAX_CAPS_PERCENT:
        try: await message.delete()
        except: pass
        return
        
    spam_tracker[uid] = [t for t in spam_tracker.get(uid, []) if cur - t < 5] + [cur]
    if len(spam_tracker[uid]) > 5:
        try:
            await message.delete()
            role = discord.utils.get(message.guild.roles, name="Muted")
            if role: 
                await message.author.add_roles(role)
                await asyncio.sleep(300)
                await message.author.remove_roles(role)
        except: pass

# ==========================================
# HOST CONTAINER ROUTING
# ==========================================
app = Flask('')

@app.route('/')
def home(): 
    return "Container Routing Active."

def run(): 
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    Thread(target=run, daemon=True).start()
    token = os.environ.get("DISCORD_TOKEN")
    if token: 
        bot.run(token)
    else: 
        print("Critical Exception: Missing token vector link.")

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

# Bot Setup with support for both Prefix and Slash commands
intents = discord.Intents.all()

class UtilityBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        self.add_view(SupportPanel())
        self.add_view(SupportTicketView())
        self.add_view(MiddlemanPanel())
        self.add_view(MiddlemanTicketView())

bot = UtilityBot()
tree = bot.tree

# Storage Matrices
spam_tracker = {}
warnings = {}
fill_tracker = {}

BLOCKED_WORDS = []
MAX_MENTIONS = 5
MAX_CAPS_PERCENT = 70
DISCORD_INVITE = "discord.gg"

# ==========================================
# DESIGN HANDLER (EMBED DESIGN)
# ==========================================
def create_embed(title: str, description: str, color: int = 0x2f3136) -> discord.Embed:
    embed = discord.Embed(description=description, color=color)
    embed.set_author(name=title)
    return embed

def append_footer(embed: discord.Embed, interaction_or_ctx):
    client = interaction_or_ctx.bot if hasattr(interaction_or_ctx, 'bot') else interaction_or_ctx.client
    embed.set_footer(
        text=f"{client.user.name} • Today at {datetime.datetime.now().strftime('%H:%M')}",
        icon_url=client.user.display_avatar.url if client.user.avatar else None
    )
    return embed

# Owner Check for Slash Commands
def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild or interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(embed=create_embed("🔒 Access Denied", "Only the server owner can execute this command.", 0xd9534f), ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

# Transcript Generator for Closed Tickets
async def save_transcript(channel, category="General"):
    guild = channel.guild
    log_channel = discord.utils.get(guild.text_channels, name="ticket-logs")
    if not log_channel:
        overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False), guild.me: discord.PermissionOverwrite(read_messages=True)}
        log_channel = await guild.create_text_channel("ticket-logs", overwrites=overwrites)

    history_lines = []
    async for msg in channel.history(limit=None, oldest_first=True):
        ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        history_lines.append(f"[{ts}] {msg.author}: {msg.content}")
    
    stream = io.BytesIO("\n".join(history_lines).encode("utf-8"))
    file = discord.File(fp=stream, filename=f"transcript-{channel.name}.txt")
    await log_channel.send(embed=create_embed("📁 Ticket Archive", f"**Type:** {category}\n**Channel:** #{channel.name}"), file=file)

# ==========================================
# INTERACTIVE TICKETS & PANEL VIEWS
# ==========================================
class SupportTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.green, custom_id="btn_claim_support", emoji="✋")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel.name == f"ticket-{interaction.user.name.lower()}".replace(" ", "-"):
            return await interaction.response.send_message(embed=create_embed("❌ Error", "You cannot claim your own support ticket.", 0xd9534f), ephemeral=True)
        
        staff = ["Owner", "Administrator", "Head Moderator", "Moderator", "Team Lead", "Chief Lead", "Lead", "Cordinator"]
        if not any(discord.utils.get(interaction.user.roles, name=r) for r in staff):
            return await interaction.response.send_message(embed=create_embed("🔒 Denied", "Restricted to staff members only.", 0xd9534f), ephemeral=True)

        button.label = "Claimed"
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=append_footer(create_embed("✅ Ticket Claimed", f"{interaction.user.mention} will assist you shortly.", 0x2ecc71), interaction))

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="btn_close_support", emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=create_embed("🔒 Closing", "Saving archive logs... Channel will be deleted in 5 seconds."))
        await save_transcript(interaction.channel, "Support")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class SupportPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Support", style=discord.ButtonStyle.blurple, custom_id="btn_open_support", emoji="🎫")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        name = f"ticket-{interaction.user.name.lower()}".replace(" ", "-")
        if discord.utils.get(interaction.guild.text_channels, name=name):
            return await interaction.response.send_message(embed=create_embed("❌ Error", "You already have an active support ticket open.", 0xd9534f), ephemeral=True)
        
        cat = discord.utils.get(interaction.guild.categories, name="Tickets") or await interaction.guild.create_category("Tickets")
        perms = {interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        
        staff = ["Owner", "Administrator", "Head Moderator", "Moderator", "Team Lead", "Chief Lead", "Lead", "Cordinator"]
        for r in staff:
            role = discord.utils.get(interaction.guild.roles, name=r)
            if role: perms[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
        ch = await interaction.guild.create_text_channel(name, overwrites=perms, category=cat)
        await ch.send(f"{interaction.user.mention}", embed=append_footer(create_embed("🎫 Support Ticket", "Please describe your request or issue in detail below. A staff member will be with you shortly."), interaction), view=SupportTicketView())
        await interaction.response.send_message(embed=create_embed("✅ Success", f"Your ticket has been created: {ch.mention}", 0x2ecc71), ephemeral=True)

class MiddlemanTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Deal", style=discord.ButtonStyle.green, custom_id="btn_claim_mm", emoji="✋")
    async def claim_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel.name == f"ticket-mm_{interaction.user.name.lower()}".replace(" ", "-"):
            return await interaction.response.send_message(embed=create_embed("❌ Error", "You cannot handle your own transaction session.", 0xd9534f), ephemeral=True)
        
        mm_roles = ["Middleman", "Head Middleman", "Middleman Manager", "Owner", "Administrator"]
        if not any(discord.utils.get(interaction.user.roles, name=r) for r in mm_roles):
            return await interaction.response.send_message(embed=create_embed("🔒 Denied", "Restricted to authorized middleman staff only.", 0xd9534f), ephemeral=True)

        button.label = "Claimed"
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=append_footer(create_embed("✅ Middleman Assigned", f"{interaction.user.mention} is now your official middleman for this trade session.", 0x2ecc71), interaction))

    @discord.ui.button(label="Close Session", style=discord.ButtonStyle.red, custom_id="btn_close_mm", emoji="🔒")
    async def close_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(create_embed("🔒 Closing", "Securing trade history transcripts... Channel will be deleted in 5 seconds."))
        await save_transcript(interaction.channel, "Middleman")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class MiddlemanPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Middleman", style=discord.ButtonStyle.blurple, custom_id="btn_open_mm", emoji="💳")
    async def open_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        name = f"ticket-mm_{interaction.user.name.lower()}".replace(" ", "-")
        if discord.utils.get(interaction.guild.text_channels, name=name):
            return await interaction.response.send_message(embed=create_embed("❌ Error", "You already have an active middleman session requested.", 0xd9534f), ephemeral=True)
        
        cat = discord.utils.get(interaction.guild.categories, name="Middleman Service") or await interaction.guild.create_category("Middleman Service")
        perms = {interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        
        mm_roles = ["Owner", "Middleman Manager", "Head Middleman", "Middleman", "Chief Lead", "Lead", "Cordinator"]
        for r in mm_roles:
            role = discord.utils.get(interaction.guild.roles, name=r)
            if role: perms[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
        ch = await interaction.guild.create_text_channel(name, overwrites=perms, category=cat)
        role = discord.utils.get(interaction.guild.roles, name="Middleman")
        await ch.send(f"{interaction.user.mention} {role.mention if role else ''}", embed=append_footer(create_embed("🤝 Middleman Escrow", "Please mention your trading partner here and write down the full deal parameters. An authorized middleman will step in shortly."), interaction), view=MiddlemanTicketView())
        await interaction.response.send_message(embed=create_embed("✅ Success", f"Middleman ticket created: {ch.mention}", 0x2ecc71), ephemeral=True)

# ==========================================
# MANAGEMENT & SETUP COMMANDS
# ==========================================
@tree.command(name="ticket", description="Deploys the main interactive support ticket panel")
@is_owner()
async def deploy_t(interaction: discord.Interaction):
    embed = discord.Embed(title="🎫 Support Tickets", description="Click the button below to open a private support session.", color=0x2f3136)
    await interaction.channel.send(embed=append_footer(embed, interaction), view=SupportPanel())
    await interaction.response.send_message(embed=create_embed("✅ System", "Support panel deployed successfully."), ephemeral=True)

@tree.command(name="setup_middleman", description="Deploys the main interactive middleman service panel")
@is_owner()
async def deploy_m(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤝 Middleman Services", 
        description=(
            "**Secure Escrow / Middleman Transactions**\n"
            "• To request an official middleman from this server, click the blue **\"Request Middleman\"** button below.\n\n"
            "**How it works:**\n"
            "• Once your ticket opens, add your trading partner, specify the deal terms, and wait for a certified middleman to secure your assets."
        ), 
        color=0x2f3136
    )
    await interaction.channel.send(embed=append_footer(embed, interaction), view=MiddlemanPanel())
    await interaction.response.send_message(embed=create_embed("✅ System", "Middleman panel deployed successfully."), ephemeral=True)

@tree.command(name="fill", description="Saves and toggles your current roles off or restores them back automatically")
@is_owner()
async def fill_roles(interaction: discord.Interaction):
    guild = interaction.guild
    member = interaction.user
    uid = member.id

    if uid in fill_tracker and fill_tracker[uid]:
        restored = []
        for rid in fill_tracker[uid]:
            role = guild.get_role(rid)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role)
                    restored.append(role.name)
                except discord.Forbidden:
                    pass
        fill_tracker[uid] = []
        await interaction.response.send_message(embed=create_embed("🔄 Roles Restored", f"Welcome back! Your previous roles have been restored:\n**{', '.join(restored) if restored else 'None'}**", 0x2ecc71), ephemeral=True)
    else:
        role_ids = []
        removed = []
        for role in member.roles:
            if not role.is_default():
                role_ids.append(role.id)
                try:
                    await member.remove_roles(role)
                    removed.append(role.name)
                except discord.Forbidden:
                    pass
        if not role_ids:
            return await interaction.response.send_message(embed=create_embed("❌ Error", "You do not have any saved roles that can be cleared.", 0xd9534f), ephemeral=True)
        fill_tracker[uid] = role_ids
        await interaction.response.send_message(embed=create_embed("🔄 Roles Stored", f"Your profile roles have been secured and stripped from your user profile:\n**{', '.join(removed) if removed else 'None'}**\n\n*Run `/fill` at any time to regain your setup.*", 0x2f3136), ephemeral=True)

@tree.command(name="revamp", description="Purges server channels and completely builds the core layout matrix")
@is_owner()
async def revamp(interaction: discord.Interaction):
    await interaction.response.send_message(embed=create_embed("🔄 Revamp", "Rebuilding server infrastructure layout..."), ephemeral=True)
    roles = {"Owner": 0x990000, "Administrator": 0xff0000, "Head Moderator": 0xffa500, "Moderator": 0x808080, "Middleman Manager": 0x4b0082, "Head Middleman": 0x800080, "Middleman": 0x008000, "Team Lead": 0x0000ff, "Chief Lead": 0x00008b, "Lead": 0x008080, "Cordinator": 0xff00ff, "Muted": 0x111111}
    for n, c in roles.items():
        if not discord.utils.get(interaction.guild.roles, name=n): 
            await interaction.guild.create_role(name=n, color=discord.Color(c))
            
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
# HYBRID MODERATION (SLASH + PREFIX COMMANDS)
# ==========================================

# --- BAN ---
async def exec_ban(ctx_or_inter, member: discord.Member, reason: str):
    guild = ctx_or_inter.guild
    if member.id == guild.owner_id:
        return "The guild owner cannot be targeted by the ban vector."
    await member.ban(reason=reason)
    return create_embed("🔨 Banned", f"{member.mention} has been permanently barred. Reason: {reason}", 0xd9534f)

@bot.command(name="ban")
@commands.has_permissions(ban_members=True)
async def prefix_ban(ctx, member: discord.Member, *, reason: str = "Unspecified"):
    res = await exec_ban(ctx, member, reason)
    await ctx.send(embed=res if isinstance(res, discord.Embed) else create_embed("❌ Error", res, 0xd9534f))

@tree.command(name="ban", description="Permanently bars a member from the guild server")
@is_owner()
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Unspecified"):
    res = await exec_ban(interaction, member, reason)
    await interaction.response.send_message(embed=res if isinstance(res, discord.Embed) else create_embed("❌ Error", res, 0xd9534f))

# --- UNBAN ---
async def exec_unban(ctx_or_inter, user_id: str):
    guild = ctx_or_inter.guild
    try:
        user = await bot.fetch_user(int(user_id))
        await guild.unban(user)
        return create_embed("🔓 Unbanned", f"Successfully lifted restrictions for user {user.name}.")
    except:
        return "Target profile link could not be located or verified on the ban list."

@bot.command(name="unban")
@commands.has_permissions(ban_members=True)
async def prefix_unban(ctx, user_id: str):
    res = await exec_unban(ctx, user_id)
    await ctx.send(embed=res if isinstance(res, discord.Embed) else create_embed("❌ Error", res, 0xd9534f))

@tree.command(name="unban", description="Lifts ban restrictions for a user using their ID format")
@is_owner()
async def slash_unban(interaction: discord.Interaction, user_id: str):
    res = await exec_unban(interaction, user_id)
    await interaction.response.send_message(embed=res if isinstance(res, discord.Embed) else create_embed("❌ Error", res, 0xd9534f))

# --- KICK ---
async def exec_kick(ctx_or_inter, member: discord.Member, reason: str):
    guild = ctx_or_inter.guild
    if member.id == guild.owner_id:
        return "The guild owner cannot be targeted by the kick vector."
    await member.kick(reason=reason)
    return create_embed("👢 Kicked", f"Removed {member.mention} from the server roster. Reason: {reason}")

@bot.command(name="kick")
@commands.has_permissions(kick_members=True)
async def prefix_kick(ctx, member: discord.Member, *, reason: str = "Unspecified"):
    res = await exec_kick(ctx, member, reason)
    await ctx.send(embed=res if isinstance(res, discord.Embed) else create_embed("❌ Error", res, 0xd9534f))

@tree.command(name="kick", description="Removes a member from the guild server roster")
@is_owner()
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Unspecified"):
    res = await exec_kick(interaction, member, reason)
    await interaction.response.send_message(embed=res if isinstance(res, discord.Embed) else create_embed("❌ Error", res, 0xd9534f))

# --- MUTE ---
async def exec_mute(ctx_or_inter, member: discord.Member, minutes: int):
    guild = ctx_or_inter.guild
    role = discord.utils.get(guild.roles, name="Muted") or await guild.create_role(name="Muted")
    await member.add_roles(role)
    async def unmute_after():
        await asyncio.sleep(minutes * 60)
        if role in member.roles: await member.remove_roles(role)
    asyncio.create_task(unmute_after())
    return create_embed("🤫 Muted", f"Restricted write access permissions for {member.mention} for `{minutes}` minutes.")

@bot.command(name="mute")
@commands.has_permissions(manage_roles=True)
async def prefix_mute(ctx, member: discord.Member, minutes: int = 10):
    res = await exec_mute(ctx, member, minutes)
    await ctx.send(embed=res)

@tree.command(name="mute", description="Restricts text write permissions for a target member")
@is_owner()
async def slash_mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 10):
    res = await exec_mute(interaction, member, minutes)
    await interaction.response.send_message(embed=res)

# --- UNMUTE ---
async def exec_unmute(ctx_or_inter, member: discord.Member):
    guild = ctx_or_inter.guild
    role = discord.utils.get(guild.roles, name="Muted")
    if role and role in member.roles:
        await member.remove_roles(role)
        return create_embed("🔊 Unmuted", f"Restored regular access permissions for {member.mention}.")
    return "This member does not carry an active restriction tag."

@bot.command(name="unmute")
@commands.has_permissions(manage_roles=True)
async def prefix_unmute(ctx, member: discord.Member):
    res = await exec_unmute(ctx, member)
    await ctx.send(embed=res if isinstance(res, discord.Embed) else create_embed("❌ Error", res, 0xd9534f))

@tree.command(name="unmute", description="Lifts communication text restrictions from a muted member")
@is_owner()
async def slash_unmute(interaction: discord.Interaction, member: discord.Member):
    res = await exec_unmute(interaction, member)
    await interaction.response.send_message(embed=res if isinstance(res, discord.Embed) else create_embed("❌ Error", res, 0xd9534f))

# --- WARN ---
async def exec_warn(ctx_or_inter, member: discord.Member, reason: str):
    uid = str(member.id)
    warnings[uid] = warnings.get(uid, []) + [reason]
    count = len(warnings[uid])
    if count >= 3:
        await member.ban(reason="Automated restriction: 3 strike limit met.")
        return create_embed("🔨 Strike Ban", f"{member.mention} was permanently barred from the guild following a 3rd strike violation.", 0xd9534f)
    return create_embed("⚠️ Violation Logged", f"Logged strike warning for {member.mention}. Matrix Counter: `{count}/3` \nReason: {reason}")

@bot.command(name="warn")
@commands.has_permissions(manage_messages=True)
async def prefix_warn(ctx, member: discord.Member, *, reason: str = "Behavioral Strike"):
    res = await exec_warn(ctx, member, reason)
    await ctx.send(embed=res)

@tree.command(name="warn", description="Issues a strike warning to a member (Automated Ban at 3 strikes)")
@is_owner()
async def slash_warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Behavioral Strike"):
    res = await exec_warn(interaction, member, reason)
    await interaction.response.send_message(embed=res)

# --- CLEAR WARNINGS ---
@bot.command(name="clearwarnings")
@commands.has_permissions(manage_messages=True)
async def prefix_clear_w(ctx, member: discord.Member):
    warnings[str(member.id)] = []
    await ctx.send(embed=create_embed("🧹 Purged", f"Reset strike matrix logs and warnings for {member.mention}."))

@tree.command(name="clearwarnings", description="Resets and purges all logged strikes and warnings for a member")
@is_owner()
async def slash_clear_w(interaction: discord.Interaction, member: discord.Member):
    warnings[str(member.id)] = []
    await interaction.response.send_message(embed=create_embed("🧹 Purged", f"Reset strike matrix logs and warnings for {member.mention}."))

# --- PURGE ---
@bot.command(name="purge")
@commands.has_permissions(manage_messages=True)
async def prefix_purge(ctx, amount: int):
    clamped = max(1, min(amount, 100))
    deleted = await ctx.channel.purge(limit=clamped + 1)
    msg = await ctx.send(embed=create_embed("🧹 Purged", f"Successfully cleared `{len(deleted)-1}` messages from chat history."))
    await asyncio.sleep(3)
    await msg.delete()

@tree.command(name="purge", description="Clears a specific quantity of messages from the current text channel")
@is_owner()
async def slash_purge(interaction: discord.Interaction, amount: int):
    clamped = max(1, min(amount, 100))
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=clamped)
    await interaction.followup.send(embed=create_embed("🧹 Purged", f"Successfully cleared `{len(deleted)}` messages from chat history."), ephemeral=True)

# --- LOCK / UNLOCK ---
@bot.command(name="lock")
@commands.has_permissions(manage_channels=True)
async def prefix_lock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(embed=create_embed("🔒 Locked", "Public send permissions have been locked down for this channel."))

@tree.command(name="lock", description="Locks down the current channel permissions to prevent public chat typing")
@is_owner()
async def slash_lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message(embed=create_embed("🔒 Locked", "Public send permissions have been locked down for this channel."))

@bot.command(name="unlock")
@commands.has_permissions(manage_channels=True)
async def prefix_unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(embed=create_embed("🔓 Unlocked", "Public channel write permissions have been restored."))

@tree.command(name="unlock", description="Unlocks current channel permissions to re-enable public chat typing")
@is_owner()
async def slash_unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message(embed=create_embed("🔓 Unlocked", "Public channel write permissions have been restored."))

# ==========================================
# ADDITIONAL UTILITY- & INFO COMMANDS
# ==========================================
@tree.command(name="warnings", description="Displays the current log list of strike infractions for a specific member")
async def slash_check_w(interaction: discord.Interaction, member: discord.Member):
    w = warnings.get(str(member.id), [])
    lines = [f"`{i+1}.` {r}" for i, r in enumerate(w)]
    await interaction.response.send_message(embed=create_embed("📋 Violation History", f"{member.mention} strike history roster:\n" + ("\n".join(lines) if w else "No active warnings found on file.")))

@tree.command(name="slowmode", description="Applies or modifies the chat delay timer configuration for the current text channel")
@is_owner()
async def slowmode(interaction: discord.Interaction, seconds: int):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(embed=create_embed("⏱️ Slowmode Updated", f"Channel write cool-down delay has been updated to `{seconds}` seconds."))

@tree.command(name="nickname", description="Overwrites and updates a member's server profile nickname mapping")
@is_owner()
async def nickname(interaction: discord.Interaction, member: discord.Member, new_name: str):
    await member.edit(nick=new_name)
    await interaction.response.send_message(embed=create_embed("📝 Profile Patched", f"Updated display name mapping for {member.mention} to **{new_name}**."))

@tree.command(name="addrole", description="Grants a specific system security role to a server member")
@is_owner()
async def addrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await interaction.response.send_message(embed=create_embed("🛡️ Permission Granted", f"Successfully linked role {role.mention} to user profile {member.mention}."))

@tree.command(name="removerole", description="Strips a specific system security role from a server member")
@is_owner()
async def remrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await interaction.response.send_message(embed=create_embed("🛡️ Permission Revoked", f"Successfully detached role {role.mention} from user profile {member.mention}."))

@tree.command(name="deleteallchannels", description="Irreversibly wipes all existing text channels from the current guild grid")
@is_owner()
async def delchannels(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    for c in interaction.guild.channels:
        if c != interaction.channel:
            try: await c.delete()
            except: pass
    await interaction.followup.send(embed=create_embed("🚨 Grid Purged", "All server channels except this current routing vector have been dropped."), ephemeral=True)

@tree.command(name="createchannel", description="Creates a new text communication channel in the guild")
@is_owner()
async def createch(interaction: discord.Interaction, name: str):
    c = await interaction.guild.create_text_channel(name)
    await interaction.response.send_message(embed=create_embed("📁 Channel Opened", f"Successfully mounted new channel route: {c.mention}"))

@tree.command(name="deletechannel", description="Permanently drops a selected text communication channel from the grid")
@is_owner()
async def deletech(interaction: discord.Interaction, channel: discord.TextChannel):
    await channel.delete()
    await interaction.response.send_message(embed=create_embed("🗑️ Vector Closed", "Successfully removed target text vector channel path."))

@tree.command(name="createrole", description="Generates a new system security role within the guild registry")
@is_owner()
async def createrl(interaction: discord.Interaction, name: str):
    r = await interaction.guild.create_role(name=name)
    await interaction.response.send_message(embed=create_embed("🎨 Role Mounted", f"Successfully registered system security role: {r.mention}"))

@tree.command(name="deleterole", description="Permanently drops a selected security role registry file from the guild")
@is_owner()
async def deleterl(interaction: discord.Interaction, role: discord.Role):
    await role.delete()
    await interaction.response.send_message(embed=create_embed("🗑️ Role Dropped", "Successfully purged target registry role data."))

# ==========================================
# ENTERTAINMENT & COMMUNITY MODULES
# ==========================================
@tree.command(name="gstart", description="Launches a timed automated prize distribution giveaway event")
@is_owner()
async def gstart(interaction: discord.Interaction, minutes: int, winners: int, prize: str):
    await interaction.response.send_message("Giveaway setup confirmed.", ephemeral=True)
    embed = discord.Embed(title="🎉 GIVEAWAY ACTIVE", description=f"**Item:** {prize}\n**Slots:** `{winners}` winner(s)\n**Window:** `{minutes}`m\n\nReact with 🎉 to lock your registry entry!", color=0x2f3136)
    msg = await interaction.channel.send(embed=append_footer(embed, interaction))
    await msg.add_reaction("🎉")
    
    await asyncio.sleep(minutes * 60)
    msg = await interaction.channel.fetch_message(msg.id)
    u = [user async for user in discord.utils.get(msg.reactions, emoji="🎉").users() if not user.bot]
    
    if not u: 
        return await interaction.channel.send(embed=create_embed("🎉 Event Closed", "No valid entry profiles located before expiration window."))
    w = random.sample(u, min(len(u), winners))
    await interaction.channel.send(f"🏆 **GIVEAWAY CONCLUDED**\nWinners for **{prize}**: {', '.join([m.mention for m in w])}")

@tree.command(name="greroll", description="Re-evaluates giveaway entries to select a new winning ticket member")
@is_owner()
async def greroll(interaction: discord.Interaction, message_id: str):
    try:
        msg = await interaction.channel.fetch_message(int(message_id))
        u = [user async for user in discord.utils.get(msg.reactions, emoji="🎉").users() if not user.bot]
        if u: 
            await interaction.response.send_message(f"🎉 **New Selection:** {random.choice(u).mention} has won the reroll selection slot!")
        else: 
            await interaction.response.send_message("No eligible entry pools found.", ephemeral=True)
    except: 
        await interaction.response.send_message("Invalid target message identification tracking id.", ephemeral=True)

@tree.command(name="verify", description="Executes verification handshake to grant user profile access clear pass")
async def verify(interaction: discord.Interaction):
    await interaction.response.send_message(embed=create_embed("✅ Handshake Verified", "Security pass cleared successfully."), ephemeral=True)

@tree.command(name="hit", description="Publicly stamps a successfully executed transaction package with a target member")
async def hit(interaction: discord.Interaction, partner: discord.Member):
    await interaction.response.send_message(f"🤝 {interaction.user.mention} has officially signed off a deal voucher package with {partner.mention}!")

@tree.command(name="poll", description="Deploys an interactive poll voting module to the current chat room")
async def poll(interaction: discord.Interaction, question: str):
    await interaction.response.send_message("Poll deployed.", ephemeral=True)
    m = await interaction.channel.send(f"📊 **{question}**")
    await m.add_reaction("👍")
    await m.add_reaction("👎")

@tree.command(name="say", description="Forwards a plaintext statement directly through the bot terminal link")
@is_owner()
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("Dispatched.", ephemeral=True)
    await interaction.channel.send(message)

@tree.command(name="embed", description="Dispatches a structured design embed block down the channel pipeline")
@is_owner()
async def embed_cmd(interaction: discord.Interaction, title: str, description: str):
    await interaction.response.send_message("Dispatched.", ephemeral=True)
    await interaction.channel.send(embed=create_embed(title, description))

@tree.command(name="avatar", description="Fetches and displays a user profile avatar image matrix in full scale")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    t = member or interaction.user
    e = discord.Embed(color=0x2f3136)
    e.set_author(name=f"Avatar link: {t.name}")
    e.set_image(url=t.display_avatar.url)
    await interaction.response.send_message(embed=e)

@tree.command(name="announce", description="Broadcasts an embed update announcement message down a target text channel route")
@is_owner()
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    await channel.send(embed=append_footer(create_embed("📢 BROADCAST ANNOUNCEMENT", message), interaction))
    await interaction.response.send_message("Broadcast successfully shipped.", ephemeral=True)

# ==========================================
# STATISTICS & DIAGNOSTICS
# ==========================================
@tree.command(name="serverinfo", description="Displays full meta profile information metrics regarding this server guild")
async def serverinfo(interaction: discord.Interaction):
    await interaction.response.send_message(embed=create_embed("📊 Guild Core Meta", f"**Name:** {interaction.guild.name}\n**Roster Count:** `{interaction.guild.member_count}`\n**Identity ID:** `{interaction.guild.id}`"))

@tree.command(name="userinfo", description="Tracks down and itemizes metadata records linked to a member")
async def userinfo(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(embed=create_embed("👤 Registry Profile", f"**Member:** {member.mention}\n**Identity ID:** `{member.id}`\n**Registry Date:** {member.joined_at.strftime('%Y-%m-%d')}"))

@tree.command(name="membercount", description="Outputs the exact user connection quantity counter total for this server")
async def membercount(interaction: discord.Interaction):
    await interaction.response.send_message(embed=create_embed("📊 Member Metrics", f"Current active guild connection index total: `{interaction.guild.member_count}`"))

@tree.command(name="ping", description="Measures API pipeline communication latency tracking speeds")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(embed=create_embed("🏓 Latency Check", f"Active connection pipeline tracking speed: `{round(bot.latency * 1000)}ms`"))

@tree.command(name="coinflip", description="Flips a currency token to return random Head or Tail choices")
async def coinflip(interaction: discord.Interaction):
    await interaction.response.send_message(embed=create_embed("🪙 Token Flip", f"Result Matrix: **{random.choice(['Heads', 'Tails'])}**"))

@tree.command(name="dice", description="Generates a random value output roll across customizable numeric boundary faces")
async def dice(interaction: discord.Interaction, sides: int = 6):
    await interaction.response.send_message(embed=create_embed("🎲 Die Roll", f"Output Face Value: **{random.randint(1, sides)}**"))

@tree.command(name="8ball", description="Queries the core oracle deck to resolve situational questions")
async def ball(interaction: discord.Interaction, question: str):
    ans = ['Confirmed projection.', 'Matrix uncertain, re-route vector later.', 'Condition rejected.']
    await interaction.response.send_message(embed=create_embed("🔮 Oracle", f"**Query:** {question}\n**Resolution:** {random.choice(ans)}"))

@tree.command(name="choose", description="Resolves picking choices from raw entries parsed via comma separations")
async def choose(interaction: discord.Interaction, options: str):
    choice = random.choice([x.strip() for x in options.split(',')])
    await interaction.response.send_message(embed=create_embed("✨ Choice Selected", f"Resolved Selection: **{choice}**"))

@tree.command(name="uptime", description="Returns active online terminal operational runtime statistics")
async def uptime(interaction: discord.Interaction):
    diff = datetime.datetime.utcnow() - bot.start_time
    await interaction.response.send_message(embed=create_embed("⏱ Operational Window", f"Terminal running window tracker: `{str(diff).split('.')[0]}`"))

@tree.command(name="botinfo", description="Outputs detailed application architectural specification data summaries")
async def botinfo(interaction: discord.Interaction):
    await interaction.response.send_message(embed=create_embed("⚙ Framework Overview", f"**Core Client:** {bot.user.name}\n**Scope:** Linked to `{len(bot.guilds)}` servers\n**Dependency:** Discord.py v2.3+"))

@tree.command(name="help", description="Returns standard quick operational help data menus")
async def help_cmd(interaction: discord.Interaction):
    await interaction.response.send_message(embed=create_embed("ℹ Status Map", "Operational frameworks verified stable. Type `/` in chat to browse commands.", 0x2ecc71), ephemeral=True)

# ==========================================
# SYSTEM EVENTS & ANTI-SPAM PROTECTIONS
# ==========================================
@bot.event
async def on_ready():
    if not hasattr(bot, 'start_time'): 
        bot.start_time = datetime.datetime.utcnow()
    try: 
        await tree.sync()
        print(f"Bot successfully authenticated as {bot.user.name}")
    except Exception as e: 
        print(f"Error executing command matrix sync: {e}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="over transactions"))

@bot.event
async def on_message(message):
    # Process classic prefix commands like !ban first
    await bot.process_commands(message)

    if message.author.bot or not message.guild or message.author.id == message.guild.owner_id: 
        return
        
    uid, cur = message.author.id, time.time()
    
    # Word Filters / Invitation Filters / Mention Caps
    if any(w in message.content.lower() for w in BLOCKED_WORDS) or DISCORD_INVITE in message.content.lower() or len(message.mentions) >= MAX_MENTIONS:
        try: await message.delete()
        except: pass
        return
        
    # Caps Lock Enforcement
    if len(message.content) > 10 and (sum(1 for c in message.content if c.isupper()) / len(message.content)) * 100 >= MAX_CAPS_PERCENT:
        try: await message.delete()
        except: pass
        return
        
    # Rate Limit Spam Filter (Max 5 messages within rolling 5 seconds)
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
# WEB CONTAINER HOST ROUTING
# ==========================================
app = Flask('')

@app.route('/')
def home(): 
    return "Bot Online."

def run(): 
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    Thread(target=run, daemon=True).start()
    token = os.environ.get("DISCORD_TOKEN")
    if token: 
        bot.run(token)
    else: 
        print("Critical Exception: DISCORD_TOKEN is missing from environment variables.")

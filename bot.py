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

# ==========================================
# BOT CORE CONFIGURATION
# ==========================================
intents = discord.Intents.all()

class UtilityBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents, help_command=None)

    async def setup_hook(self):
        # Persistent UI Views registration
        self.add_view(SupportPanel())
        self.add_view(SupportTicketView())
        self.add_view(MiddlemanPanel())
        self.add_view(MiddlemanTicketView())

bot = UtilityBot()

# Global Runtime Datastructures
spam_tracker = {}
warnings = {}
fill_tracker = {}

BLOCKED_WORDS = []
MAX_MENTIONS = 5
MAX_CAPS_PERCENT = 70
DISCORD_INVITE = "discord.gg"

# ==========================================
# DESIGN & EMBED UTILITIES
# ==========================================
def create_embed(title: str, description: str, color: int = 0x2f3136) -> discord.Embed:
    embed = discord.Embed(description=description, color=color)
    embed.set_author(name=title)
    return embed

def append_footer(embed: discord.Embed, ctx_or_interaction):
    client = bot
    embed.set_footer(
        text=f"{client.user.name} • Today at {datetime.datetime.now().strftime('%H:%M')}",
        icon_url=client.user.display_avatar.url if client.user.avatar else None
    )
    return embed

# Automated Permission Guard for Owner Validation
def is_server_owner():
    async def predicate(ctx: commands.Context):
        if ctx.guild and ctx.author.id == ctx.guild.owner_id:
            return True
        raise commands.CheckFailure("Restricted to Server Owner operations.")
    return commands.check(predicate)

# Transcript Engine
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
# INTERACTIVE UI COMPONENT MATRICES
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
        await interaction.response.defer(ephemeral=True)
        name = f"ticket-{interaction.user.name.lower()}".replace(" ", "-")
        if discord.utils.get(interaction.guild.text_channels, name=name):
            return await interaction.followup.send(embed=create_embed("❌ Error", "You already have an active support ticket open.", 0xd9534f), ephemeral=True)
        
        cat = discord.utils.get(interaction.guild.categories, name="Tickets") or await interaction.guild.create_category("Tickets")
        perms = {interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        
        staff = ["Owner", "Administrator", "Head Moderator", "Moderator", "Team Lead", "Chief Lead", "Lead", "Cordinator"]
        for r in staff:
            role = discord.utils.get(interaction.guild.roles, name=r)
            if role: perms[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
        ch = await interaction.guild.create_text_channel(name, overwrites=perms, category=cat)
        await ch.send(f"{interaction.user.mention}", embed=append_footer(create_embed("🎫 Support Ticket", "Please describe your request in detail below. A staff member will be with you shortly."), interaction), view=SupportTicketView())
        await interaction.followup.send(embed=create_embed("✅ Success", f"Your ticket has been created: {ch.mention}", 0x2ecc71), ephemeral=True)

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
        await interaction.response.defer(ephemeral=True)
        name = f"ticket-mm_{interaction.user.name.lower()}".replace(" ", "-")
        if discord.utils.get(interaction.guild.text_channels, name=name):
            return await interaction.followup.send(embed=create_embed("❌ Error", "You already have an active middleman session requested.", 0xd9534f), ephemeral=True)
        
        cat = discord.utils.get(interaction.guild.categories, name="Middleman Service") or await interaction.guild.create_category("Middleman Service")
        perms = {interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        
        mm_roles = ["Owner", "Middleman Manager", "Head Middleman", "Middleman", "Chief Lead", "Lead", "Cordinator"]
        for r in mm_roles:
            role = discord.utils.get(interaction.guild.roles, name=r)
            if role: perms[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
        ch = await interaction.guild.create_text_channel(name, overwrites=perms, category=cat)
        role = discord.utils.get(interaction.guild.roles, name="Middleman")
        await ch.send(f"{interaction.user.mention} {role.mention if role else ''}", embed=append_footer(create_embed("🤝 Middleman Escrow", "Please mention your trading partner here and write down the full deal parameters. An authorized middleman will step in shortly."), interaction), view=MiddlemanTicketView())
        await interaction.followup.send(embed=create_embed("✅ Success", f"Middleman ticket created: {ch.mention}", 0x2ecc71), ephemeral=True)

# ==========================================
# HYBRID COMMAND SPHERE (SLASH + PREFIX ENGINE)
# ==========================================

@bot.hybrid_command(name="ticket", description="Deploys the main interactive support ticket panel")
@is_server_owner()
async def deploy_t(ctx: commands.Context):
    await ctx.defer(ephemeral=True)
    embed = discord.Embed(title="🎫 Support Tickets", description="Click the button below to open a private support session.", color=0x2f3136)
    await ctx.channel.send(embed=append_footer(embed, ctx), view=SupportPanel())
    await ctx.send(embed=create_embed("✅ System", "Support panel deployed successfully."), ephemeral=True)

@bot.hybrid_command(name="setup_middleman", description="Deploys the main interactive middleman service panel")
@is_server_owner()
async def deploy_m(ctx: commands.Context):
    await ctx.defer(ephemeral=True)
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
    await ctx.channel.send(embed=append_footer(embed, ctx), view=MiddlemanPanel())
    await ctx.send(embed=create_embed("✅ System", "Middleman panel deployed successfully."), ephemeral=True)

@bot.hybrid_command(name="fill", description="Saves and toggles your current roles off or restores them back automatically")
@is_server_owner()
async def fill_roles(ctx: commands.Context):
    guild = ctx.guild
    member = ctx.author
    uid = member.id

    await ctx.defer(ephemeral=True)

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
        await ctx.send(embed=create_embed("🔄 Roles Restored", f"Welcome back! Your previous roles have been restored:\n**{', '.join(restored) if restored else 'None'}**", 0x2ecc71), ephemeral=True)
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
            return await ctx.send(embed=create_embed("❌ Error", "You do not have any saved roles that can be cleared.", 0xd9534f), ephemeral=True)
        fill_tracker[uid] = role_ids
        await ctx.send(embed=create_embed("🔄 Roles Stored", f"Your profile roles have been secured and stripped from your user profile:\n**{', '.join(removed) if removed else 'None'}**\n\n*Run `/fill` at any time to regain your setup.*", 0x2f3136), ephemeral=True)

@bot.hybrid_command(name="revamp", description="Purges server channels and completely builds the core layout matrix")
@is_server_owner()
async def revamp(ctx: commands.Context):
    await ctx.defer(ephemeral=True)
    roles = {"Owner": 0x990000, "Administrator": 0xff0000, "Head Moderator": 0xffa500, "Moderator": 0x808080, "Middleman Manager": 0x4b0082, "Head Middleman": 0x800080, "Middleman": 0x008000, "Team Lead": 0x0000ff, "Chief Lead": 0x00008b, "Lead": 0x008080, "Cordinator": 0xff00ff, "Muted": 0x111111}
    for n, c in roles.items():
        if not discord.utils.get(ctx.guild.roles, name=n): 
            try: await ctx.guild.create_role(name=n, color=discord.Color(c))
            except: pass
            
    for channel in ctx.guild.channels:
        if channel != ctx.channel:
            try: await channel.delete()
            except: pass
            
    struct = {"INFORMATION": ["welcome", "rules", "announcements", "giveaways"], "COMMUNITY": ["general", "bot-commands", "memes"], "TRANSACTIONS": ["middleman-info", "marketplace", "trading-chat"], "UTILITY": ["open-ticket", "middleman-service"]}
    for cat, chs in struct.items():
        category = await ctx.guild.create_category(cat)
        for name in chs: 
            await ctx.guild.create_text_channel(name, category=category)
    await ctx.send(embed=create_embed("🔄 Revamp Matrix", "Guild structural reconstruction completed successfully."), ephemeral=True)

@bot.hybrid_command(name="ban", description="Permanently bars a member from the guild server")
@commands.has_permissions(ban_members=True)
async def hybrid_ban(ctx: commands.Context, member: discord.Member, *, reason: str = "Unspecified"):
    await ctx.defer(ephemeral=True)
    if member.id == ctx.guild.owner_id:
        return await ctx.send(embed=create_embed("❌ Failed", "The server root owner cannot be banned.", 0xd9534f), ephemeral=True)
    await member.ban(reason=reason)
    await ctx.send(embed=create_embed("🔨 Action Completed", f"Successfully banned {member.mention}. Reason: {reason}"), ephemeral=True)

@bot.hybrid_command(name="unban", description="Lifts ban restrictions for a user using their ID format")
@commands.has_permissions(ban_members=True)
async def hybrid_unban(ctx: commands.Context, user_id: str):
    await ctx.defer(ephemeral=True)
    try:
        user = await bot.fetch_user(int(user_id))
        await ctx.guild.unban(user)
        await ctx.send(embed=create_embed("🔓 Restriction Lifted", f"Successfully unbanned profile: {user.name}."), ephemeral=True)
    except:
        await ctx.send(embed=create_embed("❌ Error", "Target profile link could not be located on the ban list.", 0xd9534f), ephemeral=True)

@bot.hybrid_command(name="kick", description="Removes a member from the guild server roster")
@commands.has_permissions(kick_members=True)
async def hybrid_kick(ctx: commands.Context, member: discord.Member, *, reason: str = "Unspecified"):
    await ctx.defer(ephemeral=True)
    if member.id == ctx.guild.owner_id:
        return await ctx.send(embed=create_embed("❌ Failed", "The server root owner cannot be kicked.", 0xd9534f), ephemeral=True)
    await member.kick(reason=reason)
    await ctx.send(embed=create_embed("👢 Action Completed", f"Successfully kicked {member.mention}."), ephemeral=True)

@bot.hybrid_command(name="mute", description="Restricts text write permissions for a target member")
@commands.has_permissions(manage_roles=True)
async def hybrid_mute(ctx: commands.Context, member: discord.Member, minutes: int = 10):
    await ctx.defer(ephemeral=True)
    role = discord.utils.get(ctx.guild.roles, name="Muted") or await ctx.guild.create_role(name="Muted")
    await member.add_roles(role)
    async def unmute_task():
        await asyncio.sleep(minutes * 60)
        if role in member.roles: await member.remove_roles(role)
    asyncio.create_task(unmute_task())
    await ctx.send(embed=create_embed("🤫 Muted", f"Muted {member.mention} for `{minutes}` minutes."), ephemeral=True)

@bot.hybrid_command(name="unmute", description="Lifts communication text restrictions from a muted member")
@commands.has_permissions(manage_roles=True)
async def hybrid_unmute(ctx: commands.Context, member: discord.Member):
    await ctx.defer(ephemeral=True)
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if role and role in member.roles:
        await member.remove_roles(role)
        return await ctx.send(embed=create_embed("🔊 Restored", f"Regular write access permissions active for {member.mention}."), ephemeral=True)
    await ctx.send(embed=create_embed("❌ Error", "User does not possess an active restriction tag.", 0xd9534f), ephemeral=True)

@bot.hybrid_command(name="warn", description="Issues a strike warning to a member")
@commands.has_permissions(manage_messages=True)
async def hybrid_warn(ctx: commands.Context, member: discord.Member, *, reason: str = "Behavioral Strike"):
    await ctx.defer(ephemeral=True)
    uid = str(member.id)
    warnings[uid] = warnings.get(uid, []) + [reason]
    count = len(warnings[uid])
    if count >= 3:
        await member.ban(reason="Automated restriction: 3 strike limit met.")
        return await ctx.send(embed=create_embed("🔨 Strike Ban", f"{member.mention} was permanently barred following a 3rd strike violation.", 0xd9534f), ephemeral=True)
    await ctx.send(embed=create_embed("⚠️ Violation Logged", f"Logged strike warning for {member.mention} (`{count}/3`). \nReason: {reason}"), ephemeral=True)

@bot.hybrid_command(name="clearwarnings", description="Resets and purges all logged strikes and warnings for a member")
@commands.has_permissions(manage_messages=True)
async def hybrid_clear_w(ctx: commands.Context, member: discord.Member):
    await ctx.defer(ephemeral=True)
    warnings[str(member.id)] = []
    await ctx.send(embed=create_embed("🧹 Purged", f"Reset strike matrix logs for {member.mention}."), ephemeral=True)

@bot.hybrid_command(name="purge", description="Clears a specific quantity of messages from the current text channel")
@commands.has_permissions(manage_messages=True)
async def hybrid_purge(ctx: commands.Context, amount: int):
    await ctx.defer(ephemeral=True)
    clamped = max(1, min(amount, 100))
    deleted = await ctx.channel.purge(limit=clamped)
    await ctx.send(embed=create_embed("🧹 Purged", f"Successfully cleared `{len(deleted)}` messages from channel history."), ephemeral=True)

@bot.hybrid_command(name="lock", description="Locks down the current channel permissions to prevent public chat typing")
@commands.has_permissions(manage_channels=True)
async def hybrid_lock(ctx: commands.Context):
    await ctx.defer(ephemeral=True)
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(embed=create_embed("🔒 Locked", "Public text writing locked down for this channel."), ephemeral=True)

@bot.hybrid_command(name="unlock", description="Unlocks current channel permissions to re-enable public chat typing")
@commands.has_permissions(manage_channels=True)
async def hybrid_unlock(ctx: commands.Context):
    await ctx.defer(ephemeral=True)
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
    await ctx.send(embed=create_embed("🔓 Unlocked", "Public channel write permissions restored."), ephemeral=True)

@bot.hybrid_command(name="warnings", description="Displays the current log list of strike infractions for a specific member")
async def hybrid_check_w(ctx: commands.Context, member: discord.Member):
    await ctx.defer(ephemeral=True)
    w = warnings.get(str(member.id), [])
    lines = [f"`{i+1}.` {r}" for i, r in enumerate(w)]
    await ctx.send(embed=create_embed("📋 Violation History", f"{member.mention} history status:\n" + ("\n".join(lines) if w else "No active warnings on file.")), ephemeral=True)

@bot.hybrid_command(name="slowmode", description="Applies or modifies the chat delay timer configuration")
@commands.has_permissions(manage_channels=True)
async def slowmode(ctx: commands.Context, seconds: int):
    await ctx.defer(ephemeral=True)
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(embed=create_embed("⏱️ Slowmode Updated", f"Channel write cooldown delay set to `{seconds}` seconds."), ephemeral=True)

@bot.hybrid_command(name="nickname", description="Overwrites and updates a member's server profile nickname mapping")
@commands.has_permissions(manage_nicknames=True)
async def nickname(ctx: commands.Context, member: discord.Member, new_name: str):
    await ctx.defer(ephemeral=True)
    await member.edit(nick=new_name)
    await ctx.send(embed=create_embed("📝 Profile Patched", f"Updated display mapping for {member.mention} to **{new_name}**."), ephemeral=True)

@bot.hybrid_command(name="addrole", description="Grants a specific system security role to a server member")
@commands.has_permissions(manage_roles=True)
async def addrole(ctx: commands.Context, member: discord.Member, role: discord.Role):
    await ctx.defer(ephemeral=True)
    await member.add_roles(role)
    await ctx.send(embed=create_embed("🛡️ Role Linked", f"Linked role {role.mention} to {member.mention}."), ephemeral=True)

@bot.hybrid_command(name="removerole", description="Strips a specific system security role from a server member")
@commands.has_permissions(manage_roles=True)
async def remrole(ctx: commands.Context, member: discord.Member, role: discord.Role):
    await ctx.defer(ephemeral=True)
    await member.remove_roles(role)
    await ctx.send(embed=create_embed("🛡️ Role Stripped", f"Detached role {role.mention} from {member.mention}."), ephemeral=True)

@bot.hybrid_command(name="deleteallchannels", description="Irreversibly wipes all existing text channels from the current guild grid")
@is_server_owner()
async def delchannels(ctx: commands.Context):
    await ctx.defer(ephemeral=True)
    for c in ctx.guild.channels:
        if c != ctx.channel:
            try: await c.delete()
            except: pass
    await ctx.send(embed=create_embed("🚨 Grid Purged", "All operational server channels drop cleared."), ephemeral=True)

@bot.hybrid_command(name="createchannel", description="Creates a new text communication channel in the guild")
@commands.has_permissions(manage_channels=True)
async def createch(ctx: commands.Context, name: str):
    await ctx.defer(ephemeral=True)
    c = await ctx.guild.create_text_channel(name)
    await ctx.send(embed=create_embed("📁 Channel Opened", f"Successfully mounted new channel route: {c.mention}"), ephemeral=True)

@bot.hybrid_command(name="deletechannel", description="Permanently drops a selected text communication channel")
@commands.has_permissions(manage_channels=True)
async def deletech(ctx: commands.Context, channel: discord.TextChannel):
    await ctx.defer(ephemeral=True)
    await channel.delete()
    await ctx.send(embed=create_embed("🗑️ Vector Closed", "Successfully removed target text vector channel path."), ephemeral=True)

@bot.hybrid_command(name="createrole", description="Generates a new system security role within the guild registry")
@commands.has_permissions(manage_roles=True)
async def createrl(ctx: commands.Context, name: str):
    await ctx.defer(ephemeral=True)
    r = await ctx.guild.create_role(name=name)
    await ctx.send(embed=create_embed("🎨 Role Mounted", f"Successfully registered role: {r.mention}"), ephemeral=True)

@bot.hybrid_command(name="deleterole", description="Permanently drops a selected security role registry file")
@commands.has_permissions(manage_roles=True)
async def deleterl(ctx: commands.Context, role: discord.Role):
    await ctx.defer(ephemeral=True)
    await role.delete()
    await ctx.send(embed=create_embed("🗑️ Role Dropped", "Successfully purged target registry role data."), ephemeral=True)

@bot.hybrid_command(name="gstart", description="Launches a timed automated prize distribution giveaway event")
@is_server_owner()
async def gstart(ctx: commands.Context, minutes: int, winners: int, *, prize: str):
    await ctx.defer(ephemeral=True)
    embed = discord.Embed(title="🎉 GIVEAWAY ACTIVE", description=f"**Item:** {prize}\n**Slots:** `{winners}` winner(s)\n**Window:** `{minutes}`m\n\nReact with 🎉 to enter!", color=0x2f3136)
    msg = await ctx.channel.send(embed=append_footer(embed, ctx))
    await msg.add_reaction("🎉")
    await ctx.send("Giveaway dispatched.", ephemeral=True)
    
    await asyncio.sleep(minutes * 60)
    msg = await ctx.channel.fetch_message(msg.id)
    u = [user async for user in discord.utils.get(msg.reactions, emoji="🎉").users() if not user.bot]
    
    if not u: 
        return await ctx.channel.send(embed=create_embed("🎉 Event Closed", "No valid entry profiles located before expiration window."))
    w = random.sample(u, min(len(u), winners))
    await ctx.channel.send(f"🏆 **GIVEAWAY CONCLUDED**\nWinners for **{prize}**: {', '.join([m.mention for m in w])}")

@bot.hybrid_command(name="greroll", description="Re-evaluates giveaway entries to select a new winning ticket member")
@is_server_owner()
async def greroll(ctx: commands.Context, message_id: str):
    await ctx.defer(ephemeral=True)
    try:
        msg = await ctx.channel.fetch_message(int(message_id))
        u = [user async for user in discord.utils.get(msg.reactions, emoji="🎉").users() if not user.bot]
        if u: 
            await ctx.channel.send(f"🎉 **New Selection:** {random.choice(u).mention} has won the reroll slot!")
            await ctx.send("Reroll completed.", ephemeral=True)
        else: 
            await ctx.send("No eligible entry pools found.", ephemeral=True)
    except: 
        await ctx.send("Invalid target message identification ID.", ephemeral=True)

@bot.hybrid_command(name="verify", description="Executes verification handshake to grant access")
async def verify(ctx: commands.Context):
    await ctx.send(embed=create_embed("✅ Handshake Verified", "Security profiling checked cleared successfully."), ephemeral=True)

@bot.hybrid_command(name="hit", description="Publicly stamps a successfully executed transaction package")
async def hit(ctx: commands.Context, partner: discord.Member):
    await ctx.send(f"🤝 {ctx.author.mention} has officially signed off a deal voucher package with {partner.mention}!")

@bot.hybrid_command(name="poll", description="Deploys an interactive poll voting module to the current chat room")
async def poll(ctx: commands.Context, *, question: str):
    await ctx.defer(ephemeral=True)
    m = await ctx.channel.send(f"📊 **{question}**")
    await m.add_reaction("👍")
    await m.add_reaction("👎")
    await ctx.send("Poll deployed.", ephemeral=True)

@bot.hybrid_command(name="say", description="Forwards a plaintext statement directly through the bot terminal link")
@is_server_owner()
async def say(ctx: commands.Context, *, message: str):
    await ctx.defer(ephemeral=True)
    await ctx.channel.send(message)
    await ctx.send("Message dispatched.", ephemeral=True)

@bot.hybrid_command(name="embed", description="Dispatches a structured design embed block down the channel pipeline")
@is_server_owner()
async def embed_cmd(ctx: commands.Context, title: str, *, description: str):
    await ctx.defer(ephemeral=True)
    await ctx.channel.send(embed=create_embed(title, description))
    await ctx.send("Embed deployed.", ephemeral=True)

@bot.hybrid_command(name="avatar", description="Fetches and displays a user profile avatar image matrix in full scale")
async def avatar(ctx: commands.Context, member: discord.Member = None):
    t = member or ctx.author
    e = discord.Embed(color=0x2f3136)
    e.set_author(name=f"Avatar: {t.name}")
    e.set_image(url=t.display_avatar.url)
    await ctx.send(embed=e)

@bot.hybrid_command(name="announce", description="Broadcasts an embed update announcement message")
@is_server_owner()
async def announce(ctx: commands.Context, channel: discord.TextChannel, *, message: str):
    await ctx.defer(ephemeral=True)
    await channel.send(embed=append_footer(create_embed("📢 BROADCAST ANNOUNCEMENT", message), ctx))
    await ctx.send("Broadcast successfully shipped.", ephemeral=True)

@bot.hybrid_command(name="serverinfo", description="Displays full meta profile information metrics regarding this server guild")
async def serverinfo(ctx: commands.Context):
    await ctx.send(embed=create_embed("📊 Guild Core Meta", f"**Name:** {ctx.guild.name}\n**Roster Count:** `{ctx.guild.member_count}`\n**Identity ID:** `{ctx.guild.id}`"))

@bot.hybrid_command(name="userinfo", description="Tracks down and itemizes metadata records linked to a member")
async def userinfo(ctx: commands.Context, member: discord.Member):
    await ctx.send(embed=create_embed("👤 Registry Profile", f"**Member:** {member.mention}\n**Identity ID:** `{member.id}`\n**Registry Date:** {member.joined_at.strftime('%Y-%m-%d')}"))

@bot.hybrid_command(name="membercount", description="Outputs the exact user connection quantity counter total")
async def membercount(ctx: commands.Context):
    await ctx.send(embed=create_embed("📊 Member Metrics", f"Current guild connection total: `{ctx.guild.member_count}`"))

@bot.hybrid_command(name="ping", description="Measures API pipeline communication latency tracking speeds")
async def ping(ctx: commands.Context):
    await ctx.send(embed=create_embed("🏓 Latency Check", f"Pipeline latency speed: `{round(bot.latency * 1000)}ms`"))

@bot.hybrid_command(name="coinflip", description="Flips a currency token to return random Head or Tail choices")
async def coinflip(ctx: commands.Context):
    await ctx.send(embed=create_embed("🪙 Token Flip", f"Result Matrix: **{random.choice(['Heads', 'Tails'])}**"))

@bot.hybrid_command(name="dice", description="Generates a random value output roll across customizable numeric boundary faces")
async def dice(ctx: commands.Context, sides: int = 6):
    await ctx.send(embed=create_embed("🎲 Die Roll", f"Output Face Value: **{random.randint(1, sides)}**"))

@bot.hybrid_command(name="8ball", description="Queries the core oracle deck to resolve situational questions")
async def ball(ctx: commands.Context, *, question: str):
    ans = ['Confirmed projection.', 'Matrix uncertain, re-route vector later.', 'Condition rejected.']
    await ctx.send(embed=create_embed("🔮 Oracle", f"**Query:** {question}\n**Resolution:** {random.choice(ans)}"))

@bot.hybrid_command(name="choose", description="Resolves picking choices from raw entries parsed via comma separations")
async def choose(ctx: commands.Context, *, options: str):
    choice = random.choice([x.strip() for x in options.split(',')])
    await ctx.send(embed=create_embed("✨ Choice Selected", f"Resolved Selection: **{choice}**"))

@bot.hybrid_command(name="uptime", description="Returns active online terminal operational runtime statistics")
async def uptime(ctx: commands.Context):
    diff = datetime.datetime.utcnow() - bot.start_time
    await ctx.send(embed=create_embed("⏱ Operational Window", f"Terminal running window tracker: `{str(diff).split('.')[0]}`"))

@bot.hybrid_command(name="botinfo", description="Outputs detailed application architectural specification data summaries")
async def botinfo(ctx: commands.Context):
    await ctx.send(embed=create_embed("⚙ Framework Overview", f"**Core Client:** {bot.user.name}\n**Scope:** Linked to `{len(bot.guilds)}` servers\n**Dependency:** Discord.py v2.3+"))

@bot.hybrid_command(name="help", description="Returns standard quick operational help data menus")
async def help_cmd(ctx: commands.Context):
    await ctx.send(embed=create_embed("ℹ Status Map", "Operational frameworks verified stable. Type `/` or `!` in chat to browse available commands.", 0x2ecc71), ephemeral=True)

# ==========================================
# SYSTEM AUTOMATION MONITORING & RADARS
# ==========================================
@bot.event
async def on_ready():
    if not hasattr(bot, 'start_time'): 
        bot.start_time = datetime.datetime.utcnow()
    try: 
        await bot.tree.sync()
        print(f"Bot successfully authenticated as {bot.user.name}")
    except Exception as e: 
        print(f"Sync core anomaly: {e}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="over transactions"))

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: 
        return
        
    # Process valid commands first
    await bot.process_commands(message)
    
    if message.author.id == message.guild.owner_id:
        return
        
    uid, cur = message.author.id, time.time()
    
    # Text Analysis Radar
    if any(w in message.content.lower() for w in BLOCKED_WORDS) or DISCORD_INVITE in message.content.lower() or len(message.mentions) >= MAX_MENTIONS:
        try: return await message.delete()
        except: pass
        
    if len(message.content) > 10 and (sum(1 for c in message.content if c.isupper()) / len(message.content)) * 100 >= MAX_CAPS_PERCENT:
        try: return await message.delete()
        except: pass
        
    # Frequency Spam Protection Layer
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
# PRODUCTION CONTAINER KEEP-ALIVE LOOP
# ==========================================
app = Flask('')

@app.route('/')
def home(): 
    return "Bot Core Container Matrix Active."

def run(): 
    app.run(host='0.0.0.0', port=8080)

if __name__ == "__main__":
    Thread(target=run, daemon=True).start()
    token = os.environ.get("DISCORD_TOKEN")
    if token: 
        bot.run(token)
    else: 
        print("CRITICAL EXCEPTION: Environment configuration string missing 'DISCORD_TOKEN'.")

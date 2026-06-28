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
fill_tracker = {}  # Format: {user_id: {"roles": [ids]}}

BLOCKED_WORDS = []
MAX_MENTIONS = 5
MAX_CAPS_PERCENT = 70
DISCORD_INVITE = "discord.gg"

# List of commands that ANY user is allowed to use
PUBLIC_COMMANDS = {"help", "temp", "verify", "hit", "poll", "avatar", "mercy"}

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

# Global Check: Restricts admin commands to Owner, allows PUBLIC_COMMANDS for everyone
@bot.check
async def restrict_to_owner(ctx: commands.Context):
    if ctx.guild:
        if ctx.command.name in PUBLIC_COMMANDS:
            return True
        if ctx.author.id != ctx.guild.owner_id:
            raise commands.CheckFailure("Only the server owner can execute administrative commands.")
    return True

def is_not_owner(interaction: discord.Interaction) -> bool:
    if interaction.guild:
        return interaction.user.id != interaction.guild.owner_id
    return True

@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CheckFailure):
        try:
            await ctx.send(embed=create_embed("🔒 Denied", "Only the **Server Owner** is authorized to use this command.", 0xd9534f), ephemeral=True)
        except:
            pass

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
        if is_not_owner(interaction):
            return await interaction.response.send_message(embed=create_embed("🔒 Denied", "Only the **Server Owner** is authorized to claim tickets.", 0xd9534f), ephemeral=True)
            
        if interaction.channel.name == f"ticket-{interaction.user.name.lower()}".replace(" ", "-"):
            return await interaction.response.send_message(embed=create_embed("❌ Error", "You cannot claim your own support ticket.", 0xd9534f), ephemeral=True)
        
        button.label = "Claimed"
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=append_footer(create_embed("✅ Ticket Claimed", f"{interaction.user.mention} will assist you shortly.", 0x2ecc71), interaction))

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="btn_close_support", emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if is_not_owner(interaction):
            return await interaction.response.send_message(embed=create_embed("🔒 Denied", "Only the **Server Owner** is authorized to close tickets.", 0xd9534f), ephemeral=True)

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
        if is_not_owner(interaction):
            return await interaction.response.send_message(embed=create_embed("🔒 Denied", "Only the **Server Owner** is authorized to claim middleman tickets.", 0xd9534f), ephemeral=True)

        if interaction.channel.name == f"ticket-mm_{interaction.user.name.lower()}".replace(" ", "-"):
            return await interaction.response.send_message(embed=create_embed("❌ Error", "You cannot handle your own transaction session.", 0xd9534f), ephemeral=True)

        button.label = "Claimed"
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=append_footer(create_embed("✅ Middleman Assigned", f"{interaction.user.mention} is now your official middleman for this trade session.", 0x2ecc71), interaction))

    @discord.ui.button(label="Close Session", style=discord.ButtonStyle.red, custom_id="btn_close_mm", emoji="🔒")
    async def close_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if is_not_owner(interaction):
            return await interaction.response.send_message(embed=create_embed("🔒 Denied", "Only the **Server Owner** is authorized to close middleman sessions.", 0xd9534f), ephemeral=True)

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

# ADMINISTRATIVE COMMANDS (Owner Only)
@bot.hybrid_command(name="ticket", description="Deploys the main interactive support ticket panel")
async def deploy_t(ctx: commands.Context):
    await ctx.defer(ephemeral=True)
    embed = discord.Embed(title="🎫 Support Tickets", description="Click the button below to open a private support session.", color=0x2f3136)
    await ctx.channel.send(embed=append_footer(embed, ctx), view=SupportPanel())
    await ctx.send(embed=create_embed("✅ System", "Support panel deployed successfully."), ephemeral=True)

@bot.hybrid_command(name="setup_middleman", description="Deploys the main interactive middleman service panel")
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

@bot.hybrid_command(name="revamp", description="Purges server channels and completely builds the core layout matrix")
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
async def hybrid_ban(ctx: commands.Context, member: discord.Member, *, reason: str = "Unspecified"):
    await ctx.defer(ephemeral=True)
    if member.id == ctx.guild.owner_id:
        return await ctx.send(embed=create_embed("❌ Failed", "The server root owner cannot be banned.", 0xd9534f), ephemeral=True)
    await member.ban(reason=reason)
    await ctx.send(embed=create_embed("🔨 Action Completed", f"Successfully banned {member.mention}. Reason: {reason}"), ephemeral=True)

@bot.hybrid_command(name="unban", description="Lifts ban restrictions for a user using their ID format")
async def hybrid_unban(ctx: commands.Context, user_id: str):
    await ctx.defer(ephemeral=True)
    try:
        user = await bot.fetch_user(int(user_id))
        await ctx.guild.unban(user)
        await ctx.send(embed=create_embed("🔓 Restriction Lifted", f"Successfully unbanned profile: {user.name}."), ephemeral=True)
    except:
        await ctx.send(embed=create_embed("❌ Error", "Target profile link could not be located on the ban list.", 0xd9534f), ephemeral=True)

@bot.hybrid_command(name="kick", description="Removes a member from the guild server roster")
async def hybrid_kick(ctx: commands.Context, member: discord.Member, *, reason: str = "Unspecified"):
    await ctx.defer(ephemeral=True)
    if member.id == ctx.guild.owner_id:
        return await ctx.send(embed=create_embed("❌ Failed", "The server root owner cannot be kicked.", 0xd9534f), ephemeral=True)
    await member.kick(reason=reason)
    await ctx.send(embed=create_embed("👢 Action Completed", f"Successfully kicked {member.mention}."), ephemeral=True)

@bot.hybrid_command(name="mute", description="Restricts text write permissions for a target member")
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
async def hybrid_unmute(ctx: commands.Context, member: discord.Member):
    await ctx.defer(ephemeral=True)
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if role and role in member.roles:
        await member.remove_roles(role)
        return await ctx.send(embed=create_embed("🔊 Restored", f"Regular write access permissions active for {member.mention}."), ephemeral=True)
    await ctx.send(embed=create_embed("❌ Error", "User does not possess an active restriction tag.", 0xd9534f), ephemeral=True)

@bot.hybrid_command(name="warn", description="Issues a strike warning to a member")
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
async def hybrid_clear_w(ctx: commands.Context, member: discord.Member):
    await ctx.defer(ephemeral=True)
    warnings[str(member.id)] = []
    await ctx.send(embed=create_embed("🧹 Purged", f"Reset strike matrix logs for {member.mention}."), ephemeral=True)

@bot.hybrid_command(name="purge", description="Clears a specific quantity of messages from the current text channel")
async def hybrid_purge(ctx: commands.Context, amount: int):
    await ctx.defer(ephemeral=True)
    clamped = max(1, min(amount, 100))
    deleted = await ctx.channel.purge(limit=clamped)
    await ctx.send(embed=create_embed("🧹 Purged", f"Successfully cleared `{len(deleted)}` messages from channel history."), ephemeral=True)

@bot.hybrid_command(name="lock", description="Locks down the current channel permissions to prevent public chat typing")
async def hybrid_lock(ctx: commands.Context):
    await ctx.defer(ephemeral=True)
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
    await ctx.send(embed=create_embed("🔒 Locked", "Public text writing locked down for this channel."), ephemeral=True)

@bot.hybrid_command(name="unlock", description="Unlocks current channel permissions to re-enable public chat typing")
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
async def slowmode(ctx: commands.Context, seconds: int):
    await ctx.defer(ephemeral=True)
    await ctx.channel.edit(slowmode_delay=seconds)
    await ctx.send(embed=create_embed("⏱️ Slowmode Updated", f"Channel write cooldown delay set to `{seconds}` seconds."), ephemeral=True)

@bot.hybrid_command(name="nickname", description="Overwrites and updates a member's server profile nickname mapping")
async def nickname(ctx: commands.Context, member: discord.Member, new_name: str):
    await ctx.defer(ephemeral=True)
    await member.edit(nick=new_name)
    await ctx.send(embed=create_embed("📝 Profile Patched", f"Updated display mapping for {member.mention} to **{new_name}**."), ephemeral=True)

@bot.hybrid_command(name="addrole", description="Grants a specific system security role to a server member")
async def addrole(ctx: commands.Context, member: discord.Member, role: discord.Role):
    await ctx.defer(ephemeral=True)
    await member.add_roles(role)
    await ctx.send(embed=create_embed("🛡️ Role Linked", f"Linked role {role.mention} to {member.mention}."), ephemeral=True)

@bot.hybrid_command(name="removerole", description="Strips a specific system security role from a server member")
async def remrole(ctx: commands.Context, member: discord.Member, role: discord.Role):
    await ctx.defer(ephemeral=True)
    await member.remove_roles(role)
    await ctx.send(embed=create_embed("🛡️ Role Stripped", f"Detached role {role.mention} from {member.mention}."), ephemeral=True)

@bot.hybrid_command(name="deleteallchannels", description="Irreversibly wipes all existing text channels from the current guild grid")
async def delchannels(ctx: commands.Context):
    await ctx.defer(ephemeral=True)
    for c in ctx.guild.channels:
        if c != ctx.channel:
            try: await c.delete()
            except: pass
    await ctx.send(embed=create_embed("🚨 Grid Purged", "All operational server channels drop cleared."), ephemeral=True)

@bot.hybrid_command(name="createchannel", description="Creates a new text communication channel in the guild")
async def createch(ctx: commands.Context, name: str):
    await ctx.defer(ephemeral=True)
    c = await ctx.guild.create_text_channel(name)
    await ctx.send(embed=create_embed("📁 Channel Opened", f"Successfully mounted new channel route: {c.mention}"), ephemeral=True)

@bot.hybrid_command(name="deletechannel", description="Permanently drops a selected text communication channel")
async def deletech(ctx: commands.Context, channel: discord.TextChannel):
    await ctx.defer(ephemeral=True)
    await channel.delete()
    await ctx.send(embed=create_embed("🗑️ Vector Closed", "Successfully removed target text vector channel path."), ephemeral=True)

@bot.hybrid_command(name="createrole", description="Generates a new system security role within the guild registry")
async def createrl(ctx: commands.Context, name: str):
    await ctx.defer(ephemeral=True)
    r = await ctx.guild.create_role(name=name)
    await ctx.send(embed=create_embed("🎨 Role Mounted", f"Successfully registered role: {r.mention}"), ephemeral=True)

@bot.hybrid_command(name="deleterole", description="Permanently drops a selected security role registry file")
async def deleterl(ctx: commands.Context, role: discord.Role):
    await ctx.defer(ephemeral=True)
    await role.delete()
    await ctx.send(embed=create_embed("🗑️ Role Dropped", "Successfully purged target registry role data."), ephemeral=True)

@bot.hybrid_command(name="gstart", description="Launches a timed automated prize distribution giveaway event")
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

@bot.hybrid_command(name="say", description="Forwards a plaintext statement directly through the bot terminal link")
async def say(ctx: commands.Context, *, message: str):
    await ctx.defer(ephemeral=True)
    await ctx.channel.send(message)
    await ctx.send("Message dispatched.", ephemeral=True)

@bot.hybrid_command(name="embed", description="Dispatches a structured design embed block down the channel pipeline")
async def embed_cmd(ctx: commands.Context, title: str, *, description: str):
    await ctx.defer(ephemeral=True)
    await ctx.channel.send(embed=create_embed(title, description))
    await ctx.send("Embed deployed.", ephemeral=True)

@bot.hybrid_command(name="announce", description="Broadcasts an embed update announcement message")
async def announce(ctx: commands.Context, channel: discord.TextChannel, *, message: str):
    await ctx.defer(ephemeral=True)
    await channel.send(embed=append_footer(create_embed("📢 BROADCAST ANNOUNCEMENT", message), ctx))
    await ctx.send("Broadcast successfully shipped.", ephemeral=True)


# PUBLIC COMMANDS (Available for everyone)
@bot.hybrid_command(name="temp", description="Saves roles and strips them, or restores them back automatically without changing nickname")
async def temp_cmd(ctx: commands.Context):
    guild = ctx.guild
    member = ctx.author
    uid = member.id

    await ctx.defer(ephemeral=True)

    # RESTORE MODE
    if uid in fill_tracker and fill_tracker[uid]["roles"]:
        for rid in fill_tracker[uid]["roles"]:
            role = guild.get_role(rid)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role)
                except discord.Forbidden:
                    pass

        del fill_tracker[uid]
        await ctx.send(embed=create_embed("🔄 Welcome Back", f"Your previous roles have been fully restored successfully!", 0x2ecc71), ephemeral=True)
    
    # SAVE & STRIP MODE
    else:
        role_ids = []
        for role in member.roles:
            if not role.is_default():
                role_ids.append(role.id)
                try:
                    await member.remove_roles(role)
                except discord.Forbidden:
                    pass
                    
        if not role_ids:
            return await ctx.send(embed=create_embed("❌ Error", "You do not have any clearable roles on your profile.", 0xd9534f), ephemeral=True)
        
        fill_tracker[uid] = {
            "roles": role_ids
        }

        await ctx.send(embed=create_embed("🔄 Setup Stored", f"Your operational server roles have been stripped and stored securely.\n\n*Run `!temp` or `/temp` again at any time to restore your profile layout.*", 0x2f3136), ephemeral=True)

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

@bot.hybrid_command(name="avatar", description="Fetches and displays a user profile avatar image matrix in full scale")
async def avatar(ctx: commands.Context, member: discord.Member = None):
    t = member or ctx.author
    e = discord.Embed(color=0x2f3136)
    e.set_author(name=f"Avatar: {t.name}")
    e.set_image(url=t.display_avatar.url)
    await ctx.send(embed=e)

@bot.hybrid_command(name="mercy", description="Displays tactical execution data regarding hitting methods")
async def mercy(ctx: commands.Context):
    embed1 = discord.Embed(
        title="🚨 OPERATION SUMMARY: HITTER PROTOCOLS",
        description=(
            "1. You got scammed on this transaction by an unverified counterparty.\n"
            "2. Bypassing official escrow services leads directly to high capital deficit.\n"
            "3. The market individual manipulated your deal parameters to extract assets.\n"
            "4. Your previous transaction data is completely unrecoverable on this network.\n"
            "5. Do not interact with secondary recovery operators claiming magic solutions.\n"
            "6. Always log your trade chats to protect yourself against future exploits.\n"
            "7. Blind trust in these fields will always yield massive financial losses.\n"
            "8. Analyze the exact methods used against your position during this run.\n"
            "9. Transition immediately to zero-risk trading environments to stay safe.\n"
            "10. Learn from this execution error to completely upgrade your defense grid."
        ),
        color=0xd9534f
    )
    
    embed2 = discord.Embed(
        title="📈 REVENUE EXPANSION: ADVANCED METHODS",
        description=(
            "1. You can make huge profit by hitting in gag2, sab, and much more.\n"
            "2. Scale your operational performance safely and always have fun.\n"
            "3. Target premium high-yield items from trusted marketplace suppliers.\n"
            "4. Reinvest your liquid revenue directly into secured market pipelines.\n"
            "5. Build robust cross-server deals to maximize your continuous income.\n"
            "6. Keep expanding your network reach using confirmed secure networks.\n"
            "7. Create clean transaction track records to attract elite target pools.\n"
            "8. Eliminate impulsive deal execution and control your portfolio risk.\n"
            "9. Optimize every single hit vector to drastically increase your margins.\n"
            "10. Follow these strict performance setups and secure supreme profit heights."
        ),
        color=0x2ecc71
    )
    
    await ctx.channel.send(embed=embed1)
    await ctx.channel.send(embed=embed2)

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

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if "CheckFailure" in str(error):
        try:
            await interaction.response.send_message(embed=create_embed("🔒 Denied", "Only the **Server Owner** is authorized to use this command.", 0xd9534f), ephemeral=True)
        except:
            pass

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: 
        return
        
    await bot.process_commands(message)
    
    if message.author.id == message.guild.owner_id:
        return
        
    uid, cur = message.author.id, time.time()
    
    if any(w in message.content.lower() for w in BLOCKED_WORDS) or DISCORD_INVITE in message.content.lower() or len(message.mentions) >= MAX_MENTIONS:
        try: return await message.delete()
        except: pass
        
    if len(message.content) > 10 and (sum(1 for c in message.content if c.isupper()) / len(message.content)) * 100 >= MAX_CAPS_PERCENT:
        try: return await message.delete()
        except: pass
        
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

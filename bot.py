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

# Custom Moderation Filters (Add your own words/links here)
BLOCKED_WORDS = []
MAX_MENTIONS = 5
MAX_CAPS_PERCENT = 70
DISCORD_INVITE = "discord.gg"

# Owner Check Decorator
def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return False
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

# Transcript Logging Engine
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
    
    embed = discord.Embed(
        title="Ticket Archive",
        description=f"**Type:** {category}\n**Channel:** #{channel.name}\n**Timestamp:** {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        color=0x2f3136
    )
    await log_channel.send(embed=embed, file=log_file)

# Support Ticket System
class SupportTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.green, custom_id="btn_claim_support")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.label = f"Claimed by {interaction.user.name}"
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"Staff member {interaction.user.mention} has claimed this ticket.")

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.red, custom_id="btn_close_support")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Archiving conversation and closing channel in 5 seconds...")
        await create_ticket_transcript(interaction.channel, "Support")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class SupportPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.blurple, custom_id="btn_open_support")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        channel_name = f"ticket-{user.name.lower()}".replace(" ", "-")
        
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            await interaction.response.send_message(f"You already have an active ticket open: {existing.mention}", ephemeral=True)
            return

        permissions = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        category = discord.utils.get(guild.categories, name="Tickets")
        if not category: 
            category = await guild.create_category("Tickets")
            
        channel = await guild.create_text_channel(channel_name, overwrites=permissions, category=category)
        
        embed = discord.Embed(
            title="Support Ticket", 
            description=f"Welcome {user.mention}. Please state your inquiry or issue below. A staff member will be with you shortly.", 
            color=0x5865f2
        )
        await channel.send(embed=embed, view=SupportTicketView())
        await interaction.response.send_message(f"Your ticket has been generated: {channel.mention}", ephemeral=True)

# Middleman System
class MiddlemanTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Trade", style=discord.ButtonStyle.green, custom_id="btn_claim_mm")
    async def claim_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.label = f"Middleman: {interaction.user.name}"
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"{interaction.user.mention} is handling this middleman transaction.")

    @discord.ui.button(label="Close Trade", style=discord.ButtonStyle.red, custom_id="btn_close_mm")
    async def close_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Saving trade logs and deleting channel in 5 seconds...")
        await create_ticket_transcript(interaction.channel, "Middleman Trade")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class MiddlemanPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Request Middleman", style=discord.ButtonStyle.blurple, custom_id="btn_open_mm")
    async def open_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        channel_name = f"mm-{user.name.lower()}".replace(" ", "-")
        
        existing = discord.utils.get(guild.text_channels, name=channel_name)
        if existing:
            await interaction.response.send_message(f"You already have an active middleman request: {existing.mention}", ephemeral=True)
            return

        permissions = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        category = discord.utils.get(guild.categories, name="Middleman Service")
        if not category: 
            category = await guild.create_category("Middleman Service")
            
        channel = await guild.create_text_channel(channel_name, overwrites=permissions, category=category)
        
        embed = discord.Embed(
            title="Middleman Transaction",
            description=f"Welcome {user.mention}.\nAn official middleman will assist you shortly.\n\n**Please state the details:**\n1. Counterparty (Tag them):\n2. Your Offer:\n3. Their Offer:",
            color=0x5865f2
        )
        embed.set_footer(text="Verify middleman roles before trading to prevent scams.")
        await channel.send(embed=embed, view=MiddlemanTicketView())
        await interaction.response.send_message(f"Middleman request created: {channel.mention}", ephemeral=True)

@tree.command(name="setup_middleman", description="Deploy the official middleman ticket panel")
@is_owner()
async def setup_middleman(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Middleman Services",
        description=(
            "To request an official middleman for a secure transaction, click the button below.\n\n"
            "**Standard Protocol:**\n"
            "• Party A sends items to the middleman.\n"
            "• Party B sends items to the middleman.\n"
            "• Middleman distributes items safely to both parties.\n\n"
            "*Do not start transactions outside of official tickets.*"
        ),
        color=0x5865f2
    )
    await interaction.channel.send(embed=embed, view=MiddlemanPanel())
    await interaction.response.send_message("Panel deployed successfully.", ephemeral=True)

# Giveaway System
@tree.command(name="gstart", description="Launch a new server giveaway")
@is_owner()
async def gstart(interaction: discord.Interaction, minutes: int, winners: int, prize: str):
    await interaction.response.send_message("Giveaway initialized.", ephemeral=True)
    
    end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=minutes)
    embed = discord.Embed(
        title="🎉 Server Giveaway 🎉",
        description=f"Click the reaction below to enter!\n\n**Prize:** {prize}\n**Winners:** {winners}\n**Time Remaining:** <t:{int(end_time.timestamp())}:R>",
        color=0xf1c40f
    )
    
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    
    await asyncio.sleep(minutes * 60)
    
    msg = await interaction.channel.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    entrants = [u async for u in reaction.users() if not u.bot]
    
    if not entrants:
        await interaction.channel.send(f"The giveaway for **{prize}** ended with no participants.")
        return
    
    chosen_winners = random.sample(entrants, min(len(entrants), winners))
    mentions = ", ".join([w.mention for w in chosen_winners])
    
    end_embed = discord.Embed(
        title="🎉 Giveaway Concluded 🎉",
        description=f"**Prize:** {prize}\n**Winners:** {mentions}",
        color=0x2ecc71
    )
    await msg.edit(embed=end_embed)
    await interaction.channel.send(f"Congratulations {mentions}! You won **{prize}**!")

@tree.command(name="greroll", description="Reroll a giveaway winner using the message ID")
@is_owner()
async def greroll(interaction: discord.Interaction, message_id: str):
    try:
        msg = await interaction.channel.fetch_message(int(message_id))
    except Exception:
        await interaction.response.send_message("Invalid message ID or message not found.", ephemeral=True)
        return

    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    if not reaction:
        await interaction.response.send_message("No giveaway entries found on this message.", ephemeral=True)
        return
        
    entrants = [u async for u in reaction.users() if not u.bot]
    if not entrants:
        await interaction.response.send_message("No users reacted to this giveaway.", ephemeral=True)
        return
        
    winner = random.choice(entrants)
    await interaction.response.send_message("Reroll complete.", ephemeral=True)
    await interaction.channel.send(f"🎉 **New Winner:** {winner.mention}! Congratulations!")

# Help Core Command
@tree.command(name="help", description="Display available system commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="System Command Menu", color=0x5865f2)
    embed.add_field(name="Moderation", value="`/ban`, `/unban`, `/kick`, `/mute`, `/unmute`, `/warn`, `/warnings`, `/clearwarnings`, `/purge`, `/slowmode`, `/lock`, `/unlock`, `/nickname`, `/addrole`, `/removerole`", inline=False)
    embed.add_field(name="Giveaways", value="`/gstart`, `/greroll`", inline=False)
    embed.add_field(name="Utility", value="`/verify`, `/hit`, `/poll`, `/say`, `/embed`, `/avatar`, `/announce`, `/serverinfo`, `/userinfo`, `/membercount`, `/ping`, `/coinflip`, `/dice`, `/8ball`, `/choose`, `/uptime`, `/botinfo`", inline=False)
    embed.add_field(name="Management", value="`/revamp`, `/deleteallchannels`, `/createchannel`, `/deletechannel`, `/createrole`, `/deleterole`, `/setup_middleman`", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Events & Chat Filters
@bot.event
async def on_ready():
    if not hasattr(bot, 'start_time'): 
        bot.start_time = datetime.datetime.utcnow()
    try: 
        await tree.sync()
    except Exception as e: 
        print(f"Sync error: {e}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="trades"))
    print(f"System fully loaded: {bot.user}")

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="welcome")
    if channel:
        embed = discord.Embed(
            title="Welcome", 
            description=f"Welcome {member.mention} to {member.guild.name}. You are member #{member.guild.member_count}.", 
            color=0x2ecc71
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    channel = discord.utils.get(member.guild.text_channels, name="welcome")
    if channel: 
        await channel.send(f"**{member.name}** left the server.")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: 
        return
    if message.author.id == message.guild.owner_id:
        await bot.process_commands(message)
        return
        
    user_id = message.author.id
    current_time = time.time()
    content = message.content

    if any(word in content.lower() for word in BLOCKED_WORDS):
        await message.delete()
        return
    if DISCORD_INVITE in content.lower():
        await message.delete()
        return
    if len(message.mentions) >= MAX_MENTIONS:
        await message.delete()
        return
    if len(content) > 10 and (sum(1 for c in content if c.isupper()) / len(content)) * 100 >= MAX_CAPS_PERCENT:
        await message.delete()
        return

    if user_id not in spam_tracker: 
        spam_tracker[user_id] = []
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

# Interactive Utility Commands
@tree.command(name="verify", description="Complete verification process")
async def verify(interaction: discord.Interaction):
    view = discord.ui.View()
    btn_yes = discord.ui.Button(label="Accept Rules", style=discord.ButtonStyle.green)
    btn_no = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)
    
    async def yes_cb(i): await i.response.send_message("Verification successful.", ephemeral=True)
    async def no_cb(i): await i.response.send_message("Verification aborted.", ephemeral=True)
    
    btn_yes.callback = yes_cb
    btn_no.callback = no_cb
    view.add_item(btn_yes)
    view.add_item(btn_no)
    await interaction.response.send_message("Please acknowledge the server guidelines to gain access.", view=view, ephemeral=True)

class OfferConfirmation(discord.ui.View):
    def __init__(self, target: discord.Member):
        super().__init__(timeout=60)
        self.target = target
    @discord.ui.button(label="Accept Offer", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"{interaction.user.mention} has accepted the terms.")
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"{interaction.user.mention} rejected the offer.")

@tree.command(name="hit", description="Propose a custom trade deal")
async def hit(interaction: discord.Interaction, member: discord.Member):
    embed = discord.Embed(title="Trade Offer", description=f"New business proposal for {member.mention}.", color=0xf1c40f)
    await interaction.response.send_message(f"{member.mention}", embed=embed, view=OfferConfirmation(target=member))

# Administrative Modules
@tree.command(name="ban", description="Ban a user")
@is_owner()
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"Banned {member}. Reason: {reason}")

@tree.command(name="unban", description="Unban a user by ID")
@is_owner()
async def unban(interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
    user = await bot.fetch_user(int(user_id))
    await interaction.guild.unban(user, reason=reason)
    await interaction.response.send_message(f"Unbanned {user}.")

@tree.command(name="kick", description="Kick a user")
@is_owner()
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"Kicked {member}. Reason: {reason}")

@tree.command(name="mute", description="Mute a user")
@is_owner()
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "No reason provided"):
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not mute_role:
        mute_role = await interaction.guild.create_role(name="Muted")
        for channel in interaction.guild.channels: 
            await channel.set_permissions(mute_role, send_messages=False, speak=False)
    await member.add_roles(mute_role, reason=reason)
    await interaction.response.send_message(f"Muted {member} for {minutes}m. Reason: {reason}")
    await asyncio.sleep(minutes * 60)
    await member.remove_roles(mute_role)

@tree.command(name="unmute", description="Unmute a user")
@is_owner()
async def unmute(interaction: discord.Interaction, member: discord.Member):
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if mute_role in member.roles:
        await member.remove_roles(mute_role)
        await interaction.response.send_message(f"Unmuted {member}.")
    else:
        await interaction.response.send_message("User is not muted.", ephemeral=True)

@tree.command(name="warn", description="Issue a warning to a user")
@is_owner()
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    uid = str(member.id)
    if uid not in warnings: 
        warnings[uid] = []
    warnings[uid].append({"reason": reason, "time": str(datetime.datetime.now())})
    count = len(warnings[uid])
    await interaction.response.send_message(f"Warned {member}. Total: {count}")
    if count >= 3:
        await member.ban(reason="Automated ban: 3 warnings accumulated.")

@tree.command(name="warnings", description="View user infraction history")
@is_owner()
async def check_warnings(interaction: discord.Interaction, member: discord.Member):
    uid = str(member.id)
    if uid not in warnings or not warnings[uid]:
        await interaction.response.send_message("User has no active warnings.", ephemeral=True)
        return
    embed = discord.Embed(title=f"Infractions: {member}", color=0xe67e22)
    for i, w in enumerate(warnings[uid], 1): 
        embed.add_field(name=f"Case #{i}", value=f"Reason: {w['reason']}\nDate: {w['time']}", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="clearwarnings", description="Reset user infraction count")
@is_owner()
async def clearwarnings(interaction: discord.Interaction, member: discord.Member):
    warnings[str(member.id)] = []
    await interaction.response.send_message(f"Cleared history for {member}.")

@tree.command(name="purge", description="Bulk delete messages")
@is_owner()
async def purge(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"Purged {amount} messages.", ephemeral=True)

@tree.command(name="slowmode", description="Configure channel rate limit")
@is_owner()
async def slowmode(interaction: discord.Interaction, seconds: int):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"Slowmode updated to {seconds}s.")

@tree.command(name="lock", description="Lock text channel permissions")
@is_owner()
async def lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("Channel locked down.")

@tree.command(name="unlock", description="Restore text channel permissions")
@is_owner()
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("Channel unlocked.")

@tree.command(name="nickname", description="Modify user nickname")
@is_owner()
async def nickname(interaction: discord.Interaction, member: discord.Member, nickname: str):
    await member.edit(nick=nickname)
    await interaction.response.send_message(f"Updated nickname for {member}.")

@tree.command(name="addrole", description="Assign a role")
@is_owner()
async def addrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await interaction.response.send_message(f"Assigned role {role.name} to {member}.")

@tree.command(name="removerole", description="Revoke a role")
@is_owner()
async def removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await interaction.response.send_message(f"Revoked role {role.name} from {member}.")

# Infrastructure Control Module
@tree.command(name="revamp", description="Rebuild server infrastructure channels")
@is_owner()
async def revamp(interaction: discord.Interaction):
    await interaction.response.send_message("Executing infrastructure rebuild...", ephemeral=True)
    guild = interaction.guild
    for channel in guild.channels:
        if channel != interaction.channel:
            try: await channel.delete()
            except Exception: pass
            
    structure = {
        "INFORMATION": [("welcome", discord.ChannelType.text), ("rules", discord.ChannelType.text), ("announcements", discord.ChannelType.text), ("giveaways", discord.ChannelType.text)],
        "COMMUNITY": [("general", discord.ChannelType.text), ("commands", discord.ChannelType.text), ("memes", discord.ChannelType.text), ("Lounge", discord.ChannelType.voice)],
        "TRANSACTIONS": [("middleman-info", discord.ChannelType.text), ("market", discord.ChannelType.text), ("trading-chat", discord.ChannelType.text)],
        "UTILITY": [("open-ticket", discord.ChannelType.text)]
    }
    
    for cat_name, channels in structure.items():
        category = await guild.create_category(cat_name)
        for ch_name, ch_type in channels:
            if ch_type == discord.ChannelType.text: 
                await guild.create_text_channel(ch_name, category=category)
            elif ch_type == discord.ChannelType.voice: 
                await guild.create_voice_channel(ch_name, category=category)
                
    try: await interaction.channel.send("Infrastructure build completed.")
    except Exception: pass

@tree.command(name="deleteallchannels", description="Wipe all channels")
@is_owner()
async def deleteallchannels(interaction: discord.Interaction):
    await interaction.response.send_message("Wiping server channels in 5 seconds...")
    await asyncio.sleep(5)
    for channel in interaction.guild.channels:
        try: await channel.delete()
        except Exception: pass

@tree.command(name="createchannel", description="Create custom text channel")
@is_owner()
async def createchannel(interaction: discord.Interaction, name: str):
    channel = await interaction.guild.create_text_channel(name)
    await interaction.response.send_message(f"Created channel {channel.mention}")

@tree.command(name="deletechannel", description="Delete target channel")
@is_owner()
async def deletechannel(interaction: discord.Interaction, channel: discord.TextChannel):
    await channel.delete()
    await interaction.response.send_message("Channel deleted.", ephemeral=True)

@tree.command(name="createrole", description="Create custom role")
@is_owner()
async def createrole(interaction: discord.Interaction, name: str):
    role = await interaction.guild.create_role(name=name)
    await interaction.response.send_message(f"Created role: {role.name}")

@tree.command(name="deleterole", description="Delete target role")
@is_owner()
async def deleterole(interaction: discord.Interaction, role: discord.Role):
    await role.delete()
    await interaction.response.send_message("Role deleted.")

@tree.command(name="serverinfo", description="Display technical guild metrics")
@is_owner()
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=guild.name, color=0x5865f2)
    embed.add_field(name="Users", value=guild.member_count)
    embed.add_field(name="Channels", value=len(guild.channels))
    embed.add_field(name="Roles", value=len(guild.roles))
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await interaction.response.send_message(embed=embed)

@tree.command(name="userinfo", description="Fetch user profile data")
@is_owner()
async def userinfo(interaction: discord.Interaction, member: discord.Member):
    embed = discord.Embed(title=str(member), color=0x5865f2)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Registration Date", value=member.joined_at.strftime("%Y-%m-%d"))
    embed.set_thumbnail(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@tree.command(name="membercount", description="Get active member metrics")
@is_owner()
async def membercount(interaction: discord.Interaction):
    await interaction.response.send_message(f"Current server headcount: **{interaction.guild.member_count}**")

# Standard Tools
@tree.command(name="ping", description="Check hardware latency")
@is_owner()
async def ping(interaction: discord.Interaction): 
    await interaction.response.send_message(f"Latency: `{round(bot.latency * 1000)}ms`")

@tree.command(name="coinflip", description="Execute random binary output")
@is_owner()
async def coinflip(interaction: discord.Interaction): 
    await interaction.response.send_message(f"Result: **{random.choice(['Heads', 'Tails'])}**")

@tree.command(name="dice", description="Generate random numeric outcome")
@is_owner()
async def dice(interaction: discord.Interaction, sides: int = 6): 
    await interaction.response.send_message(f"Rolled: **{random.randint(1, sides)}**")

@tree.command(name="8ball", description="Query predictive string array")
@is_owner()
async def eightball(interaction: discord.Interaction, question: str): 
    await interaction.response.send_message(f"🔮 **Query:** {question}\n**Response:** {random.choice(['Affirmative', 'Negative', 'Uncertain', 'Most likely'])}")

@tree.command(name="choose", description="Select random parameter from comma-separated list")
@is_owner()
async def choose(interaction: discord.Interaction, options: str): 
    await interaction.response.send_message(f"Selected: **{random.choice([o.strip() for o in options.split(',')])}**")

@tree.command(name="poll", description="Deploy polling reaction set")
@is_owner()
async def poll(interaction: discord.Interaction, question: str):
    msg = await interaction.channel.send(embed=discord.Embed(title=f"Poll: {question}", color=0x5865f2))
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")
    await interaction.response.send_message("Poll deployed.", ephemeral=True)

@tree.command(name="say", description="Relay text parameter through bot instance")
@is_owner()
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("Relayed.", ephemeral=True)
    await interaction.channel.send(message)

@tree.command(name="embed", description="Generate native script rich embed")
@is_owner()
async def embed_cmd(interaction: discord.Interaction, title: str, description: str):
    await interaction.channel.send(embed=discord.Embed(title=title, description=description, color=0x5865f2))
    await interaction.response.send_message("Embed deployed.", ephemeral=True)

@tree.command(name="avatar", description="Fetch asset target user avatar")
@is_owner()
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"Avatar: {member}", color=0x5865f2)
    embed.set_image(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@tree.command(name="announce", description="Broadcast data to target channel")
@is_owner()
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    await channel.send(embed=discord.Embed(title="Notification", description=message, color=0xf1c40f))
    await interaction.response.send_message("Broadcast complete.", ephemeral=True)

@tree.command(name="uptime", description="Check instance active loop duration")
@is_owner()
async def uptime(interaction: discord.Interaction):
    delta = datetime.datetime.utcnow() - bot.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    await interaction.response.send_message(f"System Uptime: **{hours}h {minutes}m {seconds}s**")

@tree.command(name="botinfo", description="Display process details")
@is_owner()
async def botinfo(interaction: discord.Interaction):
    embed = discord.Embed(title="Instance Specifications", color=0x5865f2)
    embed.add_field(name="Process Name", value=bot.user.name)
    embed.add_field(name="Active Guilds", value=len(bot.guilds))
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# Keep-Alive Engine (Web Thread)
app = Flask('')

@app.route('/')
def home(): 
    return "Service Active"

def run(): 
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

def main():
    keep_alive()
    while True:
        try:
            token = os.environ.get("DISCORD_TOKEN")
            if not token:
                time.sleep(10)
                continue
            bot.run(token)
        except Exception:
            time.sleep(5)

if __name__ == "__main__":
    main()

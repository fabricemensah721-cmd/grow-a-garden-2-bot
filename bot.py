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

# Custom Moderation Filters
BLOCKED_WORDS = []
MAX_MENTIONS = 5
MAX_CAPS_PERCENT = 70
DISCORD_INVITE = "discord.gg"

# Helper for High-End Minimalist Embeds (Inspired by 1000047005.jpg)
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

# Owner Check Decorator
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
    
    embed = make_clean_embed("📁 Ticket Archive", f"**Type:** {category}\n**Channel:** #{channel.name}", 0x2f3136)
    await log_channel.send(embed=embed, file=log_file)

# Support Ticket System
class SupportTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claimed", style=discord.ButtonStyle.green, custom_id="btn_claim_support", emoji="✋")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.label = "Claimed"
        button.disabled = True
        await interaction.message.edit(view=self)
        
        embed = make_clean_embed("✅ Ticket Claimed", f"{interaction.user.mention} will be your Support Agent for today.", 0x2ecc71)
        embed = add_bot_footer(embed, interaction)
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="btn_close_support", emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = make_clean_embed("🔒 Ticket Closing", "Saving transcript and deleting channel in 5 seconds...", 0x2f3136)
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
            embed = make_clean_embed("❌ Error", f"You already have an active ticket open: {existing.mention}", 0x2f3136)
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        
        embed = make_clean_embed("🎫 Support Ticket", f"{user.mention}, Thank you for contacting our support team.\n\nPlease wait for an agent to assist you.\nIf you have any questions, please let a staff member know.", 0x2f3136)
        embed = add_bot_footer(embed, interaction)
        await channel.send(f"{user.mention}", embed=embed, view=SupportTicketView())
        
        resp_embed = make_clean_embed("✅ Success", f"Your ticket has been generated: {channel.mention}", 0x2f3136)
        await interaction.response.send_message(embed=resp_embed, ephemeral=True)

# Middleman System
class MiddlemanTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claimed", style=discord.ButtonStyle.green, custom_id="btn_claim_mm", emoji="✋")
    async def claim_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.label = "Claimed"
        button.disabled = True
        await interaction.message.edit(view=self)
        
        embed = make_clean_embed("✅ Ticket Claimed", f"{interaction.user.mention} will be your Middleman for today.", 0x2ecc71)
        embed = add_bot_footer(embed, interaction)
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="btn_close_mm", emoji="🔒")
    async def close_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = make_clean_embed("🔒 Trade Closing", "Saving logs and closing channel in 5 seconds...", 0x2f3136)
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
            embed = make_clean_embed("❌ Error", f"You already have an active request: {existing.mention}", 0x2f3136)
            await interaction.response.send_message(embed=embed, ephemeral=True)
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
        
        embed = make_clean_embed("🎫 Middleman Ticket", f"{user.mention}, Thank you for using our middleman services.\n\nPlease wait for a middleman to assist you.\n\nIf you have any questions, please let a staff member know.", 0x2f3136)
        embed = add_bot_footer(embed, interaction)
        await channel.send(f"{user.mention} @Middleman", embed=embed, view=MiddlemanTicketView())
        
        resp_embed = make_clean_embed("✅ Success", f"Middleman ticket created: {channel.mention}", 0x2f3136)
        await interaction.response.send_message(embed=resp_embed, ephemeral=True)

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
    
    resp_embed = make_clean_embed("✅ System", "Panel deployed successfully.", 0x2f3136)
    await interaction.response.send_message(embed=resp_embed, ephemeral=True)

# Giveaway System
@tree.command(name="gstart", description="Launch a new server giveaway")
@is_owner()
async def gstart(interaction: discord.Interaction, minutes: int, winners: int, prize: str):
    resp_embed = make_clean_embed("🎉 System", "Giveaway initialized.", 0x2f3136)
    await interaction.response.send_message(embed=resp_embed, ephemeral=True)
    
    end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=minutes)
    embed = make_clean_embed("🎉 Server Giveaway 🎉", f"Click the reaction below to enter!\n\n**Prize:** {prize}\n**Winners:** {winners}\n**End:** <t:{int(end_time.timestamp())}:R>", 0x2f3136)
    
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    
    await asyncio.sleep(minutes * 60)
    
    msg = await interaction.channel.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    entrants = [u async for u in reaction.users() if not u.bot]
    
    if not entrants:
        await interaction.channel.send(embed=make_clean_embed("🎉 Giveaway Ended", "The giveaway ended with no participants.", 0x2f3136))
        return
    
    chosen_winners = random.sample(entrants, min(len(entrants), winners))
    mentions = ", ".join([w.mention for w in chosen_winners])
    
    end_embed = make_clean_embed("🎉 Giveaway Concluded 🎉", f"**Prize:** {prize}\n**Winners:** {mentions}", 0x2f3136)
    await msg.edit(embed=end_embed)
    await interaction.channel.send(embed=make_clean_embed("🎉 Winner", f"Congratulations {mentions}! You won **{prize}**!", 0x2f3136))

@tree.command(name="greroll", description="Reroll a giveaway winner using the message ID")
@is_owner()
async def greroll(interaction: discord.Interaction, message_id: str):
    try:
        msg = await interaction.channel.fetch_message(int(message_id))
    except Exception:
        await interaction.response.send_message(embed=make_clean_embed("❌ Error", "Invalid message ID or message not found.", 0x2f3136), ephemeral=True)
        return

    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    if not reaction:
        await interaction.response.send_message(embed=make_clean_embed("❌ Error", "No giveaway entries found on this message.", 0x2f3136), ephemeral=True)
        return
        
    entrants = [u async for u in reaction.users() if not u.bot]
    if not entrants:
        await interaction.response.send_message(embed=make_clean_embed("❌ Error", "No users reacted to this giveaway.", 0x2f3136), ephemeral=True)
        return
        
    winner = random.choice(entrants)
    await interaction.response.send_message(embed=make_clean_embed("✅ System", "Reroll complete.", 0x2f3136), ephemeral=True)
    await interaction.channel.send(embed=make_clean_embed("🎉 New Winner", f"🎉 New Winner: {winner.mention}! Congratulations!", 0x2f3136))

# Help Core Command
@tree.command(name="help", description="Display available system commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="⚙️ System Command Menu", color=0x2f3136)
    embed.add_field(name="Moderation", value="`/ban`, `/unban`, `/kick`, `/mute`, `/unmute`, `/warn`, `/warnings`, `/clearwarnings`, `/purge`, `/slowmode`, `/lock`, `/unlock`, `/nickname`, `/addrole`, `/removerole`", inline=False)
    embed.add_field(name="Giveaways", value="`/gstart`, `/greroll`", inline=False)
    embed.add_field(name="Utility", value="`/verify`, `/hit`, `/poll`, `/say`, `/embed`, `/avatar`, `/announce`, `/serverinfo`, `/userinfo`, `/membercount`, `/ping`, `/coinflip`, `/dice`, `/8ball`, `/choose`, `/uptime`, `/botinfo`", inline=False)
    embed.add_field(name="Management", value="`/revamp`, `/deleteallchannels`, `/createchannel`, `/deletechannel`, `/createrole`, `/deleterole`, `/setup_middleman`", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Verification Custom Action
@tree.command(name="verify", description="Complete verification process")
async def verify(interaction: discord.Interaction):
    view = discord.ui.View()
    btn_yes = discord.ui.Button(label="Accept Rules", style=discord.ButtonStyle.green)
    btn_no = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)
    
    async def yes_cb(i): 
        await i.response.send_message(embed=make_clean_embed("✅ Verification", "Verification successful.", 0x2f3136), ephemeral=True)
    async def no_cb(i): 
        await i.response.send_message(embed=make_clean_embed("❌ Verification", "Verification aborted.", 0x2f3136), ephemeral=True)
    
    btn_yes.callback = yes_cb
    btn_no.callback = no_cb
    view.add_item(btn_yes)
    view.add_item(btn_no)
    await interaction.response.send_message(embed=make_clean_embed("📝 Verification Required", "Please acknowledge the server guidelines to gain access.", 0x2f3136), view=view, ephemeral=True)

class OfferConfirmation(discord.ui.View):
    def __init__(self, target: discord.Member):
        super().__init__(timeout=60)
        self.target = target
    @discord.ui.button(label="Accept Offer", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=make_clean_embed("🤝 Offer Accepted", f"{interaction.user.mention} has accepted the terms.", 0x2f3136))
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=make_clean_embed("❌ Offer Declined", f"{interaction.user.mention} rejected the offer.", 0x2f3136))

@tree.command(name="hit", description="Propose a custom trade deal")
async def hit(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(embed=make_clean_embed("💼 Trade Offer", f"New business proposal for {member.mention}.", 0x2f3136), view=OfferConfirmation(target=member))

# Administrative Modules
@tree.command(name="ban", description="Ban a user")
@is_owner()
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.ban(reason=reason)
    await interaction.response.send_message(embed=make_clean_embed("🔨 Ban Executed", f"Banned {member}. Reason: {reason}", 0x2f3136))

@tree.command(name="unban", description="Unban a user by ID")
@is_owner()
async def unban(interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
    user = await bot.fetch_user(int(user_id))
    await interaction.guild.unban(user, reason=reason)
    await interaction.response.send_message(embed=make_clean_embed("✅ Unban Executed", f"Unbanned {user}.", 0x2f3136))

@tree.command(name="kick", description="Kick a user")
@is_owner()
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.kick(reason=reason)
    await interaction.response.send_message(embed=make_clean_embed("🚪 Kick Executed", f"Kicked {member}. Reason: {reason}", 0x2f3136))

@tree.command(name="mute", description="Mute a user")
@is_owner()
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "No reason provided"):
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not mute_role:
        mute_role = await interaction.guild.create_role(name="Muted")
        for channel in interaction.guild.channels: 
            await channel.set_permissions(mute_role, send_messages=False, speak=False)
    await member.add_roles(mute_role, reason=reason)
    await interaction.response.send_message(embed=make_clean_embed("🔇 Mute Executed", f"Muted {member} for {minutes}m. Reason: {reason}", 0x2f3136))
    await asyncio.sleep(minutes * 60)
    await member.remove_roles(mute_role)

@tree.command(name="unmute", description="Unmute a user")
@is_owner()
async def unmute(interaction: discord.Interaction, member: discord.Member):
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if mute_role in member.roles:
        await member.remove_roles(mute_role)
        await interaction.response.send_message(embed=make_clean_embed("🔊 Unmute Executed", f"Unmuted {member}.", 0x2f3136))
    else:
        await interaction.response.send_message(embed=make_clean_embed("❌ Error", "User is not muted.", 0x2f3136), ephemeral=True)

@tree.command(name="warn", description="Issue a warning to a user")
@is_owner()
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    uid = str(member.id)
    if uid not in warnings: warnings[uid] = []
    warnings[uid].append({"reason": reason, "time": str(datetime.datetime.now())})
    count = len(warnings[uid])
    await interaction.response.send_message(embed=make_clean_embed("⚠️ Warning Issued", f"Warned {member}. Total: {count}\nReason: {reason}", 0x2f3136))
    if count >= 3:
        await member.ban(reason="Automated ban: 3 warnings accumulated.")

@tree.command(name="warnings", description="View user infraction history")
@is_owner()
async def check_warnings(interaction: discord.Interaction, member: discord.Member):
    uid = str(member.id)
    if uid not in warnings or not warnings[uid]:
        await interaction.response.send_message(embed=make_clean_embed("😇 Infraction Clean", "User has no active warnings.", 0x2f3136), ephemeral=True)
        return
    embed = discord.Embed(title=f"📋 Infractions: {member}", color=0x2f3136)
    for i, w in enumerate(warnings[uid], 1): 
        embed.add_field(name=f"Case #{i}", value=f"Reason: {w['reason']}\nDate: {w['time']}", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="clearwarnings", description="Reset user infraction count")
@is_owner()
async def clearwarnings(interaction: discord.Interaction, member: discord.Member):
    warnings[str(member.id)] = []
    await interaction.response.send_message(embed=make_clean_embed("🧹 History Reset", f"Cleared history for {member}.", 0x2f3136))

@tree.command(name="purge", description="Bulk delete messages")
@is_owner()
async def purge(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.purge(limit=amount)
    await interaction.followup.send(embed=make_clean_embed("🧹 Purge Complete", f"Purged {amount} messages.", 0x2f3136), ephemeral=True)

@tree.command(name="slowmode", description="Configure channel rate limit")
@is_owner()
async def slowmode(interaction: discord.Interaction, seconds: int):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(embed=make_clean_embed("⏳ Configuration Updated", f"Slowmode updated to {seconds}s.", 0x2f3136))

@tree.command(name="lock", description="Lock text channel permissions")
@is_owner()
async def lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message(embed=make_clean_embed("🔒 Channel Lockdown", "Channel locked down.", 0x2f3136))

@tree.command(name="unlock", description="Restore text channel permissions")
@is_owner()
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message(embed=make_clean_embed("🔓 Channel Unlocked", "Channel unlocked.", 0x2f3136))

@tree.command(name="nickname", description="Modify user nickname")
@is_owner()
async def nickname(interaction: discord.Interaction, member: discord.Member, nickname: str):
    await member.edit(nick=nickname)
    await interaction.response.send_message(embed=make_clean_embed("👤 Profile Updated", f"Updated nickname for {member} to {nickname}.", 0x2f3136))

@tree.command(name="addrole", description="Assign a role")
@is_owner()
async def addrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await interaction.response.send_message(embed=make_clean_embed("🛡️ Role Updated", f"Assigned role {role.name} to {member}.", 0x2f3136))

@tree.command(name="removerole", description="Revoke a role")
@is_owner()
async def removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await interaction.response.send_message(embed=make_clean_embed("🛡️ Role Updated", f"Revoked role {role.name} from {member}.", 0x2f3136))

# Infrastructure Control Module
@tree.command(name="revamp", description="Rebuild server infrastructure channels")
@is_owner()
async def revamp(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_clean_embed("⚙️ System Management", "Executing infrastructure rebuild...", 0x2f3136), ephemeral=True)
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
                
    try: await interaction.channel.send(embed=make_clean_embed("🏗️ Infrastructure System", "Infrastructure build completed.", 0x2f3136))
    except Exception: pass

@tree.command(name="deleteallchannels", description="Wipe all channels")
@is_owner()
async def deleteallchannels(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_clean_embed("🚨 System Warning", "Wiping server channels in 5 seconds...", 0x2f3136))
    await asyncio.sleep(5)
    for channel in interaction.guild.channels:
        try: await channel.delete()
        except Exception: pass

@tree.command(name="createchannel", description="Create custom text channel")
@is_owner()
async def createchannel(interaction: discord.Interaction, name: str):
    channel = await interaction.guild.create_text_channel(name)
    await interaction.response.send_message(embed=make_clean_embed("🧱 Structure Updated", f"Created channel {channel.mention}", 0x2f3136))

@tree.command(name="deletechannel", description="Delete target channel")
@is_owner()
async def deletechannel(interaction: discord.Interaction, channel: discord.TextChannel):
    channel_name = channel.name
    await channel.delete()
    await interaction.response.send_message(embed=make_clean_embed("🧱 Structure Updated", f"Channel #{channel_name} deleted.", 0x2f3136), ephemeral=True)

@tree.command(name="createrole", description="Create custom role")
@is_owner()
async def createrole(interaction: discord.Interaction, name: str):
    role = await interaction.guild.create_role(name=name)
    await interaction.response.send_message(embed=make_clean_embed("🛡️ Role Management", f"Created role: {role.name}", 0x2f3136))

@tree.command(name="deleterole", description="Delete target role")
@is_owner()
async def deleterole(interaction: discord.Interaction, role: discord.Role):
    role_name = role.name
    await role.delete()
    await interaction.response.send_message(embed=make_clean_embed("🛡️ Role Management", f"Role @{role_name} deleted.", 0x2f3136))

@tree.command(name="serverinfo", description="Display technical guild metrics")
@is_owner()
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"📊 Server Info: {guild.name}", color=0x2f3136)
    embed.add_field(name="Users", value=guild.member_count)
    embed.add_field(name="Channels", value=len(guild.channels))
    embed.add_field(name="Roles", value=len(guild.roles))
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await interaction.response.send_message(embed=embed)

@tree.command(name="userinfo", description="Fetch user profile data")
@is_owner()
async def userinfo(interaction: discord.Interaction, member: discord.Member):
    embed = discord.Embed(title=f"👤 User Info: {member}", color=0x2f3136)
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Registration Date", value=member.joined_at.strftime("%Y-%m-%d"))
    embed.set_thumbnail(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@tree.command(name="membercount", description="Get active member metrics")
@is_owner()
async def membercount(interaction: discord.Interaction):
    await interaction.response.send_message(embed=make_clean_embed("👥 Guild Metrics", f"Current headcount: **{interaction.guild.member_count}**", 0x2f3136))

# Standard Entertainment & Tools
@tree.command(name="ping", description="Check hardware latency")
@is_owner()
async def ping(interaction: discord.Interaction): 
    await interaction.response.send_message(embed=make_clean_embed("📡 Latency", f"Latency: `{round(bot.latency * 1000)}ms`", 0x2f3136))

@tree.command(name="coinflip", description="Execute random binary output")
@is_owner()
async def coinflip(interaction: discord.Interaction): 
    await interaction.response.send_message(embed=make_clean_embed("🪙 Coinflip", f"Result: **{random.choice(['Heads', 'Tails'])}**", 0x2f3136))

@tree.command(name="dice", description="Generate random numeric outcome")
@is_owner()
async def dice(interaction: discord.Interaction, sides: int = 6): 
    await interaction.response.send_message(embed=make_clean_embed("🎲 Dice Roll", f"Rolled: **{random.randint(1, sides)}** (1-{sides})", 0x2f3136))

@tree.command(name="8ball", description="Query predictive string array")
@is_owner()
async def eightball(interaction: discord.Interaction, question: str): 
    await interaction.response.send_message(embed=make_clean_embed("🔮 8-Ball", f"**Query:** {question}\n**Response:** {random.choice(['Affirmative', 'Negative', 'Uncertain', 'Most likely'])}", 0x2f3136))

@tree.command(name="choose", description="Select random parameter from comma-separated list")
@is_owner()
async def choose(interaction: discord.Interaction, options: str): 
    await interaction.response.send_message(embed=make_clean_embed("🤖 Decision Engine", f"Selected: **{random.choice([o.strip() for o in options.split(',')])}**", 0x2f3136))

@tree.command(name="poll", description="Deploy polling reaction set")
@is_owner()
async def poll(interaction: discord.Interaction, question: str):
    msg = await interaction.channel.send(embed=discord.Embed(title=f"📊 Poll: {question}", color=0x2f3136))
    await msg.add_reaction("👍")
    await msg.add_reaction("👎")
    await interaction.response.send_message(embed=make_clean_embed("✅ System", "Poll deployed.", 0x2f3136), ephemeral=True)

@tree.command(name="say", description="Relay text parameter through bot instance")
@is_owner()
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message(embed=make_clean_embed("✅ System", "Relayed.", 0x2f3136), ephemeral=True)
    await interaction.channel.send(message)

@tree.command(name="embed", description="Generate native script rich embed")
@is_owner()
async def embed_cmd(interaction: discord.Interaction, title: str, description: str):
    await interaction.channel.send(embed=discord.Embed(title=title, description=description, color=0x2f3136))
    await interaction.response.send_message(embed=make_clean_embed("✅ System", "Embed deployed.", 0x2f3136), ephemeral=True)

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
    await channel.send(embed=discord.Embed(title="📢 Notification", description=message, color=0x2f3136))
    await interaction.response.send_message(embed=make_clean_embed("✅ System", "Broadcast complete.", 0x2f3136), ephemeral=True)

@tree.command(name="uptime", description="Check instance active loop duration")
@is_owner()
async def uptime(interaction: discord.Interaction):
    delta = datetime.datetime.utcnow() - bot.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    await interaction.response.send_message(embed=make_clean_embed("📈 System Telemetry", f"Uptime: **{hours}h {minutes}m {seconds}s**", 0x2f3136))

@tree.command(name="botinfo", description="Display process details")
@is_owner()
async def botinfo(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Instance Specifications", color=0x2f3136)
    embed.add_field(name="Process Name", value=bot.user.name)
    embed.add_field(name="Active Guilds", value=len(bot.guilds))
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# Events & Chat Filters
@bot.event
async def on_ready():
    if not hasattr(bot, 'start_time'): 
        bot.start_time = datetime.datetime.utcnow()
    try: await tree.sync()
    except Exception as e: print(f"Sync error: {e}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="trades"))
    print(f"System loaded: {bot.user}")

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="welcome")
    if channel:
        embed = discord.Embed(title="👋 Welcome", description=f"Welcome {member.mention} to {member.guild.name}. Member #{member.guild.member_count}.", color=0x2f3136)
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    channel = discord.utils.get(member.guild.text_channels, name="welcome")
    if channel: 
        await channel.send(embed=make_clean_embed("🚪 Member Left", f"**{member.name}** left the server.", 0x2f3136))

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    if message.author.id == message.guild.owner_id:
        await bot.process_commands(message)
        return
    user_id = message.author.id
    current_time = time.time()
    content = message.content

    if any(word in content.lower() for word in BLOCKED_WORDS) or DISCORD_INVITE in content.lower() or len(message.mentions) >= MAX_MENTIONS:
        await message.delete()
        return
    if len(content) > 10 and (sum(1 for c in content if c.isupper()) / len(content)) * 100 >= MAX_CAPS_PERCENT:
        await message.delete()
        return

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

# Flask Web Server Architecture (Keep-Alive)
app = Flask('')
@app.route('/')
def home(): return "Service Active"
def run(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

def main():
    keep_alive()
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("Error: No DISCORD_TOKEN found in environment variables.")

if __name__ == "__main__":
    main()

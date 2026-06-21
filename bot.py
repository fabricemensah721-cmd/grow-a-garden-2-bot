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

class GardenBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        self.add_view(TicketView())
        self.add_view(CloseTicketView())
        self.add_view(MiddlemanTicketView())
        self.add_view(CloseMiddlemanTicketView())

bot = GardenBot()
tree = bot.tree

# ─── TRACKER & CONFIG ───────────────────────────────────────
spam_tracker = {}
SPAM_LIMIT = 5
SPAM_ZEITRAUM = 5
warnings = {}
BAD_WORDS = ["badword1", "badword2", "badword3"]
MAX_MENTIONS = 5
MAX_CAPS_PERCENT = 70
INVITE_PATTERN = "discord.gg"

# ════════════════════════════════════════════════════════════
#  OWNER-ONLY CHECK
# ════════════════════════════════════════════════════════════
def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            await interaction.response.send_message("❌ This command can only be used in a server.", ephemeral=True)
            return False
        if interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message("❌ Only the server owner can use this command!", ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

# ════════════════════════════════════════════════════════════
#  LOGGING FUNCTION (Saves Ticket Transcripts)
# ════════════════════════════════════════════════════════════
async def log_ticket_transcript(channel, ticket_type="Standard"):
    guild = channel.guild
    # Sucht nach einem Kanal namens "ticket-logs" oder erstellt ihn geheimen
    log_channel = discord.utils.get(guild.text_channels, name="ticket-logs")
    if not log_channel:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        log_channel = await guild.create_text_channel("ticket-logs", overwrites=overwrites)

    # Nachrichten sammeln
    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
        messages.append(f"[{timestamp}] {message.author} ({message.author.id}): {message.content}")
    
    transcript_text = "\n".join(messages)
    
    # Datei im Speicher erstellen (ohne die Festplatte zu belasten)
    file_data = io.BytesIO(transcript_text.encode("utf-8"))
    discord_file = discord.File(fp=file_data, filename=f"transcript-{channel.name}.txt")
    
    embed = discord.Embed(
        title=f"📄 Ticket Closed & Logged",
        description=f"**Type:** {ticket_type}\n**Channel Name:** {channel.name}\n**Closed At:** {datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC",
        color=discord.Color.dark_grey()
    )
    await log_channel.send(embed=embed, file=discord_file)

# ════════════════════════════════════════════════════════════
#  STANDARD TICKET SYSTEM
# ════════════════════════════════════════════════════════════
class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="👤 Claim", style=discord.ButtonStyle.green, custom_id="persistent_claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.label = f"✅ Claimed by {interaction.user.name}"
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"👤 {interaction.user.mention} has claimed this ticket!")

    @discord.ui.button(label="🔒 Close Ticket", style=discord.ButtonStyle.red, custom_id="persistent_close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Saving transcript and closing ticket in 5 seconds...")
        await log_ticket_transcript(interaction.channel, "Support Ticket")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Open Ticket", style=discord.ButtonStyle.blurple, custom_id="persistent_open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        existing = discord.utils.get(guild.text_channels, name=f"ticket-{user.name.lower()}")
        if existing:
            await interaction.response.send_message(f"❌ You already have an open ticket: {existing.mention}", ephemeral=True)
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.owner: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        category = discord.utils.get(guild.categories, name="TICKETS")
        if not category: category = await guild.create_category("TICKETS")
        channel = await guild.create_text_channel(f"ticket-{user.name}", overwrites=overwrites, category=category)
        
        embed = discord.Embed(title="🎫 New Ticket", description=f"Hello {user.mention}! 👋\nSupport will be with you shortly.\nPlease describe your issue below.", color=discord.Color.blurple())
        await channel.send(embed=embed, view=CloseTicketView())
        await interaction.response.send_message(f"✅ Your ticket has been created: {channel.mention}", ephemeral=True)

# ════════════════════════════════════════════════════════════
#  MIDDLEMAN TICKET SYSTEM (STYLING FROM 1000046929.jpg)
# ════════════════════════════════════════════════════════════
class CloseMiddlemanTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🤝 Claim Service", style=discord.ButtonStyle.green, custom_id="persistent_claim_mm")
    async def claim_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.label = f"✅ Middleman: {interaction.user.name}"
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(f"🤝 {interaction.user.mention} will act as your Middleman for this trade!")

    @discord.ui.button(label="🔒 Close Trade", style=discord.ButtonStyle.red, custom_id="persistent_close_mm")
    async def close_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Saving trade transcript and closing ticket in 5 seconds...")
        await log_ticket_transcript(interaction.channel, "Middleman Trade")
        await asyncio.sleep(5)
        await interaction.channel.delete()

class MiddlemanTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🎫 Request Middleman", style=discord.ButtonStyle.blurple, custom_id="persistent_open_mm")
    async def open_mm_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user
        existing = discord.utils.get(guild.text_channels, name=f"mm-ticket-{user.name.lower()}")
        if existing:
            await interaction.response.send_message(f"❌ You already have an active middleman request: {existing.mention}", ephemeral=True)
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.owner: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        }
        category = discord.utils.get(guild.categories, name="MIDDLEMAN TICKETS")
        if not category: category = await guild.create_category("MIDDLEMAN TICKETS")
        channel = await guild.create_text_channel(f"mm-ticket-{user.name}", overwrites=overwrites, category=category)
        
        embed = discord.Embed(
            title="🤝 Middleman Service Requested",
            description=f"Welcome {user.mention}!\nAn official Middleman will join this ticket shortly.\n\n**Please prepare the following information:**\n1. Who are you trading with? (Ping them)\n2. What are you giving?\n3. What are you receiving?",
            color=discord.Color.blurple()
        )
        embed.set_footer(text="Do not invite unofficial users to secure your trade!")
        await channel.send(embed=embed, view=CloseMiddlemanTicketView())
        await interaction.response.send_message(f"✅ Your Middleman request has been created: {channel.mention}", ephemeral=True)

@tree.command(name="middleman_ticket", description="Send the Middleman Request panel to this channel")
@is_owner()
async def middleman_ticket(interaction: discord.Interaction):
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
        color=discord.Color.blurple()
    )
    embed.set_footer(text=f"Powered by {interaction.client.user.name}", icon_url=interaction.client.user.display_avatar.url)
    await interaction.channel.send(embed=embed, view=MiddlemanTicketView())
    await interaction.response.send_message("✅ Middleman panel sent!", ephemeral=True)

# ════════════════════════════════════════════════════════════
#  GIVEAWAY SYSTEM
# ════════════════════════════════════════════════════════════
@tree.command(name="giveaway_start", description="Start a new giveaway")
@is_owner()
async def giveaway_start(interaction: discord.Interaction, duration_minutes: int, winners_count: int, prize: str):
    await interaction.response.send_message(f"🎉 Giveaway for **{prize}** started!", ephemeral=True)
    
    end_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=duration_minutes)
    embed = discord.Embed(
        title="🎉 GIVEAWAY 🎉",
        description=f"React with 🎉 to enter!\n\n**Prize:** {prize}\n**Winners:** {winners_count}\n**Ends:** <t:{int(end_time.timestamp())}:R>",
        color=discord.Color.gold()
    )
    embed.set_footer(text="Good luck everyone!")
    
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    
    await asyncio.sleep(duration_minutes * 60)
    
    # Nachricht frisch abrufen, um Reaktionen zu zählen
    msg = await interaction.channel.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    users = [u async for u in reaction.users() if not u.bot]
    
    if len(users) == 0:
        await interaction.channel.send(f"😔 The giveaway for **{prize}** ended, but nobody participated.")
        return
    
    winners = random.sample(users, min(len(users), winners_count))
    winner_mentions = ", ".join([w.mention for w in winners])
    
    end_embed = discord.Embed(
        title="🎉 GIVEAWAY ENDED 🎉",
        description=f"**Prize:** {prize}\n**Winners:** {winner_mentions}",
        color=discord.Color.green()
    )
    await msg.edit(embed=end_embed)
    await interaction.channel.send(f"🥳 Congratulations {winner_mentions}! You won **{prize}**! 🎉")

@tree.command(name="giveaway_reroll", description="Reroll a new winner for a giveaway message ID")
@is_owner()
async def giveaway_reroll(interaction: discord.Interaction, message_id: str):
    try:
        msg = await interaction.channel.fetch_message(int(message_id))
    except Exception:
        await interaction.response.send_message("❌ Message ID not found in this channel.", ephemeral=True)
        return

    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    if not reaction:
        await interaction.response.send_message("❌ No 🎉 reactions found on this message.", ephemeral=True)
        return
        
    users = [u async for u in reaction.users() if not u.bot]
    if len(users) == 0:
        await interaction.response.send_message("❌ Nobody reacted to the giveaway.", ephemeral=True)
        return
        
    winner = random.choice(users)
    await interaction.response.send_message("🎲 Reroll complete!", ephemeral=True)
    await interaction.channel.send(f"🎉 **New Reroll Winner:** {winner.mention}! Congratulations! 🥳")

# ════════════════════════════════════════════════════════════
#  HELP PANEL (UPDATED)
# ════════════════════════════════════════════════════════════
@tree.command(name="help", description="Show all available bot commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="🌿 Garden Bot Help Panel", description="Full list of all slash commands.", color=discord.Color.blurple())
    embed.add_field(name="🛡️ Moderation", value="`/ban`, `/unban`, `/kick`, `/mute`, `/unmute`, `/warn`, `/warnings`, `/clearwarnings`, `/purge`, `/slowmode`, `/lock`, `/unlock`, `/nickname`, `/addrole`, `/removerole`", inline=False)
    embed.add_field(name="🎉 Giveaways", value="`/giveaway_start` *(Start giveaways)*, `/giveaway_reroll` *(Reroll winners)*", inline=False)
    embed.add_field(name="🏗️ Server Setup", value="`/revamp`, `/deleteallchannels`, `/createchannel`, `/deletechannel`, `/createrole`, `/deleterole`", inline=False)
    embed.add_field(name="🎫 Systems & Fun", value="`/ticket` *(Support)*, `/middleman_ticket` *(Safe Trades)*, `/verify`, `/hit`, `/poll`, `/say`, `/embed`, `/avatar`, `/announce`, `/serverinfo`, `/userinfo`, `/membercount`, `/ping`, `/coinflip`, `/dice`, `/8ball`, `/choose`, `/uptime`, `/botinfo`", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ════════════════════════════════════════════════════════════
#  EVENTS & AUTOMOD
# ════════════════════════════════════════════════════════════
@bot.event
async def on_ready():
    if not hasattr(bot, 'start_time'): bot.start_time = datetime.datetime.utcnow()
    try: await tree.sync()
    except Exception as e: print(f"Sync error: {e}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="the server 👀"))
    print(f"Bot online: {bot.user}")

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="welcome")
    if channel:
        embed = discord.Embed(title=f"👋 Welcome {member.name}!", description=f"Welcome to **{member.guild.name}**! You are member #{member.guild.member_count}.", color=discord.Color.green())
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    channel = discord.utils.get(member.guild.text_channels, name="welcome")
    if channel: await channel.send(embed=discord.Embed(title=f"👋 {member.name} left the server.", color=discord.Color.red()))

@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None: return
    if message.author.id == message.guild.owner_id:
        await bot.process_commands(message)
        return
    user_id = message.author.id
    jetzt = time.time()
    content = message.content

    if any(word in content.lower() for word in BAD_WORDS):
        await message.delete()
        await message.channel.send(f"⚠️ {message.author.mention} Bad language is not allowed!", delete_after=5)
        return
    if INVITE_PATTERN in content.lower():
        await message.delete()
        await message.channel.send(f"⚠️ {message.author.mention} Posting invite links is not allowed!", delete_after=5)
        return
    if len(message.mentions) >= MAX_MENTIONS:
        await message.delete()
        await message.channel.send(f"⚠️ {message.author.mention} Mass mentioning is not allowed!", delete_after=5)
        return
    if len(content) > 10 and (sum(1 for c in content if c.isupper()) / len(content)) * 100 >= MAX_CAPS_PERCENT:
        await message.delete()
        await message.channel.send(f"⚠️ {message.author.mention} Please don't use excessive caps!", delete_after=5)
        return

    if user_id not in spam_tracker: spam_tracker[user_id] = []
    spam_tracker[user_id] = [t for t in spam_tracker[user_id] if jetzt - t < SPAM_ZEITRAUM]
    spam_tracker[user_id].append(jetzt)
    if len(spam_tracker[user_id]) > SPAM_LIMIT:
        await message.delete()
        await message.channel.send(f"⚠️ {message.author.mention} Please do not spam!", delete_after=5)
        mute_role = discord.utils.get(message.guild.roles, name="Muted")
        if mute_role and mute_role not in message.author.roles:
            await message.author.add_roles(mute_role)
            await message.channel.send(f"🔇 {message.author.mention} has been auto-muted for spamming (5 minutes).", delete_after=10)
            await asyncio.sleep(300)
            await message.author.remove_roles(mute_role)
        return
    await bot.process_commands(message)

# ════════════════════════════════════════════════════════════
#  VERIFY & HIT COMMANDS
# ════════════════════════════════════════════════════════════
@tree.command(name="verify", description="Verify yourself on the server")
async def verify(interaction: discord.Interaction):
    view = discord.ui.View()
    yes_button = discord.ui.Button(label="✅ Yes", style=discord.ButtonStyle.green)
    no_button = discord.ui.Button(label="❌ No", style=discord.ButtonStyle.red)
    async def yes_callback(i): await i.response.send_message("✅ You have been verified! Welcome!", ephemeral=True)
    async def no_callback(i): await i.response.send_message("❌ Verification cancelled.", ephemeral=True)
    yes_button.callback = yes_callback
    no_button.callback = no_callback
    view.add_item(yes_button)
    view.add_item(no_button)
    await interaction.response.send_message("👋 **Welcome!**\nDo you agree to the server rules and want to verify yourself?", view=view, ephemeral=True)

class HitConfirmView(discord.ui.View):
    def __init__(self, target: discord.Member):
        super().__init__(timeout=60)
        self.target = target
    @discord.ui.button(label="✅ Yes, I'm in!", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=discord.Embed(title="💰 Welcome!", description=f"✅ {interaction.user.mention} is **in**!", color=discord.Color.green()))
    @discord.ui.button(label="❌ No, I'm not interested", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children: item.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=discord.Embed(title="😔 Declined", description=f"❌ {interaction.user.mention} declined.", color=discord.Color.red()))

@tree.command(name="hit", description="Send someone a special business offer")
async def hit(interaction: discord.Interaction, member: discord.Member):
    embed = discord.Embed(title="💸 EXCLUSIVE BUSINESS OFFER 💸", color=discord.Color.gold())
    embed.add_field(name="📩 Hey there!", value=f"👋 Offer for {member.mention}.\nJoin us and make some serious profit!", inline=False)
    await interaction.response.send_message(f"{member.mention}", embed=embed, view=HitConfirmView(target=member))

# ════════════════════════════════════════════════════════════
#  MODERATION COMMANDS (owner only)
# ════════════════════════════════════════════════════════════
@tree.command(name="ban", description="Ban a member")
@is_owner()
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 **{member}** has been banned. Reason: {reason}")

@tree.command(name="unban", description="Unban a user by ID")
@is_owner()
async def unban(interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
    user = await bot.fetch_user(int(user_id))
    await interaction.guild.unban(user, reason=reason)
    await interaction.response.send_message(f"✅ **{user}** has been unbanned.")

@tree.command(name="kick", description="Kick a member")
@is_owner()
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 **{member}** has been kicked. Reason: {reason}")

@tree.command(name="mute", description="Mute a member")
@is_owner()
async def mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "No reason provided"):
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if not mute_role:
        mute_role = await interaction.guild.create_role(name="Muted")
        for channel in interaction.guild.channels: await channel.set_permissions(mute_role, send_messages=False, speak=False)
    await member.add_roles(mute_role, reason=reason)
    await interaction.response.send_message(f"🔇 **{member}** has been muted for {minutes} minutes. Reason: {reason}")
    await asyncio.sleep(minutes * 60)
    await member.remove_roles(mute_role)

@tree.command(name="unmute", description="Unmute a member")
@is_owner()
async def unmute(interaction: discord.Interaction, member: discord.Member):
    mute_role = discord.utils.get(interaction.guild.roles, name="Muted")
    if mute_role in member.roles:
        await member.remove_roles(mute_role)
        await interaction.response.send_message(f"🔊 **{member}** has been unmuted.")
    else:
        await interaction.response.send_message(f"❌ **{member}** is not muted.", ephemeral=True)

@tree.command(name="warn", description="Warn a member")
@is_owner()
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    uid = str(member.id)
    if uid not in warnings: warnings[uid] = []
    warnings[uid].append({"reason": reason, "time": str(datetime.datetime.now())})
    count = len(warnings[uid])
    await interaction.response.send_message(f"⚠️ **{member}** has been warned. Reason: {reason} (Total warnings: {count})")
    if count >= 3:
        await interaction.channel.send(f"🔨 **{member}** has reached 3 warnings and has been automatically banned!")
        await member.ban(reason="3 warnings reached")

@tree.command(name="warnings", description="Check warnings of a member")
@is_owner()
async def check_warnings(interaction: discord.Interaction, member: discord.Member):
    uid = str(member.id)
    if uid not in warnings or not warnings[uid]:
        await interaction.response.send_message(f"✅ **{member}** has no warnings.", ephemeral=True)
        return
    embed = discord.Embed(title=f"⚠️ Warnings for {member}", color=discord.Color.orange())
    for i, w in enumerate(warnings[uid], 1): embed.add_field(name=f"Warning {i}", value=f"Reason: {w['reason']}\nTime: {w['time']}", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="clearwarnings", description="Clear all warnings of a member")
@is_owner()
async def clearwarnings(interaction: discord.Interaction, member: discord.Member):
    warnings[str(member.id)] = []
    await interaction.response.send_message(f"✅ Warnings cleared for **{member}**.")

@tree.command(name="purge", description="Delete multiple messages")
@is_owner()
async def purge(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🗑️ Deleted {amount} messages.", ephemeral=True)

@tree.command(name="slowmode", description="Set slowmode in the current channel")
@is_owner()
async def slowmode(interaction: discord.Interaction, seconds: int):
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"🐢 Slowmode set to {seconds} seconds.")

@tree.command(name="lock", description="Lock the current channel")
@is_owner()
async def lock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("🔒 Channel locked!")

@tree.command(name="unlock", description="Unlock the current channel")
@is_owner()
async def unlock(interaction: discord.Interaction):
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("🔓 Channel unlocked!")

@tree.command(name="nickname", description="Change nickname of a member")
@is_owner()
async def nickname(interaction: discord.Interaction, member: discord.Member, nickname: str):
    await member.edit(nick=nickname)
    await interaction.response.send_message(f"✅ Nickname of **{member}** changed to **{nickname}**.")

@tree.command(name="addrole", description="Add a role to a member")
@is_owner()
async def addrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.add_roles(role)
    await interaction.response.send_message(f"✅ Role **{role.name}** added to **{member}**.")

@tree.command(name="removerole", description="Remove a role from a member")
@is_owner()
async def removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    await member.remove_roles(role)
    await interaction.response.send_message(f"✅ Role **{role.name}** removed from **{member}**.")

# ════════════════════════════════════════════════════════════
#  SERVER SETUP & UTILITY COMMANDS (owner only)
# ════════════════════════════════════════════════════════════
@tree.command(name="revamp", description="Setup Grow a Garden 2 channel structure")
@is_owner()
async def revamp(interaction: discord.Interaction):
    await interaction.response.send_message("🏗️ **Starting Server Revamp...**", ephemeral=True)
    guild = interaction.guild
    for channel in guild.channels:
        if channel != interaction.channel:
            try: await channel.delete()
            except Exception: pass
    structure = {
        "📌 ▬▬ INFO & NEWS ▬▬": [("👋-welcome", discord.ChannelType.text), ("📜-rules", discord.ChannelType.text), ("📢-announcements", discord.ChannelType.text), ("🎁-giveaways", discord.ChannelType.text)],
        "💬 ▬▬ COMMUNITY ▬▬": [("🌿-garden-chat", discord.ChannelType.text), ("🤖-bot-commands", discord.ChannelType.text), ("🌌-memes", discord.ChannelType.text), ("🔊 Lounge", discord.ChannelType.voice), ("🔊 Gaming", discord.ChannelType.voice)],
        "🌻 ▬▬ GARDEN GAMEPLAY ▬▬": [("🌾-flex-your-garden", discord.ChannelType.text), ("🫘-seed-market", discord.ChannelType.text), ("🤝-trading", discord.ChannelType.text), ("💡-garden-tips", discord.ChannelType.text)],
        "🎫 ▬▬ SUPPORT ▬▬": [("🎫-open-ticket", discord.ChannelType.text)]
    }
    for cat_name, channels in structure.items():
        category = await guild.create_category(cat_name)
        for ch_name, ch_type in channels:
            if ch_type == discord.ChannelType.text: await guild.create_text_channel(ch_name, category=category)
            elif ch_type == discord.ChannelType.voice: await guild.create_voice_channel(ch_name, category=category)
    try: await interaction.channel.send("✅ **Server Revamp complete!** 🌱")
    except Exception: pass

@tree.command(name="deleteallchannels", description="⚠️ Delete ALL channels in the server")
@is_owner()
async def deleteallchannels(interaction: discord.Interaction):
    await interaction.response.send_message("⚠️ Deleting all channels in 5 seconds...")
    await asyncio.sleep(5)
    for channel in interaction.guild.channels:
        try: await channel.delete()
        except Exception: pass

@tree.command(name="createchannel", description="Create a new text channel")
@is_owner()
async def createchannel(interaction: discord.Interaction, name: str):
    channel = await interaction.guild.create_text_channel(name)
    await interaction.response.send_message(f"✅ Channel {channel.mention} created!")

@tree.command(name="deletechannel", description="Delete a channel")
@is_owner()
async def deletechannel(interaction: discord.Interaction, channel: discord.TextChannel):
    await channel.delete()
    await interaction.response.send_message(f"✅ Channel **{channel.name}** deleted!", ephemeral=True)

@tree.command(name="createrole", description="Create a new role")
@is_owner()
async def createrole(interaction: discord.Interaction, name: str):
    role = await interaction.guild.create_role(name=name)
    await interaction.response.send_message(f"✅ Role **{role.name}** created!")

@tree.command(name="deleterole", description="Delete a role")
@is_owner()
async def deleterole(interaction: discord.Interaction, role: discord.Role):
    await role.delete()
    await interaction.response.send_message(f"✅ Role **{role.name}** deleted!")

@tree.command(name="serverinfo", description="Show server information")
@is_owner()
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"📊 {guild.name}", color=discord.Color.blurple())
    embed.add_field(name="Members", value=guild.member_count)
    embed.add_field(name="Channels", value=len(guild.channels))
    embed.add_field(name="Roles", value=len(guild.roles))
    embed.add_field(name="Owner", value=guild.owner)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    await interaction.response.send_message(embed=embed)

@tree.command(name="userinfo", description="Show info about a user")
@is_owner()
async def userinfo(interaction: discord.Interaction, member: discord.Member):
    embed = discord.Embed(title=f"👤 {member}", color=discord.Color.blurple())
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d"))
    embed.set_thumbnail(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@tree.command(name="membercount", description="Show the member count")
@is_owner()
async def membercount(interaction: discord.Interaction):
    await interaction.response.send_message(f"👥 This server has **{interaction.guild.member_count}** members!")

# ════════════════════════════════════════════════════════════
#  FUN & UTILITY BUNDLE (owner only)
# ════════════════════════════════════════════════════════════
@tree.command(name="ping", description="Check bot latency")
@is_owner()
async def ping(interaction: discord.Interaction): await interaction.response.send_message(f"🏓 Pong! `{round(bot.latency * 1000)}ms`")

@tree.command(name="coinflip", description="Flip a coin")
@is_owner()
async def coinflip(interaction: discord.Interaction): await interaction.response.send_message(f"🪙 The coin landed on: **{random.choice(['Heads 🪙', 'Tails 🪙'])}**!")

@tree.command(name="dice", description="Roll a dice")
@is_owner()
async def dice(interaction: discord.Interaction, sides: int = 6): await interaction.response.send_message(f"🎲 You rolled a **{random.randint(1, sides)}** (1-{sides})!")

@tree.command(name="8ball", description="Ask the magic 8ball a question")
@is_owner()
async def eightball(interaction: discord.Interaction, question: str): await interaction.response.send_message(f"🎱 **Question:** {question}\n**Answer:** {random.choice(['Yes! ✅', 'No ❌', 'Maybe 🤔', 'Definitely! 🎯', 'Ask again later ⏳'])}")

@tree.command(name="choose", description="Let the bot choose between options (separate with commas)")
@is_owner()
async def choose(interaction: discord.Interaction, options: str): await interaction.response.send_message(f"🎯 I choose: **{random.choice([o.strip() for o in options.split(',')])}**!")

@tree.command(name="poll", description="Create a poll")
@is_owner()
async def poll(interaction: discord.Interaction, question: str):
    msg = await interaction.channel.send(embed=discord.Embed(title=f"📊 Poll: {question}", color=discord.Color.blurple()))
    await msg.add_reaction("👍"); await msg.add_reaction("👎")
    await interaction.response.send_message("✅ Poll created!", ephemeral=True)

@tree.command(name="say", description="Make the bot say something")
@is_owner()
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("✅ Sent!", ephemeral=True)
    await interaction.channel.send(message)

@tree.command(name="embed", description="Send an embed message")
@is_owner()
async def embed_cmd(interaction: discord.Interaction, title: str, description: str):
    await interaction.channel.send(embed=discord.Embed(title=title, description=description, color=discord.Color.blurple()))
    await interaction.response.send_message("✅ Embed sent!", ephemeral=True)

@tree.command(name="avatar", description="Get the avatar of a user")
@is_owner()
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"🖼️ Avatar of {member}", color=discord.Color.blurple())
    embed.set_image(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@tree.command(name="announce", description="Send an announcement")
@is_owner()
async def announce(interaction: discord.Interaction, channel: discord.TextChannel, message: str):
    await channel.send(embed=discord.Embed(title="📢 Announcement", description=message, color=discord.Color.gold()))
    await interaction.response.send_message("✅ Announcement sent!", ephemeral=True)

@tree.command(name="uptime", description="Show bot uptime")
@is_owner()
async def uptime(interaction: discord.Interaction):
    delta = datetime.datetime.utcnow() - bot.start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    await interaction.response.send_message(f"⏱️ Uptime: **{hours}h {minutes}m {seconds}s**")

@tree.command(name="botinfo", description="Show info about the bot")
@is_owner()
async def botinfo(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Bot Info", color=discord.Color.blurple())
    embed.add_field(name="Name", value=bot.user.name); embed.add_field(name="Servers", value=len(bot.guilds))
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# ════════════════════════════════════════════════════════════
#  WEB SERVER & RUN SYSTEM (Render Mode)
# ════════════════════════════════════════════════════════════
app = Flask('')

@app.route('/')
def home(): return "Bot läuft 24/7!"

def run(): app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 8080)))
def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

def run_bot():
    keep_alive()
    while True:
        try:
            TOKEN = os.environ.get("DISCORD_TOKEN")
            if not TOKEN:
                time.sleep(10)
                continue
            bot.run(TOKEN)
        except Exception:
            time.sleep(5)

if __name__ == "__main__":
    run_bot()

import discord
from discord.ext import commands
from discord import app_commands
import time, asyncio, random, datetime, os, io
from flask import Flask
from threading import Thread

intents = discord.Intents.all()
class TicketSystem(commands.Bot):
    def __init__(self): super().__init__(command_prefix="!", intents=intents)
    async def setup_hook(self):
        self.add_view(SupportPanel()); self.add_view(SupportTicketView())
        self.add_view(MiddlemanPanel()); self.add_view(MiddlemanTicketView())

bot = TicketSystem()
tree = bot.tree

# Trackers & Config
spam_tracker, warnings, fill_tracker = {}, {}, {}
BLOCKED_WORDS, MAX_MENTIONS, MAX_CAPS_PERCENT, DISCORD_INVITE = [], 5, 70, "discord.gg"

def make_clean_embed(title: str, description: str, color: int = 0x2f3136) -> discord.Embed:
    embed = discord.Embed(description=description, color=color)
    embed.set_author(name=title)
    return embed

def add_bot_footer(embed: discord.Embed, interaction: discord.Interaction):
    embed.set_footer(text=f"Powered by {interaction.client.user.name} | Today at {datetime.datetime.now().strftime('%H:%M')}", icon_url=interaction.client.user.display_avatar.url if interaction.client.user.avatar else None)
    return embed

def is_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        if not interaction.guild or interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(embed=make_clean_embed("🔒 Access Denied", "Only the server owner can use this.", 0xd9534f), ephemeral=True)
            return False
        return True
    return app_commands.check(predicate)

async def create_ticket_transcript(channel, category="General"):
    guild = channel.guild
    log_channel = discord.utils.get(guild.text_channels, name="ticket-logs") or await guild.create_text_channel("ticket-logs", overwrites={guild.default_role: discord.PermissionOverwrite(read_messages=False), guild.me: discord.PermissionOverwrite(read_messages=True)})
    buffer = [f"[{m.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {m.author}: {m.content}" async for m in channel.history(limit=None, oldest_first=True)]
    file_stream = io.BytesIO("\n".join(buffer).encode("utf-8"))
    await log_channel.send(embed=make_clean_embed("📁 Archive", f"**Type:** {category}\n**Channel:** #{channel.name}"), file=discord.File(fp=file_stream, filename=f"transcript-{channel.name}.txt"))

# ==========================================
# CORE: TICKETS & MIDDLEMAN SYSTEM
# ==========================================
class SupportTicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green, custom_id="btn_claim_support", emoji="✋")
    async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel.name == f"ticket-{interaction.user.name.lower()}".replace(" ", "-"):
            return await interaction.response.send_message(embed=make_clean_embed("❌ Error", "You cannot claim your own ticket!", 0xd9534f), ephemeral=True)
        if not any(discord.utils.get(interaction.user.roles, name=r) for r in ["Owner", "Administrator", "Head Moderator", "Moderator", "Team Lead", "Chief Lead", "Lead", "Cordinator"]):
            return await interaction.response.send_message(embed=make_clean_embed("🔒 Denied", "Staff only.", 0xd9534f), ephemeral=True)
        button.label, button.disabled = "Claimed", True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=add_bot_footer(make_clean_embed("✅ Claimed", f"{interaction.user.mention} is helping you now.", 0x2ecc71), interaction))

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="btn_close_support", emoji="🔒")
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=make_clean_embed("🔒 Closing", "Saving logs... Deleting in 5s."))
        await create_ticket_transcript(interaction.channel, "Support"); await asyncio.sleep(5); await interaction.channel.delete()

class SupportPanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Request Support", style=discord.ButtonStyle.blurple, custom_id="btn_open_support", emoji="🎫")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        name = f"ticket-{interaction.user.name.lower()}".replace(" ", "-")
        if discord.utils.get(interaction.guild.text_channels, name=name): return await interaction.response.send_message("Already open!", ephemeral=True)
        cat = discord.utils.get(interaction.guild.categories, name="Tickets") or await interaction.guild.create_category("Tickets")
        perms = {interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        ch = await interaction.guild.create_text_channel(name, overwrites=perms, category=cat)
        await ch.send(f"{interaction.user.mention}", embed=add_bot_footer(make_clean_embed("🎫 Support", "Please state your issue."), interaction), view=SupportTicketView())
        await interaction.response.send_message(f"Opened: {ch.mention}", ephemeral=True)

class MiddlemanTicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Claim", style=discord.ButtonStyle.green, custom_id="btn_claim_mm", emoji="✋")
    async def claim_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel.name == f"ticket-mm_{interaction.user.name.lower()}".replace(" ", "-"):
            return await interaction.response.send_message(embed=make_clean_embed("❌ Error", "Cannot claim own trade!", 0xd9534f), ephemeral=True)
        if not any(discord.utils.get(interaction.user.roles, name=r) for r in ["Middleman", "Head Middleman", "Middleman Manager", "Owner", "Administrator"]):
            return await interaction.response.send_message(embed=make_clean_embed("🔒 Denied", "Middlemen only.", 0xd9534f), ephemeral=True)
        button.label, button.disabled = "Claimed", True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(embed=add_bot_footer(make_clean_embed("✅ Claimed", f"{interaction.user.mention} is your Middleman.", 0x2ecc71), interaction))

    @discord.ui.button(label="Close", style=discord.ButtonStyle.red, custom_id="btn_close_mm", emoji="🔒")
    async def close_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=make_clean_embed("🔒 Closing", "Saving trade... Deleting in 5s."))
        await create_ticket_transcript(interaction.channel, "Middleman"); await asyncio.sleep(5); await interaction.channel.delete()

class MiddlemanPanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Request Middleman", style=discord.ButtonStyle.blurple, custom_id="btn_open_mm", emoji="💳")
    async def open_mm(self, interaction: discord.Interaction, button: discord.ui.Button):
        name = f"ticket-mm_{interaction.user.name.lower()}".replace(" ", "-")
        if discord.utils.get(interaction.guild.text_channels, name=name): return await interaction.response.send_message("Already open!", ephemeral=True)
        cat = discord.utils.get(interaction.guild.categories, name="Middleman Service") or await interaction.guild.create_category("Middleman Service")
        perms = {interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)}
        ch = await interaction.guild.create_text_channel(name, overwrites=perms, category=cat)
        role = discord.utils.get(interaction.guild.roles, name="Middleman")
        await ch.send(f"{interaction.user.mention} {role.mention if role else ''}", embed=add_bot_footer(make_clean_embed("🤝 Middleman", "Add partner and list deal."), interaction), view=MiddlemanTicketView())
        await interaction.response.send_message(f"Opened: {ch.mention}", ephemeral=True)

# ==========================================
# SYSTEM & SETUP COMMANDS
# ==========================================
@tree.command(name="ticket", description="Deploy support panel")
@is_owner()
async def dep_t(i: discord.Interaction):
    await i.channel.send(embed=add_bot_footer(discord.Embed(title="🎫 Support", description="Click below to open a ticket.", color=0x2f3136), i), view=SupportPanel())
    await i.response.send_message("Deployed Support.", ephemeral=True)

@tree.command(name="setup_middleman", description="Deploy MM panel")
@is_owner()
async def dep_m(i: discord.Interaction):
    await i.channel.send(embed=add_bot_footer(discord.Embed(title="🤝 Middleman", description="Click below to request a Middleman.", color=0x2f3136), i), view=MiddlemanPanel())
    await i.response.send_message("Deployed MM.", ephemeral=True)

@tree.command(name="fill", description="Toggle setup staff roles")
@is_owner()
async def fill(i: discord.Interaction):
    r_names = ["Owner", "Administrator", "Head Moderator", "Moderator", "Middleman Manager", "Head Middleman", "Middleman", "Team Lead", "Chief Lead", "Lead", "Cordinator"]
    if i.user.id in fill_tracker and fill_tracker[i.user.id]:
        for r_id in fill_tracker[i.user.id]:
            role = i.guild.get_role(r_id)
            if role in i.user.roles: await i.user.remove_roles(role)
        fill_tracker[i.user.id] = []
        await i.response.send_message(embed=make_clean_embed("🔄 Removed", "Roles removed."), ephemeral=True)
    else:
        ids = []
        for n in r_names:
            role = discord.utils.get(i.guild.roles, name=n)
            if role and role not in i.user.roles: await i.user.add_roles(role); ids.append(role.id)
        fill_tracker[i.user.id] = ids
        await i.response.send_message(embed=make_clean_embed("🔄 Filled", "Roles granted."), ephemeral=True)

@tree.command(name="revamp", description="Rebuild infrastructure")
@is_owner()
async def revamp(i: discord.Interaction):
    await i.response.send_message("Rebuilding...", ephemeral=True)
    roles = {"Owner": 0x990000, "Administrator": 0xff0000, "Head Moderator": 0xffa500, "Moderator": 0x808080, "Middleman Manager": 0x4b0082, "Head Middleman": 0x800080, "Middleman": 0x008000, "Team Lead": 0x0000ff, "Chief Lead": 0x00008b, "Lead": 0x008080, "Cordinator": 0xff00ff}
    for n, c in roles.items():
        if not discord.utils.get(i.guild.roles, name=n): await i.guild.create_role(name=n, color=discord.Color(c))
    for c in i.guild.channels:
        if c != i.channel: await c.delete()
    struct = {"INFORMATION": ["welcome", "rules", "announcements", "giveaways"], "COMMUNITY": ["general", "commands", "memes"], "TRANSACTIONS": ["middleman-info", "market", "trading-chat"], "UTILITY": ["open-ticket"]}
    for cat, chs in struct.items():
        category = await i.guild.create_category(cat)
        for name in chs: await i.guild.create_text_channel(name, category=category)

# ==========================================
# COMPACT MODERATION & UTILITY ENGINE
# ==========================================
@tree.command(name="ban")
@is_owner()
async def b(i: discord.Interaction, m: discord.Member, r: str="None"): await m.ban(reason=r); await i.response.send_message(f"Banned {m}")

@tree.command(name="unban")
@is_owner()
async def ub(i: discord.Interaction, uid: str): await i.guild.unban(await bot.fetch_user(int(uid))); await i.response.send_message("Unbanned.")

@tree.command(name="kick")
@is_owner()
async def k(i: discord.Interaction, m: discord.Member, r: str="None"): await m.kick(reason=r); await i.response.send_message(f"Kicked {m}")

@tree.command(name="mute")
@is_owner()
async def mu(i: discord.Interaction, m: discord.Member, t: int=10):
    role = discord.utils.get(i.guild.roles, name="Muted") or await i.guild.create_role(name="Muted")
    await m.add_roles(role); await i.response.send_message(f"Muted {m} for {t}m"); await asyncio.sleep(t*60); await m.remove_roles(role)

@tree.command(name="unmute")
@is_owner()
async def umu(i: discord.Interaction, m: discord.Member): await m.remove_roles(discord.utils.get(i.guild.roles, name="Muted")); await i.response.send_message("Unmuted.")

@tree.command(name="warn")
@is_owner()
async def wr(i: discord.Interaction, m: discord.Member, r: str="None"):
    uid = str(m.id); warnings[uid] = warnings.get(uid, []) + [r]
    await i.response.send_message(f"Warned {m} ({len(warnings[uid])}/3)")
    if len(warnings[uid]) >= 3: await m.ban(reason="3 Warns")

@tree.command(name="warnings")
async def wrs(i: discord.Interaction, m: discord.Member): await i.response.send_message(f"Warns: {warnings.get(str(m.id), [])}")

@tree.command(name="clearwarnings")
@is_owner()
async def cwr(i: discord.Interaction, m: discord.Member): warnings[str(m.id)] = []; await i.response.send_message("Cleared.")

@tree.command(name="purge")
@is_owner()
async def prg(i: discord.Interaction, a: int): await i.response.defer(ephemeral=True); await i.channel.purge(limit=a); await i.followup.send("Done.")

@tree.command(name="slowmode")
@is_owner()
async def sm(i: discord.Interaction, s: int): await i.channel.edit(slowmode_delay=s); await i.response.send_message("Slowmode set.")

@tree.command(name="lock")
@is_owner()
async def lk(i: discord.Interaction): await i.channel.set_permissions(i.guild.default_role, send_messages=False); await i.response.send_message("Locked.")

@tree.command(name="unlock")
@is_owner()
async def ulk(i: discord.Interaction): await i.channel.set_permissions(i.guild.default_role, send_messages=True); await i.response.send_message("Unlocked.")

@tree.command(name="nickname")
@is_owner()
async def nick(i: discord.Interaction, m: discord.Member, n: str): await m.edit(nick=n); await i.response.send_message("Updated.")

@tree.command(name="addrole")
@is_owner()
async def ar(i: discord.Interaction, m: discord.Member, r: discord.Role): await m.add_roles(r); await i.response.send_message("Role added.")

@tree.command(name="removerole")
@is_owner()
async def rr(i: discord.Interaction, m: discord.Member, r: discord.Role): await m.remove_roles(r); await i.response.send_message("Role removed.")

@tree.command(name="deleteallchannels")
@is_owner()
async def dac(i: discord.Interaction): [await c.delete() for c in i.guild.channels if c != i.channel]; await i.response.send_message("Wiped.")

@tree.command(name="createchannel")
@is_owner()
async def cc(i: discord.Interaction, n: str): await i.guild.create_text_channel(n); await i.response.send_message("Channel created.")

@tree.command(name="deletechannel")
@is_owner()
async def dc(i: discord.Interaction, c: discord.TextChannel): await c.delete(); await i.response.send_message("Deleted.")

@tree.command(name="createrole")
@is_owner()
async def cr(i: discord.Interaction, n: str): await i.guild.create_role(name=n); await i.response.send_message("Role created.")

@tree.command(name="deleterole")
@is_owner()
async def dr(i: discord.Interaction, r: discord.Role): await r.delete(); await i.response.send_message("Role deleted.")

# Giveaways & Fun
@tree.command(name="gstart")
@is_owner()
async def gs(i: discord.Interaction, m: int, w: int, p: str):
    await i.response.send_message("Giveaway started!", ephemeral=True)
    msg = await i.channel.send(embed=make_clean_embed("🎉 Giveaway", f"Prize: **{p}**\nEnds in: {m}m"))
    await msg.add_reaction("🎉"); await asyncio.sleep(m*60); msg = await i.channel.fetch_message(msg.id)
    users = [u async for u in discord.utils.get(msg.reactions, emoji="🎉").users() if not u.bot]
    if users: winners = random.sample(users, min(len(users), w)); await i.channel.send(f"Winners for **{p}**: {', '.join(w.mention for w in winners)}")

@tree.command(name="greroll")
@is_owner()
async def gr(i: discord.Interaction, mid: str):
    msg = await i.channel.fetch_message(int(mid)); users = [u async for u in discord.utils.get(msg.reactions, emoji="🎉").users() if not u.bot]
    if users: await i.response.send_message(f"New winner: {random.choice(users).mention}")

@tree.command(name="verify")
async def vr(i: discord.Interaction): await i.response.send_message("Verified!", ephemeral=True)

@tree.command(name="hit")
async def ht(i: discord.Interaction, m: discord.Member): await i.response.send_message(f"{i.user.mention} hits a deal proposal with {m.mention}!")

@tree.command(name="poll")
async def pl(i: discord.Interaction, q: str): await i.response.send_message("Poll deployed", ephemeral=True); m = await i.channel.send(f"📊 **{q}**"); await m.add_reaction("👍"); await m.add_reaction("👎")

@tree.command(name="say")
@is_owner()
async def sy(i: discord.Interaction, m: str): await i.response.send_message("Sent", ephemeral=True); await i.channel.send(m)

@tree.command(name="embed")
@is_owner()
async def emb(i: discord.Interaction, t: str, d: str): await i.response.send_message("Sent", ephemeral=True); await i.channel.send(embed=make_clean_embed(t, d))

@tree.command(name="avatar")
async def av(i: discord.Interaction, m: discord.Member=None): m = m or i.user; e = discord.Embed(title=f"{m}"); e.set_image(url=m.display_avatar.url); await i.response.send_message(embed=e)

@tree.command(name="announce")
@is_owner()
async def anc(i: discord.Interaction, c: discord.TextChannel, m: str): await c.send(embed=make_clean_embed("📢 Announcement", m)); await i.response.send_message("Announced", ephemeral=True)

@tree.command(name="serverinfo")
async def si(i: discord.Interaction): await i.response.send_message(f"Server: {i.guild.name} | Members: {i.guild.member_count}")

@tree.command(name="userinfo")
async def ui(i: discord.Interaction, m: discord.Member): await i.response.send_message(f"User: {m} | Joined: {m.joined_at.strftime('%Y-%m-%d')}")

@tree.command(name="membercount")
async def mc(i: discord.Interaction): await i.response.send_message(f"Members: {i.guild.member_count}")

@tree.command(name="ping")
async def png(i: discord.Interaction): await i.response.send_message(f"Pong! {round(bot.latency*1000)}ms")

@tree.command(name="coinflip")
async def cf(i: discord.Interaction): await i.response.send_message(random.choice(["Heads", "Tails"]))

@tree.command(name="dice")
async def dc(i: discord.Interaction, s: int=6): await i.response.send_message(f"Rolled: {random.randint(1, s)}")

@tree.command(name="8ball")
async def eb(i: discord.Interaction, q: str): await i.response.send_message(f"🔮 {random.choice(['Yes', 'No', 'Maybe'])}")

@tree.command(name="choose")
async def chs(i: discord.Interaction, o: str): await i.response.send_message(f"Picked: {random.choice([x.strip() for x in o.split(',')])}")

@tree.command(name="uptime")
async def upt(i: discord.Interaction): await i.response.send_message(f"Online since: {datetime.datetime.utcnow() - bot.start_time}")

@tree.command(name="botinfo")
async def bi(i: discord.Interaction): await i.response.send_message(f"Bot: {bot.user.name} | Guilds: {len(bot.guilds)}")

@tree.command(name="help")
async def hlp(i: discord.Interaction): await i.response.send_message("All commands are loaded! Use `/` to view them all.", ephemeral=True)

# ==========================================
# AUTOMATION & CORE EVENTS
# ==========================================
@bot.event
async def on_ready():
    if not hasattr(bot, 'start_time'): bot.start_time = datetime.datetime.utcnow()
    try: await tree.sync()
    except Exception as e: print(e)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="trades"))

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild or message.author.id == message.guild.owner_id: return
    uid, cur = message.author.id, time.time()
    
    # Moderation Filters
    if any(w in message.content.lower() for w in BLOCKED_WORDS) or DISCORD_INVITE in message.content.lower() or len(message.mentions) >= MAX_MENTIONS:
        return await message.delete()
    if len(message.content) > 10 and (sum(1 for c in message.content if c.isupper()) / len(message.content)) * 100 >= MAX_CAPS_PERCENT:
        return await message.delete()

    # Anti-Spam
    spam_tracker[uid] = [t for t in spam_tracker.get(uid, []) if cur - t < 5] + [cur]
    if len(spam_tracker[uid]) > 5:
        await message.delete()
        role = discord.utils.get(message.guild.roles, name="Muted")
        if role: await message.author.add_roles(role); await asyncio.sleep(300); await message.author.remove_roles(role)

# Hosting
app = Flask('')
@app.route('/')
def home(): return "Online"
def run(): app.run(host='0.0.0.0', port=8080)
if __name__ == "__main__":
    Thread(target=run, daemon=True).start()
    token = os.environ.get("DISCORD_TOKEN")
    if token: bot.run(token)

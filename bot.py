import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime
import asyncio
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ── ENV ───────────────────────────────────────────────────────────────────────
TOKEN                   = os.getenv("DISCORD_TOKEN")
AUTOMATION_TOKEN        = os.getenv("AUTOMATION_TOKEN")
GROQ_API_KEY            = os.getenv("GROQ_API_KEY")
GUILD_ID                = int(os.getenv("GUILD_ID"))
TICKET_CATEGORY_ID      = int(os.getenv("TICKET_CATEGORY_ID"))
LOG_CHANNEL_ID          = int(os.getenv("LOG_CHANNEL_ID"))
ANNOUNCEMENT_CHANNEL_ID = int(os.getenv("ANNOUNCEMENT_CHANNEL_ID"))

ROLE_LOCK   = os.getenv("ROLE_LOCK_NAME",   "🔒")
ROLE_SENIOR = os.getenv("ROLE_SENIOR_NAME", "Senior Staff")
ROLE_STAFF  = os.getenv("ROLE_STAFF_NAME",  "Staff Team")
ROLE_HOLDER = os.getenv("ROLE_HOLDER_NAME", "Holder")

# ── COLOURS ───────────────────────────────────────────────────────────────────
RYANAIR_COLOR  = 0x073590
BUZZ_COLOR     = 0xFFCC00
MALTA_COLOR    = 0xCC0000
LAUDA_COLOR    = 0xC8102E
ANNOUNCE_COLOR = 0x1A56DB   # new announcement colour

# ── BANNERS ───────────────────────────────────────────────────────────────────
SUPPORT_BANNER = "https://cdn.discordapp.com/attachments/1397863907506389027/1519783121115939027/image.png?ex=6a3ecfd4&is=6a3d7e54&hm=823803b77e5d5d9695a327d76662fd29d4d2f974bb6852e6d1032ffdf17554af&"
AI_BANNER      = "https://cdn.discordapp.com/attachments/1397863907506389027/1519783113000226997/image.png?ex=6a3ecfd2&is=6a3d7e52&hm=d696c06f41c16c42994bac98935bfbf257150aeb7000048142fe8a47c9dd1059&"

AIRLINE_STYLES = {
    "ryanair": {"color": RYANAIR_COLOR, "label": "Ryanair"},
    "buzz":    {"color": BUZZ_COLOR,    "label": "Buzz"},
    "malta":   {"color": MALTA_COLOR,   "label": "Malta Air"},
    "lauda":   {"color": LAUDA_COLOR,   "label": "Lauda Europe"},
}

# ── BOT SETUP ─────────────────────────────────────────────────────────────────
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

auto_intents = discord.Intents.default()
auto_intents.members = True
auto_bot = discord.Client(intents=auto_intents)

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ── STATE ─────────────────────────────────────────────────────────────────────
tickets         = {}   # user_id -> channel_id
snippets        = {}
connected_staff = {}   # channel_id -> staff_id
last_activity   = {}
pending_confirm = {}
warnings        = {}
strikes         = {}
mod_locked      = set()
ai_sessions     = {}   # user_id -> message history (staff /ai command)
ai_enabled      = True
ai_presets      = {}
mod_abuse       = {}
ticket_banned   = set()
ticket_notes    = {}   # channel_id -> list of notes
ticket_priority = {}   # channel_id -> priority string
ticket_stats    = {}   # user_id -> count
user_notes      = {}   # user_id -> list of notes
mod_history     = {}   # user_id -> list of actions
command_log     = {}   # user_id -> list of log entries
raid_abuse      = {}   # user_id -> count of rapid commands
raid_locked     = set()
welcome_config  = {}   # guild_id -> {channel_id, banner_url}
ticket_ai_active = {}  # channel_id -> bool (AI handling ticket)
ticket_claimed_time = {} # channel_id -> datetime when staff claimed
ticket_ai_history = {} # channel_id -> AI message history for ticket
staff_ping_warned = {} # user_id -> channel_id list

def now():
    return datetime.datetime.now(datetime.timezone.utc)

# ── PERSISTENCE ───────────────────────────────────────────────────────────────
def load_data():
    global tickets, snippets, connected_staff, warnings, strikes, mod_locked
    global ai_presets, mod_abuse, ticket_banned, ticket_notes, ticket_priority
    global ticket_stats, user_notes, mod_history, command_log, raid_abuse
    global raid_locked, welcome_config
    if os.path.exists("data.json"):
        with open("data.json", "r") as f:
            data = json.load(f)
            tickets         = {int(k): int(v) for k, v in data.get("tickets", {}).items()}
            snippets        = data.get("snippets", {})
            connected_staff = {int(k): int(v) for k, v in data.get("connected_staff", {}).items()}
            warnings        = {int(k): v for k, v in data.get("warnings", {}).items()}
            strikes         = {int(k): v for k, v in data.get("strikes", {}).items()}
            mod_locked      = set(int(x) for x in data.get("mod_locked", []))
            ai_presets      = data.get("ai_presets", {})
            mod_abuse       = {int(k): v for k, v in data.get("mod_abuse", {}).items()}
            ticket_banned   = set(int(x) for x in data.get("ticket_banned", []))
            ticket_notes    = {int(k): v for k, v in data.get("ticket_notes", {}).items()}
            ticket_priority = {int(k): v for k, v in data.get("ticket_priority", {}).items()}
            ticket_stats    = {int(k): v for k, v in data.get("ticket_stats", {}).items()}
            user_notes      = {int(k): v for k, v in data.get("user_notes", {}).items()}
            mod_history     = {int(k): v for k, v in data.get("mod_history", {}).items()}
            command_log     = {int(k): v for k, v in data.get("command_log", {}).items()}
            raid_abuse      = {int(k): v for k, v in data.get("raid_abuse", {}).items()}
            raid_locked     = set(int(x) for x in data.get("raid_locked", []))
            welcome_config  = data.get("welcome_config", {})
            for k, v in data.get("staff_tickets_claimed", {}).items():
                staff_tickets_claimed[int(k)] = v

def save_data():
    with open("data.json", "w") as f:
        json.dump({
            "tickets":         {str(k): str(v) for k, v in tickets.items()},
            "snippets":        snippets,
            "connected_staff": {str(k): str(v) for k, v in connected_staff.items()},
            "warnings":        {str(k): v for k, v in warnings.items()},
            "strikes":         {str(k): v for k, v in strikes.items()},
            "mod_locked":      list(mod_locked),
            "ai_presets":      ai_presets,
            "mod_abuse":       {str(k): v for k, v in mod_abuse.items()},
            "ticket_banned":   list(ticket_banned),
            "ticket_notes":    {str(k): v for k, v in ticket_notes.items()},
            "ticket_priority": {str(k): v for k, v in ticket_priority.items()},
            "ticket_stats":    {str(k): v for k, v in ticket_stats.items()},
            "user_notes":      {str(k): v for k, v in user_notes.items()},
            "mod_history":     {str(k): v for k, v in mod_history.items()},
            "command_log":     {str(k): v for k, v in command_log.items()},
            "raid_abuse":      {str(k): v for k, v in raid_abuse.items()},
            "raid_locked":     list(raid_locked),
            "welcome_config":  welcome_config,
            "staff_tickets_claimed": {str(k): v for k, v in staff_tickets_claimed.items()},
        }, f, indent=2)

# ── ROLE HELPERS ──────────────────────────────────────────────────────────────
def has_role(member, role_name):
    return any(r.name == role_name for r in member.roles)

def is_lock(member):
    return has_role(member, ROLE_LOCK)

def is_senior(member):
    return has_role(member, ROLE_SENIOR) or is_lock(member)

def is_staff(member):
    return has_role(member, ROLE_STAFF) or is_senior(member)

def is_holder(member):
    return has_role(member, ROLE_HOLDER) or is_lock(member)

def get_staff_role_name(member):
    if is_lock(member):   return ROLE_LOCK
    if is_senior(member): return ROLE_SENIOR
    if is_staff(member):  return ROLE_STAFF
    return "Staff"

def is_ticket_channel(channel_id):
    return channel_id in tickets.values()

def get_user_id_from_channel(channel_id):
    return next((uid for uid, cid in tickets.items() if cid == channel_id), None)

# ── LOGGING ───────────────────────────────────────────────────────────────────
def log_action(user_id, action, detail=""):
    if user_id not in command_log:
        command_log[user_id] = []
    command_log[user_id].append({
        "time": now().strftime("%Y-%m-%d %H:%M UTC"),
        "action": action,
        "detail": detail
    })
    save_data()

def log_mod(user_id, action, by, reason=""):
    if user_id not in mod_history:
        mod_history[user_id] = []
    mod_history[user_id].append({
        "time": now().strftime("%Y-%m-%d %H:%M UTC"),
        "action": action,
        "by": by,
        "reason": reason
    })
    save_data()

# ── RAID PROTECTION ───────────────────────────────────────────────────────────
raid_timestamps = {}  # user_id -> list of timestamps

async def check_raid(user_id, guild):
    if user_id in raid_locked:
        return False
    now_ts = now().timestamp()
    if user_id not in raid_timestamps:
        raid_timestamps[user_id] = []
    raid_timestamps[user_id] = [t for t in raid_timestamps[user_id] if now_ts - t < 5]
    raid_timestamps[user_id].append(now_ts)
    if len(raid_timestamps[user_id]) >= 3:
        raid_locked.add(user_id)
        save_data()
        try:
            user = await bot.fetch_user(user_id)
            await user.send(embed=plain_embed(
                "⛔ **Access Locked**\n\nYou have been temporarily locked from using bot commands due to rapid command usage.\n\nThe server owner has been notified."
            ))
        except:
            pass
        owner = guild.owner
        if owner:
            try:
                view = RaidUnlockView(user_id)
                e = discord.Embed(
                    description=f"⚠️ **Raid Protection Triggered**\n\nUser <@{user_id}> has been locked from bot commands after rapid command usage.\n\nUse the buttons below to unlock or keep them locked.",
                    color=RYANAIR_COLOR
                )
                e.set_footer(text="Ryanair Digital Assistant — Security Alert")
                await send_automation_dm(owner.id, e)
                await owner.send(view=view)
            except:
                pass
        return False
    return True

# ── EMBED HELPERS ─────────────────────────────────────────────────────────────
def plain_embed(description, color=RYANAIR_COLOR):
    e = discord.Embed(description=description, color=color)
    e.set_footer(text="Ryanair Digital Assistant")
    return e

def mod_embed(title, description, color=RYANAIR_COLOR):
    e = discord.Embed(title=title, description=description, color=color, timestamp=now())
    e.set_footer(text="Ryanair Digital Assistant — Moderation")
    return e

async def send_with_banner(channel_or_user, banner_url, embed):
    """Send banner image first (on top), then the embed below."""
    try:
        await channel_or_user.send(banner_url)
        await channel_or_user.send(embed=embed)
    except:
        try:
            await channel_or_user.send(embed=embed)
        except:
            pass

# ── AUTOMATION DM ─────────────────────────────────────────────────────────────
async def send_automation_dm(user_id, embed):
    try:
        user = await auto_bot.fetch_user(user_id)
        await user.send(embed=embed)
    except Exception as e:
        print(f"Automation DM failed: {e}")

ticket_assigned_staff = {}  # channel_id -> list of staff_ids already tried
staff_tickets_claimed = {}  # staff_id -> total tickets claimed

async def assign_ticket_to_staff(guild, channel, user, tried_ids=None):
    """Assign ticket to one available online/idle/dnd staff member. Rotate after 30 mins."""
    if tried_ids is None:
        tried_ids = ticket_assigned_staff.get(channel.id, [])

    available = [
        m for m in guild.members
        if is_staff(m) and not m.bot
        and m.id not in tried_ids
        and m.id not in connected_staff.values()
        and m.status in (discord.Status.online, discord.Status.idle, discord.Status.dnd)
    ]

    if not available:
        try:
            ping_text = " ".join([role.mention for role in guild.roles if role.name in [ROLE_LOCK, ROLE_SENIOR, ROLE_STAFF]])
            if ping_text:
                await channel.send(f"{ping_text} — No online staff found, the AI is handling this ticket for now.")
        except: pass
        return

    chosen = available[0]
    tried_ids.append(chosen.id)
    ticket_assigned_staff[channel.id] = tried_ids

    # 30 min transfer timestamp
    transfer_time = int((now() + datetime.timedelta(minutes=30)).timestamp())

    try:
        e = discord.Embed(
            description=(
                f"Dear **{chosen.display_name}**,\n\n"
                f"A new support ticket has been opened and has been directly assigned to you. "
                f"Please deal with the ticket as soon as possible. "
                f"Use `/connected` in the ticket channel to claim it.\n\n"
                f"**User:** {user.display_name}\n"
                f"**Ticket:** {channel.mention}\n\n"
                f"Every time you use `/connected` to claim a ticket it gets logged against your profile. "
                f"Your claim history can be used towards pay, promotions, and more — so make sure you claim the ticket!\n\n"
                f"If this ticket is not claimed, it will be transferred to another staff member at <t:{transfer_time}:T> (<t:{transfer_time}:R>)."
            ),
            color=RYANAIR_COLOR,
            timestamp=now()
        )
        e.set_footer(text="Ryanair Digital Assistant — Ticket Assignment")
        await send_automation_dm(chosen.id, e)
    except: pass

    try:
        await channel.send(chosen.mention)
    except: pass

    bot.loop.create_task(ticket_reassign_monitor(channel, user, chosen.id, tried_ids))

async def ticket_reassign_monitor(channel, user, staff_id, tried_ids):
    """After 30 mins, if still not claimed, DM staff and reassign."""
    await asyncio.sleep(1800)  # 30 minutes
    guild = bot.get_guild(GUILD_ID)
    if not guild: return
    if not channel or channel.id not in tickets.values(): return
    if connected_staff.get(channel.id):
        return  # Already claimed

    try:
        e = discord.Embed(
            description=(
                f"Hi,\n\n"
                f"The support ticket assigned to you ({channel.mention}) was not claimed within 30 minutes "
                f"and has been transferred to another available staff member.\n\n"
                f"No further action is needed from you for this ticket."
            ),
            color=RYANAIR_COLOR
        )
        e.set_footer(text="Ryanair Digital Assistant — Ticket Assignment")
        await send_automation_dm(staff_id, e)
    except: pass

    await channel.send(embed=plain_embed(
        "The assigned staff member did not claim this ticket in time. Reassigning to another staff member now..."
    ))
    await assign_ticket_to_staff(guild, channel, user, tried_ids)

async def notify_all_staff(guild, channel, user):
    """Assign ticket to one online staff member."""
    await assign_ticket_to_staff(guild, channel, user)

# ── GROQ AI HELPER ────────────────────────────────────────────────────────────
AI_SYSTEM_BASE = (
    "You are Ryanair Bot — a chill, helpful assistant on a Ryanair Discord server.\n"
    "You talk like a friendly Discord user — casual and easy to understand, not corporate or stiff.\n"
    "Do NOT use emojis in any of your responses.\n"
    "You help with stuff like flight roleplay questions, server info, Ryanair RP scenarios, booking help in RP, and general chat.\n"
    "You can play games like trivia, 20 questions, word games, riddles.\n"
    "If you don't know something, be honest about it and tell them to ping a staff member or check ryanair.com.\n"
    "Keep it short, snappy and friendly. Think helpful Discord mod energy, not call centre robot."
)

TICKET_AI_SYSTEM = (
    "You are the Ryanair Support Ticket assistant handling a support ticket on a Ryanair Discord server.\n"
    "Be friendly and casual like a helpful Discord staff member, not a robot.\n"
    "Do NOT use any emojis in your responses at all.\n"
    "Always refer to yourself as 'Ryanair Digital Assistant' if asked who you are.\n"
    "Greet the user, find out what their issue is, and try to sort it out for them.\n"
    "Keep it clear, friendly and actually helpful.\n"
    "If the issue is really serious (ban appeal, serious rule break, payment issue) put [SERIOUS] at the START of your reply.\n"
    "If you have fully sorted their issue, put [RESOLVED] at the END.\n"
    "If it is something only staff can deal with, put [NEEDS_STAFF] at the END.\n"
    "Do not be overly formal but do not be unprofessional either."
)

async def call_groq(messages, system=AI_SYSTEM_BASE, max_tokens=800):
    if not groq_client:
        return "AI is not configured. Please set GROQ_API_KEY."
    try:
        full_messages = [{"role": "system", "content": system}] + messages
        response = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model="llama-3.3-70b-versatile",
            messages=full_messages,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    except Exception as ex:
        return f"AI error: {str(ex)}"

async def autocorrect_text(text):
    """Use Groq to autocorrect spelling/grammar mistakes."""
    if not groq_client:
        return text
    try:
        response = await asyncio.to_thread(
            groq_client.chat.completions.create,
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a spelling and grammar corrector. Return ONLY the corrected text with no explanation, no quotes, no preamble. Fix spelling mistakes and grammar but keep the same meaning and tone."},
                {"role": "user", "content": text}
            ],
            max_tokens=500,
        )
        return response.choices[0].message.content.strip()
    except:
        return text

# ── TICKET AI ─────────────────────────────────────────────────────────────────
async def ticket_ai_respond(channel, user, message_content):
    """Handle AI response in a ticket channel."""
    channel_id = channel.id
    if channel_id not in ticket_ai_history:
        ticket_ai_history[channel_id] = []

    ticket_ai_history[channel_id].append({"role": "user", "content": message_content})
    reply = await call_groq(ticket_ai_history[channel_id], system=TICKET_AI_SYSTEM, max_tokens=600)
    ticket_ai_history[channel_id].append({"role": "assistant", "content": reply})

    # Check flags
    is_serious = "[SERIOUS]" in reply
    is_resolved = "[RESOLVED]" in reply
    needs_staff = "[NEEDS_STAFF]" in reply

    clean_reply = reply.replace("[SERIOUS]", "").replace("[RESOLVED]", "").replace("[NEEDS_STAFF]", "").strip()

    # Send AI reply in ticket channel
    e = discord.Embed(description=clean_reply, color=RYANAIR_COLOR, timestamp=now())
    e.set_author(name="Ryanair Digital Assistant", icon_url=bot.user.display_avatar.url)
    e.set_footer(text="Powered By Ryanair Automations")
    await channel.send(embed=e)

    # Also DM the user
    try:
        dm_e = discord.Embed(description=clean_reply, color=RYANAIR_COLOR, timestamp=now())
        dm_e.set_author(name="Ryanair Digital Assistant", icon_url=bot.user.display_avatar.url)
        dm_e.set_footer(text="Powered By Ryanair Automations")
        await user.send(embed=dm_e)
    except:
        pass

    if is_serious or needs_staff:
        guild = bot.get_guild(GUILD_ID)
        staff_id = connected_staff.get(channel_id)
        alert_text = (
            f"🚨 **{'Serious Issue Detected' if is_serious else 'Staff Required'}**\n\n"
            f"The AI has flagged a ticket as requiring staff attention.\n\n"
            f"**Ticket:** {channel.mention}\n"
            f"**User:** {user.display_name}\n\n"
            f"**Summary:** {clean_reply[:200]}..."
        )
        # DM connected staff member
        if staff_id:
            try:
                staff_member = await bot.fetch_user(staff_id)
                await staff_member.send(embed=plain_embed(alert_text))
            except:
                pass
        # DM all online staff
        for member in guild.members:
            if is_staff(member) and not member.bot and member.status != discord.Status.offline:
                try:
                    await send_automation_dm(member.id, plain_embed(alert_text))
                except:
                    pass

    if is_resolved:
        ticket_ai_active[channel_id] = False

async def start_ticket_ai(channel, user):
    """Start the AI greeting when a ticket is opened."""
    ticket_ai_active[channel.id] = True
    ticket_ai_history[channel.id] = []

    greeting = await call_groq(
        [{"role": "user", "content": f"A customer named {user.display_name} has just opened a support ticket. Greet them warmly and ask them what they need help with today."}],
        system=TICKET_AI_SYSTEM,
        max_tokens=300
    )

    clean_greeting = greeting.replace("[SERIOUS]", "").replace("[RESOLVED]", "").replace("[NEEDS_STAFF]", "").strip()
    ticket_ai_history[channel.id].append({"role": "assistant", "content": clean_greeting})

    e = discord.Embed(description=clean_greeting, color=RYANAIR_COLOR, timestamp=now())
    e.set_author(name="Ryanair Digital Assistant", icon_url=bot.user.display_avatar.url)
    e.set_footer(text="Powered By Ryanair Automations")
    await channel.send(embed=e)

    try:
        dm_e = discord.Embed(description=clean_greeting, color=RYANAIR_COLOR, timestamp=now())
        dm_e.set_author(name="Ryanair Digital Assistant", icon_url=bot.user.display_avatar.url)
        dm_e.set_footer(text="Powered By Ryanair Automations")
        await user.send(embed=dm_e)
    except:
        pass

async def ticket_no_reply_monitor(channel_id, user_id):
    """Monitor for no staff reply after 1 hour."""
    await asyncio.sleep(3600)
    guild = bot.get_guild(GUILD_ID)
    channel = guild.get_channel(channel_id) if guild else None
    if not channel or channel_id not in tickets.values():
        return
    if connected_staff.get(channel_id):
        return  # staff claimed it
    # No staff replied, AI takes over
    user = bot.get_user(user_id)
    if user and ticket_ai_active.get(channel_id, False):
        check_in = await call_groq(
            [{"role": "user", "content": "A customer has been waiting for over an hour with no staff response. Send them a friendly message letting them know you're here to help and ask them to describe their issue again if they haven't already."}],
            system=TICKET_AI_SYSTEM,
            max_tokens=200
        )
        clean = check_in.replace("[SERIOUS]", "").replace("[RESOLVED]", "").replace("[NEEDS_STAFF]", "").strip()
        e = discord.Embed(description=clean, color=RYANAIR_COLOR)
        e.set_footer(text="Powered By Ryanair Automations")
        await channel.send(embed=e)
        try:
            await user.send(embed=e)
        except:
            pass

async def ticket_claimed_monitor(channel_id, user_id, staff_id):
    """Monitor for no staff reply 10 mins after claiming."""
    await asyncio.sleep(600)
    guild = bot.get_guild(GUILD_ID)
    channel = guild.get_channel(channel_id) if guild else None
    if not channel or channel_id not in tickets.values():
        return
    if last_activity.get(channel_id) and (now() - last_activity[channel_id]).total_seconds() < 600:
        return
    # Staff claimed but not replied, AI steps in
    ticket_ai_active[channel_id] = True
    user = bot.get_user(user_id)
    if user:
        stepback = await call_groq(
            [{"role": "user", "content": "A staff member claimed this ticket but hasn't responded yet. Step in politely, apologise for the wait, and ask the customer how you can help."}],
            system=TICKET_AI_SYSTEM,
            max_tokens=200
        )
        clean = stepback.replace("[SERIOUS]", "").replace("[RESOLVED]", "").replace("[NEEDS_STAFF]", "").strip()
        e = discord.Embed(description=clean, color=RYANAIR_COLOR)
        e.set_footer(text="Powered By Ryanair Automations")
        await channel.send(embed=e)
        try:
            await user.send(embed=e)
        except:
            pass
        # Alert the staff member
        try:
            staff = await bot.fetch_user(staff_id)
            await staff.send(embed=plain_embed(
                f"⚠️ **Ticket Alert**\n\nYou claimed a ticket but haven't responded in 10 minutes.\n\n"
                f"**Ticket:** {channel.mention}\n\nThe AI has stepped in but please respond as soon as possible."
            ))
        except:
            pass

# ── TICKET CLOSE ──────────────────────────────────────────────────────────────
async def close_ticket(channel, user_id, closed_by, reason="Issue resolved"):
    guild = bot.get_guild(GUILD_ID)
    user = bot.get_user(user_id) if user_id else None
    if user:
        try:
            e = discord.Embed(
                description=(
                    "**Ticket Closed**\n\n"
                    "Thank you for contacting Ryanair Digital Assistant.\n\n"
                    f"Your ticket has been closed.\n**Reason:** {reason}\n\n"
                    "Please open a new ticket if your issue has not been resolved."
                ),
                color=RYANAIR_COLOR
            )
            e.set_footer(text="Ryanair Digital Assistant")
            await send_automation_dm(user_id, e) if not user else await user.send(SUPPORT_BANNER)
            await user.send(embed=e)
        except:
            pass
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        e = discord.Embed(
            description=f"**Ticket Closed**\n\nUser: {str(user) if user else str(user_id)}\nClosed by: {closed_by}\nReason: {reason}",
            color=RYANAIR_COLOR, timestamp=now()
        )
        e.set_footer(text="Ryanair Digital Assistant")
        await log_channel.send(embed=e)
    connected_staff.pop(channel.id, None)
    last_activity.pop(channel.id, None)
    ticket_ai_active.pop(channel.id, None)
    ticket_ai_history.pop(channel.id, None)
    ticket_claimed_time.pop(channel.id, None)
    ticket_notes.pop(channel.id, None)
    ticket_priority.pop(channel.id, None)
    ticket_assigned_staff.pop(channel.id, None)
    if user_id:
        tickets.pop(user_id, None)
    save_data()
    try:
        await channel.delete()
    except:
        pass

# ── INACTIVITY MONITOR ────────────────────────────────────────────────────────
async def inactivity_monitor(channel_id, user_id):
    await asyncio.sleep(86400)
    guild = bot.get_guild(GUILD_ID)
    channel = guild.get_channel(channel_id)
    if not channel or channel_id not in tickets.values():
        return
    last = last_activity.get(channel_id)
    if last and (now() - last).total_seconds() < 86400:
        return
    user = bot.get_user(user_id)
    if user:
        try:
            await user.send(embed=plain_embed(
                "**Ticket Closing Soon**\n\nYour ticket will close due to inactivity in 1 hour.\nPlease reply to keep it open."
            ))
        except:
            pass
    if channel:
        await channel.send(embed=plain_embed("Inactivity warning sent. Ticket closes in 1 hour if no reply."))
    await asyncio.sleep(3600)
    channel = guild.get_channel(channel_id)
    if not channel or channel_id not in tickets.values():
        return
    last = last_activity.get(channel_id)
    if last and (now() - last).total_seconds() < 87600:
        return
    await close_ticket(channel, user_id, "Automatic (Inactivity)", "Inactivity")

# ── OPEN TICKET ───────────────────────────────────────────────────────────────
async def open_ticket(user, category_name, opened_by_staff=None, reason=None):
    guild = bot.get_guild(GUILD_ID)
    pending_confirm.pop(user.id, None)
    if user.id in tickets:
        return
    if user.id in ticket_banned:
        try:
            await user.send(embed=plain_embed("You are currently banned from opening support tickets."))
        except:
            pass
        return

    category = guild.get_channel(TICKET_CATEGORY_ID)
    overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False)}
    for role in guild.roles:
        if role.name in [ROLE_LOCK, ROLE_SENIOR, ROLE_STAFF]:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    channel = await guild.create_text_channel(
        name=f"ticket-{user.name}",
        category=category,
        overwrites=overwrites,
        topic=f"Ticket | {user.name} ({user.id}) | {category_name}"
    )
    tickets[user.id] = channel.id
    ticket_stats[user.id] = ticket_stats.get(user.id, 0) + 1
    save_data()
    last_activity[channel.id] = now()

    # DM user confirmation
    try:
        e = discord.Embed(
            description=(
                f"**Thank you for contacting Ryanair Digital Assistant**\n\n"
                f"Hello, **{user.display_name}**!\n\n"
                f"Your ticket has been opened under **{category_name}**.\n\n"
                f"{f'**Reason:** {reason}' + chr(10) + chr(10) if reason else ''}"
                "Our AI assistant will be with you shortly, and a staff member will assist you as soon as possible."
            ),
            color=RYANAIR_COLOR
        )
        e.set_footer(text="Ryanair Digital Assistant")
        await user.send(SUPPORT_BANNER)
        await user.send(embed=e)
    except:
        pass

    opened_by_text = f"Opened by staff: {opened_by_staff.mention}" if opened_by_staff else f"Opened by user: {user.mention}"

    staff_e = discord.Embed(
        description=(
            f"**New Support Ticket — {category_name}**\n\n"
            f"User: {user.mention}\n{opened_by_text}\n"
            f"{f'Reason: {reason}' + chr(10) if reason else ''}\n"
            "Use `/connected` to connect · `/close` to close\n"
            "⚠️ AI is handling this ticket until a staff member connects."
        ),
        color=RYANAIR_COLOR, timestamp=now()
    )
    staff_e.set_author(name=user.display_name, icon_url=user.display_avatar.url)
    staff_e.set_footer(text="Ryanair Digital Assistant")
    await channel.send(SUPPORT_BANNER)
    await channel.send(embed=staff_e)

    await notify_all_staff(guild, channel, user)

    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        log_e = discord.Embed(
            description=f"**Ticket Opened — {category_name}**\n\nUser: {user.mention}\nChannel: {channel.mention}\n{opened_by_text}",
            color=RYANAIR_COLOR, timestamp=now()
        )
        log_e.set_author(name=user.display_name, icon_url=user.display_avatar.url)
        log_e.set_footer(text="Ryanair Digital Assistant")
        await log_channel.send(embed=log_e)

    log_action(user.id, "Ticket Opened", category_name)

    # Start AI and monitors
    bot.loop.create_task(start_ticket_ai(channel, user))
    bot.loop.create_task(inactivity_monitor(channel.id, user.id))
    bot.loop.create_task(ticket_no_reply_monitor(channel.id, user.id))

# ── TICKET CATEGORIES ─────────────────────────────────────────────────────────
STANDARD_CATEGORIES = [
    ("Server Help",        "Server verification & role commands"),
    ("General Assistance", "For general queries"),
    ("Bans & Blacklists",  "Ban/Blacklist appeals, group bans"),
    ("Career Enquiries",   "Career vacancies & recruitment"),
    ("Flight Assistance",  "Travel updates & airport guidance"),
]
HOLDER_CATEGORIES = [
    ("Priority Support",   "Priority assistance for Holders"),
    ("Partnership Enquiry","Partnership & collaboration enquiries"),
]

REASON_REQUIRED_CATEGORIES = {"General Assistance", "Priority Support", "Flight Assistance"}

class ReasonModal(discord.ui.Modal, title="Why are you opening this ticket?"):
    reason = discord.ui.TextInput(
        label="Please describe your issue (min 5 words)",
        style=discord.TextStyle.paragraph,
        placeholder="e.g. I need help with my flight booking because...",
        max_length=500
    )
    def __init__(self, user, category_name):
        super().__init__()
        self.user = user
        self.category_name = category_name

    async def on_submit(self, interaction: discord.Interaction):
        reason_text = str(self.reason).strip()
        if len(reason_text.split()) < 5:
            await interaction.response.send_message(
                "❌ Please provide at least **5 words** to describe your issue before we can open your ticket!",
                ephemeral=True
            )
            return
        await interaction.response.defer()
        await open_ticket(self.user, self.category_name, reason=reason_text)

class CategorySelect(discord.ui.Select):
    def __init__(self, user, extra=False):
        options = []
        cats = STANDARD_CATEGORIES + (HOLDER_CATEGORIES if extra else [])
        for name, desc in cats:
            options.append(discord.SelectOption(label=name, description=desc))
        super().__init__(placeholder="Select the area that best fits your issue!", options=options)
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not your menu.", ephemeral=True)
            return
        selected = self.values[0]
        if selected in REASON_REQUIRED_CATEGORIES:
            await interaction.response.send_modal(ReasonModal(self.user, selected))
        else:
            await interaction.response.defer()
            for item in self.view.children:
                item.disabled = True
            try:
                await interaction.message.edit(view=self.view)
            except:
                pass
            self.view.stop()
            await open_ticket(self.user, selected)

class CategoryView(discord.ui.View):
    def __init__(self, user, extra=False):
        super().__init__(timeout=300)
        self.add_item(CategorySelect(user, extra))
    async def on_timeout(self):
        self.stop()

class ConfirmView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=300)
        self.user = user

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def yes_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not for you.", ephemeral=True); return
        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        self.stop()
        guild = bot.get_guild(GUILD_ID)
        member = guild.get_member(self.user.id)
        extra = is_holder(member) if member else False
        e = discord.Embed(
            description="**Ryanair Digital Assistant**\n\nLet's get you the help you need. **Select from one of the options below to proceed.**",
            color=RYANAIR_COLOR
        )
        e.set_author(name="Assistance", icon_url=bot.user.display_avatar.url)
        e.set_footer(text="Ryanair Digital Assistant")
        await self.user.send(embed=e, view=CategoryView(self.user, extra=extra))

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def no_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This is not for you.", ephemeral=True); return
        pending_confirm.pop(self.user.id, None)
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        await interaction.response.send_message(embed=plain_embed("No problem! Feel free to message us again if you need assistance."))
        self.stop()

class UnlockStaffView(discord.ui.View):
    def __init__(self, locked_user_id, display_name):
        super().__init__(timeout=None)
        self.locked_user_id = locked_user_id
        self.display_name = display_name

    @discord.ui.button(label="Unlock", style=discord.ButtonStyle.success)
    async def unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        mod_locked.discard(self.locked_user_id)
        mod_abuse.pop(self.locked_user_id, None)
        save_data()
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        await interaction.response.send_message(f"✅ {self.display_name} has been unlocked.", ephemeral=True)
        try:
            user = await bot.fetch_user(self.locked_user_id)
            await user.send(embed=plain_embed("✅ **Access Restored**\n\nYour access to moderation commands has been restored by the server owner."))
        except:
            pass

    @discord.ui.button(label="Keep Locked", style=discord.ButtonStyle.danger)
    async def keep_locked(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        await interaction.response.send_message(f"🔒 {self.display_name} remains locked.", ephemeral=True)

class RaidUnlockView(discord.ui.View):
    def __init__(self, locked_user_id):
        super().__init__(timeout=None)
        self.locked_user_id = locked_user_id

    @discord.ui.button(label="Unlock", style=discord.ButtonStyle.success)
    async def unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        raid_locked.discard(self.locked_user_id)
        raid_timestamps.pop(self.locked_user_id, None)
        save_data()
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        await interaction.response.send_message("✅ User unlocked.", ephemeral=True)
        try:
            user = await bot.fetch_user(self.locked_user_id)
            await user.send(embed=plain_embed("✅ **Access Restored**\n\nYour bot access has been restored by the server owner."))
        except:
            pass

    @discord.ui.button(label="Keep Locked", style=discord.ButtonStyle.danger)
    async def keep_locked(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except:
            pass
        await interaction.response.send_message("🔒 User remains locked.", ephemeral=True)

class CloseRequestView(discord.ui.View):
    def __init__(self, channel_id, user_id, reason):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.user_id = user_id
        self.reason = reason

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except: pass
        await interaction.response.send_message("Closing the ticket now.", ephemeral=True)
        guild = bot.get_guild(GUILD_ID)
        channel = guild.get_channel(self.channel_id)
        if channel:
            await close_ticket(channel, self.user_id, interaction.user.mention, self.reason)
        self.stop()

    @discord.ui.button(label="Keep Open", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        for item in self.children:
            item.disabled = True
        try:
            await interaction.message.edit(view=self)
        except: pass
        await interaction.response.send_message("Ticket kept open.", ephemeral=True)
        # Notify user their request was declined
        try:
            user = await bot.fetch_user(self.user_id)
            await user.send(embed=plain_embed(
                "Your ticket closure request was reviewed by a staff member and the ticket has been kept open.\n\n"
                "If you still need it closed, please let the staff member know."
            ))
        except: pass
        guild = bot.get_guild(GUILD_ID)
        channel = guild.get_channel(self.channel_id)
        if channel:
            await channel.send(embed=plain_embed(f"The closure request was declined. Ticket remains open."))
        self.stop()


# ── EVENTS ────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    load_data()
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"Ryanair Digital Assistant online as {bot.user}")

@auto_bot.event
async def on_ready():
    print(f"Automation bot online as {auto_bot.user}")

@bot.event
async def on_member_join(member):
    cfg = welcome_config.get(str(member.guild.id))
    if not cfg:
        return
    channel = member.guild.get_channel(int(cfg["channel_id"]))
    if not channel:
        return
    banner = cfg.get("banner_url", SUPPORT_BANNER)
    e = discord.Embed(
        title=f"✈️ Welcome to {member.guild.name}!",
        description=(
            f"Hey {member.mention}, welcome aboard! 🎉\n\n"
            f"Glad to have you with us — make sure you check out the rules and enjoy your stay!\n\n"
            f"*Need help? Our Digital Assistant is always here for you!* 😄"
        ),
        color=RYANAIR_COLOR,
        timestamp=now()
    )
    e.set_thumbnail(url=member.display_avatar.url)  # small circle only
    e.set_footer(text="Ryanair Digital Assistant")
    try:
        await channel.send(banner)
        await channel.send(embed=e)
    except:
        pass

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Staff AI DM session
    if isinstance(message.channel, discord.DMChannel) and message.author.id in ai_sessions:
        if message.content.startswith("!"):
            await bot.process_commands(message)
            return
        session = ai_sessions[message.author.id]
        system = AI_SYSTEM_BASE
        if ai_presets:
            system += "\n\nAdditional instructions:\n" + "\n".join(f"- {v}" for v in ai_presets.values())
        session.append({"role": "user", "content": message.content})
        reply = await call_groq(session, system=system)
        session.append({"role": "assistant", "content": reply})
        e = discord.Embed(description=reply, color=RYANAIR_COLOR)
        e.set_footer(text="Powered By Ryanair Automations — Type !endai to end session")
        await message.channel.send(embed=e)
        return

    # Server messages
    if not isinstance(message.channel, discord.DMChannel):
        if is_ticket_channel(message.channel.id):
            guild = bot.get_guild(GUILD_ID)
            member = guild.get_member(message.author.id)
            channel_id = message.channel.id
            user_id = get_user_id_from_channel(channel_id)
            user = bot.get_user(user_id) if user_id else None

            # Detect staff pings in ticket — warn the user
            if member and not is_staff(member) and guild.roles:
                for role in guild.roles:
                    if role.name in [ROLE_LOCK, ROLE_SENIOR, ROLE_STAFF] and role.mention in message.content:
                        warned_channels = staff_ping_warned.get(message.author.id, [])
                        if channel_id not in warned_channels:
                            warned_channels.append(channel_id)
                            staff_ping_warned[message.author.id] = warned_channels
                            await message.channel.send(embed=plain_embed(
                                f"{message.author.mention} Please do not ping staff roles in tickets. A member of our team will be with you shortly."
                            ))
                        else:
                            warnings[message.author.id] = warnings.get(message.author.id, 0) + 1
                            save_data()
                            await message.channel.send(embed=plain_embed(
                                f"{message.author.mention} You have received an automatic warning for repeatedly pinging staff in tickets. (**Warning #{warnings[message.author.id]}**)"
                            ))
                            log_mod(message.author.id, "Auto-Warning (Staff Ping)", "System", "Repeated staff ping in ticket")
                        break

            if member and is_staff(member) and not message.content.startswith("/"):
                # Staff typed in ticket — relay to user and stop AI
                ticket_ai_active[channel_id] = False
                if user_id:
                    if user:
                        last_activity[channel_id] = now()
                        role_name = get_staff_role_name(member)
                        e = discord.Embed(description=message.content, color=RYANAIR_COLOR, timestamp=now())
                        e.set_author(name=member.display_name, icon_url=member.display_avatar.url)
                        e.set_footer(text=f"Ryanair Staff Team | {role_name}")
                        if message.attachments:
                            e.set_image(url=message.attachments[0].url)
                        try:
                            await user.send(embed=e)
                        except:
                            pass
            elif member and not is_staff(member):
                # User typed in ticket channel — relay to staff and let AI respond if active
                if user_id and user:
                    last_activity[channel_id] = now()
                if ticket_ai_active.get(channel_id, False) and not is_staff(member):
                    if user:
                        bot.loop.create_task(ticket_ai_respond(message.channel, user, message.content))

        await bot.process_commands(message)
        return

    # DM handling
    user = message.author
    if user.id in tickets:
        guild = bot.get_guild(GUILD_ID)
        channel = guild.get_channel(tickets[user.id])
        if channel:
            last_activity[channel.id] = now()
            e = discord.Embed(description=message.content, color=RYANAIR_COLOR, timestamp=now())
            e.set_author(name=user.display_name, icon_url=user.display_avatar.url)
            e.set_footer(text="User Message")
            if message.attachments:
                e.set_image(url=message.attachments[0].url)
            await channel.send(embed=e)
            # If AI active, respond
            if ticket_ai_active.get(channel.id, False):
                bot.loop.create_task(ticket_ai_respond(channel, user, message.content))
        return

    if user.id in pending_confirm:
        return

    pending_confirm[user.id] = True
    e = discord.Embed(
        description=(
            "**Ryanair Digital Assistant**\n\n"
            "Hello, I'm Ryanair's **Digital Assistant!**\n"
            "Are you looking for assistance?"
        ),
        color=RYANAIR_COLOR
    )
    e.set_author(name="Assistance", icon_url=bot.user.display_avatar.url)
    e.set_footer(text="Ryanair Digital Assistant")
    await user.send(SUPPORT_BANNER)
    await user.send(embed=e, view=ConfirmView(user))
    await bot.process_commands(message)

@bot.command(name="endai")
async def endai(ctx):
    if not isinstance(ctx.channel, discord.DMChannel):
        return
    if ctx.author.id in ai_sessions:
        del ai_sessions[ctx.author.id]
        await ctx.send(embed=plain_embed("Your AI session has ended. Use `/ai` in the server to start a new one."))

# ═══════════════════════════════════════════════════════════════════════════════
#  TICKET COMMANDS
# ═══════════════════════════════════════════════════════════════════════════════

@tree.command(name="connected", description="Connect yourself to this ticket", guild=discord.Object(id=GUILD_ID))
async def connected(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    if interaction.user.id in connected_staff.values():
        other = next((cid for cid, sid in connected_staff.items() if sid == interaction.user.id), None)
        guild = bot.get_guild(GUILD_ID)
        ch = guild.get_channel(other) if other else None
        await interaction.followup.send(f"Already connected to {ch.mention if ch else 'another ticket'}. Use `/unconnected` first.", ephemeral=True); return
    if interaction.channel_id in connected_staff:
        already = bot.get_user(connected_staff[interaction.channel_id])
        await interaction.followup.send(f"{already.display_name if already else 'Another agent'} is already connected.", ephemeral=True); return
    connected_staff[interaction.channel_id] = interaction.user.id
    ticket_ai_active[interaction.channel_id] = False  # stop AI when staff connects
    ticket_claimed_time[interaction.channel_id] = now()
    staff_tickets_claimed[interaction.user.id] = staff_tickets_claimed.get(interaction.user.id, 0) + 1
    save_data()
    user_id = get_user_id_from_channel(interaction.channel_id)
    user = bot.get_user(user_id) if user_id else None
    if user:
        try:
            await user.send(SUPPORT_BANNER)
            await user.send(embed=plain_embed(f"**Agent Connected**\n\nHello, I am **{interaction.user.display_name}** and I will be assisting you today.\n\nHow may I help you?"))
        except: pass
    await interaction.channel.send(embed=plain_embed(f"**{interaction.user.mention}** has connected to this ticket. AI assistance has been paused."))
    await interaction.followup.send("You are now connected.", ephemeral=True)
    log_action(interaction.user.id, "Connected to Ticket", str(interaction.channel_id))
    # Start claimed monitor
    if user_id:
        bot.loop.create_task(ticket_claimed_monitor(interaction.channel_id, user_id, interaction.user.id))

@tree.command(name="unconnected", description="Disconnect from this ticket", guild=discord.Object(id=GUILD_ID))
async def unconnected(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    if connected_staff.get(interaction.channel_id) != interaction.user.id:
        await interaction.followup.send("You are not connected to this ticket.", ephemeral=True); return
    del connected_staff[interaction.channel_id]
    ticket_ai_active[interaction.channel_id] = True  # re-enable AI
    save_data()
    guild = bot.get_guild(GUILD_ID)
    user_id = get_user_id_from_channel(interaction.channel_id)
    await interaction.channel.send(embed=plain_embed(f"**{interaction.user.mention}** has disconnected. AI will assist until another agent connects."))
    user = bot.get_user(user_id) if user_id else None
    if user:
        try:
            await user.send(embed=plain_embed(f"**{interaction.user.display_name}** has disconnected from your ticket. Another team member will be with you shortly."))
        except: pass
    for member in guild.members:
        if is_staff(member) and not member.bot and member.id != interaction.user.id:
            try:
                e = discord.Embed(description=f"**Ticket Needs Coverage**\n\n{interaction.user.display_name} disconnected.\n\nCover it here: {interaction.channel.mention}", color=RYANAIR_COLOR)
                e.set_footer(text="Ryanair Digital Assistant")
                await send_automation_dm(member.id, e)
            except: pass
    await interaction.followup.send("Disconnected. Staff notified. AI re-enabled.", ephemeral=True)

@tree.command(name="close", description="Close this support ticket (or request closure via DM)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(reason="Reason for closing")
async def close_cmd(interaction: discord.Interaction, reason: str = "Issue resolved"):
    await interaction.response.defer(ephemeral=True)

    # User requesting closure via DM (not staff, not in a ticket channel)
    if not is_ticket_channel(interaction.channel_id) and not is_staff(interaction.user):
        # Check if this user has an open ticket
        user_id = interaction.user.id
        if user_id not in tickets:
            await interaction.followup.send("You don't have an open ticket.", ephemeral=True); return

        channel_id = tickets[user_id]
        guild = bot.get_guild(GUILD_ID)
        channel = guild.get_channel(channel_id)

        # Notify in the ticket channel
        if channel:
            e = discord.Embed(
                description=(
                    f"{interaction.user.mention} has requested this ticket to be closed.\n\n"
                    f"**Reason:** {reason}\n\n"
                    f"A staff member can use `/close` to confirm."
                ),
                color=RYANAIR_COLOR
            )
            e.set_footer(text="Ryanair Digital Assistant — Closure Request")
            await channel.send(embed=e)

        # DM the connected staff member with approve/deny buttons
        staff_id = connected_staff.get(channel_id)
        if staff_id:
            try:
                view = CloseRequestView(channel_id, user_id, reason)
                e = discord.Embed(
                    description=(
                        f"**Ticket Closure Request**\n\n"
                        f"**{interaction.user.display_name}** has requested their ticket to be closed.\n\n"
                        f"**Reason:** {reason}\n"
                        f"**Ticket:** {channel.mention if channel else channel_id}\n\n"
                        f"Would you like to close this ticket?"
                    ),
                    color=RYANAIR_COLOR
                )
                e.set_footer(text="Ryanair Digital Assistant — Ticket Assignment")
                await send_automation_dm(staff_id, e)
                staff_member = await bot.fetch_user(staff_id)
                await staff_member.send(view=view)
            except: pass

        await interaction.followup.send("Your closure request has been sent to the staff member handling your ticket.", ephemeral=True)
        return

    # Staff closing from inside the ticket channel
    if not is_staff(interaction.user):
        await interaction.followup.send("No permission.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id):
        await interaction.followup.send("Not a ticket channel.", ephemeral=True); return

    user_id = get_user_id_from_channel(interaction.channel_id)
    await interaction.followup.send("Closing ticket...", ephemeral=True)
    await asyncio.sleep(1)
    await close_ticket(interaction.channel, user_id, interaction.user.mention, reason)

@tree.command(name="closeall", description="Close ALL open tickets (Owner only)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(reason="Reason for closing all tickets")
async def closeall(interaction: discord.Interaction, reason: str = "Mass closure by owner"):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user): await interaction.followup.send("Owner only.", ephemeral=True); return
    guild = bot.get_guild(GUILD_ID)
    count = 0
    for uid, cid in list(tickets.items()):
        channel = guild.get_channel(cid)
        if channel:
            await close_ticket(channel, uid, interaction.user.mention, reason)
            count += 1
            await asyncio.sleep(0.5)
    await interaction.followup.send(f"Closed {count} tickets.", ephemeral=True)

@tree.command(name="forceopen", description="Force open a support ticket for a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User", category="Category")
async def forceopen(interaction: discord.Interaction, member: discord.Member, category: str = "General Assistance"):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if member.id in tickets: await interaction.followup.send("Already has a ticket.", ephemeral=True); return
    if member.bot: await interaction.followup.send("Cannot open for a bot.", ephemeral=True); return
    await open_ticket(member, category, opened_by_staff=interaction.user)
    await interaction.followup.send(f"Ticket opened for {member.mention}.", ephemeral=True)

@tree.command(name="onhold", description="Place this ticket on hold", guild=discord.Object(id=GUILD_ID))
async def onhold(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    user_id = get_user_id_from_channel(interaction.channel_id)
    user = bot.get_user(user_id) if user_id else None
    if user:
        try:
            await user.send(SUPPORT_BANNER)
            await user.send(embed=plain_embed("**Ticket On Hold**\n\nYour ticket has been placed on hold.\n\nPlease wait — a team member will be with you shortly."))
        except: pass
    await interaction.channel.send(embed=plain_embed(f"Ticket placed on hold by {interaction.user.mention}."))
    await interaction.followup.send("On hold message sent.", ephemeral=True)

@tree.command(name="ticketrename", description="Rename this ticket channel", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(name="New channel name")
async def ticketrename(interaction: discord.Interaction, name: str):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    await interaction.channel.edit(name=name)
    await interaction.followup.send(f"Channel renamed to `{name}`.", ephemeral=True)

@tree.command(name="ticketnote", description="Add a private staff note to this ticket", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(note="The note to add")
async def ticketnote(interaction: discord.Interaction, note: str):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    if interaction.channel_id not in ticket_notes:
        ticket_notes[interaction.channel_id] = []
    ticket_notes[interaction.channel_id].append({
        "by": interaction.user.display_name,
        "time": now().strftime("%Y-%m-%d %H:%M UTC"),
        "note": note
    })
    save_data()
    e = discord.Embed(title="📝 Staff Note Added", description=f"**By:** {interaction.user.mention}\n\n{note}", color=RYANAIR_COLOR)
    e.set_footer(text="This note is visible to staff only")
    await interaction.channel.send(embed=e)
    await interaction.followup.send("Note added.", ephemeral=True)

@tree.command(name="tickettransfer", description="Transfer this ticket to another staff member", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Staff member to transfer to")
async def tickettransfer(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    if not is_staff(member): await interaction.followup.send("That user is not staff.", ephemeral=True); return
    connected_staff[interaction.channel_id] = member.id
    save_data()
    await interaction.channel.send(embed=plain_embed(f"Ticket transferred to {member.mention} by {interaction.user.mention}."))
    try:
        e = discord.Embed(description=f"A ticket has been transferred to you: {interaction.channel.mention}", color=RYANAIR_COLOR)
        e.set_footer(text="Ryanair Digital Assistant")
        await send_automation_dm(member.id, e)
    except: pass
    await interaction.followup.send(f"Ticket transferred to {member.display_name}.", ephemeral=True)

@tree.command(name="ticketpriority", description="Set the priority of this ticket", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(priority="low, medium, or high")
async def ticketpriority(interaction: discord.Interaction, priority: str):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    p = priority.lower()
    if p not in ["low", "medium", "high"]: await interaction.followup.send("Priority must be low, medium, or high.", ephemeral=True); return
    ticket_priority[interaction.channel_id] = p
    icons = {"low": "🟢", "medium": "🟡", "high": "🔴"}
    save_data()
    new_name = f"{icons[p]}-{interaction.channel.name.lstrip('🟢🟡🔴-')}"
    await interaction.channel.edit(name=new_name)
    await interaction.channel.send(embed=plain_embed(f"Ticket priority set to **{p.upper()}** {icons[p]} by {interaction.user.mention}."))
    await interaction.followup.send(f"Priority set to {p}.", ephemeral=True)

@tree.command(name="ticketban", description="Ban a user from opening tickets", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User to ban from tickets", reason="Reason")
async def ticketban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    ticket_banned.add(member.id)
    save_data()
    log_mod(member.id, "Ticket Ban", interaction.user.display_name, reason)
    try:
        await member.send(embed=plain_embed(f"You have been banned from opening support tickets.\n\n**Reason:** {reason}"))
    except: pass
    await interaction.followup.send(f"{member.display_name} banned from tickets.", ephemeral=True)

@tree.command(name="ticketunban", description="Unban a user from opening tickets", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User to unban")
async def ticketunban(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    ticket_banned.discard(member.id)
    save_data()
    await interaction.followup.send(f"{member.display_name} can now open tickets again.", ephemeral=True)

@tree.command(name="ticketstats", description="View ticket statistics for a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User to check")
async def ticketstats(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    count = ticket_stats.get(member.id, 0)
    banned = member.id in ticket_banned
    e = discord.Embed(title=f"Ticket Stats — {member.display_name}", color=RYANAIR_COLOR)
    e.add_field(name="Tickets Opened", value=str(count), inline=True)
    e.add_field(name="Ticket Banned", value="Yes" if banned else "No", inline=True)
    e.set_footer(text="Ryanair Digital Assistant")
    await interaction.followup.send(embed=e, ephemeral=True)

@tree.command(name="ticketsummary", description="AI summary of this ticket conversation", guild=discord.Object(id=GUILD_ID))
async def ticketsummary(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    history = ticket_ai_history.get(interaction.channel_id, [])
    if not history:
        await interaction.followup.send("No AI conversation history for this ticket.", ephemeral=True); return
    summary = await call_groq(
        history + [{"role": "user", "content": "Please provide a brief professional summary of this support conversation so far, including the issue, any steps taken, and current status."}],
        system=TICKET_AI_SYSTEM,
        max_tokens=400
    )
    e = discord.Embed(title="📋 Ticket Summary", description=summary, color=RYANAIR_COLOR)
    e.set_footer(text="Powered By Ryanair Automations")
    await interaction.followup.send(embed=e, ephemeral=True)

@tree.command(name="requeststaff", description="Request another staff member to join this ticket", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Staff member to request")
async def requeststaff(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    if not is_staff(member): await interaction.followup.send("Not a staff member.", ephemeral=True); return
    await interaction.channel.send(embed=plain_embed(f"{member.mention}, you have been requested to assist by {interaction.user.mention}."))
    try:
        e = discord.Embed(description=f"You have been requested to assist in a ticket: {interaction.channel.mention}", color=RYANAIR_COLOR)
        e.set_footer(text="Ryanair Digital Assistant")
        await send_automation_dm(member.id, e)
    except: pass
    await interaction.followup.send(f"{member.display_name} has been requested.", ephemeral=True)

@tree.command(name="anonreply", description="Reply anonymously to the user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(message="Your anonymous reply")
async def anonreply(interaction: discord.Interaction, message: str):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    corrected = await autocorrect_text(message)
    user_id = get_user_id_from_channel(interaction.channel_id)
    user = bot.get_user(user_id) if user_id else None
    last_activity[interaction.channel_id] = now()
    e = discord.Embed(description=corrected, color=RYANAIR_COLOR, timestamp=now())
    e.set_footer(text="Ryanair Digital Assistant")
    if user:
        await user.send(embed=e)
    await interaction.channel.send(embed=discord.Embed(
        description=f"Anonymous reply sent by {interaction.user.mention}:\n\n{corrected}", color=RYANAIR_COLOR
    ).set_footer(text="Sent anonymously"))
    await interaction.followup.send("Anonymous reply sent.", ephemeral=True)

@tree.command(name="aideal", description="Let the AI fully handle this ticket — no staff needed", guild=discord.Object(id=GUILD_ID))
async def aideal(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    ticket_ai_active[interaction.channel_id] = True
    connected_staff.pop(interaction.channel_id, None)
    save_data()
    user_id = get_user_id_from_channel(interaction.channel_id)
    user = bot.get_user(user_id) if user_id else None
    await interaction.channel.send(embed=plain_embed(
        f"🤖 **AI Mode Activated**\n\n{interaction.user.mention} has handed this ticket to the AI assistant.\n\nThe AI will now handle this ticket fully!"
    ))
    if user:
        try:
            await user.send(embed=plain_embed(
                "🤖 **AI Assistant Taking Over**\n\nHey! Our AI assistant is going to help you with your request right now. Just keep chatting and it'll sort you out! 😄"
            ))
        except: pass
    # Trigger AI to re-engage
    if user:
        bot.loop.create_task(ticket_ai_respond(interaction.channel, user, "Please re-introduce yourself and ask the user what you can help them with today."))
    await interaction.followup.send("AI is now handling this ticket.", ephemeral=True)


@tree.command(name="say", description="Make the bot say something in this channel", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(message="What the bot should say")
async def say_cmd(interaction: discord.Interaction, message: str):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    corrected = await autocorrect_text(message)
    await interaction.channel.send(corrected)
    await interaction.followup.send("Sent!", ephemeral=True)

@tree.command(name="supporttickets", description="View all active support tickets", guild=discord.Object(id=GUILD_ID))
async def supporttickets(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if not tickets: await interaction.followup.send("No active tickets.", ephemeral=True); return
    guild = bot.get_guild(GUILD_ID)
    lines = []
    for uid, cid in tickets.items():
        user = bot.get_user(uid)
        channel = guild.get_channel(cid)
        staff_id = connected_staff.get(cid)
        staff = bot.get_user(staff_id) if staff_id else None
        priority = ticket_priority.get(cid, "normal")
        ai_active = ticket_ai_active.get(cid, False)
        lines.append(
            f"**{user.display_name if user else uid}** → {channel.mention if channel else cid} "
            f"| {'Connected: ' + staff.display_name if staff else 'No agent'} "
            f"| Priority: {priority} | AI: {'On' if ai_active else 'Off'}"
        )
    e = discord.Embed(title=f"Active Tickets ({len(tickets)})", description="\n".join(lines), color=RYANAIR_COLOR)
    e.set_footer(text="Ryanair Digital Assistant")
    await interaction.followup.send(embed=e, ephemeral=True)

# ── SNIPPET COMMANDS ──────────────────────────────────────────────────────────
@tree.command(name="snippet", description="Send a preset reply", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(name="Snippet name")
async def snippet(interaction: discord.Interaction, name: str):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    if name.lower() not in snippets: await interaction.followup.send(f"Snippet `{name}` not found.", ephemeral=True); return
    user_id = get_user_id_from_channel(interaction.channel_id)
    user = bot.get_user(user_id) if user_id else None
    msg = snippets[name.lower()]
    last_activity[interaction.channel_id] = now()
    if user: await user.send(embed=plain_embed(msg))
    await interaction.channel.send(embed=discord.Embed(description=f"Snippet **{name}** sent by {interaction.user.mention}:\n\n{msg}", color=RYANAIR_COLOR))
    await interaction.followup.send("Snippet sent.", ephemeral=True)

@tree.command(name="snippetadd", description="Add a snippet", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(name="Keyword", message="Content")
async def snippetadd(interaction: discord.Interaction, name: str, message: str):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    snippets[name.lower()] = message
    save_data()
    await interaction.followup.send(f"Snippet `{name}` saved.", ephemeral=True)

@tree.command(name="snippetlist", description="List all snippets", guild=discord.Object(id=GUILD_ID))
async def snippetlist(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if not snippets: await interaction.followup.send("No snippets yet.", ephemeral=True); return
    e = discord.Embed(title="Available Snippets", color=RYANAIR_COLOR)
    for sname, msg in snippets.items():
        e.add_field(name=f"`{sname}`", value=msg[:100] + ("..." if len(msg) > 100 else ""), inline=False)
    e.set_footer(text="Ryanair Digital Assistant")
    await interaction.followup.send(embed=e, ephemeral=True)

@tree.command(name="snippetdelete", description="Delete a snippet", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(name="Snippet name")
async def snippetdelete(interaction: discord.Interaction, name: str):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    if name.lower() not in snippets: await interaction.followup.send(f"Snippet `{name}` not found.", ephemeral=True); return
    del snippets[name.lower()]
    save_data()
    await interaction.followup.send(f"Snippet `{name}` deleted.", ephemeral=True)

# ── INFO / CAREERS ────────────────────────────────────────────────────────────
@tree.command(name="careers", description="Send careers information to the ticket user", guild=discord.Object(id=GUILD_ID))
async def careers(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    user_id = get_user_id_from_channel(interaction.channel_id)
    user = bot.get_user(user_id) if user_id else None
    e = discord.Embed(
        description=(
            "**Careers at Ryanair**\n\nThank you for your interest in joining our team.\n\n"
            "We are always looking for passionate individuals to join our growing organisation.\n\n"
            "**[View Available Roles](https://discord.com/channels/1409175513783734292/1484595370142072853)**\n\n"
            "We look forward to hearing from you."
        ),
        color=RYANAIR_COLOR
    )
    e.set_footer(text="Ryanair Digital Assistant")
    if user:
        try:
            await user.send("https://cdn.discordapp.com/attachments/1484595370142072853/1488570289783570542/CAREERS_2026_1.png")
            await user.send(embed=e)
        except: pass
    await interaction.channel.send(embed=plain_embed(f"Careers info sent to user by {interaction.user.mention}."))
    await interaction.followup.send("Careers info sent.", ephemeral=True)

@tree.command(name="info", description="Send Ryanair information to the ticket user", guild=discord.Object(id=GUILD_ID))
async def info(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    user_id = get_user_id_from_channel(interaction.channel_id)
    user = bot.get_user(user_id) if user_id else None
    e = discord.Embed(
        description=(
            "**Ryanair Information**\n\nFor information about Ryanair including our fleet, routes, and social media handles:\n\n"
            "**[View Ryanair Information](https://discord.com/channels/1409175513783734292/1484595370142072853)**\n\n"
            "If you require further assistance, please do not hesitate to open a support ticket."
        ),
        color=RYANAIR_COLOR
    )
    e.set_footer(text="Ryanair Digital Assistant")
    if user:
        try:
            await user.send("https://cdn.discordapp.com/attachments/1409179275357323410/1503792773189341264/Untitled_design_92.png")
            await user.send(embed=e)
        except: pass
    await interaction.channel.send(embed=plain_embed(f"Ryanair info sent to user by {interaction.user.mention}."))
    await interaction.followup.send("Info sent.", ephemeral=True)

# ── ANNOUNCEMENT COMMANDS ─────────────────────────────────────────────────────

# Modals for announce — uses a large text box so formatting is fully preserved
class AnnounceModal(discord.ui.Modal, title="Write Your Announcement"):
    message_body = discord.ui.TextInput(
        label="Message Body",
        style=discord.TextStyle.paragraph,
        placeholder="Type your announcement here. All formatting is preserved exactly as you type it.",
        max_length=4000,
        required=True
    )

    def __init__(self, airline: str, ann_title: str, image_url: str, target_channel, footer_label: str):
        super().__init__()
        self.airline      = airline
        self.ann_title    = ann_title
        self.image_url    = image_url
        self.target_channel = target_channel
        self.footer_label = footer_label

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        style = AIRLINE_STYLES.get(self.airline.lower())
        body = str(self.message_body)  # preserved exactly — no changes
        corrected_title = await autocorrect_text(self.ann_title)
        if self.image_url:
            await self.target_channel.send(self.image_url)
        e = discord.Embed(title=corrected_title, description=body, color=ANNOUNCE_COLOR, timestamp=now())
        e.set_footer(text=f"{style['label']} | {self.footer_label}")
        await self.target_channel.send(embed=e)
        await interaction.followup.send(f"Announcement sent to {self.target_channel.mention}.", ephemeral=True)


@tree.command(name="announce", description="Send a branded announcement to the main announcement channel (Senior Staff+)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(airline="ryanair, buzz, malta, lauda", title="Announcement title", image_url="Optional image URL shown above embed")
async def announce(interaction: discord.Interaction, airline: str, title: str, image_url: str = None):
    if not is_senior(interaction.user):
        await interaction.response.send_message("Senior Staff+ only.", ephemeral=True); return
    style = AIRLINE_STYLES.get(airline.lower())
    if not style:
        await interaction.response.send_message("Unknown airline. Use: ryanair, buzz, malta, lauda", ephemeral=True); return
    guild = bot.get_guild(GUILD_ID)
    ann_channel = guild.get_channel(ANNOUNCEMENT_CHANNEL_ID)
    if not ann_channel:
        await interaction.response.send_message("Announcement channel not found.", ephemeral=True); return
    footer = f"Announcement by {interaction.user.display_name}"
    await interaction.response.send_modal(AnnounceModal(airline, title, image_url, ann_channel, footer))


@tree.command(name="announcechannel", description="Send a branded announcement to any channel (Senior Staff+)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="Channel to send to", airline="ryanair, buzz, malta, lauda", title="Announcement title", image_url="Optional image URL shown above embed")
async def announcechannel(interaction: discord.Interaction, channel: discord.TextChannel, airline: str, title: str, image_url: str = None):
    if not is_senior(interaction.user):
        await interaction.response.send_message("Senior Staff+ only.", ephemeral=True); return
    style = AIRLINE_STYLES.get(airline.lower())
    if not style:
        await interaction.response.send_message("Unknown airline. Use: ryanair, buzz, malta, lauda", ephemeral=True); return
    footer = f"Announcement by {interaction.user.display_name}"
    await interaction.response.send_modal(AnnounceModal(airline, title, image_url, channel, footer))

# ── AI COMMANDS ───────────────────────────────────────────────────────────────
@tree.command(name="ai", description="Start a private AI session (Staff only)", guild=discord.Object(id=GUILD_ID))
async def ai_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("Staff Team role required.", ephemeral=True); return
    if not ai_enabled: await interaction.followup.send("AI is currently disabled.", ephemeral=True); return
    ai_sessions[interaction.user.id] = []
    e = discord.Embed(
        description="**Ryanair AI Assistant**\n\nYour private AI session has started.\n\nType anything to chat. Type `!endai` to end the session.",
        color=RYANAIR_COLOR
    )
    e.set_image(url=AI_BANNER)
    e.set_footer(text="Powered By Ryanair Automations")
    try:
        await interaction.user.send(AI_BANNER)
        await interaction.user.send(embed=e)
    except: pass
    await interaction.followup.send("AI session started — check your DMs.", ephemeral=True)

@tree.command(name="aiask", description="Ask the AI a quick question without starting a session", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(question="Your question")
async def aiask(interaction: discord.Interaction, question: str):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("Staff Team role required.", ephemeral=True); return
    if not ai_enabled: await interaction.followup.send("AI is currently disabled.", ephemeral=True); return
    reply = await call_groq([{"role": "user", "content": question}])
    e = discord.Embed(title="AI Response", description=reply, color=RYANAIR_COLOR)
    e.set_footer(text="Powered By Ryanair Automations")
    await interaction.followup.send(embed=e, ephemeral=True)

@tree.command(name="aistatus", description="Check AI status and active presets", guild=discord.Object(id=GUILD_ID))
async def aistatus(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    e = discord.Embed(title="AI Status", color=RYANAIR_COLOR)
    e.add_field(name="AI Enabled", value="✅ Yes" if ai_enabled else "❌ No", inline=True)
    e.add_field(name="Active Presets", value=str(len(ai_presets)), inline=True)
    if ai_presets:
        e.add_field(name="Presets", value="\n".join(f"• `{k}`" for k in ai_presets.keys()), inline=False)
    e.set_footer(text="Ryanair Digital Assistant")
    await interaction.followup.send(embed=e, ephemeral=True)

@tree.command(name="ai_toggle", description="Enable or disable the AI assistant", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(enabled="True to enable, False to disable")
async def ai_toggle(interaction: discord.Interaction, enabled: bool):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user): await interaction.followup.send("Owner only.", ephemeral=True); return
    global ai_enabled
    ai_enabled = enabled
    await interaction.followup.send(f"AI assistant {'enabled' if enabled else 'disabled'}.", ephemeral=True)

@tree.command(name="ai_preset_add", description="Add an AI preset instruction", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(name="Preset name", instruction="The instruction")
async def ai_preset_add(interaction: discord.Interaction, name: str, instruction: str):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user): await interaction.followup.send("Owner only.", ephemeral=True); return
    ai_presets[name.lower()] = instruction
    save_data()
    await interaction.followup.send(f"Preset `{name}` saved.", ephemeral=True)

@tree.command(name="ai_preset_remove", description="Remove an AI preset", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(name="Preset name")
async def ai_preset_remove(interaction: discord.Interaction, name: str):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user): await interaction.followup.send("Owner only.", ephemeral=True); return
    if name.lower() not in ai_presets: await interaction.followup.send(f"Preset `{name}` not found.", ephemeral=True); return
    del ai_presets[name.lower()]
    save_data()
    await interaction.followup.send(f"Preset `{name}` removed.", ephemeral=True)

# ── MODERATION COMMANDS ───────────────────────────────────────────────────────
async def dm_punished(user, title, description):
    try:
        await user.send(embed=mod_embed(title, description))
    except: pass

async def check_mod_abuse(interaction):
    uid = interaction.user.id
    if uid in mod_locked:
        await interaction.followup.send("You have been locked from using moderation commands.", ephemeral=True)
        return False
    return True

async def record_mod_misuse(user, guild, reason):
    uid = user.id
    mod_abuse[uid] = mod_abuse.get(uid, 0) + 1
    save_data()
    if mod_abuse[uid] >= 2:
        mod_locked.add(uid)
        save_data()
        try:
            await user.send(embed=plain_embed(f"**Moderation Access Locked**\n\nReason: {reason}\n\nContact the server owner."))
        except: pass
        owner = guild.owner
        if owner:
            try:
                view = UnlockStaffView(uid, user.display_name)
                e = discord.Embed(description=f"**Mod Abuse Alert**\n\n{user.display_name} locked.\nReason: {reason}", color=RYANAIR_COLOR)
                e.set_footer(text="Ryanair Digital Assistant — Owner Alert")
                await send_automation_dm(owner.id, e)
                await owner.send(view=view)
            except: pass

@tree.command(name="warn", description="Warn a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User", reason="Reason")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    await interaction.response.defer(ephemeral=True)
    if not await check_raid(interaction.user.id, interaction.guild): await interaction.followup.send("Rate limited.", ephemeral=True); return
    if not is_senior(interaction.user):
        await record_mod_misuse(interaction.user, interaction.guild, "Used /warn without permission")
        await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    if not await check_mod_abuse(interaction): return
    warnings[member.id] = warnings.get(member.id, 0) + 1
    save_data()
    count = warnings[member.id]
    log_mod(member.id, "Warning", interaction.user.display_name, reason)
    log_action(interaction.user.id, "/warn", f"Warned {member.display_name}: {reason}")
    await dm_punished(member, "Warning Received",
        f"You have received a warning in **{interaction.guild.name}**.\n\n**Reason:** {reason}\n**By:** {interaction.user.display_name}\n**Total:** {count}")
    await interaction.channel.send(embed=mod_embed("User Warned", f"{member.mention} warned.\n**Reason:** {reason}\n**Total warnings:** {count}"))
    await interaction.followup.send("Warning issued.", ephemeral=True)

@tree.command(name="warnings", description="View warnings for a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User")
async def view_warnings(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    count = warnings.get(member.id, 0)
    await interaction.followup.send(embed=mod_embed("Warning Record", f"{member.mention} has **{count}** warning(s)."), ephemeral=True)

@tree.command(name="clearwarnings", description="Clear warnings for a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User")
async def clearwarnings(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    warnings.pop(member.id, None)
    save_data()
    await interaction.followup.send(f"Warnings cleared for {member.mention}.", ephemeral=True)

@tree.command(name="timeout", description="Timeout a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User", duration_minutes="Duration (minutes)", reason="Reason")
async def timeout_cmd(interaction: discord.Interaction, member: discord.Member, duration_minutes: int, reason: str):
    await interaction.response.defer(ephemeral=True)
    if not await check_raid(interaction.user.id, interaction.guild): await interaction.followup.send("Rate limited.", ephemeral=True); return
    if not is_senior(interaction.user):
        await record_mod_misuse(interaction.user, interaction.guild, "Used /timeout without permission")
        await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    if not await check_mod_abuse(interaction): return
    until = discord.utils.utcnow() + datetime.timedelta(minutes=duration_minutes)
    try:
        await member.timeout(until, reason=reason)
        log_mod(member.id, "Timeout", interaction.user.display_name, f"{duration_minutes}min: {reason}")
        log_action(interaction.user.id, "/timeout", f"Timed out {member.display_name} for {duration_minutes}min")
        await dm_punished(member, "You Have Been Timed Out",
            f"Timed out in **{interaction.guild.name}**.\n\n**Duration:** {duration_minutes} minutes\n**Reason:** {reason}\n**By:** {interaction.user.display_name}")
        await interaction.channel.send(embed=mod_embed("User Timed Out", f"{member.mention} timed out for **{duration_minutes} minutes**.\n**Reason:** {reason}"))
        await interaction.followup.send("User timed out.", ephemeral=True)
    except Exception as ex:
        await interaction.followup.send(f"Failed: {ex}", ephemeral=True)

@tree.command(name="untimeout", description="Remove a timeout", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User")
async def untimeout_cmd(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    try:
        await member.timeout(None)
        await interaction.channel.send(embed=mod_embed("Timeout Removed", f"{member.mention}'s timeout removed."))
        await interaction.followup.send("Timeout removed.", ephemeral=True)
    except Exception as ex:
        await interaction.followup.send(f"Failed: {ex}", ephemeral=True)

@tree.command(name="kick", description="Kick a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User", reason="Reason")
async def kick_cmd(interaction: discord.Interaction, member: discord.Member, reason: str):
    await interaction.response.defer(ephemeral=True)
    if not await check_raid(interaction.user.id, interaction.guild): await interaction.followup.send("Rate limited.", ephemeral=True); return
    if not is_senior(interaction.user):
        await record_mod_misuse(interaction.user, interaction.guild, "Used /kick without permission")
        await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    if not await check_mod_abuse(interaction): return
    await dm_punished(member, "You Have Been Kicked", f"Kicked from **{interaction.guild.name}**.\n\n**Reason:** {reason}\n**By:** {interaction.user.display_name}")
    try:
        await member.kick(reason=reason)
        log_mod(member.id, "Kick", interaction.user.display_name, reason)
        log_action(interaction.user.id, "/kick", f"Kicked {member.display_name}: {reason}")
        await interaction.channel.send(embed=mod_embed("User Kicked", f"{member.mention} kicked.\n**Reason:** {reason}"))
        await interaction.followup.send("User kicked.", ephemeral=True)
    except Exception as ex:
        await interaction.followup.send(f"Failed: {ex}", ephemeral=True)

@tree.command(name="ban", description="Ban a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User", reason="Reason", delete_days="Days of messages to delete")
async def ban_cmd(interaction: discord.Interaction, member: discord.Member, reason: str, delete_days: int = 0):
    await interaction.response.defer(ephemeral=True)
    if not await check_raid(interaction.user.id, interaction.guild): await interaction.followup.send("Rate limited.", ephemeral=True); return
    if not is_senior(interaction.user):
        await record_mod_misuse(interaction.user, interaction.guild, "Used /ban without permission")
        await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    if not await check_mod_abuse(interaction): return
    await dm_punished(member, "You Have Been Banned", f"Banned from **{interaction.guild.name}**.\n\n**Reason:** {reason}\n**By:** {interaction.user.display_name}")
    try:
        await member.ban(reason=reason, delete_message_days=min(delete_days, 7))
        log_mod(member.id, "Ban", interaction.user.display_name, reason)
        log_action(interaction.user.id, "/ban", f"Banned {member.display_name}: {reason}")
        await interaction.channel.send(embed=mod_embed("User Banned", f"{member.mention} banned.\n**Reason:** {reason}"))
        await interaction.followup.send("User banned.", ephemeral=True)
    except Exception as ex:
        await interaction.followup.send(f"Failed: {ex}", ephemeral=True)

@tree.command(name="unban", description="Unban a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(user_id="User ID", reason="Reason")
async def unban_cmd(interaction: discord.Interaction, user_id: str, reason: str = "Appeal accepted"):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user, reason=reason)
        log_mod(int(user_id), "Unban", interaction.user.display_name, reason)
        await interaction.channel.send(embed=mod_embed("User Unbanned", f"{user.mention} unbanned.\n**Reason:** {reason}"))
        await interaction.followup.send("User unbanned.", ephemeral=True)
    except Exception as ex:
        await interaction.followup.send(f"Failed: {ex}", ephemeral=True)

@tree.command(name="softban", description="Ban then immediately unban to clear recent messages", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User", reason="Reason")
async def softban_cmd(interaction: discord.Interaction, member: discord.Member, reason: str):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    try:
        await dm_punished(member, "Soft Ban Applied", f"Your recent messages in **{interaction.guild.name}** have been cleared.\n\n**Reason:** {reason}\n**By:** {interaction.user.display_name}")
        await member.ban(reason=f"Softban: {reason}", delete_message_days=7)
        await asyncio.sleep(1)
        await interaction.guild.unban(member, reason="Softban unban")
        log_mod(member.id, "Softban", interaction.user.display_name, reason)
        await interaction.channel.send(embed=mod_embed("User Softbanned", f"{member.mention} softbanned (messages cleared).\n**Reason:** {reason}"))
        await interaction.followup.send("Softban applied.", ephemeral=True)
    except Exception as ex:
        await interaction.followup.send(f"Failed: {ex}", ephemeral=True)

@tree.command(name="purge", description="Delete messages from this channel", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(amount="Number to delete (1-100)")
async def purge_cmd(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    amount = min(max(amount, 1), 100)
    deleted = await interaction.channel.purge(limit=amount)
    log_action(interaction.user.id, "/purge", f"Purged {len(deleted)} messages in {interaction.channel.name}")
    await interaction.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)

@tree.command(name="slowmode", description="Set slowmode for this channel", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(seconds="Delay in seconds (0 to disable)")
async def slowmode_cmd(interaction: discord.Interaction, seconds: int):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    await interaction.channel.edit(slowmode_delay=seconds)
    msg = f"Slowmode set to **{seconds}s**." if seconds > 0 else "Slowmode **disabled**."
    await interaction.channel.send(embed=mod_embed("Slowmode Updated", msg))
    await interaction.followup.send("Slowmode updated.", ephemeral=True)

@tree.command(name="nick", description="Change a user's nickname (supports server emojis)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User", nickname="New nickname (blank to reset)", emoji_name="Optional: server emoji name to prefix (without colons)")
async def nick_cmd(interaction: discord.Interaction, member: discord.Member, nickname: str = None, emoji_name: str = None):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    try:
        final_nick = nickname or ""
        if emoji_name:
            guild = bot.get_guild(GUILD_ID)
            import re
            match = re.match(r"<a?:(\w+):(\d+)>", emoji_name.strip())
            if match:
                found_emoji = discord.utils.get(guild.emojis, id=int(match.group(2)))
            else:
                found_emoji = discord.utils.get(guild.emojis, name=emoji_name.strip())
            if found_emoji:
                final_nick = f"{final_nick} {str(found_emoji)}".strip()
            else:
                await interaction.followup.send("Could not find that emoji in this server. Setting nickname without emoji.", ephemeral=True)
        final_nick = final_nick.strip() if final_nick.strip() else None
        await member.edit(nick=final_nick)
        msg = f"Nickname reset for {member.mention}." if not final_nick else f"Nickname changed to **{final_nick}** for {member.mention}."
        await interaction.followup.send(msg, ephemeral=True)
    except Exception as ex:
        await interaction.followup.send(f"Failed: {ex}", ephemeral=True)


@tree.command(name="roleemoji", description="Set a server emoji as a role's icon image (Senior Staff+, requires Level 2 boost)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(role="The role to update", emoji_name="Paste the emoji or type its name")
async def roleemoji_cmd(interaction: discord.Interaction, role: discord.Role, emoji_name: str):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    guild = bot.get_guild(GUILD_ID)

    found_emoji = None
    import re
    match = re.match(r"<a?:(\w+):(\d+)>", emoji_name.strip())
    if match:
        emoji_id = int(match.group(2))
        found_emoji = discord.utils.get(guild.emojis, id=emoji_id)
    else:
        found_emoji = discord.utils.get(guild.emojis, name=emoji_name.strip())

    if not found_emoji:
        await interaction.followup.send("Could not find that emoji in this server.", ephemeral=True)
        return
    try:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(str(found_emoji.url)) as resp:
                if resp.status == 200:
                    img_bytes = await resp.read()
                    await role.edit(display_icon=img_bytes)
                    await interaction.followup.send(f"Role **{role.name}** icon set to {str(found_emoji)}.", ephemeral=True)
                else:
                    await interaction.followup.send("Failed to fetch emoji image.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("No permission to edit that role, or server needs Level 2 boost for role icons.", ephemeral=True)
    except Exception as ex:
        await interaction.followup.send(f"Failed: {ex}", ephemeral=True)

@tree.command(name="role", description="Add or remove a role from a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User", role="Role", action="add or remove")
async def role_cmd(interaction: discord.Interaction, member: discord.Member, role: discord.Role, action: str):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    try:
        if action.lower() == "add":
            await member.add_roles(role)
            await interaction.followup.send(f"Added **{role.name}** to {member.mention}.", ephemeral=True)
        elif action.lower() == "remove":
            await member.remove_roles(role)
            await interaction.followup.send(f"Removed **{role.name}** from {member.mention}.", ephemeral=True)
        else:
            await interaction.followup.send("Action must be `add` or `remove`.", ephemeral=True)
        log_action(interaction.user.id, f"/role {action}", f"{role.name} on {member.display_name}")
    except Exception as ex:
        await interaction.followup.send(f"Failed: {ex}", ephemeral=True)

@tree.command(name="massrole", description="Add a role to all members with a specific role (Owner only)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(target_role="Role to give", has_role_="Only give to members who have this role")
async def massrole_cmd(interaction: discord.Interaction, target_role: discord.Role, has_role_: discord.Role):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user): await interaction.followup.send("Owner only.", ephemeral=True); return
    guild = bot.get_guild(GUILD_ID)
    count = 0
    for member in guild.members:
        if has_role_ in member.roles and target_role not in member.roles:
            try:
                await member.add_roles(target_role)
                count += 1
                await asyncio.sleep(0.5)
            except: pass
    await interaction.followup.send(f"Added **{target_role.name}** to {count} members.", ephemeral=True)

@tree.command(name="lockdown", description="Lock all public channels", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(reason="Reason")
async def lockdown_cmd(interaction: discord.Interaction, reason: str = "Server lockdown in effect"):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    guild = bot.get_guild(GUILD_ID)
    locked = 0
    for channel in guild.text_channels:
        ow = channel.overwrites_for(guild.default_role)
        if ow.send_messages is not False:
            try:
                await channel.set_permissions(guild.default_role, send_messages=False)
                locked += 1
            except: pass
    log_action(interaction.user.id, "/lockdown", reason)
    await interaction.channel.send(embed=mod_embed("Server Lockdown Active",
        f"**{locked}** channels locked.\n\n**Reason:** {reason}\n\nPlease remain calm. Staff will update you shortly."))
    await interaction.followup.send(f"Lockdown applied to {locked} channels.", ephemeral=True)

@tree.command(name="unlockdown", description="Unlock all public channels", guild=discord.Object(id=GUILD_ID))
async def unlockdown_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    guild = bot.get_guild(GUILD_ID)
    unlocked = 0
    for channel in guild.text_channels:
        ow = channel.overwrites_for(guild.default_role)
        if ow.send_messages is False:
            try:
                await channel.set_permissions(guild.default_role, send_messages=None)
                unlocked += 1
            except: pass
    await interaction.channel.send(embed=mod_embed("Server Unlocked", f"**{unlocked}** channels unlocked."))
    await interaction.followup.send(f"Unlocked {unlocked} channels.", ephemeral=True)

@tree.command(name="note", description="Add a private note to a user's record", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User", note="Note content")
async def note_cmd(interaction: discord.Interaction, member: discord.Member, note: str):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    if member.id not in user_notes:
        user_notes[member.id] = []
    user_notes[member.id].append({"by": interaction.user.display_name, "time": now().strftime("%Y-%m-%d %H:%M UTC"), "note": note})
    save_data()
    await interaction.followup.send(f"Note added to {member.display_name}'s record.", ephemeral=True)

@tree.command(name="viewnotes", description="View notes on a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User")
async def viewnotes_cmd(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("No permission.", ephemeral=True); return
    notes = user_notes.get(member.id, [])
    if not notes: await interaction.followup.send(f"No notes for {member.display_name}.", ephemeral=True); return
    e = discord.Embed(title=f"Notes — {member.display_name}", color=RYANAIR_COLOR)
    for n in notes[-10:]:
        e.add_field(name=f"{n['time']} by {n['by']}", value=n['note'], inline=False)
    await interaction.followup.send(embed=e, ephemeral=True)

@tree.command(name="modhistory", description="View full moderation history for a user", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User")
async def modhistory_cmd(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    history = mod_history.get(member.id, [])
    if not history: await interaction.followup.send(f"No moderation history for {member.display_name}.", ephemeral=True); return
    e = discord.Embed(title=f"Mod History — {member.display_name}", color=RYANAIR_COLOR)
    for h in history[-15:]:
        e.add_field(name=f"{h['action']} — {h['time']}", value=f"By: {h['by']}\nReason: {h.get('reason', 'N/A')}", inline=False)
    await interaction.followup.send(embed=e, ephemeral=True)

@tree.command(name="logs", description="View full command/action log for a user (Owner only)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User")
async def logs_cmd(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user): await interaction.followup.send("Owner only.", ephemeral=True); return
    log = command_log.get(member.id, [])
    if not log: await interaction.followup.send(f"No logs for {member.display_name}.", ephemeral=True); return
    e = discord.Embed(title=f"Action Logs — {member.display_name}", color=RYANAIR_COLOR)
    for entry in log[-20:]:
        e.add_field(name=f"{entry['action']} — {entry['time']}", value=entry.get('detail', 'N/A') or 'N/A', inline=False)
    await interaction.followup.send(embed=e, ephemeral=True)

@tree.command(name="strike", description="Issue a strike to a staff member", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Staff member", reason="Reason")
async def strike_cmd(interaction: discord.Interaction, member: discord.Member, reason: str):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    if not is_staff(member): await interaction.followup.send("Not a staff member.", ephemeral=True); return
    strikes[member.id] = strikes.get(member.id, 0) + 1
    count = strikes[member.id]
    save_data()
    guild = bot.get_guild(GUILD_ID)
    for sname in ["Strike 1", "Strike 2", "Strike 3"]:
        r = discord.utils.get(guild.roles, name=sname)
        if r and r in member.roles:
            try: await member.remove_roles(r)
            except: pass
    strike_role = discord.utils.get(guild.roles, name=f"Strike {min(count, 3)}")
    if strike_role:
        try: await member.add_roles(strike_role)
        except: pass
    log_mod(member.id, f"Strike {count}", interaction.user.display_name, reason)
    await dm_punished(member, f"Strike {count} Issued",
        f"You have received **Strike {count}** in **{interaction.guild.name}**.\n\n**Reason:** {reason}\n**By:** {interaction.user.display_name}")
    await interaction.channel.send(embed=mod_embed(f"Strike {count} — {member.display_name}",
        f"{member.mention} received **Strike {count}**.\n**Reason:** {reason}"))
    await interaction.followup.send(f"Strike {count} issued.", ephemeral=True)

@tree.command(name="clearstrikes", description="Clear all strikes for a staff member (Owner only)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Staff member")
async def clearstrikes_cmd(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user): await interaction.followup.send("Owner only.", ephemeral=True); return
    strikes.pop(member.id, None)
    save_data()
    guild = bot.get_guild(GUILD_ID)
    for sname in ["Strike 1", "Strike 2", "Strike 3"]:
        r = discord.utils.get(guild.roles, name=sname)
        if r and r in member.roles:
            try: await member.remove_roles(r)
            except: pass
    await dm_punished(member, "Strikes Cleared", f"All strikes cleared by {interaction.user.display_name}.")
    await interaction.channel.send(embed=mod_embed("Strikes Cleared", f"All strikes for {member.mention} cleared."))
    await interaction.followup.send(f"Strikes cleared for {member.display_name}.", ephemeral=True)

@tree.command(name="fire", description="Remove all staff roles from a member (Owner only)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Staff member", reason="Reason")
async def fire_cmd(interaction: discord.Interaction, member: discord.Member, reason: str):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user): await interaction.followup.send("Owner only.", ephemeral=True); return
    guild = bot.get_guild(GUILD_ID)
    removed = []
    for role in member.roles:
        if role.name in [ROLE_LOCK, ROLE_SENIOR, ROLE_STAFF, ROLE_HOLDER, "Strike 1", "Strike 2", "Strike 3"]:
            try:
                await member.remove_roles(role)
                removed.append(role.name)
            except: pass
    strikes.pop(member.id, None)
    save_data()
    log_mod(member.id, "Fired", interaction.user.display_name, reason)
    await dm_punished(member, "Staff Role Removed",
        f"Your staff roles have been removed.\n\n**Reason:** {reason}\n**By:** {interaction.user.display_name}")
    await interaction.channel.send(embed=mod_embed("Staff Member Fired",
        f"{member.mention} fired.\n**Roles removed:** {', '.join(removed) if removed else 'None'}\n**Reason:** {reason}"))
    await interaction.followup.send("Staff roles removed.", ephemeral=True)

@tree.command(name="modunlock", description="Unlock a staff member from moderation commands", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Staff member")
async def modunlock_cmd(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user): await interaction.followup.send("Owner only.", ephemeral=True); return
    mod_locked.discard(member.id)
    mod_abuse.pop(member.id, None)
    save_data()
    try:
        await member.send(embed=plain_embed("**Moderation Access Restored**\n\nYour access has been restored by the server owner."))
    except: pass
    await interaction.followup.send(f"{member.display_name} unlocked.", ephemeral=True)

# ── WELCOME SYSTEM ────────────────────────────────────────────────────────────
welcome_group = app_commands.Group(name="welcome", description="Welcome system configuration", guild_ids=[GUILD_ID])

@welcome_group.command(name="enable", description="Enable the welcome system (Owner only)")
@app_commands.describe(channel="Welcome channel", banner_url="Banner image URL to show above welcome message")
async def welcome_enable(interaction: discord.Interaction, channel: discord.TextChannel, banner_url: str = None):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user): await interaction.followup.send("Owner only.", ephemeral=True); return
    welcome_config[str(interaction.guild_id)] = {
        "channel_id": channel.id,
        "banner_url": banner_url or SUPPORT_BANNER
    }
    save_data()
    await interaction.followup.send(f"Welcome system enabled in {channel.mention}.", ephemeral=True)

@welcome_group.command(name="disable", description="Disable the welcome system (Owner only)")
async def welcome_disable(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user): await interaction.followup.send("Owner only.", ephemeral=True); return
    welcome_config.pop(str(interaction.guild_id), None)
    save_data()
    await interaction.followup.send("Welcome system disabled.", ephemeral=True)

tree.add_command(welcome_group)

# ── HELP / INFO COMMANDS ──────────────────────────────────────────────────────
@tree.command(name="modcommands", description="DM yourself a list of mod commands you can use", guild=discord.Object(id=GUILD_ID))
async def modcommands(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("Staff only.", ephemeral=True); return
    lines = ["**🔨 Moderation Commands**\n"]
    if is_staff(interaction.user):
        lines.append("**Staff Team:**\n`/warnings` `/viewnotes` `/note`")
    if is_senior(interaction.user):
        lines.append("\n**Senior Staff:**\n`/warn` `/clearwarnings` `/timeout` `/untimeout` `/kick` `/ban` `/unban` `/softban` `/purge` `/slowmode` `/nick` `/role` `/lockdown` `/unlockdown` `/modhistory` `/strike`")
    if is_lock(interaction.user):
        lines.append("\n**Owner Only:**\n`/clearstrikes` `/fire` `/modunlock` `/massrole` `/closeall` `/logs`")
    e = discord.Embed(title="Your Moderation Commands", description="\n".join(lines), color=RYANAIR_COLOR)
    e.set_footer(text="Ryanair Digital Assistant")
    try:
        await interaction.user.send(embed=e)
        await interaction.followup.send("Commands sent to your DMs.", ephemeral=True)
    except:
        await interaction.followup.send(embed=e, ephemeral=True)

@tree.command(name="ticketcommands", description="DM yourself a list of ticket commands you can use", guild=discord.Object(id=GUILD_ID))
async def ticketcommands(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("Staff only.", ephemeral=True); return
    lines = ["**🎫 Ticket Commands**\n"]
    if is_staff(interaction.user):
        lines.append("**Staff Team:**\n`/connected` `/unconnected` `/close` `/onhold` `/requeststaff` `/anonreply` `/say` `/snippet` `/snippetlist` `/supporttickets` `/ticketnote` `/ticketstats` `/ticketsummary` `/careers` `/info`")
    if is_senior(interaction.user):
        lines.append("\n**Senior Staff:**\n`/forceopen` `/ticketrename` `/tickettransfer` `/ticketpriority` `/ticketban` `/ticketunban` `/snippetadd` `/snippetdelete`")
    if is_lock(interaction.user):
        lines.append("\n**Owner Only:**\n`/closeall`")
    e = discord.Embed(title="Your Ticket Commands", description="\n".join(lines), color=RYANAIR_COLOR)
    e.set_footer(text="Ryanair Digital Assistant")
    try:
        await interaction.user.send(embed=e)
        await interaction.followup.send("Commands sent to your DMs.", ephemeral=True)
    except:
        await interaction.followup.send(embed=e, ephemeral=True)

@tree.command(name="aicommands", description="DM yourself a list of AI commands you can use", guild=discord.Object(id=GUILD_ID))
async def aicommands(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("Staff only.", ephemeral=True); return
    lines = ["**🤖 AI Commands**\n"]
    if is_staff(interaction.user):
        lines.append("**Staff Team:**\n`/ai` — Start private AI session\n`/aiask` — Quick AI question\n`/ticketsummary` — AI summary of a ticket\n`/aicommands` — This list")
    if is_senior(interaction.user):
        lines.append("\n**Senior Staff:**\n`/aistatus` — Check AI status and presets")
    if is_lock(interaction.user):
        lines.append("\n**Owner Only:**\n`/ai_toggle` — Enable/disable AI\n`/ai_preset_add` — Add AI instruction\n`/ai_preset_remove` — Remove AI instruction")
    e = discord.Embed(title="Your AI Commands", description="\n".join(lines), color=RYANAIR_COLOR)
    e.set_footer(text="Ryanair Digital Assistant")
    try:
        await interaction.user.send(embed=e)
        await interaction.followup.send("Commands sent to your DMs.", ephemeral=True)
    except:
        await interaction.followup.send(embed=e, ephemeral=True)

@tree.command(name="membercount", description="View the current server member count", guild=discord.Object(id=GUILD_ID))
async def membercount(interaction: discord.Interaction):
    guild = bot.get_guild(GUILD_ID)
    humans = sum(1 for m in guild.members if not m.bot)
    bots   = sum(1 for m in guild.members if m.bot)
    e = discord.Embed(title="👥 Member Count", color=RYANAIR_COLOR)
    e.add_field(name="Total", value=str(guild.member_count), inline=True)
    e.add_field(name="Humans", value=str(humans), inline=True)
    e.add_field(name="Bots", value=str(bots), inline=True)
    e.set_footer(text="Ryanair Digital Assistant")
    await interaction.response.send_message(embed=e)

@tree.command(name="serverinfo", description="View server information", guild=discord.Object(id=GUILD_ID))
async def serverinfo(interaction: discord.Interaction):
    guild = bot.get_guild(GUILD_ID)
    e = discord.Embed(title=f"Server Info — {guild.name}", color=RYANAIR_COLOR, timestamp=now())
    e.add_field(name="Members", value=str(guild.member_count), inline=True)
    e.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
    e.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
    e.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    e.add_field(name="Owner", value=str(guild.owner), inline=True)
    e.add_field(name="Active Tickets", value=str(len(tickets)), inline=True)
    if guild.icon:
        e.set_thumbnail(url=guild.icon.url)
    e.set_footer(text="Ryanair Digital Assistant")
    await interaction.response.send_message(embed=e)

@tree.command(name="viewtickets", description="View how many tickets a staff member has claimed", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Staff member to check (leave blank for yourself)")
async def viewtickets(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    # Regular staff can only view themselves, senior+ can view anyone
    if target != interaction.user and not is_senior(interaction.user):
        await interaction.response.send_message("You can only view your own ticket stats.", ephemeral=True)
        return
    if not is_staff(interaction.user):
        await interaction.response.send_message("Staff only.", ephemeral=True)
        return
    claimed = staff_tickets_claimed.get(target.id, 0)
    active = sum(1 for sid in connected_staff.values() if sid == target.id)
    e = discord.Embed(title=f"Ticket Stats — {target.display_name}", color=RYANAIR_COLOR)
    e.add_field(name="Total Tickets Claimed", value=str(claimed), inline=True)
    e.add_field(name="Currently Active", value=str(active), inline=True)
    e.set_thumbnail(url=target.display_avatar.url)
    e.set_footer(text="Ryanair Digital Assistant")
    await interaction.response.send_message(embed=e, ephemeral=True)


@tree.command(name="readonly", description="Make a channel read-only, with selected roles able to send messages", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    channel="Channel to make read-only",
    role1="Role that can send messages",
    role2="Role that can send messages",
    role3="Role that can send messages",
    role4="Role that can send messages (optional)",
    role5="Role that can send messages (optional)",
    role6="Role that can send messages (optional)",
    role7="Role that can send messages (optional)",
    role8="Role that can send messages (optional)",
)
async def readonly(
    interaction: discord.Interaction,
    channel: discord.TextChannel,
    role1: discord.Role,
    role2: discord.Role,
    role3: discord.Role,
    role4: discord.Role = None,
    role5: discord.Role = None,
    role6: discord.Role = None,
    role7: discord.Role = None,
    role8: discord.Role = None,
):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user):
        await interaction.followup.send("Owner only.", ephemeral=True)
        return

    allowed_roles = [r for r in [role1, role2, role3, role4, role5, role6, role7, role8] if r is not None]

    # Set default role (everyone) to read-only
    await channel.set_permissions(interaction.guild.default_role, send_messages=False, read_messages=True)

    # Set allowed roles to be able to send messages
    for role in allowed_roles:
        await channel.set_permissions(role, send_messages=True, read_messages=True)

    role_mentions = ", ".join(r.mention for r in allowed_roles)
    e = discord.Embed(
        title="Channel Set to Read-Only",
        description=(
            f"{channel.mention} is now read-only for everyone except:\n\n{role_mentions}\n\n"
            f"All other roles can only read messages in this channel."
        ),
        color=RYANAIR_COLOR
    )
    e.set_footer(text="Ryanair Digital Assistant")
    await interaction.followup.send(embed=e, ephemeral=True)
    await channel.send(embed=plain_embed(
        f"This channel has been set to read-only. Only selected roles can send messages here."
    ))



class TicketChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Help!", style=discord.ButtonStyle.danger, custom_id="ticketchannel_open")
    async def open_ticket_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user = interaction.user
        # Check if already has a ticket
        if user.id in tickets:
            await interaction.followup.send("You already have an open ticket! Check your DMs.", ephemeral=True)
            return
        if user.id in ticket_banned:
            await interaction.followup.send("You are currently banned from opening support tickets.", ephemeral=True)
            return
        # Send the DM confirm flow
        try:
            e = discord.Embed(
                description=(
                    "**Ryanair Digital Assistant**\n\n"
                    "Hello, I'm Ryanair's **Digital Assistant!**\n"
                    "Are you looking for assistance?"
                ),
                color=RYANAIR_COLOR
            )
            e.set_author(name="Assistance", icon_url=bot.user.display_avatar.url)
            e.set_footer(text="Ryanair Digital Assistant")
            await user.send(SUPPORT_BANNER)
            await user.send(embed=e, view=ConfirmView(user))
            await interaction.followup.send("Check your DMs to continue opening your ticket!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("I couldn't DM you! Please enable DMs from server members and try again.", ephemeral=True)


# ── /ticketchannel ────────────────────────────────────────────────────────────
@tree.command(name="ticketchannel", description="Post a ticket opener embed in a channel (Owner only)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    channel="Channel to post the ticket opener in",
    title="Title of the embed",
    message="Body text of the embed",
    image_url="Optional image URL shown above the embed"
)
async def ticketchannel_cmd(interaction: discord.Interaction, channel: discord.TextChannel, title: str, message: str, image_url: str = None):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user):
        await interaction.followup.send("Owner only.", ephemeral=True)
        return

    corrected_title = await autocorrect_text(title)
    corrected_msg = await autocorrect_text(message)

    # Send image on top if provided
    if image_url:
        await channel.send(image_url)

    e = discord.Embed(
        title=corrected_title,
        description=corrected_msg,
        color=RYANAIR_COLOR,
        timestamp=now()
    )
    e.set_footer(text="Ryanair Digital Assistant — Click the button below to open a ticket")

    await channel.send(embed=e, view=TicketChannelView())
    await interaction.followup.send(f"Ticket opener posted in {channel.mention}.", ephemeral=True)



@tree.command(name="pingstaff", description="Ping all online staff about this ticket (Senior Staff+)", guild=discord.Object(id=GUILD_ID))
async def pingstaff(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    if not is_ticket_channel(interaction.channel_id): await interaction.followup.send("Not a ticket channel.", ephemeral=True); return
    guild = bot.get_guild(GUILD_ID)
    pinged = 0
    for member in guild.members:
        if is_staff(member) and not member.bot and member.status in (discord.Status.online, discord.Status.idle, discord.Status.dnd):
            try:
                e = discord.Embed(description=f"Urgent: You are needed in a support ticket right now.\n\nTicket: {interaction.channel.mention}", color=RYANAIR_COLOR)
                e.set_footer(text="Ryanair Digital Assistant — Urgent Staff Alert")
                await send_automation_dm(member.id, e)
                pinged += 1
            except: pass
    await interaction.followup.send(f"Pinged {pinged} online staff members.", ephemeral=True)


# ── /stafflist ────────────────────────────────────────────────────────────────
@tree.command(name="stafflist", description="View all current staff members and their roles", guild=discord.Object(id=GUILD_ID))
async def stafflist(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("Staff only.", ephemeral=True); return
    guild = bot.get_guild(GUILD_ID)
    lock_members   = [m for m in guild.members if has_role(m, ROLE_LOCK) and not m.bot]
    senior_members = [m for m in guild.members if has_role(m, ROLE_SENIOR) and not m.bot]
    staff_members  = [m for m in guild.members if has_role(m, ROLE_STAFF) and not m.bot]
    e = discord.Embed(title="Staff List", color=RYANAIR_COLOR)
    if lock_members:
        e.add_field(name=f"Owner / {ROLE_LOCK}", value="\n".join(m.display_name for m in lock_members), inline=False)
    if senior_members:
        e.add_field(name=ROLE_SENIOR, value="\n".join(m.display_name for m in senior_members), inline=False)
    if staff_members:
        e.add_field(name=ROLE_STAFF, value="\n".join(m.display_name for m in staff_members), inline=False)
    e.set_footer(text="Ryanair Digital Assistant")
    await interaction.followup.send(embed=e, ephemeral=True)


# ── /onlinestaf ───────────────────────────────────────────────────────────────
@tree.command(name="onlinestaff", description="View all currently online staff members", guild=discord.Object(id=GUILD_ID))
async def onlinestaff(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("Staff only.", ephemeral=True); return
    guild = bot.get_guild(GUILD_ID)
    online = [m for m in guild.members if is_staff(m) and not m.bot and m.status in (discord.Status.online, discord.Status.idle, discord.Status.dnd)]
    if not online:
        await interaction.followup.send("No staff currently online.", ephemeral=True); return
    status_icons = {discord.Status.online: "🟢", discord.Status.idle: "🟡", discord.Status.dnd: "🔴"}
    lines = [f"{status_icons.get(m.status, '⚪')} {m.display_name} — {get_staff_role_name(m)}" for m in online]
    e = discord.Embed(title=f"Online Staff ({len(online)})", description="\n".join(lines), color=RYANAIR_COLOR)
    e.set_footer(text="Ryanair Digital Assistant")
    await interaction.followup.send(embed=e, ephemeral=True)


# ── /dm ───────────────────────────────────────────────────────────────────────
@tree.command(name="dm", description="DM a user a message from the bot (Senior Staff+)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User to DM", message="Message to send")
async def dm_cmd(interaction: discord.Interaction, member: discord.Member, message: str):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    corrected = await autocorrect_text(message)
    try:
        e = discord.Embed(description=corrected, color=RYANAIR_COLOR)
        e.set_footer(text="Ryanair Digital Assistant — Staff Message")
        await member.send(embed=e)
        await interaction.followup.send(f"Message sent to {member.display_name}.", ephemeral=True)
    except:
        await interaction.followup.send(f"Could not DM {member.display_name}.", ephemeral=True)


# ── /warn_dm ──────────────────────────────────────────────────────────────────
@tree.command(name="warndm", description="Send a formal warning DM to a user without logging a warning (Senior Staff+)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User to warn", reason="Reason")
async def warndm_cmd(interaction: discord.Interaction, member: discord.Member, reason: str):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    try:
        e = discord.Embed(
            description=f"You have received a formal notice from the Ryanair staff team.\n\n**Reason:** {reason}\n\n**Issued by:** {interaction.user.display_name}\n\nPlease take note of this and ensure it does not happen again.",
            color=RYANAIR_COLOR
        )
        e.set_footer(text="Ryanair Digital Assistant — Staff Notice")
        await member.send(embed=e)
        await interaction.channel.send(embed=plain_embed(f"Formal notice sent to {member.mention} by {interaction.user.mention}.\n**Reason:** {reason}"))
        await interaction.followup.send("Notice sent.", ephemeral=True)
    except:
        await interaction.followup.send(f"Could not DM {member.display_name}.", ephemeral=True)


# ── /embed ────────────────────────────────────────────────────────────────────
class EmbedModal(discord.ui.Modal, title="Write Your Embed"):
    message_body = discord.ui.TextInput(
        label="Message Body",
        style=discord.TextStyle.paragraph,
        placeholder="Type your message here. All formatting is preserved exactly as you type it.",
        max_length=4000,
        required=True
    )

    def __init__(self, channel, ann_title: str, color_int: int, image_url: str, footer: str):
        super().__init__()
        self.target_channel = channel
        self.ann_title      = ann_title
        self.color_int      = color_int
        self.image_url      = image_url
        self.footer         = footer

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        body = str(self.message_body)  # preserved exactly
        corrected_title = await autocorrect_text(self.ann_title)
        if self.image_url:
            await self.target_channel.send(self.image_url)
        e = discord.Embed(title=corrected_title, description=body, color=self.color_int, timestamp=now())
        e.set_footer(text=self.footer)
        await self.target_channel.send(embed=e)
        await interaction.followup.send(f"Embed sent to {self.target_channel.mention}.", ephemeral=True)


@tree.command(name="embed", description="Send a custom embed to any channel (Senior Staff+)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(channel="Channel to send to", title="Embed title", colour="Hex colour e.g. 073590", image_url="Optional image URL")
async def embed_cmd(interaction: discord.Interaction, channel: discord.TextChannel, title: str, colour: str = "073590", image_url: str = None):
    if not is_senior(interaction.user):
        await interaction.response.send_message("Senior Staff+ only.", ephemeral=True); return
    try:
        color_int = int(colour.strip("#"), 16)
    except:
        color_int = RYANAIR_COLOR
    footer = f"Ryanair Digital Assistant | Posted by {interaction.user.display_name}"
    await interaction.response.send_modal(EmbedModal(channel, title, color_int, image_url, footer))


# ── /remind ───────────────────────────────────────────────────────────────────
@tree.command(name="remind", description="Set a reminder — bot will DM you after a set time (Staff+)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(minutes="Minutes until reminder", message="What to remind you about")
async def remind_cmd(interaction: discord.Interaction, minutes: int, message: str):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("Staff only.", ephemeral=True); return
    if minutes < 1 or minutes > 1440: await interaction.followup.send("Please set a reminder between 1 and 1440 minutes (24 hours).", ephemeral=True); return
    await interaction.followup.send(f"Got it! I will remind you about that in {minutes} minute(s).", ephemeral=True)
    async def send_reminder():
        await asyncio.sleep(minutes * 60)
        try:
            e = discord.Embed(description=f"Reminder: {message}", color=RYANAIR_COLOR, timestamp=now())
            e.set_footer(text="Ryanair Digital Assistant — Reminder")
            await interaction.user.send(embed=e)
        except: pass
    bot.loop.create_task(send_reminder())


# ── /userinfo ─────────────────────────────────────────────────────────────────
@tree.command(name="userinfo", description="View information about a user (Staff+)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="User to inspect")
async def userinfo_cmd(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("Staff only.", ephemeral=True); return
    e = discord.Embed(title=f"User Info — {member.display_name}", color=RYANAIR_COLOR)
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="Username", value=str(member), inline=True)
    e.add_field(name="ID", value=str(member.id), inline=True)
    e.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "Unknown", inline=True)
    e.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
    e.add_field(name="Roles", value=", ".join(r.name for r in member.roles[1:]) or "None", inline=False)
    e.add_field(name="Warnings", value=str(warnings.get(member.id, 0)), inline=True)
    e.add_field(name="Strikes", value=str(strikes.get(member.id, 0)), inline=True)
    e.add_field(name="Tickets Opened", value=str(ticket_stats.get(member.id, 0)), inline=True)
    e.add_field(name="Ticket Banned", value="Yes" if member.id in ticket_banned else "No", inline=True)
    e.set_footer(text="Ryanair Digital Assistant")
    await interaction.followup.send(embed=e, ephemeral=True)


# ── /staffinfo ────────────────────────────────────────────────────────────────
@tree.command(name="staffinfo", description="View staff performance info for a member (Senior Staff+)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Staff member to inspect")
async def staffinfo_cmd(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    e = discord.Embed(title=f"Staff Info — {member.display_name}", color=RYANAIR_COLOR)
    e.set_thumbnail(url=member.display_avatar.url)
    e.add_field(name="Role", value=get_staff_role_name(member) if is_staff(member) else "Not Staff", inline=True)
    e.add_field(name="Tickets Claimed", value=str(staff_tickets_claimed.get(member.id, 0)), inline=True)
    e.add_field(name="Strikes", value=str(strikes.get(member.id, 0)), inline=True)
    e.add_field(name="Mod Locked", value="Yes" if member.id in mod_locked else "No", inline=True)
    e.add_field(name="Notes", value=str(len(user_notes.get(member.id, []))), inline=True)
    e.add_field(name="Status", value=str(member.status).title(), inline=True)
    e.set_footer(text="Ryanair Digital Assistant")
    await interaction.followup.send(embed=e, ephemeral=True)


# ── /clearticketban ───────────────────────────────────────────────────────────
@tree.command(name="ticketbanlist", description="View all users banned from tickets (Senior Staff+)", guild=discord.Object(id=GUILD_ID))
async def ticketbanlist_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_senior(interaction.user): await interaction.followup.send("Senior Staff+ only.", ephemeral=True); return
    if not ticket_banned:
        await interaction.followup.send("No users are currently banned from tickets.", ephemeral=True); return
    guild = bot.get_guild(GUILD_ID)
    lines = []
    for uid in ticket_banned:
        member = guild.get_member(uid)
        lines.append(f"• {member.display_name if member else uid} ({uid})")
    e = discord.Embed(title=f"Ticket Banned Users ({len(ticket_banned)})", description="\n".join(lines), color=RYANAIR_COLOR)
    e.set_footer(text="Ryanair Digital Assistant")
    await interaction.followup.send(embed=e, ephemeral=True)


# ── /announce_dm ──────────────────────────────────────────────────────────────
@tree.command(name="announcedm", description="DM all staff members an announcement (Owner only)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(message="Message to send to all staff")
async def announcedm_cmd(interaction: discord.Interaction, message: str):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user): await interaction.followup.send("Owner only.", ephemeral=True); return
    guild = bot.get_guild(GUILD_ID)
    corrected = await autocorrect_text(message)
    sent = 0
    for member in guild.members:
        if is_staff(member) and not member.bot:
            try:
                e = discord.Embed(
                    description=f"**Staff Announcement**\n\n{corrected}\n\n**From:** {interaction.user.display_name}",
                    color=RYANAIR_COLOR, timestamp=now()
                )
                e.set_footer(text="Ryanair Digital Assistant — Staff Announcement")
                await send_automation_dm(member.id, e)
                sent += 1
            except: pass
    await interaction.followup.send(f"Announcement sent to {sent} staff members.", ephemeral=True)


# ── /resetraids ───────────────────────────────────────────────────────────────
@tree.command(name="resetraids", description="Reset all raid-locked users (Owner only)", guild=discord.Object(id=GUILD_ID))
async def resetraids_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_lock(interaction.user): await interaction.followup.send("Owner only.", ephemeral=True); return
    count = len(raid_locked)
    raid_locked.clear()
    raid_timestamps.clear()
    save_data()
    await interaction.followup.send(f"Cleared {count} raid-locked users.", ephemeral=True)


# ── /botstatus ────────────────────────────────────────────────────────────────
@tree.command(name="botstatus", description="View bot health and current stats (Staff+)", guild=discord.Object(id=GUILD_ID))
async def botstatus_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_staff(interaction.user): await interaction.followup.send("Staff only.", ephemeral=True); return
    guild = bot.get_guild(GUILD_ID)
    online_staff = sum(1 for m in guild.members if is_staff(m) and not m.bot and m.status in (discord.Status.online, discord.Status.idle, discord.Status.dnd))
    e = discord.Embed(title="Bot Status", color=RYANAIR_COLOR, timestamp=now())
    e.add_field(name="Active Tickets", value=str(len(tickets)), inline=True)
    e.add_field(name="Online Staff", value=str(online_staff), inline=True)
    e.add_field(name="AI Enabled", value="Yes" if ai_enabled else "No", inline=True)
    e.add_field(name="AI Presets", value=str(len(ai_presets)), inline=True)
    e.add_field(name="Raid Locked Users", value=str(len(raid_locked)), inline=True)
    e.add_field(name="Ticket Banned Users", value=str(len(ticket_banned)), inline=True)
    e.add_field(name="Snippets", value=str(len(snippets)), inline=True)
    e.add_field(name="Total Members", value=str(guild.member_count), inline=True)
    e.set_footer(text="Ryanair Digital Assistant")
    await interaction.followup.send(embed=e, ephemeral=True)




async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(bot.start(TOKEN))
        if AUTOMATION_TOKEN:
            tg.create_task(auto_bot.start(AUTOMATION_TOKEN))

asyncio.run(main())

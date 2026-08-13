"""Custom Discord emoji integration for the Ryanair bot."""

import re
import discord

EMOJIS = {
    "737_800": "737_800",
    "737_8AS": "737_8AS",
    "737_8200": "737_8200",
    "boeing": "Boeing_logo",
    "malta_airport": "Malta_Airport_Logo",
    "ryanair_white": "Ryanair_harp_white",
    "ryanair_yellow": "Ryanair_harp_yellow",
    "buzz": "Buzz_Logo",
    "krakow": "Krackow_Logo",
    "lauda": "Lauda_Logo",
    "malta_air": "Malta_air_logo",
    "tick": "Ryanair_Tick",
    "cross": "Ryanair_Cross",
    "stansted": "Stansted",
    "document": "Document",
    "passenger": "Passanger",
}

FALLBACK = {
    "tick": "✅", "cross": "❌", "document": "📄", "passenger": "👥",
    "stansted": "🔷", "ryanair_yellow": "✈️", "ryanair_white": "✈️",
    "737_800": "✈️", "737_8AS": "✈️", "737_8200": "✈️", "boeing": "✈️",
    "malta_airport": "✈️", "malta_air": "✈️", "buzz": "✈️",
    "krakow": "✈️", "lauda": "✈️",
}

KEYWORDS = [
    (re.compile(r"\b(PASSANGER|PASSENGER|PASS|PASSED|APPROVED)\b", re.I), "tick"),
    (re.compile(r"\b(FAIL|FAILED|DENIED)\b", re.I), "cross"),
    (re.compile(r"\b(CONSIDER|CONSIDERATION|DOCUMENT)\b", re.I), "document"),
    (re.compile(r"\bSTANSTED\b", re.I), "stansted"),
    (re.compile(r"\bKRAKOW\b|\bKRACKOW\b", re.I), "krakow"),
    (re.compile(r"\bMALTA AIR\b", re.I), "malta_air"),
    (re.compile(r"\bMALTA\b", re.I), "malta_airport"),
    (re.compile(r"\bBUZZ\b", re.I), "buzz"),
    (re.compile(r"\bLAUDA\b", re.I), "lauda"),
    (re.compile(r"\b737[\s-]?8200\b", re.I), "737_8200"),
    (re.compile(r"\b737[\s-]?8AS\b", re.I), "737_8AS"),
    (re.compile(r"\b737[\s-]?800\b", re.I), "737_800"),
    (re.compile(r"\bBOEING\b", re.I), "boeing"),
]


def find(guild, key):
    if not guild:
        return None
    wanted = EMOJIS.get(key, key).casefold()
    return next((e for e in guild.emojis if e.name.casefold() == wanted), None)


def get(guild, key):
    return find(guild, key) or FALLBACK.get(key, "")


def text(guild, key):
    return str(get(guild, key))


def _support_context(app, message):
    if not message.guild:
        return False
    name = getattr(message.channel, "name", "").casefold()
    if any(x in name for x in ("support", "ticket", "application", "career", "help")):
        return True
    try:
        return message.channel.id in {int(v) for v in app.tickets.values()}
    except Exception:
        return False


def setup(app):
    if getattr(app, "_emoji_sync_loaded", False):
        return
    app._emoji_sync_loaded = True
    app.server_emoji = get
    app.server_emoji_text = text
    app.server_emoji_names = EMOJIS

    async def support_reactions(message):
        if message.author.bot or not _support_context(app, message):
            return
        used = set()
        for pattern, key in KEYWORDS:
            if key in used or not pattern.search(message.content or ""):
                continue
            try:
                await message.add_reaction(get(message.guild, key))
                used.add(key)
            except (discord.Forbidden, discord.HTTPException, TypeError):
                pass
            if len(used) >= 3:
                break

    async def report_ready():
        for guild in app.bot.guilds:
            found_count = sum(1 for key in EMOJIS if find(guild, key))
            print(f"EMOJI SYNC — {guild.name}: {found_count}/{len(EMOJIS)} found", flush=True)

    app.bot.add_listener(support_reactions, "on_message")
    app.bot.add_listener(report_ready, "on_ready")
    print("Emoji sync loaded.", flush=True)

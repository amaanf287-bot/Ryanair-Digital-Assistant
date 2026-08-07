import discord

import music_system

RYANAIR_BLUE = 0x073590
RYANAIR_YELLOW = 0xF1C933


def _ryanair_rules_embed():
    embed = discord.Embed(
        title="🎵 Ryanair Music — Rules & Access",
        description=(
            f"{music_system.MUSIC_RULES}\n\n"
            "Press **I Accept the Music Rules** below to unlock Ryanair Music."
        ),
        color=RYANAIR_BLUE,
    )
    embed.add_field(
        name="🛡️ Music Safety",
        value=(
            "Every requested track is checked before playback. "
            "Tracks that cannot be verified are blocked."
        ),
        inline=False,
    )
    embed.set_footer(text="Ryanair Digital Assistant • Ryanair Music")
    return embed


def _ryanair_panel_embed(message: discord.Message, manager):
    scanner = (
        "**Online** — strict verification enabled"
        if manager.groq_client
        else "**Unavailable** — unverified tracks will be blocked"
    )
    embed = discord.Embed(
        title="🎵 Ryanair Music Player",
        description=(
            f"Server: **{message.guild.name}**\n"
            f"Voice channel: **{message.author.voice.channel.name}**\n\n"
            "Use the controls below to search for and control music. "
            "The player will only accept tracks that pass the safety check."
        ),
        color=RYANAIR_BLUE,
    )
    embed.add_field(name="🛡️ AI Safety Scanner", value=scanner, inline=False)
    embed.add_field(
        name="Access",
        value="Your music-rules acceptance is active for this account.",
        inline=False,
    )
    embed.set_footer(text="Ryanair Digital Assistant • Ryanair Music")
    return embed


def _commands_embed():
    embed = discord.Embed(
        title="⌨️ Ryanair Text Commands",
        description="These commands use `!` and do not consume slash-command slots.",
        color=RYANAIR_BLUE,
    )
    embed.add_field(
        name="🎵 Ryanair Music",
        value=(
            "`!acceptmusicrules` — read and accept the Ryanair Music rules\n"
            "`!music` — open your private music panel while you are in a voice channel\n"
            "`!commands` — show this text-command list"
        ),
        inline=False,
    )
    embed.add_field(
        name="🛡️ Safety",
        value="Requested songs are checked before playback; unverified tracks are rejected.",
        inline=False,
    )
    embed.set_footer(text="Ryanair Digital Assistant")
    return embed


async def _delete_message(message: discord.Message):
    try:
        await message.delete()
    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
        pass


async def _send_dm_or_notice(message: discord.Message, *, content=None, embed=None, view=None):
    try:
        await message.author.send(content=content, embed=embed, view=view)
        return True
    except discord.Forbidden:
        try:
            await message.channel.send(
                f"{message.author.mention}, I need permission to DM you for this private Ryanair Music panel.",
                delete_after=10,
            )
        except (discord.Forbidden, discord.HTTPException):
            pass
        return False


def setup(bot, manager):
    if getattr(bot, "_ryanair_music_prefix_bridge_loaded", False):
        return
    bot._ryanair_music_prefix_bridge_loaded = True

    # The main bot has a custom on_message handler. Remove the normal prefix
    # registrations from music_system and handle these three commands through a
    # dedicated listener so they work regardless of that handler's control flow.
    for command_name in ("acceptmusicrules", "music", "commands"):
        try:
            bot.remove_command(command_name)
        except Exception:
            pass

    async def ryanair_music_message_listener(message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        content = (message.content or "").strip()
        command = content.split(maxsplit=1)[0].casefold() if content else ""
        if command not in {"!acceptmusicrules", "!music", "!commands"}:
            return

        await _delete_message(message)

        if command == "!acceptmusicrules":
            if manager.has_accepted(message.author.id):
                await _send_dm_or_notice(
                    message,
                    content=(
                        "✅ You have already accepted the Ryanair Music rules. "
                        "Join a voice channel and use `!music` in the server."
                    ),
                )
                return

            await _send_dm_or_notice(
                message,
                embed=_ryanair_rules_embed(),
                view=music_system.AcceptMusicRulesView(manager, message.author.id),
            )
            return

        if command == "!commands":
            await _send_dm_or_notice(message, embed=_commands_embed())
            return

        # !music
        if not manager.has_accepted(message.author.id):
            await _send_dm_or_notice(
                message,
                content=(
                    "❌ Ryanair Music is locked for your account. "
                    "Run `!acceptmusicrules` in the server first."
                ),
            )
            return

        if not isinstance(message.author, discord.Member) or not message.author.voice or not message.author.voice.channel:
            await _send_dm_or_notice(
                message,
                content="❌ Join a voice channel first, then run `!music` again.",
            )
            return

        await _send_dm_or_notice(
            message,
            embed=_ryanair_panel_embed(message, manager),
            view=music_system.MusicPanelView(
                manager,
                message.author.id,
                message.guild.id,
            ),
        )

    bot.add_listener(ryanair_music_message_listener, "on_message")
    print(
        "Ryanair Music prefix bridge loaded: !acceptmusicrules, !music, !commands",
        flush=True,
    )

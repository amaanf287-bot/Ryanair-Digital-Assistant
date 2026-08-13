"""Resolve and route Discord log output to the rebuilt log channels."""

import discord


def _text_channel(guild, name):
    return discord.utils.get(guild.text_channels, name=name)


def resolve(app, guild):
    action = _text_channel(guild, "action-logs")
    moderation = _text_channel(guild, "moderation-logs")
    ticket = _text_channel(guild, "ticket-logs")
    if action:
        app.LOG_CHANNEL_ID = action.id
        app.ACTION_LOG_CHANNEL_ID = action.id
    if moderation:
        app.MODERATION_LOG_CHANNEL_ID = moderation.id
    if ticket:
        app.TICKET_LOG_CHANNEL_ID = ticket.id
    return action, moderation, ticket


def setup(app):
    if getattr(app, "_log_channels_loaded", False):
        return
    app._log_channels_loaded = True
    old_log = app.log_to_channel

    async def log_to_channel(action, detail, user, color=None):
        guild = app.bot.get_guild(app.GUILD_ID)
        if not guild:
            return
        action_ch, mod_ch, ticket_ch = resolve(app, guild)
        text = str(action or "").casefold()
        if "ticket" in text:
            channel = ticket_ch or action_ch
            footer = "Ryanair Digital Assistant — Ticket Log"
        elif any(word in text for word in ("warn", "strike", "timeout", "kick", "ban", "raid", "moderation", "blacklist", "lockdown")):
            channel = mod_ch or action_ch
            footer = "Ryanair Digital Assistant — Moderation Log"
        else:
            channel = action_ch
            footer = "Ryanair Digital Assistant — Action Log"

        if channel is None:
            return await old_log(action, detail, user, app.RYANAIR_BLUE if color is None else color)

        try:
            embed = discord.Embed(
                title=str(action),
                description=str(detail),
                color=app.RYANAIR_BLUE if color is None else color,
                timestamp=app.now(),
            )
            if user is not None:
                embed.set_author(name=getattr(user, "display_name", str(user)))
            embed.set_footer(text=footer)
            app.apply_configured_banner(embed, guild, "logs")
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    app.log_to_channel = log_to_channel

    async def resolve_on_ready():
        guild = app.bot.get_guild(app.GUILD_ID)
        if guild:
            resolve(app, guild)

    app.bot.add_listener(resolve_on_ready, "on_ready")
    print("Log channel routing loaded: action-logs, moderation-logs, ticket-logs.", flush=True)

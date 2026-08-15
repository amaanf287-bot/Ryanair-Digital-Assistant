"""Quality-of-life layer for the Ryanair Digital Assistant.

This module deliberately replaces existing /update and /commands entries rather
than adding new top-level slash commands. It also adds rotating presence and a
small startup health report without changing moderation/ticket behaviour.
"""

import asyncio
import contextlib

import discord
from discord import app_commands


CATEGORY_CHOICES = [
    app_commands.Choice(name="Tickets", value="tickets"),
    app_commands.Choice(name="Moderation", value="moderation"),
    app_commands.Choice(name="Flight", value="flight"),
    app_commands.Choice(name="Announcements", value="announcements"),
    app_commands.Choice(name="AI", value="ai"),
    app_commands.Choice(name="General", value="general"),
    app_commands.Choice(name="All", value="all"),
]


def _brand(embed, app, interaction=None):
    user = getattr(app.bot, "user", None)
    if user:
        with contextlib.suppress(Exception):
            embed.set_author(name="Ryanair Digital Assistant", icon_url=user.display_avatar.url)
    embed.set_footer(text="Ryanair Roblox • Digital Operations")
    if interaction and interaction.guild:
        with contextlib.suppress(Exception):
            if interaction.guild.icon:
                embed.set_thumbnail(url=interaction.guild.icon.url)
    return embed


def _user_level(app, member):
    try:
        return int(app.get_user_level(member))
    except Exception:
        return 5 if app.is_server_owner(member) else 0


def _command_line(*names):
    return " ".join(f"`/{name}`" for name in names)


async def _presence_loop(app):
    await app.bot.wait_until_ready()
    while not app.bot.is_closed():
        guild = app.bot.get_guild(app.GUILD_ID)
        members = guild.member_count if guild else 0
        activities = [
            discord.Activity(type=discord.ActivityType.watching, name="Ryanair Roblox"),
            discord.Activity(type=discord.ActivityType.watching, name=f"{members:,} community members"),
            discord.Activity(type=discord.ActivityType.listening, name="support requests"),
            discord.Game(name="Flights • Careers • Support"),
        ]
        for activity in activities:
            if app.bot.is_closed():
                return
            try:
                await app.bot.change_presence(status=discord.Status.online, activity=activity)
            except Exception as exc:
                print(f"BOT QUALITY PRESENCE WARNING — {type(exc).__name__}: {exc}", flush=True)
            await asyncio.sleep(180)


async def _health_report(app):
    await app.bot.wait_until_ready()
    await asyncio.sleep(5)
    guild = app.bot.get_guild(app.GUILD_ID)
    if not guild:
        print(f"BOT QUALITY HEALTH — configured guild {app.GUILD_ID} is not available to the bot.", flush=True)
        return

    me = guild.me
    missing = []
    if me:
        perms = me.guild_permissions
        required = (
            "manage_channels",
            "manage_roles",
            "manage_messages",
            "moderate_members",
            "view_audit_log",
        )
        missing = [name for name in required if not getattr(perms, name, False)]

    remote_names = set()
    try:
        remote = await app.tree.fetch_commands(guild=discord.Object(id=app.GUILD_ID))
        remote_names = {cmd.name.casefold() for cmd in remote}
    except Exception as exc:
        print(f"BOT QUALITY COMMAND CHECK WARNING — {type(exc).__name__}: {exc}", flush=True)

    latency_ms = round(app.bot.latency * 1000) if app.bot.latency >= 0 else -1
    print(
        "BOT QUALITY HEALTH — "
        f"guild={guild.name!r} ({guild.id}), members={guild.member_count}, "
        f"channels={len(guild.channels)}, roles={len(guild.roles)}, latency={latency_ms}ms, "
        f"/channel={'YES' if 'channel' in remote_names else 'NO'}, "
        f"/massrole={'YES' if 'massrole' in remote_names else 'NO'}, "
        f"missing_permissions={','.join(missing) if missing else 'none'}",
        flush=True,
    )


def setup(app):
    if getattr(app, "_bot_quality_loaded", False):
        return
    app._bot_quality_loaded = True

    guild_obj = discord.Object(id=app.GUILD_ID)

    # Replace stale informational commands without consuming additional
    # top-level Discord command slots.
    app.tree.remove_command("update", guild=guild_obj)
    app.tree.remove_command("commands", guild=guild_obj)

    @app_commands.command(
        name="update",
        description="View the current Ryanair Digital Assistant systems and status",
    )
    async def update_cmd(interaction: discord.Interaction):
        guild = interaction.guild
        members = guild.member_count if guild else 0
        open_tickets = len(getattr(app, "tickets", {}) or {})
        active_flights = len(getattr(app, "active_flights", {}) or {})
        latency = round(app.bot.latency * 1000) if app.bot.latency >= 0 else 0

        embed = discord.Embed(
            title="Ryanair Digital Assistant",
            description=(
                "The community operations bot for support, flights, moderation, "
                "server management and staff tools."
            ),
            color=app.RYANAIR_BLUE,
            timestamp=app.now(),
        )
        embed.add_field(
            name="Live Status",
            value=(
                f"**Latency:** {latency} ms\n"
                f"**Members:** {members:,}\n"
                f"**Open Tickets:** {open_tickets}\n"
                f"**Active Flights:** {active_flights}"
            ),
            inline=True,
        )
        embed.add_field(
            name="Applications",
            value=(
                "Applications are handled on the website. "
                "Use `/apply` or `/application` to be directed to `#website`."
            ),
            inline=True,
        )
        embed.add_field(
            name="Support & Tickets",
            value=(
                "Department-aware ticket access, Digital Assistant handover, ticket notes, "
                "priorities, transfers and weekly staff grammar qualification."
            ),
            inline=False,
        )
        embed.add_field(
            name="Flights",
            value=(
                "Passenger flight creation, staff assignment, departures posts, attendance, "
                "updates, cancellations and flight reports."
            ),
            inline=False,
        )
        embed.add_field(
            name="Moderation & Safety",
            value=(
                "Warnings, timeouts, kicks, bans, anti-raid protection, moderation history, "
                "staff safeguards and approval workflows."
            ),
            inline=False,
        )
        embed.add_field(
            name="Server Operations",
            value=(
                "`/setupserver` • `/forceranklocks` • `/checklocks` • "
                "`/channel annoucments` • `/grammer`"
            ),
            inline=False,
        )
        embed.add_field(
            name="AI & Automation",
            value=(
                "AI assistance, AI ticket mode, presets, Digital Assistant handover and "
                "automated server utilities."
            ),
            inline=False,
        )
        _brand(embed, app, interaction)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="commands",
        description="View the commands available to you by category",
    )
    @app_commands.describe(category="Which category to view")
    @app_commands.choices(category=CATEGORY_CHOICES)
    async def commands_cmd(interaction: discord.Interaction, category: str = "all"):
        if not app.is_level1(interaction.user):
            await interaction.response.send_message(
                "This command is for Ryanair staff members.",
                ephemeral=True,
            )
            return

        level = _user_level(app, interaction.user)
        embeds = []

        def add_embed(title, description, fields):
            embed = discord.Embed(
                title=title,
                description=description,
                color=app.RYANAIR_BLUE,
                timestamp=app.now(),
            )
            for name, value in fields:
                embed.add_field(name=name, value=value, inline=False)
            embed.set_footer(text=f"Ryanair Digital Assistant • Your command level: {level}")
            embeds.append(embed)

        if category in ("tickets", "all"):
            fields = [
                (
                    "Common Ticket Tools",
                    _command_line(
                        "connect", "unconnected", "closerequest", "close", "onhold",
                        "ticketnote", "ticketsummary", "requeststaff", "anonreply",
                        "aideal", "say", "supporttickets",
                    ),
                )
            ]
            if level >= 4:
                fields.append((
                    "Management Ticket Tools",
                    _command_line(
                        "forceopen", "ticketrename", "tickettransfer", "ticketpriority",
                        "ticketban", "ticketunban", "snippetadd", "snippetdelete", "pingstaff",
                    ),
                ))
            if level >= 5:
                fields.append((
                    "Owner Ticket Tools",
                    _command_line("closeall", "ticketchannel", "grammer"),
                ))
            add_embed("Ticket & Support Commands", "Customer support and ticket operations.", fields)

        if category in ("moderation", "all") and level >= 4:
            fields = [(
                "Moderation",
                _command_line(
                    "warn", "warnings", "clearwarnings", "timeout", "untimeout", "kick",
                    "ban", "unban", "softban", "purge", "slowmode", "nick", "role",
                    "roleemoji", "lockdown", "unlockdown", "strike", "modhistory", "warndm",
                    "dm", "embed",
                ),
            )]
            if level >= 5:
                fields.append((
                    "Owner Moderation",
                    _command_line(
                        "clearstrikes", "fire", "modunlock", "logs", "allow", "usernick",
                        "resetraids", "readonly", "blacklist", "unblacklist", "viewblacklist",
                    ),
                ))
            add_embed("Moderation Commands", "Server safety and moderation tools.", fields)

        if category in ("flight", "all") and level >= 4:
            add_embed(
                "Flight Operations Commands",
                "Flight creation, staffing and live operations.",
                [(
                    "Flight Operations",
                    _command_line(
                        "paxflight", "createflight", "shortcut assign", "flightupdate",
                        "flightended", "attended", "assign", "reassign", "report", "assigned",
                        "flightcancel",
                    ),
                )],
            )

        if category in ("announcements", "all") and level >= 4:
            fields = [(
                "Publishing",
                _command_line("announce", "announcechannel", "channelembed", "notifydm", "announcedm", "embed"),
            )]
            if level >= 5:
                fields.append((
                    "Permanent Channel Content",
                    "`/channel annoucments` refreshes Rules, Verify Help, Travel Assistant and Ryanair Help.",
                ))
            add_embed("Announcement Commands", "Formal server publishing tools.", fields)

        if category in ("ai", "all"):
            add_embed(
                "AI & Digital Assistant Commands",
                "AI assistance and ticket automation.",
                [(
                    "AI",
                    _command_line("ai", "aiask", "ai_toggle", "ai_ticket_toggle", "ai_preset_add", "ai_preset_remove", "aideal", "ticketsummary"),
                )],
            )

        if category in ("general", "all"):
            fields = [(
                "General",
                _command_line("update", "commands", "apply", "application", "careers", "info"),
            )]
            if level >= 5:
                fields.append((
                    "Owner Server Tools",
                    "`/setupserver` • `/forceranklocks` • `/checklocks` • `/channel annoucments` • `/grammer`",
                ))
            add_embed("General & Server Commands", "Information and server management.", fields)

        if not embeds:
            embed = discord.Embed(
                title="No Commands Available",
                description="There are no commands in that category for your current access level.",
                color=app.RYANAIR_BLUE,
            )
            embed.set_footer(text=f"Ryanair Digital Assistant • Your command level: {level}")
            embeds = [embed]

        await interaction.response.send_message(embeds=embeds[:10], ephemeral=True)

    app.tree.add_command(update_cmd, guild=guild_obj, override=True)
    app.tree.add_command(commands_cmd, guild=guild_obj, override=True)

    async def on_ready_quality():
        task = getattr(app, "_quality_presence_task", None)
        if task is None or task.done():
            app._quality_presence_task = asyncio.create_task(_presence_loop(app))

        health = getattr(app, "_quality_health_task", None)
        if health is None or health.done():
            app._quality_health_task = asyncio.create_task(_health_report(app))

    app.bot.add_listener(on_ready_quality, "on_ready")

    print(
        "Bot quality layer loaded: polished /update + /commands, rotating presence and startup health checks.",
        flush=True,
    )

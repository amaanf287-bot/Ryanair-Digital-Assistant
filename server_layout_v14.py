"""Ryanair Discord layout V14: authoritative public channel rank locks.

V14 fixes public Information/Bulletin rank locks by replacing each managed
channel's overwrite table with a small authoritative set:
- @everyone: visible/readable, Send Messages OFF;
- bot member: operational access;
- exact publisher/job roles for that channel: Send Messages ON.

Replacing the overwrite table removes stale role-specific allows and avoids
Discord's 100-overwrite limit. No channels are deleted on startup.
"""

import asyncio
import discord
from discord import app_commands
import server_layout_v9 as v9
import server_layout_v12 as v12
import server_layout_v7 as layout
import server_layout_v4 as role_base


PUBLIC_LOCK_CHANNELS = (
    "rules",
    "information",
    "ryanair-help",
    "travel-assistant",
    "announcements",
    "press-releases",
    "development",
    "careers",
    "off-topic-announcements",
    "boosters",
    "departures",
    "community-events",
)


def role_named(guild, name):
    return discord.utils.get(guild.roles, name=name)


def reader_overwrite():
    return discord.PermissionOverwrite(
        view_channel=True,
        read_message_history=True,
        send_messages=False,
        send_messages_in_threads=False,
        create_public_threads=False,
        create_private_threads=False,
        add_reactions=True,
        use_application_commands=True,
    )


def publisher_overwrite():
    return discord.PermissionOverwrite(
        view_channel=True,
        read_message_history=True,
        send_messages=True,
        send_messages_in_threads=True,
        create_public_threads=False,
        create_private_threads=False,
        add_reactions=True,
        use_application_commands=True,
    )


async def fetch_channel(guild, channel_id):
    try:
        return await guild.fetch_channel(channel_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return guild.get_channel(channel_id)


def authoritative_overwrites(app, guild, channel_name):
    publisher_names = set(v12.channel_publishers(app, channel_name))
    found_publishers = []

    overwrites = {
        guild.default_role: reader_overwrite(),
    }

    for name in sorted(publisher_names):
        found = role_named(guild, name)
        if found is None:
            continue
        overwrites[found] = publisher_overwrite()
        found_publishers.append(found)

    if guild.me:
        overwrites[guild.me] = layout.bot_overwrite()

    return overwrites, publisher_names, found_publishers


async def lock_one(app, guild, channel, errors, results):
    name = channel.name.casefold()

    for attempt in range(1, 4):
        overwrites, configured_names, found_publishers = authoritative_overwrites(
            app, guild, name
        )
        try:
            # IMPORTANT: channel.edit(overwrites=...) REPLACES stale channel
            # overwrites instead of adding more role entries on top of them.
            await channel.edit(
                overwrites=overwrites,
                reason="Ryanair V14 authoritative rank lock",
            )

            await asyncio.sleep(0.25)
            fresh = await fetch_channel(guild, channel.id)
            if fresh is None:
                raise RuntimeError("channel could not be refetched")

            everyone = fresh.overwrites_for(guild.default_role)
            if everyone.send_messages is not False:
                raise RuntimeError("@everyone Send Messages is not explicitly OFF")

            allowed = []
            leaks = []
            for target, overwrite in fresh.overwrites.items():
                if isinstance(target, discord.Role):
                    if target == guild.default_role:
                        continue
                    if overwrite.send_messages is True:
                        if target.name in configured_names:
                            allowed.append(target.name)
                        else:
                            leaks.append(target.name)

            if leaks:
                raise RuntimeError("unexpected role send allow: " + ", ".join(leaks[:5]))

            missing = sorted(
                n for n in configured_names if role_named(guild, n) is None
            )
            results[name] = {
                "ok": True,
                "allowed": sorted(allowed),
                "missing": missing,
            }
            print(
                f"V14 LOCK VERIFIED: #{name} everyone_send=False allowed={len(allowed)} stale_allows=0",
                flush=True,
            )
            return True

        except (discord.Forbidden, discord.HTTPException, RuntimeError, TypeError) as exc:
            if attempt >= 3:
                msg = f"{name}: {type(exc).__name__}: {str(exc)[:160]}"
                errors.append(msg)
                results[name] = {"ok": False, "error": msg}
                return False
            await asyncio.sleep(0.7 * attempt)
            refreshed = await fetch_channel(guild, channel.id)
            if refreshed is not None:
                channel = refreshed

    return False


async def enforce_public_rank_locks(app, guild):
    errors = []
    results = {}

    # Fresh lookup by name for every channel. Finish one lock before the next.
    for name in PUBLIC_LOCK_CHANNELS:
        try:
            fresh_channels = await guild.fetch_channels()
        except (discord.Forbidden, discord.HTTPException):
            fresh_channels = list(guild.channels)

        channel = next(
            (
                c
                for c in fresh_channels
                if isinstance(c, discord.TextChannel)
                and c.name.casefold() == name.casefold()
            ),
            None,
        )
        if channel is None:
            results[name] = {"ok": False, "error": "channel not found"}
            continue

        await lock_one(app, guild, channel, errors, results)
        await asyncio.sleep(0.12)

    return errors, results


async def enforce_private_operational_locks(app, guild, errors):
    logs = discord.utils.get(guild.categories, name="Logs")
    if logs:
        directors = v9.director_access(app)
        support = v9.support_access(app)
        await v9.private_category(guild, logs, directors | support, errors)

        by_name = {c.name.casefold(): c for c in guild.text_channels}
        for name, access in (
            ("action-logs", directors),
            ("moderation-logs", directors),
            ("ticket-logs", support),
        ):
            channel = by_name.get(name)
            if channel:
                await layout.set_private_channel(
                    app, channel, guild, access, errors, read_only=True
                )

    tickets = discord.utils.get(guild.categories, name="Support Tickets")
    if tickets:
        await v9.private_category(guild, tickets, v9.support_access(app), errors)
        app.TICKET_CATEGORY_ID = tickets.id


async def repair_all_locks(app, guild):
    errors, results = await enforce_public_rank_locks(app, guild)
    await enforce_private_operational_locks(app, guild, errors)
    layout.resolve_ids(app, guild)
    return errors, results


def setup(app):
    if getattr(app, "_professional_layout_v14_loaded", False):
        return
    app._professional_layout_v14_loaded = True

    # Keep extra role names available to the channel-specific publisher map.
    for level, names in role_base.EXTRA_LEVEL_ROLES.items():
        app.ROLE_LEVEL_NAMES.setdefault(level, set()).update(names)
    app.ALL_STAFF_ROLE_NAMES = set().union(*app.ROLE_LEVEL_NAMES.values())
    app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES = (
        set(app.ROLE_LEVEL_NAMES.get(5, set()))
        | set(app.ROLE_LEVEL_NAMES.get(4, set()))
    )
    app.TICKET_ACCESS_ROLE_NAMES = v9.support_access(app)

    # Make V7/V9 use the V12 per-channel publisher map on any future rebuild.
    layout.public_publishers = v12.channel_publishers

    # Load only V9's clean rebuild command; do not load the old V10/V11/V13
    # startup repair listeners that could overwrite V14 afterwards.
    v9.setup(app)

    previous_build = v9.build_clean_layout

    async def build_clean_layout_v14(app_obj, guild):
        made, errors = await previous_build(app_obj, guild)
        lock_errors, _ = await repair_all_locks(app_obj, guild)
        errors.extend(lock_errors)
        return made, errors

    v9.build_clean_layout = build_clean_layout_v14

    async def on_ready_v14():
        await asyncio.sleep(6)
        guild = app.bot.get_guild(app.GUILD_ID)
        if not guild or not guild.me or not guild.me.guild_permissions.manage_channels:
            return
        errors, results = await repair_all_locks(app, guild)
        ok_count = sum(1 for r in results.values() if r.get("ok"))
        print(
            f"SERVER LAYOUT V14 RANK LOCK REPAIR: verified={ok_count}/{len(PUBLIC_LOCK_CHANNELS)} errors={len(errors)}",
            flush=True,
        )
        if errors:
            print("V14 first issues: " + " | ".join(errors[:8]), flush=True)

    app.bot.add_listener(on_ready_v14, "on_ready")

    guild_obj = discord.Object(id=app.GUILD_ID)
    app.tree.remove_command("forceranklocks", guild=guild_obj)
    app.tree.remove_command("checklocks", guild=guild_obj)

    @app_commands.command(
        name="forceranklocks",
        description="Force and verify Information/Bulletin channel rank locks (Owner only)",
    )
    async def forceranklocks(interaction: discord.Interaction):
        if not app.is_server_owner(interaction.user):
            await interaction.response.send_message(
                "Only the server owner can run `/forceranklocks`.", ephemeral=True
            )
            return
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                "Run this inside the server.", ephemeral=True
            )
            return
        if not guild.me or not guild.me.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "The bot needs **Manage Channels**.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        errors, results = await repair_all_locks(app, guild)
        lines = []
        for name in PUBLIC_LOCK_CHANNELS:
            result = results.get(name, {})
            if result.get("ok"):
                lines.append(
                    f"✅ #{name}: locked | publisher roles={len(result.get('allowed', []))}"
                )
            else:
                lines.append(
                    f"❌ #{name}: {result.get('error', 'not verified')[:100]}"
                )
        if errors:
            lines.append(f"\nPermission issues: {len(errors)}")
        await interaction.followup.send("\n".join(lines)[:1900], ephemeral=True)

    @app_commands.command(
        name="checklocks",
        description="Check Information/Bulletin rank locks (Owner only)",
    )
    async def checklocks(interaction: discord.Interaction):
        if not app.is_server_owner(interaction.user):
            await interaction.response.send_message(
                "Only the server owner can run `/checklocks`.", ephemeral=True
            )
            return
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("Run this inside the server.", ephemeral=True)
            return

        lines = []
        for name in PUBLIC_LOCK_CHANNELS:
            channel = discord.utils.get(guild.text_channels, name=name)
            if not channel:
                lines.append(f"❌ #{name}: missing")
                continue
            everyone_locked = (
                channel.overwrites_for(guild.default_role).send_messages is False
            )
            configured = set(v12.channel_publishers(app, name))
            allowed = []
            leaks = []
            for target, overwrite in channel.overwrites.items():
                if not isinstance(target, discord.Role) or target == guild.default_role:
                    continue
                if overwrite.send_messages is True:
                    if target.name in configured:
                        allowed.append(target.name)
                    else:
                        leaks.append(target.name)
            ok = everyone_locked and not leaks
            lines.append(
                f"{'✅' if ok else '❌'} #{name}: everyone={'OFF' if everyone_locked else 'NOT OFF'} allowed={len(allowed)} leaks={len(leaks)}"
            )

        admin_roles = [
            r.name for r in guild.roles
            if r != guild.default_role and r.permissions.administrator
        ]
        if admin_roles:
            lines.append(
                f"\nAdmin-bypass roles: {len(admin_roles)} (Administrator always bypasses channel locks)"
            )

        await interaction.response.send_message("\n".join(lines)[:1900], ephemeral=True)

    app.tree.add_command(forceranklocks, guild=guild_obj, override=True)
    app.tree.add_command(checklocks, guild=guild_obj, override=True)

    print(
        "Professional server layout V14 loaded: authoritative minimal overwrite rank locks + /forceranklocks.",
        flush=True,
    )

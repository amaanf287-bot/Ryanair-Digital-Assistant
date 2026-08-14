"""Ryanair Discord layout V15: guaranteed category-backed rank locks.

V15 makes the managed Information/Bulletin/community notice locks resilient:
- Information and Bulletin categories explicitly deny @everyone Send Messages;
- each managed channel replaces stale overwrites with @everyone denied + exact
  publisher/job roles allowed + bot access;
- permissions are refetched and verified after every write;
- startup performs two passes;
- a channel-update/create watchdog re-applies the managed lock if another task or
  manual sync later removes it.

No channels are deleted on startup.
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

BASE_LOCK_CATEGORIES = ("Information", "Bulletin")


def role_named(guild, name):
    return discord.utils.get(guild.roles, name=name)


def reader_no_send():
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


def publisher_allow():
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


def category_everyone_lock():
    return discord.PermissionOverwrite(
        view_channel=True,
        read_message_history=True,
        send_messages=False,
        send_messages_in_threads=False,
        create_public_threads=False,
        create_private_threads=False,
    )


async def fetch_channel(guild, channel_id):
    try:
        return await guild.fetch_channel(channel_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return guild.get_channel(channel_id)


def publisher_names(app, channel_name):
    return set(v12.channel_publishers(app, channel_name))


def channel_overwrites(app, guild, channel_name):
    configured = publisher_names(app, channel_name)
    overwrites = {guild.default_role: reader_no_send()}
    found = []

    for name in sorted(configured):
        role = role_named(guild, name)
        if role is None:
            continue
        overwrites[role] = publisher_allow()
        found.append(role)

    if guild.me:
        overwrites[guild.me] = layout.bot_overwrite()

    return overwrites, configured, found


def bot_permission_problem(guild):
    me = guild.me
    if me is None:
        return "Bot member is unavailable in the guild cache."
    perms = me.guild_permissions
    if perms.administrator:
        return None
    missing = []
    if not perms.manage_channels:
        missing.append("Manage Channels")
    if not perms.manage_roles:
        missing.append("Manage Roles")
    if missing:
        return "Bot is missing: " + ", ".join(missing)
    return None


async def lock_base_categories(guild, errors):
    """Put a hard @everyone send deny on Information and Bulletin categories."""
    for category_name in BASE_LOCK_CATEGORIES:
        category = discord.utils.get(guild.categories, name=category_name)
        if category is None:
            errors.append(f"[{category_name}] category not found")
            continue
        try:
            # Preserve unrelated category role overwrites, but force the public base deny.
            overwrites = dict(category.overwrites)
            overwrites[guild.default_role] = category_everyone_lock()
            if guild.me:
                overwrites[guild.me] = layout.bot_overwrite()
            await category.edit(
                overwrites=overwrites,
                reason="Ryanair V15 category-level rank lock base",
            )
            await asyncio.sleep(0.15)
            fresh = await fetch_channel(guild, category.id)
            if fresh is None:
                raise RuntimeError("category could not be refetched")
            if fresh.overwrites_for(guild.default_role).send_messages is not False:
                raise RuntimeError("@everyone Send Messages did not become OFF")
            print(f"V15 CATEGORY LOCK VERIFIED: [{category_name}] everyone_send=False", flush=True)
        except (discord.Forbidden, discord.HTTPException, RuntimeError, TypeError) as exc:
            errors.append(f"[{category_name}] lock failed: {type(exc).__name__}: {str(exc)[:150]}")


async def lock_one_channel(app, guild, channel, errors, results):
    name = channel.name.casefold()
    configured = publisher_names(app, name)

    for attempt in range(1, 4):
        overwrites, configured, found_roles = channel_overwrites(app, guild, name)
        try:
            # Replacement is intentional: remove all stale channel-level role allows.
            await channel.edit(
                overwrites=overwrites,
                reason="Ryanair V15 authoritative per-channel rank lock",
            )
            await asyncio.sleep(0.22)
            fresh = await fetch_channel(guild, channel.id)
            if fresh is None:
                raise RuntimeError("channel could not be refetched")

            default_ow = fresh.overwrites_for(guild.default_role)
            if default_ow.send_messages is not False:
                raise RuntimeError("@everyone Send Messages is not OFF")

            allowed = []
            leaks = []
            for target, overwrite in fresh.overwrites.items():
                if not isinstance(target, discord.Role) or target == guild.default_role:
                    continue
                if overwrite.send_messages is True:
                    if target.name in configured:
                        allowed.append(target.name)
                    else:
                        leaks.append(target.name)

            if leaks:
                raise RuntimeError("stale/unapproved send allow: " + ", ".join(leaks[:5]))

            missing = sorted(name for name in configured if role_named(guild, name) is None)
            results[name] = {
                "ok": True,
                "allowed": sorted(allowed),
                "missing": missing,
            }
            print(
                f"V15 CHANNEL LOCK VERIFIED: #{name} everyone_send=False allowed={len(allowed)} leaks=0",
                flush=True,
            )
            return True

        except (discord.Forbidden, discord.HTTPException, RuntimeError, TypeError) as exc:
            if attempt >= 3:
                message = f"#{name}: {type(exc).__name__}: {str(exc)[:160]}"
                errors.append(message)
                results[name] = {"ok": False, "error": message}
                return False
            await asyncio.sleep(0.65 * attempt)
            refreshed = await fetch_channel(guild, channel.id)
            if refreshed is not None:
                channel = refreshed

    return False


async def enforce_public_rank_locks(app, guild):
    errors = []
    results = {}

    permission_problem = bot_permission_problem(guild)
    if permission_problem:
        errors.append(permission_problem)
        for name in PUBLIC_LOCK_CHANNELS:
            results[name] = {"ok": False, "error": permission_problem}
        return errors, results

    await lock_base_categories(guild, errors)

    for name in PUBLIC_LOCK_CHANNELS:
        try:
            fresh_channels = await guild.fetch_channels()
        except (discord.Forbidden, discord.HTTPException):
            fresh_channels = list(guild.channels)

        channel = next(
            (
                channel
                for channel in fresh_channels
                if isinstance(channel, discord.TextChannel)
                and channel.name.casefold() == name.casefold()
            ),
            None,
        )
        if channel is None:
            results[name] = {"ok": False, "error": "channel not found"}
            errors.append(f"#{name}: channel not found")
            continue

        await lock_one_channel(app, guild, channel, errors, results)
        await asyncio.sleep(0.10)

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
                await layout.set_private_channel(app, channel, guild, access, errors, read_only=True)

    tickets = discord.utils.get(guild.categories, name="Support Tickets")
    if tickets:
        await v9.private_category(guild, tickets, v9.support_access(app), errors)
        app.TICKET_CATEGORY_ID = tickets.id


async def repair_all(app, guild):
    errors, results = await enforce_public_rank_locks(app, guild)
    await enforce_private_operational_locks(app, guild, errors)
    layout.resolve_ids(app, guild)
    return errors, results


def channel_is_compliant(app, guild, channel):
    if not isinstance(channel, discord.TextChannel):
        return True
    name = channel.name.casefold()
    if name not in PUBLIC_LOCK_CHANNELS:
        return True
    if channel.overwrites_for(guild.default_role).send_messages is not False:
        return False
    configured = publisher_names(app, name)
    for target, overwrite in channel.overwrites.items():
        if isinstance(target, discord.Role) and target != guild.default_role:
            if overwrite.send_messages is True and target.name not in configured:
                return False
    return True


def setup(app):
    if getattr(app, "_professional_layout_v15_loaded", False):
        return
    app._professional_layout_v15_loaded = True

    for level, names in role_base.EXTRA_LEVEL_ROLES.items():
        app.ROLE_LEVEL_NAMES.setdefault(level, set()).update(names)
    app.ALL_STAFF_ROLE_NAMES = set().union(*app.ROLE_LEVEL_NAMES.values())
    app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES = (
        set(app.ROLE_LEVEL_NAMES.get(5, set())) | set(app.ROLE_LEVEL_NAMES.get(4, set()))
    )
    app.TICKET_ACCESS_ROLE_NAMES = v9.support_access(app)
    layout.public_publishers = v12.channel_publishers

    # Keep the V9 owner-only clean rebuild command, but no older lock listeners.
    v9.setup(app)

    previous_build = v9.build_clean_layout

    async def build_clean_layout_v15(app_obj, guild):
        made, errors = await previous_build(app_obj, guild)
        lock_errors, _ = await repair_all(app_obj, guild)
        errors.extend(lock_errors)
        return made, errors

    v9.build_clean_layout = build_clean_layout_v15

    async def on_ready_v15():
        guild = app.bot.get_guild(app.GUILD_ID)
        if not guild:
            return
        # Two passes prevent another startup task from undoing the first pass.
        await asyncio.sleep(3)
        errors, results = await repair_all(app, guild)
        await asyncio.sleep(8)
        errors2, results2 = await repair_all(app, guild)
        errors.extend(errors2)
        final_results = results2 or results
        ok_count = sum(1 for value in final_results.values() if value.get("ok"))
        print(
            f"SERVER LAYOUT V15 GUARANTEED LOCKS: verified={ok_count}/{len(PUBLIC_LOCK_CHANNELS)} errors={len(errors)}",
            flush=True,
        )
        if errors:
            print("V15 first issues: " + " | ".join(errors[:10]), flush=True)

    app.bot.add_listener(on_ready_v15, "on_ready")

    # Self-heal if another bot/task/manual category sync changes a managed channel.
    repair_guard = set()

    async def heal_channel(channel):
        if not isinstance(channel, discord.TextChannel):
            return
        if channel.name.casefold() not in PUBLIC_LOCK_CHANNELS:
            return
        if channel.id in repair_guard:
            return
        guild = channel.guild
        if channel_is_compliant(app, guild, channel):
            return
        repair_guard.add(channel.id)
        try:
            await asyncio.sleep(0.6)
            errors = []
            results = {}
            fresh = await fetch_channel(guild, channel.id)
            if isinstance(fresh, discord.TextChannel):
                await lock_one_channel(app, guild, fresh, errors, results)
            if errors:
                print("V15 WATCHDOG ISSUE: " + " | ".join(errors[:3]), flush=True)
        finally:
            repair_guard.discard(channel.id)

    async def on_guild_channel_update_v15(before, after):
        await heal_channel(after)

    async def on_guild_channel_create_v15(channel):
        await heal_channel(channel)

    app.bot.add_listener(on_guild_channel_update_v15, "on_guild_channel_update")
    app.bot.add_listener(on_guild_channel_create_v15, "on_guild_channel_create")

    guild_obj = discord.Object(id=app.GUILD_ID)
    app.tree.remove_command("forceranklocks", guild=guild_obj)
    app.tree.remove_command("checklocks", guild=guild_obj)

    @app_commands.command(
        name="forceranklocks",
        description="Force and verify all managed channel rank locks (Owner only)",
    )
    async def forceranklocks(interaction: discord.Interaction):
        if not app.is_server_owner(interaction.user):
            await interaction.response.send_message("Only the server owner can run `/forceranklocks`.", ephemeral=True)
            return
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("Run this inside the server.", ephemeral=True)
            return

        problem = bot_permission_problem(guild)
        if problem:
            await interaction.response.send_message(
                "❌ Cannot rank-lock channels yet. " + problem + ". Give the bot those server permissions, then run `/forceranklocks` again.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        errors, results = await repair_all(app, guild)
        lines = []
        for name in PUBLIC_LOCK_CHANNELS:
            result = results.get(name, {})
            if result.get("ok"):
                lines.append(f"✅ #{name}: RANK LOCKED | allowed roles={len(result.get('allowed', []))}")
            else:
                lines.append(f"❌ #{name}: {result.get('error', 'not verified')[:95]}")
        if errors:
            lines.append(f"\nErrors: {len(errors)}")
        await interaction.followup.send("\n".join(lines)[:1900], ephemeral=True)

    @app_commands.command(
        name="checklocks",
        description="Check effective managed channel rank locks (Owner only)",
    )
    async def checklocks(interaction: discord.Interaction):
        if not app.is_server_owner(interaction.user):
            await interaction.response.send_message("Only the server owner can run `/checklocks`.", ephemeral=True)
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
            default_locked = channel.overwrites_for(guild.default_role).send_messages is False
            configured = publisher_names(app, name)
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
            status = default_locked and not leaks
            lines.append(
                f"{'✅' if status else '❌'} #{name}: everyone={'OFF' if default_locked else 'NOT OFF'} allowed={len(allowed)} leaks={len(leaks)}"
            )

        admin_roles = [r.name for r in guild.roles if r != guild.default_role and r.permissions.administrator]
        problem = bot_permission_problem(guild)
        if problem:
            lines.append("\nBOT PERMISSION PROBLEM: " + problem)
        if admin_roles:
            lines.append(f"\nAdministrator-bypass roles: {len(admin_roles)}")

        await interaction.response.send_message("\n".join(lines)[:1900], ephemeral=True)

    app.tree.add_command(forceranklocks, guild=guild_obj, override=True)
    app.tree.add_command(checklocks, guild=guild_obj, override=True)

    print(
        "Professional server layout V15 loaded: category-backed authoritative rank locks + watchdog.",
        flush=True,
    )

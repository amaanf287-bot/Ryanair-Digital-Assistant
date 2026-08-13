"""Ryanair professional Discord layout V8.

Public/reference channels are repaired first, including real Announcement/news
channels. Then exact bot-created staff/department channels are removed. Only
channels that need restricted access remain rank-locked: public read-only posting,
Support Tickets, and operational Logs.
"""

import asyncio
import discord
from discord import app_commands
import server_layout_v7 as base
import server_layout_v4 as role_base


MANAGED_STAFF_CHANNELS = {
    "staff-hub", "staff-announcements", "staff-chat", "staff-commands", "staff-resources",
    "talent-pool", "trainee-hub", "training-information", "recruitment-updates", "recruitment-training",
    "management", "management-chat", "staffing", "operations-planning",
    "directors", "director-chat", "director-reports", "approvals",
    "executive", "executive-chat", "executive-decisions", "confidential",
    "flight-operations", "flight-dispatch", "crew-assignments", "flight-reports",
    "cabin-operations", "cabin-crew-chat", "training-and-standards",
    "ground-operations", "airport-operations", "base-operations",
    "customer-support", "support-team", "ticket-management", "application-reviews",
    "people-recruitment", "human-resources", "recruitment-team", "training-team",
    "development-team", "bot-development", "bug-reports",
}

LEGACY_STAFF_CATEGORIES = {
    "Staff Hub", "Recruitment & Training", "Management", "Directors", "Executive",
    "Flight Operations", "Cabin Operations", "Ground & Airport Operations",
    "Customer Support", "People & Recruitment", "Development Team",
}


def role(guild, name):
    return discord.utils.get(guild.roles, name=name)


def support_access(app):
    return base.access_map(app)["customer-support"]


def director_access(app):
    return base.director_plus(app)


async def private_category(guild, category, names, errors):
    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    if guild.me:
        overwrites[guild.me] = base.bot_overwrite()
    for name in sorted(set(names)):
        r = role(guild, name)
        if r:
            overwrites[r] = discord.PermissionOverwrite(view_channel=True)
    await base.apply_overwrites(category, overwrites, errors)


async def configure_logs(app, guild, made, errors):
    logs = await base.ensure_category(guild, "Logs", made, errors)
    if not logs:
        return
    directors = director_access(app)
    support = support_access(app)
    await private_category(guild, logs, directors | support, errors)

    for name, access in (
        ("action-logs", directors),
        ("moderation-logs", directors),
        ("ticket-logs", support),
    ):
        channel = await base.ensure_text(guild, logs, name, None, made, errors, wants_news=False)
        if channel:
            await base.set_private_channel(app, channel, guild, access, errors, read_only=True)


async def configure_tickets(app, guild, made, errors):
    tickets = await base.ensure_category(guild, "Support Tickets", made, errors)
    if not tickets:
        return
    await private_category(guild, tickets, support_access(app), errors)
    app.TICKET_CATEGORY_ID = tickets.id


async def remove_managed_staff_channels(guild, deleted, errors):
    fresh = await base.fetch_channels(guild)
    for channel in list(fresh):
        if isinstance(channel, discord.CategoryChannel):
            continue
        name = channel.name.casefold()
        if name not in MANAGED_STAFF_CHANNELS:
            continue
        try:
            await channel.delete(reason="Remove bot-created staff channel by server owner request")
            deleted.append(channel.name)
            await asyncio.sleep(0.06)
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"delete {channel.name}: {str(exc)[:100]}")


async def remove_empty_legacy_categories(guild, deleted, errors):
    fresh = await base.fetch_channels(guild)
    for category in [c for c in fresh if isinstance(c, discord.CategoryChannel)]:
        if category.name not in LEGACY_STAFF_CATEGORIES:
            continue
        children = [c for c in fresh if not isinstance(c, discord.CategoryChannel) and getattr(c, "category_id", None) == category.id]
        if children:
            continue
        try:
            await category.delete(reason="Remove empty bot-created staff category by server owner request")
            deleted.append(f"[{category.name}]")
            await asyncio.sleep(0.06)
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"delete {category.name}: {str(exc)[:100]}")


async def repair(app, guild):
    made, deleted, errors = [], [], []

    # FIRST: reference/public layout and Announcement channels.
    await base.build_public(app, guild, made, errors)

    # Keep only required operational private areas.
    await configure_logs(app, guild, made, errors)
    await configure_tickets(app, guild, made, errors)

    # THEN remove exact bot-created staff/department clutter.
    await remove_managed_staff_channels(guild, deleted, errors)
    await remove_empty_legacy_categories(guild, deleted, errors)

    base.resolve_ids(app, guild)
    return made, deleted, errors


def setup(app):
    if getattr(app, "_professional_layout_v8_loaded", False):
        return
    app._professional_layout_v8_loaded = True

    for level, names in role_base.EXTRA_LEVEL_ROLES.items():
        app.ROLE_LEVEL_NAMES.setdefault(level, set()).update(names)
    app.ALL_STAFF_ROLE_NAMES = set().union(*app.ROLE_LEVEL_NAMES.values())
    app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES = set(app.ROLE_LEVEL_NAMES.get(5, set())) | set(app.ROLE_LEVEL_NAMES.get(4, set()))
    app.TICKET_ACCESS_ROLE_NAMES = support_access(app)

    guild_obj = discord.Object(id=app.GUILD_ID)
    app.tree.remove_command("setupserver", guild=guild_obj)

    @app_commands.command(name="setupserver", description="Sync public Ryanair channels, Announcement types and required rank locks")
    async def setupserver_v8(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not app.is_server_owner(interaction.user):
            await interaction.followup.send("Only the server owner can run `/setupserver`.", ephemeral=True)
            return
        guild = interaction.guild
        if not guild or not guild.me or not guild.me.guild_permissions.manage_channels or not guild.me.guild_permissions.manage_roles:
            await interaction.followup.send("The bot needs **Manage Channels** and **Manage Roles**.", ephemeral=True)
            return

        made, deleted, errors = await repair(app, guild)
        megaphone_errors = [e for e in errors if "megaphone" in e]
        await interaction.followup.send(
            f"V8 sync complete. Public/new items: **{len(made)}**. Staff items removed: **{len(deleted)}**. "
            f"Issues: **{len(errors)}**. Announcement conversion issues: **{len(megaphone_errors)}**. "
            "Only required posting locks, Logs and Support Tickets remain restricted.",
            ephemeral=True,
        )

    app.tree.add_command(setupserver_v8, guild=guild_obj, override=True)

    async def on_ready_v8():
        await asyncio.sleep(5)
        guild = app.bot.get_guild(app.GUILD_ID)
        if not guild or not guild.me or not guild.me.guild_permissions.manage_channels:
            return
        made, deleted, errors = await repair(app, guild)
        print(f"SERVER LAYOUT V8: made={len(made)} deleted={len(deleted)} errors={len(errors)}", flush=True)

    app.bot.add_listener(on_ready_v8, "on_ready")
    print("Professional server layout V8 loaded: public first, Announcement channels, no bot-created Staff Hub clutter.", flush=True)

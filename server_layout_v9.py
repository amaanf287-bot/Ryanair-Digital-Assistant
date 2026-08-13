"""Ryanair Discord layout V9: explicit clean rebuild.

V9 does NOT wipe channels on startup. The owner must explicitly run
/setupserver confirm:true. That command removes the existing channel/category
structure, clears stale ticket runtime state, then rebuilds only:
- reference-style public categories/channels,
- real Announcement/news channels where supported,
- private operational Logs,
- private Support Tickets.

No Staff Hub, management, executive, or department staff channels are created.
"""

import asyncio
import discord
from discord import app_commands
import server_layout_v7 as layout
import server_layout_v4 as role_base


def role(guild, name):
    return discord.utils.get(guild.roles, name=name)


def support_access(app):
    return layout.access_map(app)["customer-support"]


def director_access(app):
    return layout.director_plus(app)


async def private_category(guild, category, names, errors):
    overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    if guild.me:
        overwrites[guild.me] = layout.bot_overwrite()
    for name in sorted(set(names)):
        found = role(guild, name)
        if found:
            overwrites[found] = discord.PermissionOverwrite(view_channel=True)
    await layout.apply_overwrites(category, overwrites, errors)


async def configure_logs(app, guild, made, errors):
    logs = await layout.ensure_category(guild, "Logs", made, errors)
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
        channel = await layout.ensure_text(
            guild, logs, name, None, made, errors, wants_news=False
        )
        if channel:
            await layout.set_private_channel(
                app, channel, guild, access, errors, read_only=True
            )


async def configure_tickets(app, guild, made, errors):
    tickets = await layout.ensure_category(guild, "Support Tickets", made, errors)
    if not tickets:
        return
    access = support_access(app)
    await private_category(guild, tickets, access, errors)
    app.TICKET_CATEGORY_ID = tickets.id


def clear_ticket_runtime(app):
    for attr in (
        "tickets",
        "connected_staff",
        "ticket_ai_active",
        "ticket_ai_history",
        "last_activity",
    ):
        value = getattr(app, attr, None)
        if hasattr(value, "clear"):
            value.clear()
    try:
        app.save_data()
    except Exception:
        pass


async def delete_all_channels(guild, invoking_channel_id, deleted, errors):
    """Delete every guild channel/category; invoking text channel is deleted last."""
    try:
        fresh = await guild.fetch_channels()
    except (discord.Forbidden, discord.HTTPException):
        fresh = list(guild.channels)

    invoking = next((c for c in fresh if c.id == invoking_channel_id), None)

    # Delete every non-category channel except the command channel first.
    for channel in list(fresh):
        if isinstance(channel, discord.CategoryChannel) or channel.id == invoking_channel_id:
            continue
        try:
            await channel.delete(reason="Owner requested clean Ryanair server rebuild V9")
            deleted.append(channel.name)
            await asyncio.sleep(0.08)
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"delete {channel.name}: {str(exc)[:110]}")

    # Delete all categories. Discord uncategorises the invoking channel if needed.
    try:
        fresh = await guild.fetch_channels()
    except (discord.Forbidden, discord.HTTPException):
        fresh = list(guild.channels)
    for category in [c for c in fresh if isinstance(c, discord.CategoryChannel)]:
        try:
            await category.delete(reason="Owner requested clean Ryanair server rebuild V9")
            deleted.append(f"[{category.name}]")
            await asyncio.sleep(0.08)
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"delete {category.name}: {str(exc)[:110]}")

    # Delete the command channel last so the interaction has already been acknowledged.
    if invoking:
        try:
            current = guild.get_channel(invoking.id) or invoking
            await current.delete(reason="Owner requested clean Ryanair server rebuild V9")
            deleted.append(invoking.name)
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"delete {invoking.name}: {str(exc)[:110]}")


async def build_clean_layout(app, guild):
    made, errors = [], []

    # Public/reference structure first, including Announcement/megaphone channels.
    await layout.build_public(app, guild, made, errors)

    # Only operational private areas are recreated. No Staff Hub/staff channels.
    await configure_logs(app, guild, made, errors)
    await configure_tickets(app, guild, made, errors)

    layout.resolve_ids(app, guild)
    return made, errors


def setup(app):
    if getattr(app, "_professional_layout_v9_loaded", False):
        return
    app._professional_layout_v9_loaded = True

    for level, names in role_base.EXTRA_LEVEL_ROLES.items():
        app.ROLE_LEVEL_NAMES.setdefault(level, set()).update(names)
    app.ALL_STAFF_ROLE_NAMES = set().union(*app.ROLE_LEVEL_NAMES.values())
    app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES = (
        set(app.ROLE_LEVEL_NAMES.get(5, set()))
        | set(app.ROLE_LEVEL_NAMES.get(4, set()))
    )
    app.TICKET_ACCESS_ROLE_NAMES = support_access(app)

    guild_obj = discord.Object(id=app.GUILD_ID)
    app.tree.remove_command("setupserver", guild=guild_obj)

    @app_commands.command(
        name="setupserver",
        description="Wipe channels then rebuild the clean Ryanair public layout (Owner only)",
    )
    @app_commands.describe(confirm="Must be true: this deletes ALL existing server channels/categories")
    async def setupserver_v9(interaction: discord.Interaction, confirm: bool):
        if not app.is_server_owner(interaction.user):
            await interaction.response.send_message(
                "Only the server owner can run `/setupserver`.", ephemeral=True
            )
            return
        if not confirm:
            await interaction.response.send_message(
                "Nothing changed. Run `/setupserver confirm:true` to perform the clean rebuild.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if not guild or not guild.me or not guild.me.guild_permissions.manage_channels:
            await interaction.response.send_message(
                "The bot needs **Manage Channels** before it can rebuild the server.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        # Send a DM before deleting the channel that contains this interaction.
        try:
            await interaction.user.send(
                "Ryanair clean rebuild V9 started. All existing channels/categories are being removed, then the clean public layout will be recreated."
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        clear_ticket_runtime(app)
        deleted, delete_errors = [], []
        await delete_all_channels(
            guild,
            interaction.channel_id,
            deleted,
            delete_errors,
        )

        # Give Discord a moment to settle before rebuilding from an empty structure.
        await asyncio.sleep(1.0)
        made, build_errors = await build_clean_layout(app, guild)
        errors = delete_errors + build_errors
        megaphone_errors = [e for e in errors if "megaphone" in e]

        summary = (
            "Ryanair V9 clean rebuild finished.\n\n"
            f"Old channels/categories removed: **{len(deleted)}**\n"
            f"New public/operational items created: **{len(made)}**\n"
            f"Issues: **{len(errors)}**\n"
            f"Announcement conversion issues: **{len(megaphone_errors)}**\n\n"
            "No Staff Hub, management, executive or department staff channels were recreated. "
            "Support Tickets and Logs were recreated with rank locks, and runtime channel IDs were refreshed."
        )
        if errors:
            summary += "\n\nFirst issues:\n" + "\n".join(
                f"- {item[:170]}" for item in errors[:8]
            )

        try:
            await interaction.user.send(summary)
        except (discord.Forbidden, discord.HTTPException):
            pass

        # The original interaction channel has been deleted, so followup may no longer exist.
        try:
            await interaction.followup.send(summary, ephemeral=True)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    app.tree.add_command(setupserver_v9, guild=guild_obj, override=True)

    # Startup is intentionally non-destructive. Only reconnect IDs for an existing V9 layout.
    async def on_ready_v9():
        await asyncio.sleep(3)
        guild = app.bot.get_guild(app.GUILD_ID)
        if guild:
            layout.resolve_ids(app, guild)

    app.bot.add_listener(on_ready_v9, "on_ready")
    print(
        "Professional server layout V9 loaded: explicit clean rebuild, no staff-channel recreation.",
        flush=True,
    )

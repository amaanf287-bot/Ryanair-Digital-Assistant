"""Ryanair professional server layout V5.

V5 builds on the recovery-safe V4 layout, adds real Discord Announcement
(megaphone/news) channels matching the reference server, and performs a final
explicit permission pass so every private category/channel is rank-locked.

No channels are deleted by this module.
"""

import asyncio
import discord
from discord import app_commands
import server_layout_v4 as base


# Match the reference screenshots: these use Discord's Announcement/News type.
ANNOUNCEMENT_CHANNELS = {
    "announcements",
    "press-releases",
    "development",
    "careers",
}


async def ensure_text_v5(guild, category_name, name, topic, made, errors):
    """Create/repair a text channel, converting selected channels to Announcement."""
    channel = await base.find_text_anywhere(guild, name)
    wants_news = name.casefold() in ANNOUNCEMENT_CHANNELS

    if channel is None:
        try:
            # Create uncategorised first, just like V4, to avoid stale parent IDs.
            channel = await guild.create_text_channel(
                name,
                topic=topic,
                news=wants_news,
                reason="Ryanair professional layout V5",
            )
            made.append(name)
            await asyncio.sleep(0.20)
        except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
            errors.append(f"{name} create: {type(exc).__name__}: {str(exc)[:140]}")
            return None

    # Existing normal text channels can be converted in place to Announcement.
    if wants_news and channel.type != discord.ChannelType.news:
        try:
            channel = await channel.edit(
                type=discord.ChannelType.news,
                reason="Convert to Ryanair Announcement channel",
            )
            await asyncio.sleep(0.20)
        except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
            errors.append(
                f"{name} announcement conversion: {type(exc).__name__}: {str(exc)[:140]}"
            )

    if topic is not None and getattr(channel, "topic", None) != topic:
        try:
            channel = await channel.edit(topic=topic, reason="Ryanair channel topic sync")
        except (discord.Forbidden, discord.HTTPException, TypeError):
            pass

    await base.move_text_to_category(channel, guild, category_name, errors)
    return channel


async def enforce_rank_locks(app, guild, errors):
    """Explicitly apply final permissions to categories and every child channel."""
    specs = base.build_specs(app)
    directors = base.roles_at_or_above(app, 4)

    for spec in specs:
        category = await base.fresh_category(guild, spec["name"])
        if category is None:
            errors.append(f"{spec['name']}: missing during final rank-lock pass")
            continue

        if spec["mode"] == "private":
            access = spec.get("access", set())
            await base.set_private(category, guild, access, errors=errors)

            # Explicit child locks instead of relying only on inherited permissions.
            fresh = await base.fresh_channels(guild)
            children = [
                ch for ch in fresh
                if getattr(ch, "category_id", None) == category.id
                and isinstance(ch, (discord.TextChannel, discord.VoiceChannel))
            ]
            for child in children:
                if spec["name"] == "Logs" and child.name.casefold() == "ticket-logs":
                    await base.set_private(
                        child,
                        guild,
                        spec.get("ticket_log_access", set()),
                        errors=errors,
                    )
                else:
                    await base.set_private(child, guild, access, errors=errors)

        else:
            # Public channels remain viewable. Read-only/Announcement channels are
            # posting-locked to Directors+ while @everyone can read/react.
            await base.set_public(category, guild, read_only=False, director_names=directors)
            fresh = await base.fresh_channels(guild)
            children = [
                ch for ch in fresh
                if getattr(ch, "category_id", None) == category.id
                and isinstance(ch, (discord.TextChannel, discord.VoiceChannel))
            ]
            readonly_names = {
                cname.casefold()
                for cname, _topic, read_only in spec.get("channels", [])
                if read_only
            }
            for child in children:
                if isinstance(child, discord.TextChannel):
                    read_only = child.name.casefold() in readonly_names
                    await base.set_public(
                        child,
                        guild,
                        read_only=read_only,
                        director_names=directors,
                    )
                else:
                    await base.set_public(child, guild, read_only=False, director_names=directors)


async def repair_layout_v5(app, guild):
    # Patch V4's safe repair path with V5's Announcement-aware creator.
    original_ensure_text = base.ensure_text
    base.ensure_text = ensure_text_v5
    try:
        made, errors = await base.repair_layout(app, guild)
    finally:
        base.ensure_text = original_ensure_text

    # Convert/verify the four megaphone channels again after placement.
    for name in sorted(ANNOUNCEMENT_CHANNELS):
        channel = await base.find_text_anywhere(guild, name)
        if channel and channel.type != discord.ChannelType.news:
            try:
                await channel.edit(
                    type=discord.ChannelType.news,
                    reason="Ryanair V5 announcement type enforcement",
                )
            except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
                errors.append(
                    f"{name} announcement enforce: {type(exc).__name__}: {str(exc)[:140]}"
                )

    # Final explicit pass: private = hidden to @everyone, named ranks granted.
    await enforce_rank_locks(app, guild, errors)
    base.resolve_runtime_channels(app, guild)
    return made, errors


async def run_repair(app, *, notify_owner=True):
    if getattr(app, "_v5_repair_running", False):
        return None
    app._v5_repair_running = True
    try:
        guild = app.bot.get_guild(app.GUILD_ID)
        if not guild or not guild.me:
            return None
        if not guild.me.guild_permissions.manage_channels:
            return None

        made, errors = await repair_layout_v5(app, guild)
        base.resolve_runtime_channels(app, guild)
        print(
            f"SERVER LAYOUT V5 REPAIR: made={len(made)} errors={len(errors)}",
            flush=True,
        )

        if notify_owner and guild.owner and (made or errors):
            text = (
                "Ryanair server layout V5 finished.\n\n"
                f"New/repaired items: **{len(made)}**\n"
                f"Permission/layout issues: **{len(errors)}**\n"
                "Announcement channels enforced: **announcements, press-releases, development, careers**.\n"
                "All private categories/channels received explicit rank locks."
            )
            if errors:
                text += "\n\nFirst issues:\n" + "\n".join(
                    f"- {item[:160]}" for item in errors[:8]
                )
            try:
                await guild.owner.send(text)
            except (discord.Forbidden, discord.HTTPException):
                pass
        return made, errors
    finally:
        app._v5_repair_running = False


def setup(app):
    if getattr(app, "_professional_layout_v5_loaded", False):
        return
    app._professional_layout_v5_loaded = True

    for level, names in base.EXTRA_LEVEL_ROLES.items():
        app.ROLE_LEVEL_NAMES.setdefault(level, set()).update(names)
    app.ALL_STAFF_ROLE_NAMES = set().union(*app.ROLE_LEVEL_NAMES.values())
    app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES = app.ROLE_LEVEL_NAMES[5] | app.ROLE_LEVEL_NAMES[4]
    app.TICKET_ACCESS_ROLE_NAMES = app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES | {
        "Senior Management", "Customer Support Manager", "Customer Support Officer",
        "Customer Support Trainee", "Recruitment Manager", "Recruitment Assessor",
    }

    guild_obj = discord.Object(id=app.GUILD_ID)
    app.tree.remove_command("setupserver", guild=guild_obj)

    @app_commands.command(
        name="setupserver",
        description="Repair Ryanair channels, Announcement types and rank locks (Owner only)",
    )
    async def setupserver_v5(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not app.is_server_owner(interaction.user):
            await interaction.followup.send("Only the server owner can run `/setupserver`.", ephemeral=True)
            return
        guild = interaction.guild
        if not guild or not guild.me:
            await interaction.followup.send("Run this inside the Ryanair server.", ephemeral=True)
            return
        if not guild.me.guild_permissions.manage_channels or not guild.me.guild_permissions.manage_roles:
            await interaction.followup.send(
                "The bot needs **Manage Channels** and **Manage Roles**.",
                ephemeral=True,
            )
            return

        made, errors = await repair_layout_v5(app, guild)
        await interaction.followup.send(
            f"V5 sync complete. New/repaired items: **{len(made)}**. "
            f"Issues: **{len(errors)}**. Announcement types and rank locks were enforced. "
            "No channels were deleted.",
            ephemeral=True,
        )

    app.tree.add_command(setupserver_v5, guild=guild_obj, override=True)

    async def on_ready_v5():
        await asyncio.sleep(5)
        await run_repair(app, notify_owner=True)

    app.bot.add_listener(on_ready_v5, "on_ready")
    print(
        "Professional server layout V5 loaded: Announcement channels + strict rank locks, no deletion.",
        flush=True,
    )

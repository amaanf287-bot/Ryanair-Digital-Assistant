"""Ryanair Discord layout V10: non-destructive permission repair.

V10 keeps the V9 clean layout, but adds a final explicit rank-lock pass for
public read-only/bulletin channels. It never deletes channels on startup.

Public announcement/information channels remain visible to everyone; posting is
explicitly denied to @everyone and granted only to the appropriate rank roles.
Logs and Support Tickets are also re-checked as private rank-locked areas.
"""

import asyncio
import discord
import server_layout_v9 as v9
import server_layout_v7 as layout


POST_LOCK_CHANNELS = {
    "rules",
    "information",
    "announcements",
    "press-releases",
    "development",
    "careers",
    "off-topic-announcements",
    "boosters",
    "departures",
    "community-events",
}


def role_named(guild, name):
    return discord.utils.get(guild.roles, name=name)


def public_read_only_overwrite():
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


async def enforce_public_post_locks(app, guild, errors):
    """Force explicit posting locks on every managed public read-only channel."""
    by_name = {channel.name.casefold(): channel for channel in guild.text_channels}

    for channel_name in sorted(POST_LOCK_CHANNELS):
        channel = by_name.get(channel_name)
        if channel is None:
            continue

        overwrites = {
            guild.default_role: public_read_only_overwrite(),
        }
        if guild.me:
            overwrites[guild.me] = layout.bot_overwrite()

        # Use the channel-specific publisher hierarchy already defined by V7.
        for role_name in sorted(layout.public_publishers(app, channel_name)):
            found = role_named(guild, role_name)
            if found:
                overwrites[found] = publisher_overwrite()

        try:
            await channel.edit(
                overwrites=overwrites,
                reason="Ryanair V10 explicit rank/post lock",
            )
        except TypeError:
            # Compatibility fallback for discord.py variants.
            try:
                await channel.set_permissions(
                    guild.default_role,
                    overwrite=public_read_only_overwrite(),
                    reason="Ryanair V10 @everyone post lock",
                )
                if guild.me:
                    await channel.set_permissions(
                        guild.me,
                        overwrite=layout.bot_overwrite(),
                        reason="Ryanair V10 bot access",
                    )
                for role_name in sorted(layout.public_publishers(app, channel_name)):
                    found = role_named(guild, role_name)
                    if found:
                        await channel.set_permissions(
                            found,
                            overwrite=publisher_overwrite(),
                            reason="Ryanair V10 publisher rank access",
                        )
            except (discord.Forbidden, discord.HTTPException) as exc:
                errors.append(f"{channel_name} lock fallback: {str(exc)[:120]}")
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"{channel_name} lock: {str(exc)[:120]}")


async def enforce_private_operational_locks(app, guild, errors):
    """Re-apply private visibility to Logs and Support Tickets without rebuilding."""
    logs = discord.utils.get(guild.categories, name="Logs")
    if logs:
        await v9.private_category(
            guild,
            logs,
            v9.director_access(app) | v9.support_access(app),
            errors,
        )

        by_name = {channel.name.casefold(): channel for channel in guild.text_channels}
        action = by_name.get("action-logs")
        moderation = by_name.get("moderation-logs")
        ticket = by_name.get("ticket-logs")
        if action:
            await layout.set_private_channel(
                app, action, guild, v9.director_access(app), errors, read_only=True
            )
        if moderation:
            await layout.set_private_channel(
                app, moderation, guild, v9.director_access(app), errors, read_only=True
            )
        if ticket:
            await layout.set_private_channel(
                app, ticket, guild, v9.support_access(app), errors, read_only=True
            )

    tickets = discord.utils.get(guild.categories, name="Support Tickets")
    if tickets:
        await v9.private_category(guild, tickets, v9.support_access(app), errors)
        app.TICKET_CATEGORY_ID = tickets.id


async def repair_rank_locks(app, guild):
    errors = []
    await enforce_public_post_locks(app, guild, errors)
    await enforce_private_operational_locks(app, guild, errors)
    layout.resolve_ids(app, guild)
    return errors


def setup(app):
    if getattr(app, "_professional_layout_v10_loaded", False):
        return
    app._professional_layout_v10_loaded = True

    # Keep V9's explicit owner-only /setupserver clean rebuild available.
    # Patch the V9 builder so any future deliberate rebuild receives the V10
    # permission pass before it reports completion.
    original_build_clean_layout = v9.build_clean_layout

    async def build_clean_layout_v10(app_obj, guild):
        made, errors = await original_build_clean_layout(app_obj, guild)
        errors.extend(await repair_rank_locks(app_obj, guild))
        return made, errors

    v9.build_clean_layout = build_clean_layout_v10
    v9.setup(app)

    async def on_ready_v10():
        await asyncio.sleep(5)
        guild = app.bot.get_guild(app.GUILD_ID)
        if not guild or not guild.me or not guild.me.guild_permissions.manage_channels:
            return
        errors = await repair_rank_locks(app, guild)
        print(
            f"SERVER LAYOUT V10 RANK LOCK REPAIR: errors={len(errors)}",
            flush=True,
        )
        if errors:
            print("V10 first permission issues: " + " | ".join(errors[:5]), flush=True)

    app.bot.add_listener(on_ready_v10, "on_ready")
    print(
        "Professional server layout V10 loaded: explicit bulletin post locks + private operational locks.",
        flush=True,
    )

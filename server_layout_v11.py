"""Ryanair Discord layout V11: verified sequential rank locks.

V11 keeps the existing clean V9/V10 channel layout. It does not wipe channels.
For every managed read-only/public channel it applies explicit Discord permission
overrides with set_permissions(), fetches the channel back from Discord, verifies
@everyone Send Messages is OFF, and retries before moving to the next channel.

Logs and Support Tickets are also re-checked as private rank-locked areas.
"""

import asyncio
import discord
from discord import app_commands
import server_layout_v10 as v10
import server_layout_v9 as v9
import server_layout_v7 as layout


LOCK_CHANNELS = tuple(sorted(v10.POST_LOCK_CHANNELS))


def role_named(guild, name):
    return discord.utils.get(guild.roles, name=name)


def everyone_lock_overwrite():
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


async def refetch_text_channel(guild, channel_id):
    try:
        fresh = await guild.fetch_channel(channel_id)
        if isinstance(fresh, discord.TextChannel):
            return fresh
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass
    cached = guild.get_channel(channel_id)
    return cached if isinstance(cached, discord.TextChannel) else None


async def lock_one_channel(app, guild, channel, errors):
    """Apply, refetch and verify one channel before returning."""
    channel_name = channel.name.casefold()
    publisher_names = set(layout.public_publishers(app, channel_name))

    for attempt in range(1, 4):
        try:
            # Critical public deny first. This is a direct channel override and
            # therefore wins over inherited category Send Messages permissions.
            await channel.set_permissions(
                guild.default_role,
                overwrite=everyone_lock_overwrite(),
                reason="Ryanair V11 verified @everyone post lock",
            )

            if guild.me:
                await channel.set_permissions(
                    guild.me,
                    overwrite=layout.bot_overwrite(),
                    reason="Ryanair V11 bot access",
                )

            found_publishers = 0
            for role_name in sorted(publisher_names):
                found = role_named(guild, role_name)
                if not found:
                    continue
                found_publishers += 1
                await channel.set_permissions(
                    found,
                    overwrite=publisher_overwrite(),
                    reason="Ryanair V11 ranked publisher access",
                )

            # Fetch the authoritative channel object back from Discord before
            # deciding whether this channel is complete.
            await asyncio.sleep(0.20)
            fresh = await refetch_text_channel(guild, channel.id)
            if fresh is None:
                raise RuntimeError("channel could not be refetched for verification")

            everyone = fresh.overwrites_for(guild.default_role)
            if everyone.send_messages is not False:
                raise RuntimeError("@everyone Send Messages is not explicitly OFF")

            # At least one configured publisher should normally exist. This does
            # not fail the @everyone lock if a named role has been removed, but it
            # records the issue so the hierarchy can be corrected.
            if publisher_names and found_publishers == 0:
                errors.append(f"{channel_name}: no configured publisher roles were found")

            print(
                f"V11 LOCK VERIFIED: #{channel_name} @everyone send=False publishers={found_publishers}",
                flush=True,
            )
            return True

        except (discord.Forbidden, discord.HTTPException, RuntimeError) as exc:
            if attempt >= 3:
                errors.append(
                    f"{channel_name} lock failed after 3 attempts: {type(exc).__name__}: {str(exc)[:140]}"
                )
                return False
            await asyncio.sleep(0.60 * attempt)
            refreshed = await refetch_text_channel(guild, channel.id)
            if refreshed is not None:
                channel = refreshed

    return False


async def enforce_verified_public_locks(app, guild, errors):
    """Sequentially lock and verify each channel; never advance early."""
    for name in LOCK_CHANNELS:
        channel = discord.utils.get(guild.text_channels, name=name)
        if channel is None:
            continue
        await lock_one_channel(app, guild, channel, errors)
        await asyncio.sleep(0.15)


async def enforce_private_locks(app, guild, errors):
    # Reuse V10's private operational repair, then verify the category-level
    # @everyone visibility deny exists for both operational areas.
    await v10.enforce_private_operational_locks(app, guild, errors)

    for category_name in ("Logs", "Support Tickets"):
        category = discord.utils.get(guild.categories, name=category_name)
        if category is None:
            continue
        current = category.overwrites_for(guild.default_role)
        if current.view_channel is not False:
            errors.append(f"{category_name}: @everyone View Channel is not explicitly OFF")


async def repair_verified_locks(app, guild):
    errors = []
    await enforce_verified_public_locks(app, guild, errors)
    await enforce_private_locks(app, guild, errors)
    layout.resolve_ids(app, guild)
    return errors


def setup(app):
    if getattr(app, "_professional_layout_v11_loaded", False):
        return
    app._professional_layout_v11_loaded = True

    # Load V10/V9 command/runtime behaviour first.
    v10.setup(app)

    # Wrap future deliberate V9 rebuilds. The existing V10 wrapper creates and
    # locks each channel; V11 then performs authoritative refetch verification.
    previous_build = v9.build_clean_layout

    async def build_clean_layout_v11(app_obj, guild):
        made, errors = await previous_build(app_obj, guild)
        errors.extend(await repair_verified_locks(app_obj, guild))
        return made, errors

    v9.build_clean_layout = build_clean_layout_v11

    async def on_ready_v11():
        # Existing server: non-destructive permission repair only.
        await asyncio.sleep(7)
        guild = app.bot.get_guild(app.GUILD_ID)
        if not guild or not guild.me or not guild.me.guild_permissions.manage_channels:
            return
        errors = await repair_verified_locks(app, guild)
        print(f"SERVER LAYOUT V11 VERIFIED LOCK REPAIR: errors={len(errors)}", flush=True)
        if errors:
            print("V11 first issues: " + " | ".join(errors[:8]), flush=True)

    app.bot.add_listener(on_ready_v11, "on_ready")

    guild_obj = discord.Object(id=app.GUILD_ID)
    app.tree.remove_command("checklocks", guild=guild_obj)

    @app_commands.command(
        name="checklocks",
        description="Check managed Ryanair channel rank/post locks (Owner only)",
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
        for name in LOCK_CHANNELS:
            channel = discord.utils.get(guild.text_channels, name=name)
            if not channel:
                continue
            current = channel.overwrites_for(guild.default_role)
            locked = current.send_messages is False
            publishers = [
                role_name
                for role_name in sorted(layout.public_publishers(app, name))
                if role_named(guild, role_name)
            ]
            lines.append(
                f"{'✅' if locked else '❌'} #{name}: @everyone send={'OFF' if locked else 'NOT OFF'} | publisher roles={len(publishers)}"
            )

        for category_name in ("Logs", "Support Tickets"):
            category = discord.utils.get(guild.categories, name=category_name)
            if category:
                current = category.overwrites_for(guild.default_role)
                hidden = current.view_channel is False
                lines.append(
                    f"{'✅' if hidden else '❌'} [{category_name}]: @everyone view={'OFF' if hidden else 'NOT OFF'}"
                )

        text = "\n".join(lines) or "No managed channels were found."
        await interaction.response.send_message(text[:1900], ephemeral=True)

    app.tree.add_command(checklocks, guild=guild_obj, override=True)

    print(
        "Professional server layout V11 loaded: direct set_permissions + refetch verification + /checklocks.",
        flush=True,
    )

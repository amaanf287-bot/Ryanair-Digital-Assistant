"""Ryanair Discord layout V13: strict per-channel role matrix locks.

V13 fixes a Discord overwrite edge case from V12. Denying Send Messages only on
@everyone is not sufficient when another role has its own channel-level allow.
For each managed public read-only channel V13 therefore writes a strict matrix:
- @everyone: can view/read, cannot send;
- every ordinary guild role: cannot send;
- exact configured publisher/job ranks for that channel: can send;
- bot: full operational access.

Channels remain publicly readable. Logs and Support Tickets remain private.
No channels are deleted or rebuilt by this module on startup.
"""

import asyncio
import discord
from discord import app_commands
import server_layout_v12 as v12
import server_layout_v11 as v11
import server_layout_v10 as v10
import server_layout_v9 as v9
import server_layout_v7 as layout


MANAGED_CHANNELS = tuple(sorted(set(v11.LOCK_CHANNELS) | set(v12.EXTRA_LOCK_CHANNELS)))


def role_named(guild, name):
    return discord.utils.get(guild.roles, name=name)


def everyone_reader_overwrite():
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


def denied_role_overwrite():
    # Leave viewing inherited/public, but explicitly prevent posting.
    return discord.PermissionOverwrite(
        send_messages=False,
        send_messages_in_threads=False,
        create_public_threads=False,
        create_private_threads=False,
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


async def refetch_text(guild, channel_id):
    try:
        fresh = await guild.fetch_channel(channel_id)
        if isinstance(fresh, discord.TextChannel):
            return fresh
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        pass
    cached = guild.get_channel(channel_id)
    return cached if isinstance(cached, discord.TextChannel) else None


def strict_overwrite_map(app, guild, channel_name):
    publisher_names = set(v12.channel_publishers(app, channel_name))
    publisher_roles = {
        r for r in guild.roles
        if r != guild.default_role and r.name in publisher_names
    }

    overwrites = {
        guild.default_role: everyone_reader_overwrite(),
    }

    # Explicitly deny posting for every ordinary role. Publisher roles are
    # replaced with an allow below. Managed integration/bot roles are harmless
    # because the bot member receives its own explicit overwrite afterwards.
    for guild_role in guild.roles:
        if guild_role == guild.default_role:
            continue
        if guild_role in publisher_roles:
            overwrites[guild_role] = publisher_overwrite()
        else:
            overwrites[guild_role] = denied_role_overwrite()

    if guild.me:
        overwrites[guild.me] = layout.bot_overwrite()

    return overwrites, publisher_roles


async def apply_strict_channel_lock(app, guild, channel, errors):
    name = channel.name.casefold()

    for attempt in range(1, 4):
        overwrites, publisher_roles = strict_overwrite_map(app, guild, name)

        # Discord supports at most 100 permission overwrites per channel. If a
        # guild ever grows beyond that, fall back to the smaller direct method
        # rather than failing the whole repair.
        try:
            if len(overwrites) <= 100:
                await channel.edit(
                    overwrites=overwrites,
                    reason="Ryanair V13 strict rank/post matrix",
                )
            else:
                await channel.set_permissions(
                    guild.default_role,
                    overwrite=everyone_reader_overwrite(),
                    reason="Ryanair V13 @everyone post deny",
                )
                for guild_role in guild.roles:
                    if guild_role == guild.default_role:
                        continue
                    overwrite = publisher_overwrite() if guild_role in publisher_roles else denied_role_overwrite()
                    await channel.set_permissions(
                        guild_role,
                        overwrite=overwrite,
                        reason="Ryanair V13 strict role post matrix",
                    )
                if guild.me:
                    await channel.set_permissions(
                        guild.me,
                        overwrite=layout.bot_overwrite(),
                        reason="Ryanair V13 bot access",
                    )

            await asyncio.sleep(0.25)
            fresh = await refetch_text(guild, channel.id)
            if fresh is None:
                raise RuntimeError("could not refetch channel")

            everyone = fresh.overwrites_for(guild.default_role)
            if everyone.send_messages is not False:
                raise RuntimeError("@everyone Send Messages is not OFF")

            # Verify every configured publisher role found in the server has an
            # explicit allow, and every other role has no explicit allow.
            bad_publishers = []
            leaked_roles = []
            for guild_role in guild.roles:
                if guild_role == guild.default_role:
                    continue
                ow = fresh.overwrites_for(guild_role)
                if guild_role in publisher_roles:
                    if ow.send_messages is not True:
                        bad_publishers.append(guild_role.name)
                elif ow.send_messages is True:
                    leaked_roles.append(guild_role.name)

            if bad_publishers:
                raise RuntimeError("publisher allow missing: " + ", ".join(bad_publishers[:4]))
            if leaked_roles:
                raise RuntimeError("unexpected send allow: " + ", ".join(leaked_roles[:4]))

            print(
                f"V13 STRICT LOCK VERIFIED: #{name} publishers={len(publisher_roles)} roles_checked={len(guild.roles)}",
                flush=True,
            )
            return True

        except (discord.Forbidden, discord.HTTPException, RuntimeError, TypeError) as exc:
            if attempt >= 3:
                errors.append(
                    f"{name} strict lock failed: {type(exc).__name__}: {str(exc)[:160]}"
                )
                return False
            await asyncio.sleep(0.7 * attempt)
            refreshed = await refetch_text(guild, channel.id)
            if refreshed:
                channel = refreshed

    return False


async def repair_strict_locks(app, guild):
    errors = []

    # Sequential by design: finish and verify one channel before the next.
    for name in MANAGED_CHANNELS:
        channel = discord.utils.get(guild.text_channels, name=name)
        if not channel:
            continue
        await apply_strict_channel_lock(app, guild, channel, errors)
        await asyncio.sleep(0.12)

    # Preserve V11/V10 private operational locks.
    await v10.enforce_private_operational_locks(app, guild, errors)
    layout.resolve_ids(app, guild)
    return errors


def setup(app):
    if getattr(app, "_professional_layout_v13_loaded", False):
        return
    app._professional_layout_v13_loaded = True

    # Install the V12 publisher map and V11/V10/V9 command chain first.
    v12.setup(app)

    # Future deliberate clean rebuilds also receive the strict matrix before
    # completion. Startup itself remains non-destructive.
    previous_build = v9.build_clean_layout

    async def build_clean_layout_v13(app_obj, guild):
        made, errors = await previous_build(app_obj, guild)
        errors.extend(await repair_strict_locks(app_obj, guild))
        return made, errors

    v9.build_clean_layout = build_clean_layout_v13

    async def on_ready_v13():
        await asyncio.sleep(9)
        guild = app.bot.get_guild(app.GUILD_ID)
        if not guild or not guild.me or not guild.me.guild_permissions.manage_channels:
            return
        errors = await repair_strict_locks(app, guild)
        print(f"SERVER LAYOUT V13 STRICT LOCK REPAIR: errors={len(errors)}", flush=True)
        if errors:
            print("V13 first issues: " + " | ".join(errors[:8]), flush=True)

    app.bot.add_listener(on_ready_v13, "on_ready")

    guild_obj = discord.Object(id=app.GUILD_ID)
    app.tree.remove_command("checklocks", guild=guild_obj)

    @app_commands.command(
        name="checklocks",
        description="Verify strict Ryanair channel role locks (Owner only)",
    )
    async def checklocks_v13(interaction: discord.Interaction):
        if not app.is_server_owner(interaction.user):
            await interaction.response.send_message("Only the server owner can run `/checklocks`.", ephemeral=True)
            return
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message("Run this inside the server.", ephemeral=True)
            return

        lines = []
        for name in MANAGED_CHANNELS:
            channel = discord.utils.get(guild.text_channels, name=name)
            if not channel:
                continue
            publisher_names = set(v12.channel_publishers(app, name))
            allowed = []
            leaked = []
            for guild_role in guild.roles:
                if guild_role == guild.default_role:
                    continue
                send = channel.overwrites_for(guild_role).send_messages
                if send is True:
                    if guild_role.name in publisher_names:
                        allowed.append(guild_role.name)
                    else:
                        leaked.append(guild_role.name)
            everyone_locked = channel.overwrites_for(guild.default_role).send_messages is False
            ok = everyone_locked and not leaked
            lines.append(
                f"{'✅' if ok else '❌'} #{name}: everyone={'OFF' if everyone_locked else 'NOT OFF'} allowed={len(allowed)} leaks={len(leaked)}"
            )

        text = "\n".join(lines) or "No managed channels found."
        await interaction.response.send_message(text[:1900], ephemeral=True)

    app.tree.add_command(checklocks_v13, guild=guild_obj, override=True)

    print(
        "Professional server layout V13 loaded: strict per-channel role matrix + verification.",
        flush=True,
    )

"""Export Discord server structure for layout/reference work.

This exporter intentionally does NOT read or export message contents or member lists.
It captures server structure only: categories, channels, roles and role-based
permission overwrites visible to the bot.
"""

from __future__ import annotations

import io
import json
from datetime import datetime, timezone

import discord
from discord import app_commands


REFERENCE_GUILD_ID = 414176899930259467


def _enabled_permissions(perms: discord.Permissions) -> list[str]:
    return [name for name, enabled in perms if enabled]


def _overwrite_payload(channel) -> list[dict]:
    """Return role-only overwrites; member-specific overwrites are omitted."""
    output = []
    for target, overwrite in channel.overwrites.items():
        if not isinstance(target, discord.Role):
            continue
        allow, deny = overwrite.pair()
        output.append(
            {
                "role_id": target.id,
                "role_name": target.name,
                "allow": _enabled_permissions(allow),
                "deny": _enabled_permissions(deny),
                "allow_value": allow.value,
                "deny_value": deny.value,
            }
        )
    return output


def _channel_payload(channel) -> dict:
    payload = {
        "id": channel.id,
        "name": channel.name,
        "type": str(channel.type),
        "position": channel.position,
        "category_id": getattr(channel, "category_id", None),
        "permissions_synced": getattr(channel, "permissions_synced", False),
        "role_overwrites": _overwrite_payload(channel),
    }

    topic = getattr(channel, "topic", None)
    if topic:
        payload["topic"] = topic

    if hasattr(channel, "nsfw"):
        payload["nsfw"] = bool(channel.nsfw)
    if hasattr(channel, "slowmode_delay"):
        payload["slowmode_delay"] = channel.slowmode_delay
    if hasattr(channel, "bitrate"):
        payload["bitrate"] = channel.bitrate
    if hasattr(channel, "user_limit"):
        payload["user_limit"] = channel.user_limit

    default_auto_archive_duration = getattr(channel, "default_auto_archive_duration", None)
    if default_auto_archive_duration is not None:
        payload["default_auto_archive_duration"] = default_auto_archive_duration

    available_tags = getattr(channel, "available_tags", None)
    if available_tags:
        payload["forum_tags"] = [tag.name for tag in available_tags]

    return payload


def _role_payload(role: discord.Role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "position": role.position,
        "colour_hex": f"#{role.colour.value:06X}",
        "hoist": role.hoist,
        "mentionable": role.mentionable,
        "managed": role.managed,
        "permissions": _enabled_permissions(role.permissions),
        "permissions_value": role.permissions.value,
    }


def build_export(guild: discord.Guild) -> dict:
    categories = []
    for category in sorted(guild.categories, key=lambda item: item.position):
        categories.append(
            {
                "id": category.id,
                "name": category.name,
                "position": category.position,
                "role_overwrites": _overwrite_payload(category),
                "channels": [
                    _channel_payload(channel)
                    for channel in sorted(category.channels, key=lambda item: item.position)
                ],
            }
        )

    uncategorized = [
        _channel_payload(channel)
        for channel in sorted(guild.channels, key=lambda item: item.position)
        if not isinstance(channel, discord.CategoryChannel)
        and getattr(channel, "category_id", None) is None
    ]

    return {
        "export_version": 1,
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "privacy": {
            "messages_exported": False,
            "member_list_exported": False,
            "member_specific_overwrites_exported": False,
        },
        "guild": {
            "id": guild.id,
            "name": guild.name,
            "description": guild.description,
            "owner_id": guild.owner_id,
            "preferred_locale": str(guild.preferred_locale),
            "verification_level": str(guild.verification_level),
            "roles": [
                _role_payload(role)
                for role in sorted(guild.roles, key=lambda item: item.position, reverse=True)
            ],
            "categories": categories,
            "uncategorized_channels": uncategorized,
        },
    }


def _export_file(guild: discord.Guild) -> discord.File:
    payload = build_export(guild)
    raw = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    return discord.File(io.BytesIO(raw), filename=f"discord-server-export-{guild.id}.json")


async def _authorised(app, user: discord.abc.User, guild: discord.Guild) -> bool:
    if user.id == guild.owner_id:
        return True
    try:
        return await app.bot.is_owner(user)
    except Exception:
        return False


async def _sync_reference_guild(app) -> None:
    guild = app.bot.get_guild(REFERENCE_GUILD_ID)
    if guild is None:
        return
    try:
        synced = await app.tree.sync(guild=discord.Object(id=REFERENCE_GUILD_ID))
        print(
            f"Reference server slash sync complete — {len(synced)} commands in {REFERENCE_GUILD_ID}.",
            flush=True,
        )
    except Exception as error:
        print(
            f"REFERENCE SERVER SLASH SYNC FAILED: {type(error).__name__}: {error}",
            flush=True,
        )


def setup(app):
    if getattr(app, "_server_export_loaded", False):
        return
    app._server_export_loaded = True

    guild_obj = discord.Object(id=REFERENCE_GUILD_ID)

    @app_commands.command(
        name="exportserver",
        description="Export this server's channel/category/role structure",
    )
    async def exportserver(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("Use this command inside a server.", ephemeral=True)
            return

        if not await _authorised(app, interaction.user, interaction.guild):
            await interaction.response.send_message(
                "Only this server's owner or the bot owner can export its structure.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        file = _export_file(interaction.guild)
        await interaction.followup.send(
            "Server structure exported. Upload this JSON file back into our ChatGPT conversation. "
            "It contains no message contents or member list.",
            file=file,
            ephemeral=True,
        )

    app.tree.add_command(exportserver, guild=guild_obj, override=True)

    @app.bot.command(name="exportserver")
    async def exportserver_prefix(ctx):
        if ctx.guild is None:
            return
        if not await _authorised(app, ctx.author, ctx.guild):
            return
        try:
            await ctx.author.send(
                "Here is the server structure export. It contains no message contents or member list.",
                file=_export_file(ctx.guild),
            )
            await ctx.reply("Server export sent to your DMs.", mention_author=False, delete_after=10)
        except discord.Forbidden:
            await ctx.reply(
                "I couldn't DM you. Enable DMs from server members and run `!exportserver` again.",
                mention_author=False,
                delete_after=15,
            )

    async def on_ready_export_sync():
        await _sync_reference_guild(app)

    async def on_guild_join_export_sync(guild: discord.Guild):
        if guild.id == REFERENCE_GUILD_ID:
            await _sync_reference_guild(app)

    app.bot.add_listener(on_ready_export_sync, "on_ready")
    app.bot.add_listener(on_guild_join_export_sync, "on_guild_join")

    print(
        f"Reference server exporter loaded for guild {REFERENCE_GUILD_ID}: /exportserver + !exportserver",
        flush=True,
    )

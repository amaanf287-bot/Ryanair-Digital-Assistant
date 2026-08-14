"""Deterministic Discord slash-command repair for the Ryanair guild.

This module patches bot.py's normal slash sync so that the legacy /massrole
command is removed from Discord itself (guild and global scope if present), then
syncs the current guild tree and verifies /channel is registered remotely.
"""

import discord


async def _delete_remote_named(tree, name, *, guild=None):
    deleted = 0
    commands = await tree.fetch_commands(guild=guild)
    for command in commands:
        if command.name.casefold() != name.casefold():
            continue
        try:
            await command.delete()
            deleted += 1
            print(
                f"REMOTE SLASH DELETE: /{command.name} scope={'guild' if guild else 'global'} id={command.id}",
                flush=True,
            )
        except discord.NotFound:
            pass
    return deleted


def setup(app):
    if getattr(app, "_slash_command_repair_loaded", False):
        return
    app._slash_command_repair_loaded = True

    original_sync = app.sync_ryanair_slash_commands
    guild_obj = discord.Object(id=app.GUILD_ID)

    async def repaired_sync_ryanair_slash_commands():
        # Make absolutely sure the old command cannot be re-sent from the local
        # tree, regardless of which earlier module registered it.
        app.tree.remove_command("massrole", guild=guild_obj)
        app.tree.remove_command("massrole")

        # Delete any stale remote copies before the bulk guild sync. This covers
        # both old guild registrations and any historical global registration.
        guild_deleted = await _delete_remote_named(
            app.tree,
            "massrole",
            guild=guild_obj,
        )
        global_deleted = await _delete_remote_named(
            app.tree,
            "massrole",
            guild=None,
        )

        synced = await app.tree.sync(guild=guild_obj)

        # Read Discord's remote state back instead of trusting local state.
        remote_guild = await app.tree.fetch_commands(guild=guild_obj)
        guild_names = {command.name.casefold() for command in remote_guild}
        remote_global = await app.tree.fetch_commands()
        global_names = {command.name.casefold() for command in remote_global}

        problems = []
        if "channel" not in guild_names:
            problems.append("/channel is missing from Discord's guild command list")
        if "massrole" in guild_names:
            problems.append("/massrole still exists as a guild command")
        if "massrole" in global_names:
            problems.append("/massrole still exists as a global command")

        if problems:
            raise RuntimeError("Slash repair verification failed: " + "; ".join(problems))

        synced_names = sorted(command.name for command in synced)
        print(
            "SLASH REPAIR VERIFIED — "
            f"guild_deleted={guild_deleted}, global_deleted={global_deleted}, "
            f"remote_guild_count={len(remote_guild)}, /channel=YES, /massrole=NO",
            flush=True,
        )
        print("Synced slash commands: " + ", ".join(synced_names), flush=True)
        return synced

    app.sync_ryanair_slash_commands = repaired_sync_ryanair_slash_commands

    print(
        "Slash command repair loaded: remote /massrole purge + /channel verification enabled.",
        flush=True,
    )

"""Free one top-level Discord slash-command slot for /channel.

The legacy /massrole command remains in bot.py for source compatibility, but is
removed from the guild command tree before Discord syncs commands. This allows
/channel annoucments to occupy that top-level command slot instead.
"""

import discord


def setup(app):
    if getattr(app, "_command_slot_swap_loaded", False):
        return
    app._command_slot_swap_loaded = True

    guild_obj = discord.Object(id=app.GUILD_ID)
    removed = app.tree.remove_command("massrole", guild=guild_obj)

    print(
        "Command slot swap: /massrole removed from slash tree; slot reserved for /channel."
        if removed
        else "Command slot swap: /massrole was not present in slash tree; /channel can still load.",
        flush=True,
    )

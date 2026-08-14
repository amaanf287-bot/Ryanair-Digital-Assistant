"""Ryanair Discord layout V17: website channel + V16 permissions.

Adds a public read-only #website channel under Information. Everyone can read it;
only the normal senior publishing hierarchy can post the current website/application
link. Existing V16 public rank locks and ticket/grammar behaviour are preserved.
No channels are deleted on startup.
"""

import asyncio
import discord

import server_layout_v16 as v16
import server_layout_v15 as v15
import server_layout_v7 as layout


WEBSITE_TOPIC = "Official Ryanair Roblox community website and application link."


def patch_layout_definition():
    items = list(layout.PUBLIC_LAYOUT.get("Information", []))
    if not any(name == "website" for name, _topic, _ro in items):
        insert_at = 2 if len(items) >= 2 else len(items)
        items.insert(insert_at, ("website", WEBSITE_TOPIC, True))
        layout.PUBLIC_LAYOUT["Information"] = items

    if "website" not in v15.PUBLIC_LOCK_CHANNELS:
        v15.PUBLIC_LOCK_CHANNELS = tuple(list(v15.PUBLIC_LOCK_CHANNELS) + ["website"])


async def ensure_website_channel(app, guild):
    category = discord.utils.get(guild.categories, name="Information")
    if category is None:
        category = await guild.create_category("Information", reason="Ryanair V17 website channel")

    channel = discord.utils.get(guild.text_channels, name="website")
    if channel is None:
        channel = await guild.create_text_channel(
            "website",
            category=category,
            topic=WEBSITE_TOPIC,
            reason="Ryanair V17 website/application channel",
        )
    else:
        changes = {}
        if channel.category_id != category.id:
            changes["category"] = category
        if channel.topic != WEBSITE_TOPIC:
            changes["topic"] = WEBSITE_TOPIC
        if changes:
            channel = await channel.edit(
                reason="Ryanair V17 website channel sync",
                **changes,
            )

    # Same public-read / ranked-posting model as Information/Bulletin channels.
    overwrites, _configured, _found = v15.channel_overwrites(app, guild, "website")
    await channel.edit(
        overwrites=overwrites,
        reason="Ryanair V17 website read-only rank lock",
    )
    return channel


def setup(app):
    if getattr(app, "_professional_layout_v17_loaded", False):
        return
    app._professional_layout_v17_loaded = True

    patch_layout_definition()
    v16.setup(app)

    async def on_ready_v17():
        await asyncio.sleep(2)
        guild = app.bot.get_guild(app.GUILD_ID)
        if not guild or not guild.me or not guild.me.guild_permissions.manage_channels:
            return
        try:
            channel = await ensure_website_channel(app, guild)
            print(
                f"SERVER LAYOUT V17 WEBSITE READY: #{channel.name} ({channel.id})",
                flush=True,
            )
        except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
            print(
                f"SERVER LAYOUT V17 WEBSITE ERROR: {type(exc).__name__}: {exc}",
                flush=True,
            )

    app.bot.add_listener(on_ready_v17, "on_ready")
    print(
        "Professional server layout V17 loaded: public read-only #website added under Information.",
        flush=True,
    )

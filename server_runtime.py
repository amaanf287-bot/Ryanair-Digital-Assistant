"""Load current Ryanair Discord/Roblox community server integrations."""


def setup(app):
    import discord
    import role_sync
    role_sync.setup(app)

    import server_layout_v6

    # Match the reference server's megaphone channels more closely.
    server_layout_v6.ANNOUNCEMENT_CHANNELS.update({
        "announcements",
        "press-releases",
        "development",
        "careers",
        "off-topic-announcements",
    })

    # Public bulletin channels stay visible to everyone, but only Director+
    # ranks can publish. This does not weaken any private Staff Hub locks.
    async def strict_public_permissions(target, guild, read_only=False):
        try:
            await target.set_permissions(
                guild.default_role,
                view_channel=True,
                read_message_history=True,
                send_messages=False if read_only else True,
                add_reactions=True,
                reason="Ryanair public/bulletin access",
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        await server_layout_v6.grant_bot(target, guild)

        if read_only:
            publisher_names = (
                {"Directors"}
                | set(app.ROLE_LEVEL_NAMES.get(4, set()))
                | set(app.ROLE_LEVEL_NAMES.get(5, set()))
            )
            for name in sorted(publisher_names):
                publisher = server_layout_v6.role(guild, name)
                if not publisher:
                    continue
                try:
                    await target.set_permissions(
                        publisher,
                        view_channel=True,
                        read_message_history=True,
                        send_messages=True,
                        send_messages_in_threads=True,
                        add_reactions=True,
                        use_application_commands=True,
                        reason="Ryanair Director+ publisher access",
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass

    server_layout_v6.set_public = strict_public_permissions
    server_layout_v6.setup(app)

    import log_channels
    log_channels.setup(app)

    import emoji_sync
    emoji_sync.setup(app)

    # Non-employment Roblox community role forms; final decisions are human-only.
    import application_commands
    application_commands.setup(app)

    import aideal_toggle
    aideal_toggle.setup(app)

    import server_export
    server_export.setup(app)

    print(
        "Ryanair server sync ready: layout V6 single Staff Hub, strict rank locks, Announcement channels, dedicated logs, emojis, forms, AI handoff and exporter.",
        flush=True,
    )

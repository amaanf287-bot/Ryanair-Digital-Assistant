"""Load current Ryanair Discord/Roblox community server integrations."""


def setup(app):
    import role_sync
    role_sync.setup(app)

    import server_layout_v6
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

    print("Ryanair server sync ready: layout V6 single Staff Hub, Announcement channels, rank locks, roles, logs, emojis, forms, AI handoff and exporter.", flush=True)

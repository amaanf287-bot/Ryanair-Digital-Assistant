"""Load current Ryanair Discord/Roblox community server integrations."""


def setup(app):
    import role_sync
    role_sync.setup(app)

    import emoji_sync
    emoji_sync.setup(app)

    # Non-employment Roblox community role forms; final decisions are human-only.
    import application_commands
    application_commands.setup(app)

    # Per-ticket AI/human handoff toggle.
    import aideal_toggle
    aideal_toggle.setup(app)

    # Reference Discord server structure exporter.
    import server_export
    server_export.setup(app)

    print("Ryanair server sync ready: roles, emojis, community forms, AI handoff and server exporter.", flush=True)

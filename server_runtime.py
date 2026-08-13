"""Load current Ryanair Discord/Roblox community server integrations."""


def setup(app):
    import role_sync
    role_sync.setup(app)

    import server_layout_v9
    server_layout_v9.setup(app)

    import log_channels
    log_channels.setup(app)

    import emoji_sync
    emoji_sync.setup(app)

    import application_commands
    application_commands.setup(app)

    import aideal_toggle
    aideal_toggle.setup(app)

    import server_export
    server_export.setup(app)

    print("Ryanair server sync ready: layout V9 loaded.", flush=True)

"""Load current Ryanair Discord/Roblox community server integrations."""


def setup(app):
    import role_sync
    role_sync.setup(app)

    # Public/reference layout first, no Staff Hub clutter, focused rank locks.
    import server_layout_v8
    server_layout_v8.setup(app)

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
        "Ryanair server sync ready: layout V8 public-first Announcement channels, focused rank locks, Logs, tickets, emojis, forms and AI handoff.",
        flush=True,
    )

"""Load current Ryanair Discord/Roblox community server integrations."""


def setup(app):
    import role_sync
    role_sync.setup(app)

    import emoji_sync
    emoji_sync.setup(app)

    # Non-employment Roblox community role forms; final decisions are human-only.
    import application_commands
    application_commands.setup(app)

    print("Ryanair server sync ready: roles, emojis and community forms.", flush=True)

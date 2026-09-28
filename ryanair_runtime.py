"""Jet2 runtime bootstrap.

Keeps the legacy Jet2-to-Jet2 visible-name migration, then loads the current
server role, emoji and Roblox community integrations.
"""

import discord


LEGACY_ROLE_RENAMES = {
    "jet2 digital assistant": "Jet2 Digital Assistant",
    "jet2 digital assistant": "Jet2 Digital Assistant",
    "head of jet2.rblx": "Jet2 DAC Chief Executive Officer",
    "head of jet2": "Jet2 DAC Chief Executive Officer",
    "head of jet2holidays": "Jet2 UK Chief Executive Officer",
    "head of jet2 holidays": "Jet2 UK Chief Executive Officer",
    "jet2.rblx staff team": "Jet2 Staff Team",
    "jet2.rblx priority": "Jet2 Priority",
    "jet2.rblx club member": "Community Member",
}


def _install_branding_listener(app):
    if getattr(app.bot, "_jet2_branding_listener_loaded", False):
        return
    app.bot._jet2_branding_listener_loaded = True

    async def on_ready_branding():
        for guild in app.bot.guilds:
            for role in list(guild.roles):
                replacement = LEGACY_ROLE_RENAMES.get(role.name.casefold())
                if not replacement or role.managed:
                    continue
                if discord.utils.get(guild.roles, name=replacement):
                    continue
                try:
                    await role.edit(name=replacement, reason="Jet2 server branding migration")
                except (discord.Forbidden, discord.HTTPException):
                    pass

    app.bot.add_listener(on_ready_branding, "on_ready")


def setup(app):
    if getattr(app, "_jet2_runtime_applied", False):
        return
    app._jet2_runtime_applied = True
    _install_branding_listener(app)

    # Current server integration. Community applications are Roblox/Discord
    # volunteer roles and always require an explicit human review decision.
    import server_runtime
    server_runtime.setup(app)

    print("Jet2 runtime applied: branding + current server sync", flush=True)

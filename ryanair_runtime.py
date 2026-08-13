"""Ryanair runtime bootstrap.

Keeps the legacy Jet2-to-Ryanair visible-name migration, then loads the current
server role, emoji and Roblox community integrations.
"""

import discord


LEGACY_ROLE_RENAMES = {
    "jet2.rblx digital assistant": "Ryanair Digital Assistant",
    "jet2 digital assistant": "Ryanair Digital Assistant",
    "head of jet2.rblx": "Ryanair DAC Chief Executive Officer",
    "head of jet2": "Ryanair DAC Chief Executive Officer",
    "head of jet2holidays": "Ryanair UK Chief Executive Officer",
    "head of jet2 holidays": "Ryanair UK Chief Executive Officer",
    "jet2.rblx staff team": "Ryanair Staff Team",
    "jet2.rblx priority": "Ryanair Priority",
    "jet2.rblx club member": "Community Member",
}


def _install_branding_listener(app):
    if getattr(app.bot, "_ryanair_branding_listener_loaded", False):
        return
    app.bot._ryanair_branding_listener_loaded = True

    async def on_ready_branding():
        for guild in app.bot.guilds:
            for role in list(guild.roles):
                replacement = LEGACY_ROLE_RENAMES.get(role.name.casefold())
                if not replacement or role.managed:
                    continue
                if discord.utils.get(guild.roles, name=replacement):
                    continue
                try:
                    await role.edit(name=replacement, reason="Ryanair server branding migration")
                except (discord.Forbidden, discord.HTTPException):
                    pass

    app.bot.add_listener(on_ready_branding, "on_ready")


def setup(app):
    if getattr(app, "_ryanair_runtime_applied", False):
        return
    app._ryanair_runtime_applied = True
    _install_branding_listener(app)

    # Current server integration. Community applications are Roblox/Discord
    # volunteer roles and always require an explicit human review decision.
    import server_runtime
    server_runtime.setup(app)

    print("Ryanair runtime applied: branding + current server sync", flush=True)

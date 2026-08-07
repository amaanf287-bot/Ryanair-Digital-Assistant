import discord


SENIOR_LEVEL4_ROLES = [
    ("Airline Subsidiaries Overseer", 0xF1C933, "executive"),
    ("Head of Airline Operations", 0x073590, "director"),
    ("Head of Flight Operations", 0x0B3B8F, "director"),
    ("Head of Inflight", 0x7C3AED, "director"),
    ("Head of Ground Operations", 0x15803D, "director"),
    ("Head of Airport Operations", 0x0F766E, "director"),
    ("Head of Training", 0x9333EA, "director"),
    ("Head of Engineering", 0x475569, "director"),
    ("Head of Safety & Security", 0xB91C1C, "director"),
    ("Head of Customer Experience", 0x0284C7, "director"),
    ("Head of Corporate Affairs", 0xC026D3, "director"),
    ("Head of Recruitment & People", 0xDB2777, "director"),
    ("Head of Digital Development", 0x2563EB, "director"),
]

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


def _apply_role_extensions(app):
    level4 = app.ROLE_LEVEL_NAMES.setdefault(4, set())
    level4.update(name for name, _, _ in SENIOR_LEVEL4_ROLES)

    existing_targets = {
        spec.get("target")
        for spec in app.ROLE_BLUEPRINTS
        if isinstance(spec, dict)
    }

    if not any(name in existing_targets for name, _, _ in SENIOR_LEVEL4_ROLES):
        insert_at = len(app.ROLE_BLUEPRINTS)
        for index, spec in enumerate(app.ROLE_BLUEPRINTS):
            if isinstance(spec, dict) and spec.get("target") == "━━━━━━━━ DEPARTMENT DIRECTORS ━━━━━━━━":
                insert_at = index
                break

        additions = [app.divider_spec("━━━━━━━━ SENIOR OPERATIONS LEADERSHIP ━━━━━━━━")]
        for name, color, tier in SENIOR_LEVEL4_ROLES:
            permissions = (
                app.EXECUTIVE_PERMISSIONS
                if tier == "executive"
                else app.DIRECTOR_PERMISSIONS
            )
            additions.append(
                app.role_spec(
                    name,
                    set(),
                    color,
                    permissions,
                    hoist=True,
                )
            )
        app.ROLE_BLUEPRINTS[insert_at:insert_at] = additions

    # Rebuild derived role sets so permissions recognise the new hierarchy.
    app.ALL_STAFF_ROLE_NAMES = set().union(*app.ROLE_LEVEL_NAMES.values())
    app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES = (
        app.ROLE_LEVEL_NAMES[5] | app.ROLE_LEVEL_NAMES[4]
    )
    app.TICKET_ACCESS_ROLE_NAMES = app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES | {
        "Customer Support Manager",
        "Customer Support Officer",
    }


def _install_ryanair_branding_listener(app):
    if getattr(app.bot, "_ryanair_branding_listener_loaded", False):
        return
    app.bot._ryanair_branding_listener_loaded = True

    async def ryanair_branding_on_ready():
        for guild in app.bot.guilds:
            for role in list(guild.roles):
                replacement = LEGACY_ROLE_RENAMES.get(role.name.casefold())
                if not replacement or role.managed:
                    continue
                if discord.utils.get(guild.roles, name=replacement):
                    continue
                try:
                    await role.edit(
                        name=replacement,
                        reason="Ryanair-only server branding migration",
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass

    app.bot.add_listener(ryanair_branding_on_ready, "on_ready")


def setup(app):
    if getattr(app, "_ryanair_runtime_applied", False):
        return
    app._ryanair_runtime_applied = True
    _apply_role_extensions(app)
    _install_ryanair_branding_listener(app)
    print(
        "Ryanair runtime applied: senior roles + Ryanair-only visible branding",
        flush=True,
    )

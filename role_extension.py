"""Additional senior Ryanair Group roles loaded by launcher.py.

Kept separate from bot.py so the existing command implementation remains stable.
/setupserver will create/order these roles with the rest of the hierarchy.
"""


def setup(app):
    new_role_names = {
        "Airline Subsidiaries Overseer",
        "Head of Airline Operations",
        "Head of Flight Operations",
        "Head of Inflight",
        "Head of Ground Operations",
        "Head of Airport Operations",
        "Head of Training",
        "Head of Engineering",
        "Head of Safety & Security",
        "Head of Customer Experience",
        "Head of Corporate Affairs",
        "Head of Recruitment & People",
        "Head of Digital Development",
    }

    # Level 4: same command-access tier as directors/executives.
    app.ROLE_LEVEL_NAMES.setdefault(4, set()).update(new_role_names)

    senior_operations_blueprints = [
        app.divider_spec("━━━━━━━━ SENIOR OPERATIONS LEADERSHIP ━━━━━━━━"),
        app.role_spec(
            "Airline Subsidiaries Overseer",
            {"Airline Subsidiary Overseer", "Subsidiaries Overseer"},
            app.RYANAIR_YELLOW,
            app.EXECUTIVE_PERMISSIONS,
            hoist=True,
        ),
        app.role_spec(
            "Head of Airline Operations",
            {"Head Of Airline Operations"},
            app.RYANAIR_BLUE,
            app.DIRECTOR_PERMISSIONS,
            hoist=True,
        ),
        app.role_spec(
            "Head of Flight Operations",
            {"Head Of Flight Operations", "Head of Flight Deck"},
            0x0B3B8F,
            app.DIRECTOR_PERMISSIONS,
            hoist=True,
        ),
        app.role_spec(
            "Head of Inflight",
            {"Head Of Inflight", "Head of Cabin Operations", "Head of Cabin Services"},
            0x7C3AED,
            app.DIRECTOR_PERMISSIONS,
            hoist=True,
        ),
        app.role_spec(
            "Head of Ground Operations",
            {"Head Of Ground Operations", "Head of Ground Ops"},
            0x15803D,
            app.DIRECTOR_PERMISSIONS,
            hoist=True,
        ),
        app.role_spec(
            "Head of Airport Operations",
            {"Head Of Airport Operations", "Head of Airport Ops"},
            0x0F766E,
            app.DIRECTOR_PERMISSIONS,
            hoist=True,
        ),
        app.role_spec(
            "Head of Training",
            {"Head Of Training"},
            0x9333EA,
            app.DIRECTOR_PERMISSIONS,
            hoist=True,
        ),
        app.role_spec(
            "Head of Engineering",
            {"Head Of Engineering"},
            0x475569,
            app.DIRECTOR_PERMISSIONS,
            hoist=True,
        ),
        app.role_spec(
            "Head of Safety & Security",
            {"Head Of Safety And Security", "Head of Safety and Security"},
            0xB91C1C,
            app.DIRECTOR_PERMISSIONS,
            hoist=True,
        ),
        app.role_spec(
            "Head of Customer Experience",
            {"Head Of Customer Experience"},
            0x0284C7,
            app.DIRECTOR_PERMISSIONS,
            hoist=True,
        ),
        app.role_spec(
            "Head of Corporate Affairs",
            {"Head Of Corporate Affairs"},
            0xC026D3,
            app.DIRECTOR_PERMISSIONS,
            hoist=True,
        ),
        app.role_spec(
            "Head of Recruitment & People",
            {"Head Of Recruitment And People", "Head of Recruitment and People"},
            0xDB2777,
            app.DIRECTOR_PERMISSIONS,
            hoist=True,
        ),
        app.role_spec(
            "Head of Digital Development",
            {"Head Of Digital Development", "Head of Development"},
            app.RYANAIR_LIGHT_BLUE,
            app.DIRECTOR_PERMISSIONS,
            hoist=True,
        ),
    ]

    # Insert immediately before the existing Department Directors divider.
    existing_targets = {spec.get("target") for spec in app.ROLE_BLUEPRINTS}
    to_insert = [
        spec for spec in senior_operations_blueprints
        if spec.get("target") not in existing_targets
    ]

    if to_insert:
        director_divider = "━━━━━━━━ DEPARTMENT DIRECTORS ━━━━━━━━"
        insert_at = next(
            (
                i
                for i, spec in enumerate(app.ROLE_BLUEPRINTS)
                if spec.get("target") == director_divider
            ),
            len(app.ROLE_BLUEPRINTS),
        )
        app.ROLE_BLUEPRINTS[insert_at:insert_at] = to_insert

    # Rebuild derived permission-role sets after extending Level 4.
    app.ALL_STAFF_ROLE_NAMES = set().union(*app.ROLE_LEVEL_NAMES.values())
    app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES = (
        app.ROLE_LEVEL_NAMES.get(5, set()) | app.ROLE_LEVEL_NAMES.get(4, set())
    )
    app.TICKET_ACCESS_ROLE_NAMES = app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES | {
        "Customer Support Manager",
        "Customer Support Officer",
    }

    print(
        f"Role extension ready: {len(new_role_names)} senior leadership roles loaded.",
        flush=True,
    )

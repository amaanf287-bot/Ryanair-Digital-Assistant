"""Ryanair role hierarchy override used by /setupserver."""

LEVELS = {
    5: {"Chairman & Group CEO", "Vice Chairman", "Executive Access"},
    4: {"Group Chief Operating Officer", "Ryanair DAC Chief Executive Officer", "Ryanair UK Chief Executive Officer",
        "Buzz Chief Executive Officer", "Malta Air Chief Executive Officer", "Lauda Europe Chief Executive Officer",
        "Executive Board", "Director of Operations", "Director of Inflight", "Director of Ground & Airport Operations",
        "Director of People & Recruitment", "Director of Digital Development"},
    3: {"Senior Management", "Base Manager", "Station Manager", "Inflight Manager", "Ground & Airport Operations Manager",
        "Customer Support Manager", "Recruitment Manager", "Training Manager", "Development Manager",
        "Senior Cabin Crew", "Ground Operations Supervisor", "Recruitment Assessor"},
    2: {"Captain", "First Officer", "Cadet Pilot", "Cabin Crew", "Flight Operations Dispatcher", "Ground Operations Agent",
        "Passenger Service Agent", "Gate Agent", "Ramp Agent", "Aircraft Engineer", "Aviation Security Officer",
        "Customer Support Officer", "Recruitment Officer", "Developer", "Events Officer", "Ryanair Staff Team"},
    1: {"Recruitment Talent Pool"},
}

SECTIONS = [
    ("━━━━━━━━ EXECUTIVE LEADERSHIP ━━━━━━━━", [
        ("Chairman & Group CEO", 0xF1C933, "owner", True, {"Group Chief Executive Officer"}),
        ("Vice Chairman", 0xD4AF37, "owner", True, set()),
        ("Group Chief Operating Officer", 0x073590, "executive", True, {"Chief Operating Officer"}),
        ("Ryanair DAC Chief Executive Officer", 0x073590, "executive", True, {"Head of Jet2.rblx", "Head of Jet2"}),
        ("Ryanair UK Chief Executive Officer", 0x2563EB, "executive", True, {"Head of Jet2holidays", "Head of Jet2 Holidays"}),
        ("Buzz Chief Executive Officer", 0xF2C300, "executive", True, set()),
        ("Malta Air Chief Executive Officer", 0xD71920, "executive", True, set()),
        ("Lauda Europe Chief Executive Officer", 0xE31E24, "executive", True, set()),
        ("Executive Board", 0x082B73, "executive", True, {"Executive Management Team", "Group Chief Financial Officer", "Group Chief People Officer"}),
        ("Executive Access", 0x031B4E, "owner", True, {"🔒"}),
    ]),
    ("━━━━━━━━ RYANAIR GROUP AIRLINES ━━━━━━━━", [
        ("Ryanair DAC", 0x073590, "tag", True, set()), ("Ryanair UK", 0x2563EB, "tag", True, set()),
        ("Buzz", 0xF2C300, "tag", True, set()), ("Malta Air", 0xD71920, "tag", True, set()), ("Lauda Europe", 0xE31E24, "tag", True, set()),
    ]),
    ("━━━━━━━━ DIRECTORS ━━━━━━━━", [
        ("Director of Operations", 0x0B3B8F, "director", True, {"Director of Flight Operations", "Director of Engineering", "Head of Airline Operations", "Head of Flight Operations"}),
        ("Director of Inflight", 0x7C3AED, "director", True, {"Head of Inflight"}),
        ("Director of Ground & Airport Operations", 0x15803D, "director", True, {"Director of Ground Operations", "Director of Airport Operations", "Head of Ground Operations", "Head of Airport Operations"}),
        ("Director of People & Recruitment", 0xDB2777, "director", True, {"Director of Training", "Director of Recruitment & People", "Head of Training", "Head of Recruitment & People"}),
        ("Director of Digital Development", 0x2563EB, "director", True, {"Head of Digital Development"}),
    ]),
    ("━━━━━━━━ SENIOR MANAGEMENT ━━━━━━━━", [
        ("Senior Management", 0x1D4ED8, "lead", True, {"Senior Manager", "Senior Base Manager", "Airline Operations Manager"}),
        ("Base Manager", 0x2563EB, "lead", True, {"Deputy Base Manager"}), ("Station Manager", 0x0F766E, "lead", True, set()),
        ("Inflight Manager", 0x7C3AED, "lead", True, set()),
        ("Ground & Airport Operations Manager", 0x15803D, "lead", True, {"Ground Operations Manager", "Airport Operations Manager"}),
        ("Customer Support Manager", 0x0284C7, "lead", True, set()), ("Recruitment Manager", 0xDB2777, "lead", True, set()),
        ("Training Manager", 0x9333EA, "lead", True, {"Training Captain", "Cabin Crew Trainer", "Ground Operations Trainer"}),
        ("Development Manager", 0x2563EB, "lead", True, set()), ("Senior Cabin Crew", 0x8B5CF6, "lead", True, set()),
        ("Ground Operations Supervisor", 0x16A34A, "lead", True, {"Safety & Security Supervisor"}),
        ("Recruitment Assessor", 0xEC4899, "lead", True, set()),
    ]),
    ("━━━━━━━━ FLIGHT & CABIN OPERATIONS ━━━━━━━━", [
        ("Captain", 0xF59E0B, "staff", True, set()), ("First Officer", 0xFBBF24, "staff", True, set()),
        ("Cadet Pilot", 0xFCD34D, "staff", False, set()), ("Cabin Crew", 0x8B5CF6, "staff", True, set()),
        ("Flight Operations Dispatcher", 0x0EA5E9, "staff", False, set()),
    ]),
    ("━━━━━━━━ GROUND & AIRPORT OPERATIONS ━━━━━━━━", [
        ("Ground Operations Agent", 0x22C55E, "staff", False, set()), ("Passenger Service Agent", 0x06B6D4, "staff", False, set()),
        ("Gate Agent", 0x14B8A6, "staff", False, set()), ("Ramp Agent", 0x84CC16, "staff", False, set()),
        ("Aircraft Engineer", 0x64748B, "staff", False, {"Engineering Technician"}), ("Aviation Security Officer", 0xDC2626, "staff", False, set()),
    ]),
    ("━━━━━━━━ SUPPORT, RECRUITMENT & DIGITAL ━━━━━━━━", [
        ("Customer Support Officer", 0x38BDF8, "staff", True, set()), ("Recruitment Officer", 0xF472B6, "staff", False, set()),
        ("Developer", 0x2563EB, "staff", True, set()), ("Events Officer", 0xA855F7, "staff", False, set()),
        ("Ryanair Staff Team", 0x073590, "staff", True, {"Jet2.rblx Staff Team", "Jet2 Staff Team"}),
    ]),
    ("━━━━━━━━ RECRUITMENT & COMMUNITY ━━━━━━━━", [
        ("Recruitment Talent Pool", 0xF9A8D4, "base", False, set()), ("Ryanair Priority", 0xF1C933, "base", False, {"Jet2.rblx Priority"}),
        ("Community Member", 0x94A3B8, "base", False, {"Jet2.rblx Club Member"}), ("Passenger", 0x64748B, "base", False, {"Passanger"}),
    ]),
]


def setup(app):
    if getattr(app, "_role_sync_loaded", False):
        return
    app._role_sync_loaded = True
    perms = {"base": app.BASE_MEMBER_PERMISSIONS, "staff": app.STAFF_PERMISSIONS, "lead": app.TEAM_LEAD_PERMISSIONS,
             "director": app.DIRECTOR_PERMISSIONS, "executive": app.EXECUTIVE_PERMISSIONS, "owner": app.OWNER_PERMISSIONS,
             "tag": app.TAG_PERMISSIONS}
    blueprints = [app.role_spec("Ryanair Digital Assistant", {"Jet2.rblx Digital Assistant", "Jet2 Digital Assistant"},
                                app.RYANAIR_YELLOW, app.STAFF_PERMISSIONS, hoist=True, create_if_missing=False)]
    for divider, roles in SECTIONS:
        blueprints.append(app.divider_spec(divider))
        for name, colour, tier, hoist, aliases in roles:
            blueprints.append(app.role_spec(name, aliases, colour, perms[tier], hoist=hoist))
    app.ROLE_LEVEL_NAMES = {k: set(v) for k, v in LEVELS.items()}
    app.ROLE_BLUEPRINTS = blueprints
    app.ALL_STAFF_ROLE_NAMES = set().union(*app.ROLE_LEVEL_NAMES.values())
    app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES = app.ROLE_LEVEL_NAMES[5] | app.ROLE_LEVEL_NAMES[4]
    app.TICKET_ACCESS_ROLE_NAMES = app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES | {
        "Senior Management", "Customer Support Manager", "Customer Support Officer", "Recruitment Manager", "Recruitment Assessor"
    }
    print("Role sync loaded: clean Ryanair hierarchy ready for /setupserver.", flush=True)

"""Ryanair Discord layout V12: channel-specific publisher rank locks.

V12 keeps the existing clean layout and V11 verification, but assigns the
appropriate publishing roles to each managed Information/Bulletin channel.
Normal members can still view these public channels, while @everyone is denied
Send Messages and only the configured department/rank roles can post.
"""

import server_layout_v11 as v11
import server_layout_v7 as layout


# Information channels that V11 did not previously treat as read-only/rank-posted.
EXTRA_LOCK_CHANNELS = {
    "ryanair-help",
    "travel-assistant",
}


def channel_publishers(app, channel_name):
    """Return the exact roles allowed to publish in a managed public channel."""
    name = str(channel_name).casefold()
    directors = layout.director_plus(app)
    management = layout.level_at_or_above(app, 3)

    mapping = {
        # Information
        "rules": directors | {"Senior Management"},
        "information": directors | {"Senior Management"},
        "ryanair-help": directors | {
            "Senior Management",
            "Director of Customer Service",
            "Customer Support Manager",
            "Customer Support Officer",
            "Passenger Service Agent",
        },
        "travel-assistant": directors | {
            "Senior Management",
            "Director of Customer Service",
            "Customer Support Manager",
            "Customer Support Officer",
            "Passenger Service Agent",
        },

        # Bulletin
        "announcements": directors | {"Senior Management"},
        "press-releases": directors | {"Senior Management", "Director of Community"},
        "development": directors | {
            "Senior Management",
            "Director of Digital Development",
            "Development Manager",
            "Developer",
        },
        "careers": directors | {
            "Senior Management",
            "Director of People & Recruitment",
            "Director of Talent",
            "Director of Recruitment & Human Resources",
            "Human Resources Manager",
            "Human Resources Officer",
            "Recruitment Manager",
            "Recruitment Assessor",
            "Recruitment Officer",
            "Training Manager",
        },
        "off-topic-announcements": directors | {
            "Senior Management",
            "Director of Community",
            "Community Engagement Officer",
            "Events Officer",
        },
        "boosters": directors | {
            "Senior Management",
            "Director of Community",
            "Community Engagement Officer",
            "Events Officer",
        },
        "departures": directors | {
            "Senior Management",
            "Director of Operations",
            "Chief Pilot",
            "Flight Dispatcher",
            "Flight Operations Dispatcher",
            "Base Manager",
            "European Bases Manager",
            "Base Supervisor",
        },

        # Community notices
        "community-events": directors | {
            "Senior Management",
            "Director of Community",
            "Community Engagement Officer",
            "Events Officer",
            "Recruitment Talent Pool",
            "Recruitment Manager",
            "Recruitment Assessor",
            "Recruitment Officer",
        },
    }

    # Only use Management+ as a fallback for a managed channel without an
    # explicit map. All current managed channels above have an explicit entry.
    return set(mapping.get(name, management))


def setup(app):
    if getattr(app, "_professional_layout_v12_loaded", False):
        return
    app._professional_layout_v12_loaded = True

    # V11 and V10 both consult layout.public_publishers(), so patching this
    # before setup updates startup repairs, /checklocks, and future rebuilds.
    layout.public_publishers = channel_publishers

    # Lock every Information channel plus the existing Bulletin/community set.
    v11.LOCK_CHANNELS = tuple(
        sorted(set(v11.LOCK_CHANNELS) | EXTRA_LOCK_CHANNELS)
    )

    v11.setup(app)

    print(
        "Professional server layout V12 loaded: channel-specific department/rank publisher locks.",
        flush=True,
    )

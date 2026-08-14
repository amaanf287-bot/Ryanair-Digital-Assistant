"""Ryanair Discord layout V16: corrected public publisher ranks + ticket base access.

Changes from V15:
- all senior leadership roles can publish in managed Information/Bulletin channels;
- travel-assistant is no longer a Customer Support publishing channel;
- Support Tickets category/log access is no longer granted to every Director;
  it is limited to Executive Leadership + core Customer Support.

Public Information/Bulletin channels remain visible/readable to everyone while
posting is restricted to the configured publisher ranks.
"""

import server_layout_v15 as v15
import server_layout_v12 as v12
import server_layout_v9 as v9
import server_layout_v7 as layout


EXECUTIVE_LEADERSHIP = {
    "Chairman & Group CEO",
    "Vice Chairman",
    "Executive Access",
    "Group Chief Operating Officer",
    "Group Chief Financial Officer",
    "Group Chief People Officer",
    "Group Chief Safety & Compliance Officer",
    "Ryanair DAC Chief Executive Officer",
    "Ryanair UK Chief Executive Officer",
    "Buzz Chief Executive Officer",
    "Malta Air Chief Executive Officer",
    "Lauda Europe Chief Executive Officer",
    "Executive Board",
}

CORE_SUPPORT = {
    "Customer Support Manager",
    "Customer Support Officer",
}

CUSTOMER_SUPPORT_PUBLISHERS = {
    "Customer Support Manager",
    "Customer Support Officer",
    "Passenger Service Agent",
    "Director of Customer Experience",
    "Director of Customer Service",
}

TRAVEL_PUBLISHERS = {
    "Flight Operations Dispatcher",
    "Flight Dispatcher",
    "Passenger Service Agent",
    "Airline Operations Manager",
    "Airport Operations Manager",
    "Base Manager",
    "Station Manager",
    "Director of Flight Operations",
    "Director of Airport Operations",
}


def senior_publishers(app):
    # director_plus contains the configured Director/Executive hierarchy; the
    # explicit executive names ensure Chairman/CEO-style roles are never missed.
    return set(layout.director_plus(app)) | EXECUTIVE_LEADERSHIP | {"Senior Management"}


def channel_publishers(app, channel_name):
    """Return exact roles permitted to post in each managed public channel."""
    name = str(channel_name).casefold()
    senior = senior_publishers(app)

    mapping = {
        "rules": senior,
        "information": senior,
        "ryanair-help": senior | CUSTOMER_SUPPORT_PUBLISHERS,
        # Travel help is deliberately NOT a Customer Support publishing channel.
        "travel-assistant": senior | TRAVEL_PUBLISHERS,
        "announcements": senior,
        "press-releases": senior | {
            "Director of Community",
            "Director of Corporate Affairs",
            "Corporate Affairs Manager",
            "Public Affairs Officer",
            "Media & Communications Officer",
        },
        "development": senior | {
            "Director of Digital Development",
            "Development Manager",
            "Developer",
        },
        "careers": senior | {
            "Director of People & Recruitment",
            "Director of Recruitment & Human Resources",
            "Director of Recruitment & People",
            "Director of Talent",
            "Human Resources Manager",
            "Human Resources Officer",
            "Recruitment Manager",
            "Recruitment Assessor",
            "Recruitment Officer",
            "Training Manager",
        },
        "off-topic-announcements": senior | {
            "Director of Community",
            "Community Engagement Officer",
            "Community Affairs Officer",
            "Events Officer",
        },
        "boosters": senior | {
            "Director of Community",
            "Community Engagement Officer",
            "Community Affairs Officer",
            "Events Officer",
        },
        "departures": senior | {
            "Director of Operations",
            "Director of Flight Operations",
            "Chief Pilot",
            "Flight Dispatcher",
            "Flight Operations Dispatcher",
            "Airline Operations Manager",
            "Base Manager",
            "European Bases Manager",
            "Base Supervisor",
        },
        "community-events": senior | {
            "Director of Community",
            "Community Engagement Officer",
            "Community Affairs Officer",
            "Events Officer",
            "Recruitment Talent Pool",
            "Recruitment Manager",
            "Recruitment Assessor",
            "Recruitment Officer",
        },
    }
    return set(mapping.get(name, senior))


def ticket_base_access(app):
    """Base visibility for Support Tickets: Executives + core support only."""
    return set(EXECUTIVE_LEADERSHIP) | set(CORE_SUPPORT)


def setup(app):
    if getattr(app, "_professional_layout_v16_loaded", False):
        return
    app._professional_layout_v16_loaded = True

    # Patch before V15 setup so all startup repairs and /forceranklocks use V16.
    v12.channel_publishers = channel_publishers
    layout.public_publishers = channel_publishers
    v9.support_access = ticket_base_access

    v15.setup(app)

    print(
        "Professional server layout V16 loaded: senior publishers + travel separation + executive/support ticket base access.",
        flush=True,
    )

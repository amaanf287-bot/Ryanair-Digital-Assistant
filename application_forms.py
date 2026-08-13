"""Application form definitions and reviewer permissions for Ryanair."""

FORMS = {
    "cabin_crew": {
        "label": "Cabin Crew",
        "emoji": "ryanair_yellow",
        "role": "Cabin Crew",
        "questions": [
            ("Why Cabin Crew?", "Why do you want to join the Ryanair Cabin Crew team?"),
            ("Passenger support", "How would you help a confused or upset passenger during a Roblox flight?"),
            ("Teamwork", "How would you work well with cabin crew and ground staff?"),
            ("Professionalism", "How would you stay professional during a busy or disrupted flight?"),
            ("Activity", "What experience and availability can you offer?"),
        ],
    },
    "ground_airport": {
        "label": "Ground & Airport Operations",
        "emoji": "malta_airport",
        "role": "Ground Operations Agent",
        "questions": [
            ("Why this department?", "Why do you want to join Ground & Airport Operations?"),
            ("Passenger queue", "How would you manage a busy check-in queue while keeping passengers informed?"),
            ("Boarding problem", "What would you do if a passenger arrived late while boarding was closing?"),
            ("Coordination", "How would you communicate with gate, dispatch and cabin teams during a turnaround?"),
            ("Activity", "What experience and availability can you offer?"),
        ],
    },
    "customer_support": {
        "label": "Customer Support",
        "emoji": "passenger",
        "role": "Customer Support Officer",
        "questions": [
            ("Why support?", "Why do you want to join Customer Support?"),
            ("Difficult passenger", "How would you deal with an angry passenger professionally?"),
            ("Ticket handling", "How would you keep a support ticket clear, professional and useful?"),
            ("Escalation", "When should a support issue be escalated to management?"),
            ("Activity", "What experience and availability can you offer?"),
        ],
    },
    "senior_management": {
        "label": "Senior Management",
        "emoji": "ryanair_yellow",
        "role": "Senior Management",
        "questions": [
            ("Leadership", "Why are you applying for Senior Management at Ryanair?"),
            ("Staff conflict", "How would you resolve a disagreement between two staff members fairly?"),
            ("Performance", "How would you deal with repeated poor performance while supporting the staff member?"),
            ("Disruption", "How would you lead during a delayed or disorganised flight event?"),
            ("Improvement", "What realistic improvement would you bring to Ryanair?"),
        ],
    },
    "developer": {
        "label": "Developer",
        "emoji": "document",
        "role": "Developer",
        "questions": [
            ("Development skills", "Which Roblox, coding, modelling or UI skills can you contribute?"),
            ("Previous work", "Describe a project you built and what you personally completed."),
            ("Bug handling", "How would you safely investigate and fix a serious live-game bug?"),
            ("Team working", "How do you share progress, receive feedback and protect private assets?"),
            ("Availability", "How often can you contribute, and can you provide a portfolio?"),
        ],
    },
}

REVIEW_ROLES = {
    "Senior Management",
    "Recruitment Manager",
    "Recruitment Assessor",
    "Director of People & Recruitment",
    "Executive Board",
    "Chairman & Group CEO",
    "Vice Chairman",
    "Executive Access",
}


def choices(app_commands):
    return [
        app_commands.Choice(name=details["label"], value=key)
        for key, details in FORMS.items()
    ]

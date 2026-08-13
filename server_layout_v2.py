"""Professional Ryanair Discord server rebuild V2.

Owner-only /setupserver preserves Staff Hub, removes the other server channels,
creates a clean reference-style layout, normalises rank-role permissions, and
uses category/channel overwrites for rank access.
"""

import asyncio
import discord
from discord import app_commands


EXTRA_LEVEL_ROLES = {
    4: {
        "Chief Pilot", "Chief Instructor, Safety", "Director of Ground Operations",
        "Director of Customer Service", "Director of Talent",
        "Director of Recruitment & Human Resources", "Director of Community",
    },
    3: {"European Bases Manager", "Base Supervisor", "Human Resources Manager"},
    2: {"Flight Dispatcher", "Engineer", "Human Resources Officer", "Community Engagement Officer"},
    1: {"Trainee", "Cabin Crew Trainee", "Ground Operations Trainee", "Customer Support Trainee", "Flight Operations Trainee"},
}

EXTRA_ROLES = [
    ("Chief Pilot", 0x0EA5E9, True, False),
    ("Chief Instructor, Safety", 0x38BDF8, True, False),
    ("Director of Ground Operations", 0x15803D, True, False),
    ("Director of Customer Service", 0x0284C7, True, False),
    ("Director of Talent", 0xDB2777, True, False),
    ("Director of Recruitment & Human Resources", 0xEC4899, True, False),
    ("Director of Community", 0xA855F7, True, False),
    ("European Bases Manager", 0xF6E7A7, True, False),
    ("Base Supervisor", 0xF59E0B, True, False),
    ("Human Resources Manager", 0xDB2777, True, False),
    ("Flight Dispatcher", 0x0EA5E9, False, False),
    ("Engineer", 0x64748B, False, False),
    ("Human Resources Officer", 0xF472B6, False, False),
    ("Community Engagement Officer", 0x3B82F6, False, False),
    ("Trainee", 0xF9A8D4, False, False),
    ("Cabin Crew Trainee", 0xC4B5FD, False, False),
    ("Ground Operations Trainee", 0x86EFAC, False, False),
    ("Customer Support Trainee", 0x7DD3FC, False, False),
    ("Flight Operations Trainee", 0xFDE68A, False, False),
    ("Verified", 0x23C483, False, False),
    ("Directors", 0x0B6E99, False, False),
    ("Staff", 0xC7F000, False, False),
    ("Bloxlink Updater", 0xE23B45, False, False),
    ("Community Announcements", 0xFFB000, False, True),
    ("Off Topic Announcements", 0xFFB000, False, True),
    ("QOTD Announcements", 0xFFB000, False, True),
    ("Music Channels", 0x9CA3AF, False, False),
]


def norm(name):
    return "".join(ch for ch in str(name).casefold() if ch.isalnum())


def role_named(guild, name):
    return discord.utils.get(guild.roles, name=name)


def find_role(guild, names):
    wanted = {norm(name) for name in names}
    return next((role for role in guild.roles if norm(role.name) in wanted), None)


def bot_overwrite():
    return discord.PermissionOverwrite(
        view_channel=True, send_messages=True, read_message_history=True,
        manage_channels=True, manage_messages=True, embed_links=True,
        attach_files=True, add_reactions=True, connect=True, speak=True,
    )


def public_overwrites(guild, read_only=False):
    data = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True, read_message_history=True,
            send_messages=False if read_only else True,
            add_reactions=True, connect=True, speak=True,
        )
    }
    if guild.me:
        data[guild.me] = bot_overwrite()
    return data


def private_overwrites(guild, allowed_names, read_only=False):
    data = {guild.default_role: discord.PermissionOverwrite(view_channel=False)}
    if guild.me:
        data[guild.me] = bot_overwrite()
    for name in allowed_names:
        role = role_named(guild, name)
        if role:
            data[role] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=False if read_only else True,
                add_reactions=True,
                use_application_commands=True,
                connect=True,
                speak=True,
            )
    return data


def roles_at_or_above(app, minimum):
    names = set()
    for level in range(minimum, 6):
        names |= set(app.ROLE_LEVEL_NAMES.get(level, set()))
    return names


def department_access(app, names):
    return set(names) | roles_at_or_above(app, 4)


async def ensure_roles(app, guild, actor):
    bot_member = guild.me
    if not bot_member or not bot_member.guild_permissions.manage_roles:
        raise RuntimeError("The bot needs Manage Roles.")

    created, updated, failed = [], [], []
    none = discord.Permissions.none()
    processed = set()

    for spec in app.ROLE_BLUEPRINTS:
        role = find_role(guild, spec.get("aliases", {spec["target"]}))
        if role is None and spec.get("create_if_missing", True):
            try:
                role = await guild.create_role(
                    name=spec["target"], colour=discord.Colour(spec["color"]),
                    permissions=none, hoist=spec.get("hoist", False),
                    mentionable=spec.get("mentionable", False),
                    reason=f"Ryanair server rebuild requested by {actor}",
                )
                created.append(spec["target"])
            except (discord.Forbidden, discord.HTTPException) as exc:
                failed.append(f"{spec['target']}: {str(exc)[:100]}")
                continue
        if not role or role.id in processed:
            continue
        processed.add(role.id)
        if role.managed or role.is_default() or role >= bot_member.top_role:
            continue
        try:
            old = role.name
            await role.edit(
                name=spec["target"], colour=discord.Colour(spec["color"]),
                permissions=none, hoist=spec.get("hoist", False),
                mentionable=spec.get("mentionable", False),
                reason=f"Normal role permissions set by {actor}",
            )
            if spec["target"] not in created:
                updated.append(spec["target"] if old == spec["target"] else f"{old} -> {spec['target']}")
        except (discord.Forbidden, discord.HTTPException) as exc:
            failed.append(f"{role.name}: {str(exc)[:100]}")

    for name, colour, hoist, mentionable in EXTRA_ROLES:
        role = role_named(guild, name)
        if role is None:
            try:
                role = await guild.create_role(
                    name=name, colour=discord.Colour(colour), permissions=none,
                    hoist=hoist, mentionable=mentionable,
                    reason=f"Professional Ryanair role created by {actor}",
                )
                created.append(name)
            except (discord.Forbidden, discord.HTTPException) as exc:
                failed.append(f"{name}: {str(exc)[:100]}")
                continue
        elif not role.managed and role < bot_member.top_role:
            try:
                await role.edit(
                    colour=discord.Colour(colour), permissions=none,
                    hoist=hoist, mentionable=mentionable,
                    reason=f"Normal role permissions set by {actor}",
                )
                updated.append(name)
            except (discord.Forbidden, discord.HTTPException) as exc:
                failed.append(f"{name}: {str(exc)[:100]}")

    ordered = []
    for spec in app.ROLE_BLUEPRINTS:
        role = role_named(guild, spec["target"])
        if role and not role.managed and not role.is_default() and role < bot_member.top_role and role not in ordered:
            ordered.append(role)
    for name, *_ in EXTRA_ROLES:
        role = role_named(guild, name)
        if role and not role.managed and role < bot_member.top_role and role not in ordered:
            ordered.append(role)

    positions = {}
    top = bot_member.top_role.position - 1
    for index, role in enumerate(ordered):
        target = top - index
        if target <= 0:
            break
        positions[role] = target
    if positions:
        try:
            await guild.edit_role_positions(positions=positions, reason=f"Ryanair role ordering by {actor}")
        except (discord.Forbidden, discord.HTTPException) as exc:
            failed.append(f"Role ordering: {str(exc)[:100]}")

    cfg = app.level_config.setdefault(str(guild.id), {})
    for key, name in {
        "5": "Executive Access", "4": "Executive Board", "3": "Senior Management",
        "2": "Ryanair Staff Team", "1": "Recruitment Talent Pool",
        "ticket_role": "Customer Support Officer",
    }.items():
        role = role_named(guild, name)
        if role:
            cfg[key] = str(role.id)
    app.save_data()
    return created, updated, failed


def staff_hub_preserve(guild):
    preserve = set()
    for category in guild.categories:
        if norm(category.name) == "staffhub":
            preserve.add(category.id)
            preserve |= {channel.id for channel in category.channels}
    for channel in guild.channels:
        if not isinstance(channel, discord.CategoryChannel) and norm(channel.name) == "staffhub":
            preserve.add(channel.id)
    return preserve


async def delete_old_channels(guild, preserve_ids, actor):
    deleted, failed = [], []
    for channel in [c for c in guild.channels if not isinstance(c, discord.CategoryChannel)]:
        if channel.id in preserve_ids:
            continue
        try:
            deleted.append(channel.name)
            await channel.delete(reason=f"Professional rebuild by {actor}; Staff Hub preserved")
            await asyncio.sleep(0.15)
        except (discord.Forbidden, discord.HTTPException) as exc:
            failed.append(f"{channel.name}: {str(exc)[:90]}")
    for category in list(guild.categories):
        if category.id in preserve_ids:
            continue
        try:
            deleted.append(category.name)
            await category.delete(reason=f"Professional rebuild by {actor}; Staff Hub preserved")
            await asyncio.sleep(0.15)
        except (discord.Forbidden, discord.HTTPException) as exc:
            failed.append(f"{category.name}: {str(exc)[:90]}")
    return deleted, failed


async def make_category(guild, name, overwrites):
    return await guild.create_category(name, overwrites=overwrites, reason="Professional Ryanair server layout")


async def make_text(guild, category, name, topic=None, overwrites=None):
    return await guild.create_text_channel(
        name, category=category, topic=topic, overwrites=overwrites,
        reason="Professional Ryanair server layout",
    )


async def build_layout(app, guild, preserve_ids):
    made = {}

    verification = await make_category(guild, "Verification", public_overwrites(guild))
    made["verify-help"] = await make_text(guild, verification, "verify-help", "Help with server verification.")
    made["verify"] = await make_text(guild, verification, "verify", "Complete server verification here.")

    info = await make_category(guild, "Information", public_overwrites(guild))
    made["rules"] = await make_text(guild, info, "rules", "Official community rules.", public_overwrites(guild, True))
    made["information"] = await make_text(guild, info, "information", "Ryanair Roblox community information.", public_overwrites(guild, True))
    made["ryanair-help"] = await make_text(guild, info, "ryanair-help", "Frequently asked questions and help.")
    made["travel-assistant"] = await make_text(guild, info, "travel-assistant", "Travel and community assistance.")

    bulletin = await make_category(guild, "Bulletin", public_overwrites(guild, True))
    for name, topic in [
        ("announcements", "Official Ryanair community announcements."),
        ("press-releases", "Official press releases and major updates."),
        ("development", "Development progress and release notes."),
        ("careers", "Staffing and application notices."),
        ("off-topic-announcements", "Optional off-topic announcements."),
        ("boosters", "Server booster recognition and updates."),
        ("departures", "Live passenger flight departures and updates."),
    ]:
        made[name] = await make_text(guild, bulletin, name, topic, public_overwrites(guild, True))

    public = await make_category(guild, "Public", public_overwrites(guild))
    for name, topic in [
        ("chat", "Main community chat."), ("photo-gallery", "Community aviation images."),
        ("aviation", "Aviation discussion."), ("bot-commands", "Use bot commands here to keep chat clean."),
    ]:
        made[name] = await make_text(guild, public, name, topic)

    community = await make_category(guild, "Community", public_overwrites(guild))
    made["community-events"] = await make_text(guild, community, "community-events", "Community event notices.", public_overwrites(guild, True))
    made["community-posts"] = await make_text(guild, community, "community-posts", "Community posts and discussion.")

    voice = await make_category(guild, "Community Voice", public_overwrites(guild))
    made["voice-chat"] = await guild.create_voice_channel("Voice Chat", category=voice, reason="Professional Ryanair server layout")
    made["voice-chat-2"] = await guild.create_voice_channel("Voice Chat 2", category=voice, reason="Professional Ryanair server layout")

    recruitment = await make_category(guild, "Recruitment & Training", private_overwrites(guild, roles_at_or_above(app, 1)))
    for name in ["talent-pool", "trainee-hub", "training-information", "recruitment-updates"]:
        made[name] = await make_text(guild, recruitment, name)

    staff_category = next((c for c in guild.categories if c.id in preserve_ids and norm(c.name) == "staffhub"), None)
    if staff_category:
        await staff_category.edit(overwrites=private_overwrites(guild, roles_at_or_above(app, 2)), reason="Rank-lock Staff Hub")
    else:
        staff_category = await make_category(guild, "Staff Hub", private_overwrites(guild, roles_at_or_above(app, 2)))
        old_staff_hub = next((c for c in guild.channels if c.id in preserve_ids and not isinstance(c, discord.CategoryChannel)), None)
        if old_staff_hub:
            try:
                await old_staff_hub.edit(category=staff_category, sync_permissions=True, reason="Preserve Staff Hub")
            except (discord.Forbidden, discord.HTTPException):
                pass
        else:
            made["staff-hub"] = await make_text(guild, staff_category, "staff-hub", "Main staff hub.")
    existing = {norm(c.name) for c in staff_category.channels}
    for name in ["staff-announcements", "staff-chat", "staff-commands", "staff-resources"]:
        if norm(name) not in existing:
            made[name] = await make_text(guild, staff_category, name)

    management = await make_category(guild, "Management", private_overwrites(guild, roles_at_or_above(app, 3)))
    for name in ["management-chat", "staffing", "operations-planning"]:
        made[name] = await make_text(guild, management, name)

    directors = await make_category(guild, "Directors", private_overwrites(guild, roles_at_or_above(app, 4)))
    for name in ["director-chat", "director-reports", "approvals"]:
        made[name] = await make_text(guild, directors, name)

    executive_names = set(app.ROLE_LEVEL_NAMES.get(5, set())) | {
        "Group Chief Operating Officer", "Ryanair DAC Chief Executive Officer",
        "Ryanair UK Chief Executive Officer", "Buzz Chief Executive Officer",
        "Malta Air Chief Executive Officer", "Lauda Europe Chief Executive Officer", "Executive Board",
    }
    executive = await make_category(guild, "Executive", private_overwrites(guild, executive_names))
    for name in ["executive-chat", "executive-decisions", "confidential"]:
        made[name] = await make_text(guild, executive, name)

    flight_access = department_access(app, {
        "Chief Pilot", "Chief Instructor, Safety", "Captain", "First Officer", "Cadet Pilot",
        "Flight Dispatcher", "Flight Operations Dispatcher", "Flight Operations Trainee",
        "Senior Management", "Base Manager", "European Bases Manager", "Base Supervisor",
    })
    flight = await make_category(guild, "Flight Operations", private_overwrites(guild, flight_access))
    for name in ["flight-operations", "flight-dispatch", "crew-assignments", "flight-reports"]:
        made[name] = await make_text(guild, flight, name)

    cabin_access = department_access(app, {
        "Director of Inflight", "Inflight Manager", "Senior Cabin Crew", "Cabin Crew", "Cabin Crew Trainee",
        "Training Manager", "Senior Management",
    })
    cabin = await make_category(guild, "Cabin Operations", private_overwrites(guild, cabin_access))
    for name in ["cabin-operations", "cabin-crew-chat", "training-and-standards"]:
        made[name] = await make_text(guild, cabin, name)

    ground_access = department_access(app, {
        "Director of Ground & Airport Operations", "Director of Ground Operations", "Ground & Airport Operations Manager",
        "Ground Operations Supervisor", "Ground Operations Agent", "Ground Operations Trainee", "Passenger Service Agent",
        "Gate Agent", "Ramp Agent", "Aircraft Engineer", "Engineer", "Aviation Security Officer", "Station Manager",
        "European Bases Manager", "Base Manager", "Base Supervisor", "Senior Management",
    })
    ground = await make_category(guild, "Ground & Airport Operations", private_overwrites(guild, ground_access))
    for name in ["ground-operations", "airport-operations", "base-operations"]:
        made[name] = await make_text(guild, ground, name)

    support_access = department_access(app, {
        "Director of Customer Service", "Customer Support Manager", "Customer Support Officer", "Customer Support Trainee",
        "Recruitment Manager", "Recruitment Assessor", "Senior Management",
    })
    support = await make_category(guild, "Customer Support", private_overwrites(guild, support_access))
    for name in ["support-team", "ticket-management", "application-reviews"]:
        made[name] = await make_text(guild, support, name)

    people_access = department_access(app, {
        "Director of Talent", "Director of People & Recruitment", "Director of Recruitment & Human Resources",
        "Human Resources Manager", "Human Resources Officer", "Recruitment Manager", "Recruitment Assessor",
        "Recruitment Officer", "Training Manager", "Senior Management",
    })
    people = await make_category(guild, "People & Recruitment", private_overwrites(guild, people_access))
    for name in ["human-resources", "recruitment-team", "training-team"]:
        made[name] = await make_text(guild, people, name)

    dev_access = department_access(app, {"Director of Digital Development", "Development Manager", "Developer", "Senior Management"})
    dev = await make_category(guild, "Development Team", private_overwrites(guild, dev_access))
    for name in ["development-team", "bot-development", "bug-reports"]:
        made[name] = await make_text(guild, dev, name)

    ticket_category = await make_category(guild, "Support Tickets", private_overwrites(guild, support_access))

    logs = await make_category(guild, "Logs", private_overwrites(guild, roles_at_or_above(app, 4)))
    made["action-logs"] = await make_text(guild, logs, "action-logs")
    made["moderation-logs"] = await make_text(guild, logs, "moderation-logs")
    made["ticket-logs"] = await make_text(guild, logs, "ticket-logs", overwrites=private_overwrites(guild, support_access))

    return made, ticket_category


def resolve_runtime_channels(app, guild):
    by_name = {channel.name.casefold(): channel for channel in guild.channels}
    announcements = by_name.get("announcements")
    departures = by_name.get("departures")
    logs = by_name.get("action-logs") or by_name.get("moderation-logs")
    ticket_category = next((c for c in guild.categories if c.name.casefold() == "support tickets"), None)
    if announcements:
        app.ANNOUNCEMENT_CHANNEL_ID = announcements.id
    if departures:
        app.DEPARTURES_CHANNEL_ID = departures.id
    if logs:
        app.LOG_CHANNEL_ID = logs.id
    if ticket_category:
        app.TICKET_CATEGORY_ID = ticket_category.id


def setup(app):
    if getattr(app, "_professional_layout_v2_loaded", False):
        return
    app._professional_layout_v2_loaded = True

    for level, names in EXTRA_LEVEL_ROLES.items():
        app.ROLE_LEVEL_NAMES.setdefault(level, set()).update(names)
    app.ALL_STAFF_ROLE_NAMES = set().union(*app.ROLE_LEVEL_NAMES.values())
    app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES = app.ROLE_LEVEL_NAMES[5] | app.ROLE_LEVEL_NAMES[4]
    app.TICKET_ACCESS_ROLE_NAMES = app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES | {
        "Senior Management", "Customer Support Manager", "Customer Support Officer",
        "Customer Support Trainee", "Recruitment Manager", "Recruitment Assessor",
    }

    guild_obj = discord.Object(id=app.GUILD_ID)
    app.tree.remove_command("setupserver", guild=guild_obj)

    @app_commands.command(name="setupserver", description="Rebuild Ryanair channels, roles and rank locks (Owner only)")
    async def setupserver_rebuild(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not app.is_server_owner(interaction.user):
            await interaction.followup.send("Only the server owner can run `/setupserver`.", ephemeral=True)
            return
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("Run this inside the Ryanair server.", ephemeral=True)
            return
        me = guild.me
        if not me or not me.guild_permissions.manage_channels or not me.guild_permissions.manage_roles:
            await interaction.followup.send("The bot needs **Manage Channels** and **Manage Roles**.", ephemeral=True)
            return

        try:
            await interaction.user.send(
                "Ryanair server rebuild started. Existing **Staff Hub** is being preserved; other channels/categories are being replaced."
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        created_roles, updated_roles, role_failures = await ensure_roles(app, guild, interaction.user)
        preserve_ids = staff_hub_preserve(guild)
        deleted, delete_failures = await delete_old_channels(guild, preserve_ids, interaction.user)

        app.tickets.clear()
        app.connected_staff.clear()
        app.ticket_ai_active.clear()
        app.ticket_ai_history.clear()
        app.last_activity.clear()
        app.save_data()

        created_channels = {}
        layout_error = None
        try:
            created_channels, ticket_category = await build_layout(app, guild, preserve_ids)
            app.TICKET_CATEGORY_ID = ticket_category.id
            resolve_runtime_channels(app, guild)
        except Exception as exc:
            layout_error = f"{type(exc).__name__}: {exc}"

        summary = (
            "Ryanair server rebuild finished.\n\n"
            f"Roles created: **{len(created_roles)}**\n"
            f"Roles normalised: **{len(updated_roles)}**\n"
            f"Old channels/categories removed: **{len(deleted)}**\n"
            f"New channels created: **{len(created_channels)}**\n"
            f"Role issues: **{len(role_failures)}**\n"
            f"Delete issues: **{len(delete_failures)}**\n"
            f"Layout error: **{layout_error or 'None'}**\n\n"
            "Staff Hub was preserved where found. Rank roles now have normal permissions; private access is handled by category/channel rank locks."
        )
        try:
            await interaction.user.send(summary)
        except (discord.Forbidden, discord.HTTPException):
            pass
        try:
            await interaction.followup.send(summary, ephemeral=True)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    app.tree.add_command(setupserver_rebuild, guild=guild_obj, override=True)

    async def resolve_on_ready():
        guild = app.bot.get_guild(app.GUILD_ID)
        if guild:
            resolve_runtime_channels(app, guild)

    app.bot.add_listener(resolve_on_ready, "on_ready")
    print("Professional server layout V2 loaded: /setupserver rebuild + rank locks.", flush=True)

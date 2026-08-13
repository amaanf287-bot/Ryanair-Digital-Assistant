"""Professional Ryanair Discord server rebuild and rank-locked channel layout.

/setupserver is intentionally destructive for channels: it preserves an existing
Staff Hub category/channel, removes other channels/categories, then creates the
clean structure requested by the server owner. Role permissions stay normal;
private access is controlled with channel/category overwrites instead.
"""

import asyncio
import discord
from discord import app_commands


EXTRA_LEVEL_ROLES = {
    5: set(),
    4: {
        "Chief Pilot",
        "Chief Instructor, Safety",
        "Director of Ground Operations",
        "Director of Customer Service",
        "Director of Talent",
        "Director of Recruitment & Human Resources",
        "Director of Community",
    },
    3: {
        "European Bases Manager",
        "Base Supervisor",
        "Human Resources Manager",
    },
    2: {
        "Flight Dispatcher",
        "Engineer",
        "Human Resources Officer",
        "Community Engagement Officer",
    },
    1: {
        "Trainee",
        "Cabin Crew Trainee",
        "Ground Operations Trainee",
        "Customer Support Trainee",
        "Flight Operations Trainee",
    },
}

EXTRA_ROLES = [
    # name, colour, hoist, mentionable
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
    # Classification / opt-in roles inspired by the reference server.
    ("Verified", 0x23C483, False, False),
    ("Directors", 0x0B6E99, False, False),
    ("Staff", 0xC7F000, False, False),
    ("Bloxlink Updater", 0xE23B45, False, False),
    ("Community Announcements", 0xFFB000, False, True),
    ("Off Topic Announcements", 0xFFB000, False, True),
    ("QOTD Announcements", 0xFFB000, False, True),
    ("Music Channels", 0x9CA3AF, False, False),
]


def _normalise(name: str) -> str:
    return "".join(ch for ch in name.casefold() if ch.isalnum())


def _find_role(guild: discord.Guild, names):
    wanted = {_normalise(name) for name in names}
    return next((role for role in guild.roles if _normalise(role.name) in wanted), None)


def _role(guild: discord.Guild, name: str):
    return discord.utils.get(guild.roles, name=name)


def _bot_overwrite():
    return discord.PermissionOverwrite(
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        manage_channels=True,
        manage_messages=True,
        embed_links=True,
        attach_files=True,
        add_reactions=True,
        connect=True,
        speak=True,
    )


def _public_overwrites(guild: discord.Guild, *, read_only=False):
    everyone = discord.PermissionOverwrite(
        view_channel=True,
        read_message_history=True,
        send_messages=False if read_only else True,
        add_reactions=True,
        connect=True,
        speak=True,
    )
    data = {guild.default_role: everyone}
    if guild.me:
        data[guild.me] = _bot_overwrite()
    return data


def _private_overwrites(guild: discord.Guild, allowed_names, *, read_only=False):
    data = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
    }
    if guild.me:
        data[guild.me] = _bot_overwrite()
    for name in allowed_names:
        role = _role(guild, name)
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


def _roles_at_or_above(app, minimum: int):
    names = set()
    for level in range(minimum, 6):
        names.update(app.ROLE_LEVEL_NAMES.get(level, set()))
    return names


def _department_access(app, role_names):
    # Directors/executives always retain operational oversight.
    return set(role_names) | _roles_at_or_above(app, 4)


async def _ensure_roles(app, guild: discord.Guild, actor) -> tuple[list[str], list[str], list[str]]:
    created, updated, failed = [], [], []
    bot_member = guild.me
    if not bot_member or not bot_member.guild_permissions.manage_roles:
        raise RuntimeError("The bot needs Manage Roles to rebuild the role hierarchy.")

    resolved = {}
    processed = set()
    normal_permissions = discord.Permissions.none()

    for spec in app.ROLE_BLUEPRINTS:
        role = _find_role(guild, spec.get("aliases", {spec["target"]}))
        if role is None and spec.get("create_if_missing", True):
            try:
                role = await guild.create_role(
                    name=spec["target"],
                    colour=discord.Colour(spec["color"]),
                    permissions=normal_permissions,
                    hoist=spec.get("hoist", False),
                    mentionable=spec.get("mentionable", False),
                    reason=f"Professional Ryanair server rebuild requested by {actor}",
                )
                created.append(spec["target"])
            except (discord.Forbidden, discord.HTTPException) as exc:
                failed.append(f"{spec['target']}: {str(exc)[:100]}")
                continue
        if not role:
            continue
        resolved[spec["target"]] = role
        if role.id in processed or role.managed or role.is_default() or role >= bot_member.top_role:
            continue
        processed.add(role.id)
        try:
            old = role.name
            await role.edit(
                name=spec["target"],
                colour=discord.Colour(spec["color"]),
                permissions=normal_permissions,
                hoist=spec.get("hoist", False),
                mentionable=spec.get("mentionable", False),
                reason=f"Normalised role permissions during server rebuild by {actor}",
            )
            if spec["target"] not in created:
                updated.append(spec["target"] if old == spec["target"] else f"{old} → {spec['target']}")
        except (discord.Forbidden, discord.HTTPException) as exc:
            failed.append(f"{role.name}: {str(exc)[:100]}")

    for name, colour, hoist, mentionable in EXTRA_ROLES:
        role = _role(guild, name)
        if role is None:
            try:
                role = await guild.create_role(
                    name=name,
                    colour=discord.Colour(colour),
                    permissions=normal_permissions,
                    hoist=hoist,
                    mentionable=mentionable,
                    reason=f"Professional Ryanair role created by {actor}",
                )
                created.append(name)
            except (discord.Forbidden, discord.HTTPException) as exc:
                failed.append(f"{name}: {str(exc)[:100]}")
                continue
        elif not role.managed and not role.is_default() and role < bot_member.top_role:
            try:
                await role.edit(
                    colour=discord.Colour(colour),
                    permissions=normal_permissions,
                    hoist=hoist,
                    mentionable=mentionable,
                    reason=f"Normalised role permissions during server rebuild by {actor}",
                )
                updated.append(name)
            except (discord.Forbidden, discord.HTTPException) as exc:
                failed.append(f"{name}: {str(exc)[:100]}")

    # Put configured roles under the bot in hierarchy order where Discord permits it.
    ordered = []
    for spec in app.ROLE_BLUEPRINTS:
        role = _role(guild, spec["target"])
        if role and not role.managed and not role.is_default() and role < bot_member.top_role and role not in ordered:
            ordered.append(role)
    for name, *_ in EXTRA_ROLES:
        role = _role(guild, name)
        if role and role < bot_member.top_role and role not in ordered:
            ordered.append(role)
    available_top = bot_member.top_role.position - 1
    positions = {}
    for index, role in enumerate(ordered):
        pos = available_top - index
        if pos <= 0:
            break
        positions[role] = pos
    if positions:
        try:
            await guild.edit_role_positions(
                positions=positions,
                reason=f"Professional role ordering requested by {actor}",
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            failed.append(f"Role ordering: {str(exc)[:100]}")

    cfg = app.level_config.setdefault(str(guild.id), {})
    mapping = {
        "5": "Executive Access",
        "4": "Executive Board",
        "3": "Senior Management",
        "2": "Ryanair Staff Team",
        "1": "Recruitment Talent Pool",
        "ticket_role": "Customer Support Officer",
    }
    for key, name in mapping.items():
        role = _role(guild, name)
        if role:
            cfg[key] = str(role.id)
    app.save_data()
    return created, updated, failed


def _staff_hub_preserve_set(guild: discord.Guild):
    preserve = set()
    staff_categories = [c for c in guild.categories if _normalise(c.name) == "staffhub"]
    for category in staff_categories:
        preserve.add(category.id)
        preserve.update(channel.id for channel in category.channels)
    for channel in guild.channels:
        if not isinstance(channel, discord.CategoryChannel) and _normalise(channel.name) == "staffhub":
            preserve.add(channel.id)
    return preserve


async def _delete_old_channels(guild: discord.Guild, preserve_ids, actor):
    deleted, failed = [], []
    # Delete children first so category deletion cannot leave unwanted uncategorised channels.
    channels = [c for c in guild.channels if not isinstance(c, discord.CategoryChannel)]
    for channel in channels:
        if channel.id in preserve_ids:
            continue
        try:
            deleted.append(channel.name)
            await channel.delete(reason=f"Server rebuild requested by {actor}; Staff Hub preserved")
            await asyncio.sleep(0.15)
        except (discord.Forbidden, discord.HTTPException) as exc:
            failed.append(f"#{channel.name}: {str(exc)[:90]}")

    for category in list(guild.categories):
        if category.id in preserve_ids:
            continue
        try:
            deleted.append(category.name)
            await category.delete(reason=f"Server rebuild requested by {actor}; Staff Hub preserved")
            await asyncio.sleep(0.15)
        except (discord.Forbidden, discord.HTTPException) as exc:
            failed.append(f"{category.name}: {str(exc)[:90]}")
    return deleted, failed


async def _create_text(guild, category, name, *, topic=None, read_only=False, overwrites=None):
    return await guild.create_text_channel(
        name,
        category=category,
        topic=topic,
        overwrites=overwrites,
        reason="Professional Ryanair server layout",
    )


async def _create_category(guild, name, overwrites):
    return await guild.create_category(name, overwrites=overwrites, reason="Professional Ryanair server layout")


async def _build_layout(app, guild: discord.Guild, preserve_ids):
    created = {}

    # Public/reference-style structure.
    verification = await _create_category(guild, "Verification", _public_overwrites(guild))
    created["verify-help"] = await _create_text(guild, verification, "verify-help", topic="Help with server verification.")
    created["verify"] = await _create_text(guild, verification, "verify", topic="Complete server verification here.")

    information = await _create_category(guild, "Information", _public_overwrites(guild))
    for name, topic in [
        ("rules", "Official community rules and conduct."),
        ("information", "Ryanair Roblox community information."),
        ("ryanair-help", "Frequently asked questions and help."),
        ("travel-assistant", "Ask for travel and community assistance."),
    ]:
        created[name] = await _create_text(guild, information, name, topic=topic)

    bulletin = await _create_category(guild, "Bulletin", _public_overwrites(guild, read_only=True))
    for name, topic in [
        ("announcements", "Official Ryanair community announcements."),
        ("press-releases", "Official press releases and major updates."),
        ("development", "Development progress and release notes."),
        ("careers", "Community staffing and application notices."),
        ("off-topic-announcements", "Optional off-topic announcements."),
        ("boosters", "Server booster recognition and updates."),
        ("departures", "Live passenger flight departures and operational updates."),
    ]:
        created[name] = await _create_text(
            guild,
            bulletin,
            name,
            topic=topic,
            read_only=True,
            overwrites=_public_overwrites(guild, read_only=True),
        )

    public = await _create_category(guild, "Public", _public_overwrites(guild))
    for name, topic in [
        ("chat", "Main community chat."),
        ("photo-gallery", "Share approved aviation and community images."),
        ("aviation", "Aviation discussion."),
        ("bot-commands", "Use bot commands here to keep other channels clean."),
    ]:
        created[name] = await _create_text(guild, public, name, topic=topic)

    community = await _create_category(guild, "Community", _public_overwrites(guild))
    created["community-events"] = await _create_text(guild, community, "community-events", topic="Community event notices.", overwrites=_public_overwrites(guild, read_only=True))
    created["community-posts"] = await _create_text(guild, community, "community-posts", topic="Community posts and discussion.")

    voice = await _create_category(guild, "Community Voice", _public_overwrites(guild))
    created["voice-chat"] = await guild.create_voice_channel("Voice Chat", category=voice, reason="Professional Ryanair server layout")
    created["voice-chat-2"] = await guild.create_voice_channel("Voice Chat 2", category=voice, reason="Professional Ryanair server layout")

    # Recruitment / trainee area — Level 1+.
    recruitment_access = _roles_at_or_above(app, 1)
    recruitment = await _create_category(guild, "Recruitment & Training", _private_overwrites(guild, recruitment_access))
    for name in ["talent-pool", "trainee-hub", "training-information", "recruitment-updates"]:
        created[name] = await _create_text(guild, recruitment, name)

    # Preserve Staff Hub if it already exists. If not, create a new clean one.
    staff_category = next((c for c in guild.categories if c.id in preserve_ids and _normalise(c.name) == "staffhub"), None)
    if staff_category:
        await staff_category.edit(overwrites=_private_overwrites(guild, _roles_at_or_above(app, 2)), reason="Rank-lock Staff Hub")
    else:
        staff_category = await _create_category(guild, "Staff Hub", _private_overwrites(guild, _roles_at_or_above(app, 2)))
        preserved_channel = next((c for c in guild.channels if c.id in preserve_ids and not isinstance(c, discord.CategoryChannel)), None)
        if preserved_channel:
            try:
                await preserved_channel.edit(category=staff_category, sync_permissions=True, reason="Keep existing Staff Hub")
            except (discord.Forbidden, discord.HTTPException):
                pass
        else:
            created["staff-hub"] = await _create_text(guild, staff_category, "staff-hub", topic="Main staff hub.")
    existing_staff_names = {_normalise(c.name) for c in staff_category.channels}
    for name in ["staff-announcements", "staff-chat", "staff-commands", "staff-resources"]:
        if _normalise(name) not in existing_staff_names:
            created[name] = await _create_text(guild, staff_category, name)

    # Management, director and executive tiers.
    management = await _create_category(guild, "Management", _private_overwrites(guild, _roles_at_or_above(app, 3)))
    for name in ["management-chat", "staffing", "operations-planning"]:
        created[name] = await _create_text(guild, management, name)

    directors = await _create_category(guild, "Directors", _private_overwrites(guild, _roles_at_or_above(app, 4)))
    for name in ["director-chat", "director-reports", "approvals"]:
        created[name] = await _create_text(guild, directors, name)

    executive_names = set(app.ROLE_LEVEL_NAMES.get(5, set())) | {
        "Group Chief Operating Officer",
        "Ryanair DAC Chief Executive Officer",
        "Ryanair UK Chief Executive Officer",
        "Buzz Chief Executive Officer",
        "Malta Air Chief Executive Officer",
        "Lauda Europe Chief Executive Officer",
        "Executive Board",
    }
    executive = await _create_category(guild, "Executive", _private_overwrites(guild, executive_names))
    for name in ["executive-chat", "executive-decisions", "confidential"]:
        created[name] = await _create_text(guild, executive, name)

    # Department-specific rank locks.
    flight_roles = _department_access(app, {
        "Chief Pilot", "Chief Instructor, Safety", "Captain", "First Officer", "Cadet Pilot",
        "Flight Dispatcher", "Flight Operations Dispatcher", "Flight Operations Trainee",
        "Senior Management", "Base Manager", "European Bases Manager", "Base Supervisor",
    })
    flight = await _create_category(guild, "Flight Operations", _private_overwrites(guild, flight_roles))
    for name in ["flight-operations", "flight-dispatch", "crew-assignments", "flight-reports"]:
        created[name] = await _create_text(guild, flight, name)

    cabin_roles = _department_access(app, {
        "Director of Inflight", "Inflight Manager", "Senior Cabin Crew", "Cabin Crew", "Cabin Crew Trainee",
        "Training Manager", "Senior Management",
    })
    cabin = await _create_category(guild, "Cabin Operations", _private_overwrites(guild, cabin_roles))
    for name in ["cabin-operations", "cabin-crew-chat", "training-and-standards"]:
        created[name] = await _create_text(guild, cabin, name)

    ground_roles = _department_access(app, {
        "Director of Ground & Airport Operations", "Director of Ground Operations", "Ground & Airport Operations Manager",
        "Ground Operations Supervisor", "Ground Operations Agent", "Ground Operations Trainee", "Passenger Service Agent",
        "Gate Agent", "Ramp Agent", "Aircraft Engineer", "Engineer", "Aviation Security Officer", "Station Manager",
        "European Bases Manager", "Base Manager", "Base Supervisor", "Senior Management",
    })
    ground = await _create_category(guild, "Ground & Airport Operations", _private_overwrites(guild, ground_roles))
    for name in ["ground-operations", "airport-operations", "base-operations"]:
        created[name] = await _create_text(guild, ground, name)

    support_roles = _department_access(app, {
        "Director of Customer Service", "Customer Support Manager", "Customer Support Officer", "Customer Support Trainee",
        "Recruitment Manager", "Recruitment Assessor", "Senior Management",
    })
    support = await _create_category(guild, "Customer Support", _private_overwrites(guild, support_roles))
    for name in ["support-team", "ticket-management", "application-reviews"]:
        created[name] = await _create_text(guild, support, name)

    hr_roles = _department_access(app, {
        "Director of Talent", "Director of People & Recruitment", "Director of Recruitment & Human Resources",
        "Human Resources Manager", "Human Resources Officer", "Recruitment Manager", "Recruitment Assessor",
        "Recruitment Officer", "Training Manager", "Senior Management",
    })
    hr = await _create_category(guild, "People & Recruitment", _private_overwrites(guild, hr_roles))
    for name in ["human-resources", "recruitment-team", "training-team"]:
        created[name] = await _create_text(guild, hr, name)

    dev_roles = _department_access(app, {"Director of Digital Development", "Development Manager", "Developer", "Senior Management"})
    development = await _create_category(guild, "Development Team", _private_overwrites(guild, dev_roles))
    for name in ["development-team", "bot-development", "bug-reports"]:
        created[name] = await _create_text(guild, development, name)

    # Ticket channels created by the bot live here. Nobody public can browse it.
    ticket_category = await _create_category(guild, "Support Tickets", _private_overwrites(guild, support_roles))

    logs = await _create_category(guild, "Logs", _private_overwrites(guild, _roles_at_or_above(app, 4)))
    created["action-logs"] = await _create_text(guild, logs, "action-logs")
    created["moderation-logs"] = await _create_text(guild, logs, "moderation-logs")
    # Support team can see ticket transcripts without getting all moderation logs.
    created["ticket-logs"] = await _create_text(guild, logs, "ticket-logs", overwrites=_private_overwrites(guild, support_roles))

    return created, ticket_category


def _resolve_runtime_channels(app, guild: discord.Guild):
    by_name = {channel.name.casefold(): channel for channel in guild.channels}
    announcements = by_name.get("announcements")
    departures = by_name.get("departures")
    logs = by_name.get("action-logs") or by_name.get("moderation-logs")
    tickets_category = next((c for c in guild.categories if c.name.casefold() == "support tickets"), None)
    if announcements:
        app.ANNOUNCEMENT_CHANNEL_ID = announcements.id
    if departures:
        app.DEPARTURES_CHANNEL_ID = departures.id
    if logs:
        app.LOG_CHANNEL_ID = logs.id
    if tickets_category:
        app.TICKET_CATEGORY_ID = tickets_category.id


async def _on_ready_resolve(app):
    guild = app.bot.get_guild(app.GUILD_ID)
    if guild:
        _resolve_runtime_channels(app, guild)


def setup(app):
    if getattr(app, "_professional_layout_loaded", False):
        return
    app._professional_layout_loaded = True

    # Extend the rank model before slash commands begin handling permissions.
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

    @app_commands.command(
        name="setupserver",
        description="Rebuild the Ryanair server layout and rank locks (Owner only)",
    )
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
        required = me and me.guild_permissions.manage_channels and me.guild_permissions.manage_roles
        if not required:
            await interaction.followup.send(
                "The bot needs **Manage Channels** and **Manage Roles** before the full rebuild can run.",
                ephemeral=True,
            )
            return

        # Warn in DM before any destructive changes begin.
        try:
            await interaction.user.send(
                "Ryanair server rebuild started. Existing **Staff Hub** is being preserved; other channels/categories are being replaced."
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        created_roles, updated_roles, role_failures = await _ensure_roles(app, guild, interaction.user)
        preserve_ids = _staff_hub_preserve_set(guild)
        deleted, delete_failures = await _delete_old_channels(guild, preserve_ids, interaction.user)

        # Old ticket channel IDs are no longer valid after the rebuild.
        app.tickets.clear()
        app.connected_staff.clear()
        app.ticket_ai_active.clear()
        app.ticket_ai_history.clear()
        app.last_activity.clear()
        app.save_data()

        created_channels = {}
        layout_failure = None
        try:
            created_channels, ticket_category = await _build_layout(app, guild, preserve_ids)
            app.TICKET_CATEGORY_ID = ticket_category.id
            _resolve_runtime_channels(app, guild)
        except Exception as exc:
            layout_failure = f"{type(exc).__name__}: {exc}"

        summary = (
            "Ryanair server rebuild finished.\n\n"
            f"Roles created: **{len(created_roles)}**\n"
            f"Roles normalised: **{len(updated_roles)}**\n"
            f"Old channels/categories removed: **{len(deleted)}**\n"
            f"New channels created: **{len(created_channels)}**\n"
            f"Role issues: **{len(role_failures)}**\n"
            f"Delete issues: **{len(delete_failures)}**\n"
            f"Layout error: **{layout_failure or 'None'}**\n\n"
            "Staff Hub was preserved where found. Rank roles now use normal role permissions; private access is controlled by rank-locked categories."
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
    app.bot.add_listener(lambda: _on_ready_resolve(app), "on_ready")
    print("Professional server layout loaded: destructive /setupserver + rank locks.", flush=True)

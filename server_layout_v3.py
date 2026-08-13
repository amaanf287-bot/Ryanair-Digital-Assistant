"""Recovery-safe professional Ryanair Discord layout V3.

This version deliberately creates categories/channels without passing permission
overwrite kwargs, then applies permissions with set_permissions(). This avoids
Discord library compatibility failures during category creation.
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


def norm(value):
    return "".join(ch for ch in str(value).casefold() if ch.isalnum())


def role_named(guild, name):
    return discord.utils.get(guild.roles, name=name)


def find_role(guild, names):
    wanted = {norm(name) for name in names}
    return next((role for role in guild.roles if norm(role.name) in wanted), None)


def roles_at_or_above(app, minimum):
    names = set()
    for level in range(minimum, 6):
        names.update(app.ROLE_LEVEL_NAMES.get(level, set()))
    return names


def department_access(app, names):
    return set(names) | roles_at_or_above(app, 4)


async def ensure_roles(app, guild, actor):
    """Create/normalise rank roles using ordinary global permissions."""
    me = guild.me
    if not me or not me.guild_permissions.manage_roles:
        raise RuntimeError("The bot needs Manage Roles.")

    created, updated, failed = [], [], []
    ordinary = discord.Permissions.none()
    processed = set()

    for spec in app.ROLE_BLUEPRINTS:
        role = find_role(guild, spec.get("aliases", {spec["target"]}))
        if role is None and spec.get("create_if_missing", True):
            try:
                role = await guild.create_role(
                    name=spec["target"], colour=discord.Colour(spec["color"]),
                    permissions=ordinary, hoist=spec.get("hoist", False),
                    mentionable=spec.get("mentionable", False),
                    reason=f"Ryanair professional role setup by {actor}",
                )
                created.append(spec["target"])
            except (discord.Forbidden, discord.HTTPException) as exc:
                failed.append(f"{spec['target']}: {str(exc)[:100]}")
                continue
        if not role or role.id in processed:
            continue
        processed.add(role.id)
        if role.managed or role.is_default() or role >= me.top_role:
            continue
        try:
            old = role.name
            await role.edit(
                name=spec["target"], colour=discord.Colour(spec["color"]),
                permissions=ordinary, hoist=spec.get("hoist", False),
                mentionable=spec.get("mentionable", False),
                reason=f"Normal role permissions by {actor}",
            )
            if spec["target"] not in created:
                updated.append(spec["target"] if old == spec["target"] else f"{old} -> {spec['target']}")
        except (discord.Forbidden, discord.HTTPException) as exc:
            failed.append(f"{role.name}: {str(exc)[:100]}")

    for name, colour, hoist, mentionable in EXTRA_ROLES:
        role = role_named(guild, name)
        if role is None:
            try:
                await guild.create_role(
                    name=name, colour=discord.Colour(colour), permissions=ordinary,
                    hoist=hoist, mentionable=mentionable,
                    reason=f"Professional Ryanair role created by {actor}",
                )
                created.append(name)
            except (discord.Forbidden, discord.HTTPException) as exc:
                failed.append(f"{name}: {str(exc)[:100]}")
        elif not role.managed and not role.is_default() and role < me.top_role:
            try:
                await role.edit(colour=discord.Colour(colour), permissions=ordinary,
                                hoist=hoist, mentionable=mentionable,
                                reason=f"Normal role permissions by {actor}")
                updated.append(name)
            except (discord.Forbidden, discord.HTTPException) as exc:
                failed.append(f"{name}: {str(exc)[:100]}")

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


async def grant_bot(channel, guild):
    if guild.me:
        try:
            await channel.set_permissions(
                guild.me,
                view_channel=True, send_messages=True, read_message_history=True,
                manage_channels=True, manage_messages=True, embed_links=True,
                attach_files=True, add_reactions=True, connect=True, speak=True,
                reason="Ryanair bot access",
            )
        except (discord.Forbidden, discord.HTTPException):
            pass


async def apply_public(channel, guild, *, read_only=False):
    await channel.set_permissions(
        guild.default_role,
        view_channel=True, read_message_history=True,
        send_messages=False if read_only else True,
        add_reactions=True, connect=True, speak=True,
        reason="Ryanair public channel permissions",
    )
    await grant_bot(channel, guild)
    if read_only:
        # Directors+ can publish while the community remains read-only.
        for name in []:
            pass


async def apply_private(channel, guild, allowed_names, *, read_only=False):
    await channel.set_permissions(guild.default_role, view_channel=False, reason="Ryanair rank lock")
    await grant_bot(channel, guild)
    for name in sorted(set(allowed_names)):
        role = role_named(guild, name)
        if not role:
            continue
        try:
            await channel.set_permissions(
                role,
                view_channel=True, read_message_history=True,
                send_messages=False if read_only else True,
                add_reactions=True, use_application_commands=True,
                connect=True, speak=True,
                reason="Ryanair rank access",
            )
        except (discord.Forbidden, discord.HTTPException):
            continue


async def ensure_category(guild, name):
    existing = next((c for c in guild.categories if c.name.casefold() == name.casefold()), None)
    if existing:
        return existing, False
    category = await guild.create_category(name, reason="Professional Ryanair server layout")
    return category, True


async def ensure_text(guild, category, name, topic=None):
    existing = next((c for c in category.text_channels if c.name.casefold() == name.casefold()), None)
    if existing:
        if topic is not None and existing.topic != topic:
            try:
                await existing.edit(topic=topic, reason="Ryanair channel topic sync")
            except (discord.Forbidden, discord.HTTPException):
                pass
        return existing, False
    channel = await guild.create_text_channel(name, category=category, topic=topic,
                                              reason="Professional Ryanair server layout")
    return channel, True


async def ensure_voice(guild, category, name):
    existing = next((c for c in category.voice_channels if c.name.casefold() == name.casefold()), None)
    if existing:
        return existing, False
    channel = await guild.create_voice_channel(name, category=category,
                                               reason="Professional Ryanair server layout")
    return channel, True


async def make_public_category(guild, name, channels, made, *, category_read_only=False):
    category, new_cat = await ensure_category(guild, name)
    await apply_public(category, guild, read_only=category_read_only)
    if new_cat:
        made.append(f"[{name}]")
    for item in channels:
        if len(item) == 2:
            cname, topic = item
            read_only = category_read_only
        else:
            cname, topic, read_only = item
        channel, new_channel = await ensure_text(guild, category, cname, topic)
        await apply_public(channel, guild, read_only=read_only)
        if new_channel:
            made.append(cname)
    return category


async def make_private_category(guild, name, allowed_names, channel_names, made):
    category, new_cat = await ensure_category(guild, name)
    await apply_private(category, guild, allowed_names)
    if new_cat:
        made.append(f"[{name}]")
    for cname in channel_names:
        channel, new_channel = await ensure_text(guild, category, cname)
        # Explicitly apply as well so old unsynchronised overrides cannot leak access.
        await apply_private(channel, guild, allowed_names)
        if new_channel:
            made.append(cname)
    return category


async def build_layout(app, guild):
    made = []

    await make_public_category(guild, "Verification", [
        ("verify-help", "Help with server verification."),
        ("verify", "Complete server verification here."),
    ], made)

    await make_public_category(guild, "Information", [
        ("rules", "Official community rules.", True),
        ("information", "Ryanair Roblox community information.", True),
        ("ryanair-help", "Frequently asked questions and help.", False),
        ("travel-assistant", "Travel and community assistance.", False),
    ], made)

    await make_public_category(guild, "Bulletin", [
        ("announcements", "Official Ryanair community announcements.", True),
        ("press-releases", "Official press releases and major updates.", True),
        ("development", "Development progress and release notes.", True),
        ("careers", "Staffing and application notices.", True),
        ("off-topic-announcements", "Optional off-topic announcements.", True),
        ("boosters", "Server booster recognition and updates.", True),
        ("departures", "Live passenger flight departures and updates.", True),
    ], made)

    await make_public_category(guild, "Public", [
        ("chat", "Main community chat."),
        ("photo-gallery", "Community aviation images."),
        ("aviation", "Aviation discussion."),
        ("bot-commands", "Use bot commands here to keep chat clean."),
    ], made)

    await make_public_category(guild, "Community", [
        ("community-events", "Community event notices.", True),
        ("community-posts", "Community posts and discussion.", False),
    ], made)

    voice, new_voice_cat = await ensure_category(guild, "Community Voice")
    await apply_public(voice, guild)
    if new_voice_cat:
        made.append("[Community Voice]")
    for name in ("Voice Chat", "Voice Chat 2"):
        vc, created = await ensure_voice(guild, voice, name)
        await apply_public(vc, guild)
        if created:
            made.append(name)

    await make_private_category(guild, "Recruitment & Training", roles_at_or_above(app, 1),
                                ["talent-pool", "trainee-hub", "training-information", "recruitment-updates"], made)

    # Preserve any existing Staff Hub category and its existing content.
    staff_category = next((c for c in guild.categories if norm(c.name) == "staffhub"), None)
    if staff_category is None:
        staff_category, created = await ensure_category(guild, "Staff Hub")
        if created:
            made.append("[Staff Hub]")
    staff_access = roles_at_or_above(app, 2)
    await apply_private(staff_category, guild, staff_access)
    for existing in list(staff_category.channels):
        await apply_private(existing, guild, staff_access)
    for name in ("staff-announcements", "staff-chat", "staff-commands", "staff-resources"):
        channel, created = await ensure_text(guild, staff_category, name)
        await apply_private(channel, guild, staff_access)
        if created:
            made.append(name)

    await make_private_category(guild, "Management", roles_at_or_above(app, 3),
                                ["management-chat", "staffing", "operations-planning"], made)
    await make_private_category(guild, "Directors", roles_at_or_above(app, 4),
                                ["director-chat", "director-reports", "approvals"], made)

    executive_access = set(app.ROLE_LEVEL_NAMES.get(5, set())) | {
        "Group Chief Operating Officer", "Ryanair DAC Chief Executive Officer",
        "Ryanair UK Chief Executive Officer", "Buzz Chief Executive Officer",
        "Malta Air Chief Executive Officer", "Lauda Europe Chief Executive Officer", "Executive Board",
    }
    await make_private_category(guild, "Executive", executive_access,
                                ["executive-chat", "executive-decisions", "confidential"], made)

    flight_access = department_access(app, {
        "Chief Pilot", "Chief Instructor, Safety", "Captain", "First Officer", "Cadet Pilot",
        "Flight Dispatcher", "Flight Operations Dispatcher", "Flight Operations Trainee",
        "Senior Management", "Base Manager", "European Bases Manager", "Base Supervisor",
    })
    await make_private_category(guild, "Flight Operations", flight_access,
                                ["flight-operations", "flight-dispatch", "crew-assignments", "flight-reports"], made)

    cabin_access = department_access(app, {
        "Director of Inflight", "Inflight Manager", "Senior Cabin Crew", "Cabin Crew", "Cabin Crew Trainee",
        "Training Manager", "Senior Management",
    })
    await make_private_category(guild, "Cabin Operations", cabin_access,
                                ["cabin-operations", "cabin-crew-chat", "training-and-standards"], made)

    ground_access = department_access(app, {
        "Director of Ground & Airport Operations", "Director of Ground Operations", "Ground & Airport Operations Manager",
        "Ground Operations Supervisor", "Ground Operations Agent", "Ground Operations Trainee", "Passenger Service Agent",
        "Gate Agent", "Ramp Agent", "Aircraft Engineer", "Engineer", "Aviation Security Officer", "Station Manager",
        "European Bases Manager", "Base Manager", "Base Supervisor", "Senior Management",
    })
    await make_private_category(guild, "Ground & Airport Operations", ground_access,
                                ["ground-operations", "airport-operations", "base-operations"], made)

    support_access = department_access(app, {
        "Director of Customer Service", "Customer Support Manager", "Customer Support Officer", "Customer Support Trainee",
        "Recruitment Manager", "Recruitment Assessor", "Senior Management",
    })
    await make_private_category(guild, "Customer Support", support_access,
                                ["support-team", "ticket-management", "application-reviews"], made)

    people_access = department_access(app, {
        "Director of Talent", "Director of People & Recruitment", "Director of Recruitment & Human Resources",
        "Human Resources Manager", "Human Resources Officer", "Recruitment Manager", "Recruitment Assessor",
        "Recruitment Officer", "Training Manager", "Senior Management",
    })
    await make_private_category(guild, "People & Recruitment", people_access,
                                ["human-resources", "recruitment-team", "training-team"], made)

    dev_access = department_access(app, {
        "Director of Digital Development", "Development Manager", "Developer", "Senior Management",
    })
    await make_private_category(guild, "Development Team", dev_access,
                                ["development-team", "bot-development", "bug-reports"], made)

    ticket_category, ticket_created = await ensure_category(guild, "Support Tickets")
    await apply_private(ticket_category, guild, support_access)
    if ticket_created:
        made.append("[Support Tickets]")

    log_access = roles_at_or_above(app, 4)
    logs, logs_created = await ensure_category(guild, "Logs")
    await apply_private(logs, guild, log_access)
    if logs_created:
        made.append("[Logs]")
    for name in ("action-logs", "moderation-logs"):
        channel, created = await ensure_text(guild, logs, name)
        await apply_private(channel, guild, log_access)
        if created:
            made.append(name)
    ticket_logs, created = await ensure_text(guild, logs, "ticket-logs")
    await apply_private(ticket_logs, guild, support_access)
    if created:
        made.append("ticket-logs")

    return made, ticket_category


def resolve_runtime_channels(app, guild):
    by_name = {channel.name.casefold(): channel for channel in guild.text_channels}
    if by_name.get("announcements"):
        app.ANNOUNCEMENT_CHANNEL_ID = by_name["announcements"].id
    if by_name.get("departures"):
        app.DEPARTURES_CHANNEL_ID = by_name["departures"].id
    if by_name.get("action-logs"):
        app.LOG_CHANNEL_ID = by_name["action-logs"].id
        app.ACTION_LOG_CHANNEL_ID = by_name["action-logs"].id
    if by_name.get("moderation-logs"):
        app.MODERATION_LOG_CHANNEL_ID = by_name["moderation-logs"].id
    if by_name.get("ticket-logs"):
        app.TICKET_LOG_CHANNEL_ID = by_name["ticket-logs"].id
    ticket_category = next((c for c in guild.categories if c.name.casefold() == "support tickets"), None)
    if ticket_category:
        app.TICKET_CATEGORY_ID = ticket_category.id


async def delete_non_staffhub_channels(guild, actor):
    """Requested destructive cleanup; only used by explicit /setupserver."""
    preserve_categories = {c.id for c in guild.categories if norm(c.name) == "staffhub"}
    preserve_channels = set()
    for category in guild.categories:
        if category.id in preserve_categories:
            preserve_channels.update(c.id for c in category.channels)
    preserve_channels.update(c.id for c in guild.channels if not isinstance(c, discord.CategoryChannel) and norm(c.name) == "staffhub")

    deleted, failed = [], []
    for channel in [c for c in list(guild.channels) if not isinstance(c, discord.CategoryChannel)]:
        if channel.id in preserve_channels:
            continue
        try:
            deleted.append(channel.name)
            await channel.delete(reason=f"Full Ryanair rebuild by {actor}; Staff Hub preserved")
            await asyncio.sleep(0.08)
        except (discord.Forbidden, discord.HTTPException) as exc:
            failed.append(f"{channel.name}: {str(exc)[:90]}")
    for category in list(guild.categories):
        if category.id in preserve_categories:
            continue
        try:
            deleted.append(category.name)
            await category.delete(reason=f"Full Ryanair rebuild by {actor}; Staff Hub preserved")
            await asyncio.sleep(0.08)
        except (discord.Forbidden, discord.HTTPException) as exc:
            failed.append(f"{category.name}: {str(exc)[:90]}")
    return deleted, failed


async def recover_if_missing(app):
    """Repair the failed V2 deletion automatically after deployment, without deleting again."""
    guild = app.bot.get_guild(app.GUILD_ID)
    if not guild or not guild.me:
        return
    if not guild.me.guild_permissions.manage_channels:
        return
    # Only auto-recover when the expected public layout is clearly absent.
    has_verification = any(c.name.casefold() == "verification" for c in guild.categories)
    has_public = any(c.name.casefold() == "public" for c in guild.categories)
    if has_verification and has_public:
        resolve_runtime_channels(app, guild)
        return
    try:
        made, ticket_category = await build_layout(app, guild)
        app.TICKET_CATEGORY_ID = ticket_category.id
        resolve_runtime_channels(app, guild)
        print(f"SERVER RECOVERY COMPLETE: created/repaired {len(made)} layout items.", flush=True)
        if guild.owner:
            try:
                await guild.owner.send(
                    f"Ryanair server recovery completed automatically. Created/repaired **{len(made)}** categories/channels after the failed V2 rebuild."
                )
            except (discord.Forbidden, discord.HTTPException):
                pass
    except Exception as exc:
        print(f"SERVER RECOVERY FAILED: {type(exc).__name__}: {exc}", flush=True)
        if guild.owner:
            try:
                await guild.owner.send(f"Ryanair server recovery failed: `{type(exc).__name__}: {exc}`")
            except (discord.Forbidden, discord.HTTPException):
                pass


def setup(app):
    if getattr(app, "_professional_layout_v3_loaded", False):
        return
    app._professional_layout_v3_loaded = True

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
    async def setupserver(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not app.is_server_owner(interaction.user):
            await interaction.followup.send("Only the server owner can run `/setupserver`.", ephemeral=True)
            return
        guild = interaction.guild
        me = guild.me if guild else None
        if not guild or not me or not me.guild_permissions.manage_channels or not me.guild_permissions.manage_roles:
            await interaction.followup.send("The bot needs **Manage Channels** and **Manage Roles**.", ephemeral=True)
            return

        created_roles, updated_roles, role_failures = await ensure_roles(app, guild, interaction.user)
        deleted, delete_failures = await delete_non_staffhub_channels(guild, interaction.user)

        app.tickets.clear()
        app.connected_staff.clear()
        app.ticket_ai_active.clear()
        app.ticket_ai_history.clear()
        app.last_activity.clear()
        app.save_data()

        layout_error = None
        made = []
        try:
            made, ticket_category = await build_layout(app, guild)
            app.TICKET_CATEGORY_ID = ticket_category.id
            resolve_runtime_channels(app, guild)
        except Exception as exc:
            layout_error = f"{type(exc).__name__}: {exc}"

        summary = (
            "Ryanair server rebuild finished.\n\n"
            f"Roles created: **{len(created_roles)}**\n"
            f"Roles normalised: **{len(updated_roles)}**\n"
            f"Old channels/categories removed: **{len(deleted)}**\n"
            f"New/repaired layout items: **{len(made)}**\n"
            f"Role issues: **{len(role_failures)}**\n"
            f"Delete issues: **{len(delete_failures)}**\n"
            f"Layout error: **{layout_error or 'None'}**"
        )
        try:
            await interaction.user.send(summary)
        except (discord.Forbidden, discord.HTTPException):
            pass
        try:
            await interaction.followup.send(summary, ephemeral=True)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    app.tree.add_command(setupserver, guild=guild_obj, override=True)

    async def on_ready_recover():
        # Give the main on_ready a moment to finish loading state first.
        await asyncio.sleep(3)
        await recover_if_missing(app)

    app.bot.add_listener(on_ready_recover, "on_ready")
    print("Professional server layout V3 loaded: compatibility-safe recovery + rank locks.", flush=True)

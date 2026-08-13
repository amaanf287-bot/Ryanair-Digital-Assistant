"""Recovery-safe Ryanair server layout V4.

V4 never deletes channels automatically. It repairs/creates the requested layout in stages:
1) create/verify categories,
2) apply category rank locks,
3) create channels uncategorised and then move/sync them into verified categories,
4) resolve runtime channel IDs.

This avoids the stale parent/category errors seen in the earlier rebuild.
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
    1: {"Trainee", "Cabin Crew Trainee", "Ground Operations Trainee",
        "Customer Support Trainee", "Flight Operations Trainee"},
}

EXTRA_ROLES = [
    ("Chief Pilot", 0x0EA5E9, True),
    ("Chief Instructor, Safety", 0x38BDF8, True),
    ("Director of Ground Operations", 0x15803D, True),
    ("Director of Customer Service", 0x0284C7, True),
    ("Director of Talent", 0xDB2777, True),
    ("Director of Recruitment & Human Resources", 0xEC4899, True),
    ("Director of Community", 0xA855F7, True),
    ("European Bases Manager", 0xF6E7A7, True),
    ("Base Supervisor", 0xF59E0B, True),
    ("Human Resources Manager", 0xDB2777, True),
    ("Flight Dispatcher", 0x0EA5E9, False),
    ("Engineer", 0x64748B, False),
    ("Human Resources Officer", 0xF472B6, False),
    ("Community Engagement Officer", 0x3B82F6, False),
    ("Trainee", 0xF9A8D4, False),
    ("Cabin Crew Trainee", 0xC4B5FD, False),
    ("Ground Operations Trainee", 0x86EFAC, False),
    ("Customer Support Trainee", 0x7DD3FC, False),
    ("Flight Operations Trainee", 0xFDE68A, False),
    ("Verified", 0x23C483, False),
    ("Directors", 0x0B6E99, False),
    ("Staff", 0xC7F000, False),
    ("Bloxlink Updater", 0xE23B45, False),
    ("Community Announcements", 0xFFB000, False),
    ("Off Topic Announcements", 0xFFB000, False),
    ("QOTD Announcements", 0xFFB000, False),
    ("Music Channels", 0x9CA3AF, False),
]


def norm(value):
    return "".join(ch for ch in str(value).casefold() if ch.isalnum())


def role_named(guild, name):
    return discord.utils.get(guild.roles, name=name)


def roles_at_or_above(app, minimum):
    out = set()
    for level in range(minimum, 6):
        out.update(app.ROLE_LEVEL_NAMES.get(level, set()))
    return out


def department_access(app, names):
    return set(names) | roles_at_or_above(app, 4)


async def fresh_channels(guild):
    try:
        return await guild.fetch_channels()
    except (discord.Forbidden, discord.HTTPException):
        return list(guild.channels)


async def fresh_category(guild, name):
    channels = await fresh_channels(guild)
    wanted = norm(name)
    return next(
        (ch for ch in channels if isinstance(ch, discord.CategoryChannel) and norm(ch.name) == wanted),
        None,
    )


async def ensure_category(guild, name, made, errors):
    category = await fresh_category(guild, name)
    if category:
        return category
    try:
        created = await guild.create_category(name, reason="Ryanair professional layout V4")
        made.append(f"[{name}]")
        await asyncio.sleep(0.35)
        fresh = await fresh_category(guild, name)
        return fresh or created
    except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
        errors.append(f"{name} category: {type(exc).__name__}: {str(exc)[:140]}")
        return None


def desired_private_overwrite(read_only=False):
    return discord.PermissionOverwrite(
        view_channel=True,
        read_message_history=True,
        send_messages=False if read_only else True,
        add_reactions=True,
        use_application_commands=True,
        send_messages_in_threads=False if read_only else True,
        create_public_threads=False if read_only else True,
        connect=True,
        speak=True,
    )


async def grant_bot(target, guild):
    if not guild.me:
        return
    try:
        await target.set_permissions(
            guild.me,
            view_channel=True,
            read_message_history=True,
            send_messages=True,
            send_messages_in_threads=True,
            manage_channels=True,
            manage_messages=True,
            embed_links=True,
            attach_files=True,
            add_reactions=True,
            use_application_commands=True,
            connect=True,
            speak=True,
            reason="Ryanair bot access",
        )
    except (discord.Forbidden, discord.HTTPException):
        pass


async def set_public(target, guild, *, read_only=False, director_names=None):
    try:
        await target.set_permissions(
            guild.default_role,
            view_channel=True,
            read_message_history=True,
            send_messages=False if read_only else True,
            add_reactions=True,
            connect=True,
            speak=True,
            reason="Ryanair public access",
        )
    except (discord.Forbidden, discord.HTTPException):
        pass
    await grant_bot(target, guild)

    if read_only and director_names:
        for name in sorted(director_names):
            role = role_named(guild, name)
            if not role:
                continue
            try:
                await target.set_permissions(
                    role,
                    view_channel=True,
                    read_message_history=True,
                    send_messages=True,
                    add_reactions=True,
                    use_application_commands=True,
                    reason="Ryanair bulletin publisher access",
                )
            except (discord.Forbidden, discord.HTTPException):
                pass


async def set_private(target, guild, allowed_names, *, read_only=False, errors=None):
    try:
        await target.set_permissions(
            guild.default_role,
            view_channel=False,
            reason="Ryanair rank lock",
        )
    except (discord.Forbidden, discord.HTTPException) as exc:
        if errors is not None:
            errors.append(f"{getattr(target, 'name', 'channel')} @everyone lock: {str(exc)[:120]}")
    await grant_bot(target, guild)

    desired = desired_private_overwrite(read_only)
    for name in sorted(set(allowed_names)):
        role = role_named(guild, name)
        if not role:
            continue
        try:
            await target.set_permissions(role, overwrite=desired, reason="Ryanair rank access")
        except (discord.Forbidden, discord.HTTPException) as exc:
            if errors is not None:
                errors.append(f"{getattr(target, 'name', 'channel')} -> {name}: {str(exc)[:100]}")


async def ensure_extra_roles(guild, errors):
    me = guild.me
    if not me or not me.guild_permissions.manage_roles:
        return
    none = discord.Permissions.none()
    for name, colour, hoist in EXTRA_ROLES:
        if role_named(guild, name):
            continue
        try:
            await guild.create_role(
                name=name,
                colour=discord.Colour(colour),
                permissions=none,
                hoist=hoist,
                mentionable=False,
                reason="Ryanair professional role recovery V4",
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"role {name}: {str(exc)[:100]}")


async def find_text_anywhere(guild, name):
    channels = await fresh_channels(guild)
    wanted = name.casefold()
    return next((ch for ch in channels if isinstance(ch, discord.TextChannel) and ch.name.casefold() == wanted), None)


async def find_voice_anywhere(guild, name):
    channels = await fresh_channels(guild)
    wanted = name.casefold()
    return next((ch for ch in channels if isinstance(ch, discord.VoiceChannel) and ch.name.casefold() == wanted), None)


async def verified_category(guild, name):
    category = await fresh_category(guild, name)
    if category:
        return category
    await asyncio.sleep(0.4)
    return await fresh_category(guild, name)


async def move_text_to_category(channel, guild, category_name, errors):
    category = await verified_category(guild, category_name)
    if not category:
        errors.append(f"{channel.name}: verified category {category_name} missing")
        return False
    if channel.category_id == category.id:
        return True
    try:
        await channel.edit(category=category, sync_permissions=True, reason="Ryanair V4 category placement")
        return True
    except TypeError:
        try:
            await channel.edit(category=category, reason="Ryanair V4 category placement")
            return True
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"{channel.name} move: {str(exc)[:140]}")
            return False
    except (discord.Forbidden, discord.HTTPException):
        await asyncio.sleep(0.5)
        category = await verified_category(guild, category_name)
        if not category:
            errors.append(f"{channel.name}: {category_name} disappeared before move")
            return False
        try:
            await channel.edit(category=category, sync_permissions=True, reason="Ryanair V4 placement retry")
            return True
        except TypeError:
            try:
                await channel.edit(category=category, reason="Ryanair V4 placement retry")
                return True
            except (discord.Forbidden, discord.HTTPException) as exc:
                errors.append(f"{channel.name} move retry: {str(exc)[:140]}")
                return False
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"{channel.name} move retry: {str(exc)[:140]}")
            return False


async def ensure_text(guild, category_name, name, topic, made, errors):
    channel = await find_text_anywhere(guild, name)
    if channel is None:
        try:
            channel = await guild.create_text_channel(
                name,
                topic=topic,
                reason="Ryanair professional layout V4",
            )
            made.append(name)
        except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
            errors.append(f"{name} create: {type(exc).__name__}: {str(exc)[:140]}")
            return None

    if topic is not None and getattr(channel, "topic", None) != topic:
        try:
            await channel.edit(topic=topic, reason="Ryanair channel topic sync")
        except (discord.Forbidden, discord.HTTPException):
            pass

    await move_text_to_category(channel, guild, category_name, errors)
    return channel


async def move_voice_to_category(channel, guild, category_name, errors):
    category = await verified_category(guild, category_name)
    if not category:
        errors.append(f"{channel.name}: verified category {category_name} missing")
        return False
    if channel.category_id == category.id:
        return True
    try:
        await channel.edit(category=category, sync_permissions=True, reason="Ryanair V4 voice placement")
        return True
    except TypeError:
        try:
            await channel.edit(category=category, reason="Ryanair V4 voice placement")
            return True
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"{channel.name} move: {str(exc)[:140]}")
            return False
    except (discord.Forbidden, discord.HTTPException) as exc:
        errors.append(f"{channel.name} move: {str(exc)[:140]}")
        return False


async def ensure_voice(guild, category_name, name, made, errors):
    channel = await find_voice_anywhere(guild, name)
    if channel is None:
        try:
            channel = await guild.create_voice_channel(name, reason="Ryanair professional layout V4")
            made.append(name)
        except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
            errors.append(f"{name} create: {type(exc).__name__}: {str(exc)[:140]}")
            return None
    await move_voice_to_category(channel, guild, category_name, errors)
    return channel


def build_specs(app):
    directors = roles_at_or_above(app, 4)
    level1 = roles_at_or_above(app, 1)
    level2 = roles_at_or_above(app, 2)
    level3 = roles_at_or_above(app, 3)
    level4 = directors

    executive = set(app.ROLE_LEVEL_NAMES.get(5, set())) | {
        "Group Chief Operating Officer", "Ryanair DAC Chief Executive Officer",
        "Ryanair UK Chief Executive Officer", "Buzz Chief Executive Officer",
        "Malta Air Chief Executive Officer", "Lauda Europe Chief Executive Officer", "Executive Board",
    }

    flight = department_access(app, {
        "Chief Pilot", "Chief Instructor, Safety", "Captain", "First Officer", "Cadet Pilot",
        "Flight Dispatcher", "Flight Operations Dispatcher", "Flight Operations Trainee",
        "Senior Management", "Base Manager", "European Bases Manager", "Base Supervisor",
    })
    cabin = department_access(app, {
        "Director of Inflight", "Inflight Manager", "Senior Cabin Crew", "Cabin Crew",
        "Cabin Crew Trainee", "Training Manager", "Senior Management",
    })
    ground = department_access(app, {
        "Director of Ground & Airport Operations", "Director of Ground Operations",
        "Ground & Airport Operations Manager", "Ground Operations Supervisor",
        "Ground Operations Agent", "Ground Operations Trainee", "Passenger Service Agent",
        "Gate Agent", "Ramp Agent", "Aircraft Engineer", "Engineer",
        "Aviation Security Officer", "Station Manager", "European Bases Manager",
        "Base Manager", "Base Supervisor", "Senior Management",
    })
    support = department_access(app, {
        "Director of Customer Service", "Customer Support Manager", "Customer Support Officer",
        "Customer Support Trainee", "Recruitment Manager", "Recruitment Assessor", "Senior Management",
    })
    people = department_access(app, {
        "Director of Talent", "Director of People & Recruitment",
        "Director of Recruitment & Human Resources", "Human Resources Manager",
        "Human Resources Officer", "Recruitment Manager", "Recruitment Assessor",
        "Recruitment Officer", "Training Manager", "Senior Management",
    })
    development = department_access(app, {
        "Director of Digital Development", "Development Manager", "Developer", "Senior Management",
    })

    return [
        {"name": "Verification", "mode": "public", "channels": [
            ("verify-help", "Help with server verification.", False),
            ("verify", "Complete server verification here.", False),
        ]},
        {"name": "Information", "mode": "public", "channels": [
            ("rules", "Official community rules.", True),
            ("information", "Ryanair Roblox community information.", True),
            ("ryanair-help", "Frequently asked questions and help.", False),
            ("travel-assistant", "Travel and community assistance.", False),
        ]},
        {"name": "Bulletin", "mode": "public", "channels": [
            ("announcements", "Official Ryanair community announcements.", True),
            ("press-releases", "Official press releases and major updates.", True),
            ("development", "Development progress and release notes.", True),
            ("careers", "Staffing and application notices.", True),
            ("off-topic-announcements", "Optional off-topic announcements.", True),
            ("boosters", "Server booster recognition and updates.", True),
            ("departures", "Live passenger flight departures and updates.", True),
        ]},
        {"name": "Public", "mode": "public", "channels": [
            ("chat", "Main community chat.", False),
            ("photo-gallery", "Community aviation images.", False),
            ("aviation", "Aviation discussion.", False),
            ("bot-commands", "Use bot commands here to keep chat clean.", False),
        ]},
        {"name": "Community", "mode": "public", "channels": [
            ("community-events", "Community event notices.", True),
            ("community-posts", "Community posts and discussion.", False),
        ]},
        {"name": "Community Voice", "mode": "public", "voice": ["Voice Chat", "Voice Chat 2"]},
        {"name": "Recruitment & Training", "mode": "private", "access": level1,
         "channels": [("talent-pool", None, False), ("trainee-hub", None, False),
                      ("training-information", None, False), ("recruitment-updates", None, False)]},
        {"name": "Staff Hub", "mode": "private", "access": level2, "preserve_children": True,
         "channels": [("staff-announcements", None, False), ("staff-chat", None, False),
                      ("staff-commands", None, False), ("staff-resources", None, False)]},
        {"name": "Management", "mode": "private", "access": level3,
         "channels": [("management-chat", None, False), ("staffing", None, False),
                      ("operations-planning", None, False)]},
        {"name": "Directors", "mode": "private", "access": level4,
         "channels": [("director-chat", None, False), ("director-reports", None, False),
                      ("approvals", None, False)]},
        {"name": "Executive", "mode": "private", "access": executive,
         "channels": [("executive-chat", None, False), ("executive-decisions", None, False),
                      ("confidential", None, False)]},
        {"name": "Flight Operations", "mode": "private", "access": flight,
         "channels": [("flight-operations", None, False), ("flight-dispatch", None, False),
                      ("crew-assignments", None, False), ("flight-reports", None, False)]},
        {"name": "Cabin Operations", "mode": "private", "access": cabin,
         "channels": [("cabin-operations", None, False), ("cabin-crew-chat", None, False),
                      ("training-and-standards", None, False)]},
        {"name": "Ground & Airport Operations", "mode": "private", "access": ground,
         "channels": [("ground-operations", None, False), ("airport-operations", None, False),
                      ("base-operations", None, False)]},
        {"name": "Customer Support", "mode": "private", "access": support,
         "channels": [("support-team", None, False), ("ticket-management", None, False),
                      ("application-reviews", None, False)]},
        {"name": "People & Recruitment", "mode": "private", "access": people,
         "channels": [("human-resources", None, False), ("recruitment-team", None, False),
                      ("training-team", None, False)]},
        {"name": "Development Team", "mode": "private", "access": development,
         "channels": [("development-team", None, False), ("bot-development", None, False),
                      ("bug-reports", None, False)]},
        {"name": "Support Tickets", "mode": "private", "access": support, "channels": []},
        {"name": "Logs", "mode": "private", "access": directors,
         "channels": [("action-logs", None, False), ("moderation-logs", None, False),
                      ("ticket-logs", None, False)], "ticket_log_access": support},
    ]


async def repair_layout(app, guild):
    made, errors = [], []
    await ensure_extra_roles(guild, errors)
    specs = build_specs(app)

    categories = {}
    for spec in specs:
        category = await ensure_category(guild, spec["name"], made, errors)
        if category:
            categories[spec["name"]] = category

    await asyncio.sleep(1.0)
    for name in list(categories):
        fresh = await fresh_category(guild, name)
        if fresh:
            categories[name] = fresh
        else:
            errors.append(f"{name}: category not visible after creation")
            categories.pop(name, None)

    directors = roles_at_or_above(app, 4)
    for spec in specs:
        category = categories.get(spec["name"])
        if not category:
            continue
        if spec["mode"] == "public":
            await set_public(category, guild, read_only=False, director_names=directors)
        else:
            await set_private(category, guild, spec.get("access", set()), errors=errors)

    for spec in specs:
        category = categories.get(spec["name"])
        if not category:
            continue

        if spec.get("preserve_children"):
            for child in list(getattr(category, "channels", [])):
                try:
                    await child.edit(sync_permissions=True, reason="Ryanair Staff Hub rank-lock sync")
                except TypeError:
                    await set_private(child, guild, spec["access"], errors=errors)
                except (discord.Forbidden, discord.HTTPException):
                    await set_private(child, guild, spec["access"], errors=errors)

        for cname, topic, read_only in spec.get("channels", []):
            channel = await ensure_text(guild, spec["name"], cname, topic, made, errors)
            if channel is None:
                continue

            if spec["mode"] == "public" and read_only:
                await set_public(channel, guild, read_only=True, director_names=directors)
            elif spec["name"] == "Logs" and cname == "ticket-logs":
                await set_private(channel, guild, spec.get("ticket_log_access", set()), errors=errors)
            else:
                fresh_cat = await fresh_category(guild, spec["name"])
                if fresh_cat and channel.category_id == fresh_cat.id:
                    try:
                        await channel.edit(sync_permissions=True, reason="Ryanair permission sync")
                    except TypeError:
                        if spec["mode"] == "public":
                            await set_public(channel, guild, director_names=directors)
                        else:
                            await set_private(channel, guild, spec.get("access", set()), errors=errors)
                    except (discord.Forbidden, discord.HTTPException):
                        if spec["mode"] == "public":
                            await set_public(channel, guild, director_names=directors)
                        else:
                            await set_private(channel, guild, spec.get("access", set()), errors=errors)

        for vname in spec.get("voice", []):
            voice = await ensure_voice(guild, spec["name"], vname, made, errors)
            if voice:
                try:
                    await voice.edit(sync_permissions=True, reason="Ryanair voice permission sync")
                except TypeError:
                    if spec["mode"] == "public":
                        await set_public(voice, guild, director_names=directors)
                    else:
                        await set_private(voice, guild, spec.get("access", set()), errors=errors)
                except (discord.Forbidden, discord.HTTPException):
                    pass

    resolve_runtime_channels(app, guild)
    return made, errors


def resolve_runtime_channels(app, guild):
    by_name = {ch.name.casefold(): ch for ch in guild.text_channels}
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
    ticket_category = next((c for c in guild.categories if norm(c.name) == norm("Support Tickets")), None)
    if ticket_category:
        app.TICKET_CATEGORY_ID = ticket_category.id


async def run_repair(app, *, notify_owner=True):
    if getattr(app, "_v4_repair_running", False):
        return None
    app._v4_repair_running = True
    try:
        guild = app.bot.get_guild(app.GUILD_ID)
        if not guild or not guild.me:
            return None
        if not guild.me.guild_permissions.manage_channels:
            return None

        made, errors = await repair_layout(app, guild)
        resolve_runtime_channels(app, guild)
        print(
            f"SERVER LAYOUT V4 REPAIR: made={len(made)} errors={len(errors)}",
            flush=True,
        )

        if notify_owner and guild.owner and (made or errors):
            text = (
                f"Ryanair server layout V4 finished.\n\n"
                f"New/repaired items created: **{len(made)}**\n"
                f"Permission/layout issues: **{len(errors)}**\n"
                f"All private categories were processed with rank locks."
            )
            if errors:
                text += "\n\nFirst issues:\n" + "\n".join(f"- {item[:160]}" for item in errors[:8])
            try:
                await guild.owner.send(text)
            except (discord.Forbidden, discord.HTTPException):
                pass
        return made, errors
    finally:
        app._v4_repair_running = False


def setup(app):
    if getattr(app, "_professional_layout_v4_loaded", False):
        return
    app._professional_layout_v4_loaded = True

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
        description="Repair/sync Ryanair channels, roles and rank locks (Owner only)",
    )
    async def setupserver_v4(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not app.is_server_owner(interaction.user):
            await interaction.followup.send("Only the server owner can run `/setupserver`.", ephemeral=True)
            return
        guild = interaction.guild
        if not guild or not guild.me:
            await interaction.followup.send("Run this inside the Ryanair server.", ephemeral=True)
            return
        if not guild.me.guild_permissions.manage_channels or not guild.me.guild_permissions.manage_roles:
            await interaction.followup.send(
                "The bot needs **Manage Channels** and **Manage Roles**.",
                ephemeral=True,
            )
            return

        made, errors = await repair_layout(app, guild)
        await interaction.followup.send(
            f"Server sync complete. New/repaired items: **{len(made)}**. "
            f"Issues: **{len(errors)}**. No channels were deleted.",
            ephemeral=True,
        )

    app.tree.add_command(setupserver_v4, guild=guild_obj, override=True)

    async def on_ready_v4():
        await asyncio.sleep(5)
        await run_repair(app, notify_owner=True)

    app.bot.add_listener(on_ready_v4, "on_ready")
    print("Professional server layout V4 loaded: staged recovery + rank locks, no auto-delete.", flush=True)

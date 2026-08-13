"""Ryanair professional Discord layout V7.

V7 keeps the clean public layout and ONE private Staff Hub. It uses the actual
rank/job roles for every managed private channel (no dependency on generic Staff
or Directors tag roles), converts the reference-style bulletin channels to real
Discord Announcement/news channels where the guild supports them, and applies
permission overwrites in bulk for speed.

Safety: V7 never deletes channels. It may remove ONLY an empty, known legacy
category created by the older layout versions after confirming it has no child
channels.
"""

import asyncio
import discord
from discord import app_commands
import server_layout_v4 as base


ANNOUNCEMENT_CHANNELS = {
    "announcements",
    "press-releases",
    "development",
    "careers",
    "off-topic-announcements",
}

PUBLIC_LAYOUT = {
    "Verification": [
        ("verify-help", "Help with server verification.", False),
        ("verify", "Complete server verification here.", False),
    ],
    "Information": [
        ("rules", "Official community rules.", True),
        ("information", "Ryanair Roblox community information.", True),
        ("ryanair-help", "Frequently asked questions and help.", False),
        ("travel-assistant", "Travel and community assistance.", False),
    ],
    "Bulletin": [
        ("announcements", "Official Ryanair community announcements.", True),
        ("press-releases", "Official press releases and major updates.", True),
        ("development", "Development progress and release notes.", True),
        ("careers", "Staffing and application notices.", True),
        ("off-topic-announcements", "Optional off-topic announcements.", True),
        ("boosters", "Server booster recognition and updates.", True),
        ("departures", "Live passenger flight departures and updates.", True),
    ],
    "Public": [
        ("chat", "Main community chat.", False),
        ("photo-gallery", "Community aviation images.", False),
        ("aviation", "Aviation discussion.", False),
        ("bot-commands", "Use bot commands here to keep chat clean.", False),
    ],
    "Community": [
        ("community-events", "Community event notices.", True),
        ("community-posts", "Community posts and discussion.", False),
    ],
}

STAFF_CHANNELS = [
    "staff-announcements",
    "staff-chat",
    "staff-commands",
    "staff-resources",
    "recruitment-training",
    "management",
    "directors",
    "executive",
    "flight-operations",
    "cabin-operations",
    "ground-operations",
    "customer-support",
    "people-recruitment",
    "development-team",
    "action-logs",
    "moderation-logs",
    "ticket-logs",
]

# Channels from the older multi-category layouts which can be reused rather
# than creating duplicates.
OLD_TO_NEW = {
    "trainee-hub": "recruitment-training",
    "management-chat": "management",
    "director-chat": "directors",
    "executive-chat": "executive",
    "support-team": "customer-support",
    "human-resources": "people-recruitment",
}

# Only these known old categories can be removed, and only when completely empty.
LEGACY_EMPTY_CATEGORIES = {
    "Recruitment & Training",
    "Management",
    "Directors",
    "Executive",
    "Flight Operations",
    "Cabin Operations",
    "Ground & Airport Operations",
    "Customer Support",
    "People & Recruitment",
    "Development Team",
    "Logs",
}


def norm(value):
    return "".join(ch for ch in str(value).casefold() if ch.isalnum())


def role(guild, name):
    return discord.utils.get(guild.roles, name=name)


def level_names(app, level):
    return set(app.ROLE_LEVEL_NAMES.get(level, set()))


def level_at_or_above(app, minimum):
    out = set()
    for level in range(minimum, 6):
        out |= level_names(app, level)
    return out


def director_plus(app):
    return level_at_or_above(app, 4)


def access_map(app):
    dirs = director_plus(app)
    management = level_at_or_above(app, 3)
    staff = level_at_or_above(app, 2)

    executive = level_names(app, 5) | {
        "Group Chief Operating Officer",
        "Ryanair DAC Chief Executive Officer",
        "Ryanair UK Chief Executive Officer",
        "Buzz Chief Executive Officer",
        "Malta Air Chief Executive Officer",
        "Lauda Europe Chief Executive Officer",
        "Executive Board",
    }

    recruitment_training = level_names(app, 1) | {
        "Recruitment Officer",
        "Recruitment Manager",
        "Recruitment Assessor",
        "Training Manager",
        "Director of People & Recruitment",
        "Director of Talent",
        "Director of Recruitment & Human Resources",
    } | management

    flight = {
        "Chief Pilot", "Chief Instructor, Safety", "Captain", "First Officer",
        "Cadet Pilot", "Flight Dispatcher", "Flight Operations Dispatcher",
        "Flight Operations Trainee", "Base Manager", "European Bases Manager",
        "Base Supervisor", "Senior Management", "Director of Operations",
    } | dirs

    cabin = {
        "Director of Inflight", "Inflight Manager", "Senior Cabin Crew",
        "Cabin Crew", "Cabin Crew Trainee", "Training Manager",
        "Senior Management",
    } | dirs

    ground = {
        "Director of Ground & Airport Operations", "Director of Ground Operations",
        "Ground & Airport Operations Manager", "Ground Operations Supervisor",
        "Ground Operations Agent", "Ground Operations Trainee",
        "Passenger Service Agent", "Gate Agent", "Ramp Agent",
        "Aircraft Engineer", "Engineer", "Aviation Security Officer",
        "Station Manager", "European Bases Manager", "Base Manager",
        "Base Supervisor", "Senior Management",
    } | dirs

    support = {
        "Director of Customer Service", "Customer Support Manager",
        "Customer Support Officer", "Customer Support Trainee",
        "Recruitment Manager", "Recruitment Assessor", "Senior Management",
    } | dirs

    people = {
        "Director of Talent", "Director of People & Recruitment",
        "Director of Recruitment & Human Resources", "Human Resources Manager",
        "Human Resources Officer", "Recruitment Manager", "Recruitment Assessor",
        "Recruitment Officer", "Training Manager", "Senior Management",
    } | dirs

    development = {
        "Director of Digital Development", "Development Manager", "Developer",
        "Senior Management",
    } | dirs

    return {
        "staff-announcements": staff,
        "staff-chat": staff,
        "staff-commands": staff,
        "staff-resources": staff,
        "recruitment-training": recruitment_training,
        "management": management,
        "directors": dirs,
        "executive": executive,
        "flight-operations": flight,
        "cabin-operations": cabin,
        "ground-operations": ground,
        "customer-support": support,
        "people-recruitment": people,
        "development-team": development,
        "action-logs": dirs,
        "moderation-logs": dirs,
        "ticket-logs": support,
    }


def staff_read_only_channels():
    return {"staff-announcements", "staff-resources", "action-logs", "moderation-logs", "ticket-logs"}


def staff_publishers(app, channel_name):
    dirs = director_plus(app)
    management = level_at_or_above(app, 3)
    if channel_name in {"staff-announcements", "staff-resources"}:
        return management
    # Log channels are bot-output channels; humans do not need Send Messages.
    if channel_name in {"action-logs", "moderation-logs", "ticket-logs"}:
        return set()
    return set()


def public_publishers(app, channel_name):
    dirs = director_plus(app)
    management = level_at_or_above(app, 3)
    if channel_name in {"announcements", "press-releases", "rules", "information"}:
        return dirs
    if channel_name == "development":
        return dirs | {"Director of Digital Development", "Development Manager"}
    if channel_name == "careers":
        return dirs | {
            "Director of People & Recruitment", "Director of Talent",
            "Director of Recruitment & Human Resources", "Recruitment Manager",
        }
    if channel_name == "off-topic-announcements":
        return dirs | {"Director of Community", "Events Officer", "Senior Management"}
    if channel_name == "boosters":
        return management
    if channel_name == "departures":
        return dirs | {
            "Director of Operations", "Chief Pilot", "Flight Dispatcher",
            "Flight Operations Dispatcher", "Senior Management",
        }
    if channel_name == "community-events":
        return dirs | {"Director of Community", "Events Officer", "Senior Management"}
    return dirs


async def fetch_channels(guild):
    try:
        return await guild.fetch_channels()
    except (discord.Forbidden, discord.HTTPException):
        return list(guild.channels)


async def find_category(guild, name):
    wanted = norm(name)
    return next(
        (
            c for c in await fetch_channels(guild)
            if isinstance(c, discord.CategoryChannel) and norm(c.name) == wanted
        ),
        None,
    )


async def ensure_category(guild, name, made, errors):
    found = await find_category(guild, name)
    if found:
        return found
    try:
        await guild.create_category(name, reason="Ryanair V7 layout")
        made.append(f"[{name}]")
        await asyncio.sleep(0.20)
        return await find_category(guild, name)
    except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
        errors.append(f"{name} category: {type(exc).__name__}: {str(exc)[:120]}")
        return None


async def find_text(guild, name):
    wanted = name.casefold()
    return next(
        (
            c for c in await fetch_channels(guild)
            if isinstance(c, discord.TextChannel) and c.name.casefold() == wanted
        ),
        None,
    )


async def create_text_compat(guild, name, topic, wants_news, errors):
    try:
        return await guild.create_text_channel(
            name,
            topic=topic,
            news=wants_news,
            reason="Ryanair V7 layout",
        )
    except TypeError:
        # Compatibility fallback for older/forked discord.py builds.
        try:
            return await guild.create_text_channel(
                name,
                topic=topic,
                reason="Ryanair V7 layout",
            )
        except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
            errors.append(f"{name} create: {type(exc).__name__}: {str(exc)[:120]}")
            return None
    except (discord.Forbidden, discord.HTTPException) as exc:
        errors.append(f"{name} create: {type(exc).__name__}: {str(exc)[:120]}")
        return None


async def ensure_text(guild, target_category, name, topic, made, errors, *, wants_news=False):
    channel = await find_text(guild, name)
    if channel is None:
        channel = await create_text_compat(guild, name, topic, wants_news, errors)
        if channel is None:
            return None
        made.append(name)
        await asyncio.sleep(0.10)

    if target_category and channel.category_id != target_category.id:
        try:
            channel = await channel.edit(
                category=target_category,
                reason="Ryanair V7 channel placement",
            )
        except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
            errors.append(f"{name} move: {type(exc).__name__}: {str(exc)[:100]}")

    if topic is not None and getattr(channel, "topic", None) != topic:
        try:
            channel = await channel.edit(topic=topic, reason="Ryanair V7 topic sync")
        except (discord.Forbidden, discord.HTTPException, TypeError):
            pass

    if wants_news and channel.type != discord.ChannelType.news:
        try:
            channel = await channel.edit(
                type=discord.ChannelType.news,
                reason="Ryanair V7 Announcement channel",
            )
        except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
            errors.append(
                f"{name} megaphone: {type(exc).__name__}: {str(exc)[:120]}"
            )

    return channel


def bot_overwrite():
    return discord.PermissionOverwrite(
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
    )


def role_overwrite(*, send=True):
    return discord.PermissionOverwrite(
        view_channel=True,
        read_message_history=True,
        send_messages=send,
        send_messages_in_threads=send,
        add_reactions=True,
        use_application_commands=True,
        connect=True,
        speak=True,
    )


async def apply_overwrites(target, overwrites, errors):
    """Bulk-edit first (fast); fall back to set_permissions if the library rejects it."""
    try:
        await target.edit(overwrites=overwrites, reason="Ryanair V7 permission sync")
        return
    except TypeError:
        pass
    except (discord.Forbidden, discord.HTTPException) as exc:
        errors.append(f"{target.name} bulk permissions: {str(exc)[:100]}")
        return

    # Compatibility fallback.
    for subject, overwrite in overwrites.items():
        try:
            await target.set_permissions(
                subject,
                overwrite=overwrite,
                reason="Ryanair V7 permission sync fallback",
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"{target.name}->{getattr(subject, 'name', subject)}: {str(exc)[:80]}")


async def set_public_channel(app, channel, guild, *, read_only=False):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=False if read_only else True,
            add_reactions=True,
        )
    }
    if guild.me:
        overwrites[guild.me] = bot_overwrite()
    if read_only:
        for name in public_publishers(app, channel.name.casefold()):
            r = role(guild, name)
            if r:
                overwrites[r] = role_overwrite(send=True)
    await apply_overwrites(channel, overwrites, [])


async def set_public_category(category, guild, errors):
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=True),
    }
    if guild.me:
        overwrites[guild.me] = bot_overwrite()
    await apply_overwrites(category, overwrites, errors)


async def set_private_channel(app, channel, guild, allowed_names, errors, *, read_only=False):
    publishers = staff_publishers(app, channel.name.casefold()) if read_only else set()
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
    }
    if guild.me:
        overwrites[guild.me] = bot_overwrite()

    for name in sorted(set(allowed_names)):
        r = role(guild, name)
        if not r:
            continue
        can_send = (not read_only) or (name in publishers)
        overwrites[r] = role_overwrite(send=can_send)

    await apply_overwrites(channel, overwrites, errors)


async def set_staff_hub_category(app, category, guild, errors):
    # Category is hidden from the public. Level 1+ can see the category shell;
    # individual child channels still have stricter job/rank overwrites.
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
    }
    if guild.me:
        overwrites[guild.me] = bot_overwrite()
    for name in sorted(level_at_or_above(app, 1)):
        r = role(guild, name)
        if r:
            overwrites[r] = discord.PermissionOverwrite(view_channel=True)
    await apply_overwrites(category, overwrites, errors)


async def build_public(app, guild, made, errors):
    for category_name, channel_specs in PUBLIC_LAYOUT.items():
        cat = await ensure_category(guild, category_name, made, errors)
        if not cat:
            continue
        await set_public_category(cat, guild, errors)

        for name, topic, read_only in channel_specs:
            channel = await ensure_text(
                guild,
                cat,
                name,
                topic,
                made,
                errors,
                wants_news=name.casefold() in ANNOUNCEMENT_CHANNELS,
            )
            if channel:
                await set_public_channel(app, channel, guild, read_only=read_only)

    voice_cat = await ensure_category(guild, "Community Voice", made, errors)
    if voice_cat:
        await set_public_category(voice_cat, guild, errors)
        for voice_name in ("Voice Chat", "Voice Chat 2"):
            vc = next(
                (v for v in guild.voice_channels if v.name.casefold() == voice_name.casefold()),
                None,
            )
            if vc is None:
                try:
                    vc = await guild.create_voice_channel(
                        voice_name,
                        reason="Ryanair V7 community voice",
                    )
                    made.append(voice_name)
                except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
                    errors.append(f"{voice_name}: {str(exc)[:100]}")
                    continue
            try:
                if vc.category_id != voice_cat.id:
                    vc = await vc.edit(category=voice_cat, reason="Ryanair V7 voice placement")
            except (discord.Forbidden, discord.HTTPException, TypeError):
                pass


async def consolidate_staff(app, guild, made, errors):
    staff_hub = await ensure_category(guild, "Staff Hub", made, errors)
    if not staff_hub:
        return
    await set_staff_hub_category(app, staff_hub, guild, errors)

    # Reuse selected old channel names where possible.
    for old_name, new_name in OLD_TO_NEW.items():
        if await find_text(guild, new_name):
            continue
        old = await find_text(guild, old_name)
        if old:
            try:
                await old.edit(name=new_name, reason="Ryanair V7 concise Staff Hub")
            except (discord.Forbidden, discord.HTTPException, TypeError):
                pass

    accesses = access_map(app)
    readonly = staff_read_only_channels()
    for name in STAFF_CHANNELS:
        channel = await ensure_text(guild, staff_hub, name, None, made, errors)
        if channel:
            await set_private_channel(
                app,
                channel,
                guild,
                accesses[name],
                errors,
                read_only=name in readonly,
            )


async def configure_support_tickets(app, guild, made, errors):
    cat = await ensure_category(guild, "Support Tickets", made, errors)
    if not cat:
        return
    access = access_map(app)["customer-support"]
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
    }
    if guild.me:
        overwrites[guild.me] = bot_overwrite()
    for name in sorted(access):
        r = role(guild, name)
        if r:
            overwrites[r] = role_overwrite(send=True)
    await apply_overwrites(cat, overwrites, errors)
    app.TICKET_CATEGORY_ID = cat.id


async def cleanup_empty_legacy_categories(guild, errors):
    # Non-destructive cleanup: only exact known legacy categories with zero children.
    fresh = await fetch_channels(guild)
    for cat in [c for c in fresh if isinstance(c, discord.CategoryChannel)]:
        if cat.name not in LEGACY_EMPTY_CATEGORIES:
            continue
        children = [c for c in fresh if getattr(c, "category_id", None) == cat.id]
        if children:
            continue
        try:
            await cat.delete(reason="Remove empty legacy Ryanair layout category")
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"empty {cat.name} cleanup: {str(exc)[:90]}")


def resolve_ids(app, guild):
    by_name = {c.name.casefold(): c for c in guild.text_channels}
    if "announcements" in by_name:
        app.ANNOUNCEMENT_CHANNEL_ID = by_name["announcements"].id
    if "departures" in by_name:
        app.DEPARTURES_CHANNEL_ID = by_name["departures"].id
    if "action-logs" in by_name:
        app.LOG_CHANNEL_ID = by_name["action-logs"].id
        app.ACTION_LOG_CHANNEL_ID = by_name["action-logs"].id
    if "moderation-logs" in by_name:
        app.MODERATION_LOG_CHANNEL_ID = by_name["moderation-logs"].id
    if "ticket-logs" in by_name:
        app.TICKET_LOG_CHANNEL_ID = by_name["ticket-logs"].id
    tickets = discord.utils.get(guild.categories, name="Support Tickets")
    if tickets:
        app.TICKET_CATEGORY_ID = tickets.id


async def repair(app, guild):
    made, errors = [], []
    await build_public(app, guild, made, errors)
    await consolidate_staff(app, guild, made, errors)
    await configure_support_tickets(app, guild, made, errors)
    await cleanup_empty_legacy_categories(guild, errors)
    resolve_ids(app, guild)
    return made, errors


def setup(app):
    if getattr(app, "_professional_layout_v7_loaded", False):
        return
    app._professional_layout_v7_loaded = True

    # Make sure the expanded rank list is available to all bot permission checks.
    for level, names in base.EXTRA_LEVEL_ROLES.items():
        app.ROLE_LEVEL_NAMES.setdefault(level, set()).update(names)
    app.ALL_STAFF_ROLE_NAMES = set().union(*app.ROLE_LEVEL_NAMES.values())
    app.EXECUTIVE_AND_DIRECTOR_ROLE_NAMES = level_names(app, 5) | level_names(app, 4)
    app.TICKET_ACCESS_ROLE_NAMES = access_map(app)["customer-support"]

    guild_obj = discord.Object(id=app.GUILD_ID)
    app.tree.remove_command("setupserver", guild=guild_obj)

    @app_commands.command(
        name="setupserver",
        description="Sync clean Ryanair channels, Announcement types and rank locks (Owner only)",
    )
    async def setupserver_v7(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not app.is_server_owner(interaction.user):
            await interaction.followup.send("Only the server owner can run `/setupserver`.", ephemeral=True)
            return
        guild = interaction.guild
        if (
            not guild
            or not guild.me
            or not guild.me.guild_permissions.manage_channels
            or not guild.me.guild_permissions.manage_roles
        ):
            await interaction.followup.send(
                "The bot needs **Manage Channels** and **Manage Roles**.",
                ephemeral=True,
            )
            return

        made, errors = await repair(app, guild)
        megaphone_errors = [e for e in errors if "megaphone" in e]
        await interaction.followup.send(
            f"V7 sync complete. Created/repaired: **{len(made)}**. "
            f"Issues: **{len(errors)}**. "
            f"Announcement conversion issues: **{len(megaphone_errors)}**. "
            "All managed private channels were rank-locked using their actual job/rank roles.",
            ephemeral=True,
        )

    app.tree.add_command(setupserver_v7, guild=guild_obj, override=True)

    async def on_ready_v7():
        await asyncio.sleep(5)
        guild = app.bot.get_guild(app.GUILD_ID)
        if not guild or not guild.me or not guild.me.guild_permissions.manage_channels:
            return
        made, errors = await repair(app, guild)
        print(
            f"SERVER LAYOUT V7: made={len(made)} errors={len(errors)}",
            flush=True,
        )

    app.bot.add_listener(on_ready_v7, "on_ready")
    print(
        "Professional server layout V7 loaded: one Staff Hub, real Announcement channels, actual-rank locks, bulk permissions.",
        flush=True,
    )

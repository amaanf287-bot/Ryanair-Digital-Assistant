"""Ryanair professional server layout V6.

V6 is non-destructive. It keeps the reference-style public categories, moves the
private staff channels into one Staff Hub, keeps Support Tickets separate,
keeps real Announcement channels, and applies channel-specific rank locks.
It does not delete channels or categories automatically.
"""

import asyncio
import discord
from discord import app_commands
import server_layout_v4 as base

ANNOUNCEMENT_CHANNELS = {"announcements", "press-releases", "development", "careers"}

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
    "staff-announcements", "staff-chat", "staff-commands", "staff-resources",
    "recruitment-training", "management", "directors", "executive",
    "flight-operations", "cabin-operations", "ground-operations",
    "customer-support", "people-recruitment", "development-team",
    "action-logs", "moderation-logs", "ticket-logs",
]

OLD_TO_NEW = {
    "trainee-hub": "recruitment-training",
    "management-chat": "management",
    "director-chat": "directors",
    "executive-chat": "executive",
    "support-team": "customer-support",
    "human-resources": "people-recruitment",
}


def norm(value):
    return "".join(ch for ch in str(value).casefold() if ch.isalnum())


def role(guild, name):
    return discord.utils.get(guild.roles, name=name)


def directors(app):
    return {"Directors"} | set(app.ROLE_LEVEL_NAMES.get(4, set())) | set(app.ROLE_LEVEL_NAMES.get(5, set()))


def access_map(app):
    dirs = directors(app)
    management = set(app.ROLE_LEVEL_NAMES.get(3, set())) | dirs
    executive = set(app.ROLE_LEVEL_NAMES.get(5, set())) | {
        "Group Chief Operating Officer", "Ryanair DAC Chief Executive Officer",
        "Ryanair UK Chief Executive Officer", "Buzz Chief Executive Officer",
        "Malta Air Chief Executive Officer", "Lauda Europe Chief Executive Officer",
        "Executive Board",
    }
    return {
        "staff-announcements": {"Staff"} | dirs,
        "staff-chat": {"Staff"} | dirs,
        "staff-commands": {"Staff"} | dirs,
        "staff-resources": {"Staff"} | dirs,
        "recruitment-training": set(app.ROLE_LEVEL_NAMES.get(1, set())) | {"Recruitment Officer", "Recruitment Manager", "Recruitment Assessor", "Training Manager"} | dirs,
        "management": management,
        "directors": dirs,
        "executive": executive,
        "flight-operations": {"Chief Pilot", "Chief Instructor, Safety", "Captain", "First Officer", "Cadet Pilot", "Flight Dispatcher", "Flight Operations Dispatcher", "Flight Operations Trainee", "Base Manager", "European Bases Manager", "Base Supervisor", "Senior Management"} | dirs,
        "cabin-operations": {"Director of Inflight", "Inflight Manager", "Senior Cabin Crew", "Cabin Crew", "Cabin Crew Trainee", "Training Manager", "Senior Management"} | dirs,
        "ground-operations": {"Director of Ground & Airport Operations", "Director of Ground Operations", "Ground & Airport Operations Manager", "Ground Operations Supervisor", "Ground Operations Agent", "Ground Operations Trainee", "Passenger Service Agent", "Gate Agent", "Ramp Agent", "Aircraft Engineer", "Engineer", "Aviation Security Officer", "Station Manager", "European Bases Manager", "Base Manager", "Base Supervisor", "Senior Management"} | dirs,
        "customer-support": {"Director of Customer Service", "Customer Support Manager", "Customer Support Officer", "Customer Support Trainee", "Recruitment Manager", "Recruitment Assessor", "Senior Management"} | dirs,
        "people-recruitment": {"Director of Talent", "Director of People & Recruitment", "Director of Recruitment & Human Resources", "Human Resources Manager", "Human Resources Officer", "Recruitment Manager", "Recruitment Assessor", "Recruitment Officer", "Training Manager", "Senior Management"} | dirs,
        "development-team": {"Director of Digital Development", "Development Manager", "Developer", "Senior Management"} | dirs,
        "action-logs": dirs,
        "moderation-logs": dirs,
        "ticket-logs": {"Director of Customer Service", "Customer Support Manager", "Customer Support Officer", "Customer Support Trainee", "Senior Management"} | dirs,
    }


async def fetch_channels(guild):
    try:
        return await guild.fetch_channels()
    except (discord.Forbidden, discord.HTTPException):
        return list(guild.channels)


async def category(guild, name):
    wanted = norm(name)
    return next((c for c in await fetch_channels(guild) if isinstance(c, discord.CategoryChannel) and norm(c.name) == wanted), None)


async def ensure_category(guild, name, made, errors):
    found = await category(guild, name)
    if found:
        return found
    try:
        await guild.create_category(name, reason="Ryanair V6 layout")
        made.append(f"[{name}]")
        await asyncio.sleep(0.25)
        return await category(guild, name)
    except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
        errors.append(f"{name}: {type(exc).__name__}: {str(exc)[:110]}")
        return None


async def find_text(guild, name):
    wanted = name.casefold()
    return next((c for c in await fetch_channels(guild) if isinstance(c, discord.TextChannel) and c.name.casefold() == wanted), None)


async def ensure_text(guild, target_category, name, topic, made, errors):
    channel = await find_text(guild, name)
    if channel is None:
        try:
            channel = await guild.create_text_channel(name, topic=topic, reason="Ryanair V6 layout")
            made.append(name)
        except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
            errors.append(f"{name} create: {type(exc).__name__}: {str(exc)[:110]}")
            return None
    try:
        if target_category and channel.category_id != target_category.id:
            await channel.edit(category=target_category, reason="Ryanair V6 channel consolidation")
    except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
        errors.append(f"{name} move: {str(exc)[:100]}")
    if topic is not None and getattr(channel, "topic", None) != topic:
        try:
            await channel.edit(topic=topic, reason="Ryanair V6 topic sync")
        except (discord.Forbidden, discord.HTTPException, TypeError):
            pass
    return channel


async def grant_bot(target, guild):
    if not guild.me:
        return
    try:
        await target.set_permissions(guild.me, view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, manage_messages=True, embed_links=True, attach_files=True, add_reactions=True, use_application_commands=True, connect=True, speak=True, reason="Ryanair bot access")
    except (discord.Forbidden, discord.HTTPException):
        pass


async def set_public(target, guild, read_only=False):
    try:
        await target.set_permissions(guild.default_role, view_channel=True, read_message_history=True, send_messages=False if read_only else True, add_reactions=True, reason="Ryanair public access")
    except (discord.Forbidden, discord.HTTPException):
        pass
    await grant_bot(target, guild)
    if read_only:
        publisher = role(guild, "Directors")
        if publisher:
            try:
                await target.set_permissions(publisher, view_channel=True, read_message_history=True, send_messages=True, add_reactions=True, use_application_commands=True, reason="Ryanair publisher access")
            except (discord.Forbidden, discord.HTTPException):
                pass


async def set_private(target, guild, names, errors):
    try:
        await target.set_permissions(guild.default_role, view_channel=False, reason="Ryanair V6 rank lock")
    except (discord.Forbidden, discord.HTTPException) as exc:
        errors.append(f"{target.name} public lock: {str(exc)[:90]}")
    await grant_bot(target, guild)
    overwrite = discord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=True, send_messages_in_threads=True, add_reactions=True, use_application_commands=True, connect=True, speak=True)
    for name in sorted(set(names)):
        target_role = role(guild, name)
        if not target_role:
            continue
        try:
            await target.set_permissions(target_role, overwrite=overwrite, reason="Ryanair V6 rank access")
        except (discord.Forbidden, discord.HTTPException) as exc:
            errors.append(f"{target.name}->{name}: {str(exc)[:80]}")


async def convert_announcement(channel, errors):
    if not channel or channel.name.casefold() not in ANNOUNCEMENT_CHANNELS or channel.type == discord.ChannelType.news:
        return
    try:
        await channel.edit(type=discord.ChannelType.news, reason="Ryanair V6 Announcement channel")
    except (discord.Forbidden, discord.HTTPException, TypeError) as exc:
        errors.append(f"{channel.name} announcement: {type(exc).__name__}: {str(exc)[:100]}")


async def build_public(guild, made, errors):
    for category_name, channel_specs in PUBLIC_LAYOUT.items():
        cat = await ensure_category(guild, category_name, made, errors)
        if not cat:
            continue
        await set_public(cat, guild)
        for name, topic, read_only in channel_specs:
            channel = await ensure_text(guild, cat, name, topic, made, errors)
            if channel:
                await set_public(channel, guild, read_only)
                await convert_announcement(channel, errors)

    voice_cat = await ensure_category(guild, "Community Voice", made, errors)
    if voice_cat:
        await set_public(voice_cat, guild)
        for voice_name in ("Voice Chat", "Voice Chat 2"):
            vc = next((v for v in guild.voice_channels if v.name.casefold() == voice_name.casefold()), None)
            if vc is None:
                try:
                    vc = await guild.create_voice_channel(voice_name, reason="Ryanair V6 community voice")
                    made.append(voice_name)
                except (discord.Forbidden, discord.HTTPException, TypeError):
                    continue
            try:
                if vc.category_id != voice_cat.id:
                    await vc.edit(category=voice_cat, reason="Ryanair V6 voice placement")
            except (discord.Forbidden, discord.HTTPException, TypeError):
                pass
            await set_public(vc, guild)


async def ensure_staff_tag_roles(app, guild):
    me = guild.me
    if not me or not me.guild_permissions.manage_roles:
        return
    staff = role(guild, "Staff")
    dirs = role(guild, "Directors")
    for member in list(guild.members):
        if member.bot:
            continue
        level = app.get_user_level(member)
        try:
            if staff and staff < me.top_role and level >= 2 and staff not in member.roles:
                await member.add_roles(staff, reason="Ryanair V6 Staff tag sync")
            if dirs and dirs < me.top_role and level >= 4 and dirs not in member.roles:
                await member.add_roles(dirs, reason="Ryanair V6 Directors tag sync")
        except (discord.Forbidden, discord.HTTPException):
            pass


async def consolidate_staff(app, guild, made, errors):
    staff_hub = await ensure_category(guild, "Staff Hub", made, errors)
    if not staff_hub:
        return
    try:
        await staff_hub.set_permissions(guild.default_role, view_channel=False, reason="Ryanair private Staff Hub")
    except (discord.Forbidden, discord.HTTPException):
        pass
    await grant_bot(staff_hub, guild)

    for old_name, new_name in OLD_TO_NEW.items():
        if await find_text(guild, new_name):
            continue
        old = await find_text(guild, old_name)
        if old:
            try:
                await old.edit(name=new_name, reason="Ryanair V6 concise Staff Hub")
            except (discord.Forbidden, discord.HTTPException):
                pass

    accesses = access_map(app)
    for name in STAFF_CHANNELS:
        channel = await ensure_text(guild, staff_hub, name, None, made, errors)
        if channel:
            await set_private(channel, guild, accesses[name], errors)


async def support_tickets(app, guild, made, errors):
    cat = await ensure_category(guild, "Support Tickets", made, errors)
    if not cat:
        return
    access = access_map(app)["customer-support"]
    await set_private(cat, guild, access, errors)
    app.TICKET_CATEGORY_ID = cat.id


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
    await ensure_staff_tag_roles(app, guild)
    await build_public(guild, made, errors)
    await consolidate_staff(app, guild, made, errors)
    await support_tickets(app, guild, made, errors)
    resolve_ids(app, guild)
    return made, errors


def setup(app):
    if getattr(app, "_professional_layout_v6_loaded", False):
        return
    app._professional_layout_v6_loaded = True

    for level, names in base.EXTRA_LEVEL_ROLES.items():
        app.ROLE_LEVEL_NAMES.setdefault(level, set()).update(names)
    app.ALL_STAFF_ROLE_NAMES = set().union(*app.ROLE_LEVEL_NAMES.values())

    guild_obj = discord.Object(id=app.GUILD_ID)
    app.tree.remove_command("setupserver", guild=guild_obj)

    @app_commands.command(name="setupserver", description="Sync the clean Ryanair Staff Hub and rank locks (Owner only)")
    async def setupserver_v6(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not app.is_server_owner(interaction.user):
            await interaction.followup.send("Only the server owner can run `/setupserver`.", ephemeral=True)
            return
        guild = interaction.guild
        if not guild or not guild.me or not guild.me.guild_permissions.manage_channels or not guild.me.guild_permissions.manage_roles:
            await interaction.followup.send("The bot needs **Manage Channels** and **Manage Roles**.", ephemeral=True)
            return
        made, errors = await repair(app, guild)
        await interaction.followup.send(f"V6 sync complete. Created/repaired: **{len(made)}**. Issues: **{len(errors)}**. Staff channels are now consolidated under Staff Hub. No channels/categories were deleted.", ephemeral=True)

    app.tree.add_command(setupserver_v6, guild=guild_obj, override=True)

    async def on_ready_v6():
        await asyncio.sleep(5)
        guild = app.bot.get_guild(app.GUILD_ID)
        if not guild or not guild.me or not guild.me.guild_permissions.manage_channels:
            return
        made, errors = await repair(app, guild)
        print(f"SERVER LAYOUT V6: made={len(made)} errors={len(errors)}", flush=True)

    app.bot.add_listener(on_ready_v6, "on_ready")
    print("Professional server layout V6 loaded: one Staff Hub, Announcement channels and rank locks.", flush=True)

"""Department-aware support ticket permissions + weekly grammar qualification.

Rules:
- Support Tickets base access: Executive Leadership + core Customer Support.
- Normal ticket channels additionally expose only the department relevant to the
  selected ticket option.
- Directors do NOT receive blanket ticket access; a Director only receives a
  ticket when their own department is explicitly mapped to that option.
- Every non-executive customer-facing helper must pass the current /grammer
  cycle before they can send messages in tickets. Executives are exempt.
- Grammar passes expire after seven days and are persisted inside branding_config
  so the existing data.json save/load system retains them.
"""

import asyncio
import datetime
import re
import uuid

import discord
from discord import app_commands

import server_layout_v16 as layout16
import server_layout_v7 as layout


EXECUTIVES = set(layout16.EXECUTIVE_LEADERSHIP)
CORE_SUPPORT = set(layout16.CORE_SUPPORT)

DEPARTMENT_ACCESS = {
    "Server Help": {
        "Developer",
        "Development Manager",
        "Director of Digital Development",
        "Community Affairs Officer",
    },
    "General Assistance": set(),
    "Bans & Blacklists": {
        "Aviation Security Officer",
        "Safety & Security Supervisor",
        "Safety & Security Manager",
        "Director of Safety & Security",
    },
    "Career Enquiries": {
        "Recruitment Officer",
        "Recruitment Assessor",
        "Recruitment Manager",
        "Training Manager",
        "Director of Recruitment & People",
        "Director of People & Recruitment",
        "Director of Recruitment & Human Resources",
        "Human Resources Officer",
        "Human Resources Manager",
    },
    "Flight Assistance": {
        "Flight Operations Dispatcher",
        "Flight Dispatcher",
        "Passenger Service Agent",
        "Base Manager",
        "Station Manager",
        "Airline Operations Manager",
        "Airport Operations Manager",
        "Director of Flight Operations",
        "Director of Airport Operations",
    },
    "Priority Support": set(),
    "Partnership Enquiry": {
        "Corporate Affairs Officer",
        "Public Affairs Officer",
        "Media & Communications Officer",
        "Corporate Affairs Manager",
        "Director of Corporate Affairs",
    },
}

ALL_DEPARTMENT_HELPERS = set().union(*DEPARTMENT_ACCESS.values()) if DEPARTMENT_ACCESS else set()
ALL_NON_EXEC_HELPERS = CORE_SUPPORT | ALL_DEPARTMENT_HELPERS
PASS_VALID_DAYS = 7
PASS_SCORE = 4
STATE_KEY = "_weekly_grammar_qualification"


def member_role_names(member):
    return {role.name for role in getattr(member, "roles", [])}


def has_any_role(member, names):
    return bool(member_role_names(member) & set(names))


def is_executive(member):
    if member is None:
        return False
    if getattr(member.guild, "owner_id", None) == member.id:
        return True
    return has_any_role(member, EXECUTIVES)


def is_nonexec_ticket_helper(member):
    return member is not None and not is_executive(member) and has_any_role(member, ALL_NON_EXEC_HELPERS)


def grammar_state(app, guild_id):
    server_cfg = app.branding_config.setdefault(str(guild_id), {})
    state = server_cfg.setdefault(
        STATE_KEY,
        {"cycle_id": None, "started_at": None, "passes": {}},
    )
    state.setdefault("cycle_id", None)
    state.setdefault("started_at", None)
    state.setdefault("passes", {})
    return state


def grammar_qualified(app, member):
    if member is None:
        return False
    if is_executive(member):
        return True
    if not is_nonexec_ticket_helper(member):
        return False

    state = grammar_state(app, member.guild.id)
    cycle_id = state.get("cycle_id")
    if not cycle_id:
        return False
    record = state.get("passes", {}).get(str(member.id), {})
    if record.get("cycle_id") != cycle_id:
        return False
    passed_at = record.get("passed_at")
    if not passed_at:
        return False
    try:
        passed = datetime.datetime.fromisoformat(passed_at)
        if passed.tzinfo is None:
            passed = passed.replace(tzinfo=datetime.timezone.utc)
    except (TypeError, ValueError):
        return False
    return app.now() - passed <= datetime.timedelta(days=PASS_VALID_DAYS)


def ticket_category_name(channel):
    topic = str(getattr(channel, "topic", "") or "")
    if "|" not in topic or not topic.startswith("Ticket |"):
        return None
    return topic.rsplit("|", 1)[-1].strip()


def roles_for_ticket(category_name):
    return CORE_SUPPORT | set(DEPARTMENT_ACCESS.get(category_name, set()))


def member_relevant_to_ticket(member, category_name):
    if is_executive(member):
        return True
    return has_any_role(member, roles_for_ticket(category_name))


def reader_no_send():
    return discord.PermissionOverwrite(
        view_channel=True,
        read_message_history=True,
        send_messages=False,
        send_messages_in_threads=False,
        create_public_threads=False,
        create_private_threads=False,
        add_reactions=True,
        use_application_commands=True,
    )


def writer():
    return discord.PermissionOverwrite(
        view_channel=True,
        read_message_history=True,
        send_messages=True,
        send_messages_in_threads=True,
        create_public_threads=False,
        create_private_threads=False,
        add_reactions=True,
        use_application_commands=True,
    )


def hidden():
    return discord.PermissionOverwrite(
        view_channel=False,
        read_message_history=False,
        send_messages=False,
    )


def find_role(guild, name):
    return discord.utils.get(guild.roles, name=name)


def ticket_overwrites(app, guild, channel, category_name):
    overwrites = {guild.default_role: hidden()}

    if guild.me:
        overwrites[guild.me] = layout.bot_overwrite()

    for role_name in sorted(EXECUTIVES):
        role = find_role(guild, role_name)
        if role:
            overwrites[role] = writer()

    # Staff Hub stays private to the opener + executives.
    if category_name == "Staff Hub":
        opener_id = app.get_user_id_from_channel(channel.id)
        if opener_id:
            opener = guild.get_member(int(opener_id))
            if opener:
                overwrites[opener] = writer()
        return overwrites

    permitted_roles = roles_for_ticket(category_name)

    # Roles grant visibility only. A current grammar pass grants member-level Send.
    for role_name in sorted(permitted_roles):
        role = find_role(guild, role_name)
        if role:
            overwrites[role] = reader_no_send()

    for member in guild.members:
        if member.bot or is_executive(member):
            continue
        if member_relevant_to_ticket(member, category_name) and grammar_qualified(app, member):
            overwrites[member] = writer()

    return overwrites


async def sync_support_category(app, guild):
    category = discord.utils.get(guild.categories, name="Support Tickets")
    if not category:
        return
    overwrites = {guild.default_role: hidden()}
    if guild.me:
        overwrites[guild.me] = layout.bot_overwrite()
    for role_name in sorted(EXECUTIVES):
        role = find_role(guild, role_name)
        if role:
            overwrites[role] = writer()
    for role_name in sorted(CORE_SUPPORT):
        role = find_role(guild, role_name)
        if role:
            overwrites[role] = reader_no_send()
    await category.edit(overwrites=overwrites, reason="Ryanair support/executive ticket base access")
    app.TICKET_CATEGORY_ID = category.id


async def sync_ticket_channel(app, channel):
    if not isinstance(channel, discord.TextChannel):
        return
    category_name = ticket_category_name(channel)
    if not category_name:
        return
    overwrites = ticket_overwrites(app, channel.guild, channel, category_name)
    await channel.edit(
        overwrites=overwrites,
        reason="Ryanair department ticket access + weekly grammar qualification",
    )


async def sync_all_open_tickets(app, guild):
    await sync_support_category(app, guild)
    for channel_id in list(app.tickets.values()):
        channel = guild.get_channel(int(channel_id))
        if isinstance(channel, discord.TextChannel):
            try:
                await sync_ticket_channel(app, channel)
            except (discord.Forbidden, discord.HTTPException) as exc:
                print(f"TICKET ACCESS SYNC ERROR #{channel.name}: {exc}", flush=True)
            await asyncio.sleep(0.10)


def normalise_answer(text):
    text = str(text or "").strip().lower()
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def grade_answers(answers):
    scores = []
    scores.append(normalise_answer(answers[0]) == "your flight has been delayed because of weather")
    scores.append(normalise_answer(answers[1]) == "please send your booking reference")
    scores.append(normalise_answer(answers[2]) == "we were unable to locate the ticket")

    q4 = str(answers[3] or "").strip()
    q4_lower = q4.lower()
    scores.append(
        q4.startswith("Hello")
        and "how can i help you today" in q4_lower
        and (q4.endswith("?") or q4.endswith("."))
    )

    q5 = normalise_answer(answers[4])
    scores.append(q5 in {"a", "a their flight is delayed", "their flight is delayed"})
    return sum(1 for item in scores if item), [i + 1 for i, ok in enumerate(scores) if not ok]


class GrammarTestModal(discord.ui.Modal):
    def __init__(self, app):
        super().__init__(title="Weekly Customer Support Grammar Test", timeout=600)
        self.app = app
        self.q1 = discord.ui.TextInput(
            label="1. Correct this sentence",
            placeholder="your flight have been delayed because of weather",
            max_length=100,
        )
        self.q2 = discord.ui.TextInput(
            label="2. Correct this sentence",
            placeholder="please send you're booking reference",
            max_length=100,
        )
        self.q3 = discord.ui.TextInput(
            label="3. Correct this sentence",
            placeholder="we was unable to locate the ticket",
            max_length=100,
        )
        self.q4 = discord.ui.TextInput(
            label="4. Write this professionally",
            placeholder="hello how can i help you today",
            max_length=100,
        )
        self.q5 = discord.ui.TextInput(
            label="5. Which is correct? Type A, B, or C",
            placeholder="A) Their flight is delayed. B) There flight... C) They're flight...",
            max_length=10,
        )
        for item in (self.q1, self.q2, self.q3, self.q4, self.q5):
            self.add_item(item)

    async def on_submit(self, interaction: discord.Interaction):
        guild = self.app.bot.get_guild(self.app.GUILD_ID)
        member = guild.get_member(interaction.user.id) if guild else None
        if not member or not is_nonexec_ticket_helper(member):
            await interaction.response.send_message(
                "You are not currently in a non-executive customer-facing role that requires this test."
            )
            return

        state = grammar_state(self.app, guild.id)
        if not state.get("cycle_id"):
            await interaction.response.send_message(
                "There is no active grammar cycle. Ask the server owner to run `/grammer`."
            )
            return

        answers = [self.q1.value, self.q2.value, self.q3.value, self.q4.value, self.q5.value]
        score, wrong = grade_answers(answers)
        if score >= PASS_SCORE:
            state.setdefault("passes", {})[str(member.id)] = {
                "cycle_id": state["cycle_id"],
                "passed_at": self.app.now().isoformat(),
                "score": score,
            }
            self.app.save_data()
            await sync_all_open_tickets(self.app, guild)
            await interaction.response.send_message(
                f"✅ **Passed: {score}/5.** You are qualified to speak in the customer tickets your role can access for this grammar cycle."
            )
        else:
            await interaction.response.send_message(
                f"❌ **Not passed: {score}/5.** You need **{PASS_SCORE}/5**. Check question(s) {', '.join(map(str, wrong))} and press **Start Grammar Test** again to retry."
            )


class GrammarTestView(discord.ui.View):
    def __init__(self, app):
        super().__init__(timeout=None)
        self.app = app

    @discord.ui.button(
        label="Start Grammar Test",
        style=discord.ButtonStyle.primary,
        custom_id="ryanair_weekly_grammar_test_start_v1",
    )
    async def start_test(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.app.bot.get_guild(self.app.GUILD_ID)
        member = guild.get_member(interaction.user.id) if guild else None
        if not member or not is_nonexec_ticket_helper(member):
            await interaction.response.send_message(
                "You do not currently need the customer-support grammar qualification."
            )
            return
        await interaction.response.send_modal(GrammarTestModal(self.app))


async def dm_grammar_test(app, member):
    embed = discord.Embed(
        title="Weekly Customer Support Grammar Check",
        description=(
            "A new customer-facing grammar qualification cycle has started.\n\n"
            "Until you pass, you can still **view** the support tickets your role is allowed to access, "
            "but you **cannot send customer replies** in them.\n\n"
            f"**Pass mark:** {PASS_SCORE}/5\n"
            f"**Validity:** {PASS_VALID_DAYS} days / until the next `/grammer` cycle\n\n"
            "Press the button below to take the test. You can retry if needed."
        ),
        color=getattr(app, "RYANAIR_BLUE", 0x073590),
        timestamp=app.now(),
    )
    embed.set_footer(text="Ryanair Digital Assistant — Customer Support Standards")
    await member.send(embed=embed, view=GrammarTestView(app))


async def assign_ticket_to_staff(app, guild, channel, user, tried_ids=None):
    """Assign only grammar-qualified staff who can access this ticket's department."""
    if tried_ids is None:
        tried_ids = app.ticket_assigned_staff.get(channel.id, [])
    category_name = ticket_category_name(channel) or "General Assistance"
    available = [
        member
        for member in guild.members
        if not member.bot
        and member.id not in tried_ids
        and member.id not in app.connected_staff.values()
        and member_relevant_to_ticket(member, category_name)
        and grammar_qualified(app, member)
        and member.status in (discord.Status.online, discord.Status.idle, discord.Status.dnd)
    ]
    if not available:
        return

    chosen = available[0]
    tried_ids.append(chosen.id)
    app.ticket_assigned_staff[channel.id] = tried_ids
    transfer_time = int((app.now() + datetime.timedelta(minutes=30)).timestamp())
    try:
        embed = discord.Embed(
            title="Support Ticket Assignment",
            description=(
                f"A **{category_name}** ticket has been assigned to you.\n\n"
                f"**User:** {user.display_name}\n"
                f"**Ticket:** {channel.mention}\n\n"
                "Use `/connect` to claim the ticket. "
                f"If it is not claimed, it transfers at <t:{transfer_time}:T> (<t:{transfer_time}:R>)."
            ),
            color=getattr(app, "RYANAIR_BLUE", 0x073590),
            timestamp=app.now(),
        )
        embed.set_footer(text="Ryanair Digital Assistant — Ticket Assignment")
        await app.send_automation_dm(chosen.id, embed)
    except Exception:
        pass
    try:
        await channel.send(chosen.mention)
    except (discord.Forbidden, discord.HTTPException):
        pass
    asyncio.create_task(app.ticket_reassign_monitor(channel, user, chosen.id, tried_ids))


def setup(app):
    if getattr(app, "_ticket_grammar_access_loaded", False):
        return
    app._ticket_grammar_access_loaded = True

    original_open_ticket = app.open_ticket

    app.TICKET_ACCESS_ROLE_NAMES = set(EXECUTIVES) | set(CORE_SUPPORT)

    def qualified_support(member):
        return is_executive(member) or (
            is_nonexec_ticket_helper(member) and grammar_qualified(app, member)
        )

    app.is_support_staff = qualified_support

    async def open_ticket_with_access(user, category_name, opened_by_staff=None, reason=None):
        await original_open_ticket(user, category_name, opened_by_staff=opened_by_staff, reason=reason)
        guild = app.bot.get_guild(app.GUILD_ID)
        channel_id = app.tickets.get(user.id)
        channel = guild.get_channel(channel_id) if guild and channel_id else None
        if isinstance(channel, discord.TextChannel):
            try:
                await sync_ticket_channel(app, channel)
            except (discord.Forbidden, discord.HTTPException) as exc:
                print(f"NEW TICKET ACCESS SYNC ERROR: {exc}", flush=True)

    app.open_ticket = open_ticket_with_access

    async def assign_ticket_wrapper(guild, channel, user, tried_ids=None):
        await assign_ticket_to_staff(app, guild, channel, user, tried_ids)

    app.assign_ticket_to_staff = assign_ticket_wrapper

    app.bot.add_view(GrammarTestView(app))

    guild_obj = discord.Object(id=app.GUILD_ID)
    app.tree.remove_command("grammer", guild=guild_obj)

    @app_commands.command(
        name="grammer",
        description="Start the weekly grammar test for customer-facing ticket staff (Owner only)",
    )
    async def grammer(interaction: discord.Interaction):
        if not app.is_server_owner(interaction.user):
            await interaction.response.send_message(
                "Only the server owner can start a grammar qualification cycle.",
                ephemeral=True,
            )
            return
        guild = interaction.guild or app.bot.get_guild(app.GUILD_ID)
        if not guild:
            await interaction.response.send_message("Run this inside the server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        state = grammar_state(app, guild.id)
        state["cycle_id"] = uuid.uuid4().hex[:12]
        state["started_at"] = app.now().isoformat()
        state["passes"] = {}
        app.save_data()

        await sync_all_open_tickets(app, guild)

        eligible = [
            member
            for member in guild.members
            if not member.bot and is_nonexec_ticket_helper(member)
        ]
        sent = 0
        failed = []
        for member in eligible:
            try:
                await dm_grammar_test(app, member)
                sent += 1
            except (discord.Forbidden, discord.HTTPException):
                failed.append(member.display_name)
            await asyncio.sleep(0.05)

        message = (
            f"✅ New grammar cycle started. **{sent}/{len(eligible)}** eligible non-executive ticket staff were DM'd. "
            "Their ticket sending permission stays locked until they pass."
        )
        if failed:
            message += "\n\nCould not DM: " + ", ".join(failed[:20])
        await interaction.followup.send(message[:1900], ephemeral=True)

    app.tree.add_command(grammer, guild=guild_obj, override=True)

    async def grammar_expiry_watch():
        await app.bot.wait_until_ready()
        while not app.bot.is_closed():
            await asyncio.sleep(3600)
            guild = app.bot.get_guild(app.GUILD_ID)
            if guild:
                try:
                    await sync_all_open_tickets(app, guild)
                except Exception as exc:
                    print(f"GRAMMAR EXPIRY SYNC ERROR: {exc}", flush=True)

    async def on_ready_ticket_access():
        await asyncio.sleep(14)
        guild = app.bot.get_guild(app.GUILD_ID)
        if not guild:
            return
        await sync_all_open_tickets(app, guild)
        if not getattr(app, "_grammar_expiry_task_started", False):
            app._grammar_expiry_task_started = True
            asyncio.create_task(grammar_expiry_watch())
        print(
            "TICKET ACCESS READY: executives + support base; department option access; weekly grammar gating active.",
            flush=True,
        )

    async def on_guild_channel_create_ticket_access(channel):
        if not isinstance(channel, discord.TextChannel):
            return
        if not ticket_category_name(channel):
            return
        await asyncio.sleep(0.8)
        try:
            await sync_ticket_channel(app, channel)
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def on_member_update_ticket_access(before, after):
        if before.guild.id != app.GUILD_ID:
            return
        before_roles = {r.id for r in before.roles}
        after_roles = {r.id for r in after.roles}
        if before_roles == after_roles:
            return
        await asyncio.sleep(0.5)
        await sync_all_open_tickets(app, after.guild)

    async def grammar_message_guard(message):
        if message.author.bot or isinstance(message.channel, discord.DMChannel):
            return
        if not app.is_ticket_channel(message.channel.id):
            return
        guild = message.guild
        member = guild.get_member(message.author.id) if guild else None
        if not member or is_executive(member):
            return
        if not is_nonexec_ticket_helper(member):
            return
        if grammar_qualified(app, member):
            return
        try:
            await message.delete()
            notice = await message.channel.send(
                f"{member.mention} your weekly grammar qualification is not current, so that ticket reply was blocked. "
                "Complete the latest grammar-test DM before replying to customers."
            )
            await asyncio.sleep(8)
            await notice.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass

    app.bot.add_listener(on_ready_ticket_access, "on_ready")
    app.bot.add_listener(on_guild_channel_create_ticket_access, "on_guild_channel_create")
    app.bot.add_listener(on_member_update_ticket_access, "on_member_update")
    app.bot.add_listener(grammar_message_guard, "on_message")

    print(
        "Ticket grammar/access module loaded: /grammer + department routing + executive exemption.",
        flush=True,
    )

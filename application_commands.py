"""Slash commands for NON-EMPLOYMENT Roblox community applications."""

import asyncio
import discord
from discord import app_commands

from application_forms import FORMS, choices
from application_review_core import can_review, decide, emoji_text, resolve_reviewer
from application_review_ui import ReviewView, send_review


def setup(app):
    if getattr(app, "_community_application_commands_loaded", False):
        return
    app._community_application_commands_loaded = True

    # Reuse the existing modal/scorer, but replace its available community roles.
    app.APPLICATION_QUESTIONS.clear()
    app.APPLICATION_QUESTIONS.update(FORMS)
    app.send_application_to_executives = lambda app_id, record: send_review(app, app_id, record)

    guild_obj = discord.Object(id=app.GUILD_ID)
    app.tree.remove_command("apply", guild=guild_obj)
    app.tree.remove_command("application", guild=guild_obj)

    @app_commands.command(name="apply", description="Open a Ryanair Roblox community role application")
    @app_commands.describe(application_type="Community role or department")
    @app_commands.choices(application_type=choices(app_commands))
    async def apply_cmd(interaction: discord.Interaction, application_type: str):
        if application_type == "senior_management" and app.get_user_level(interaction.user) < 2:
            await interaction.response.send_message(
                "Senior Management applications are for existing Ryanair community staff.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(
            app.ApplicationModal(interaction.user.id, application_type, interaction.user.id)
        )

    group = app_commands.Group(
        name="application",
        description="Send and review Roblox community role applications",
    )

    @group.command(name="send", description="Send a community application to a selected user")
    @app_commands.describe(member="Applicant", application_type="Application type")
    @app_commands.choices(application_type=choices(app_commands))
    async def send_cmd(interaction: discord.Interaction, member: discord.Member, application_type: str):
        _, reviewer = resolve_reviewer(app, interaction)
        if not (can_review(app, reviewer) or app.is_support_staff(reviewer)):
            await interaction.response.send_message(
                "Customer Support / Senior Management / Recruitment permission required.",
                ephemeral=True,
            )
            return
        if member.bot:
            await interaction.response.send_message("Applications cannot be sent to bots.", ephemeral=True)
            return
        form = FORMS[application_type]
        embed = discord.Embed(
            title=f"{emoji_text(app, interaction.guild, form['emoji'], '✈️')} Ryanair {form['label']} Application",
            description=(
                "Press **Start Application** below and answer every question carefully. "
                "A human community reviewer will choose **Pass**, **Consider** or **Fail**."
            ),
            color=app.RYANAIR_BLUE,
            timestamp=app.now(),
        )
        embed.set_footer(text="Ryanair Roblox Community Applications")
        app.apply_configured_banner(embed, interaction.guild, "applications")
        try:
            await member.send(
                embed=embed,
                view=app.ApplicationStartView(member.id, application_type, interaction.user.id),
            )
        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message("I could not DM that user.", ephemeral=True)
            return
        app.log_action(interaction.user.id, "Community Application Sent", f"{form['label']} to {member} ({member.id})")
        await interaction.response.send_message(
            f"{emoji_text(app, interaction.guild, 'tick', '✅')} Application sent to {member.mention}.",
            ephemeral=True,
        )

    @group.command(name="pass", description="Pass a Roblox community application")
    @app_commands.describe(application_id="Application ID", reason="Human review reason")
    async def pass_cmd(interaction: discord.Interaction, application_id: str, reason: str):
        await decide(app, interaction, application_id, "pass", reason)

    @group.command(name="fail", description="Fail a Roblox community application")
    @app_commands.describe(application_id="Application ID", reason="Human review reason")
    async def fail_cmd(interaction: discord.Interaction, application_id: str, reason: str):
        await decide(app, interaction, application_id, "fail", reason)

    @group.command(name="consider", description="Take a Roblox community application into consideration")
    @app_commands.describe(application_id="Application ID", reason="Why another review is needed")
    async def consider_cmd(interaction: discord.Interaction, application_id: str, reason: str):
        await decide(app, interaction, application_id, "consider", reason)

    @group.command(name="view", description="View a Roblox community application review record")
    @app_commands.describe(application_id="Application ID")
    async def view_cmd(interaction: discord.Interaction, application_id: str):
        _, reviewer = resolve_reviewer(app, interaction)
        if not can_review(app, reviewer):
            await interaction.response.send_message("Application reviewer permission required.", ephemeral=True)
            return
        app_id = application_id.strip().upper()
        record = app.applications.get(app_id)
        if not record:
            await interaction.response.send_message("Application ID not found.", ephemeral=True)
            return
        status = record.get("status", "awaiting_review")
        status_key = "tick" if status == "passed" else "cross" if status == "failed" else "document"
        embed = discord.Embed(
            title=f"{emoji_text(app, interaction.guild, status_key, '📄')} Application {app_id}",
            description=(
                f"**Applicant:** <@{record['user_id']}>\n"
                f"**Type:** {record.get('type_label')}\n"
                f"**Score:** {record.get('score', 'N/A')}/10\n"
                f"**Status:** `{status}`\n"
                f"**Summary:** {record.get('summary', 'N/A')}\n"
                f"**Review reason:** {record.get('review_reason', 'Not reviewed yet.')}"
            ),
            color=app.RYANAIR_BLUE,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @group.command(name="emojis", description="Check the custom server emojis used by the bot")
    async def emojis_cmd(interaction: discord.Interaction):
        if not app.is_server_owner(interaction.user):
            await interaction.response.send_message("Owner only.", ephemeral=True)
            return
        names = getattr(app, "server_emoji_names", {})
        resolver = getattr(app, "server_emoji", None)
        found, missing = [], []
        for key, name in names.items():
            value = resolver(interaction.guild, key) if resolver else None
            if hasattr(value, "id"):
                found.append(f"{value} `{name}`")
            else:
                missing.append(f"`{name}`")
        embed = discord.Embed(
            title=f"{emoji_text(app, interaction.guild, 'ryanair_yellow', '✈️')} Server Emoji Sync",
            description="Custom emojis are resolved by their server names, so no hard-coded emoji IDs are required.",
            color=app.RYANAIR_BLUE,
        )
        embed.add_field(
            name=f"{emoji_text(app, interaction.guild, 'tick', '✅')} Found ({len(found)})",
            value="\n".join(found)[:1024] or "None",
            inline=False,
        )
        embed.add_field(
            name=f"{emoji_text(app, interaction.guild, 'cross', '❌')} Missing ({len(missing)})",
            value="\n".join(missing)[:1024] or "None",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    app.tree.add_command(apply_cmd, guild=guild_obj, override=True)
    app.tree.add_command(group, guild=guild_obj, override=True)

    async def restore_views():
        await asyncio.sleep(2)
        for app_id, record in list(app.applications.items()):
            if record.get("status") not in {"passed", "failed"}:
                try:
                    app.bot.add_view(ReviewView(app, app_id))
                except Exception:
                    pass

    async def on_ready_restore_views():
        app.bot.loop.create_task(restore_views())

    app.bot.add_listener(on_ready_restore_views, "on_ready")
    print("Community application commands loaded: /apply and /application pass/fail/consider.", flush=True)

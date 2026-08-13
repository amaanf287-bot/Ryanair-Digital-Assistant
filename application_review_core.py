"""Human review helpers for NON-EMPLOYMENT Roblox community game staff applications.

These are volunteer/community Discord roles for a Roblox airline roleplay server.
The bot never automatically decides pass/fail; a human reviewer explicitly chooses.
"""

import discord
from application_forms import FORMS, REVIEW_ROLES


def resolve_reviewer(app, interaction):
    guild = interaction.guild or app.bot.get_guild(app.GUILD_ID)
    member = guild.get_member(interaction.user.id) if guild else interaction.user
    return guild, member


def can_review(app, member):
    if not member:
        return False
    if app.is_server_owner(member) or app.get_user_level(member) >= 4:
        return True
    return any(role.name in REVIEW_ROLES for role in getattr(member, "roles", []))


def emoji_text(app, guild, key, fallback):
    resolver = getattr(app, "server_emoji_text", None)
    return resolver(guild, key) if resolver else fallback


async def decide(app, interaction, application_id, action, reason):
    app_id = application_id.strip().upper()
    guild, reviewer = resolve_reviewer(app, interaction)
    if not can_review(app, reviewer):
        await interaction.response.send_message("Senior Management / Recruitment / Director+ required.", ephemeral=True)
        return
    record = app.applications.get(app_id)
    if not record:
        await interaction.response.send_message("Application ID not found.", ephemeral=True)
        return
    if record.get("status") in {"passed", "failed"}:
        await interaction.response.send_message(f"Already **{record['status']}**.", ephemeral=True)
        return
    if record.get("application_type") == "senior_management" and action == "pass":
        if app.get_user_level(reviewer) < 4 and not app.is_server_owner(reviewer):
            await interaction.response.send_message("Director+ must pass Senior Management applications.", ephemeral=True)
            return

    record["status"] = {"pass":"passed", "fail":"failed", "consider":"under_consideration"}[action]
    record["reviewed_by"] = interaction.user.id
    record["review_reason"] = reason[:1000]
    record["reviewed_at"] = app.now().isoformat()
    app.applications[app_id] = record

    applicant = guild.get_member(int(record["user_id"])) if guild else None
    assigned = None
    if action == "pass" and applicant:
        role_name = FORMS.get(record["application_type"], {}).get("role")
        target = discord.utils.get(guild.roles, name=role_name)
        if target:
            try:
                await applicant.add_roles(target, reason=f"Human approved community application {app_id}")
                assigned = target
            except (discord.Forbidden, discord.HTTPException):
                pass
    app.save_data()

    key, fallback = {"pass":("tick","✅"), "fail":("cross","❌"), "consider":("document","📄")}[action]
    title = {"pass":"Application Passed", "fail":"Application Failed", "consider":"Application Under Consideration"}[action]
    colour = {"pass":0x22C55E, "fail":0xEF4444, "consider":0xF59E0B}[action]
    embed = discord.Embed(
        title=f"{emoji_text(app, guild, key, fallback)} {title}",
        description=(f"**Application ID:** `{app_id}`\n**Type:** {record.get('type_label')}\n"
                     f"**Applicant:** <@{record['user_id']}>\n**Reviewed by:** {interaction.user.mention}\n**Reason:** {reason}"),
        color=colour, timestamp=app.now())
    if assigned:
        embed.add_field(name="Community Role Assigned", value=assigned.mention, inline=False)
    elif action == "pass":
        embed.add_field(name="Role Assignment", value="Passed, but automatic Discord role assignment failed.", inline=False)
    embed.set_footer(text="Ryanair Roblox Community Applications")
    app.apply_configured_banner(embed, guild, "applications")
    if applicant:
        try:
            await applicant.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass
    app.log_action(interaction.user.id, title, f"{app_id} — {reason}")
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

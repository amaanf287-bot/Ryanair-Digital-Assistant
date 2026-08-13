"""Review DMs/buttons for NON-EMPLOYMENT Roblox community applications.

A human reviewer must press Pass, Consider or Fail. The preliminary AI score is
advisory and never makes the final decision.
"""

import discord

from application_forms import FORMS
from application_review_core import can_review, decide, emoji_text


class ReviewButton(discord.ui.Button):
    def __init__(self, app, app_id, action, label, style, emoji):
        super().__init__(
            label=label,
            style=style,
            emoji=emoji,
            custom_id=f"ryr-community-app:{action}:{app_id}",
        )
        self.app_module = app
        self.application_id = app_id
        self.review_action = action

    async def callback(self, interaction):
        await decide(
            self.app_module,
            interaction,
            self.application_id,
            self.review_action,
            f"Human review completed using the {self.label} button.",
        )


class ReviewView(discord.ui.View):
    def __init__(self, app, app_id):
        super().__init__(timeout=None)
        self.add_item(ReviewButton(app, app_id, "pass", "Pass", discord.ButtonStyle.success, "✅"))
        self.add_item(ReviewButton(app, app_id, "consider", "Consider", discord.ButtonStyle.secondary, "📄"))
        self.add_item(ReviewButton(app, app_id, "fail", "Fail", discord.ButtonStyle.danger, "❌"))


async def send_review(app, app_id, record):
    guild = app.bot.get_guild(app.GUILD_ID)
    if not guild:
        return

    reviewers = {m.id: m for m in guild.members if not m.bot and can_review(app, m)}
    if guild.owner:
        reviewers[guild.owner.id] = guild.owner

    form = FORMS[record["application_type"]]
    icon = emoji_text(app, guild, form["emoji"], "✈️")
    tick = emoji_text(app, guild, "tick", "✅")
    document = emoji_text(app, guild, "document", "📄")
    cross = emoji_text(app, guild, "cross", "❌")

    summary = discord.Embed(
        title=f"{icon} Community Application Review — {record['type_label']}",
        description=(
            f"**Application ID:** `{app_id}`\n"
            f"**Applicant:** <@{record['user_id']}>\n"
            f"**Preliminary writing-quality score:** **{record['score']}/10**\n\n"
            f"**System summary:** {record['summary']}\n"
            f"**Concerns:** {record['concerns']}\n\n"
            f"{tick} **Pass**   {document} **Consider**   {cross} **Fail**\n\n"
            "This is a Roblox community role application. The score is advisory only; "
            "a human reviewer makes the final decision."
        ),
        color=app.RYANAIR_BLUE,
        timestamp=app.now(),
    )
    summary.set_footer(text="Ryanair Roblox Community Applications")
    app.apply_configured_banner(summary, guild, "applications")

    answer_embeds = []
    for start in range(0, len(form["questions"]), 3):
        embed = discord.Embed(
            title=f"{document} Application Answers — {record['type_label']}",
            color=app.RYANAIR_BLUE,
        )
        for (_, question), answer in zip(
            form["questions"][start:start + 3],
            record["answers"][start:start + 3],
        ):
            embed.add_field(name=question[:256], value=answer[:1024] or "No answer", inline=False)
        answer_embeds.append(embed)

    for member in reviewers.values():
        try:
            await member.send(embed=summary, view=ReviewView(app, app_id))
            for embed in answer_embeds:
                await member.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    try:
        await app.log_to_channel(
            "Community Application Submitted",
            f"Application `{app_id}` — <@{record['user_id']}> — {record['type_label']} — {record['score']}/10",
            guild.get_member(record["sent_by"]) or app.bot.user,
            0x2ECC71,
        )
    except Exception:
        pass

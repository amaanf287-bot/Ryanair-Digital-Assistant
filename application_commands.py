"""Website-only application redirect commands.

The old Discord application forms/review workflow is intentionally disabled.
Applications are handled on the community website; Discord only directs users
to the public #website channel where management can publish the current link.
"""

import discord
from discord import app_commands


def setup(app):
    if getattr(app, "_website_application_redirect_loaded", False):
        return
    app._website_application_redirect_loaded = True

    guild_obj = discord.Object(id=app.GUILD_ID)

    # Remove any old application commands/groups registered by previous versions.
    app.tree.remove_command("apply", guild=guild_obj)
    app.tree.remove_command("application", guild=guild_obj)

    def website_message(guild):
        channel = discord.utils.get(guild.text_channels, name="website") if guild else None
        channel_text = channel.mention if channel else "#website"
        return (
            f"Please apply on our website. The application link can be found in {channel_text}."
        )

    @app_commands.command(
        name="apply",
        description="Find the Ryanair community application website",
    )
    async def apply_cmd(interaction: discord.Interaction):
        await interaction.response.send_message(
            website_message(interaction.guild),
            ephemeral=True,
        )

    @app_commands.command(
        name="application",
        description="Find the Ryanair community application website",
    )
    async def application_cmd(interaction: discord.Interaction):
        await interaction.response.send_message(
            website_message(interaction.guild),
            ephemeral=True,
        )

    app.tree.add_command(apply_cmd, guild=guild_obj, override=True)
    app.tree.add_command(application_cmd, guild=guild_obj, override=True)

    print(
        "Applications switched to website-only: /apply and /application now point users to #website.",
        flush=True,
    )

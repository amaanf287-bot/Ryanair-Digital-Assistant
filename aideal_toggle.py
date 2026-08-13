"""Per-ticket /aideal true|false toggle for the Ryanair Roblox community bot."""

import discord
from discord import app_commands


def setup(app):
    if getattr(app, "_aideal_toggle_loaded", False):
        return
    app._aideal_toggle_loaded = True

    guild_obj = discord.Object(id=app.GUILD_ID)
    app.tree.remove_command("aideal", guild=guild_obj)

    @app_commands.command(
        name="aideal",
        description="Turn AI handling on or off for this ticket",
    )
    @app_commands.describe(
        enabled="True = AI handles this ticket; False = human support takes over",
    )
    async def aideal_toggle(interaction: discord.Interaction, enabled: bool):
        await interaction.response.defer(ephemeral=True)

        if not app.is_support_staff(interaction.user):
            await interaction.followup.send("Customer Support role required.", ephemeral=True)
            return
        if not app.is_ticket_channel(interaction.channel_id):
            await interaction.followup.send("Use this command inside an open support ticket.", ephemeral=True)
            return

        channel_id = interaction.channel_id
        app.last_activity[channel_id] = app.now()
        user_id = app.get_user_id_from_channel(channel_id)
        user = app.bot.get_user(user_id) if user_id else None

        if enabled:
            app.ticket_ai_active[channel_id] = True
            app.connected_staff.pop(channel_id, None)
            app.ticket_ai_history[channel_id] = []
            app.save_data()

            tick = getattr(app, "server_emoji_text", lambda g, k: "✅")(interaction.guild, "tick")
            await interaction.channel.send(
                embed=app.plain_embed(
                    f"{tick} {interaction.user.mention} enabled AI handling for **this ticket only**. "
                    "Human handling is paused until `/aideal enabled:false` or a staff member replies."
                )
            )
            if user:
                try:
                    await user.send(
                        embed=app.plain_embed(
                            "The AI assistant is now helping with this support ticket. "
                            "You can keep chatting normally."
                        )
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass
                app.bot.loop.create_task(
                    app.ticket_ai_respond(
                        interaction.channel,
                        user,
                        "Please introduce yourself briefly and ask what the user needs help with.",
                    )
                )

            await interaction.followup.send(
                "AI handling is ON for this ticket only.",
                ephemeral=True,
            )
            return

        # False: stop AI only in this ticket and make the staff member who ran
        # the command the active human agent immediately.
        app.ticket_ai_active[channel_id] = False
        app.connected_staff[channel_id] = interaction.user.id
        app.save_data()

        cross = getattr(app, "server_emoji_text", lambda g, k: "❌")(interaction.guild, "cross")
        await interaction.channel.send(
            embed=app.plain_embed(
                f"{cross} AI handling is now **OFF for this ticket only**. "
                f"{interaction.user.mention} has taken over as the human support agent."
            )
        )
        if user:
            try:
                await user.send(
                    embed=app.plain_embed(
                        f"AI support has been paused for your ticket. "
                        f"{interaction.user.display_name} is now handling it as a human support agent."
                    )
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        await interaction.followup.send(
            "AI handling is OFF for this ticket. You are now the connected human agent.",
            ephemeral=True,
        )

    app.tree.add_command(aideal_toggle, guild=guild_obj, override=True)
    print("AI deal toggle loaded: /aideal enabled:true|false", flush=True)

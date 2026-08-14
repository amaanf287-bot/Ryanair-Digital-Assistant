"""Owner command for publishing the permanent Information/Verification channel content.

Command spelling intentionally follows the server owner's requested spelling:
    /channel annoucments

It refreshes only messages previously created by this module, so rerunning it does
not stack duplicate rules/help posts.
"""

import asyncio

import discord
from discord import app_commands


RULES_BANNER = "https://cdn.discordapp.com/attachments/1397863907506389027/1519780475269414912/image.png?ex=6a80b85d&is=6a7f66dd&hm=ca26848d793c64b75e876b4ef1439535ed100d06b952d292b54a28b790b8ab38&"
VERIFY_HELP_BANNER = "https://cdn.discordapp.com/attachments/1397863907506389027/1519780476003422400/image.png?ex=6a80b85d&is=6a7f66dd&hm=57dafcf6dd20aea5fe026e954ac32dd99e61eae92955fb71df8fab5ed496551e&"
TRAVEL_ASSISTANT_BANNER = "https://cdn.discordapp.com/attachments/1397863907506389027/1519780474518503494/image.png?ex=6a80b85d&is=6a7f66dd&hm=0c9c10a2401513fe6116789848f55fb8ba54751fbc853b1c994ef49c0d57f7ba&"
RYANAIR_HELP_BANNER = "https://cdn.discordapp.com/attachments/1397863907506389027/1519780474871091210/image.png?ex=6a80b85d&is=6a7f66dd&hm=c246560c3d24e739b4dc5aa69b8178b66ed285b964c2f093168b57f5d427138f&"

ROBLOX_GROUP_ID = 35660093
ROBLOX_GROUP_URL = f"https://www.roblox.com/groups/{ROBLOX_GROUP_ID}/Ryanair"
BLOXLINK_URL = "https://blox.link/"
STATE_KEY = "_channel_announcements_messages_v1"


def _channel(guild, name):
    return discord.utils.get(guild.text_channels, name=name)


def _state(app, guild):
    cfg = app.branding_config.setdefault(str(guild.id), {})
    return cfg.setdefault(STATE_KEY, {})


async def _remove_previous(app, channel):
    state = _state(app, channel.guild)
    previous = list(state.get(channel.name, []))
    for message_id in previous:
        try:
            await channel.get_partial_message(int(message_id)).delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException, ValueError, TypeError):
            pass
        await asyncio.sleep(0.08)
    state[channel.name] = []
    app.save_data()


async def _record(app, channel, messages):
    state = _state(app, channel.guild)
    state[channel.name] = [str(message.id) for message in messages]
    app.save_data()


def _brand_footer(embed):
    embed.set_footer(text="Ryanair • More Choice. Lower Fares. Great Care.")
    return embed


def _rules_embed(app, guild):
    bot_commands = _channel(guild, "bot-commands")
    photo_gallery = _channel(guild, "photo-gallery")
    bot_commands_text = bot_commands.mention if bot_commands else "#bot-commands"
    photo_gallery_text = photo_gallery.mention if photo_gallery else "#photo-gallery"
    assistant_text = app.bot.user.mention if app.bot.user else "@Ryanair Digital Assistant"

    embed = discord.Embed(
        title="Server Rules",
        description=(
            "All server members are required to adhere to the server rules.\n"
            "Breaking them will result in appropriate action based on the severity of the violation."
        ),
        color=app.RYANAIR_BLUE,
    )
    rules = [
        (
            "Rule 1",
            "Racism, discrimination, pornography, graphic content, swearing or profanity are strictly prohibited. "
            "The Discord Community Guidelines apply at all times.",
        ),
        (
            "Rule 2",
            "Being in possession of stolen assets will result in an immediate ban, which may extend to groups where you hold a senior role.",
        ),
        (
            "Rule 3",
            "Harassment, gossiping, starting drama and toxicity are forbidden. All members should feel welcomed. "
            "Memes or content that target or mock individuals in a toxic manner will not be tolerated.",
        ),
        (
            "Rule 4",
            "Do not spam, raid or mass mention users. Advertising other groups through server links or direct messages to server members is strictly prohibited.",
        ),
        (
            "Rule 5",
            f"Refrain from pinging Senior Management. If you require assistance, message {assistant_text} with your enquiry.",
        ),
        (
            "Rule 6",
            f"Ensure all messages and media are appropriate and non-offensive. Use channels for their intended purpose only "
            f"(e.g. commands in {bot_commands_text} and media in {photo_gallery_text}).",
        ),
        ("Rule 7", "Do not discuss resignations or firings."),
        (
            "Rule 8",
            "Keep all voice interactions respectful. Only play appropriate audio, and avoid playing sounds that are excessively loud, distorted or high-pitched.",
        ),
        (
            "Rule 9",
            "When attending our flights and other events, you must follow the Roblox Community Standards as well as our general rules at all times.",
        ),
        (
            "Rule 10",
            "By utilising the music features, you agree to adhere to Rule 8 regarding audio usage. "
            "Once you have read and agreed to these guidelines, run the command `!acceptmusicrules` to gain access to the music channel.",
        ),
    ]
    for title, text in rules:
        embed.add_field(name=title, value=text, inline=False)
    embed.set_image(url=RULES_BANNER)
    return _brand_footer(embed)


class VerifyHelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="Roblox Group",
                style=discord.ButtonStyle.link,
                url=ROBLOX_GROUP_URL,
            )
        )


class TravelScheduleView(discord.ui.View):
    def __init__(self, website_channel):
        super().__init__(timeout=None)
        if website_channel:
            self.add_item(
                discord.ui.Button(
                    label="Our Schedule",
                    style=discord.ButtonStyle.link,
                    url=website_channel.jump_url,
                )
            )


class RyanairHelpCentreView(discord.ui.View):
    def __init__(self, website_channel):
        super().__init__(timeout=None)
        if website_channel:
            self.add_item(
                discord.ui.Button(
                    label="Help Centre",
                    style=discord.ButtonStyle.link,
                    url=website_channel.jump_url,
                )
            )


class RyanairHelpRequestView(discord.ui.View):
    def __init__(self, app):
        super().__init__(timeout=None)
        self.app = app

    @discord.ui.button(
        label="Help!",
        style=discord.ButtonStyle.danger,
        custom_id="ryanair_information_help_request_v1",
    )
    async def help_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            embed = discord.Embed(
                description=(
                    "**Ryanair Digital Assistant**\n\n"
                    "Hello, I'm Ryanair's **Digital Assistant!**\n"
                    "Are you looking for assistance?"
                ),
                color=self.app.RYANAIR_BLUE,
            )
            embed.set_author(
                name="Assistance",
                icon_url=self.app.bot.user.display_avatar.url if self.app.bot.user else None,
            )
            embed.set_footer(text="Ryanair Digital Assistant")
            self.app.apply_configured_banner(embed, interaction.guild, "modmail")
            await interaction.user.send(embed=embed, view=self.app.ConfirmView(interaction.user))
            await interaction.response.send_message(
                "I've sent you a DM. Check your direct messages to continue with support.",
                ephemeral=True,
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I couldn't DM you. Please enable direct messages from server members and press **Help!** again.",
                ephemeral=True,
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "I couldn't start the support DM right now. Please try again in a moment.",
                ephemeral=True,
            )


def _verify_embed(app, guild):
    verify_channel = _channel(guild, "verify")
    verify_text = verify_channel.mention if verify_channel else "#verify"
    assistant_text = app.bot.user.mention if app.bot.user else "@Ryanair Digital Assistant"

    embed = discord.Embed(
        title="Struggling to access our server?",
        description=(
            "**Follow the steps below to complete the verification process:**\n\n"
            f"**1:** Make sure that you have joined our Roblox group, **Ryanair**.\n"
            f"🔗 {ROBLOX_GROUP_URL}\n\n"
            "**2:** Link your account with **@Bloxlink** by following the instructions outlined on their website.\n"
            f"🔗 {BLOXLINK_URL}\n\n"
            f"**3:** Run the `/verify` command in {verify_text}.\n\n"
            f"**Still having problems?** Contact {assistant_text} to be connected to our Customer Service team "
            "to troubleshoot your issue."
        ),
        color=app.RYANAIR_BLUE,
    )
    return embed


def _travel_embed(app, guild):
    website_channel = _channel(guild, "website")
    website_text = website_channel.mention if website_channel else "#website"
    embed = discord.Embed(
        title="Travel Assistant",
        description=(
            "All travel updates are posted here.\n\n"
            "Make sure to check the Events tab on Discord or Roblox to see when our flights are — "
            f"or visit {website_text} for the full schedule.\n\n"
            "Safe travels!"
        ),
        color=app.RYANAIR_BLUE,
    )
    embed.set_image(url=TRAVEL_ASSISTANT_BANNER)
    return _brand_footer(embed)


def _help_intro_embed(app):
    embed = discord.Embed(
        title="Ryanair Help",
        description=(
            "## Got a question? We've got answers.\n\n"
            "The quickest way to get help is through Ryanair's Digital Assistant, our automated support system, "
            "with our friendly Customer Service team ready to assist you!\n\n"
            "> Press the button below to request assistance."
        ),
        color=app.RYANAIR_BLUE,
    )
    return embed


def _help_centre_embed(app, guild):
    website_channel = _channel(guild, "website")
    website_text = website_channel.mention if website_channel else "#website"
    embed = discord.Embed(
        title="Ryanair Help",
        description=(
            f"Self-serve through our Help Centre in {website_text} to search for questions and find answers in our FAQs "
            "and how-to guidance from your computer, laptop, tablet or phone.\n\n"
            "Alternatively, you can speak with our friendly Digital Assistant, where you can connect to the appropriate "
            "support team for assistance."
        ),
        color=app.RYANAIR_BLUE,
    )
    embed.set_image(url=RYANAIR_HELP_BANNER)
    return _brand_footer(embed)


async def _publish_rules(app, guild):
    channel = _channel(guild, "rules")
    if not channel:
        return False, "#rules was not found"
    await _remove_previous(app, channel)
    message = await channel.send(embed=_rules_embed(app, guild))
    await _record(app, channel, [message])
    return True, channel.mention


async def _publish_verify_help(app, guild):
    channel = _channel(guild, "verify-help")
    if not channel:
        return False, "#verify-help was not found"
    await _remove_previous(app, channel)
    banner = await channel.send(VERIFY_HELP_BANNER)
    body = await channel.send(embed=_verify_embed(app, guild), view=VerifyHelpView())
    await _record(app, channel, [banner, body])
    return True, channel.mention


async def _publish_travel(app, guild):
    channel = _channel(guild, "travel-assistant")
    if not channel:
        return False, "#travel-assistant was not found"
    await _remove_previous(app, channel)
    website_channel = _channel(guild, "website")
    message = await channel.send(
        embed=_travel_embed(app, guild),
        view=TravelScheduleView(website_channel),
    )
    await _record(app, channel, [message])
    return True, channel.mention


async def _publish_help(app, guild):
    channel = _channel(guild, "ryanair-help")
    if not channel:
        return False, "#ryanair-help was not found"
    await _remove_previous(app, channel)
    website_channel = _channel(guild, "website")
    intro = await channel.send(embed=_help_intro_embed(app), view=RyanairHelpRequestView(app))
    centre = await channel.send(
        embed=_help_centre_embed(app, guild),
        view=RyanairHelpCentreView(website_channel),
    )
    await _record(app, channel, [intro, centre])
    return True, channel.mention


async def publish_all(app, guild):
    results = []
    for publisher in (_publish_rules, _publish_verify_help, _publish_travel, _publish_help):
        try:
            ok, detail = await publisher(app, guild)
            results.append((ok, detail))
        except (discord.Forbidden, discord.HTTPException) as exc:
            results.append((False, f"{type(exc).__name__}: {str(exc)[:160]}"))
        await asyncio.sleep(0.25)
    return results


def setup(app):
    if getattr(app, "_channel_announcements_loaded", False):
        return
    app._channel_announcements_loaded = True

    guild_obj = discord.Object(id=app.GUILD_ID)
    app.tree.remove_command("channel", guild=guild_obj)

    channel_group = app_commands.Group(
        name="channel",
        description="Publish permanent Ryanair channel information",
    )

    @channel_group.command(
        name="annoucments",
        description="Refresh Rules, Verify Help, Travel Assistant and Ryanair Help posts",
    )
    async def annoucments(interaction: discord.Interaction):
        if not app.is_server_owner(interaction.user):
            await interaction.response.send_message(
                "Only the server owner can refresh the permanent channel announcements.",
                ephemeral=True,
            )
            return
        guild = interaction.guild or app.bot.get_guild(app.GUILD_ID)
        if not guild:
            await interaction.response.send_message("Run this command inside the server.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        results = await publish_all(app, guild)
        lines = [
            f"{'✅' if ok else '❌'} {detail}"
            for ok, detail in results
        ]
        await interaction.followup.send(
            "**Channel announcements refresh complete.**\n\n" + "\n".join(lines),
            ephemeral=True,
        )

    app.tree.add_command(channel_group, guild=guild_obj, override=True)

    # Persistent support button for the Ryanair Help message.
    app.bot.add_view(RyanairHelpRequestView(app))

    print(
        "Channel announcements loaded: /channel annoucments publishes rules + verify help + travel assistant + Ryanair help.",
        flush=True,
    )

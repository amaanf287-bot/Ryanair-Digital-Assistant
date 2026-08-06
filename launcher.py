import asyncio
import traceback

import discord

import bot as app


# The companion bots only use Discord's REST API to fetch users and send DMs.
# They do not need privileged gateway intents. Replacing them here prevents a
# disabled Server Members intent on either companion application from stopping
# all three bots during startup.
app.auto_bot = discord.Client(intents=discord.Intents.none())
app.ryanair_flight_bot = discord.Client(intents=discord.Intents.none())


@app.auto_bot.event
async def on_ready():
    print(f"Automation bot online as {app.auto_bot.user}", flush=True)


@app.ryanair_flight_bot.event
async def on_ready():
    print(
        f"Ryanair Flight Operations bot online as {app.ryanair_flight_bot.user}",
        flush=True,
    )


async def start_client(name: str, client: discord.Client, token: str) -> None:
    """Start one Discord client without allowing it to cancel the others."""
    try:
        print(f"Starting {name}...", flush=True)
        await client.start(token, reconnect=True)
    except discord.LoginFailure:
        print(
            f"STARTUP ERROR — {name}: Discord rejected this bot token.",
            flush=True,
        )
    except discord.PrivilegedIntentsRequired as error:
        print(
            f"STARTUP ERROR — {name}: privileged intents are disabled: {error}",
            flush=True,
        )
    except asyncio.CancelledError:
        raise
    except Exception as error:
        print(
            f"STARTUP ERROR — {name}: {type(error).__name__}: {error}",
            flush=True,
        )
        traceback.print_exc()


async def main() -> None:
    if not app.TOKEN:
        raise RuntimeError("DISCORD_TOKEN is missing from Railway variables.")

    configured_clients = [
        ("Ryanair Digital Assistant", app.bot, app.TOKEN),
    ]

    if app.AUTOMATION_TOKEN:
        if app.AUTOMATION_TOKEN == app.TOKEN:
            print(
                "AUTOMATION_TOKEN matches DISCORD_TOKEN; duplicate login skipped.",
                flush=True,
            )
        else:
            configured_clients.append(
                ("Automation bot", app.auto_bot, app.AUTOMATION_TOKEN)
            )
    else:
        print(
            "AUTOMATION_TOKEN is missing; Automation bot skipped.",
            flush=True,
        )

    if app.RYANAIR_FLIGHT_TOKEN:
        if app.RYANAIR_FLIGHT_TOKEN in {app.TOKEN, app.AUTOMATION_TOKEN}:
            print(
                "RYANAIR_FLIGHT_TOKEN matches another token; duplicate login skipped.",
                flush=True,
            )
        else:
            configured_clients.append(
                (
                    "Ryanair Flight Operations bot",
                    app.ryanair_flight_bot,
                    app.RYANAIR_FLIGHT_TOKEN,
                )
            )
    else:
        print(
            "RYANAIR_FLIGHT_TOKEN/JET2_FLIGHT_TOKEN is missing; Flight Operations bot skipped.",
            flush=True,
        )

    tasks = [
        asyncio.create_task(start_client(name, client, token), name=name)
        for name, client, token in configured_clients
    ]

    # A failed companion bot now leaves the other clients online. If every
    # configured client stops, exit so Railway reports a failed deployment
    # instead of displaying a healthy worker with no Discord connection.
    await asyncio.gather(*tasks)
    raise RuntimeError("All configured Discord clients stopped.")


if __name__ == "__main__":
    asyncio.run(main())

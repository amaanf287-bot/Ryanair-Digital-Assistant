import asyncio
import os
import traceback

import discord


def _normalise_numeric_env(name: str, default: str | None = None) -> None:
    """Prevent placeholder text in Railway numeric variables from crashing import."""
    value = os.getenv(name)

    if value is None or not value.strip():
        if default is not None:
            os.environ[name] = default
            print(f"CONFIG WARNING — {name} was missing; using {default}.", flush=True)
        return

    try:
        int(value.strip())
    except (TypeError, ValueError):
        replacement = default if default is not None else "0"
        os.environ[name] = replacement
        print(
            f"CONFIG WARNING — {name} was not a numeric Discord ID/value; "
            f"using {replacement} so the bots can start.",
            flush=True,
        )


# bot.py converts these variables to integers while it is imported. Railway
# variables sometimes contain instruction/placeholder text such as
# RYLANS_DISCORD_USER_ID. Sanitise them before importing bot.py so one optional
# setting cannot crash the entire worker.
_numeric_defaults = {
    "GUILD_ID": "0",
    "TICKET_CATEGORY_ID": "0",
    "LOG_CHANNEL_ID": "0",
    "ANNOUNCEMENT_CHANNEL_ID": "0",
    "FLIGHT_EVENT_DURATION_MINUTES": "120",
    "RYAN_USER_ID": "0",
    "RYLAN_USER_ID": "0",
    "ANTI_RAID_TIMEOUT_DAYS": "28",
}

for _name, _default in _numeric_defaults.items():
    _normalise_numeric_env(_name, _default)

# DEPARTURES_CHANNEL_ID is optional; if it is absent bot.py falls back to the
# announcement channel. Only correct it when Railway contains an invalid value.
if os.getenv("DEPARTURES_CHANNEL_ID"):
    _normalise_numeric_env("DEPARTURES_CHANNEL_ID", "0")

import bot as app


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
        print("AUTOMATION_TOKEN is missing; Automation bot skipped.", flush=True)

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

    # Each client is isolated: one bad token or gateway configuration will no
    # longer cancel the other running Discord clients.
    await asyncio.gather(*tasks)
    raise RuntimeError("All configured Discord clients stopped.")


if __name__ == "__main__":
    asyncio.run(main())

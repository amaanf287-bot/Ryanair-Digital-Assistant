import asyncio
import os
import traceback

import discord

print("RYANAIR LAUNCHER v4 — Railway validation + music system", flush=True)


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

if os.getenv("DEPARTURES_CHANNEL_ID"):
    _normalise_numeric_env("DEPARTURES_CHANNEL_ID", "0")

import bot as app

# Music is deliberately loaded as an optional module. A future music dependency
# problem will be logged without taking the three existing Discord clients down.
try:
    import music_system
    music_system.setup(app.bot, app.groq_client)
    print("Music module ready.", flush=True)
except Exception as exc:
    print(f"MUSIC MODULE ERROR — {type(exc).__name__}: {exc}", flush=True)
    traceback.print_exc()


async def start_client(label: str, client: discord.Client, token: str) -> None:
    """Start one Discord client without allowing it to cancel the others."""
    try:
        print(f"Starting {label}...", flush=True)
        await client.start(token, reconnect=True)
    except discord.LoginFailure:
        print(f"STARTUP ERROR — {label}: Discord rejected this bot token.", flush=True)
    except discord.PrivilegedIntentsRequired as error:
        print(f"STARTUP ERROR — {label}: privileged intents are disabled: {error}", flush=True)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        print(f"STARTUP ERROR — {label}: {type(error).__name__}: {error}", flush=True)
        traceback.print_exc()


async def main() -> None:
    if not app.TOKEN:
        raise RuntimeError("DISCORD_TOKEN is missing from Railway variables.")

    # These are neutral startup labels only. Renaming the bots in Discord does
    # not require any code change and does not alter their tokens.
    configured_clients = [("Primary Discord bot", app.bot, app.TOKEN)]

    if app.AUTOMATION_TOKEN:
        if app.AUTOMATION_TOKEN == app.TOKEN:
            print("AUTOMATION_TOKEN matches DISCORD_TOKEN; duplicate login skipped.", flush=True)
        else:
            configured_clients.append(("Automation Discord bot", app.auto_bot, app.AUTOMATION_TOKEN))
    else:
        print("AUTOMATION_TOKEN is missing; Automation bot skipped.", flush=True)

    if app.RYANAIR_FLIGHT_TOKEN:
        if app.RYANAIR_FLIGHT_TOKEN in {app.TOKEN, app.AUTOMATION_TOKEN}:
            print("RYANAIR_FLIGHT_TOKEN matches another token; duplicate login skipped.", flush=True)
        else:
            configured_clients.append(("Flight Discord bot", app.ryanair_flight_bot, app.RYANAIR_FLIGHT_TOKEN))
    else:
        print("RYANAIR_FLIGHT_TOKEN/JET2_FLIGHT_TOKEN is missing; Flight bot skipped.", flush=True)

    tasks = [
        asyncio.create_task(start_client(label, client, token), name=label)
        for label, client, token in configured_clients
    ]

    await asyncio.gather(*tasks)
    raise RuntimeError("All configured Discord clients stopped.")


if __name__ == "__main__":
    asyncio.run(main())

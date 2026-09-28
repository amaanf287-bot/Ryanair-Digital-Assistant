# Jet2 Digital Assistant — Discord Automation

This repository is now configured for the **Jet2 Roblox** Discord server.

## Railway variables

Add these in **Railway → Variables**. The code reads them automatically at startup.

### Required
- `DISCORD_TOKEN`
- `GUILD_ID`
- `TICKET_CATEGORY_ID`
- `LOG_CHANNEL_ID`
- `ANNOUNCEMENT_CHANNEL_ID`
- `DEPARTURES_CHANNEL_ID`
- `GROQ_API_KEY`

### Bot/automation tokens
- `AUTOMATION_TOKEN` — optional second Discord bot token
- `JET2_FLIGHT_TOKEN` — optional flight bot token

### Owner / anti-raid
- `RYAN_USER_ID`
- `RYLAN_USER_ID`
- `ANTI_RAID_TIMEOUT_DAYS`

### Jet2 branding and server configuration
- `JET2_SERVER_NAME`
- `JET2_BRAND_NAME`
- `JET2_BOT_NAME`
- `JET2_DEFAULT_ACCESS_ROLE`
- `JET2_MEMBER_ROLE`
- `JET2_PASSENGER_ROLE`
- `JET2_STAFF_ROLE`
- `JET2_MANAGEMENT_ROLE`
- `JET2_NEWS_ROLE`
- `JET2_LOG_CHANNEL_NAME`
- `JET2_TICKET_CATEGORY_NAME`
- `JET2_ANNOUNCEMENT_CHANNEL_NAME`
- `JET2_DEPARTURES_CHANNEL_NAME`
- `JET2_VERIFY_CHANNEL_NAME`
- `JET2_WEBSITE_URL`
- `JET2_ROBLOX_GROUP_URL`
- `JET2_APPLICATION_URL`
- `JET2_SUPPORT_URL`
- `JET2_SERVER_ICON_URL`
- `JET2_BANNER_URL`
- `JET2_PRIMARY_COLOR`
- `JET2_SECONDARY_COLOR`
- `JET2_TIMEZONE`
- `JET2_PREFIX`

## Channel access

The server rebuild now treats **every channel as rank-locked**. Public/reference channels deny `@everyone` and grant access through the configured Jet2 access roles. Staff, management, director, executive, operations, recruitment, support, development and log categories retain their more restrictive role locks.

## Deployment

Railway can automatically deploy the new GitHub commit if the Railway service is connected to this repository. **Railway environment variables are not created from GitHub automatically** because tokens and secrets must remain private; add the variable names above once in Railway and fill in your values.

The bot requires the Discord permissions needed for its moderation, channel, role, ticket, logging and server-rebuild features.

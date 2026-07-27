JET2.RBLX BOT — TICKETS, APPLICATIONS, PAX FLIGHTS, LOGGING AND ANTI-RAID

DEPLOYMENT
1. Replace the bot.py in your GitHub repository with this bot.py.
2. Keep your existing Railway variables.
3. Add the two variables below using the actual Discord user IDs:
   RYAN_USER_ID=your_discord_user_id
   RYLAN_USER_ID=rylans_discord_user_id
4. Commit/push the change, then deploy the latest commit in Railway.
5. Check the Railway deploy log for the command sync message.

REQUIRED CORE RAILWAY VARIABLES
DISCORD_TOKEN
GUILD_ID
TICKET_CATEGORY_ID
LOG_CHANNEL_ID
ANNOUNCEMENT_CHANNEL_ID
DEPARTURES_CHANNEL_ID
GROQ_API_KEY
RYAN_USER_ID
RYLAN_USER_ID

OPTIONAL
ANTI_RAID_TIMEOUT_DAYS=28
AUTOMATION_TOKEN
JET2_FLIGHT_TOKEN

BOT PERMISSIONS NEEDED
View Audit Log
Manage Server
Manage Roles
Manage Channels
Moderate Members
Kick Members
Ban Members
Create Invite
Manage Events
Send Messages
Embed Links
Attach Files
Add Reactions
Read Message History

IMPORTANT
- Put the bot role ABOVE every staff role it may need to remove, restore or manage.
- The anti-raid system detects actions through Discord audit logs, rolls back where Discord permits, and locks the responsible staff account. It cannot stop the first Discord API action before it occurs.
- Deleted message history cannot be recreated. A kicked member cannot be forced back, so the bot attempts to DM a one-use invite.
- AI is OFF in tickets by default. It only starts after staff run /aideal. /connect and any staff reply turn AI OFF.
- Ticket inactivity warning is sent after 8 hours; automatic closure occurs 3 hours later if nobody replies.
- /paxflight now calls the shared flight implementation directly.
- The file contains an estimated 99 root slash commands/groups, below Discord's 100 guild CHAT_INPUT command limit.

VALIDATION
The Python file passed syntax compilation and static command checks. It was not connected to a live Discord server in this environment.

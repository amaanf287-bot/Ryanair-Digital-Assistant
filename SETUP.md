# ✈️ Ryanair Digital Assistant - Setup Guide

## What you need before starting:
1. Your bot token (from Discord Developer Portal)
2. Your Discord Server ID
3. A category ID in your server (where tickets will appear)
4. A log channel ID (where closed ticket logs go)

---

## Step 1 - Get your Server ID
1. Open Discord
2. Go to Settings > Advanced > Turn on Developer Mode
3. Right click your server name > Copy Server ID

## Step 2 - Create a Ticket Category
1. In your server, create a new Category (e.g. "Support Tickets")
2. Right click it > Copy ID

## Step 3 - Create a Log Channel
1. Create a channel called #ticket-logs
2. Right click it > Copy ID

## Step 4 - Fill in your .env file
Rename .env.example to .env and fill in:
- DISCORD_TOKEN = your bot token
- GUILD_ID = your server ID
- TICKET_CATEGORY_ID = the category ID from Step 2
- LOG_CHANNEL_ID = the log channel ID from Step 3

## Step 5 - Host on Railway (Free)
1. Go to https://railway.app and sign up with GitHub
2. Click "New Project" > "Deploy from GitHub repo"
3. Upload these files to a GitHub repo first
4. Add your .env values in Railway under "Variables"
5. Deploy!

---

## Commands Summary

| Command | Who can use | What it does |
|---|---|---|
| /reply | All staff | Reply to user (visible to staff) |
| /anonreply | All staff | Reply anonymously |
| /close | All staff | Close ticket + log it |
| /requeststaff @member | All staff | Request another staff member |
| /snippet [name] | All staff | Send a preset reply |
| /snippetadd [name] [message] | Senior Management + 🔒 | Add a preset reply |
| /snippetlist | All staff | View all presets |
| /snippetdelete [name] | Senior Management + 🔒 | Delete a preset |

---

## Role Permissions
- 🔒 = Full access to everything
- Senior Management = Can add/delete snippets, reply, close
- Support Staff = Can reply, close, request staff only

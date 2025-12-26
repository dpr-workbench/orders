# Multi-Category Orders & Messages Reporter (Discord)

Scans 7 Discord categories for messages containing 📜 (orders) or ✉️ (messages), posting unacknowledged items to dedicated output channels.

## What it does

- Scans text channels within 7 hardcoded Discord categories
- Detects 📜 for orders, ✉️ for messages (in message content)
- Messages with both emojis are posted to both output channels
- Skips messages acknowledged (✅ reacted) by any user with a specific role
- Posts results as embed + button links to 14 output channels (2 per category)
- Runs 3× daily via GitHub Actions

## Categories

| Category                    | Orders Channel          | Messages Channel          |
| --------------------------- | ----------------------- | ------------------------- |
| Anjevinian                  | Posts to orders channel | Posts to messages channel |
| Communist Party of Tinh Hai | Posts to orders channel | Posts to messages channel |
| National Tinh Hai Party     | Posts to orders channel | Posts to messages channel |
| Kampotian Liberation Army   | Posts to orders channel | Posts to messages channel |
| Free Laonam                 | Posts to orders channel | Posts to messages channel |
| Kwangchoan Peoples' Front   | Posts to orders channel | Posts to messages channel |
| Laonam Protectorate         | Posts to orders channel | Posts to messages channel |

All 14 output channels are excluded from scanning (no feedback loops).

## Setup

1. **Create a Discord bot**

   - In the Developer Portal, enable **MESSAGE CONTENT INTENT** and **SERVER MEMBERS INTENT**
   - Invite the bot to your server with:
     - _View Channels_, _Read Message History_ (server-wide)
     - _Send Messages_, _Embed Links_ (in all 14 output channels)

2. **Repo secrets (Settings → Secrets and variables → Actions)**

   - `DISCORD_TOKEN` – Bot token
   - `DISCORD_GUILD_ID` – Guild (server) ID

3. **Repo variables (Settings → Variables)**

   - _(Optional)_ `WINDOW_HOURS` – How far back to scan (default: 168 = 1 week)
   - _(Optional)_ `MAX_RESULTS` – Safety cap per category (default: 500)

4. **Schedule**
   - The workflow runs 3× daily at **4:30 AM GMT**, **4:30 PM GMT**, and **10:30 PM GMT**

## Acknowledgment

Messages are considered acknowledged when any user with role ID `1438610222267633734` reacts with ✅.

## Local testing

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r bot/requirements.txt
export DISCORD_TOKEN=... \
       DISCORD_GUILD_ID=...
python bot/report.py
```

## Notes

- Category and channel IDs are hardcoded in `bot/report.py`
- The 14 output channels are never scanned
- Both emojis can appear in the same message (dual-posted)

---

## Acceptance criteria

- [ ] Scans 7 categories for 📜 and ✉️ in message content
- [ ] Posts orders to category-specific orders channels
- [ ] Posts messages to category-specific messages channels
- [ ] Excludes all 14 output channels from scanning
- [ ] Role-based acknowledgment (role ID `1438610222267633734`)
- [ ] Runs 3× daily (4:30, 16:30, 22:30 GMT)

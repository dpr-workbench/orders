# Multi-Category Orders & Messages Reporter — Design Document

## Overview

This document outlines the redesign of the Discord bot from a server-wide order scanner to a **category-based dual-channel reporter** that separates orders (📜) and messages (✉️) into dedicated output channels.

---

## Current System

- Scans the entire server for messages containing 📜
- Posts all unacknowledged orders to a single report channel
- Runs on schedule or manually

---

## New System Architecture

### Core Concepts

| Concept                 | Description                                                                  |
| ----------------------- | ---------------------------------------------------------------------------- |
| **Category**            | One of 7 hardcoded logical groupings (e.g., "Electronics", "Clothing", etc.) |
| **Order**               | A message reacted with 📜 (`:scroll:`)                                       |
| **Message**             | A message reacted with ✉️ (`:envelope:`)                                     |
| **Output Channel Pair** | Each category has 2 output channels: one for orders, one for messages        |

### Key Changes

1. **7 Hardcoded Categories** — Each category maps to:

   - A set of source channels to scan
   - An orders output channel (for 📜 reactions)
   - A messages output channel (for ✉️ reactions)

2. **Dual Emoji Support**

   - 📜 `:scroll:` → Orders
   - ✉️ `:envelope:` → Messages

3. **14 Output Channels Excluded from Scanning**

   - The 14 output channels (7 × 2) are never scanned for reactions
   - Prevents feedback loops and duplicate reporting

4. **3× Daily Schedule**
   - 4:30 AM GMT
   - 4:30 PM GMT
   - 10:30 PM GMT

---

## Configuration Structure

```python
# Each category: source_channel_id -> (name, orders_output, messages_output)
CATEGORIES = {
    1438682137619468318: {
        "name": "Anjevinian",
        "orders_output_channel_id": 1453946617295012003,
        "messages_output_channel_id": 1453946725831282708,
    },
    1438682567778766928: {
        "name": "Communist Party of Tinh Hai",
        "orders_output_channel_id": 1453947205441425570,
        "messages_output_channel_id": 1453947310449885238,
    },
    1438683810228211894: {
        "name": "National Tinh Hai Party",
        "orders_output_channel_id": 1453947396177395873,
        "messages_output_channel_id": 1453947529422176327,
    },
    1438684269001179237: {
        "name": "Kampotian Liberation Army",
        "orders_output_channel_id": 1453947655813206169,
        "messages_output_channel_id": 1453947757164499025,
    },
    1438685313085214781: {
        "name": "Free Laonam",
        "orders_output_channel_id": 1453947848285618299,
        "messages_output_channel_id": 1453947946369417259,
    },
    1438684432453337210: {
        "name": "Kwangchoan Peoples' Front",
        "orders_output_channel_id": 1453948101562859581,
        "messages_output_channel_id": 1453948192457621585,
    },
    1438685650248401073: {
        "name": "Laonam Protectorate",
        "orders_output_channel_id": 1453948278411624478,
        "messages_output_channel_id": 1453948350796926996,
    },
}

# All 14 output channels (excluded from scanning)
OUTPUT_CHANNEL_IDS = {
    1453946617295012003, 1453946725831282708,  # Anjevinian
    1453947205441425570, 1453947310449885238,  # Communist Party of Tinh Hai
    1453947396177395873, 1453947529422176327,  # National Tinh Hai Party
    1453947655813206169, 1453947757164499025,  # Kampotian Liberation Army
    1453947848285618299, 1453947946369417259,  # Free Laonam
    1453948101562859581, 1453948192457621585,  # Kwangchoan Peoples' Front
    1453948278411624478, 1453948350796926996,  # Laonam Protectorate
}

# Role ID for acknowledgment (replaces user ID list)
ACK_ROLE_ID = 1438610222267633734
```

### Environment Variables

| Variable           | Description                                        |
| ------------------ | -------------------------------------------------- |
| `DISCORD_TOKEN`    | Bot token                                          |
| `DISCORD_GUILD_ID` | Target server ID                                   |
| `WINDOW_HOURS`     | How far back to scan (default: 168 hours / 1 week) |

> **Note:** `DISCORD_ACK_USER_IDS` is replaced by role-based acknowledgment. Any user with role `1438610222267633734` can acknowledge with ✅.

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         SCANNING PHASE                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  For each of 7 categories:                                      │
│    1. Get source channels for this category                     │
│    2. Scan messages in time window                              │
│    3. Check for 📜 reactions → collect as "orders"              │
│    4. Check for ✉️ reactions → collect as "messages"            │
│    5. Filter out already-acknowledged (✅ by ACK_USER_IDS)      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        POSTING PHASE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  For each category:                                             │
│    • Post orders to orders_output_channel_id                    │
│    • Post messages to messages_output_channel_id                │
│                                                                 │
│  Format: Embed header + button links (same as current)          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Scanning Logic

### What Gets Scanned

Each of the 7 category channels is scanned. These are Discord **category channels** (channel type), and all text channels within them are scanned.

```python
def should_scan_channel(channel: discord.TextChannel) -> bool:
    # Never scan output channels (all 14 of them)
    if channel.id in OUTPUT_CHANNEL_IDS:
        return False

    # Only scan if channel is under one of the 7 category IDs
    if channel.category_id in CATEGORIES:
        return True

    return False
```

### Emoji Detection (Content-Based)

Emojis are detected in **message content** (not reactions):

```python
SCROLL_EMOJI = "📜"
ENVELOPE_EMOJI = "✉️"

def detect_emojis(content: str) -> tuple[bool, bool]:
    """Returns (has_scroll, has_envelope)"""
    has_scroll = SCROLL_EMOJI in content
    has_envelope = ENVELOPE_EMOJI in content
    return has_scroll, has_envelope
```

### Dual-Posting

If a message contains **both** 📜 and ✉️, it is posted to **both** the orders and messages output channels for that category.

### Acknowledgment (Role-Based)

```python
ACK_ROLE_ID = 1438610222267633734

async def is_acknowledged(msg: discord.Message, guild: discord.Guild) -> bool:
    """Return True if any user with ACK_ROLE_ID has reacted with ✅"""
    check_reaction = next((r for r in msg.reactions if str(r.emoji) == "✅"), None)
    if not check_reaction:
        return False

    async for user in check_reaction.users():
        member = guild.get_member(user.id)
        if member and any(role.id == ACK_ROLE_ID for role in member.roles):
            return True

    return False
```

---

## Schedule Configuration

### GitHub Actions Cron (GMT times)

```yaml
schedule:
  - cron: "30 4 * * *" # 4:30 AM GMT
  - cron: "30 16 * * *" # 4:30 PM GMT
  - cron: "30 22 * * *" # 10:30 PM GMT
```

### Window Calculation

With 3 runs per day at 4:30, 16:30, and 22:30 GMT:

- 4:30 → 16:30 = 12 hours
- 16:30 → 22:30 = 6 hours
- 22:30 → 4:30 = 6 hours

**Recommended `WINDOW_HOURS`:** 12 (covers the longest gap with some overlap)

---

## Output Format

Each output channel receives:

### Embed Header

```
┌────────────────────────────────────────┐
│ 📜 Unacknowledged Orders               │
│ Category: Electronics                  │
│ Window: last 12 hours                  │
│ Total: 15                              │
└────────────────────────────────────────┘
```

### Button Links (up to 25 per message)

```
[#channel-name · 14:30 • Preview of message...] → jump_url
[#channel-name · 15:45 • Another preview...] → jump_url
```

---

## Module Structure

```
bot/
├── report.py           # Main entrypoint (refactored)
├── config.py           # Category definitions and env parsing
├── scanner.py          # Channel scanning logic
├── poster.py           # Report posting logic
└── requirements.txt    # Dependencies
```

Or keep it simple in a single file with clear sections.

---

## Open Questions

~~All questions resolved — ready for implementation.~~

---

## Implementation Plan

| Phase | Task                                                          | Effort |
| ----- | ------------------------------------------------------------- | ------ |
| 1     | Define category configuration schema                          | Low    |
| 2     | Refactor scanning to be reaction-based (if needed)            | Medium |
| 3     | Implement per-category scanning with output channel exclusion | Medium |
| 4     | Implement dual-channel posting (orders/messages)              | Low    |
| 5     | Update GitHub Actions schedule                                | Low    |
| 6     | Testing with real channel IDs                                 | Medium |

---

## Summary

| Aspect             | Current                | New                                                 |
| ------------------ | ---------------------- | --------------------------------------------------- |
| Categories         | None (server-wide)     | 7 hardcoded Discord categories                      |
| Emojis             | 📜 only                | 📜 orders + ✉️ messages (both in content)           |
| Output channels    | 1                      | 14 (2 per category)                                 |
| Dual-post          | N/A                    | Yes — messages with both emojis go to both channels |
| Excluded from scan | None                   | 14 output channels                                  |
| Acknowledgment     | Specific user IDs      | Role-based (role ID `1438610222267633734`)          |
| Schedule           | 2× daily (5am/5pm PST) | 3× daily (4:30/16:30/22:30 GMT)                     |

---

## Categories Reference

| Category ID           | Name                        | Orders Channel        | Messages Channel      |
| --------------------- | --------------------------- | --------------------- | --------------------- |
| `1438682137619468318` | Anjevinian                  | `1453946617295012003` | `1453946725831282708` |
| `1438682567778766928` | Communist Party of Tinh Hai | `1453947205441425570` | `1453947310449885238` |
| `1438683810228211894` | National Tinh Hai Party     | `1453947396177395873` | `1453947529422176327` |
| `1438684269001179237` | Kampotian Liberation Army   | `1453947655813206169` | `1453947757164499025` |
| `1438685313085214781` | Free Laonam                 | `1453947848285618299` | `1453947946369417259` |
| `1438684432453337210` | Kwangchoan Peoples' Front   | `1453948101562859581` | `1453948192457621585` |
| `1438685650248401073` | Laonam Protectorate         | `1453948278411624478` | `1453948350796926996` |

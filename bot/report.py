import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Set, Tuple

import discord

# ---------------------------
# Configuration from env
# ---------------------------
TOKEN = os.environ["DISCORD_TOKEN"]
GUILD_ID = int(os.environ["DISCORD_GUILD_ID"])

# Simplified knobs
WINDOW_HOURS = int(os.environ.get("WINDOW_HOURS", "168") or "168")  # default 1 week
CONCURRENCY = int(os.environ.get("CONCURRENCY", "10") or "10")

# Safety caps
MAX_RESULTS = int(os.environ.get("MAX_RESULTS", "500") or "500")
MAX_BUTTONS_PER_MSG = 25  # Discord: 5 rows * 5 buttons

# ---------------------------
# Emoji constants
# ---------------------------
SCROLL_EMOJI = "📜"
ENVELOPE_EMOJI = "✉️"
CHECK_EMOJI = "✅"

# ---------------------------
# Role-based acknowledgment
# ---------------------------
ACK_ROLE_ID = 1438610222267633734

# ---------------------------
# Category configuration
# Key: Discord category channel ID (the parent category)
# Value: name, orders output channel, messages output channel
# ---------------------------
CATEGORIES: Dict[int, Dict] = {
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

# Build set of all output channel IDs (excluded from scanning)
OUTPUT_CHANNEL_IDS: Set[int] = set()
for cat in CATEGORIES.values():
    OUTPUT_CHANNEL_IDS.add(cat["orders_output_channel_id"])
    OUTPUT_CHANNEL_IDS.add(cat["messages_output_channel_id"])

# ---------------------------
# Discord client
# ---------------------------
intents = discord.Intents.default()
intents.guilds = True
intents.members = True  # Required to check role membership
intents.message_content = True
client = discord.Client(intents=intents)

# ---------------------------
# Helpers
# ---------------------------


def _detect_emojis(content: str) -> Tuple[bool, bool]:
    """Return (has_scroll, has_envelope) based on message content."""
    if not content:
        return False, False
    has_scroll = SCROLL_EMOJI in content
    has_envelope = ENVELOPE_EMOJI in content
    return has_scroll, has_envelope


async def _is_acknowledged(msg: discord.Message, guild: discord.Guild) -> bool:
    """Return True if any user with ACK_ROLE_ID has reacted with ✅."""
    check_reaction = next((r for r in msg.reactions if str(r.emoji) == CHECK_EMOJI), None)
    if not check_reaction:
        return False

    async for user in check_reaction.users(limit=None):
        member = guild.get_member(user.id)
        if member and any(role.id == ACK_ROLE_ID for role in member.roles):
            return True

    return False


def _get_channels_for_category(guild: discord.Guild, category_id: int) -> List[discord.TextChannel]:
    """Get all text channels under a category, excluding output channels."""
    channels: List[discord.TextChannel] = []
    for ch in guild.text_channels:
        if ch.category_id == category_id and ch.id not in OUTPUT_CHANNEL_IDS:
            channels.append(ch)
    return channels


async def _scan_category(
    guild: discord.Guild,
    category_id: int,
    category_config: Dict,
    since: datetime,
    sem: asyncio.Semaphore,
) -> Tuple[List[Dict], List[Dict]]:
    """Scan all channels in a category for orders and messages.
    
    Returns (orders_list, messages_list) where each item contains message metadata.
    """
    orders: List[Dict] = []
    messages: List[Dict] = []

    channels = _get_channels_for_category(guild, category_id)

    async def scan_channel(ch: discord.TextChannel) -> Tuple[List[Dict], List[Dict]]:
        ch_orders: List[Dict] = []
        ch_messages: List[Dict] = []

        try:
            async with sem:
                async for msg in ch.history(limit=None, after=since, oldest_first=False):
                    content = msg.content or ""

                    # Check for emojis in content
                    has_scroll, has_envelope = _detect_emojis(content)
                    if not has_scroll and not has_envelope:
                        continue

                    # Check if already acknowledged
                    if await _is_acknowledged(msg, guild):
                        continue

                    # Build result dict
                    result = {
                        "channel": f"#{ch.name}",
                        "created_at_utc": msg.created_at.replace(tzinfo=timezone.utc).isoformat(timespec="minutes"),
                        "jump_url": msg.jump_url,
                        "preview": content.replace("\n", " ").strip()[:140] or "(no text)",
                    }

                    # Add to appropriate lists (can be both!)
                    if has_scroll:
                        ch_orders.append(result)
                    if has_envelope:
                        ch_messages.append(result)

                    # Bound per-channel results
                    if len(ch_orders) + len(ch_messages) >= MAX_RESULTS:
                        break

        except discord.Forbidden:
            pass
        except discord.HTTPException:
            pass

        return ch_orders, ch_messages

    # Scan all channels concurrently
    results = await asyncio.gather(*(scan_channel(ch) for ch in channels))

    for ch_orders, ch_messages in results:
        orders.extend(ch_orders)
        messages.extend(ch_messages)

    # Enforce caps
    if len(orders) > MAX_RESULTS:
        orders = orders[:MAX_RESULTS]
    if len(messages) > MAX_RESULTS:
        messages = messages[:MAX_RESULTS]

    return orders, messages


def _chunk_buttons(rows: List[Dict], chunk_size: int = MAX_BUTTONS_PER_MSG):
    """Yield Views with up to chunk_size buttons each."""
    for i in range(0, len(rows), chunk_size):
        chunk = rows[i : i + chunk_size]
        view = discord.ui.View()
        for r in chunk:
            hhmm = r["created_at_utc"][11:16]
            label = f'{r["channel"]} · {hhmm} • {r["preview"]}'
            if len(label) > 80:
                label = label[:77] + "…"
            view.add_item(
                discord.ui.Button(label=label, url=r["jump_url"], style=discord.ButtonStyle.link)
            )
        yield view


async def _post_results(
    channel: discord.abc.Messageable,
    results: List[Dict],
    category_name: str,
    emoji: str,
    result_type: str,
) -> None:
    """Post results to a channel with embed header and button links."""
    total = len(results)

    if total == 0:
        embed = discord.Embed(
            title=f"{emoji} Unacknowledged {result_type}",
            description=f"No matching messages in **{category_name}** in the last {WINDOW_HOURS} hours. 🎉",
        )
        await channel.send(embed=embed)
        return

    embed = discord.Embed(
        title=f"{emoji} Unacknowledged {result_type}",
        description=f"**{category_name}** — Tap a button to jump. Window: last {WINDOW_HOURS} hours.",
    )
    embed.set_footer(text=f"Total: {total}")
    await channel.send(embed=embed)

    for view in _chunk_buttons(results):
        await channel.send(view=view)


# ---------------------------
# Entrypoint
# ---------------------------
async def _main():
    await client.wait_until_ready()

    guild = client.get_guild(GUILD_ID)
    if not guild:
        print(f"Guild {GUILD_ID} not found or bot not in guild.")
        await client.close()
        return

    since = datetime.now(timezone.utc) - timedelta(hours=WINDOW_HOURS)
    sem = asyncio.Semaphore(CONCURRENCY)

    print(f"Scanning {len(CATEGORIES)} categories since {since.isoformat()}...")

    for category_id, config in CATEGORIES.items():
        category_name = config["name"]
        orders_channel_id = config["orders_output_channel_id"]
        messages_channel_id = config["messages_output_channel_id"]

        print(f"  Scanning category: {category_name} ({category_id})")

        # Scan for orders and messages
        orders, messages = await _scan_category(guild, category_id, config, since, sem)

        print(f"    Found {len(orders)} orders, {len(messages)} messages")

        # Post orders
        orders_channel = client.get_channel(orders_channel_id)
        if isinstance(orders_channel, (discord.TextChannel, discord.Thread)):
            await _post_results(orders_channel, orders, category_name, SCROLL_EMOJI, "Orders")
        else:
            print(f"    WARNING: Orders channel {orders_channel_id} not found")

        # Post messages
        messages_channel = client.get_channel(messages_channel_id)
        if isinstance(messages_channel, (discord.TextChannel, discord.Thread)):
            await _post_results(messages_channel, messages, category_name, ENVELOPE_EMOJI, "Messages")
        else:
            print(f"    WARNING: Messages channel {messages_channel_id} not found")

    print("Done!")
    await client.close()


@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    asyncio.create_task(_main())


if __name__ == "__main__":
    client.run(TOKEN)

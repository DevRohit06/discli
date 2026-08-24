import json
from typing import Any

import click
import discord


def format_output(data: Any, use_json: bool = False) -> str:
    if use_json:
        return json.dumps(data, indent=2, default=str)
    return str(data)


# Discord announced on 2026-08-12 that from 2026-11-16 channels a bot lacks
# VIEW_CHANNEL on are dropped from GET /guilds/{id}/channels and the Gateway
# entirely. There is no API that reports how many were withheld, so the only
# honest thing discli can do is say the listing is scoped.
CHANNEL_VISIBILITY_NOTE = (
    "channel listings only include channels this bot can view. From 2026-11-16 "
    "Discord omits channels without the View Channel permission from the API, so "
    "a short list may mean missing permissions rather than an empty server."
)


def warn_channel_visibility() -> None:
    """Disclose that a channel listing is scoped to the bot's visibility.

    Written to stderr so ``--json`` stdout stays a clean, unchanged payload --
    callers piping stdout into a JSON parser are unaffected.
    """
    click.echo(f"note: {CHANNEL_VISIBILITY_NOTE}", err=True)


def output(ctx: click.Context, data: Any, plain_text: str | None = None) -> None:
    """Print output respecting --json flag."""
    use_json = ctx.obj.get("use_json", False)
    if use_json:
        click.echo(format_output(data, use_json=True))
    else:
        click.echo(plain_text if plain_text is not None else format_output(data))


async def fetch_guilds(client) -> list[discord.Guild]:
    """Return cached guilds when available, otherwise fetch them over HTTP."""
    cached = list(getattr(client, "guilds", ()))
    if cached:
        return cached
    return [guild async for guild in client.fetch_guilds(limit=None)]


def _unique_match(matches: list[Any], kind: str, identifier: str):
    if not matches:
        raise click.ClickException(f"{kind} not found: {identifier}")
    if len(matches) > 1:
        ids = ", ".join(str(item.id) for item in matches)
        raise click.ClickException(
            f"Multiple {kind.lower()}s match '{identifier}' (IDs: {ids}). Use an ID."
        )
    return matches[0]


async def resolve_guild(client, identifier: str) -> discord.Guild:
    """Resolve a guild by ID or name, preferring Gateway cache state."""
    try:
        guild_id = int(identifier)
    except ValueError:
        pass
    else:
        get_guild = getattr(client, "get_guild", None)
        cached = get_guild(guild_id) if get_guild else None
        if cached is not None:
            return cached
        return await client.fetch_guild(guild_id)

    cached_matches = [
        guild
        for guild in getattr(client, "guilds", ())
        if guild.name.casefold() == identifier.casefold()
    ]
    if cached_matches:
        return _unique_match(cached_matches, "Server", identifier)

    matches = [
        guild
        async for guild in client.fetch_guilds(limit=None)
        if guild.name.casefold() == identifier.casefold()
    ]
    return _unique_match(matches, "Server", identifier)


async def resolve_channel(client, identifier: str):
    """Resolve a guild channel by ID/name or a thread by ID, cache first."""
    normalized = identifier.removeprefix("#")
    try:
        channel_id = int(normalized)
    except ValueError:
        pass
    else:
        get_channel = getattr(client, "get_channel", None)
        cached = get_channel(channel_id) if get_channel else None
        if cached is not None:
            return cached
        return await client.fetch_channel(channel_id)

    cached_matches = []
    for guild in getattr(client, "guilds", ()):
        cached_matches.extend(
            channel
            for channel in getattr(guild, "channels", ())
            if channel.name.casefold() == normalized.casefold()
        )
    if cached_matches:
        return _unique_match(cached_matches, "Channel", identifier)

    matches = []
    for guild in await fetch_guilds(client):
        channels = await guild.fetch_channels()
        matches.extend(ch for ch in channels if ch.name.casefold() == normalized.casefold())
    return _unique_match(matches, "Channel", identifier)


async def resolve_thread(client, identifier: str) -> discord.Thread:
    """Resolve an active thread by ID or name, preferring cached threads."""
    try:
        thread_id = int(identifier)
    except ValueError:
        pass
    else:
        get_channel = getattr(client, "get_channel", None)
        cached = get_channel(thread_id) if get_channel else None
        if cached is not None:
            if isinstance(cached, discord.Thread):
                return cached
            raise click.ClickException(f"Channel is not a thread: {identifier}")
        channel = await client.fetch_channel(thread_id)
        if isinstance(channel, discord.Thread):
            return channel
        raise click.ClickException(f"Channel is not a thread: {identifier}")

    cached_matches = []
    for guild in getattr(client, "guilds", ()):
        cached_matches.extend(
            thread
            for thread in getattr(guild, "threads", ())
            if thread.name.casefold() == identifier.casefold()
        )
    if cached_matches:
        return _unique_match(cached_matches, "Thread", identifier)

    matches = []
    for guild in await fetch_guilds(client):
        threads = await guild.active_threads()
        matches.extend(thread for thread in threads if thread.name.casefold() == identifier.casefold())
    return _unique_match(matches, "Thread", identifier)


async def resolve_member(guild: discord.Guild, identifier: str) -> discord.Member:
    """Resolve a guild member, preferring cached state and direct ID lookup."""
    try:
        member_id = int(identifier)
    except ValueError:
        pass
    else:
        get_member = getattr(guild, "get_member", None)
        cached = get_member(member_id) if get_member else None
        if cached is not None:
            return cached
        return await guild.fetch_member(member_id)

    normalized = identifier.removeprefix("@").casefold()
    cached_matches = [
        member
        for member in getattr(guild, "members", ())
        if member.name.casefold() == normalized or str(member).casefold() == normalized
    ]
    if cached_matches:
        return _unique_match(cached_matches, "Member", identifier)

    try:
        members = [member async for member in guild.fetch_members(limit=None)]
    except discord.Forbidden:
        raise click.ClickException(
            "Member name lookup requires Discord's Server Members privileged intent. "
            "Use the numeric member ID or enable that intent for this application."
        )
    matches = [
        member
        for member in members
        if member.name.casefold() == normalized or str(member).casefold() == normalized
    ]
    return _unique_match(matches, "Member", identifier)


async def resolve_user(client, identifier: str):
    """Resolve a user by ID or shared guild membership, preferring cache state."""
    try:
        user_id = int(identifier)
    except ValueError:
        pass
    else:
        get_user = getattr(client, "get_user", None)
        cached = get_user(user_id) if get_user else None
        if cached is not None:
            return cached
        return await client.fetch_user(user_id)

    normalized = identifier.removeprefix("@").casefold()
    cached_matches: dict[int, discord.Member] = {}
    for guild in getattr(client, "guilds", ()):
        for member in getattr(guild, "members", ()):
            if member.name.casefold() == normalized or str(member).casefold() == normalized:
                cached_matches[member.id] = member
    if cached_matches:
        return _unique_match(list(cached_matches.values()), "User", identifier)

    matches: dict[int, discord.Member] = {}
    members_forbidden = False
    for guild in await fetch_guilds(client):
        try:
            async for member in guild.fetch_members(limit=None):
                if member.name.casefold() == normalized or str(member).casefold() == normalized:
                    matches[member.id] = member
        except discord.Forbidden:
            members_forbidden = True

    if not matches and members_forbidden:
        raise click.ClickException(
            "User name lookup requires Discord's Server Members privileged intent. "
            "Use the numeric user ID or enable that intent for this application."
        )
    return _unique_match(list(matches.values()), "User", identifier)


async def resolve_role(guild: discord.Guild, identifier: str) -> discord.Role:
    """Resolve a guild role by ID or name, preferring cached roles."""
    role_id = None
    try:
        role_id = int(identifier)
    except ValueError:
        cached_matches = [
            role
            for role in getattr(guild, "roles", ())
            if role.name.casefold() == identifier.casefold()
        ]
    else:
        get_role = getattr(guild, "get_role", None)
        cached = get_role(role_id) if get_role else None
        if cached is not None:
            return cached
        cached_matches = []

    if cached_matches:
        return _unique_match(cached_matches, "Role", identifier)

    roles = await guild.fetch_roles()
    if role_id is not None:
        matches = [role for role in roles if role.id == role_id]
    else:
        matches = [role for role in roles if role.name.casefold() == identifier.casefold()]
    return _unique_match(matches, "Role", identifier)

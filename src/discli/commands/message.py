import click
import discord

from discli.client import run_rest
from discli.utils import output, resolve_channel


@click.group("message")
def message_group():
    """Send, list, edit, and delete messages."""


@message_group.command("send")
@click.argument("channel")
@click.argument("text")
@click.option("--embed-title", default=None, help="Embed title.")
@click.option("--embed-desc", default=None, help="Embed description.")
@click.option("--embed-color", default=None, help="Embed color (hex like ff0000).")
@click.option("--embed-footer", default=None, help="Embed footer text.")
@click.option("--embed-image", default=None, help="Embed image URL.")
@click.option("--embed-thumbnail", default=None, help="Embed thumbnail URL.")
@click.option("--embed-author", default=None, help="Embed author name.")
@click.option("--embed-field", multiple=True, help="Embed field (repeatable, format 'Name::Value::Inline').")
@click.option("--file", "files", multiple=True, type=click.Path(exists=True), help="File to attach (repeatable).")
@click.pass_context
def message_send(ctx, channel, text, embed_title, embed_desc, embed_color, embed_footer, embed_image, embed_thumbnail, embed_author, embed_field, files):
    """Send a message to a channel."""

    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            embed = None
            if any([embed_title, embed_desc, embed_color, embed_footer, embed_image, embed_thumbnail, embed_author, embed_field]):
                embed_kwargs = {}
                if embed_title:
                    embed_kwargs["title"] = embed_title
                if embed_desc:
                    embed_kwargs["description"] = embed_desc
                if embed_color:
                    try:
                        embed_kwargs["color"] = discord.Color(int(embed_color.lstrip("#"), 16))
                    except ValueError:
                        raise click.ClickException(f"Invalid embed color: {embed_color} (use hex like ff0000)")
                embed = discord.Embed(**embed_kwargs)
                if embed_footer:
                    embed.set_footer(text=embed_footer)
                if embed_image:
                    embed.set_image(url=embed_image)
                if embed_thumbnail:
                    embed.set_thumbnail(url=embed_thumbnail)
                if embed_author:
                    embed.set_author(name=embed_author)
                for field in embed_field:
                    parts = field.split("::")
                    name = parts[0] if len(parts) > 0 else ""
                    value = parts[1] if len(parts) > 1 else ""
                    inline = parts[2].lower() == "true" if len(parts) > 2 else False
                    embed.add_field(name=name, value=value, inline=inline)
            attachments = [discord.File(f) for f in files]
            kwargs = {"content": text, "embed": embed}
            if attachments:
                kwargs["files"] = attachments
            msg = await ch.send(**kwargs)
            data = {"id": str(msg.id), "channel": ch.name, "content": msg.content, "jump_url": msg.jump_url}
            if msg.attachments:
                data["attachments"] = [{"filename": a.filename, "url": a.url, "size": a.size} for a in msg.attachments]
            output(ctx, data, plain_text=f"Sent message {msg.id} to #{ch.name}")
        return _action(client)

    run_rest(ctx, action)


@message_group.command("list")
@click.argument("channel")
@click.option("--limit", default=10, help="Number of messages to fetch.")
@click.option("--before", default=None, help="Before date (YYYY-MM-DD or ISO).")
@click.option("--after", default=None, help="After date (YYYY-MM-DD or ISO).")
@click.pass_context
def message_list(ctx, channel, limit, before, after):
    """List recent messages in a channel."""
    from datetime import datetime

    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            kwargs = {"limit": limit}
            if before:
                kwargs["before"] = datetime.fromisoformat(before)
            if after:
                kwargs["after"] = datetime.fromisoformat(after)

            messages = []
            async for msg in ch.history(**kwargs):
                messages.append({
                    "id": str(msg.id),
                    "author": str(msg.author),
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                    "attachments": [{"filename": a.filename, "url": a.url, "size": a.size} for a in msg.attachments],
                    "embeds": [{
                        "title": e.title,
                        "description": e.description,
                        "fields": [{"name": f.name, "value": f.value, "inline": f.inline} for f in e.fields],
                        "footer": e.footer.text if e.footer else None,
                        "author": e.author.name if e.author else None,
                    } for e in msg.embeds],
                })
            plain_lines = []
            for m in messages:
                ts = m["timestamp"][:19].replace("T", " ")
                line = f"[{ts}] {m['author']}: {m['content']}"
                if m["attachments"]:
                    att = ", ".join(a["filename"] for a in m["attachments"])
                    line += f" [{att}]"
                for e in m["embeds"]:
                    embed_parts = []
                    if e.get("author"):
                        embed_parts.append(e["author"])
                    if e.get("title"):
                        embed_parts.append(f"[{e['title']}]")
                    if e.get("description"):
                        embed_parts.append(e["description"])
                    for f in e.get("fields", []):
                        embed_parts.append(f"{f['name']}: {f['value']}")
                    if e.get("footer"):
                        embed_parts.append(f"({e['footer']})")
                    if embed_parts:
                        line += " " + " | ".join(embed_parts)
                plain_lines.append(line)
            output(ctx, messages, plain_text="\n".join(plain_lines))
        return _action(client)

    run_rest(ctx, action)


@message_group.command("history")
@click.argument("channel")
@click.option("--days", default=None, type=int, help="Fetch messages from last N days.")
@click.option("--hours", default=None, type=int, help="Fetch messages from last N hours.")
@click.option("--limit", default=None, type=int, help="Max messages to fetch (default: unlimited).")
@click.pass_context
def message_history(ctx, channel, days, hours, limit):
    """Fetch deep message history from a channel."""
    from datetime import datetime, timedelta, timezone

    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            kwargs = {}
            if days:
                kwargs["after"] = datetime.now(timezone.utc) - timedelta(days=days)
            elif hours:
                kwargs["after"] = datetime.now(timezone.utc) - timedelta(hours=hours)
            if limit:
                kwargs["limit"] = limit

            messages = []
            count = 0
            async for msg in ch.history(**kwargs):
                messages.append({
                    "id": str(msg.id),
                    "author": str(msg.author),
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                    "attachments": [{"filename": a.filename, "url": a.url, "size": a.size} for a in msg.attachments],
                    "embeds": [{
                        "title": e.title,
                        "description": e.description,
                        "fields": [{"name": f.name, "value": f.value, "inline": f.inline} for f in e.fields],
                        "footer": e.footer.text if e.footer else None,
                        "author": e.author.name if e.author else None,
                    } for e in msg.embeds],
                })
                count += 1
                if count % 100 == 0:
                    click.echo(f"Fetched {count} messages...", err=True)

            plain_lines = []
            for m in messages:
                ts = m["timestamp"][:19].replace("T", " ")
                line = f"[{ts}] {m['author']}: {m['content']}"
                if m["attachments"]:
                    att = ", ".join(a["filename"] for a in m["attachments"])
                    line += f" [{att}]"
                for e in m["embeds"]:
                    embed_parts = []
                    if e.get("author"):
                        embed_parts.append(e["author"])
                    if e.get("title"):
                        embed_parts.append(f"[{e['title']}]")
                    if e.get("description"):
                        embed_parts.append(e["description"])
                    for f in e.get("fields", []):
                        embed_parts.append(f"{f['name']}: {f['value']}")
                    if e.get("footer"):
                        embed_parts.append(f"({e['footer']})")
                    if embed_parts:
                        line += " " + " | ".join(embed_parts)
                plain_lines.append(line)

            click.echo(f"Total: {len(messages)} messages", err=True)
            output(ctx, messages, plain_text="\n".join(plain_lines))
        return _action(client)

    run_rest(ctx, action)


@message_group.command("edit")
@click.argument("channel")
@click.argument("message_id")
@click.argument("new_text")
@click.pass_context
def message_edit(ctx, channel, message_id, new_text):
    """Edit a message."""

    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            await msg.edit(content=new_text)
            output(ctx, {"id": str(msg.id), "content": new_text}, plain_text=f"Edited message {msg.id}")
        return _action(client)

    run_rest(ctx, action)


@message_group.command("delete")
@click.argument("channel")
@click.argument("message_id")
@click.pass_context
def message_delete(ctx, channel, message_id):
    """Delete a message."""
    from discli.security import confirm_destructive, audit_log
    confirm_destructive("message delete", f"message {message_id} in {channel}")

    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            await msg.delete()
            audit_log("message delete", {"channel": channel, "message_id": message_id})
            output(ctx, {"id": str(msg.id), "deleted": True}, plain_text=f"Deleted message {msg.id}")
        return _action(client)

    run_rest(ctx, action)


@message_group.command("get")
@click.argument("channel")
@click.argument("message_id")
@click.pass_context
def message_get(ctx, channel, message_id):
    """Fetch a single message by ID."""

    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            data = {
                "id": str(msg.id),
                "author": str(msg.author),
                "author_id": str(msg.author.id),
                "content": msg.content,
                "timestamp": msg.created_at.isoformat(),
                "attachments": [{"filename": a.filename, "url": a.url} for a in msg.attachments],
                "embeds": [{"title": e.title, "description": e.description} for e in msg.embeds],
                "reply_to": str(msg.reference.message_id) if msg.reference else None,
                "jump_url": msg.jump_url,
            }
            plain_lines = [
                f"From: {data['author']} (ID: {data['author_id']})",
                f"At: {data['timestamp'][:19].replace('T', ' ')}",
                f"Content: {data['content']}",
            ]
            if data["attachments"]:
                plain_lines.append(f"Attachments: {', '.join(a['filename'] for a in data['attachments'])}")
            if data["reply_to"]:
                plain_lines.append(f"Reply to: {data['reply_to']}")
            output(ctx, data, plain_text="\n".join(plain_lines))
        return _action(client)

    run_rest(ctx, action)


@message_group.command("reply")
@click.argument("channel")
@click.argument("message_id")
@click.argument("text")
@click.option("--file", "files", multiple=True, type=click.Path(exists=True), help="File to attach (repeatable).")
@click.pass_context
def message_reply(ctx, channel, message_id, text, files):
    """Reply to a specific message."""

    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            original = await ch.fetch_message(int(message_id))
            attachments = [discord.File(f) for f in files]
            kwargs = {"content": text}
            if attachments:
                kwargs["files"] = attachments
            msg = await original.reply(**kwargs)
            data = {"id": str(msg.id), "channel": ch.name, "content": msg.content, "reply_to": message_id, "jump_url": msg.jump_url}
            if msg.attachments:
                data["attachments"] = [{"filename": a.filename, "url": a.url, "size": a.size} for a in msg.attachments]
            output(ctx, data, plain_text=f"Replied to {message_id} in #{ch.name}")
        return _action(client)

    run_rest(ctx, action)


@message_group.command("search")
@click.argument("channel")
@click.argument("query")
@click.option("--limit", default=None, type=int, help="Max matching results to return (default: unlimited).")
@click.option("--scan", default=500, type=int, help="Number of messages to scan (default: 500).")
@click.option("--author", default=None, help="Filter by author name.")
@click.option("--before", default=None, help="Before date (YYYY-MM-DD or ISO).")
@click.option("--after", default=None, help="After date (YYYY-MM-DD or ISO).")
@click.pass_context
def message_search(ctx, channel, query, limit, scan, author, before, after):
    """Search messages in a channel by content."""
    from datetime import datetime

    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            kwargs = {"limit": scan}
            if before:
                kwargs["before"] = datetime.fromisoformat(before)
            if after:
                kwargs["after"] = datetime.fromisoformat(after)

            results = []
            query_lower = query.lower()
            async for msg in ch.history(**kwargs):
                embeds = [{
                    "title": e.title,
                    "description": e.description,
                    "fields": [{"name": f.name, "value": f.value, "inline": f.inline} for f in e.fields],
                    "footer": e.footer.text if e.footer else None,
                    "author": e.author.name if e.author else None,
                } for e in msg.embeds]
                embed_text = " ".join(
                    " ".join(filter(None, [
                        e.get("title") or "",
                        e.get("description") or "",
                        e.get("author") or "",
                        e.get("footer") or "",
                        " ".join(f"{f['name']} {f['value']}" for f in e.get("fields", [])),
                    ]))
                    for e in embeds
                )
                searchable = (msg.content + " " + embed_text).lower()
                if query_lower not in searchable:
                    continue
                if author and author.lower() not in str(msg.author).lower():
                    continue
                results.append({
                    "id": str(msg.id),
                    "author": str(msg.author),
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                    "attachments": [{"filename": a.filename, "url": a.url, "size": a.size} for a in msg.attachments],
                    "embeds": embeds,
                })
                if limit is not None and len(results) >= limit:
                    break

            plain_lines = []
            for m in results:
                ts = m["timestamp"][:19].replace("T", " ")
                line = f"[{ts}] (msg:{m['id']}) {m['author']}: {m['content']}"
                if m["attachments"]:
                    att = ", ".join(f"{a['filename']} ({a['size']}B)" for a in m["attachments"])
                    line += f" [{att}]"
                for e in m["embeds"]:
                    embed_parts = []
                    if e.get("author"):
                        embed_parts.append(e["author"])
                    if e.get("title"):
                        embed_parts.append(f"[{e['title']}]")
                    if e.get("description"):
                        embed_parts.append(e["description"])
                    for f in e.get("fields", []):
                        embed_parts.append(f"{f['name']}: {f['value']}")
                    if e.get("footer"):
                        embed_parts.append(f"({e['footer']})")
                    if embed_parts:
                        line += " " + " | ".join(embed_parts)
                plain_lines.append(line)

            if not results:
                output(ctx, [], plain_text=f"No messages matching '{query}' found.")
            else:
                output(ctx, results, plain_text=f"Found {len(results)} match(es):\n" + "\n".join(plain_lines))
        return _action(client)

    run_rest(ctx, action)


@message_group.command("bulk-delete")
@click.argument("channel")
@click.argument("message_ids", nargs=-1, required=True)
@click.pass_context
def message_bulk_delete(ctx, channel, message_ids):
    """Delete multiple messages at once (max 100, must be < 14 days old)."""
    from discli.security import confirm_destructive, audit_log
    confirm_destructive("message bulk-delete", f"{len(message_ids)} messages in {channel}")

    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            messages = []
            for mid in message_ids:
                msg = await ch.fetch_message(int(mid))
                messages.append(msg)
            await ch.delete_messages(messages)
            audit_log("message bulk-delete", {"channel": channel, "count": len(messages)})
            output(ctx, {"deleted": len(messages)}, plain_text=f"Deleted {len(messages)} messages")
        return _action(client)

    run_rest(ctx, action)


@message_group.command("pin")
@click.argument("channel")
@click.argument("message_id")
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def message_pin(ctx, channel, message_id, reason):
    """Pin a message to its channel.

    Needs the Pin Messages permission, which Discord split out of
    Manage Messages in January 2026.
    """
    from discli.security import audit_log

    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            await msg.pin(reason=reason)
            audit_log("message pin", {"channel": channel, "message_id": message_id})
            output(ctx, {"id": str(msg.id), "pinned": True}, plain_text=f"Pinned message {msg.id}")
        return _action(client)

    run_rest(ctx, action)


@message_group.command("unpin")
@click.argument("channel")
@click.argument("message_id")
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def message_unpin(ctx, channel, message_id, reason):
    """Unpin a message from its channel."""
    from discli.security import audit_log

    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            await msg.unpin(reason=reason)
            audit_log("message unpin", {"channel": channel, "message_id": message_id})
            output(ctx, {"id": str(msg.id), "pinned": False}, plain_text=f"Unpinned message {msg.id}")
        return _action(client)

    run_rest(ctx, action)


@message_group.command("pins")
@click.argument("channel")
@click.option("--limit", default=50, type=int, help="Max pinned messages to return.")
@click.pass_context
def message_pins(ctx, channel, limit):
    """List pinned messages in a channel."""

    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)
            pinned = [
                {
                    "id": str(msg.id),
                    "author": str(msg.author),
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                    "jump_url": msg.jump_url,
                }
                async for msg in ch.pins(limit=limit)
            ]
            plain_lines = [
                f"[{p['timestamp'][:19].replace('T', ' ')}] {p['author']}: {p['content']} (ID: {p['id']})"
                for p in pinned
            ]
            output(ctx, pinned, plain_text="\n".join(plain_lines) if plain_lines else "No pinned messages.")
        return _action(client)

    run_rest(ctx, action)


# Discord opened GET /guilds/{id}/messages/search to bots on 2026-03-19, but
# discord.py 2.7.1 does not wrap it -- there is no Guild.search() to call. Going
# through discord.http.Route keeps the request inside discord.py's rate limiter
# and auth handling, unlike a hand-rolled aiohttp call would.
SEARCH_HAS_CHOICES = ["link", "embed", "file", "image", "video", "sound", "sticker", "poll"]
SEARCH_MAX_LIMIT = 25
SEARCH_MAX_OFFSET = 9975
SEARCH_MAX_CONTENT = 1024


@message_group.command("search-server")
@click.argument("server")
@click.argument("query", required=False)
@click.option("--author", "authors", multiple=True, help="Filter by author (ID or name, repeatable).")
@click.option(
    "--author-type",
    "author_types",
    multiple=True,
    type=click.Choice(["user", "bot", "webhook"]),
    help="Filter by author kind (repeatable).",
)
@click.option("--channel", "channels", multiple=True, help="Limit to these channels (name or ID, repeatable).")
@click.option("--mentions", multiple=True, help="Messages mentioning this user (ID or name, repeatable).")
@click.option(
    "--has",
    multiple=True,
    type=click.Choice(SEARCH_HAS_CHOICES),
    help="Only messages containing this kind of content (repeatable).",
)
@click.option("--extension", "extensions", multiple=True, help="Match attachments with this file extension (repeatable).")
@click.option("--pinned/--no-pinned", default=None, help="Restrict to pinned (or unpinned) messages.")
@click.option("--sort-by", type=click.Choice(["relevance", "timestamp"]), default="timestamp", help="Result ordering.")
@click.option("--sort-order", type=click.Choice(["desc", "asc"]), default="desc", help="Ordering direction.")
@click.option("--limit", default=SEARCH_MAX_LIMIT, type=int, help="Results per page (1-25).")
@click.option("--offset", default=0, type=int, help="Pagination offset (0-9975).")
@click.pass_context
def message_search_server(
    ctx, server, query, authors, author_types, channels, mentions, has,
    extensions, pinned, sort_by, sort_order, limit, offset,
):
    """Search messages across a whole server using Discord's search index.

    Unlike `message search`, which scans one channel's recent history client
    side, this hits Discord's native endpoint: every channel the bot can see,
    relevance ranking, and filters the local scan cannot express.

    Discord marks this endpoint a preview feature. It returns nothing until it
    has indexed the server; when that happens this reports the server as
    unindexed rather than as empty.
    """
    if not any([query, authors, author_types, channels, mentions, has, extensions]) and pinned is None:
        raise click.ClickException("Give a query or at least one filter; see --help.")
    if query and len(query) > SEARCH_MAX_CONTENT:
        raise click.ClickException(f"Query cannot exceed {SEARCH_MAX_CONTENT} characters.")
    if not 1 <= limit <= SEARCH_MAX_LIMIT:
        raise click.ClickException(f"--limit must be between 1 and {SEARCH_MAX_LIMIT}.")
    if not 0 <= offset <= SEARCH_MAX_OFFSET:
        raise click.ClickException(f"--offset must be between 0 and {SEARCH_MAX_OFFSET}.")

    def action(client):
        async def _action(client):
            from discord.http import Route

            from discli.utils import resolve_guild, resolve_member

            guild = await resolve_guild(client, server)

            async def _user_id(value: str) -> str:
                try:
                    return str(int(value))
                except ValueError:
                    member = await resolve_member(guild, value)
                    return str(member.id)

            # Repeated keys rather than a dict: Discord expects array params
            # as ?author_id=1&author_id=2.
            params: list[tuple[str, str]] = []
            if query:
                params.append(("content", query))
            for value in authors:
                params.append(("author_id", await _user_id(value)))
            for value in author_types:
                params.append(("author_type", value))
            for value in mentions:
                params.append(("mentions", await _user_id(value)))
            if channels:
                guild_channels = await guild.fetch_channels()
                for value in channels:
                    normalized = value.removeprefix("#").casefold()
                    matches = [
                        ch for ch in guild_channels
                        if str(ch.id) == value or ch.name.casefold() == normalized
                    ]
                    if not matches:
                        raise click.ClickException(f"Channel not found in {guild.name}: {value}")
                    if len(matches) > 1:
                        ids = ", ".join(str(ch.id) for ch in matches)
                        raise click.ClickException(
                            f"Multiple channels match '{value}' (IDs: {ids}). Use a channel ID."
                        )
                    params.append(("channel_id", str(matches[0].id)))
            for value in has:
                params.append(("has", value))
            for value in extensions:
                params.append(("attachment_extension", value.lstrip(".")))
            if pinned is not None:
                params.append(("pinned", "true" if pinned else "false"))
            params.append(("sort_by", sort_by))
            params.append(("sort_order", sort_order))
            params.append(("limit", str(limit)))
            params.append(("offset", str(offset)))

            route = Route("GET", "/guilds/{guild_id}/messages/search", guild_id=guild.id)
            payload = await client.http.request(route, params=params)

            # A 202 means the index is still building. discord.py hands back
            # 2xx bodies as-is, so the tell is a response with no "messages"
            # key. Reporting that as "no results" would be a wrong answer
            # rather than a slow one.
            groups = (payload or {}).get("messages")
            if groups is None:
                raise click.ClickException(
                    f"Discord has not finished indexing '{guild.name}' for search. "
                    "Try again shortly, or scan a single channel client-side with "
                    "'discli message search <channel> <query>'."
                )

            results = []
            for group in groups:
                if not group:
                    continue
                # Each group is the hit plus surrounding context; the hit is
                # flagged, but fall back to the first entry if it is not.
                raw = next((m for m in group if m.get("hit")), group[0])
                author = raw.get("author") or {}
                channel_id = raw.get("channel_id")
                results.append({
                    "id": raw.get("id"),
                    "channel_id": channel_id,
                    "author": author.get("global_name") or author.get("username"),
                    "author_id": author.get("id"),
                    "is_bot": author.get("bot", False),
                    "content": raw.get("content", ""),
                    "timestamp": raw.get("timestamp"),
                    "pinned": raw.get("pinned", False),
                    "attachments": [
                        {"filename": a.get("filename"), "url": a.get("url"), "size": a.get("size")}
                        for a in raw.get("attachments", [])
                    ],
                    "jump_url": f"https://discord.com/channels/{guild.id}/{channel_id}/{raw.get('id')}",
                })

            data = {
                "total_results": payload.get("total_results", len(results)),
                "returned": len(results),
                "offset": offset,
                "results": results,
            }

            plain_lines = []
            for r in results:
                stamp = (r["timestamp"] or "")[:19].replace("T", " ")
                plain_lines.append(f"[{stamp}] {r['author']}: {r['content']}")
                plain_lines.append(f"    {r['jump_url']}")
            if not results:
                plain = "No matching messages."
            else:
                plain = "\n".join(plain_lines) + f"\n\n{len(results)} of {data['total_results']} result(s)"
            output(ctx, data, plain_text=plain)
        return _action(client)

    run_rest(ctx, action)

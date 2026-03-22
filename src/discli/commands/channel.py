import click
import discord

from discli.client import run_discord
from discli.utils import output, resolve_channel, resolve_guild


@click.group("channel")
def channel_group():
    """List, create, delete, and inspect channels."""


@channel_group.command("list")
@click.option("--server", default=None, help="Server name or ID.")
@click.pass_context
def channel_list(ctx, server):
    """List channels in a server."""

    def action(client):
        async def _action(client):
            if server:
                guilds = [resolve_guild(client, server)]
            else:
                guilds = client.guilds
            channels = []
            for g in guilds:
                for ch in g.channels:
                    if isinstance(ch, (discord.TextChannel, discord.VoiceChannel)):
                        channels.append({
                            "id": str(ch.id),
                            "name": ch.name,
                            "type": str(ch.type),
                            "server": g.name,
                        })
            plain_lines = [f"#{c['name']} ({c['type']}) — {c['server']} (ID: {c['id']})" for c in channels]
            output(ctx, channels, plain_text="\n".join(plain_lines) if plain_lines else "No channels found.")
        return _action(client)

    run_discord(ctx, action)


@channel_group.command("create")
@click.argument("server")
@click.argument("name")
@click.option("--type", "channel_type", type=click.Choice(["text", "voice", "category", "forum"]), default="text")
@click.option("--topic", default=None, help="Channel topic (for text/forum).")
@click.pass_context
def channel_create(ctx, server, name, channel_type, topic):
    """Create a channel in a server."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            if channel_type == "text":
                ch = await guild.create_text_channel(name, topic=topic)
            elif channel_type == "voice":
                ch = await guild.create_voice_channel(name)
            elif channel_type == "forum":
                ch = await guild.create_forum(name, topic=topic)
            else:
                ch = await guild.create_category(name)
            data = {"id": str(ch.id), "name": ch.name, "type": str(ch.type)}
            output(ctx, data, plain_text=f"Created #{ch.name} (ID: {ch.id})")
        return _action(client)

    run_discord(ctx, action)


@channel_group.command("delete")
@click.argument("channel")
@click.pass_context
def channel_delete(ctx, channel):
    """Delete a channel."""
    from discli.security import confirm_destructive, audit_log
    confirm_destructive("channel delete", channel)

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            name = ch.name
            await ch.delete()
            audit_log("channel delete", {"channel": name})
            output(ctx, {"id": str(ch.id), "deleted": True}, plain_text=f"Deleted #{name}")
        return _action(client)

    run_discord(ctx, action)


@channel_group.command("info")
@click.argument("channel")
@click.pass_context
def channel_info(ctx, channel):
    """Show channel details."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            data = {
                "id": str(ch.id),
                "name": ch.name,
                "type": str(ch.type),
                "server": ch.guild.name,
                "topic": getattr(ch, "topic", None),
                "created_at": ch.created_at.isoformat(),
            }
            plain_lines = [f"{k}: {v}" for k, v in data.items() if v is not None]
            output(ctx, data, plain_text="\n".join(plain_lines))
        return _action(client)

    run_discord(ctx, action)


@channel_group.command("edit")
@click.argument("channel")
@click.option("--name", default=None, help="New channel name.")
@click.option("--topic", default=None, help="New channel topic.")
@click.option("--slowmode", default=None, type=int, help="Slowmode delay in seconds (0 to disable).")
@click.option("--nsfw/--no-nsfw", default=None, help="Set NSFW flag.")
@click.pass_context
def channel_edit(ctx, channel, name, topic, slowmode, nsfw):
    """Edit a channel's settings."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            kwargs = {}
            if name is not None:
                kwargs["name"] = name
            if topic is not None:
                kwargs["topic"] = topic
            if slowmode is not None:
                kwargs["slowmode_delay"] = slowmode
            if nsfw is not None:
                kwargs["nsfw"] = nsfw
            if not kwargs:
                raise click.ClickException("No changes specified.")
            await ch.edit(**kwargs)
            data = {"id": str(ch.id), "name": ch.name, "updated": list(kwargs.keys())}
            output(ctx, data, plain_text=f"Updated #{ch.name}: {', '.join(kwargs.keys())}")
        return _action(client)

    run_discord(ctx, action)


@channel_group.command("forum-post")
@click.argument("channel")
@click.argument("title")
@click.argument("content")
@click.option("--file", "files", multiple=True, type=click.Path(exists=True), help="File to attach.")
@click.pass_context
def channel_forum_post(ctx, channel, title, content, files):
    """Create a post in a forum channel."""
    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            if not isinstance(ch, discord.ForumChannel):
                raise click.ClickException(f"#{ch.name} is not a forum channel")
            attachments = [discord.File(f) for f in files]
            kwargs = {"content": content}
            if attachments:
                kwargs["files"] = attachments
            thread, msg = await ch.create_thread(name=title, **kwargs)
            data = {
                "thread_id": str(thread.id),
                "thread_name": thread.name,
                "message_id": str(msg.id),
                "channel": ch.name,
            }
            output(ctx, data, plain_text=f"Created forum post '{title}' in #{ch.name}")
        return _action(client)
    run_discord(ctx, action)


@channel_group.command("set-permissions")
@click.argument("channel")
@click.argument("target")
@click.option("--allow", default=None, help="Comma-separated permissions to allow (e.g. send_messages,read_messages).")
@click.option("--deny", default=None, help="Comma-separated permissions to deny.")
@click.option("--target-type", type=click.Choice(["role", "member"]), default="role", help="Target type.")
@click.pass_context
def channel_set_permissions(ctx, channel, target, allow, deny, target_type):
    """Set permission overwrites for a role or member on a channel."""
    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            guild = ch.guild
            if target_type == "role":
                obj = None
                try:
                    role_id = int(target)
                    obj = guild.get_role(role_id)
                except ValueError:
                    for role in guild.roles:
                        if role.name.lower() == target.lower():
                            obj = role
                            break
                if not obj:
                    raise click.ClickException(f"Role not found: {target}")
            else:
                obj = None
                try:
                    member_id = int(target)
                    obj = guild.get_member(member_id)
                except ValueError:
                    for member in guild.members:
                        if member.name.lower() == target.lower():
                            obj = member
                            break
                if not obj:
                    raise click.ClickException(f"Member not found: {target}")
            overwrite = ch.overwrites_for(obj)
            if allow:
                for perm in allow.split(","):
                    setattr(overwrite, perm.strip(), True)
            if deny:
                for perm in deny.split(","):
                    setattr(overwrite, perm.strip(), False)
            await ch.set_permissions(obj, overwrite=overwrite)
            data = {"channel": ch.name, "target": str(obj), "allow": allow, "deny": deny}
            output(ctx, data, plain_text=f"Updated permissions for {obj} on #{ch.name}")
        return _action(client)
    run_discord(ctx, action)

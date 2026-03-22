import click
import discord

from discli.client import run_discord
from discli.utils import output, resolve_channel, resolve_guild


def resolve_thread(client, identifier: str):
    """Resolve a thread by ID or name."""
    try:
        thread_id = int(identifier)
        for guild in client.guilds:
            for thread in guild.threads:
                if thread.id == thread_id:
                    return thread
    except ValueError:
        pass
    for guild in client.guilds:
        for thread in guild.threads:
            if thread.name.lower() == identifier.lower():
                return thread
    raise click.ClickException(f"Thread not found: {identifier}")


@click.group("thread")
def thread_group():
    """Create, list, and send messages in threads."""


@thread_group.command("create")
@click.argument("channel")
@click.argument("message_id")
@click.argument("name")
@click.pass_context
def thread_create(ctx, channel, message_id, name):
    """Create a thread from a message."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            thread = await msg.create_thread(name=name)
            data = {
                "id": str(thread.id),
                "name": thread.name,
                "parent_channel": ch.name,
                "parent_channel_id": str(ch.id),
                "message_id": message_id,
            }
            output(ctx, data, plain_text=f"Created thread '{thread.name}' (ID: {thread.id}) from message {message_id}")
        return _action(client)

    run_discord(ctx, action)


@thread_group.command("list")
@click.argument("channel")
@click.pass_context
def thread_list(ctx, channel):
    """List active threads in a channel."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            threads = []
            for thread in ch.threads:
                threads.append({
                    "id": str(thread.id),
                    "name": thread.name,
                    "message_count": thread.message_count,
                    "member_count": thread.member_count,
                    "archived": thread.archived,
                })
            plain_lines = [
                f"{t['name']} (ID: {t['id']}, msgs: {t['message_count']}, members: {t['member_count']}){' [archived]' if t['archived'] else ''}"
                for t in threads
            ]
            output(ctx, threads, plain_text="\n".join(plain_lines) if plain_lines else "No active threads.")
        return _action(client)

    run_discord(ctx, action)


@thread_group.command("send")
@click.argument("thread")
@click.argument("text")
@click.option("--file", "files", multiple=True, type=click.Path(exists=True), help="File to attach (repeatable).")
@click.pass_context
def thread_send(ctx, thread, text, files):
    """Send a message to a thread."""

    def action(client):
        async def _action(client):
            t = resolve_thread(client, thread)
            attachments = [discord.File(f) for f in files]
            kwargs = {"content": text}
            if attachments:
                kwargs["files"] = attachments
            msg = await t.send(**kwargs)
            data = {
                "id": str(msg.id),
                "thread": t.name,
                "thread_id": str(t.id),
                "content": msg.content,
            }
            if msg.attachments:
                data["attachments"] = [{"filename": a.filename, "url": a.url, "size": a.size} for a in msg.attachments]
            output(ctx, data, plain_text=f"Sent message {msg.id} to thread '{t.name}'")
        return _action(client)

    run_discord(ctx, action)


@thread_group.command("archive")
@click.argument("thread")
@click.pass_context
def thread_archive(ctx, thread):
    """Archive a thread."""
    def action(client):
        async def _action(client):
            t = resolve_thread(client, thread)
            await t.edit(archived=True)
            output(ctx, {"id": str(t.id), "archived": True}, plain_text=f"Archived thread '{t.name}'")
        return _action(client)
    run_discord(ctx, action)


@thread_group.command("unarchive")
@click.argument("thread")
@click.pass_context
def thread_unarchive(ctx, thread):
    """Unarchive a thread."""
    def action(client):
        async def _action(client):
            t = resolve_thread(client, thread)
            await t.edit(archived=False)
            output(ctx, {"id": str(t.id), "archived": False}, plain_text=f"Unarchived thread '{t.name}'")
        return _action(client)
    run_discord(ctx, action)


@thread_group.command("rename")
@click.argument("thread")
@click.argument("new_name")
@click.pass_context
def thread_rename(ctx, thread, new_name):
    """Rename a thread."""
    def action(client):
        async def _action(client):
            t = resolve_thread(client, thread)
            old = t.name
            await t.edit(name=new_name)
            output(ctx, {"id": str(t.id), "old_name": old, "new_name": new_name},
                   plain_text=f"Renamed thread '{old}' to '{new_name}'")
        return _action(client)
    run_discord(ctx, action)


@thread_group.command("add-member")
@click.argument("thread")
@click.argument("member_id")
@click.pass_context
def thread_add_member(ctx, thread, member_id):
    """Add a member to a thread."""
    def action(client):
        async def _action(client):
            t = resolve_thread(client, thread)
            try:
                mid = int(member_id)
            except ValueError:
                raise click.ClickException(f"Invalid member ID: {member_id}")
            member = t.guild.get_member(mid)
            if not member:
                raise click.ClickException(f"Member not found: {member_id}")
            await t.add_user(member)
            output(ctx, {"thread_id": str(t.id), "member": str(member)},
                   plain_text=f"Added {member} to thread '{t.name}'")
        return _action(client)
    run_discord(ctx, action)


@thread_group.command("remove-member")
@click.argument("thread")
@click.argument("member_id")
@click.pass_context
def thread_remove_member(ctx, thread, member_id):
    """Remove a member from a thread."""
    def action(client):
        async def _action(client):
            t = resolve_thread(client, thread)
            try:
                mid = int(member_id)
            except ValueError:
                raise click.ClickException(f"Invalid member ID: {member_id}")
            member = t.guild.get_member(mid)
            if not member:
                raise click.ClickException(f"Member not found: {member_id}")
            await t.remove_user(member)
            output(ctx, {"thread_id": str(t.id), "member": str(member)},
                   plain_text=f"Removed {member} from thread '{t.name}'")
        return _action(client)
    run_discord(ctx, action)

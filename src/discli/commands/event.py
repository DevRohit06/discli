import click
import discord

from discli.client import run_discord
from discli.utils import output, resolve_guild


@click.group("event")
def event_group():
    """Manage guild scheduled events."""


@event_group.command("list")
@click.argument("server")
@click.pass_context
def event_list(ctx, server):
    """List scheduled events in a server."""
    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            events = guild.scheduled_events
            data = []
            for e in events:
                data.append({
                    "id": str(e.id),
                    "name": e.name,
                    "description": e.description,
                    "start_time": e.start_time.isoformat() if e.start_time else None,
                    "end_time": e.end_time.isoformat() if e.end_time else None,
                    "status": str(e.status),
                    "location": str(e.location) if e.location else None,
                    "user_count": e.user_count,
                })
            plain_lines = [f"{ev['name']} ({ev['status']}) - {ev['start_time']}" for ev in data]
            output(ctx, data, plain_text="\n".join(plain_lines) if plain_lines else "No events.")
        return _action(client)
    run_discord(ctx, action)


@event_group.command("create")
@click.argument("server")
@click.argument("name")
@click.argument("start_time")
@click.option("--end-time", default=None, help="End time (ISO format).")
@click.option("--description", default=None, help="Event description.")
@click.option("--location", default=None, help="External location (makes this an external event).")
@click.option("--channel", default=None, help="Voice/stage channel for the event.")
@click.pass_context
def event_create(ctx, server, name, start_time, end_time, description, location, channel):
    """Create a scheduled event."""
    from datetime import datetime

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            start = datetime.fromisoformat(start_time)
            kwargs = {"name": name, "start_time": start}
            if description:
                kwargs["description"] = description
            if end_time:
                kwargs["end_time"] = datetime.fromisoformat(end_time)
            if location:
                kwargs["location"] = location
                kwargs["entity_type"] = discord.EntityType.external
                if not end_time:
                    raise click.ClickException("External events require --end-time")
            elif channel:
                from discli.utils import resolve_channel
                ch = resolve_channel(client, channel)
                kwargs["channel"] = ch
                if isinstance(ch, discord.StageChannel):
                    kwargs["entity_type"] = discord.EntityType.stage_instance
                else:
                    kwargs["entity_type"] = discord.EntityType.voice
            else:
                raise click.ClickException("Specify --location (external) or --channel (voice/stage)")
            event = await guild.create_scheduled_event(**kwargs)
            data = {"id": str(event.id), "name": event.name}
            output(ctx, data, plain_text=f"Created event '{event.name}' (ID: {event.id})")
        return _action(client)
    run_discord(ctx, action)


@event_group.command("delete")
@click.argument("server")
@click.argument("event_id")
@click.pass_context
def event_delete(ctx, server, event_id):
    """Delete a scheduled event."""
    from discli.security import confirm_destructive, audit_log
    confirm_destructive("event delete", f"event {event_id}")

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            event = guild.get_scheduled_event(int(event_id))
            if not event:
                raise click.ClickException(f"Event not found: {event_id}")
            name = event.name
            await event.delete()
            audit_log("event delete", {"server": server, "event_id": event_id})
            output(ctx, {"id": event_id, "deleted": True}, plain_text=f"Deleted event '{name}'")
        return _action(client)
    run_discord(ctx, action)

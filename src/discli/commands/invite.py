import click
import discord

from discli.client import run_rest
from discli.utils import output, resolve_channel, resolve_guild


@click.group("invite")
def invite_group():
    """Create, list, inspect, and revoke server invites."""


def _serialize(invite) -> dict:
    """Flatten an Invite into JSON-safe output.

    Guild.invites() and Client.fetch_invite() populate different subsets of
    these fields, so every one is read defensively.
    """
    channel = getattr(invite, "channel", None)
    inviter = getattr(invite, "inviter", None)
    guild = getattr(invite, "guild", None)
    expires_at = getattr(invite, "expires_at", None)
    created_at = getattr(invite, "created_at", None)
    target_type = getattr(invite, "target_type", None)
    target_application = getattr(invite, "target_application", None)

    return {
        "code": invite.code,
        "url": invite.url,
        "channel": getattr(channel, "name", None),
        "channel_id": str(channel.id) if channel is not None else None,
        "guild": getattr(guild, "name", None),
        "inviter": str(inviter) if inviter is not None else None,
        "uses": getattr(invite, "uses", None),
        "max_uses": getattr(invite, "max_uses", None),
        "max_age": getattr(invite, "max_age", None),
        "temporary": getattr(invite, "temporary", None),
        "created_at": created_at.isoformat() if created_at else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
        "member_count": getattr(invite, "approximate_member_count", None),
        "presence_count": getattr(invite, "approximate_presence_count", None),
        "target_type": target_type.name if target_type is not None else None,
        "target_application": getattr(target_application, "name", None),
    }


def _plain(data: dict) -> str:
    parts = [data["url"]]
    if data["channel"]:
        parts.append(f"-> #{data['channel']}")
    uses = data["uses"]
    if uses is not None:
        parts.append(f"uses: {uses}/{data['max_uses'] or 'unlimited'}")
    if data["expires_at"]:
        parts.append(f"expires: {data['expires_at'][:19].replace('T', ' ')}")
    elif data["max_age"] == 0:
        parts.append("never expires")
    if data["target_application"]:
        parts.append(f"activity: {data['target_application']}")
    if data["inviter"]:
        parts.append(f"by {data['inviter']}")
    return " | ".join(parts)


@invite_group.command("list")
@click.argument("server")
@click.pass_context
def invite_list(ctx, server):
    """List active invites for a server. Needs Manage Server."""

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            invites = [_serialize(inv) for inv in await guild.invites()]
            plain_lines = [_plain(inv) for inv in invites]
            output(ctx, invites, plain_text="\n".join(plain_lines) if plain_lines else "No active invites.")
        return _action(client)

    run_rest(ctx, action)


@invite_group.command("create")
@click.argument("channel")
@click.option("--max-age", default=0, type=int, help="Seconds until the invite expires (0 = never).")
@click.option("--max-uses", default=0, type=int, help="Number of uses before the invite expires (0 = unlimited).")
@click.option("--temporary", is_flag=True, default=False, help="Grant temporary membership (kicked on disconnect).")
@click.option("--unique/--no-unique", default=True, help="Force a new invite instead of reusing an equivalent one.")
@click.option(
    "--activity",
    default=None,
    help=(
        "Application ID of a Discord Activity to launch. Voice channels only. "
        "Find IDs in the Developer Portal or Discord's activity list."
    ),
)
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def invite_create(ctx, channel, max_age, max_uses, temporary, unique, activity, reason):
    """Create an invite to a channel, optionally launching an Activity."""
    from discli.security import audit_log

    if activity is not None:
        try:
            activity_id = int(activity)
        except ValueError:
            raise click.ClickException(
                f"--activity takes a numeric application ID, got: {activity}"
            )
    else:
        activity_id = None

    def action(client):
        async def _action(client):
            ch = await resolve_channel(client, channel)

            kwargs = {
                "max_age": max_age,
                "max_uses": max_uses,
                "temporary": temporary,
                "unique": unique,
                "reason": reason,
            }
            if activity_id is not None:
                # Discord only launches embedded applications from voice
                # channels; fail here rather than on an opaque 400.
                if not isinstance(ch, discord.VoiceChannel):
                    raise click.ClickException(
                        "Activity invites require a voice channel. "
                        f"'{getattr(ch, 'name', channel)}' is not one."
                    )
                kwargs["target_type"] = discord.InviteTarget.embedded_application
                kwargs["target_application_id"] = activity_id

            invite = await ch.create_invite(**kwargs)
            data = _serialize(invite)
            audit_log("invite create", {"channel": channel, "code": data["code"]})
            output(ctx, data, plain_text=_plain(data))
        return _action(client)

    run_rest(ctx, action)


@invite_group.command("info")
@click.argument("code")
@click.pass_context
def invite_info(ctx, code):
    """Show details for an invite code or URL."""

    def action(client):
        async def _action(client):
            invite = await client.fetch_invite(code, with_counts=True, with_expiration=True)
            data = _serialize(invite)
            plain_lines = [f"{k}: {v}" for k, v in data.items() if v is not None]
            output(ctx, data, plain_text="\n".join(plain_lines))
        return _action(client)

    run_rest(ctx, action)


@invite_group.command("delete")
@click.argument("code")
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def invite_delete(ctx, code, reason):
    """Revoke an invite by code or URL."""
    from discli.security import audit_log, confirm_destructive
    confirm_destructive("invite delete", f"invite {code}")

    def action(client):
        async def _action(client):
            await client.delete_invite(code, reason=reason)
            audit_log("invite delete", {"code": code})
            output(ctx, {"code": code, "deleted": True}, plain_text=f"Revoked invite {code}")
        return _action(client)

    run_rest(ctx, action)

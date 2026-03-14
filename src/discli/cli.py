import click

from discli.config import load_config
from discli.commands.channel import channel_group
from discli.commands.config_cmd import config_group
from discli.commands.dm import dm_group
from discli.commands.listen import listen_cmd
from discli.commands.member import member_group
from discli.commands.message import message_group
from discli.commands.reaction import reaction_group
from discli.commands.role import role_group
from discli.commands.server import server_group
from discli.commands.poll import poll_group
from discli.commands.thread import thread_group
from discli.commands.typing_cmd import typing_cmd
from discli.commands.serve import serve_cmd


@click.group()
@click.option("--token", envvar="DISCORD_BOT_TOKEN", default=None, help="Discord bot token.")
@click.option("--json", "use_json", is_flag=True, default=False, help="Output as JSON.")
@click.option("--yes", "-y", is_flag=True, default=False, help="Skip confirmation prompts for destructive actions.")
@click.option("--profile", envvar="DISCLI_PROFILE", default=None,
              type=click.Choice(["full", "chat", "readonly", "moderation"]),
              help="Override permission profile for this invocation.")
@click.pass_context
def main(ctx, token, use_json, yes, profile):
    """discli — Discord CLI for AI agents."""
    ctx.ensure_object(dict)
    if token is None:
        config = load_config()
        token = config.get("token")
    ctx.obj["token"] = token
    ctx.obj["use_json"] = use_json
    ctx.obj["yes"] = yes
    ctx.obj["profile"] = profile


main.add_command(channel_group)
main.add_command(config_group)
main.add_command(dm_group)
main.add_command(listen_cmd)
main.add_command(member_group)
main.add_command(message_group)
main.add_command(reaction_group)
main.add_command(role_group)
main.add_command(server_group)
main.add_command(poll_group)
main.add_command(thread_group)
main.add_command(typing_cmd)
main.add_command(serve_cmd)


# Permission management commands
@click.group("permission")
def permission_group():
    """Manage permission profiles for command access control."""


@permission_group.command("show")
@click.pass_context
def permission_show(ctx):
    """Show the active permission profile."""
    import json as json_mod
    from discli.security import get_active_profile, DEFAULT_PROFILES, PERMISSIONS_PATH

    if PERMISSIONS_PATH.exists():
        try:
            data = json_mod.loads(PERMISSIONS_PATH.read_text())
            active = data.get("active_profile", "full")
        except Exception:
            active = "full"
    else:
        active = "full"

    profile = get_active_profile()
    use_json = ctx.obj.get("use_json", False)
    result = {"active_profile": active, **profile}

    if use_json:
        click.echo(json_mod.dumps(result, indent=2))
    else:
        click.echo(f"Active profile: {active}")
        click.echo(f"Description: {profile.get('description', 'N/A')}")
        click.echo(f"Allowed: {', '.join(profile.get('allowed', []))}")
        click.echo(f"Denied: {', '.join(profile.get('denied', []))}")


@permission_group.command("set")
@click.argument("profile", type=click.Choice(["full", "chat", "readonly", "moderation"]))
def permission_set(profile):
    """Set the active permission profile."""
    from discli.security import set_active_profile, DEFAULT_PROFILES
    set_active_profile(profile)
    desc = DEFAULT_PROFILES.get(profile, {}).get("description", "")
    click.echo(f"Permission profile set to: {profile} ({desc})")


@permission_group.command("profiles")
@click.pass_context
def permission_profiles(ctx):
    """List available permission profiles."""
    import json as json_mod
    from discli.security import DEFAULT_PROFILES

    use_json = ctx.obj.get("use_json", False)
    if use_json:
        click.echo(json_mod.dumps(DEFAULT_PROFILES, indent=2))
    else:
        for name, profile in DEFAULT_PROFILES.items():
            click.echo(f"  {name}: {profile['description']}")


main.add_command(permission_group)


# Audit log commands
@click.group("audit")
def audit_group():
    """View the audit log."""


@audit_group.command("show")
@click.option("--limit", default=20, help="Number of entries to show.")
@click.pass_context
def audit_show(ctx, limit):
    """Show recent audit log entries."""
    import json as json_mod
    from discli.security import AUDIT_LOG_PATH

    if not AUDIT_LOG_PATH.exists():
        click.echo("No audit log entries.")
        return

    lines = AUDIT_LOG_PATH.read_text().strip().split("\n")
    entries = [json_mod.loads(line) for line in lines[-limit:]]

    use_json = ctx.obj.get("use_json", False)
    if use_json:
        click.echo(json_mod.dumps(entries, indent=2))
    else:
        for e in entries:
            ts = e["timestamp"][:19].replace("T", " ")
            user = f" (by {e['user']})" if e.get("user") else ""
            click.echo(f"[{ts}] {e['command']} {e.get('result', '')}{user}")


@audit_group.command("clear")
def audit_clear():
    """Clear the audit log."""
    from discli.security import AUDIT_LOG_PATH
    if AUDIT_LOG_PATH.exists():
        AUDIT_LOG_PATH.unlink()
    click.echo("Audit log cleared.")


main.add_command(audit_group)

import click

from discli.client import run_rest
from discli.utils import fetch_guilds, output, resolve_guild, warn_channel_visibility


@click.group("server")
def server_group():
    """List and inspect servers."""


@server_group.command("list")
@click.pass_context
def server_list(ctx):
    """List servers the bot is in."""

    def action(client):
        async def _action(client):
            servers = []
            for g in await fetch_guilds(client):
                member_count = g.member_count
                if member_count is None:
                    member_count = g.approximate_member_count
                servers.append({
                    "id": str(g.id),
                    "name": g.name,
                    "member_count": member_count,
                })
            plain_lines = [f"{s['name']} (ID: {s['id']}, members: {s['member_count']})" for s in servers]
            output(ctx, servers, plain_text="\n".join(plain_lines) if plain_lines else "Bot is not in any servers.")
        return _action(client)

    run_rest(ctx, action)


@server_group.command("info")
@click.argument("server")
@click.pass_context
def server_info(ctx, server):
    """Show server details."""

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            channels = await guild.fetch_channels()
            roles = await guild.fetch_roles()
            member_count = guild.member_count
            if member_count is None:
                member_count = guild.approximate_member_count
            owner = str(guild.owner_id)
            if guild.owner_id:
                try:
                    owner = str(await guild.fetch_member(guild.owner_id))
                except Exception:
                    pass
            data = {
                "id": str(guild.id),
                "name": guild.name,
                "owner": owner,
                "member_count": member_count,
                "channel_count": len(channels),
                "role_count": len(roles),
                "created_at": guild.created_at.isoformat(),
            }
            plain_lines = [f"{k}: {v}" for k, v in data.items()]
            output(ctx, data, plain_text="\n".join(plain_lines))
            # channel_count only counts what this bot can see.
            warn_channel_visibility()
        return _action(client)

    run_rest(ctx, action)


@server_group.command("audit-log")
@click.argument("server")
@click.option("--limit", default=50, type=int, help="Max entries to return.")
@click.option("--action", "action_name", default=None, help="Filter by audit action (e.g. ban, channel_delete, message_pin).")
@click.option("--user", default=None, help="Filter by the member who performed the action (ID or name).")
@click.option("--changes", "show_changes", is_flag=True, default=False, help="Include before/after values for each change.")
@click.pass_context
def server_audit_log(ctx, server, limit, action_name, user, show_changes):
    """Read the server's Discord audit log.

    Needs the View Audit Log permission. This is Discord's own log of who did
    what in the server -- distinct from 'discli audit', which records what this
    CLI did locally.
    """
    import discord

    audit_action = None
    if action_name:
        normalized = action_name.replace("-", "_").lower()
        audit_action = discord.AuditLogAction.__members__.get(normalized)
        if audit_action is None:
            near = sorted(
                name for name in discord.AuditLogAction.__members__
                if normalized in name or name in normalized
            )
            hint = f" Did you mean: {', '.join(near[:8])}?" if near else ""
            raise click.ClickException(f"Unknown audit action: {action_name}.{hint}")

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)

            kwargs = {"limit": limit}
            if audit_action is not None:
                kwargs["action"] = audit_action
            if user:
                try:
                    kwargs["user"] = discord.Object(id=int(user))
                except ValueError:
                    from discli.utils import resolve_member
                    kwargs["user"] = await resolve_member(guild, user)

            entries = []
            async for entry in guild.audit_logs(**kwargs):
                record = {
                    "id": str(entry.id),
                    "action": entry.action.name,
                    "user": str(entry.user) if entry.user else None,
                    "user_id": str(entry.user_id) if entry.user_id else None,
                    "target": str(entry.target) if entry.target is not None else None,
                    "target_id": str(getattr(entry.target, "id", "")) or None,
                    "reason": entry.reason,
                    "timestamp": entry.created_at.isoformat(),
                }
                changed = [attr for attr, _ in entry.changes.after]
                record["changed"] = changed
                if show_changes:
                    record["changes"] = {
                        attr: {
                            "before": getattr(entry.changes.before, attr, None),
                            "after": value,
                        }
                        for attr, value in entry.changes.after
                    }
                entries.append(record)

            plain_lines = []
            for e in entries:
                line = f"[{e['timestamp'][:19].replace('T', ' ')}] {e['user'] or 'unknown'} -> {e['action']}"
                if e["target"]:
                    line += f" on {e['target']}"
                if e["changed"]:
                    line += f" ({', '.join(e['changed'])})"
                if e["reason"]:
                    line += f" -- {e['reason']}"
                plain_lines.append(line)
            output(ctx, entries, plain_text="\n".join(plain_lines) if plain_lines else "No audit log entries.")
        return _action(client)

    run_rest(ctx, action)


@server_group.command("edit")
@click.argument("server")
@click.option("--name", default=None, help="New server name.")
@click.option("--description", default=None, help="New server description (Community servers).")
@click.option("--icon", default=None, type=click.Path(exists=True), help="Path to a new server icon image.")
@click.option("--banner", default=None, type=click.Path(exists=True), help="Path to a new server banner image.")
@click.option(
    "--verification-level",
    default=None,
    type=click.Choice(["none", "low", "medium", "high", "highest"]),
    help="Member verification level.",
)
@click.option("--system-channel", default=None, help="Channel for Discord's system messages (name or ID).")
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def server_edit(ctx, server, name, description, icon, banner, verification_level, system_channel, reason):
    """Edit server settings (name, description, icon, banner, verification, system channel)."""
    import discord
    from discli.security import audit_log

    if not any([name, description, icon, banner, verification_level, system_channel]):
        raise click.ClickException("Nothing to change. Pass at least one option; see --help.")

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)

            kwargs = {}
            if name:
                kwargs["name"] = name
            if description is not None:
                kwargs["description"] = description
            if icon:
                with open(icon, "rb") as fh:
                    kwargs["icon"] = fh.read()
            if banner:
                with open(banner, "rb") as fh:
                    kwargs["banner"] = fh.read()
            if verification_level:
                kwargs["verification_level"] = discord.VerificationLevel[verification_level]
            if system_channel:
                channels = await guild.fetch_channels()
                normalized = system_channel.removeprefix("#").casefold()
                matches = [
                    ch for ch in channels
                    if str(ch.id) == system_channel or ch.name.casefold() == normalized
                ]
                if not matches:
                    raise click.ClickException(f"Channel not found in {guild.name}: {system_channel}")
                if len(matches) > 1:
                    raise click.ClickException(
                        f"Multiple channels match '{system_channel}'. Use a channel ID."
                    )
                kwargs["system_channel"] = matches[0]
            if reason:
                kwargs["reason"] = reason

            updated = await guild.edit(**kwargs)
            # Guild.edit returns the updated guild on success, but older paths
            # can return None; fall back to the resolved guild for reporting.
            updated = updated or guild
            changed = sorted(k for k in kwargs if k != "reason")
            audit_log("server edit", {"server": server, "changed": changed})
            data = {"id": str(updated.id), "name": updated.name, "changed": changed}
            output(ctx, data, plain_text=f"Updated {updated.name}: {', '.join(changed)}")
        return _action(client)

    run_rest(ctx, action)


@server_group.group("onboarding")
def onboarding_group():
    """Inspect and adjust the server's onboarding flow."""


@onboarding_group.command("show")
@click.argument("server")
@click.pass_context
def onboarding_show(ctx, server):
    """Show the server's onboarding configuration."""

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            onboarding = await guild.onboarding()

            data = {
                "enabled": onboarding.enabled,
                "mode": onboarding.mode.name,
                "default_channel_ids": sorted(str(c) for c in onboarding.default_channel_ids),
                "prompts": [
                    {
                        "id": str(prompt.id),
                        "title": prompt.title,
                        "type": prompt.type.name,
                        "single_select": prompt.single_select,
                        "required": prompt.required,
                        "in_onboarding": prompt.in_onboarding,
                        "options": [
                            {
                                "id": str(option.id),
                                "title": option.title,
                                "description": option.description,
                                "role_ids": [str(r) for r in option.role_ids],
                                "channel_ids": [str(c) for c in option.channel_ids],
                            }
                            for option in prompt.options
                        ],
                    }
                    for prompt in onboarding.prompts
                ],
            }

            lines = [
                f"enabled: {data['enabled']}",
                f"mode: {data['mode']}",
                f"default channels: {', '.join(data['default_channel_ids']) or 'none'}",
            ]
            for prompt in data["prompts"]:
                flags = []
                if prompt["required"]:
                    flags.append("required")
                if prompt["single_select"]:
                    flags.append("single-select")
                suffix = f" [{', '.join(flags)}]" if flags else ""
                lines.append(f"prompt: {prompt['title']}{suffix} (ID: {prompt['id']})")
                for option in prompt["options"]:
                    lines.append(f"    - {option['title']}")
            output(ctx, data, plain_text="\n".join(lines))
        return _action(client)

    run_rest(ctx, action)


@onboarding_group.command("edit")
@click.argument("server")
@click.option("--enable/--disable", "enabled", default=None, help="Turn onboarding on or off.")
@click.option(
    "--mode",
    type=click.Choice(["default", "advanced"]),
    default=None,
    help="'default' counts only default channels toward Discord's requirements; 'advanced' counts prompts too.",
)
@click.option("--default-channel", "default_channels", multiple=True, help="Replace the default channel list (name or ID, repeatable).")
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def onboarding_edit(ctx, server, enabled, mode, default_channels, reason):
    """Edit onboarding settings.

    Covers the settings that are safe to change one at a time. Editing the
    prompts themselves is not supported here: Discord replaces the entire
    prompt list on write, so a partial spec would silently delete the prompts
    it omits. Use 'server onboarding show' to read them and Discord's UI to
    change them.
    """
    import discord

    from discli.security import audit_log

    if enabled is None and mode is None and not default_channels:
        raise click.ClickException("Nothing to change. Pass at least one option; see --help.")

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)

            kwargs = {"reason": reason}
            if enabled is not None:
                kwargs["enabled"] = enabled
            if mode is not None:
                kwargs["mode"] = discord.OnboardingMode[mode]
            if default_channels:
                channels = await guild.fetch_channels()
                resolved = []
                for value in default_channels:
                    normalized = value.removeprefix("#").casefold()
                    matches = [
                        ch for ch in channels
                        if str(ch.id) == value or ch.name.casefold() == normalized
                    ]
                    if not matches:
                        raise click.ClickException(f"Channel not found in {guild.name}: {value}")
                    if len(matches) > 1:
                        ids = ", ".join(str(ch.id) for ch in matches)
                        raise click.ClickException(
                            f"Multiple channels match '{value}' (IDs: {ids}). Use a channel ID."
                        )
                    resolved.append(matches[0])
                kwargs["default_channels"] = resolved

            await guild.edit_onboarding(**kwargs)
            changed = sorted(k for k in kwargs if k != "reason")
            audit_log("server onboarding edit", {"server": server, "changed": changed})
            output(ctx, {"server": guild.name, "changed": changed},
                   plain_text=f"Updated onboarding for {guild.name}: {', '.join(changed)}")
        return _action(client)

    run_rest(ctx, action)


# Imported last, and for its side effect: server_spec decorates server_group
# with export/diff/apply, so the group must already exist above.
from discli.commands import server_spec  # noqa: E402,F401

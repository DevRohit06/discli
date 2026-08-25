"""`discli server export` / `diff` / `apply` — a server's structure as a file.

Covers roles, categories, channels, their role permission overwrites, and a
few top-level guild settings. Deliberately *not* covered: members, messages,
emoji, webhooks, invites, and AutoMod rules, each of which has its own command
group and none of which is "structure" in the sense a template means.

Two properties worth knowing before using this:

* **Things are matched by name, not ID.** That is what makes a spec portable
  between servers, which is the point of a template -- but it also means
  renaming something in Discord reads as "delete the old, create the new".
* **`apply` is additive by default.** It creates and updates what the spec
  describes and leaves anything else alone. Deleting server-side extras needs
  ``--prune``, which confirms before it runs.

Positions are exported for reference but never applied. Discord renumbers
siblings on every positional write, so applying them naively produces churn
and ordering that depends on apply order; reordering deserves its own design
rather than a side effect of this one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import click
import discord

from discli.client import run_rest
from discli.commands.server import server_group
from discli.utils import output, resolve_guild

SPEC_VERSION = 1

# Channel kinds apply knows how to create. Anything else round-trips through
# export and diff but is refused by apply rather than guessed at.
CREATABLE_TYPES = {"text", "voice", "category", "forum"}

ROLE_FIELDS = ("color", "hoist", "mentionable", "permissions")
CHANNEL_FIELDS = ("type", "category", "topic", "slowmode", "nsfw", "overwrites")

GUILD_FIELDS = ("name", "description", "verification_level")


# ── spec files ─────────────────────────────────────────────────────


def load_spec(path: str) -> dict:
    """Read a spec file. JSON always; YAML when PyYAML happens to be present."""
    text = Path(path).read_text(encoding="utf-8")
    if path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError:
            raise click.ClickException(
                f"{path} looks like YAML but PyYAML is not installed. "
                "Install it (pip install pyyaml) or use a .json spec."
            )
        data = yaml.safe_load(text)
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"{path} is not valid JSON: {exc}")

    if not isinstance(data, dict):
        raise click.ClickException(f"{path} must contain an object at the top level.")
    version = data.get("version")
    if version is not None and version != SPEC_VERSION:
        raise click.ClickException(
            f"{path} declares spec version {version}; this discli understands {SPEC_VERSION}."
        )
    return data


def dump_spec(data: dict, path: str | None) -> str:
    if path and path.lower().endswith((".yaml", ".yml")):
        try:
            import yaml
        except ImportError:
            raise click.ClickException(
                "Writing YAML needs PyYAML (pip install pyyaml). Use a .json path instead."
            )
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


# ── serialising a live guild ───────────────────────────────────────


def _permission_names(permissions: discord.Permissions) -> list[str]:
    return sorted(name for name, value in permissions if value)


def _overwrites_spec(channel) -> list[dict]:
    """Role permission overwrites, as allow/deny name lists.

    Member overwrites are skipped: they name a specific person by ID and so
    cannot survive being applied to a different server, which is the whole
    point of a portable spec.
    """
    entries = []
    for target, overwrite in channel.overwrites.items():
        if not isinstance(target, discord.Role):
            continue
        allow, deny = overwrite.pair()
        entries.append({
            "role": target.name,
            "allow": _permission_names(allow),
            "deny": _permission_names(deny),
        })
    return sorted(entries, key=lambda e: e["role"])


def _role_spec(role: discord.Role) -> dict:
    return {
        "name": role.name,
        "color": f"{role.color.value:06x}",
        "hoist": role.hoist,
        "mentionable": role.mentionable,
        "permissions": _permission_names(role.permissions),
        "position": role.position,
    }


def _channel_spec(channel, categories_by_id: dict) -> dict:
    # Resolved from the channel list we already fetched, not `channel.category`.
    # That property goes through guild.get_channel(), and fetch_channels() never
    # populates the guild's channel cache -- so on a REST-only client it is
    # always None and every channel exports as top-level, silently flattening
    # the server. Caught by running this against a real guild.
    parent = categories_by_id.get(getattr(channel, "category_id", None))
    return {
        "name": channel.name,
        "type": channel.type.name,
        "category": parent.name if parent is not None else None,
        "topic": getattr(channel, "topic", None),
        "slowmode": getattr(channel, "slowmode_delay", 0) or 0,
        "nsfw": bool(getattr(channel, "nsfw", False)),
        "position": channel.position,
        "overwrites": _overwrites_spec(channel),
    }


async def build_spec(guild) -> dict:
    channels = await guild.fetch_channels()
    roles = await guild.fetch_roles()
    categories_by_id = {
        c.id: c for c in channels if isinstance(c, discord.CategoryChannel)
    }

    return {
        "version": SPEC_VERSION,
        "server": {
            "name": guild.name,
            "description": guild.description,
            "verification_level": guild.verification_level.name,
        },
        # @everyone is created by Discord and cannot be made or removed;
        # managed roles belong to bots and integrations and reject edits.
        "roles": [
            _role_spec(r) for r in sorted(roles, key=lambda r: r.position, reverse=True)
            if r.name != "@everyone" and not r.managed
        ],
        "categories": [
            {"name": c.name, "position": c.position}
            for c in sorted(channels, key=lambda c: c.position)
            if isinstance(c, discord.CategoryChannel)
        ],
        "channels": [
            _channel_spec(c, categories_by_id)
            for c in sorted(channels, key=lambda c: c.position)
            if not isinstance(c, discord.CategoryChannel)
        ],
    }


# ── diffing ────────────────────────────────────────────────────────


@dataclass
class Change:
    op: str          # create | update | extra | unchanged
    kind: str        # server | role | category | channel
    name: str
    fields: dict = field(default_factory=dict)  # field -> (current, desired)

    def render(self, prune: bool = False) -> str:
        marker = {
            "create": "  +",
            "update": "  ~",
            "unchanged": "   ",
            "extra": "  -" if prune else "  !",
        }[self.op]
        label = f"{self.kind:<9} {self.name}"
        if self.op == "create":
            detail = "create"
        elif self.op == "unchanged":
            detail = "unchanged"
        elif self.op == "extra":
            detail = "DELETE" if prune else "not in spec (kept)"
        else:
            detail = "; ".join(
                f"{name}: {_short(current)} -> {_short(desired)}"
                for name, (current, desired) in sorted(self.fields.items())
            )
        return f"{marker} {label:<28} {detail}"


def _short(value) -> str:
    if isinstance(value, list):
        return f"[{len(value)} item(s)]"
    text = "none" if value is None else str(value)
    return text if len(text) <= 30 else text[:27] + "..."


def _compare(kind, name, current: dict, desired: dict, fields) -> Change:
    """Compare only the fields the spec actually declares.

    A spec that omits `topic` means "I do not manage the topic", not "set the
    topic to null" -- otherwise every hand-trimmed spec would blank out
    everything it left out.
    """
    differences = {}
    for key in fields:
        if key not in desired:
            continue
        want = desired[key]
        have = current.get(key)
        if key == "permissions" or key == "overwrites":
            if _normalise(have) != _normalise(want):
                differences[key] = (have, want)
        elif have != want:
            differences[key] = (have, want)
    if differences:
        return Change("update", kind, name, differences)
    return Change("unchanged", kind, name)


def _normalise(value):
    if isinstance(value, list):
        return sorted(
            (json.dumps(v, sort_keys=True) if isinstance(v, dict) else str(v))
            for v in value
        )
    return value


def diff_spec(spec: dict, live: dict) -> list[Change]:
    changes: list[Change] = []

    wanted_server = spec.get("server") or {}
    if wanted_server:
        changes.append(
            _compare("server", live["server"]["name"], live["server"], wanted_server, GUILD_FIELDS)
        )

    for kind, key, fields in (
        ("role", "roles", ROLE_FIELDS),
        ("category", "categories", ()),
        ("channel", "channels", CHANNEL_FIELDS),
    ):
        wanted = {item["name"]: item for item in spec.get(key) or []}
        have = {item["name"]: item for item in live.get(key) or []}
        for name, desired in wanted.items():
            if name not in have:
                changes.append(Change("create", kind, name))
            else:
                changes.append(_compare(kind, name, have[name], desired, fields))
        for name in have:
            if name not in wanted:
                changes.append(Change("extra", kind, name))

    return changes


def render_changes(changes: list[Change], *, prune: bool, show_unchanged: bool) -> str:
    visible = [c for c in changes if show_unchanged or c.op != "unchanged"]
    if not visible:
        return "No differences."
    return "\n".join(c.render(prune=prune) for c in visible)


def summarise(changes: list[Change]) -> dict:
    counts = {"create": 0, "update": 0, "extra": 0, "unchanged": 0}
    for change in changes:
        counts[change.op] += 1
    return counts


# ── commands ───────────────────────────────────────────────────────


@server_group.command("export")
@click.argument("server")
@click.option("--out", default=None, type=click.Path(), help="Write to this file instead of stdout.")
@click.pass_context
def server_export(ctx, server, out):
    """Export a server's roles, categories, and channels to a spec file."""

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            spec = await build_spec(guild)
            text = dump_spec(spec, out)
            if out:
                Path(out).write_text(text, encoding="utf-8")
                counts = (
                    f"{len(spec['roles'])} role(s), {len(spec['categories'])} categor(ies), "
                    f"{len(spec['channels'])} channel(s)"
                )
                output(ctx, spec, plain_text=f"Wrote {out} — {counts}")
            else:
                # The spec itself is the payload in both modes; --json only
                # changes indentation, not shape.
                click.echo(text, nl=False)
        return _action(client)

    run_rest(ctx, action)


@server_group.command("diff")
@click.argument("server")
@click.argument("spec_file", type=click.Path(exists=True))
@click.option("--prune", is_flag=True, default=False, help="Show server-side extras as deletions.")
@click.option("--show-unchanged", is_flag=True, default=False, help="Also list items that match.")
@click.pass_context
def server_diff(ctx, server, spec_file, prune, show_unchanged):
    """Compare a spec file against a live server. Read-only."""

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            spec = load_spec(spec_file)
            live = await build_spec(guild)
            changes = diff_spec(spec, live)
            counts = summarise(changes)

            data = {
                "server": guild.name,
                "counts": counts,
                "changes": [
                    {"op": c.op, "kind": c.kind, "name": c.name, "fields": sorted(c.fields)}
                    for c in changes if show_unchanged or c.op != "unchanged"
                ],
            }
            body = render_changes(changes, prune=prune, show_unchanged=show_unchanged)
            tail = (
                f"\n\n{counts['create']} to create, {counts['update']} to update, "
                f"{counts['extra']} not in spec"
            )
            output(ctx, data, plain_text=body + (tail if changes else ""))
        return _action(client)

    run_rest(ctx, action)


@server_group.command("apply")
@click.argument("server")
@click.argument("spec_file", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, default=False, help="Show what would change without writing.")
@click.option("--prune", is_flag=True, default=False, help="Also delete anything in the server that the spec omits.")
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def server_apply(ctx, server, spec_file, dry_run, prune, reason):
    """Apply a spec file to a server.

    Additive by default: creates and updates what the spec describes and
    leaves anything else untouched. --prune additionally deletes roles,
    categories, and channels the spec does not mention, and confirms first.
    """
    from discli.security import audit_log, confirm_destructive

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            spec = load_spec(spec_file)
            live = await build_spec(guild)
            changes = diff_spec(spec, live)
            counts = summarise(changes)

            actionable = [c for c in changes if c.op in ("create", "update")]
            extras = [c for c in changes if c.op == "extra"]

            if dry_run:
                body = render_changes(changes, prune=prune, show_unchanged=False)
                output(ctx, {
                    "server": guild.name,
                    "dry_run": True,
                    "counts": counts,
                    "changes": [{"op": c.op, "kind": c.kind, "name": c.name} for c in changes],
                }, plain_text=body + "\n\n(dry run — nothing was written)")
                return

            if prune and extras:
                listing = ", ".join(f"{c.kind} {c.name}" for c in extras[:8])
                if len(extras) > 8:
                    listing += f", and {len(extras) - 8} more"
                confirm_destructive("server apply --prune", f"delete {len(extras)}: {listing}")

            applied: list[str] = []
            roles_by_name = {r.name: r for r in await guild.fetch_roles()}
            channels = await guild.fetch_channels()
            categories_by_name = {
                c.name: c for c in channels if isinstance(c, discord.CategoryChannel)
            }
            channels_by_name = {
                c.name: c for c in channels if not isinstance(c, discord.CategoryChannel)
            }

            spec_by = {
                "role": {i["name"]: i for i in spec.get("roles") or []},
                "category": {i["name"]: i for i in spec.get("categories") or []},
                "channel": {i["name"]: i for i in spec.get("channels") or []},
            }

            # Roles first: channel overwrites reference them by name.
            for change in [c for c in actionable if c.kind == "role"]:
                desired = spec_by["role"][change.name]
                kwargs = _role_kwargs(desired)
                if change.op == "create":
                    role = await guild.create_role(name=change.name, reason=reason, **kwargs)
                    roles_by_name[role.name] = role
                else:
                    await roles_by_name[change.name].edit(reason=reason, **kwargs)
                applied.append(f"role {change.name}")

            # Categories before channels, which reference them as parents.
            for change in [c for c in actionable if c.kind == "category"]:
                if change.op == "create":
                    category = await guild.create_category(change.name, reason=reason)
                    categories_by_name[category.name] = category
                    applied.append(f"category {change.name}")

            for change in [c for c in actionable if c.kind == "channel"]:
                desired = spec_by["channel"][change.name]
                ch_type = desired.get("type", "text")
                if change.op == "create" and ch_type not in CREATABLE_TYPES:
                    raise click.ClickException(
                        f"Cannot create channel '{change.name}': discli does not create "
                        f"'{ch_type}' channels. Supported: {', '.join(sorted(CREATABLE_TYPES))}."
                    )
                parent = categories_by_name.get(desired.get("category")) if desired.get("category") else None

                if change.op == "create":
                    kwargs = {"reason": reason}
                    if parent is not None:
                        kwargs["category"] = parent
                    if desired.get("topic") is not None:
                        kwargs["topic"] = desired["topic"]
                    if desired.get("nsfw") is not None:
                        kwargs["nsfw"] = desired["nsfw"]
                    if ch_type == "voice":
                        channel = await guild.create_voice_channel(change.name, **kwargs)
                    elif ch_type == "forum":
                        channel = await guild.create_forum(change.name, **kwargs)
                    else:
                        if desired.get("slowmode"):
                            kwargs["slowmode_delay"] = desired["slowmode"]
                        channel = await guild.create_text_channel(change.name, **kwargs)
                    channels_by_name[channel.name] = channel
                else:
                    channel = channels_by_name[change.name]
                    edits = {}
                    if "topic" in desired and hasattr(channel, "topic"):
                        edits["topic"] = desired["topic"]
                    if "nsfw" in desired and hasattr(channel, "nsfw"):
                        edits["nsfw"] = desired["nsfw"]
                    if "slowmode" in desired and hasattr(channel, "slowmode_delay"):
                        edits["slowmode_delay"] = desired["slowmode"]
                    if "category" in desired:
                        edits["category"] = parent
                    if edits:
                        await channel.edit(reason=reason, **edits)

                if desired.get("overwrites"):
                    await _apply_overwrites(channel, desired["overwrites"], roles_by_name, reason)
                applied.append(f"channel {change.name}")

            pruned: list[str] = []
            if prune:
                for change in extras:
                    if change.kind == "role":
                        role = roles_by_name.get(change.name)
                        if role is not None:
                            await role.delete(reason=reason)
                    elif change.kind == "category":
                        category = categories_by_name.get(change.name)
                        if category is not None:
                            await category.delete(reason=reason)
                    elif change.kind == "channel":
                        channel = channels_by_name.get(change.name)
                        if channel is not None:
                            await channel.delete(reason=reason)
                    pruned.append(f"{change.kind} {change.name}")

            audit_log("server apply", {
                "server": server,
                "spec": spec_file,
                "applied": len(applied),
                "pruned": len(pruned),
            })
            data = {
                "server": guild.name,
                "applied": applied,
                "pruned": pruned,
                "left_alone": [f"{c.kind} {c.name}" for c in extras] if not prune else [],
            }
            lines = [f"Applied {len(applied)} change(s) to {guild.name}."]
            if pruned:
                lines.append(f"Deleted {len(pruned)}: {', '.join(pruned)}")
            elif extras:
                lines.append(f"{len(extras)} item(s) not in the spec were left alone (use --prune to delete).")
            output(ctx, data, plain_text="\n".join(lines))
        return _action(client)

    run_rest(ctx, action)


def _role_kwargs(desired: dict) -> dict:
    kwargs = {}
    if "color" in desired and desired["color"] is not None:
        try:
            kwargs["color"] = discord.Color(int(str(desired["color"]).lstrip("#"), 16))
        except ValueError:
            raise click.ClickException(
                f"Invalid color for role '{desired.get('name')}': {desired['color']} (use hex like ff0000)"
            )
    if "hoist" in desired:
        kwargs["hoist"] = bool(desired["hoist"])
    if "mentionable" in desired:
        kwargs["mentionable"] = bool(desired["mentionable"])
    if "permissions" in desired:
        kwargs["permissions"] = _permissions_from(desired["permissions"], desired.get("name"))
    return kwargs


def _permissions_from(value, owner: str | None) -> discord.Permissions:
    """Accept either a list of permission names or a raw bitfield."""
    if isinstance(value, (int, str)) and not isinstance(value, list):
        try:
            return discord.Permissions(int(value))
        except ValueError:
            raise click.ClickException(f"Invalid permission bitfield for '{owner}': {value!r}")
    unknown = [name for name in value if not hasattr(discord.Permissions, name)]
    if unknown:
        raise click.ClickException(
            f"Unknown permission(s) for '{owner}': {', '.join(unknown)}"
        )
    return discord.Permissions(**{name: True for name in value})


async def _apply_overwrites(channel, overwrites: list[dict], roles_by_name: dict, reason: str | None):
    for entry in overwrites:
        role = roles_by_name.get(entry.get("role"))
        if role is None:
            raise click.ClickException(
                f"Channel '{channel.name}' has an overwrite for role '{entry.get('role')}', "
                "which does not exist in the server or the spec."
            )
        overwrite = discord.PermissionOverwrite()
        for name in entry.get("allow") or []:
            if not hasattr(discord.Permissions, name):
                raise click.ClickException(f"Unknown permission in overwrite: {name}")
            setattr(overwrite, name, True)
        for name in entry.get("deny") or []:
            if not hasattr(discord.Permissions, name):
                raise click.ClickException(f"Unknown permission in overwrite: {name}")
            setattr(overwrite, name, False)
        await channel.set_permissions(role, overwrite=overwrite, reason=reason)

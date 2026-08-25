"""`discli automod` — manage Discord AutoMod rules.

Discord models a rule as one *trigger* (what to look for) plus one or more
*actions* (what to do about it). This module keeps that shape: --trigger picks
the detector, its companion options configure it, and --action is repeatable.
"""

import datetime

import click
import discord

from discli.client import run_rest
from discli.utils import output, resolve_guild

TRIGGERS = ["keyword", "spam", "keyword-preset", "mention-spam", "member-profile"]
PRESETS = ["profanity", "sexual-content", "slurs"]
ACTIONS = ["block", "alert", "timeout"]

# Discord caps a timeout action at 28 days, the same ceiling as member timeout.
MAX_TIMEOUT_SECONDS = 2419200


@click.group("automod")
def automod_group():
    """Manage AutoMod rules."""


def _serialize(rule) -> dict:
    trigger = rule.trigger
    return {
        "id": str(rule.id),
        "name": rule.name,
        "enabled": rule.enabled,
        "trigger": trigger.type.name if trigger and trigger.type else None,
        "keywords": list(getattr(trigger, "keyword_filter", None) or []),
        "regex_patterns": list(getattr(trigger, "regex_patterns", None) or []),
        "allow_list": list(getattr(trigger, "allow_list", None) or []),
        "mention_limit": getattr(trigger, "mention_limit", None),
        "presets": [
            name for name in ("profanity", "sexual_content", "slurs")
            if getattr(getattr(trigger, "presets", None), name, False)
        ],
        "actions": [
            {
                "type": action.type.name,
                "channel_id": str(action.channel_id) if action.channel_id else None,
                "duration_seconds": int(action.duration.total_seconds()) if action.duration else None,
                "custom_message": action.custom_message,
            }
            for action in rule.actions
        ],
        "exempt_role_ids": [str(r.id) for r in rule.exempt_roles],
        "exempt_channel_ids": [str(c.id) for c in rule.exempt_channels],
        "creator_id": str(rule.creator_id) if rule.creator_id else None,
    }


def _plain(data: dict) -> str:
    state = "enabled" if data["enabled"] else "disabled"
    bits = [f"{data['name']} [{state}] (ID: {data['id']})", f"  trigger: {data['trigger']}"]
    if data["keywords"]:
        bits.append(f"  keywords: {', '.join(data['keywords'])}")
    if data["regex_patterns"]:
        bits.append(f"  regex: {', '.join(data['regex_patterns'])}")
    if data["presets"]:
        bits.append(f"  presets: {', '.join(data['presets'])}")
    if data["mention_limit"] is not None:
        bits.append(f"  mention limit: {data['mention_limit']}")
    if data["allow_list"]:
        bits.append(f"  allowed: {', '.join(data['allow_list'])}")
    for action in data["actions"]:
        detail = action["type"]
        if action["duration_seconds"]:
            detail += f" {action['duration_seconds']}s"
        if action["channel_id"]:
            detail += f" -> channel {action['channel_id']}"
        bits.append(f"  action: {detail}")
    return "\n".join(bits)


async def _resolve_rule(guild, identifier: str):
    rules = await guild.fetch_automod_rules()
    matches = [r for r in rules if str(r.id) == identifier]
    if not matches:
        matches = [r for r in rules if r.name.casefold() == identifier.casefold()]
    if not matches:
        raise click.ClickException(f"AutoMod rule not found in {guild.name}: {identifier}")
    if len(matches) > 1:
        ids = ", ".join(str(r.id) for r in matches)
        raise click.ClickException(f"Multiple rules match '{identifier}' (IDs: {ids}). Use an ID.")
    return matches[0]


def _build_trigger(trigger_name, keywords, regexes, presets, allow, mention_limit):
    """Map CLI options onto an AutoModTrigger, rejecting mismatched combinations.

    discord.py infers the trigger type from whichever argument is set, which
    silently ignores options that do not belong to the chosen trigger. Being
    explicit here means `--trigger spam --keyword foo` is an error rather than
    a rule that quietly does something else.
    """
    if trigger_name == "keyword":
        if not keywords and not regexes:
            raise click.ClickException("--trigger keyword needs at least one --keyword or --regex.")
        return discord.AutoModTrigger(
            type=discord.AutoModRuleTriggerType.keyword,
            keyword_filter=list(keywords) or None,
            regex_patterns=list(regexes) or None,
            allow_list=list(allow) or None,
        )
    if trigger_name == "keyword-preset":
        if not presets:
            raise click.ClickException(
                f"--trigger keyword-preset needs at least one --preset ({', '.join(PRESETS)})."
            )
        flags = discord.AutoModPresets()
        for preset in presets:
            setattr(flags, preset.replace("-", "_"), True)
        return discord.AutoModTrigger(
            type=discord.AutoModRuleTriggerType.keyword_preset,
            presets=flags,
            allow_list=list(allow) or None,
        )
    if trigger_name == "mention-spam":
        if mention_limit is None:
            raise click.ClickException("--trigger mention-spam needs --mention-limit.")
        return discord.AutoModTrigger(
            type=discord.AutoModRuleTriggerType.mention_spam,
            mention_limit=mention_limit,
        )
    if trigger_name == "spam":
        return discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.spam)
    if trigger_name == "member-profile":
        if not keywords and not regexes:
            raise click.ClickException("--trigger member-profile needs at least one --keyword or --regex.")
        return discord.AutoModTrigger(
            type=discord.AutoModRuleTriggerType.member_profile,
            keyword_filter=list(keywords) or None,
            regex_patterns=list(regexes) or None,
            allow_list=list(allow) or None,
        )
    raise click.ClickException(f"Unknown trigger: {trigger_name}")


async def _build_actions(guild, actions, alert_channel, timeout_seconds, custom_message):
    built = []
    for name in actions:
        if name == "block":
            built.append(discord.AutoModRuleAction(
                type=discord.AutoModRuleActionType.block_message,
                custom_message=custom_message,
            ))
        elif name == "alert":
            if not alert_channel:
                raise click.ClickException("--action alert needs --alert-channel.")
            channels = await guild.fetch_channels()
            normalized = alert_channel.removeprefix("#").casefold()
            matches = [
                ch for ch in channels
                if str(ch.id) == alert_channel or ch.name.casefold() == normalized
            ]
            if not matches:
                raise click.ClickException(f"Channel not found in {guild.name}: {alert_channel}")
            if len(matches) > 1:
                ids = ", ".join(str(ch.id) for ch in matches)
                raise click.ClickException(
                    f"Multiple channels match '{alert_channel}' (IDs: {ids}). Use a channel ID."
                )
            built.append(discord.AutoModRuleAction(
                type=discord.AutoModRuleActionType.send_alert_message,
                channel_id=matches[0].id,
            ))
        elif name == "timeout":
            if timeout_seconds is None:
                raise click.ClickException("--action timeout needs --timeout.")
            built.append(discord.AutoModRuleAction(
                type=discord.AutoModRuleActionType.timeout,
                duration=datetime.timedelta(seconds=timeout_seconds),
            ))
    return built


@automod_group.command("list")
@click.argument("server")
@click.pass_context
def automod_list(ctx, server):
    """List AutoMod rules in a server."""

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            rules = [_serialize(r) for r in await guild.fetch_automod_rules()]
            plain = "\n\n".join(_plain(r) for r in rules) if rules else "No AutoMod rules."
            output(ctx, rules, plain_text=plain)
        return _action(client)

    run_rest(ctx, action)


@automod_group.command("create")
@click.argument("server")
@click.argument("name")
@click.option("--trigger", "trigger_name", type=click.Choice(TRIGGERS), required=True, help="What the rule detects.")
@click.option("--keyword", "keywords", multiple=True, help="Keyword to match (repeatable).")
@click.option("--regex", "regexes", multiple=True, help="Regex pattern to match (repeatable).")
@click.option("--preset", "presets", multiple=True, type=click.Choice(PRESETS), help="Built-in word list (repeatable).")
@click.option("--allow", multiple=True, help="Term exempt from this rule (repeatable).")
@click.option("--mention-limit", type=int, default=None, help="Max mentions per message, for --trigger mention-spam.")
@click.option("--action", "actions", multiple=True, type=click.Choice(ACTIONS), required=True, help="What to do on a match (repeatable).")
@click.option("--alert-channel", default=None, help="Channel for --action alert.")
@click.option("--timeout", "timeout_seconds", type=int, default=None, help="Timeout length in seconds, for --action timeout.")
@click.option("--custom-message", default=None, help="Message shown to the blocked member, for --action block.")
@click.option("--exempt-role", "exempt_roles", multiple=True, help="Role exempt from this rule (repeatable).")
@click.option("--exempt-channel", "exempt_channels", multiple=True, help="Channel exempt from this rule (repeatable).")
@click.option("--enable/--no-enable", default=True, help="Whether the rule is active on creation.")
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def automod_create(
    ctx, server, name, trigger_name, keywords, regexes, presets, allow, mention_limit,
    actions, alert_channel, timeout_seconds, custom_message, exempt_roles, exempt_channels,
    enable, reason,
):
    """Create an AutoMod rule."""
    from discli.security import audit_log
    from discli.utils import resolve_role

    if timeout_seconds is not None and not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise click.ClickException(
            f"--timeout must be between 1 and {MAX_TIMEOUT_SECONDS} seconds (28 days)."
        )

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            trigger = _build_trigger(trigger_name, keywords, regexes, presets, allow, mention_limit)
            built_actions = await _build_actions(
                guild, actions, alert_channel, timeout_seconds, custom_message
            )

            kwargs = {
                "name": name,
                "event_type": discord.AutoModRuleEventType.message_send,
                "trigger": trigger,
                "actions": built_actions,
                "enabled": enable,
                "reason": reason,
            }
            if exempt_roles:
                kwargs["exempt_roles"] = [await resolve_role(guild, r) for r in exempt_roles]
            if exempt_channels:
                channels = await guild.fetch_channels()
                resolved = []
                for value in exempt_channels:
                    normalized = value.removeprefix("#").casefold()
                    match = next(
                        (ch for ch in channels if str(ch.id) == value or ch.name.casefold() == normalized),
                        None,
                    )
                    if match is None:
                        raise click.ClickException(f"Channel not found in {guild.name}: {value}")
                    resolved.append(match)
                kwargs["exempt_channels"] = resolved

            rule = await guild.create_automod_rule(**kwargs)
            data = _serialize(rule)
            audit_log("automod create", {"server": server, "name": name, "id": data["id"]})
            output(ctx, data, plain_text=f"Created AutoMod rule:\n{_plain(data)}")
        return _action(client)

    run_rest(ctx, action)


@automod_group.command("edit")
@click.argument("server")
@click.argument("rule")
@click.option("--name", default=None, help="New rule name.")
@click.option("--keyword", "keywords", multiple=True, help="Replace the keyword list (repeatable).")
@click.option("--regex", "regexes", multiple=True, help="Replace the regex list (repeatable).")
@click.option("--allow", multiple=True, help="Replace the allow list (repeatable).")
@click.option("--mention-limit", type=int, default=None, help="New mention limit.")
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def automod_edit(ctx, server, rule, name, keywords, regexes, allow, mention_limit, reason):
    """Edit an AutoMod rule.

    Keyword, regex, and allow lists are replaced wholesale, not appended to --
    pass the full list you want the rule to end up with.
    """
    from discli.security import audit_log

    if not any([name, keywords, regexes, allow, mention_limit is not None]):
        raise click.ClickException("Nothing to change. Pass at least one option; see --help.")

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            target = await _resolve_rule(guild, rule)

            kwargs = {"reason": reason}
            if name:
                kwargs["name"] = name
            if keywords or regexes or allow or mention_limit is not None:
                current = target.trigger
                kwargs["trigger"] = discord.AutoModTrigger(
                    type=current.type,
                    keyword_filter=list(keywords) if keywords else getattr(current, "keyword_filter", None),
                    regex_patterns=list(regexes) if regexes else getattr(current, "regex_patterns", None),
                    allow_list=list(allow) if allow else getattr(current, "allow_list", None),
                    presets=getattr(current, "presets", None),
                    mention_limit=mention_limit if mention_limit is not None else getattr(current, "mention_limit", None),
                )

            updated = await target.edit(**kwargs)
            data = _serialize(updated or target)
            audit_log("automod edit", {"server": server, "rule": rule})
            output(ctx, data, plain_text=f"Updated AutoMod rule:\n{_plain(data)}")
        return _action(client)

    run_rest(ctx, action)


def _set_enabled(ctx, server, rule, enabled, reason):
    from discli.security import audit_log

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            target = await _resolve_rule(guild, rule)
            updated = await target.edit(enabled=enabled, reason=reason)
            data = _serialize(updated or target)
            data["enabled"] = enabled
            verb = "Enabled" if enabled else "Disabled"
            audit_log(f"automod {'enable' if enabled else 'disable'}", {"server": server, "rule": rule})
            output(ctx, data, plain_text=f"{verb} AutoMod rule '{data['name']}'")
        return _action(client)

    run_rest(ctx, action)


@automod_group.command("enable")
@click.argument("server")
@click.argument("rule")
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def automod_enable(ctx, server, rule, reason):
    """Enable an AutoMod rule."""
    _set_enabled(ctx, server, rule, True, reason)


@automod_group.command("disable")
@click.argument("server")
@click.argument("rule")
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def automod_disable(ctx, server, rule, reason):
    """Disable an AutoMod rule without deleting it."""
    _set_enabled(ctx, server, rule, False, reason)


@automod_group.command("delete")
@click.argument("server")
@click.argument("rule")
@click.option("--reason", default=None, help="Audit log reason.")
@click.pass_context
def automod_delete(ctx, server, rule, reason):
    """Delete an AutoMod rule."""
    from discli.security import audit_log, confirm_destructive
    confirm_destructive("automod delete", f"rule {rule} in {server}")

    def action(client):
        async def _action(client):
            guild = await resolve_guild(client, server)
            target = await _resolve_rule(guild, rule)
            name, rule_id = target.name, str(target.id)
            await target.delete(reason=reason)
            audit_log("automod delete", {"server": server, "name": name, "id": rule_id})
            output(ctx, {"id": rule_id, "name": name, "deleted": True},
                   plain_text=f"Deleted AutoMod rule '{name}'")
        return _action(client)

    run_rest(ctx, action)

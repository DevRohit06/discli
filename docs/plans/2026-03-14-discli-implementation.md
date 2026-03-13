# discli Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build `discli`, a Python CLI that wraps Discord's Bot API for AI agents and humans to manage Discord from the terminal.

**Architecture:** Click CLI with grouped subcommands dispatching async actions through a discord.py client wrapper. Command-based actions connect, execute, disconnect. Listen mode stays connected and streams events. Token resolved via flag → env var → config file.

**Tech Stack:** Python 3.10+, discord.py, click, pytest

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/discli/__init__.py`
- Create: `src/discli/cli.py`

**Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "discli"
version = "0.1.0"
description = "Discord CLI for AI agents"
requires-python = ">=3.10"
dependencies = [
    "discord.py>=2.3",
    "click>=8.1",
]

[project.scripts]
discli = "discli.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
]
```

**Step 2: Create `src/discli/__init__.py`**

```python
"""discli — Discord CLI for AI agents."""
```

**Step 3: Create a minimal `src/discli/cli.py`**

```python
import click


@click.group()
@click.option("--token", envvar="DISCORD_BOT_TOKEN", default=None, help="Discord bot token.")
@click.option("--json", "use_json", is_flag=True, default=False, help="Output as JSON.")
@click.pass_context
def main(ctx, token, use_json):
    """discli — Discord CLI for AI agents."""
    ctx.ensure_object(dict)
    ctx.obj["token"] = token
    ctx.obj["use_json"] = use_json
```

**Step 4: Install in dev mode and verify CLI entry point**

```bash
cd D:/side-projects/discli
pip install -e ".[dev]"
discli --help
```

Expected: Help text showing `--token`, `--json`, and `Usage: discli [OPTIONS] COMMAND [ARGS]...`

**Step 5: Commit**

```bash
git add pyproject.toml src/
git commit -m "feat: scaffold project with pyproject.toml and minimal CLI entry point"
```

---

### Task 2: Config Module

**Files:**
- Create: `src/discli/config.py`
- Create: `src/discli/commands/config_cmd.py`
- Create: `src/discli/commands/__init__.py`
- Modify: `src/discli/cli.py`
- Create: `tests/test_config.py`

**Step 1: Write failing tests for config**

```python
# tests/test_config.py
import json
from pathlib import Path

from discli.config import load_config, save_config


def test_save_and_load_config(tmp_path):
    config_path = tmp_path / "config.json"
    save_config({"token": "test-token-123"}, config_path)
    loaded = load_config(config_path)
    assert loaded["token"] == "test-token-123"


def test_load_missing_config(tmp_path):
    config_path = tmp_path / "nonexistent.json"
    loaded = load_config(config_path)
    assert loaded == {}
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement `src/discli/config.py`**

```python
import json
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".discli" / "config.json"


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def save_config(data: dict, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = load_config(path)
    existing.update(data)
    path.write_text(json.dumps(existing, indent=2))
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: 2 passed

**Step 5: Implement `src/discli/commands/__init__.py`**

```python
```

(Empty file.)

**Step 6: Implement `src/discli/commands/config_cmd.py`**

```python
import click

from discli.config import load_config, save_config


@click.group("config")
def config_group():
    """Manage discli configuration."""


@config_group.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set a config value (e.g. discli config set token YOUR_TOKEN)."""
    save_config({key: value})
    click.echo(f"Set {key}.")


@config_group.command("show")
@click.pass_context
def config_show(ctx):
    """Show current configuration."""
    import json as json_mod

    data = load_config()
    use_json = ctx.obj.get("use_json", False)
    if use_json:
        click.echo(json_mod.dumps(data, indent=2))
    else:
        if not data:
            click.echo("No configuration set.")
        else:
            for k, v in data.items():
                display = v[:8] + "..." if k == "token" and len(v) > 8 else v
                click.echo(f"{k}: {display}")
```

**Step 7: Wire config command into CLI — modify `src/discli/cli.py`**

```python
import click

from discli.config import load_config
from discli.commands.config_cmd import config_group


@click.group()
@click.option("--token", envvar="DISCORD_BOT_TOKEN", default=None, help="Discord bot token.")
@click.option("--json", "use_json", is_flag=True, default=False, help="Output as JSON.")
@click.pass_context
def main(ctx, token, use_json):
    """discli — Discord CLI for AI agents."""
    ctx.ensure_object(dict)
    if token is None:
        config = load_config()
        token = config.get("token")
    ctx.obj["token"] = token
    ctx.obj["use_json"] = use_json


main.add_command(config_group)
```

**Step 8: Manual verification**

```bash
discli config set token fake-token-123
discli config show
discli config show --json
```

Expected: Token saved and displayed (truncated in plain text, full in JSON).

**Step 9: Commit**

```bash
git add src/ tests/
git commit -m "feat: add config module with set/show commands and token resolution"
```

---

### Task 3: Async Client Wrapper

**Files:**
- Create: `src/discli/client.py`
- Create: `tests/test_client.py`

**Step 1: Write failing test for the client wrapper**

```python
# tests/test_client.py
import pytest

from discli.client import resolve_token


def test_resolve_token_from_arg():
    assert resolve_token("my-token", {}) == "my-token"


def test_resolve_token_from_config():
    assert resolve_token(None, {"token": "config-token"}) == "config-token"


def test_resolve_token_missing():
    with pytest.raises(click.ClickException):
        resolve_token(None, {})
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_client.py -v
```

Expected: FAIL

**Step 3: Implement `src/discli/client.py`**

```python
import asyncio
from typing import Any, Callable, Coroutine

import click
import discord


def resolve_token(token: str | None, config: dict) -> str:
    if token:
        return token
    config_token = config.get("token")
    if config_token:
        return config_token
    raise click.ClickException(
        "No token provided. Use --token, set DISCORD_BOT_TOKEN, or run: discli config set token YOUR_TOKEN"
    )


async def run_action(token: str, action: Callable[[discord.Client], Coroutine[Any, Any, Any]]) -> Any:
    """Connect a bot client, run an action on_ready, return the result, disconnect."""
    intents = discord.Intents.all()
    client = discord.Client(intents=intents)
    result = None
    error = None

    @client.event
    async def on_ready():
        nonlocal result, error
        try:
            result = await action(client)
        except Exception as e:
            error = e
        finally:
            await client.close()

    await client.start(token)

    if error:
        raise error
    return result


def run_discord(ctx, action: Callable[[discord.Client], Coroutine[Any, Any, Any]]) -> Any:
    """Synchronous entry point: resolve token, run action, return result."""
    token = resolve_token(ctx.obj.get("token"), {})
    try:
        return asyncio.run(run_action(token, action))
    except discord.LoginFailure:
        raise click.ClickException("Invalid bot token.")
    except discord.HTTPException as e:
        raise click.ClickException(f"Discord API error: {e}")
```

**Step 4: Fix test imports and run**

Add `import click` to the top of `tests/test_client.py`.

```bash
pytest tests/test_client.py -v
```

Expected: 3 passed

**Step 5: Commit**

```bash
git add src/discli/client.py tests/test_client.py
git commit -m "feat: add async client wrapper with token resolution and run_discord helper"
```

---

### Task 4: Output Utilities

**Files:**
- Create: `src/discli/utils.py`
- Create: `tests/test_utils.py`

**Step 1: Write failing tests**

```python
# tests/test_utils.py
import json

from discli.utils import format_output


def test_format_output_plain():
    result = format_output("hello world", use_json=False)
    assert result == "hello world"


def test_format_output_json_dict():
    data = {"key": "value"}
    result = format_output(data, use_json=True)
    assert json.loads(result) == data


def test_format_output_json_list():
    data = [{"id": 1}, {"id": 2}]
    result = format_output(data, use_json=True)
    assert json.loads(result) == data
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/test_utils.py -v
```

Expected: FAIL

**Step 3: Implement `src/discli/utils.py`**

```python
import json
from typing import Any

import click


def format_output(data: Any, use_json: bool = False) -> str:
    if use_json:
        return json.dumps(data, indent=2, default=str)
    return str(data)


def output(ctx: click.Context, data: Any, plain_text: str | None = None) -> None:
    """Print output respecting --json flag."""
    use_json = ctx.obj.get("use_json", False)
    if use_json:
        click.echo(format_output(data, use_json=True))
    else:
        click.echo(plain_text if plain_text is not None else format_output(data))


def resolve_channel(client, identifier: str):
    """Resolve a channel by ID or #name."""
    if identifier.startswith("#"):
        name = identifier[1:]
        for guild in client.guilds:
            for ch in guild.text_channels:
                if ch.name == name:
                    return ch
        raise click.ClickException(f"Channel not found: #{name}")
    else:
        try:
            channel = client.get_channel(int(identifier))
            if channel is None:
                raise click.ClickException(f"Channel not found: {identifier}")
            return channel
        except ValueError:
            raise click.ClickException(f"Invalid channel identifier: {identifier}")


def resolve_guild(client, identifier: str):
    """Resolve a guild/server by ID or name."""
    try:
        guild_id = int(identifier)
        guild = client.get_guild(guild_id)
        if guild:
            return guild
    except ValueError:
        pass
    for guild in client.guilds:
        if guild.name.lower() == identifier.lower():
            return guild
    raise click.ClickException(f"Server not found: {identifier}")
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_utils.py -v
```

Expected: 3 passed

**Step 5: Commit**

```bash
git add src/discli/utils.py tests/test_utils.py
git commit -m "feat: add output formatting and channel/server resolver utilities"
```

---

### Task 5: Message Commands

**Files:**
- Create: `src/discli/commands/message.py`
- Modify: `src/discli/cli.py`

**Step 1: Implement `src/discli/commands/message.py`**

```python
import click

from discli.client import run_discord
from discli.utils import output, resolve_channel


@click.group("message")
def message_group():
    """Send, list, edit, and delete messages."""


@message_group.command("send")
@click.argument("channel")
@click.argument("text")
@click.option("--embed-title", default=None, help="Embed title.")
@click.option("--embed-desc", default=None, help="Embed description.")
@click.pass_context
def message_send(ctx, channel, text, embed_title, embed_desc):
    """Send a message to a channel."""
    import discord

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            embed = None
            if embed_title or embed_desc:
                embed = discord.Embed(title=embed_title, description=embed_desc)
            msg = await ch.send(content=text, embed=embed)
            data = {"id": str(msg.id), "channel": ch.name, "content": msg.content}
            output(ctx, data, plain_text=f"Sent message {msg.id} to #{ch.name}")
        return _action(client)

    run_discord(ctx, action)


@message_group.command("list")
@click.argument("channel")
@click.option("--limit", default=10, help="Number of messages to fetch.")
@click.pass_context
def message_list(ctx, channel, limit):
    """List recent messages in a channel."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            messages = []
            async for msg in ch.history(limit=limit):
                messages.append({
                    "id": str(msg.id),
                    "author": str(msg.author),
                    "content": msg.content,
                    "timestamp": msg.created_at.isoformat(),
                })
            plain_lines = []
            for m in messages:
                ts = m["timestamp"][:19].replace("T", " ")
                plain_lines.append(f"[{ts}] {m['author']}: {m['content']}")
            output(ctx, messages, plain_text="\n".join(plain_lines))
        return _action(client)

    run_discord(ctx, action)


@message_group.command("edit")
@click.argument("channel")
@click.argument("message_id")
@click.argument("new_text")
@click.pass_context
def message_edit(ctx, channel, message_id, new_text):
    """Edit a message."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            await msg.edit(content=new_text)
            output(ctx, {"id": str(msg.id), "content": new_text}, plain_text=f"Edited message {msg.id}")
        return _action(client)

    run_discord(ctx, action)


@message_group.command("delete")
@click.argument("channel")
@click.argument("message_id")
@click.pass_context
def message_delete(ctx, channel, message_id):
    """Delete a message."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            await msg.delete()
            output(ctx, {"id": str(msg.id), "deleted": True}, plain_text=f"Deleted message {msg.id}")
        return _action(client)

    run_discord(ctx, action)
```

**Step 2: Register message group in `src/discli/cli.py`**

Add this import and registration:

```python
from discli.commands.message import message_group
main.add_command(message_group)
```

**Step 3: Verify CLI wiring**

```bash
discli message --help
discli message send --help
```

Expected: Help text for message group and send subcommand.

**Step 4: Commit**

```bash
git add src/discli/commands/message.py src/discli/cli.py
git commit -m "feat: add message send/list/edit/delete commands"
```

---

### Task 6: Reaction Commands

**Files:**
- Create: `src/discli/commands/reaction.py`
- Modify: `src/discli/cli.py`

**Step 1: Implement `src/discli/commands/reaction.py`**

```python
import click

from discli.client import run_discord
from discli.utils import output, resolve_channel


@click.group("reaction")
def reaction_group():
    """Add, remove, and list reactions."""


@reaction_group.command("add")
@click.argument("channel")
@click.argument("message_id")
@click.argument("emoji")
@click.pass_context
def reaction_add(ctx, channel, message_id, emoji):
    """Add a reaction to a message."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            await msg.add_reaction(emoji)
            output(ctx, {"message_id": message_id, "emoji": emoji}, plain_text=f"Reacted {emoji} to message {message_id}")
        return _action(client)

    run_discord(ctx, action)


@reaction_group.command("remove")
@click.argument("channel")
@click.argument("message_id")
@click.argument("emoji")
@click.pass_context
def reaction_remove(ctx, channel, message_id, emoji):
    """Remove a reaction from a message."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            await msg.remove_reaction(emoji, client.user)
            output(ctx, {"message_id": message_id, "emoji": emoji}, plain_text=f"Removed {emoji} from message {message_id}")
        return _action(client)

    run_discord(ctx, action)


@reaction_group.command("list")
@click.argument("channel")
@click.argument("message_id")
@click.pass_context
def reaction_list(ctx, channel, message_id):
    """List reactions on a message."""

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            msg = await ch.fetch_message(int(message_id))
            reactions = []
            for r in msg.reactions:
                reactions.append({"emoji": str(r.emoji), "count": r.count})
            plain_lines = [f"{r['emoji']} x{r['count']}" for r in reactions]
            output(ctx, reactions, plain_text="\n".join(plain_lines) if plain_lines else "No reactions.")
        return _action(client)

    run_discord(ctx, action)
```

**Step 2: Register in `src/discli/cli.py`**

```python
from discli.commands.reaction import reaction_group
main.add_command(reaction_group)
```

**Step 3: Verify**

```bash
discli reaction --help
```

Expected: Help text for reaction group.

**Step 4: Commit**

```bash
git add src/discli/commands/reaction.py src/discli/cli.py
git commit -m "feat: add reaction add/remove/list commands"
```

---

### Task 7: Channel Commands

**Files:**
- Create: `src/discli/commands/channel.py`
- Modify: `src/discli/cli.py`

**Step 1: Implement `src/discli/commands/channel.py`**

```python
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
@click.option("--type", "channel_type", type=click.Choice(["text", "voice", "category"]), default="text")
@click.pass_context
def channel_create(ctx, server, name, channel_type):
    """Create a channel in a server."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            if channel_type == "text":
                ch = await guild.create_text_channel(name)
            elif channel_type == "voice":
                ch = await guild.create_voice_channel(name)
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

    def action(client):
        async def _action(client):
            ch = resolve_channel(client, channel)
            name = ch.name
            await ch.delete()
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
```

**Step 2: Register in `src/discli/cli.py`**

```python
from discli.commands.channel import channel_group
main.add_command(channel_group)
```

**Step 3: Verify**

```bash
discli channel --help
```

**Step 4: Commit**

```bash
git add src/discli/commands/channel.py src/discli/cli.py
git commit -m "feat: add channel list/create/delete/info commands"
```

---

### Task 8: Server Commands

**Files:**
- Create: `src/discli/commands/server.py`
- Modify: `src/discli/cli.py`

**Step 1: Implement `src/discli/commands/server.py`**

```python
import click

from discli.client import run_discord
from discli.utils import output, resolve_guild


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
            for g in client.guilds:
                servers.append({
                    "id": str(g.id),
                    "name": g.name,
                    "member_count": g.member_count,
                })
            plain_lines = [f"{s['name']} (ID: {s['id']}, members: {s['member_count']})" for s in servers]
            output(ctx, servers, plain_text="\n".join(plain_lines) if plain_lines else "Bot is not in any servers.")
        return _action(client)

    run_discord(ctx, action)


@server_group.command("info")
@click.argument("server")
@click.pass_context
def server_info(ctx, server):
    """Show server details."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            data = {
                "id": str(guild.id),
                "name": guild.name,
                "owner": str(guild.owner),
                "member_count": guild.member_count,
                "channel_count": len(guild.channels),
                "role_count": len(guild.roles),
                "created_at": guild.created_at.isoformat(),
            }
            plain_lines = [f"{k}: {v}" for k, v in data.items()]
            output(ctx, data, plain_text="\n".join(plain_lines))
        return _action(client)

    run_discord(ctx, action)
```

**Step 2: Register in `src/discli/cli.py`**

```python
from discli.commands.server import server_group
main.add_command(server_group)
```

**Step 3: Verify**

```bash
discli server --help
```

**Step 4: Commit**

```bash
git add src/discli/commands/server.py src/discli/cli.py
git commit -m "feat: add server list/info commands"
```

---

### Task 9: Role Commands

**Files:**
- Create: `src/discli/commands/role.py`
- Modify: `src/discli/cli.py`

**Step 1: Implement `src/discli/commands/role.py`**

```python
import click
import discord

from discli.client import run_discord
from discli.utils import output, resolve_guild


def resolve_role(guild, identifier: str):
    try:
        role_id = int(identifier)
        role = guild.get_role(role_id)
        if role:
            return role
    except ValueError:
        pass
    for role in guild.roles:
        if role.name.lower() == identifier.lower():
            return role
    raise click.ClickException(f"Role not found: {identifier}")


def resolve_member(guild, identifier: str):
    try:
        member_id = int(identifier)
        member = guild.get_member(member_id)
        if member:
            return member
    except ValueError:
        pass
    for member in guild.members:
        if member.name.lower() == identifier.lower() or str(member).lower() == identifier.lower():
            return member
    raise click.ClickException(f"Member not found: {identifier}")


@click.group("role")
def role_group():
    """Manage server roles."""


@role_group.command("list")
@click.argument("server")
@click.pass_context
def role_list(ctx, server):
    """List roles in a server."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            roles = [{"id": str(r.id), "name": r.name, "color": str(r.color), "members": len(r.members)} for r in guild.roles if r.name != "@everyone"]
            plain_lines = [f"{r['name']} (ID: {r['id']}, color: {r['color']}, members: {r['members']})" for r in roles]
            output(ctx, roles, plain_text="\n".join(plain_lines) if plain_lines else "No roles.")
        return _action(client)

    run_discord(ctx, action)


@role_group.command("create")
@click.argument("server")
@click.argument("name")
@click.option("--color", default=None, help="Hex color (e.g. ff0000).")
@click.option("--permissions", default=None, help="Permission integer.")
@click.pass_context
def role_create(ctx, server, name, color, permissions):
    """Create a role."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            kwargs = {"name": name}
            if color:
                kwargs["color"] = discord.Color(int(color, 16))
            if permissions:
                kwargs["permissions"] = discord.Permissions(int(permissions))
            role = await guild.create_role(**kwargs)
            data = {"id": str(role.id), "name": role.name}
            output(ctx, data, plain_text=f"Created role {role.name} (ID: {role.id})")
        return _action(client)

    run_discord(ctx, action)


@role_group.command("delete")
@click.argument("server")
@click.argument("role")
@click.pass_context
def role_delete(ctx, server, role):
    """Delete a role."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            r = resolve_role(guild, role)
            name = r.name
            await r.delete()
            output(ctx, {"name": name, "deleted": True}, plain_text=f"Deleted role {name}")
        return _action(client)

    run_discord(ctx, action)


@role_group.command("assign")
@click.argument("server")
@click.argument("member")
@click.argument("role")
@click.pass_context
def role_assign(ctx, server, member, role):
    """Assign a role to a member."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            m = resolve_member(guild, member)
            r = resolve_role(guild, role)
            await m.add_roles(r)
            output(ctx, {"member": str(m), "role": r.name}, plain_text=f"Assigned {r.name} to {m}")
        return _action(client)

    run_discord(ctx, action)


@role_group.command("remove")
@click.argument("server")
@click.argument("member")
@click.argument("role")
@click.pass_context
def role_remove(ctx, server, member, role):
    """Remove a role from a member."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            m = resolve_member(guild, member)
            r = resolve_role(guild, role)
            await m.remove_roles(r)
            output(ctx, {"member": str(m), "role": r.name}, plain_text=f"Removed {r.name} from {m}")
        return _action(client)

    run_discord(ctx, action)
```

**Step 2: Register in `src/discli/cli.py`**

```python
from discli.commands.role import role_group
main.add_command(role_group)
```

**Step 3: Verify**

```bash
discli role --help
```

**Step 4: Commit**

```bash
git add src/discli/commands/role.py src/discli/cli.py
git commit -m "feat: add role list/create/delete/assign/remove commands"
```

---

### Task 10: Member Commands

**Files:**
- Create: `src/discli/commands/member.py`
- Modify: `src/discli/cli.py`

**Step 1: Implement `src/discli/commands/member.py`**

```python
import click

from discli.client import run_discord
from discli.commands.role import resolve_member
from discli.utils import output, resolve_guild


@click.group("member")
def member_group():
    """List, inspect, kick, ban, and unban members."""


@member_group.command("list")
@click.argument("server")
@click.option("--limit", default=50, help="Max members to list.")
@click.pass_context
def member_list(ctx, server, limit):
    """List members of a server."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            members = []
            for m in guild.members[:limit]:
                members.append({
                    "id": str(m.id),
                    "name": str(m),
                    "nick": m.nick,
                    "bot": m.bot,
                })
            plain_lines = [f"{m['name']}{' (bot)' if m['bot'] else ''}{f' aka {m["nick"]}' if m['nick'] else ''}" for m in members]
            output(ctx, members, plain_text="\n".join(plain_lines) if plain_lines else "No members found.")
        return _action(client)

    run_discord(ctx, action)


@member_group.command("info")
@click.argument("server")
@click.argument("member")
@click.pass_context
def member_info(ctx, server, member):
    """Show member details."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            m = resolve_member(guild, member)
            data = {
                "id": str(m.id),
                "name": str(m),
                "nick": m.nick,
                "bot": m.bot,
                "roles": [r.name for r in m.roles if r.name != "@everyone"],
                "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            }
            plain_lines = [f"{k}: {v}" for k, v in data.items() if v is not None]
            output(ctx, data, plain_text="\n".join(plain_lines))
        return _action(client)

    run_discord(ctx, action)


@member_group.command("kick")
@click.argument("server")
@click.argument("member")
@click.option("--reason", default=None, help="Reason for kick.")
@click.pass_context
def member_kick(ctx, server, member, reason):
    """Kick a member from the server."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            m = resolve_member(guild, member)
            name = str(m)
            await m.kick(reason=reason)
            output(ctx, {"member": name, "kicked": True}, plain_text=f"Kicked {name}")
        return _action(client)

    run_discord(ctx, action)


@member_group.command("ban")
@click.argument("server")
@click.argument("member")
@click.option("--reason", default=None, help="Reason for ban.")
@click.pass_context
def member_ban(ctx, server, member, reason):
    """Ban a member from the server."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            m = resolve_member(guild, member)
            name = str(m)
            await m.ban(reason=reason)
            output(ctx, {"member": name, "banned": True}, plain_text=f"Banned {name}")
        return _action(client)

    run_discord(ctx, action)


@member_group.command("unban")
@click.argument("server")
@click.argument("member")
@click.pass_context
def member_unban(ctx, server, member):
    """Unban a member from the server."""

    def action(client):
        async def _action(client):
            guild = resolve_guild(client, server)
            bans = [b async for b in guild.bans()]
            target = None
            for ban_entry in bans:
                u = ban_entry.user
                if str(u.id) == member or str(u).lower() == member.lower():
                    target = u
                    break
            if not target:
                raise click.ClickException(f"Banned user not found: {member}")
            await guild.unban(target)
            output(ctx, {"member": str(target), "unbanned": True}, plain_text=f"Unbanned {target}")
        return _action(client)

    run_discord(ctx, action)
```

**Step 2: Register in `src/discli/cli.py`**

```python
from discli.commands.member import member_group
main.add_command(member_group)
```

**Step 3: Verify**

```bash
discli member --help
```

**Step 4: Commit**

```bash
git add src/discli/commands/member.py src/discli/cli.py
git commit -m "feat: add member list/info/kick/ban/unban commands"
```

---

### Task 11: Listen Command

**Files:**
- Create: `src/discli/commands/listen.py`
- Modify: `src/discli/cli.py`

**Step 1: Implement `src/discli/commands/listen.py`**

```python
import asyncio
import json

import click
import discord


@click.command("listen")
@click.option("--server", default=None, help="Filter by server name or ID.")
@click.option("--channel", default=None, help="Filter by channel name or ID.")
@click.option("--events", default=None, help="Comma-separated event types: messages,reactions,members")
@click.pass_context
def listen_cmd(ctx, server, channel, events):
    """Listen for real-time Discord events. Ctrl+C to stop."""
    from discli.client import resolve_token

    token = resolve_token(ctx.obj.get("token"), {})
    use_json = ctx.obj.get("use_json", False)
    event_filter = set(events.split(",")) if events else None

    intents = discord.Intents.all()
    client = discord.Client(intents=intents)

    def should_emit(guild, ch):
        if server:
            try:
                if str(guild.id) != server and guild.name.lower() != server.lower():
                    return False
            except Exception:
                return False
        if channel:
            ch_name = channel.lstrip("#")
            try:
                if str(ch.id) != ch_name and ch.name != ch_name:
                    return False
            except Exception:
                return False
        return True

    def emit(data, plain):
        if use_json:
            click.echo(json.dumps(data, default=str))
        else:
            click.echo(plain)

    @client.event
    async def on_ready():
        click.echo(f"Listening as {client.user}... (Ctrl+C to stop)", err=True)

    @client.event
    async def on_message(message):
        if event_filter and "messages" not in event_filter:
            return
        if not should_emit(message.guild, message.channel):
            return
        data = {
            "event": "message",
            "server": message.guild.name if message.guild else "DM",
            "channel": message.channel.name if hasattr(message.channel, "name") else "DM",
            "author": str(message.author),
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "message_id": str(message.id),
        }
        emit(data, f"[{data['timestamp'][:19]}] #{data['channel']} {data['author']}: {data['content']}")

    @client.event
    async def on_reaction_add(reaction, user):
        if event_filter and "reactions" not in event_filter:
            return
        if not should_emit(reaction.message.guild, reaction.message.channel):
            return
        data = {
            "event": "reaction_add",
            "server": reaction.message.guild.name,
            "channel": reaction.message.channel.name,
            "message_id": str(reaction.message.id),
            "emoji": str(reaction.emoji),
            "user": str(user),
        }
        emit(data, f"{data['user']} reacted {data['emoji']} on message {data['message_id']} in #{data['channel']}")

    @client.event
    async def on_reaction_remove(reaction, user):
        if event_filter and "reactions" not in event_filter:
            return
        if not should_emit(reaction.message.guild, reaction.message.channel):
            return
        data = {
            "event": "reaction_remove",
            "server": reaction.message.guild.name,
            "channel": reaction.message.channel.name,
            "message_id": str(reaction.message.id),
            "emoji": str(reaction.emoji),
            "user": str(user),
        }
        emit(data, f"{data['user']} removed {data['emoji']} from message {data['message_id']} in #{data['channel']}")

    @client.event
    async def on_member_join(member):
        if event_filter and "members" not in event_filter:
            return
        data = {"event": "member_join", "server": member.guild.name, "member": str(member)}
        emit(data, f"{data['member']} joined {data['server']}")

    @client.event
    async def on_member_remove(member):
        if event_filter and "members" not in event_filter:
            return
        data = {"event": "member_remove", "server": member.guild.name, "member": str(member)}
        emit(data, f"{data['member']} left {data['server']}")

    try:
        asyncio.run(client.start(token))
    except KeyboardInterrupt:
        click.echo("\nStopped listening.", err=True)
```

**Step 2: Register in `src/discli/cli.py`**

```python
from discli.commands.listen import listen_cmd
main.add_command(listen_cmd)
```

**Step 3: Verify**

```bash
discli listen --help
```

Expected: Help text with `--server`, `--channel`, `--events` options.

**Step 4: Commit**

```bash
git add src/discli/commands/listen.py src/discli/cli.py
git commit -m "feat: add listen command for real-time event streaming"
```

---

### Task 12: Final CLI Wiring & Integration Verification

**Files:**
- Modify: `src/discli/cli.py` (final version with all imports)

**Step 1: Ensure `src/discli/cli.py` has all command groups registered**

```python
import click

from discli.config import load_config
from discli.commands.config_cmd import config_group
from discli.commands.message import message_group
from discli.commands.reaction import reaction_group
from discli.commands.channel import channel_group
from discli.commands.server import server_group
from discli.commands.role import role_group
from discli.commands.member import member_group
from discli.commands.listen import listen_cmd


@click.group()
@click.option("--token", envvar="DISCORD_BOT_TOKEN", default=None, help="Discord bot token.")
@click.option("--json", "use_json", is_flag=True, default=False, help="Output as JSON.")
@click.pass_context
def main(ctx, token, use_json):
    """discli — Discord CLI for AI agents."""
    ctx.ensure_object(dict)
    if token is None:
        config = load_config()
        token = config.get("token")
    ctx.obj["token"] = token
    ctx.obj["use_json"] = use_json


main.add_command(config_group)
main.add_command(message_group)
main.add_command(reaction_group)
main.add_command(channel_group)
main.add_command(server_group)
main.add_command(role_group)
main.add_command(member_group)
main.add_command(listen_cmd)
```

**Step 2: Run full verification**

```bash
discli --help
discli config --help
discli message --help
discli reaction --help
discli channel --help
discli server --help
discli role --help
discli member --help
discli listen --help
```

Expected: All command groups and subcommands visible.

**Step 3: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add src/discli/cli.py
git commit -m "feat: wire all command groups into CLI entry point"
```

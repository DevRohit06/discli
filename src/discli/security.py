"""Security features for discli."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import click

DISCLI_DIR = Path.home() / ".discli"
AUDIT_LOG_PATH = DISCLI_DIR / "audit.log"
PERMISSIONS_PATH = DISCLI_DIR / "permissions.json"

# Commands that are destructive and require confirmation
DESTRUCTIVE_COMMANDS = {
    "member kick",
    "member ban",
    "member unban",
    "channel delete",
    "message delete",
    "role delete",
}

# Default permission profiles
DEFAULT_PROFILES = {
    "full": {
        "description": "Full access to all commands",
        "allowed": ["*"],
        "denied": [],
    },
    "chat": {
        "description": "Messages, reactions, threads, typing only",
        "allowed": ["message", "reaction", "thread", "typing", "dm", "listen", "config", "server"],
        "denied": ["member kick", "member ban", "member unban", "channel delete", "role delete", "role create", "channel create"],
    },
    "readonly": {
        "description": "Read-only: list, info, get, search, listen",
        "allowed": ["message list", "message get", "message search", "message history", "channel list", "channel info", "server list", "server info", "role list", "member list", "member info", "reaction list", "thread list", "listen", "config show"],
        "denied": ["*"],
    },
    "moderation": {
        "description": "Full access including moderation",
        "allowed": ["*"],
        "denied": [],
    },
}


def get_active_profile() -> dict:
    """Load the active permission profile."""
    if not PERMISSIONS_PATH.exists():
        return DEFAULT_PROFILES["full"]
    try:
        data = json.loads(PERMISSIONS_PATH.read_text())
        profile_name = data.get("active_profile", "full")
        custom_profiles = data.get("profiles", {})
        if profile_name in custom_profiles:
            return custom_profiles[profile_name]
        return DEFAULT_PROFILES.get(profile_name, DEFAULT_PROFILES["full"])
    except (json.JSONDecodeError, KeyError):
        return DEFAULT_PROFILES["full"]


def set_active_profile(profile_name: str) -> None:
    """Set the active permission profile."""
    DISCLI_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    if PERMISSIONS_PATH.exists():
        try:
            data = json.loads(PERMISSIONS_PATH.read_text())
        except json.JSONDecodeError:
            data = {}
    data["active_profile"] = profile_name
    if "profiles" not in data:
        data["profiles"] = {}
    PERMISSIONS_PATH.write_text(json.dumps(data, indent=2))


def is_command_allowed(command_path: str) -> bool:
    """Check if a command is allowed by the active profile."""
    profile = get_active_profile()
    allowed = profile.get("allowed", ["*"])
    denied = profile.get("denied", [])

    # Check denied first
    for pattern in denied:
        if pattern == "*":
            # Everything denied, check if explicitly allowed
            for a in allowed:
                if a == "*":
                    return True
                if command_path == a or command_path.startswith(a + " "):
                    return True
            return False
        if command_path == pattern or command_path.startswith(pattern + " "):
            return False

    # Check allowed
    for pattern in allowed:
        if pattern == "*":
            return True
        if command_path == pattern or command_path.startswith(pattern + " "):
            return True

    return False


def confirm_destructive(command_path: str, details: str = "") -> None:
    """Prompt for confirmation on destructive commands unless --yes is set."""
    if command_path not in DESTRUCTIVE_COMMANDS:
        return

    ctx = click.get_current_context()
    if ctx.obj.get("yes"):
        return

    msg = f"⚠ Destructive action: {command_path}"
    if details:
        msg += f" ({details})"
    if not click.confirm(msg + ". Continue?", default=False):
        raise click.Abort()


def audit_log(command: str, args: dict, result: str = "ok", user: str = "") -> None:
    """Append an entry to the audit log."""
    DISCLI_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "args": args,
        "result": result,
        "user": user,
    }
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


# Simple rate limiter
class RateLimiter:
    """Token bucket rate limiter for Discord API calls."""

    def __init__(self, max_calls: int = 5, period: float = 5.0):
        self.max_calls = max_calls
        self.period = period
        self.calls: list[float] = []

    def wait(self) -> None:
        """Wait if rate limit would be exceeded."""
        now = time.time()
        self.calls = [t for t in self.calls if now - t < self.period]
        if len(self.calls) >= self.max_calls:
            sleep_time = self.period - (now - self.calls[0])
            if sleep_time > 0:
                click.echo(f"Rate limited. Waiting {sleep_time:.1f}s...", err=True)
                time.sleep(sleep_time)
        self.calls.append(time.time())


# Global rate limiter
rate_limiter = RateLimiter()


def check_user_permission(guild, user_id: int, required_permission: str) -> None:
    """Check if the Discord user who triggered the action has the required permission."""
    member = guild.get_member(user_id)
    if member is None:
        raise click.ClickException(f"Member {user_id} not found in server.")

    perm_map = {
        "kick": "kick_members",
        "ban": "ban_members",
        "manage_channels": "manage_channels",
        "manage_roles": "manage_roles",
        "manage_messages": "manage_messages",
    }

    perm_attr = perm_map.get(required_permission)
    if perm_attr and not getattr(member.guild_permissions, perm_attr, False):
        raise click.ClickException(
            f"User {member} does not have '{required_permission}' permission in {guild.name}."
        )

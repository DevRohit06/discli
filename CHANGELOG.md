# Changelog

All notable changes to discli are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions before 0.11.0 are documented in
[GitHub Releases](https://github.com/DevRohit06/discli/releases).

## [0.11.0] - 2026-08-25

A survey of discord.py 2.7.1 found roughly twenty guild-management APIs that
ship in the version discli already pinned but that discli never called. This
release wires up the useful ones, adds scheduling, and fixes several bugs found
only by running the commands against a live server.

### ⚠ Breaking

- **`--profile moderation` no longer grants everything.** It was defined as
  `allowed: ["*"]`, byte-identical to `full`, so selecting it for least
  privilege did nothing while the docs advertised a "moderation-safe subset".
  It is now an allowlist: read access, member and content moderation, AutoMod,
  channel lockdown, plus voice and interactions. It can no longer create or
  delete channels and roles, edit server settings, manage webhooks or emoji,
  schedule commands, clear the audit log, or change the permission profile.
  Use `--profile full` for the old behaviour.

- **`--profile chat` no longer grants `config set` or `server apply`.** The
  profile listed the bare group names `config` and `server`, and patterns match
  by prefix, so it reached every command those groups contain — including
  overwriting the stored bot token and restructuring (or, with `--prune`,
  deleting) a server.

- **Permission profiles are now enforced for commands that do not call
  Discord.** The check previously lived only in the HTTP paths, so
  `permission set`, `audit clear`, `config set`, `schedule *`, `serve`, and
  `listen` ignored the active profile entirely. Scripts relying on a restricted
  profile to run those commands will now be denied.

### Added

- **`discli invite`** — `list`, `create`, `info`, `delete`. `create --activity
  <app-id>` produces an invite that launches a Discord Activity in a voice
  channel.
- **`discli emoji`** — `list`, `upload`, `rename`, `delete`. Images over 256 KB
  are rejected before upload rather than failing at the API.
- **`discli automod`** — `list`, `create`, `edit`, `enable`, `disable`,
  `delete`. Trigger and action options are validated against each other rather
  than silently ignored.
- **`discli schedule`** — `add`, `list`, `remove`, `run-now`, `run`. Runs discli
  commands daily at a wall-clock time (with timezone) or on an interval, built
  on `discord.ext.tasks`. Actions are discli command lines, never shell
  commands, and are validated against the command tree when added.
- **`discli message search-server`** — searches a whole server through Discord's
  native index (by author, mentions, attachment type, pinned state, with
  relevance ranking), rather than scanning one channel client-side.
- **`discli server export` / `diff` / `apply`** — a server's roles, categories,
  channels, and role permission overwrites as a file. `apply` is additive by
  default; `--prune` deletes what the spec omits and confirms first.
- **`discli server audit-log`** — Discord's own log of who did what. Distinct
  from `discli audit`, which records what this CLI did locally.
- **`discli server edit`** — name, description, icon, banner, verification
  level, system channel.
- **`discli server onboarding show` / `edit`**.
- **`discli doctor --server <name>`** — reads the bot's real permission
  bitfield and flags permissions Discord split out of broader ones during 2026
  (`PIN_MESSAGES`, `BYPASS_SLOWMODE`, `CREATE_GUILD_EXPRESSIONS`,
  `CREATE_EVENTS`). A bot invited before a split keeps the old bit and silently
  loses the new capability. `doctor` stays entirely offline without `--server`.
- `discli message pin`, `unpin`, `pins`.
- `discli member nick`, `discli voice move`, `discli webhook send`.
- **Components v2 for dashboards**, opt-in per page via `"layout": "v2"` with
  container, text, section, separator, gallery, and button blocks. Pages
  without it render exactly as before.
- **Channel visibility disclosure.** From 2026-11-16 Discord omits channels a
  bot cannot view from the API entirely. `channel list` and `server info` note
  this on stderr (stdout stays a clean `--json` payload); `serve`'s
  `channel_list` reports `visible_only: true` in-band.

### Fixed

- **`role list --with-member-counts` no longer needs a privileged intent.** It
  paged the entire member list and tallied client-side; it now uses Discord's
  role member count endpoint — one request, no privileged intent.
- **`UnicodeEncodeError` on Windows.** Emoji are ordinary in Discord channel
  names, and Windows consoles and redirected pipes default to a legacy code
  page, so `channel list` crashed outright. Output is now UTF-8.
- **Resolving a server by name returned a partial guild** with no roles and no
  owner, so anything reading permissions off it computed zero. This made
  `doctor --server <name>` report no permissions at all, and made
  `--triggered-by` deny even the server owner.
- **`server export` dropped every channel's category**, which would have made
  `apply` recreate them all at the top level.
- **A failing stream flush in `serve` silently stopped updating a message** for
  the rest of the process. Transient errors now retry with backoff and anything
  else is reported as a JSONL error event.
- **Destructive commands asked for confirmation before checking permissions**,
  prompting for actions the profile forbade.

### Changed

- `tzdata` is now a dependency on Windows, which ships no IANA timezone
  database — `schedule --tz` would otherwise fail there.
- `discli doctor` gained a `PERMISSIONS` section, reported as skipped unless
  `--server` is passed.

[0.11.0]: https://github.com/DevRohit06/discli/releases/tag/v0.11.0

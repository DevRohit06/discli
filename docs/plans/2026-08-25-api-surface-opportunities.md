# discli — Discord API & discord.py Surface Opportunities

**Date:** 2026-08-25
**Status:** Research / roadmap input — not an approved plan
**Scope:** What discord.py 2.7.1 and the current Discord API make possible that discli does not yet expose.

---

## 0. TL;DR

**discli is not behind on the library. It is behind on using it.**

discord.py **2.7.1 (released 2026-03-03) is the newest release**, and `pyproject.toml`
already pins `discord-py>=2.7.1` with 2.7.1 installed. There is no upgrade to chase.

The gap is that roughly **twenty guild-management APIs that ship in the pinned version are
never called anywhere in `src/discli/`**. Soundboard, onboarding, automod, templates,
invites, emoji, stickers, audit logs, bulk-ban, prune, widget, Components v2, Modal v2,
voice-channel status, and per-guild bot identity are all sitting unused.

Three things are genuinely *new* and need work beyond wiring:

1. **Guild message search** (Discord shipped it to bots 2026-03-19) is not wrapped by
   discord.py at all. discli's current `message search` is a client-side scan of one channel.
2. **Channel obfuscation lands 2026-11-16** and will silently change what `channel list`
   returns. This is a real deadline, ~3 months out.
3. **`discord.ext.tasks`** is unused; `serve` hand-rolls its background loops.

---

## 1. Version status

| Item | Value |
|---|---|
| Latest discord.py on PyPI | **2.7.1**, released 2026-03-03 |
| discli pin (`pyproject.toml`) | `discord-py>=2.7.1` |
| Installed in `.venv` | 2.7.1 |
| Verdict | **Current. No bump needed.** |

Feature availability by version, for reference:

| Discord feature | Landed in discord.py |
|---|---|
| Voice messages | 2.3.0 |
| Polls, SKUs/entitlements | 2.4.0 |
| Soundboard, VC effects, message forwarding, subscriptions | 2.5.0 |
| Components v2 (`LayoutView`), guild onboarding, guest invites, media-only forums, gradient/holographic role colours, burst reactions | 2.6.0 |
| DAVE voice protocol, Modal v2 (`Checkbox`/`RadioGroup`/`Label`/`FileUpload`), `Guild.role_member_counts()`, `bypass_slowmode` / `set_voice_channel_status` / `pin_messages` permissions, user collectibles | 2.7.0 |

---

## 2. Deadlines and behaviour changes that affect discli

### 2.1 Channel obfuscation — **2026-11-16** (act before this)

Announced 2026-08-12. Channels the bot lacks `VIEW_CHANNEL` on become unreadable over the
Gateway and are **omitted from `GET /guilds/{guild.id}/channels`**.

Impact on discli:

- `channel list` will silently return fewer channels. Today a user cannot tell "this
  server has 12 channels" from "my bot can only see 12 channels."
- `server info` channel counts become permission-scoped.
- `serve`'s `channel_list` action has the same problem, and an agent consuming JSONL has
  no way to detect the truncation.

**Recommendation:** add an explicit visibility note to the output of `channel list` /
`server info` (e.g. a `visible_only: true` field in JSON mode) before November, so the
change does not read as data loss. Cheap now, confusing later.

### 2.2 Permission splits — already in effect

| Permission | Split from | Enforced since |
|---|---|---|
| `PIN_MESSAGES` | `MANAGE_MESSAGES` | Jan 2026 |
| `BYPASS_SLOWMODE` | `MANAGE_MESSAGES` et al. | 2026-02-23 |
| `CREATE_GUILD_EXPRESSIONS` | `MANAGE_GUILD_EXPRESSIONS` | 2026-02-23 |
| `CREATE_EVENTS` | `MANAGE_EVENTS` | 2026-02-23 |

Practical consequences:

- A future `message pin` needs **`PIN_MESSAGES`**, not `MANAGE_MESSAGES`. `serve` already
  implements `message_pin` / `message_unpin`, so this applies today.
- A future `emoji upload` / `sticker create` needs **`CREATE_GUILD_EXPRESSIONS`**.
- `event create` needs **`CREATE_EVENTS`**. This is live now and may already be failing
  for bots invited with an older permission bitfield.

**Recommendation:** `discli doctor` should report the bot's *actual* guild permission
bitfield against the set discli needs, naming the four new bits. Today doctor checks the
environment (token, ffmpeg, davey) but not the grant.

### 2.3 Privileged intent threshold changed — 2026-06-10

The gate moved from a server-count threshold to a **10,000-user** threshold, with an
**annual reapplication** requirement. `CLAUDE.md`'s intent gotchas describe the mechanics
correctly but predate this; the docs should note that verification is now user-count based
and must be renewed.

### 2.4 E2EE-only voice — since 2026-03-01

All DM/GDM/voice/Go Live audio is E2EE (DAVE). This *validates* discli's existing DAVE work
rather than obsoleting it. Note the split:

- discord.py 2.7.0 added DAVE support to the **voice client** (the send/connect path).
- `voice_engine.py:20-74` patches `discord-ext-voice-recv`'s `PacketDecoder._decode_packet`
  — the **receive** path, which core discord.py does not cover.

So the patch is still doing real work. It is worth re-testing against 2.7.1 to confirm the
patch and the library's native DAVE handling are not now double-decrypting, but do not
assume it can be deleted.

---

## 3. Tier A — shipped in discord.py 2.7.1, unused by discli

Every row below is callable today with zero new dependencies. Verified absent from
`src/discli/` by grep.

| # | Capability | discord.py API | Proposed command |
|---|---|---|---|
| A1 | Guild audit log | `Guild.audit_logs()` | `server audit-log [--action] [--user] [--limit]` |
| A2 | Invites | `Guild.invites()`, `TextChannel.create_invite()`, `Invite.delete()` | `invite list / create / delete / info` |
| A3 | Custom emoji | `Guild.fetch_emojis()`, `create_custom_emoji()`, `Emoji.delete()` | `emoji list / upload / delete / rename` |
| A4 | Stickers | `Guild.fetch_stickers()`, `create_sticker()` | `sticker list / upload / delete` |
| A5 | Soundboard | `Guild.fetch_soundboard_sounds()`, `create_soundboard_sound()`, `VoiceChannel.send_sound()` | `soundboard list / upload / delete / play` |
| A6 | AutoMod | `Guild.fetch_automod_rules()`, `create_automod_rule()`, `AutoModRule.edit/delete()` | `automod list / create / edit / delete / enable / disable` |
| A7 | Guild onboarding | `Guild.onboarding()`, `Guild.edit_onboarding()` | `server onboarding show / edit` |
| A8 | Guild templates | `Guild.templates()`, `Guild.create_template()`, `Template.sync()` | `server template list / create / sync / delete` |
| A9 | Bulk ban | `Guild.bulk_ban()` | `member bulk-ban <ids...>` (1 call vs N) |
| A10 | Member prune | `Guild.estimate_pruned_members()`, `prune_members()` | `member prune --days N [--dry-run]` |
| A11 | Role member counts | `Guild.role_member_counts()` | **fix `role list --with-member-counts`** — see §3.1 |
| A12 | Voice channel status | `VoiceChannel.edit(status=...)`, ≤500 chars | `voice status set <channel> <text>` |
| A13 | Per-guild bot identity | `Member.edit(nick=, avatar=, banner=, bio=)` on self | `bot identity set --nick --avatar --banner --bio` |
| A14 | Message forwarding | `Message.forward()`, `Message.is_forwardable()` | `message forward <msg> <channel>` |
| A15 | Server settings & icon | `Guild.edit(name=, icon=, banner=, ...)` | `server edit` (currently only `list` / `info` exist) |
| A16 | Guild widget | `Guild.widget()`, `Guild.edit_widget()` | `server widget show / edit` |
| A17 | Components v2 | `ui.LayoutView`, `Container`, `Section`, `TextDisplay`, `Thumbnail`, `MediaGallery`, `File`, `Separator` | upgrade `interact_engine.py` dashboards |
| A18 | Modal v2 | `ui.Label`, `Checkbox`, `RadioGroup`, `FileUpload` | upgrade `interact modal` beyond text inputs |
| A19 | Gradient / holographic roles | `Role.secondary_colour`, tertiary colour | `role edit --color-secondary --holographic` |
| A20 | Media-only forums | `MediaChannel` | `channel create --type media` |

### 3.1 The `role list --with-member-counts` fix

`src/discli/commands/role.py:32-49` builds member counts by **iterating the full member
list** and incrementing per role. That path requires the privileged **members intent** —
which is exactly why commits `7c915ee` and `c2aab48` had to make counts opt-in and add
Forbidden handling.

discord.py 2.7.0 exposes `Guild.role_member_counts()`, backed by the endpoint Discord
shipped 2025-12-09. It is **one REST call and needs no privileged intent**.

This is the single highest value-to-effort change in this document: it deletes a
workaround, removes an intent dependency, and turns an O(members) fetch into O(1).

### 3.2 Note on A17 / A18

Components v2 is the largest item here and the one that most changes what discli *is*.
`interact_engine.py` (611 lines) builds classic `View`s — rows of buttons and selects.
`LayoutView` allows real layout: sections with thumbnails, media galleries, separators,
containers with accent colours. For a tool whose pitch is "dashboards from the terminal,"
this is the difference between a button grid and something that looks designed.

Modal v2 matters for a different reason: `FileUpload` inside a modal means an agent can
*collect* a file from a human, not just send one. As of 2026-08-05 those uploads can also
be extension-filtered.

---

## 4. Tier B — new Discord API, not wrapped by discord.py

### B1. Guild message search — the big one

**Shipped for bots 2026-03-19.** Not present anywhere in discord.py 2.7.1 (grep for
`search` in `http.py` / `guild.py` returns nothing), so this needs a raw route via
`discord.http.Route`.

`GET /guilds/{guild_id}/messages/search`

| Param | Type | Meaning |
|---|---|---|
| `content` | string | search text, max 1024 chars |
| `author_id` | array | up to 1521 users |
| `author_type` | array | `user` / `bot` / `webhook` |
| `channel_id` | array | up to 500 channels |
| `mentions` | array | messages mentioning these users |
| `has` | array | `link`, `embed`, `file`, `image`, `video`, `sound`, `sticker`, `poll` |
| `attachment_extension` | array | match file types |
| `pinned` | boolean | pinned only |
| `sort_by` | string | `relevance` or `timestamp` |
| `sort_order` | string | asc / desc |
| `limit` | int | 1–25 |
| `offset` | int | 0–9975 |

Response: `GuildSearchResponse` — `messages` (nested arrays), `total_results`, `threads`,
`documents_indexed`.

**Why this matters so much for discli:** the current `message search`
(`src/discli/commands/message.py:312-401`) is a **client-side substring scan of a single
channel**, default `--scan 500`. It cannot search a whole guild, cannot filter by
attachment type or mentions, cannot sort by relevance, and quietly misses anything older
than the scan window. For an agent asked "find where we discussed the outage," that is the
difference between an answer and a wrong answer.

**Caveats to design around:**

- Discord may return **HTTP 202** when the guild's search index is not ready. The command
  must handle this explicitly rather than treating it as success.
- Documented as a **preview feature** subject to breaking change.
- Keep the existing scan implementation as a `--local` fallback for guilds where the index
  is unavailable.

### B2. Smaller raw-route items

- **Community invites with role assignment** (2026-01-13): `target_users_file` and
  `role_ids` let an invite pre-assign roles and restrict who may accept. Pairs naturally
  with A2.
- **`app_permissions` on resolved interaction channels** (2026-07-16): lets `serve` tell an
  agent what it is allowed to do in the channel an interaction came from, before it tries.
- **`flags_new` on Application** (2026-05-07): string-serialized flags past 32-bit. Only
  matters if discli starts reporting application flags.

---

## 5. Tier C — `discord.ext.tasks`

discli does not import `discord.ext.tasks` anywhere. `serve.py` hand-rolls its background
work: `serve.py:664-667` is a `while` loop around `asyncio.sleep(STREAM_EDIT_INTERVAL)` for
the streaming-edit flush.

What `ext.tasks` provides that the hand-rolled loop does not:

- `@tasks.loop(seconds=/minutes=/hours=/time=/count=)` — including **`time=`, which fires
  at wall-clock times with timezone support**, not just intervals.
- `reconnect=True` (default): automatic restart with **exponential backoff** on transient
  errors, using the same error set as `Client.connect()`.
- `add_exception_type()` / `remove_exception_type()` to control what triggers a restart.
- `@before_loop` (e.g. `await client.wait_until_ready()`), `@after_loop` (runs even on
  cancellation), and `@error` for unhandled exceptions.
- `change_interval()` to retune a running loop; `is_running()`, `failed()`,
  `is_being_cancelled()` for introspection.

**Two concrete uses:**

1. **Harden the existing flush loop.** Today an exception inside the stream-flush loop kills
   flushing for the life of the process, with no restart and no signal. `tasks.loop`
   restarts it and surfaces the failure via `@error`.

2. **A scheduling surface (new capability).** `time=` makes recurring jobs a first-class
   discli feature rather than something the caller must build:

   ```
   discli schedule add "daily-standup" --time 09:00 --tz America/New_York \
       --action 'message send #general "Standup in 5"'
   discli schedule list / remove / run-now
   ```

   Inside `serve`, this becomes a `schedule_add` / `schedule_list` JSONL action, so an agent
   can install a recurring job and then disconnect. Nothing in discli does this today, and
   it is the most-requested shape for "bot that posts every morning."

---

## 6. Proposed feature list, grouped by new command surface

Consolidated view of everything above, as commands.

**`discli invite`** — `list`, `create` (with `--max-age`, `--max-uses`, `--temporary`,
`--role` pre-assignment, `--activity <app-id>` for Activity-launch invites), `delete`,
`info`.

**`discli emoji`** — `list`, `upload`, `delete`, `rename`.

**`discli sticker`** — `list`, `upload`, `delete`.

**`discli soundboard`** — `list`, `upload`, `delete`, `play <sound> <voice-channel>`.

**`discli automod`** — `list`, `create` (keyword / spam / mention-spam / keyword-preset),
`edit`, `delete`, `enable`, `disable`.

**`discli schedule`** — `add`, `list`, `remove`, `run-now` (built on `ext.tasks`).

**`discli bot`** — `identity set --nick --avatar --banner --bio`, `presence set`, `whoami`
(token identity, guilds, resolved permission bitfield, intents).

**`discli command`** — `list`, `delete`, `sync` for globally registered application
commands. `serve` registers them; nothing can currently inspect or clean up orphans.

**Extensions to existing groups:**

| Group | Add |
|---|---|
| `server` | `edit` (name/icon/banner/verification/system-channel), `audit-log`, `onboarding show/edit`, `widget`, `template list/create/sync/delete`, `export`/`apply` |
| `member` | `nick`, `bulk-ban`, `prune --dry-run`, `search` |
| `message` | `pin`/`unpin` (parity with `serve`), `forward`, `search --guild` (native endpoint) |
| `role` | `--permissions` by name on `edit`, `move`, `members`, `--color-secondary`/`--holographic`, **switch counts to `role_member_counts()`** |
| `channel` | `move`, `clone`, `--type media`, forum tag management |
| `voice` | `move` (parity with `serve`), `status set` |
| `webhook` | `send`/`execute`, `edit` |
| `event` | `edit`, `start`, `end`, `subscribers` |
| `interact` | Components v2 layouts; Modal v2 checkbox/radio/file-upload |
| global | `--dry-run` on destructive commands |

---

## 7. Suggested ordering

**Wave 1 — SHIPPED 2026-08-25** (each ~1 module, existing `run_rest` pattern)
`role_member_counts()` fix · `message pin`/`unpin`/`pins` · `voice move` · `member nick` ·
`server audit-log` · `server edit` · `invite` group (incl. `--activity`) · `emoji` group ·
`webhook send`.

Notes from the build:

- `voice move` moves a **member** between voice channels over plain HTTP. `serve`'s
  `voice_move` action moves the *bot's own* connection, which has no meaning in a
  one-shot command that connects and disconnects in the same breath — so this is a
  sibling of that action, not a port of it.
- `message pins` was added alongside pin/unpin; without a way to list pins the pair is
  only half usable.
- `webhook send` and `webhook delete` now share a `_resolve_webhook()` helper that accepts
  an ID **or** a name, replacing the inline lookup that `delete` used to carry.
- Still open from §2.2: nothing yet verifies the bot actually holds `PIN_MESSAGES` or
  `CREATE_GUILD_EXPRESSIONS`. `emoji upload` and `message pin` will fail at the API with a
  403 rather than being caught by `doctor`. That is Wave 2.

**Wave 2 — SHIPPED 2026-08-25** (ahead of the 2026-11-16 deadline)
Channel visibility disclosure in `channel list` / `server info` / `serve`. Permission
bitfield check in `doctor` covering `PIN_MESSAGES`, `BYPASS_SLOWMODE`,
`CREATE_GUILD_EXPRESSIONS`, `CREATE_EVENTS`.

Notes from the build:

- **The disclosure goes to stderr, not stdout.** `channel list --json` returns a bare JSON
  array, so there is no place to add a top-level `visible_only` key without breaking every
  existing consumer. stderr carries the note to humans and to anything that captures it,
  while `--json` stdout stays byte-identical to before. A test pins that contract.
- `serve`'s `channel_list` sets `visible_only: true` **in-band** instead — the JSONL
  protocol has no stderr equivalent, and its response is already an object, so adding a
  key is safe there.
- **The permission check only fires on a real regression:** the bot holds the legacy bit
  (`manage_messages`) but not the split-out one (`pin_messages`). A bot that never had
  `manage_messages` is not flagged, because it never lost anything. This keeps the check
  silent for read-only bots instead of drowning them in warnings.
- Missing permissions that are *not* regressions are reported but never fail the run —
  doctor cannot know which commands you intended to use.
- `doctor` stays fully offline unless `--server` is passed. That is the only networked
  check in the command, and the default run prints a `[--]` line pointing at it.
- Not covered: `serve` has no test harness in this repo, so its one-line `visible_only`
  addition is verified by reading, not by a test.

**Wave 3 — SHIPPED 2026-08-25**
Native guild message search · `ext.tasks` hardening of the flush loop · `discli schedule`.

Notes from the build:

- Shipped as a **separate command**, `message search-server`, rather than a `--guild` flag on
  `message search`. That command takes its channel as a required positional argument, so a
  flag would have meant either an optional positional or a breaking signature change. The
  two searches also answer different questions, so the local scan stays as the documented
  fallback for unindexed guilds — which is the `--local` idea from the original plan, just
  spelled as the command that already existed.
- The 202 case matters more than it looks. discord.py returns 2xx bodies as-is, so an
  unindexed guild comes back as a dict with no `messages` key. Rendering that as "no results"
  would be a **wrong answer**, not a slow one, so it raises with a pointer to the local scan.
- `parse_action()` in the scheduler lexes with `shlex(punctuation_chars=True)`. Plain
  `shlex.split()` folds `;` into its neighbour (`list;`), so `server list; rm -rf /` was
  accepted by the operator check and only rejected later by the command-tree walk, with a
  confusing message. No shell is ever involved, so nothing was executable either way — but
  the error should say what is actually wrong.
- Backticks and `$` are deliberately **not** treated as shell syntax. Rejecting them would
  break `message send <ch> "run <backtick>npm test<backtick>"`, and with no shell involved
  they cannot do anything. `$(...)` is still caught via its parenthesis.
- Scheduled actions run through `asyncio.to_thread`: discli commands call `asyncio.run()`
  internally, which raises if called from the scheduler's own running loop.
- `tzdata` became a Windows-only dependency. Windows ships no IANA tz database, so
  `ZoneInfo("America/New_York")` raises there — `--tz` would have been broken on the primary
  development platform.
- **A test in this wave initially made live Discord API calls.** `discli.cli` does
  `from discli.config import load_config` at import time, so patching
  `discli.config.load_config` was a no-op and the developer's real token was picked up from
  `~/.discli/config.json`. It passed locally and would have failed in CI. `tests/conftest.py`
  now carries an autouse `no_network` fixture that patches `discord.http.HTTPClient` so this
  cannot recur silently.
- Only the stream-flush loop moved to `ext.tasks`. `_typing_loop` was left alone: it holds
  `async with ch.typing()` open around a sleep, and discord.py's own `Typing` context manager
  already re-sends the indicator: restructuring it into a repeating callback would be a
  regression in clarity, not a hardening.

**Wave 4 — needs design first** (all that remains)
Components v2 / Modal v2 rework of `interact_engine.py` · server-as-code (`server export` /
`diff` / `apply`) · automod · onboarding.

---

## 8. Sources

- [discord.py on PyPI](https://pypi.org/project/discord.py/) — latest version and release date
- [discord.py changelog](https://discordpy.readthedocs.io/en/latest/whats_new.html) — per-version features
- [discord.ext.tasks documentation](https://discordpy.readthedocs.io/en/latest/ext/tasks/index.html)
- [Discord developer change log](https://docs.discord.com/developers/change-log) — API changes and deadlines
- [Discord search API for bots — current state](https://gist.github.com/derwells/0575f28ba87fda8ec7d239b649e1c445) — search endpoint parameters
- [advaith, announcing bot access to Search Guild Messages](https://x.com/advaithj1/status/2035139632405651947)

Local verification: `src/discli/` grep for each API name; `.venv/Lib/site-packages/discord/`
for availability in the pinned version.

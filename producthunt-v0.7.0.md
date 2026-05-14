# Product Hunt Forum Post — discli v0.7.0

## Title

discli v0.7.0 — Your Discord bot now has buttons, modals, and an AI brain

## Body

Hey makers! Big update for discli — the Discord CLI for AI agents.

### What's new in v0.7.0

We went from 35 commands to **63 commands** and from 31 serve actions to **54 actions**. Here's the highlight reel:

**Interactive Components** — Buttons, select menus (string, user, role, channel pickers), and modal forms. All via the serve JSONL protocol. Your bot can now send a dropdown, collect a form response, or disable a button after it's clicked.

**Rich Embeds** — Full embed support with color, footer, image, thumbnail, author, and repeatable fields. Both CLI (`--embed-color ff0000 --embed-field "Key::Value::true"`) and serve mode (JSON).

**AI Agent** — A single Python script (`ai_serve_agent.py`) that wires Claude Agent SDK to discli serve. Claude has full Discord control — it runs CLI commands for messages/channels/roles and outputs component blocks for buttons/selects/modals. ~550 lines for an agent that can do literally anything on Discord.

**New command groups:**
- `discli webhook list/create/delete`
- `discli event list/create/delete` (guild scheduled events)
- `discli member timeout` (modern Discord moderation)
- `discli channel edit/forum-post/set-permissions`
- `discli thread archive/rename/add-member/remove-member`
- `discli role edit`, `discli reaction users`, `discli poll results/end`

**7 Claude Code Skills** — Install with `npx skills add DevRohit06/discli@discord-bot`. Skills for bot scaffolding, AI agents, moderation, support bots, welcome flows, logging, and slash commands.

**Edge case hardening** — Hex color validation, timeout duration limits, permission name validation, forum channels in listings, voice state null guards.

**Docs overhaul** — 16 pages updated, new Components & Modals guide, updated all references and examples.

**Install:**
```
pip install discord-cli-agent
```

**Try the AI agent:**
```
pip install discord-cli-agent claude-agent-sdk
discli config set token YOUR_BOT_TOKEN
python examples/ai_serve_agent.py
```

Then just @mention your bot:
```
@bot send 3 buttons: Accept, Decline, Maybe
@bot create a poll: "Best language?" with Python, Rust, Go
@bot send a feedback form with Name and Message fields
@bot create a channel called announcements
```

GitHub: https://github.com/DevRohit06/discli
Release: https://github.com/DevRohit06/discli/releases/tag/v0.7.0
Docs: https://discli.dev

Would love to hear what you build with it!

---

## Twitter/X — Short Version

discli v0.7.0 is out 🚀

Discord CLI for AI agents — now with buttons, select menus, modals, rich embeds, and a full AI agent powered by Claude.

63 commands. 54 serve actions. 7 Claude Code skills.

One Python script gives Claude full Discord control: messages, embeds, buttons, channels, roles, polls, webhooks, events.

pip install discord-cli-agent

github.com/DevRohit06/discli

---

## Twitter/X — Thread Version

**Tweet 1:**
discli v0.7.0 — Discord CLI for AI agents 🚀

Went from 35 → 63 commands. Your AI agent can now send buttons, select menus, modal forms, and rich embeds on Discord.

Here's what changed 🧵

**Tweet 2:**
Interactive components in serve mode:
- Buttons (primary, success, danger, link, disabled)
- Select menus (string, user, role, channel pickers)
- Modal forms (short + long text inputs)
- Ephemeral responses ("only you can see this")

All via JSONL protocol.

**Tweet 3:**
The AI agent (`ai_serve_agent.py`) wires Claude Agent SDK to discli serve.

Claude runs CLI commands for messages/channels/roles AND outputs component blocks for buttons/selects/modals.

~550 lines. Full Discord control. Just @mention the bot.

**Tweet 4:**
New commands:
- webhook list/create/delete
- event list/create/delete
- member timeout
- channel edit/forum-post/set-permissions
- thread archive/rename/add-member
- role edit, reaction users, poll results

**Tweet 5:**
7 Claude Code skills on skills.sh:

npx skills add DevRohit06/discli@discord-bot
npx skills add DevRohit06/discli@discord-agent
npx skills add DevRohit06/discli@discord-moderation
npx skills add DevRohit06/discli@discord-support-bot
npx skills add DevRohit06/discli@discord-welcome

**Tweet 6:**
Try it:

pip install discord-cli-agent claude-agent-sdk
discli config set token YOUR_TOKEN
python examples/ai_serve_agent.py

Then in Discord:
@bot send 3 buttons: Accept, Decline, Maybe
@bot create a poll: Best language?
@bot send a feedback form

github.com/DevRohit06/discli

---

## LinkedIn Version

Shipped discli v0.7.0 — the Discord CLI for AI agents.

This release nearly doubles the command set (35 → 63 commands) and adds what developers have been asking for: interactive message components.

What's new:
• Buttons, select menus, and modal forms via the serve JSONL protocol
• Rich embeds with full customization (color, images, fields, footer)
• An all-in-one AI agent that gives Claude complete Discord control in ~550 lines
• Webhook management, scheduled events, member timeouts, forum channels
• 7 installable Claude Code skills for common bot patterns
• 15 edge case fixes for production robustness

The AI agent architecture is what I'm most excited about. Claude runs discli CLI commands for standard operations and outputs structured component blocks for interactive elements. One @mention, and it can create channels, send embeds with buttons, open modal forms, manage roles — anything.

Open source. MIT licensed. Works with Claude, OpenAI, or any LLM.

pip install discord-cli-agent
https://github.com/DevRohit06/discli

---

## Discord/Community Announcement

**@everyone**

**discli v0.7.0 is here!** 🎉

Massive update — nearly doubled the command set and added interactive components.

**Highlights:**
🔘 Buttons, select menus, modal forms
🎨 Full rich embeds (color, images, fields, footer)
🤖 AI agent with complete Discord control (~550 lines)
🔗 Webhook management
📅 Guild scheduled events
⏱️ Member timeout (modern moderation)
📋 7 Claude Code skills

**Quick start:**
```
pip install discord-cli-agent==0.7.0
```

**Full changelog:** https://github.com/DevRohit06/discli/releases/tag/v0.7.0
**Docs:** https://discli.dev

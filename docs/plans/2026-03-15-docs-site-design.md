# discli Documentation Site Design

**Date:** 2026-03-15
**Status:** Approved
**Framework:** Lito (Astro-based, https://lito.rohitk06.in)
**Location:** `docs/` inside the discli repo

## Overview

Full Lito-powered documentation site for discli covering getting started, guides, use cases, architecture, comparisons, troubleshooting, and reference. Includes a custom HTML landing page. Target audiences: AI/LLM developers, Discord bot developers, and DevOps/automation engineers.

## Site Structure (27 pages + landing)

```
docs/
├── lito.config.json
├── src/
│   └── content/
│       └── docs/
│           ├── index.mdx                        # Custom HTML landing page
│           │
│           ├── getting-started/
│           │   ├── installation.mdx             # pip, curl, PowerShell, source
│           │   ├── quickstart.mdx               # First message in 2 minutes
│           │   ├── configuration.mdx            # Token setup, config file, env vars
│           │   └── your-first-bot.mdx           # Zero to working agent bot
│           │
│           ├── guides/
│           │   ├── cli-usage.mdx                # Day-to-day CLI for humans
│           │   ├── building-agents.mdx          # Flagship: progressive autonomy guide
│           │   ├── serve-mode.mdx               # Deep dive into discli serve + JSONL
│           │   ├── streaming-responses.mdx      # Token-by-token AI streaming
│           │   ├── slash-commands.mdx           # Registration, handling, deferred responses
│           │   ├── security-permissions.mdx     # Profiles, audit, rate limiting
│           │   └── scripting-automation.mdx     # Bash, cron, CI pipelines
│           │
│           ├── use-cases/
│           │   ├── ai-support-agent.mdx         # Claude/GPT support bot walkthrough
│           │   ├── moderation-bot.mdx           # Spam detection, warnings, kicks
│           │   ├── thread-based-support.mdx     # Thread-per-request pattern
│           │   ├── channel-logger.mdx           # Event logging to files
│           │   └── ci-notifications.mdx         # GitHub Actions → Discord alerts
│           │
│           ├── architecture/
│           │   ├── overview.mdx                 # System design with Mermaid diagrams
│           │   ├── serve-protocol.mdx           # JSONL stdin/stdout spec
│           │   ├── security-model.mdx           # Permission enforcement internals
│           │   └── token-resolution.mdx         # Flag → env → config lookup
│           │
│           ├── comparisons/
│           │   ├── vs-discord-libraries.mdx     # vs discord.py, discord.js
│           │   ├── vs-cli-tools.mdx             # vs discrawl, other CLIs
│           │   ├── vs-hosted-bots.mdx           # vs MEE6, Combot
│           │   └── why-discli.mdx               # Summary: when to choose discli
│           │
│           ├── troubleshooting/
│           │   ├── common-issues.mdx            # Token errors, permission denied, rate limits
│           │   ├── windows-quirks.mdx           # stdin threading, paths
│           │   ├── edge-cases.mdx               # Large guilds, intents, cache, expired tokens
│           │   └── faq.mdx                      # Frequently asked questions
│           │
│           └── reference/
│               ├── cli-commands.mdx             # Full command reference with all flags
│               ├── serve-actions.mdx            # All 25+ actions with JSON examples
│               ├── serve-events.mdx             # All event payloads with schemas
│               └── permission-profiles.mdx      # Profile definitions, customization
```

## Custom Landing Page (8 sections)

### 1. Hero
- Headline: "Discord, meet your AI agent."
- Subtitle: "The CLI that turns Discord into a programmable platform. Build autonomous agents, automate servers, and script everything — from your terminal."
- Animated terminal preview showing `discli serve` session
- CTAs: "Get Started" → quickstart, "View on GitHub"
- `pip install discord-cli-agent` copy-to-clipboard badge

### 2. Three Pillars (feature cards)
- **CLI-First** — "Every Discord action is a single command. Pipe, script, automate."
- **Agent-Ready** — "Persistent JSONL protocol. Your AI agent talks to Discord in real-time."
- **Secure by Default** — "Permission profiles, audit logs, rate limiting. Built for autonomous access."

### 3. "See It In Action" (side-by-side split)
- Left: Terminal with `discli serve` stdin/stdout JSONL
- Right: Discord UI showing bot messages appearing
- Animated/stepped flow: event in → agent processes → action out → Discord updates

### 4. Progressive Autonomy Showcase (tabs/horizontal scroll)
- 5 cards for autonomy levels: Reactive → Context-Aware → Proactive → Multi-Action → Full Autonomous
- Each: title, 3-line description, lines-of-code count
- Links to Building Agents guide

### 5. Comparison Strip
- "Why not just use..." row: discord.py, discord.js, MEE6, discrawl
- One-liner differentiator per tool
- CTA to full comparisons

### 6. Use Case Grid (2x3)
- AI Support Agent, Moderation Bot, Thread Support, Channel Logger, CI Notifications, Custom
- Icon, title, one-liner, link to use case page

### 7. Code Preview — "From zero to agent in 15 lines"
- Full working example with syntax highlighting
- Copy button, link to "Your First Bot"

### 8. Footer
- Quick links: Docs, GitHub, PyPI, Contributing
- "Built by Rohit" credit, MIT license badge

## Theme & Configuration

- **Primary color:** `#5865F2` (Discord blurple)
- **Dark mode** default, light mode available
- **Font:** Clean mono for code, system sans-serif for body
- **Search:** Pagefind (Lito built-in, client-side)

## Content Strategy

### Audience-specific guides
| Section | AI Developers | Bot Developers | DevOps/Automation |
|---------|:---:|:---:|:---:|
| Getting Started | x | x | x |
| CLI Usage | | | x |
| Building Agents | x | x | |
| Serve Mode | x | x | |
| Streaming | x | | |
| Slash Commands | x | x | |
| Security | x | x | x |
| Scripting | | | x |
| Use Cases | x | x | x |

### Building Agents — Progressive Autonomy Levels

**Level 1: Reactive Bot** — Responds to keywords. No state. ~20 lines.

**Level 2: Context-Aware Agent** — Reads message history via `message_list` before responding.

**Level 3: Proactive Agent** — Creates threads, manages conversations, streams responses. Detects intent.

**Level 4: Multi-Action Agent** — Combines actions autonomously: assigns roles, sends DMs, reacts, manages channels.

**Level 5: Full Autonomous Agent** — Uses permission profiles for safety, audit logging for accountability, handles edge cases gracefully.

Each level: full working code, conceptual explanation, edge cases, "what could go wrong" callout.

### Comparison Format
Each page: what it is → what it's good at → where discli differs → side-by-side table → when to use which.

| vs | Key Differentiator |
|---|---|
| discord.py/js | No boilerplate. CLI + serve = 10x less code for agent use cases |
| discrawl | discrawl reads, discli reads AND writes. Full bidirectional control |
| MEE6/Combot | Self-hosted, no vendor lock-in, full AI integration, programmable |
| Client mods | Bot-side vs client-side. Server automation, not UI tweaks |

### Use Case Format
Each page: problem → solution → full code → how it works → edge cases → extending it.

### Troubleshooting Sources
- Real GitHub issues (as they exist)
- Anticipated issues from codebase: Windows stdin threading, token resolution failures, missing Discord intents, interaction token expiry (15 min), rate limit 429s, large guild cache misses, permission check failures when bot lacks guild member intent

# discli Documentation Site Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a complete Lito-powered documentation site at `docs/` covering getting started, guides, use cases, architecture, comparisons, troubleshooting, and reference — with a custom landing page.

**Architecture:** Lito (Astro-based) docs framework initialized in `docs/`. Content lives as `.mdx` files in `docs/` root with folder-based routing. Custom landing page uses Lito's `_landing/` folder with HTML/CSS/JS. Config via `docs-config.json`.

**Tech Stack:** Lito (`npx @litodocs/cli`), MDX, Tailwind CSS, Pagefind search, Mermaid diagrams

---

### Task 1: Initialize Lito Project & Configure

**Files:**
- Create: `docs/docs-config.json`
- Create: `docs/index.mdx`

**Step 1: Initialize Lito in the docs folder**

Run: `cd docs && npx @litodocs/cli dev -i . --dry-run` to verify Lito is available. If it prompts to install, accept.

Actually, Lito works by pointing at a folder with `docs-config.json` + markdown. Create the config:

**Step 2: Create `docs/docs-config.json`**

```json
{
  "metadata": {
    "name": "discli",
    "description": "Discord CLI for AI Agents & Humans — documentation",
    "url": "https://discli.dev"
  },
  "branding": {
    "favicon": "/favicon.svg",
    "colors": {
      "primary": "#5865F2"
    },
    "fonts": {
      "heading": "Inter",
      "body": "Inter",
      "code": "Fira Code"
    }
  },
  "navigation": {
    "navbar": {
      "links": [
        { "label": "GitHub", "href": "https://github.com/DevRohit06/discli" },
        { "label": "PyPI", "href": "https://pypi.org/project/discord-cli-agent/" }
      ],
      "cta": { "label": "Get Started", "href": "/getting-started/installation" }
    },
    "sidebar": [
      {
        "label": "Getting Started",
        "items": [
          { "label": "Installation", "href": "/getting-started/installation" },
          { "label": "Quickstart", "href": "/getting-started/quickstart" },
          { "label": "Configuration", "href": "/getting-started/configuration" },
          { "label": "Your First Bot", "href": "/getting-started/your-first-bot" }
        ]
      },
      {
        "label": "Guides",
        "items": [
          { "label": "CLI Usage", "href": "/guides/cli-usage" },
          { "label": "Building Agents", "href": "/guides/building-agents" },
          { "label": "Serve Mode", "href": "/guides/serve-mode" },
          { "label": "Streaming Responses", "href": "/guides/streaming-responses" },
          { "label": "Slash Commands", "href": "/guides/slash-commands" },
          { "label": "Security & Permissions", "href": "/guides/security-permissions" },
          { "label": "Scripting & Automation", "href": "/guides/scripting-automation" }
        ]
      },
      {
        "label": "Use Cases",
        "items": [
          { "label": "AI Support Agent", "href": "/use-cases/ai-support-agent" },
          { "label": "Moderation Bot", "href": "/use-cases/moderation-bot" },
          { "label": "Thread-Based Support", "href": "/use-cases/thread-based-support" },
          { "label": "Channel Logger", "href": "/use-cases/channel-logger" },
          { "label": "CI Notifications", "href": "/use-cases/ci-notifications" }
        ]
      },
      {
        "label": "Architecture",
        "items": [
          { "label": "Overview", "href": "/architecture/overview" },
          { "label": "Serve Protocol", "href": "/architecture/serve-protocol" },
          { "label": "Security Model", "href": "/architecture/security-model" },
          { "label": "Token Resolution", "href": "/architecture/token-resolution" }
        ]
      },
      {
        "label": "Comparisons",
        "items": [
          { "label": "vs Discord Libraries", "href": "/comparisons/vs-discord-libraries" },
          { "label": "vs CLI Tools", "href": "/comparisons/vs-cli-tools" },
          { "label": "vs Hosted Bots", "href": "/comparisons/vs-hosted-bots" },
          { "label": "Why discli?", "href": "/comparisons/why-discli" }
        ]
      },
      {
        "label": "Troubleshooting",
        "items": [
          { "label": "Common Issues", "href": "/troubleshooting/common-issues" },
          { "label": "Windows Quirks", "href": "/troubleshooting/windows-quirks" },
          { "label": "Edge Cases", "href": "/troubleshooting/edge-cases" },
          { "label": "FAQ", "href": "/troubleshooting/faq" }
        ]
      },
      {
        "label": "Reference",
        "items": [
          { "label": "CLI Commands", "href": "/reference/cli-commands" },
          { "label": "Serve Actions", "href": "/reference/serve-actions" },
          { "label": "Serve Events", "href": "/reference/serve-events" },
          { "label": "Permission Profiles", "href": "/reference/permission-profiles" }
        ]
      }
    ]
  },
  "landing": {
    "enabled": true,
    "type": "custom",
    "source": "_landing",
    "injectNav": true,
    "injectFooter": true
  },
  "footer": {
    "layout": "full",
    "tagline": "Discord CLI for AI Agents & Humans",
    "copyright": "© {year} Rohit Kumar. MIT License.",
    "showBranding": true,
    "socials": {
      "github": "https://github.com/DevRohit06/discli"
    },
    "links": [
      {
        "title": "Docs",
        "items": [
          { "label": "Getting Started", "href": "/getting-started/installation" },
          { "label": "Guides", "href": "/guides/cli-usage" },
          { "label": "Reference", "href": "/reference/cli-commands" }
        ]
      },
      {
        "title": "Community",
        "items": [
          { "label": "GitHub", "href": "https://github.com/DevRohit06/discli" },
          { "label": "PyPI", "href": "https://pypi.org/project/discord-cli-agent/" },
          { "label": "Contributing", "href": "https://github.com/DevRohit06/discli/blob/main/CONTRIBUTING.md" }
        ]
      }
    ]
  },
  "theme": {
    "mode": "auto",
    "defaultDark": true
  },
  "search": {
    "enabled": true,
    "provider": "local",
    "placeholder": "Search docs..."
  },
  "integrations": {
    "editPage": {
      "enabled": true,
      "pattern": "https://github.com/DevRohit06/discli/edit/main/docs/{path}"
    },
    "lastUpdated": {
      "enabled": true
    }
  }
}
```

**Step 3: Create placeholder `docs/index.mdx`**

```mdx
---
title: discli Documentation
description: Discord CLI for AI Agents & Humans
---

# discli

Discord CLI for AI Agents & Humans.
```

**Step 4: Verify Lito runs**

Run: `npx @litodocs/cli dev -i ./docs`
Expected: Dev server starts at http://localhost:4321, shows the placeholder page.

**Step 5: Commit**

```bash
git add docs/docs-config.json docs/index.mdx
git commit -m "docs: initialize Lito docs site with config and sidebar"
```

---

### Task 2: Custom Landing Page

**Files:**
- Create: `docs/_landing/index.html`
- Create: `docs/_landing/styles.css`
- Create: `docs/_landing/script.js`

**Step 1: Create `docs/_landing/index.html`**

Build all 8 sections from the design doc:

```html
<div class="landing">
  <!-- Section 1: Hero -->
  <section class="hero">
    <div class="hero-content">
      <h1>Discord, meet your AI agent.</h1>
      <p class="hero-subtitle">
        The CLI that turns Discord into a programmable platform.
        Build autonomous agents, automate servers, and script everything — from your terminal.
      </p>
      <div class="hero-install">
        <code id="install-cmd">pip install discord-cli-agent</code>
        <button onclick="copyInstall()" class="copy-btn" title="Copy">📋</button>
      </div>
      <div class="hero-cta">
        <a href="/getting-started/quickstart" class="btn btn-primary">Get Started</a>
        <a href="https://github.com/DevRohit06/discli" class="btn btn-secondary">View on GitHub</a>
      </div>
    </div>
    <div class="hero-terminal">
      <div class="terminal-header">
        <span class="terminal-dot red"></span>
        <span class="terminal-dot yellow"></span>
        <span class="terminal-dot green"></span>
        <span class="terminal-title">discli serve</span>
      </div>
      <pre class="terminal-body"><code id="terminal-output"></code></pre>
    </div>
  </section>

  <!-- Section 2: Three Pillars -->
  <section class="pillars">
    <div class="pillar">
      <div class="pillar-icon">⌨️</div>
      <h3>CLI-First</h3>
      <p>Every Discord action is a single command. Pipe, script, automate.</p>
    </div>
    <div class="pillar">
      <div class="pillar-icon">🤖</div>
      <h3>Agent-Ready</h3>
      <p>Persistent JSONL protocol. Your AI agent talks to Discord in real-time.</p>
    </div>
    <div class="pillar">
      <div class="pillar-icon">🔒</div>
      <h3>Secure by Default</h3>
      <p>Permission profiles, audit logs, rate limiting. Built for autonomous access.</p>
    </div>
  </section>

  <!-- Section 3: See It In Action -->
  <section class="demo">
    <h2>See it in action</h2>
    <div class="demo-split">
      <div class="demo-terminal">
        <div class="terminal-header">
          <span class="terminal-dot red"></span>
          <span class="terminal-dot yellow"></span>
          <span class="terminal-dot green"></span>
          <span class="terminal-title">Terminal — stdin/stdout</span>
        </div>
        <pre class="terminal-body"><code><span class="event">← {"event":"message","author":"alice","content":"@bot help","channel_id":"123"}</span>

<span class="action">→ {"action":"typing_start","channel_id":"123"}</span>
<span class="action">→ {"action":"reply","channel_id":"123","message_id":"456","content":"Hi! How can I help?"}</span>

<span class="event">← {"event":"response","status":"ok","message_id":"789"}</span></code></pre>
      </div>
      <div class="demo-discord">
        <div class="discord-header"># general</div>
        <div class="discord-messages">
          <div class="discord-msg">
            <div class="discord-avatar alice">A</div>
            <div>
              <span class="discord-author">alice</span>
              <span class="discord-time">Today at 3:42 PM</span>
              <p>@bot help</p>
            </div>
          </div>
          <div class="discord-msg bot-msg">
            <div class="discord-avatar bot">B</div>
            <div>
              <span class="discord-author bot-name">discli-bot</span>
              <span class="discord-badge">BOT</span>
              <span class="discord-time">Today at 3:42 PM</span>
              <p>Hi! How can I help?</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- Section 4: Progressive Autonomy -->
  <section class="autonomy">
    <h2>From reactive to fully autonomous</h2>
    <p class="section-subtitle">Build agents that grow in capability — at your pace.</p>
    <div class="autonomy-levels">
      <div class="level-card" data-level="1">
        <div class="level-number">1</div>
        <h3>Reactive Bot</h3>
        <p>Responds to keywords. No state, no context. The simplest starting point.</p>
        <span class="level-loc">~20 lines</span>
      </div>
      <div class="level-card" data-level="2">
        <div class="level-number">2</div>
        <h3>Context-Aware</h3>
        <p>Reads message history before responding. Informed replies with conversation context.</p>
        <span class="level-loc">~35 lines</span>
      </div>
      <div class="level-card" data-level="3">
        <div class="level-number">3</div>
        <h3>Proactive Agent</h3>
        <p>Creates threads, streams responses, detects intent without explicit commands.</p>
        <span class="level-loc">~60 lines</span>
      </div>
      <div class="level-card" data-level="4">
        <div class="level-number">4</div>
        <h3>Multi-Action</h3>
        <p>Assigns roles, sends DMs, reacts, manages channels — all from its own reasoning.</p>
        <span class="level-loc">~90 lines</span>
      </div>
      <div class="level-card" data-level="5">
        <div class="level-number">5</div>
        <h3>Full Autonomous</h3>
        <p>Permission-bounded, audit-logged, graceful degradation. Production-ready agent.</p>
        <span class="level-loc">~120 lines</span>
      </div>
    </div>
    <a href="/guides/building-agents" class="btn btn-primary">Build your first agent →</a>
  </section>

  <!-- Section 5: Comparison Strip -->
  <section class="comparisons">
    <h2>Why not just use...</h2>
    <div class="comparison-row">
      <div class="comparison-item">
        <strong>discord.py</strong>
        <p>50+ lines of boilerplate before your first reply. discli: zero.</p>
      </div>
      <div class="comparison-item">
        <strong>discord.js</strong>
        <p>Node runtime, package.json, event handlers. discli: one subprocess.</p>
      </div>
      <div class="comparison-item">
        <strong>MEE6</strong>
        <p>Vendor lock-in, no AI integration, limited customization. discli: fully programmable.</p>
      </div>
      <div class="comparison-item">
        <strong>discrawl</strong>
        <p>Read-only scraping. discli: read AND write. Full bidirectional control.</p>
      </div>
    </div>
    <a href="/comparisons/why-discli" class="btn btn-secondary">See full comparisons →</a>
  </section>

  <!-- Section 6: Use Case Grid -->
  <section class="use-cases">
    <h2>What will you build?</h2>
    <div class="use-case-grid">
      <a href="/use-cases/ai-support-agent" class="use-case-card">
        <span class="use-case-icon">💬</span>
        <h3>AI Support Agent</h3>
        <p>Claude-powered bot that answers questions with context.</p>
      </a>
      <a href="/use-cases/moderation-bot" class="use-case-card">
        <span class="use-case-icon">🛡️</span>
        <h3>Moderation Bot</h3>
        <p>Auto-detect spam, warn users, kick repeat offenders.</p>
      </a>
      <a href="/use-cases/thread-based-support" class="use-case-card">
        <span class="use-case-icon">🧵</span>
        <h3>Thread Support</h3>
        <p>Auto-create threads per request, isolated conversations.</p>
      </a>
      <a href="/use-cases/channel-logger" class="use-case-card">
        <span class="use-case-icon">📝</span>
        <h3>Channel Logger</h3>
        <p>Stream events to JSONL files. One-liner setup.</p>
      </a>
      <a href="/use-cases/ci-notifications" class="use-case-card">
        <span class="use-case-icon">🚀</span>
        <h3>CI Notifications</h3>
        <p>GitHub Actions → Discord. Build status in your channel.</p>
      </a>
      <a href="/guides/building-agents" class="use-case-card custom">
        <span class="use-case-icon">✨</span>
        <h3>Your Idea</h3>
        <p>Build anything. discli is the bridge.</p>
      </a>
    </div>
  </section>

  <!-- Section 7: Code Preview -->
  <section class="code-preview">
    <h2>From zero to agent in 15 lines</h2>
    <pre class="code-block"><code class="language-python">import json, subprocess

proc = subprocess.Popen(
    ["discli", "--json", "serve"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
)

for line in proc.stdout:
    event = json.loads(line)
    if event.get("event") == "message" and not event.get("is_bot"):
        cmd = json.dumps({
            "action": "reply",
            "channel_id": event["channel_id"],
            "message_id": event["message_id"],
            "content": f"You said: {event['content']}",
        })
        proc.stdin.write(cmd + "\n")
        proc.stdin.flush()</code></pre>
    <a href="/getting-started/your-first-bot" class="btn btn-primary">Full walkthrough →</a>
  </section>
</div>
```

**Step 2: Create `docs/_landing/styles.css`**

Style the landing page with Discord blurple theme, dark background, terminal animations, Discord message mockup, card grid layouts, responsive breakpoints. Key design tokens:

```css
:root {
  --blurple: #5865F2;
  --blurple-dark: #4752C4;
  --bg-dark: #0b0d13;
  --bg-card: #111318;
  --bg-terminal: #1a1b26;
  --text-primary: #ffffff;
  --text-secondary: #b5bac1;
  --discord-bg: #313338;
  --discord-msg-hover: #2e3035;
  --green: #57f287;
  --yellow: #fee75c;
  --red: #ed4245;
}

/* Full CSS for all 8 sections — responsive grid layouts,
   terminal mockup styling, Discord message UI recreation,
   card hover effects, animated terminal output, code block styling.
   Use Tailwind utility approach where Lito injects Tailwind. */
```

Write complete CSS covering:
- Hero: split layout (text left, terminal right), responsive stack on mobile
- Terminal mockup: dark bg, colored dots, monospace font, line-by-line animation
- Discord mockup: recreate Discord message list appearance
- Pillars: 3-column grid, icon + heading + text cards
- Autonomy levels: horizontal scroll on mobile, 5-column grid on desktop
- Comparison strip: 4-column row with hover highlight
- Use case grid: 2x3 responsive grid with hover card lift
- Code preview: centered max-width code block with syntax colors
- All sections: consistent padding, max-width container, section spacing

**Step 3: Create `docs/_landing/script.js`**

```javascript
// Copy install command
function copyInstall() {
  navigator.clipboard.writeText('pip install discord-cli-agent');
  const btn = document.querySelector('.copy-btn');
  btn.textContent = '✓';
  setTimeout(() => btn.textContent = '📋', 2000);
}

// Animated terminal output in hero
const terminalLines = [
  { text: '$ discli serve --status online', delay: 0, cls: 'cmd' },
  { text: '{"event":"ready","bot_name":"my-agent","guilds":3}', delay: 800, cls: 'event' },
  { text: '{"event":"message","author":"alice","content":"@bot what is discli?","channel_id":"123456"}', delay: 2000, cls: 'event' },
  { text: '→ {"action":"typing_start","channel_id":"123456"}', delay: 3000, cls: 'action' },
  { text: '→ {"action":"reply","channel_id":"123456","message_id":"789","content":"discli is a Discord CLI for AI agents!"}', delay: 4000, cls: 'action' },
  { text: '{"event":"response","status":"ok","req_id":"1"}', delay: 5000, cls: 'event' },
];

function animateTerminal() {
  const output = document.getElementById('terminal-output');
  if (!output) return;
  output.innerHTML = '';
  terminalLines.forEach(({ text, delay, cls }) => {
    setTimeout(() => {
      const line = document.createElement('div');
      line.className = cls;
      line.textContent = text;
      output.appendChild(line);
    }, delay);
  });
  // Loop
  setTimeout(animateTerminal, 8000);
}

document.addEventListener('DOMContentLoaded', animateTerminal);
```

**Step 4: Verify landing page renders**

Run: `npx @litodocs/cli dev -i ./docs`
Expected: Landing page shows at root with all 8 sections, terminal animation plays.

**Step 5: Commit**

```bash
git add docs/_landing/
git commit -m "docs: add custom landing page with terminal animation and Discord mockup"
```

---

### Task 3: Getting Started Section (4 pages)

**Files:**
- Create: `docs/getting-started/installation.mdx`
- Create: `docs/getting-started/quickstart.mdx`
- Create: `docs/getting-started/configuration.mdx`
- Create: `docs/getting-started/your-first-bot.mdx`

**Step 1: Create `docs/getting-started/installation.mdx`**

```mdx
---
title: Installation
description: Install discli on macOS, Linux, or Windows
---

# Installation

<Tabs>
  <Tab title="pip (recommended)">
    ```bash
    pip install discord-cli-agent
    ```
  </Tab>
  <Tab title="macOS / Linux">
    ```bash
    curl -fsSL https://raw.githubusercontent.com/DevRohit06/discli/main/installers/install.sh | bash
    ```
  </Tab>
  <Tab title="Windows (PowerShell)">
    ```powershell
    irm https://raw.githubusercontent.com/DevRohit06/discli/main/installers/install.ps1 | iex
    ```
  </Tab>
  <Tab title="From Source">
    ```bash
    git clone https://github.com/DevRohit06/discli.git
    cd discli
    pip install -e ".[dev]"
    ```
  </Tab>
</Tabs>

Verify the install:

```bash
discli --help
```

## Requirements

- Python 3.10 or higher
- A Discord bot token ([create one here](https://discord.com/developers/applications))

## Next Steps

<CardGroup>
  <Card title="Quickstart" href="/getting-started/quickstart">
    Send your first message in 2 minutes.
  </Card>
  <Card title="Configuration" href="/getting-started/configuration">
    Set up your bot token and preferences.
  </Card>
</CardGroup>
```

**Step 2: Create `docs/getting-started/quickstart.mdx`**

Content: 3 steps — set token, send a message, read messages. Uses `discli config set token`, `discli message send`, `discli message list`. Show both text and `--json` output. End with link to "Your First Bot".

**Step 3: Create `docs/getting-started/configuration.mdx`**

Content: Token resolution priority (flag → env → config), `discli config set token`, `DISCORD_BOT_TOKEN` env var, `~/.discli/config.json` manual editing, permission profiles overview, `--profile` flag.

**Step 4: Create `docs/getting-started/your-first-bot.mdx`**

Content: Full walkthrough from Discord Developer Portal → create application → create bot → invite to server → `discli config set token` → write 15-line Python agent using `discli serve` → see it respond. Include the code from the landing page code preview, but explained line by line. End with "what to learn next" cards pointing to Building Agents and Serve Mode guides.

**Step 5: Verify pages render with correct sidebar navigation**

Run: `npx @litodocs/cli dev -i ./docs`
Expected: All 4 pages render, sidebar shows Getting Started group with all 4 items.

**Step 6: Commit**

```bash
git add docs/getting-started/
git commit -m "docs: add getting started section (installation, quickstart, config, first bot)"
```

---

### Task 4: Guides Section (7 pages)

**Files:**
- Create: `docs/guides/cli-usage.mdx`
- Create: `docs/guides/building-agents.mdx`
- Create: `docs/guides/serve-mode.mdx`
- Create: `docs/guides/streaming-responses.mdx`
- Create: `docs/guides/slash-commands.mdx`
- Create: `docs/guides/security-permissions.mdx`
- Create: `docs/guides/scripting-automation.mdx`

**Step 1: Create `docs/guides/cli-usage.mdx`**

Content for DevOps/scripters:
- Sending messages: `discli message send "#general" "Hello"`
- Reading messages: `discli message list "#general" --limit 10`
- JSON output + jq piping: `discli --json message list "#general" | jq '.[] | .content'`
- Channel management: list, create, delete
- Member operations: list, info, kick, ban
- Reactions: add, remove, list
- DMs: `discli dm send @user "message"`
- All identifiers: channel names with #, user mentions with @, raw IDs

**Step 2: Create `docs/guides/building-agents.mdx`**

This is the **flagship page**. Content structure:

- Introduction: why discli is ideal for AI agents
- Level 1: Reactive Bot — `examples/support_agent.py` code (simplified), responds to keywords
- Level 2: Context-Aware — adds `message_list` to fetch recent messages before responding
- Level 3: Proactive — uses `discli serve` with streaming, thread creation, intent detection
- Level 4: Multi-Action — role assignment, DMs, reactions, channel management in one agent
- Level 5: Full Autonomous — permission profiles, audit logging, error handling, rate limit awareness

Each level has:
- Full working code (copy-pasteable)
- "What changed" explanation
- "What could go wrong" callout box using `<Callout type="warning">`
- Edge cases specific to that level

Use code from `examples/support_agent.py`, `examples/serve_bot.py`, `examples/claude_agent.py` as the basis for levels 1, 3, and 5 respectively.

**Step 3: Create `docs/guides/serve-mode.mdx`**

Content:
- What serve mode is and when to use it (vs fire-and-forget CLI)
- Starting: `discli serve` with all flags (`--status`, `--activity`, `--activity-text`, `--slash-commands`)
- The JSONL protocol: one JSON object per line, newline-delimited
- Reading events from stdout (event types overview, link to reference)
- Sending actions via stdin (action types overview, link to reference)
- `req_id` for request-response correlation
- Subprocess spawning patterns in Python (asyncio.create_subprocess_exec, subprocess.Popen)
- Windows considerations: stdin threading (reference troubleshooting page)
- Error handling: malformed JSON, unknown actions, Discord API errors

**Step 4: Create `docs/guides/streaming-responses.mdx`**

Content:
- Why streaming matters for AI agents (shows "thinking" to users)
- The 3-step protocol: `stream_start` → `stream_chunk` → `stream_end`
- `stream_start`: creates initial message, returns `stream_id`
- `stream_chunk`: appends content, message updates every 1.5s flush interval
- `stream_end`: finalizes the message
- Full working example from `examples/serve_bot.py` stream function
- Timing considerations: Discord rate limits on message edits
- Edge case: what happens if stream_end is never sent

**Step 5: Create `docs/guides/slash-commands.mdx`**

Content:
- What slash commands are in Discord
- Creating the commands JSON file: array of `{name, description, params: [{name, type, description, required}]}`
- Passing to serve: `--slash-commands commands.json`
- Registration timing: commands sync on bot start (can take up to 1 hour for global commands)
- Handling `slash_command` events: `interaction_token`, args, user
- Responding with `interaction_followup`: must respond within 15 minutes
- Edge case: interaction token expiry, deferred responses
- Full example from `examples/serve_bot.py`

**Step 6: Create `docs/guides/security-permissions.mdx`**

Content:
- Why security matters for autonomous agents
- Permission profiles: `full`, `chat`, `readonly`, `moderation` — what each allows/denies
- Setting profiles: `discli permission set chat`, `--profile readonly`, `DISCLI_PROFILE` env var
- `--triggered-by USER_ID`: verify Discord user has permission before acting
- `--yes` flag: skip confirmation on destructive actions (use carefully with agents)
- Audit logging: `discli audit show`, JSONL format, what gets logged
- Rate limiting: 5 calls per 5 seconds on destructive actions, auto-wait behavior
- Custom profiles: editing `~/.discli/permissions.json`

**Step 7: Create `docs/guides/scripting-automation.mdx`**

Content for DevOps:
- Bash one-liners: send from CI, pipe webhook data
- Channel logging: `examples/channel_logger.sh` walkthrough
- Reaction polls: `examples/reaction_poll.sh` walkthrough
- Cron job: schedule daily messages, periodic channel cleanup
- CI/CD integration: GitHub Actions step to send deploy notifications
- JSON output + jq patterns for parsing discli output
- Error handling in scripts: check exit codes, parse stderr

**Step 8: Verify all guide pages render**

Run: `npx @litodocs/cli dev -i ./docs`

**Step 9: Commit**

```bash
git add docs/guides/
git commit -m "docs: add guides section (CLI usage, building agents, serve mode, streaming, slash commands, security, scripting)"
```

---

### Task 5: Use Cases Section (5 pages)

**Files:**
- Create: `docs/use-cases/ai-support-agent.mdx`
- Create: `docs/use-cases/moderation-bot.mdx`
- Create: `docs/use-cases/thread-based-support.mdx`
- Create: `docs/use-cases/channel-logger.mdx`
- Create: `docs/use-cases/ci-notifications.mdx`

Each page follows the format: **problem → solution → full code → how it works → edge cases → extending it**.

**Step 1: Create `docs/use-cases/ai-support-agent.mdx`**

- Problem: You want an AI that answers questions in your Discord server
- Solution: Claude Agent SDK + discli serve
- Full code: adapted from `examples/claude_agent.py` — explain each section
- How it works: listen for @mentions → fetch context → send to Claude → stream response
- Edge cases: long responses (Discord 2000 char limit), rate limits, Claude errors
- Extending: add thread creation, memory/conversation history, multi-model support

**Step 2: Create `docs/use-cases/moderation-bot.mdx`**

- Problem: Spam and toxic content in your server
- Solution: discli listen + keyword detection + escalating enforcement
- Full code: from `examples/moderation_bot.py`
- How it works: listen → check banned words → delete message → warn → kick after threshold
- Edge cases: bot needs `MANAGE_MESSAGES` and `KICK_MEMBERS` permissions, rate limiting on mass spam
- Extending: AI-powered content analysis, configurable rules, log to database

**Step 3: Create `docs/use-cases/thread-based-support.mdx`**

- Problem: Support requests clutter the main channel
- Solution: Auto-create threads per request
- Full code: from `examples/thread_support_agent.py`
- How it works: detect @mention in channel → create thread → reply inside → track active threads
- Edge cases: thread limit per channel, thread auto-archive, bot needs `CREATE_PUBLIC_THREADS`
- Extending: close threads after resolution, hand off to human

**Step 4: Create `docs/use-cases/channel-logger.mdx`**

- Problem: You need an audit trail of channel activity
- Solution: `discli listen --json` piped to a file
- Full code: from `examples/channel_logger.sh`
- How it works: JSONL stream → append to file → parse with jq
- Edge cases: large files, log rotation, disk space
- Extending: ship to S3, parse into SQLite, alert on keywords

**Step 5: Create `docs/use-cases/ci-notifications.mdx`**

- Problem: Team needs to know about deploys, test failures, releases
- Solution: `discli message send` in GitHub Actions
- Full code: GitHub Actions workflow YAML step that sends to Discord
- How it works: `discli message send "#deploys" "Deploy ${{ github.sha }} succeeded"`
- Edge cases: token as GitHub secret, channel ID vs name, rate limits in parallel jobs
- Extending: rich embeds (future feature), thread per deploy, failure alerts with diff

**Step 6: Commit**

```bash
git add docs/use-cases/
git commit -m "docs: add use cases section (AI agent, moderation, threads, logger, CI)"
```

---

### Task 6: Architecture Section (4 pages)

**Files:**
- Create: `docs/architecture/overview.mdx`
- Create: `docs/architecture/serve-protocol.mdx`
- Create: `docs/architecture/security-model.mdx`
- Create: `docs/architecture/token-resolution.mdx`

**Step 1: Create `docs/architecture/overview.mdx`**

Content with Mermaid diagrams:
- High-level: User/Agent → discli CLI → Click framework → Permission check → Token resolution → discord.py → Discord API
- Command execution flow diagram
- Serve mode event loop diagram
- Module dependency graph: cli.py → commands/* → client.py → security.py → config.py, utils.py

Reference the existing Mermaid diagrams from README.md and expand them.

**Step 2: Create `docs/architecture/serve-protocol.mdx`**

The JSONL stdin/stdout specification:
- Overview: bidirectional, newline-delimited JSON
- Events (stdout): table of all event types with payload fields
  - `ready`, `message`, `slash_command`, `message_edit`, `message_delete`, `reaction_add`, `reaction_remove`, `member_join`, `member_remove`, `response`
- Actions (stdin): table of all action types with required/optional fields
  - Messaging: `send`, `reply`, `edit`, `delete`
  - Streaming: `stream_start`, `stream_chunk`, `stream_end`
  - Interactions: `interaction_followup`
  - Typing: `typing_start`, `typing_stop`
  - Presence: `presence`
  - Reactions: `reaction_add`, `reaction_remove`
  - Threads: `thread_create`, `thread_send`, `thread_list`
  - Polls: `poll_send`
  - Channels: `channel_list`, `channel_create`, `channel_info`
  - Members: `member_list`, `member_info`
  - Roles: `role_list`, `role_assign`, `role_remove`
  - DMs: `dm_send`
  - Queries: `message_list`, `message_get`, `message_search`, `message_pin`, `message_unpin`
  - Server: `server_list`, `server_info`
- Request-response correlation: `req_id` field
- Error responses: `{"event":"response","status":"error","error":"message"}`
- Link to reference pages for complete schemas

**Step 3: Create `docs/architecture/security-model.mdx`**

Internals of security.py:
- Permission enforcement pipeline diagram
- Profile definitions: what `allowed` and `denied` arrays contain
- How `check_permission()` works: resolve profile → check command against allowed/denied
- Audit logging: when it fires, JSONL format, storage at `~/.discli/audit.log`
- Rate limiter: token bucket algorithm, 5 tokens / 5 second window, auto-wait
- `--triggered-by` flow: resolve user → check Discord permissions → allow/deny
- Config storage: `~/.discli/permissions.json` format

**Step 4: Create `docs/architecture/token-resolution.mdx`**

Content:
- Resolution priority diagram: `--token` flag → `DISCORD_BOT_TOKEN` env var → `~/.discli/config.json`
- Code walkthrough of `resolve_token()` in `client.py`
- Config file format and location
- Why this order matters (CLI override > environment > persistent config)
- Security: tokens never logged, never in audit trail

**Step 5: Commit**

```bash
git add docs/architecture/
git commit -m "docs: add architecture section (overview, serve protocol, security model, token resolution)"
```

---

### Task 7: Comparisons Section (4 pages)

**Files:**
- Create: `docs/comparisons/vs-discord-libraries.mdx`
- Create: `docs/comparisons/vs-cli-tools.mdx`
- Create: `docs/comparisons/vs-hosted-bots.mdx`
- Create: `docs/comparisons/why-discli.mdx`

Each comparison follows: what it is → what it's good at → where discli differs → side-by-side table → when to use which.

**Step 1: Create `docs/comparisons/vs-discord-libraries.mdx`**

vs discord.py and discord.js:

```mdx
---
title: discli vs Discord Libraries
description: How discli compares to discord.py, discord.js, and other Discord bot libraries
---

# discli vs Discord Libraries

## discord.py / discord.js

These are the standard libraries for building Discord bots in Python and JavaScript.

### What they're good at
- Full Discord API coverage
- Fine-grained control over every aspect of the bot
- Large ecosystems with extensions (cogs, plugins)
- Production-proven at scale

### Where discli differs

| | discord.py / discord.js | discli |
|---|---|---|
| **Setup** | 50+ lines before first reply | 0 lines — `discli serve` handles it |
| **Language** | Python or JavaScript only | Any language (subprocess + JSON) |
| **Event loop** | You manage it | discli manages it |
| **Intents** | Manual configuration | Automatic |
| **Security** | Roll your own | Built-in profiles, audit, rate limiting |
| **AI integration** | Build from scratch | Native JSONL protocol for agents |
| **Streaming** | Manual message editing | `stream_start/chunk/end` protocol |
| **Learning curve** | Hours to first bot | Minutes to first bot |

### When to use discord.py/js instead
- You need features discli doesn't expose (embeds, components, voice)
- You're building a monolithic bot with complex state management
- You need webhook or OAuth2 flows
- Performance at extreme scale (10,000+ guilds)

### When to use discli
- You're building an AI agent that needs Discord access
- You want to script Discord operations from bash/CI
- You want security guardrails out of the box
- You're prototyping and want to move fast
```

**Step 2: Create `docs/comparisons/vs-cli-tools.mdx`**

vs discrawl and other Discord CLI tools:
- discrawl: read-only scraper, no write operations, no real-time events, no agent protocol
- Other CLIs (discord-cli, cordless): user-account focused (TOS violation risk), not bot-oriented
- discli's advantage: bidirectional, bot-token based, agent-ready, security built-in

**Step 3: Create `docs/comparisons/vs-hosted-bots.mdx`**

vs MEE6, Combot, Dyno, Carl-bot:
- Hosted: easy setup, no code needed, but limited customization, vendor lock-in, paid tiers
- discli: self-hosted, fully programmable, any AI model, MIT licensed, free
- When hosted wins: non-technical server admins, simple needs
- When discli wins: AI integration, custom logic, privacy, no recurring cost

**Step 4: Create `docs/comparisons/why-discli.mdx`**

Summary decision tree:
- "I want an AI agent on Discord" → discli
- "I want to script Discord from CI/bash" → discli
- "I want a no-code moderation bot" → MEE6/Dyno
- "I want full API control in Python" → discord.py (or discli for simpler cases)
- "I want to build a complex stateful bot" → discord.py/js
- "I want to scrape messages" → discrawl (read) or discli (read + write)

**Step 5: Commit**

```bash
git add docs/comparisons/
git commit -m "docs: add comparisons section (vs libraries, vs CLI tools, vs hosted bots, why discli)"
```

---

### Task 8: Troubleshooting Section (4 pages)

**Files:**
- Create: `docs/troubleshooting/common-issues.mdx`
- Create: `docs/troubleshooting/windows-quirks.mdx`
- Create: `docs/troubleshooting/edge-cases.mdx`
- Create: `docs/troubleshooting/faq.mdx`

**Step 1: Create `docs/troubleshooting/common-issues.mdx`**

Issues and solutions:

1. **"Token not found"** — No `--token`, no `DISCORD_BOT_TOKEN` env var, no config. Solution: `discli config set token YOUR_TOKEN`
2. **"Permission denied" on a command** — Active profile restricts it. Solution: `discli permission show`, switch profile
3. **Bot doesn't respond to messages** — Missing `MESSAGE_CONTENT` intent in Discord Developer Portal. Solution: enable privileged intents
4. **"Rate limited" errors** — Hitting Discord API limits or discli's built-in rate limiter. Solution: reduce call frequency, use `--json` to check headers
5. **Commands work but `discli listen` shows nothing** — Missing intents (GUILD_MESSAGES, GUILD_MEMBERS). Solution: enable in portal
6. **`discli serve` exits immediately** — Invalid token, network error. Solution: check stderr output

Each issue: symptom → cause → fix → prevention.

**Step 2: Create `docs/troubleshooting/windows-quirks.mdx`**

Windows-specific issues:

1. **stdin reading in serve mode** — asyncio stdin doesn't work on Windows. discli uses a threading-based reader (`threading.Thread` + `queue.Queue`). Usually transparent, but: slower event processing under heavy load, `Ctrl+C` may not terminate cleanly (use `proc.terminate()`)
2. **Path separators** — Use forward slashes in commands. discli normalizes internally.
3. **PowerShell vs bash** — Command quoting differs. Show examples for both shells.
4. **Encoding** — Unicode emoji in messages may require `chcp 65001` in cmd.exe
5. **pip install issues** — `python -m pip install` if `pip` not on PATH

**Step 3: Create `docs/troubleshooting/edge-cases.mdx`**

Technical edge cases:

1. **Large guild member fetches** — Guilds with 1000+ members: discord.py lazy-loads, `member_list` may not return all. Solution: enable `GUILD_MEMBERS` intent + `fetch_members` (discli does this automatically in listen mode)
2. **Interaction token expiry** — Slash command tokens expire after 15 minutes. If agent takes too long, `interaction_followup` fails. Solution: respond quickly or acknowledge immediately
3. **Slash command sync delay** — Global commands can take up to 1 hour to appear. Guild commands appear instantly. Workaround: test with guild-specific commands first
4. **Discord 2000 character limit** — Messages over 2000 chars are rejected. Solution: split messages, or use streaming (which handles chunking)
5. **Rate limit 429 from Discord API** — Different from discli's rate limiter. Discord returns `Retry-After` header. discord.py handles this automatically with exponential backoff
6. **Cache misses** — `member_info` may fail if member not in cache. Solution: the command fetches from API as fallback (see `check_user_permission()` in security.py)
7. **Bot mentions itself** — In serve mode, filter `is_bot: true` events to avoid infinite loops
8. **Multiple bots same token** — Only one `discli serve` instance per token. Multiple CLI commands are fine (stateless)

**Step 4: Create `docs/troubleshooting/faq.mdx`**

```mdx
---
title: FAQ
description: Frequently asked questions about discli
---

# FAQ

<Accordion title="Can I use discli without Python?">
Yes for basic CLI usage — the pip install gives you a standalone `discli` binary.
For building agents, you can use any language that can spawn a subprocess and read/write JSONL.
The agent just needs to `Popen(["discli", "serve"])` and pipe stdin/stdout.
</Accordion>

<Accordion title="Does discli work with self-hosted Discord?">
No. discli uses the official Discord API via discord.py. It does not support
self-hosted alternatives like Revolt or Guilded.
</Accordion>

<Accordion title="Can multiple agents share one bot token?">
Only one `discli serve` process per token. Multiple fire-and-forget CLI commands
(message send, channel list, etc.) can share a token since they connect and disconnect.
</Accordion>

<Accordion title="Is this against Discord's TOS?">
No. discli uses official bot tokens and the public Discord API. It does not
use user tokens, self-bots, or client modifications.
</Accordion>

<Accordion title="Can I use this with OpenAI / Claude / local models?">
Yes. discli is model-agnostic. Your agent code calls whatever AI you want,
then sends actions to discli. See the Building Agents guide for examples.
</Accordion>

<Accordion title="How do I add embeds / buttons / dropdowns?">
discli currently supports text messages, reactions, threads, polls, and slash commands.
Rich embeds and message components (buttons, selects) are planned for a future release.
</Accordion>

<Accordion title="What Discord permissions does my bot need?">
Depends on what you use. At minimum: Send Messages, Read Message History.
For full functionality: Manage Messages, Kick Members, Ban Members, Manage Roles,
Create Public Threads, Add Reactions. Use the readonly profile to restrict discli's actions.
</Accordion>
```

**Step 5: Commit**

```bash
git add docs/troubleshooting/
git commit -m "docs: add troubleshooting section (common issues, Windows, edge cases, FAQ)"
```

---

### Task 9: Reference Section (4 pages)

**Files:**
- Create: `docs/reference/cli-commands.mdx`
- Create: `docs/reference/serve-actions.mdx`
- Create: `docs/reference/serve-events.mdx`
- Create: `docs/reference/permission-profiles.mdx`

**Step 1: Create `docs/reference/cli-commands.mdx`**

Complete reference for every CLI command. Source from `src/discli/cli.py` and each `commands/*.py` file. Format:

```mdx
## message

### message send

Send a message to a channel.

\`\`\`bash
discli message send <channel> <content>
\`\`\`

| Option | Type | Description |
|--------|------|-------------|
| `channel` | string | Channel name (#general) or ID |
| `content` | string | Message text |

### message list

List recent messages in a channel.

\`\`\`bash
discli message list <channel> [--limit N]
\`\`\`
...
```

Cover all command groups: message (send, list, edit, delete, search, reply), dm (send, list), reaction (add, remove, list), channel (list, create, delete, info), thread (create, list, send), server (list, info), role (list, create, assign, remove, delete), member (list, info, kick, ban, unban), poll (send), typing, listen, serve, config (set, get, show), permission (show, set, profiles), audit (show, clear).

Include global options: `--token`, `--json`, `--yes`, `--profile`.

**Step 2: Create `docs/reference/serve-actions.mdx`**

Every action accepted via stdin in serve mode. Source from `ACTION_REGISTRY` in `serve.py`. Format per action:

```mdx
### send

Send a message to a channel.

**Request:**
\`\`\`json
{"action": "send", "channel_id": "123456", "content": "Hello!", "req_id": "1"}
\`\`\`

**Response:**
\`\`\`json
{"event": "response", "status": "ok", "req_id": "1", "message_id": "789"}
\`\`\`

| Field | Required | Description |
|-------|----------|-------------|
| `channel_id` | yes | Target channel ID |
| `content` | yes | Message text |
| `req_id` | no | Correlation ID for response |
```

Cover all 25+ actions from the ACTION_REGISTRY.

**Step 3: Create `docs/reference/serve-events.mdx`**

Every event emitted via stdout. Format per event:

```mdx
### message

Fired when a user sends a message in a channel the bot can see.

\`\`\`json
{
  "event": "message",
  "message_id": "123",
  "channel_id": "456",
  "server": "789",
  "author": "alice",
  "author_id": "111",
  "content": "Hello!",
  "is_bot": false,
  "mentions_bot": true
}
\`\`\`

| Field | Type | Description |
|-------|------|-------------|
| `message_id` | string | Message snowflake ID |
| ...
```

Cover: `ready`, `message`, `slash_command`, `message_edit`, `message_delete`, `reaction_add`, `reaction_remove`, `member_join`, `member_remove`, `response`.

**Step 4: Create `docs/reference/permission-profiles.mdx`**

All 4 built-in profiles with their `allowed` and `denied` arrays. Custom profile creation via `~/.discli/permissions.json`. Format:

```mdx
## Built-in Profiles

### full (default)
All commands allowed. No restrictions.

### chat
**Allowed:** message send, message list, message reply, message edit, message search, reaction add, reaction remove, reaction list, thread create, thread send, thread list, dm send, dm list, typing
**Denied:** Everything else (kick, ban, channel delete, role management, etc.)

### readonly
**Allowed:** message list, channel list, channel info, server list, server info, member list, member info, role list, thread list, reaction list, listen
**Denied:** All write operations

### moderation
All commands allowed (same as full), explicitly labeled for moderation use.

## Custom Profiles

Create `~/.discli/permissions.json`:
\`\`\`json
{
  "active_profile": "my-custom",
  "profiles": {
    "my-custom": {
      "description": "Only messaging and threads",
      "allowed": ["message.*", "thread.*", "typing"],
      "denied": ["member.kick", "member.ban"]
    }
  }
}
\`\`\`
```

**Step 5: Commit**

```bash
git add docs/reference/
git commit -m "docs: add reference section (CLI commands, serve actions, serve events, permission profiles)"
```

---

### Task 10: Final Polish & Verify

**Step 1: Verify all pages render correctly**

Run: `npx @litodocs/cli dev -i ./docs`

Check:
- Landing page loads with all 8 sections
- Terminal animation plays in hero
- All 27 pages accessible from sidebar
- Search works (Pagefind indexes all content)
- Dark/light mode toggle works
- Mobile responsive layout
- All internal links resolve
- Code blocks have syntax highlighting
- Lito components render (Tabs, Cards, Callouts, Accordion, Steps)

**Step 2: Add `.gitignore` entry for Lito build output**

Check if Lito outputs a `dist/` or `.astro/` folder inside `docs/`. If so, add to `.gitignore`:

```
docs/dist/
docs/.astro/
docs/node_modules/
```

**Step 3: Update root README.md**

Add a "Documentation" section near the top linking to the docs site (or mentioning `npx @litodocs/cli dev -i ./docs` for local viewing).

**Step 4: Update CLAUDE.md**

Add docs development commands:

```
# Docs development
npx @litodocs/cli dev -i ./docs     # Start docs dev server
npx @litodocs/cli build -i ./docs   # Build docs for production
```

**Step 5: Final commit**

```bash
git add .gitignore README.md CLAUDE.md
git commit -m "docs: final polish — gitignore, README link, CLAUDE.md update"
```

---

## Task Dependency Graph

```
Task 1 (Init Lito) → Task 2 (Landing) → Task 3-9 (Content pages, can be parallelized) → Task 10 (Polish)
```

Tasks 3 through 9 are independent of each other and can be written in any order or in parallel. Task 10 depends on all content being complete.

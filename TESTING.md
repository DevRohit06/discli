# discli Test Messages

Test messages for the AI serve agent. Run the bot first:

```bash
pip install discord-cli-agent claude-agent-sdk
discli config set token YOUR_BOT_TOKEN
python examples/ai_serve_agent.py
```

Then @mention the bot in a Discord channel. Below are test messages grouped by feature.

---

## Basic Chat

```
@bot hey, what's up?
@bot what can you do?
@bot what did I just ask you?
```

## Embeds

```
@bot send a blue embed with title "Server Status" and 3 inline fields: Users=42, Online=15, Messages Today=337
@bot send a red warning embed saying "Maintenance in 1 hour" with a footer "Scheduled by admin"
```

## Buttons

```
@bot send a message with 3 buttons: Accept (green), Decline (red), and Maybe (grey)
@bot send a message asking "Rate this bot" with 5 buttons: 1 star through 5 stars
@bot send a message with a "Visit GitHub" link button to https://github.com/DevRohit06/discli
```

## Select Menus

```
@bot send a dropdown to pick a color: Red, Blue, Green, Yellow with emoji for each
@bot send a user picker so I can select someone
@bot send a role picker dropdown
@bot send a channel picker dropdown
```

## Modals

```
@bot send a button that opens a feedback form with Name and Message fields
@bot send a "Create Ticket" button that opens a modal asking for Subject and Description
```

## Embeds + Buttons

```
@bot send a poll-style embed titled "Movie Night" with description "Vote for Friday or Saturday" and two buttons: Friday (blue) and Saturday (green)
@bot send an embed with a "Delete this message" danger button
```

## Messages

```
@bot send "Hello from the bot!" to #general
@bot search for messages containing "hello" in this channel
@bot what were the last 5 messages in #general?
```

## Channels

```
@bot list all channels in this server
@bot create a text channel called "bot-testing"
@bot set the topic of #bot-testing to "Automated testing channel"
@bot delete #bot-testing
```

## Threads

```
@bot create a thread called "Support Ticket" on my last message
@bot say "I'm helping you in this thread!" here
@bot rename this thread to "Resolved: Support Ticket"
@bot archive this thread
```

## Roles

```
@bot what roles does this server have?
@bot create a red role called "Tester"
@bot give me the Tester role
@bot remove the Tester role from me
@bot make the Tester role green and mentionable
@bot delete the Tester role
```

## Members & Moderation

```
@bot tell me about myself in this server
@bot how many members are in this server?
@bot timeout @TestUser for 60 seconds, reason: testing
@bot remove timeout from @TestUser
```

## Reactions

```
@bot react to my last message with thumbs up, party, and fire emoji
@bot who reacted with thumbs up?
```

## Polls

```
@bot create a poll: "Best language?" with options Python, Rust, Go, JavaScript
@bot show the poll results
@bot end the poll
```

## Webhooks

```
@bot create a webhook in this channel called "Notifications"
@bot list webhooks here
@bot delete the Notifications webhook
```

## Events

```
@bot create a server event called "Game Night" on April 5th 2026 at 8pm, location "Voice Chat", ending at 10pm
@bot what events are scheduled?
@bot cancel the Game Night event
```

## Streaming

```
@bot write me a 200-word story about a robot learning to paint
```

## DMs

```
@bot DM me a secret message
```

## Multi-Step

```
@bot set up a welcome system: create a #welcome channel, send a nice embed there with a "Pick Roles" button, then tell me it's done
@bot clean up: delete #welcome
```

## Error Handling

```
@bot send a message to #nonexistent-channel
@bot play music in voice chat
@bot kick the server owner
```

---

## What the Bot Can Do

| Category | Capabilities |
|----------|-------------|
| **Messages** | Send, reply, edit, delete, search, history, bulk-delete, pin/unpin |
| **Embeds** | Title, description, color, footer, image, thumbnail, author, fields |
| **Buttons** | Primary, secondary, success, danger, link, disabled |
| **Select Menus** | String options, user picker, role picker, channel picker |
| **Modals** | Text inputs (short/long), triggered from buttons |
| **Channels** | List, create, edit, delete, forum posts, permissions |
| **Threads** | Create, send, rename, archive/unarchive, add/remove members |
| **Roles** | List, create, edit, delete, assign, remove |
| **Members** | List, info, timeout, kick, ban |
| **Reactions** | Add, remove, list, who reacted |
| **Polls** | Create, results, end |
| **Webhooks** | Create, list, delete |
| **Events** | Create, list, delete |
| **DMs** | Send, list |
| **Streaming** | Progressive message edits (token-by-token) |
| **Slash Commands** | /ask, /help, /summarize, /clear |

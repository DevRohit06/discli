# discli Bot Test Messages

Messages to send in Discord and what the bot should do. The bot is running via `python examples/claude_agent.py`.

> **Setup:** Bot is @mentioned in a test channel. It reads the message, sends it to Claude, and Claude uses discli to respond.

---

## 1. Basic Conversation

### 1.1 Simple greeting
**You type:**
```
@bot hey, what's up?
```
**Expected:** Bot replies to your message with a friendly greeting.

### 1.2 Follow-up question
**You type:**
```
@bot what can you do?
```
**Expected:** Bot describes its capabilities — managing Discord (messages, channels, roles, etc).

---

## 2. Message Operations

### 2.1 Send a message to another channel
**You type:**
```
@bot send "Hello from the bot!" to #general
```
**Expected:** Bot sends "Hello from the bot!" in #general, confirms it was sent.

### 2.2 Send with embed
**You type:**
```
@bot send an announcement in #general with a blue embed titled "Server Update" that says "We've added new features!"
```
**Expected:** Bot sends a message with a blue embed (color 5865F2) in #general with the title and description.

### 2.3 Search messages
**You type:**
```
@bot find messages containing "hello" in this channel
```
**Expected:** Bot runs `discli message search` and replies with matching messages.

### 2.4 Get message history
**You type:**
```
@bot what were the last 5 messages in #general?
```
**Expected:** Bot fetches and summarizes the last 5 messages from #general.

---

## 3. Channel Management

### 3.1 List channels
**You type:**
```
@bot list all channels in this server
```
**Expected:** Bot lists channels with names and types (text, voice, forum).

### 3.2 Create a channel
**You type:**
```
@bot create a text channel called "bot-testing"
```
**Expected:** Bot creates #bot-testing, confirms with channel ID.

### 3.3 Edit a channel
**You type:**
```
@bot set the topic of #bot-testing to "Automated testing channel"
```
**Expected:** Bot updates the topic, confirms.

### 3.4 Delete a channel
**You type:**
```
@bot delete #bot-testing
```
**Expected:** Bot deletes the channel (using --yes flag), confirms.

---

## 4. Thread Operations

### 4.1 Create a thread
**You type:**
```
@bot create a thread called "Support Ticket" on my last message
```
**Expected:** Bot creates a thread from your message, replies with thread ID.

### 4.2 Send to thread
**You type (in the thread):**
```
@bot say "I'm helping you in this thread!" here
```
**Expected:** Bot sends the message in the thread.

### 4.3 Rename thread
**You type:**
```
@bot rename this thread to "Resolved: Support Ticket"
```
**Expected:** Bot renames the thread.

### 4.4 Archive thread
**You type:**
```
@bot archive this thread
```
**Expected:** Bot archives the thread.

---

## 5. Role Management

### 5.1 List roles
**You type:**
```
@bot what roles does this server have?
```
**Expected:** Bot lists all roles with member counts.

### 5.2 Create a role
**You type:**
```
@bot create a red role called "Tester"
```
**Expected:** Bot creates role with color ff0000, confirms.

### 5.3 Assign role
**You type:**
```
@bot give me the Tester role
```
**Expected:** Bot assigns the "Tester" role to you.

### 5.4 Remove role
**You type:**
```
@bot remove the Tester role from me
```
**Expected:** Bot removes the role.

### 5.5 Edit role
**You type:**
```
@bot make the Tester role green and mentionable
```
**Expected:** Bot edits the role color to 00ff00 and sets mentionable.

### 5.6 Delete role
**You type:**
```
@bot delete the Tester role
```
**Expected:** Bot deletes the role, confirms.

---

## 6. Member Info & Moderation

### 6.1 Member info
**You type:**
```
@bot tell me about myself in this server
```
**Expected:** Bot shows your name, roles, join date, etc.

### 6.2 List members
**You type:**
```
@bot how many members are in this server? list some
```
**Expected:** Bot lists members with names and roles.

### 6.3 Timeout (test on alt or willing participant)
**You type:**
```
@bot timeout @TestUser for 60 seconds, reason: testing timeout
```
**Expected:** Bot timeouts the user for 60s, confirms.

### 6.4 Remove timeout
**You type:**
```
@bot remove timeout from @TestUser
```
**Expected:** Bot removes the timeout.

---

## 7. Reactions

### 7.1 Add reaction
**You type:**
```
@bot react to my last message with 👍
```
**Expected:** Bot adds 👍 reaction to your previous message.

### 7.2 Multiple reactions
**You type:**
```
@bot react to that message with 🎉 ❤️ and 🔥
```
**Expected:** Bot adds all 3 reactions.

### 7.3 Who reacted
**You type (after reacting yourself):**
```
@bot who reacted with 👍 to that message?
```
**Expected:** Bot lists users who reacted.

---

## 8. Polls

### 8.1 Create poll
**You type:**
```
@bot create a poll in this channel: "Best programming language?" with options Python, Rust, Go, JavaScript
```
**Expected:** Bot creates a Discord poll with the 4 options.

### 8.2 Check results
**You type (after some votes):**
```
@bot what are the poll results?
```
**Expected:** Bot shows vote counts per option.

### 8.3 End poll
**You type:**
```
@bot end the poll
```
**Expected:** Bot ends the poll early.

---

## 9. Webhooks

### 9.1 Create webhook
**You type:**
```
@bot create a webhook in this channel called "Notifications"
```
**Expected:** Bot creates webhook, shows the name and URL.

### 9.2 List webhooks
**You type:**
```
@bot list webhooks in this channel
```
**Expected:** Shows the "Notifications" webhook.

### 9.3 Delete webhook
**You type:**
```
@bot delete the Notifications webhook
```
**Expected:** Bot deletes it, confirms.

---

## 10. Scheduled Events

### 10.1 Create event
**You type:**
```
@bot create a server event called "Game Night" on April 5th 2026 at 8pm, location "Voice Chat", ending at 10pm
```
**Expected:** Bot creates a scheduled event, confirms with ID.

### 10.2 List events
**You type:**
```
@bot what events are scheduled?
```
**Expected:** Bot lists the "Game Night" event.

### 10.3 Delete event
**You type:**
```
@bot cancel the Game Night event
```
**Expected:** Bot deletes the event.

---

## 11. Server Info

### 11.1 Server stats
**You type:**
```
@bot give me stats about this server
```
**Expected:** Bot shows server name, owner, member count, channel count, role count.

### 11.2 Channel info
**You type:**
```
@bot what's the info for this channel?
```
**Expected:** Bot shows channel ID, name, type, topic, creation date.

---

## 12. DMs

### 12.1 Send DM
**You type:**
```
@bot DM me saying "Hello from Discord bot!"
```
**Expected:** You receive a DM from the bot with that message.

---

## 13. Complex / Multi-step Tasks

### 13.1 Onboarding setup
**You type:**
```
@bot set up an onboarding flow: create a channel called "welcome", send a message there with an embed titled "Welcome!" with description "Read the rules and pick your roles", make it blue
```
**Expected:** Bot creates #welcome, sends embed message, confirms.

### 13.2 Cleanup
**You type:**
```
@bot delete the #welcome channel
```
**Expected:** Bot deletes it.

### 13.3 Announcement with embed and reactions
**You type:**
```
@bot send an announcement in #general: embed titled "Maintenance" in red, description "Server maintenance at 10pm UTC", then react with ✅ and ⏰ to it
```
**Expected:** Bot sends the red embed, then adds both reactions to it.

### 13.4 Thread support flow
**You type:**
```
@bot when I say "I need help", create a support thread from my message, send a welcome message in it, and reply to me saying the thread was created
```
Then type:
```
I need help
```
**Expected:** Bot creates thread, sends welcome in it, replies to confirm.

---

## 14. Error Handling

### 14.1 Non-existent channel
**You type:**
```
@bot send "test" to #channel-that-doesnt-exist
```
**Expected:** Bot reports the channel wasn't found, doesn't crash.

### 14.2 Permission denied
**You type:**
```
@bot kick me
```
**Expected:** Bot either refuses (self-kick doesn't make sense) or handles the error gracefully.

### 14.3 Impossible task
**You type:**
```
@bot play music in the voice channel
```
**Expected:** Bot explains it can't do voice/audio — it only manages text-based Discord operations.

---

## Quick Reference: What the Bot Can Do

| Category | Capabilities |
|----------|-------------|
| **Messages** | Send, reply, edit, delete, search, history, bulk-delete, pin/unpin |
| **Embeds** | Title, description, color, footer, image, thumbnail, author, fields |
| **Channels** | List, create, edit, delete, forum posts, set permissions |
| **Threads** | Create, send, rename, archive/unarchive, add/remove members |
| **Roles** | List, create, edit, delete, assign, remove |
| **Members** | List, info, timeout, kick, ban |
| **Reactions** | Add, remove, list, who reacted |
| **Polls** | Create, results, end |
| **Webhooks** | Create, list, delete |
| **Events** | Create, list, delete |
| **DMs** | Send, list |
| **Typing** | Show typing indicator |
| **Presence** | Set bot status/activity |


 Basic Chat

  @bot hello, who are you?
  @bot what did I just ask you?

  Embeds

  @bot send a blue embed with title "Server Status" and 3 inline fields: Users=42, Online=15, Messages Today=337
  @bot send a red warning embed saying "Maintenance in 1 hour" with a footer "Scheduled by admin"

  Buttons

  @bot send a message with 3 buttons: Accept (green), Decline (red), and Maybe (grey)
  @bot send a message asking "Rate this bot" with 5 buttons: ⭐1 ⭐2 ⭐3 ⭐4 ⭐5
  @bot send a message with a "Visit GitHub" link button to https://github.com/DevRohit06/discli

  Select Menus

  @bot send a dropdown to pick a color: Red, Blue, Green, Yellow — with emoji for each
  @bot send a user picker so I can select someone
  @bot send a role picker dropdown
  @bot send a channel picker dropdown

  Modals

  @bot send a button that opens a feedback form with Name and Message fields when clicked
  @bot send a "Create Ticket" button that opens a modal asking for Subject and Description

  Embeds + Buttons Combo

  @bot send a poll-style embed titled "Movie Night" with description "Vote for Friday or Saturday" and two buttons: Friday (blue) and Saturday (green)
  @bot send an embed with a "Delete this message" danger button
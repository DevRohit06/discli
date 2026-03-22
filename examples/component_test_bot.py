"""
Interactive component test bot.

Tests buttons, select menus, and modals via discli serve mode.
Sends component messages when you @mention the bot, then handles clicks.

Usage:
    discli config set token YOUR_BOT_TOKEN
    python examples/component_test_bot.py

Then @mention the bot in Discord and pick a test from the menu.
"""

import asyncio
import json
import sys

# Channel ID where the bot listens — set via first message
ACTIVE_CHANNEL = None


async def main():
    global ACTIVE_CHANNEL

    proc = await asyncio.create_subprocess_exec(
        "discli", "--json", "serve", "--status", "online",
        "--activity", "playing", "--activity-text", "Component Tests",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    req = 0
    streams = {}  # stream_id tracking

    async def send(action: str, **kwargs):
        nonlocal req
        req += 1
        cmd = {"action": action, "req_id": str(req), **kwargs}
        line = json.dumps(cmd) + "\n"
        proc.stdin.write(line.encode())
        await proc.stdin.drain()

    def log(msg):
        print(f"  [{msg}]", file=sys.stderr)

    print("Component Test Bot starting...", file=sys.stderr)
    print("@mention the bot in Discord to begin.\n", file=sys.stderr)

    try:
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            data = json.loads(line.decode().strip())
            event = data.get("event")

            # ── Ready ──
            if event == "ready":
                print(f"Connected as {data['bot_name']}", file=sys.stderr)

            # ── Track responses ──
            elif event == "response":
                if "stream_id" in data:
                    streams["last"] = data["stream_id"]
                if data.get("error"):
                    log(f"ERROR: {data['error']}")

            # ── Message: send test menu ──
            elif event == "message" and not data.get("is_bot"):
                if not data.get("mentions_bot"):
                    continue

                ACTIVE_CHANNEL = data["channel_id"]
                content = data["content"].lower()

                if "button" in content:
                    await test_buttons(send, data)
                elif "select" in content:
                    await test_selects(send, data)
                elif "modal" in content:
                    await test_modal_trigger(send, data)
                elif "embed" in content:
                    await test_embeds(send, data)
                elif "stream" in content:
                    await test_streaming(send, data, streams)
                else:
                    # Send the main test menu
                    await send("reply",
                        channel_id=data["channel_id"],
                        message_id=data["message_id"],
                        content="**Component Test Bot** — pick a test:",
                        components=[
                            [
                                {"type": "button", "label": "Test Buttons", "style": "primary", "custom_id": "menu_buttons", "emoji": "🔘"},
                                {"type": "button", "label": "Test Selects", "style": "primary", "custom_id": "menu_selects", "emoji": "📋"},
                                {"type": "button", "label": "Test Modal", "style": "primary", "custom_id": "menu_modal", "emoji": "📝"},
                                {"type": "button", "label": "Test Embeds", "style": "primary", "custom_id": "menu_embeds", "emoji": "🎨"},
                                {"type": "button", "label": "Test Streaming", "style": "primary", "custom_id": "menu_stream", "emoji": "📡"},
                            ]
                        ],
                    )

            # ── Component Interaction ──
            elif event == "component_interaction":
                cid = data.get("custom_id", "")
                itk = data["interaction_token"]
                values = data.get("values", [])
                user = data["user"]
                log(f"Component: {cid} by {user}, values={values}")

                # Menu buttons → spawn the test
                if cid == "menu_buttons":
                    await send("interaction_respond", interaction_token=itk,
                               content="Sending button test...", ephemeral=True)
                    await test_buttons(send, data)
                elif cid == "menu_selects":
                    await send("interaction_respond", interaction_token=itk,
                               content="Sending select test...", ephemeral=True)
                    await test_selects(send, data)
                elif cid == "menu_modal":
                    # Open modal directly (no defer!)
                    await send("modal_send", interaction_token=itk,
                        title="Test Feedback Form",
                        custom_id="test_modal",
                        fields=[
                            {"label": "Your Name", "custom_id": "name", "style": "short", "placeholder": "Enter name...", "required": True},
                            {"label": "Feedback", "custom_id": "feedback", "style": "long", "placeholder": "Share your thoughts...", "max_length": 500},
                        ])
                elif cid == "menu_embeds":
                    await send("interaction_respond", interaction_token=itk,
                               content="Sending embed test...", ephemeral=True)
                    await test_embeds(send, data)
                elif cid == "menu_stream":
                    await send("interaction_respond", interaction_token=itk,
                               content="Starting stream test...", ephemeral=True)
                    await test_streaming(send, data, streams)

                # ── Button test handlers ──
                elif cid == "btn_approve":
                    await send("interaction_respond", interaction_token=itk,
                               content=f"✅ {user} approved!", ephemeral=False)
                elif cid == "btn_reject":
                    await send("interaction_respond", interaction_token=itk,
                               content=f"❌ {user} rejected!", ephemeral=False)
                elif cid == "btn_secret":
                    await send("interaction_respond", interaction_token=itk,
                               content="🤫 This is a secret only you can see!", ephemeral=True)
                elif cid == "btn_disable":
                    await send("interaction_edit", interaction_token=itk,
                        content="Buttons disabled! ✅",
                        components=[[
                            {"type": "button", "label": "Done", "style": "secondary", "custom_id": "x", "disabled": True},
                        ]])

                # ── Select test handlers ──
                elif cid == "color_select":
                    color = values[0] if values else "none"
                    color_hex = {"red": "ED4245", "blue": "5865F2", "green": "57F287", "yellow": "FEE75C"}.get(color, "99AAB5")
                    await send("interaction_respond", interaction_token=itk,
                               content="", ephemeral=False,
                               embed={"title": f"You picked: {color}", "color": color_hex})
                elif cid == "user_pick":
                    await send("interaction_respond", interaction_token=itk,
                               content=f"You selected user(s): {values}", ephemeral=True)
                elif cid == "role_pick":
                    await send("interaction_respond", interaction_token=itk,
                               content=f"You selected role(s): {values}", ephemeral=True)
                elif cid == "channel_pick":
                    await send("interaction_respond", interaction_token=itk,
                               content=f"You selected channel(s): {values}", ephemeral=True)
                else:
                    await send("interaction_respond", interaction_token=itk,
                               content=f"Unhandled component: `{cid}`", ephemeral=True)

            # ── Modal Submit ──
            elif event == "modal_submit":
                itk = data["interaction_token"]
                fields = data.get("fields", {})
                log(f"Modal submit: {fields}")

                name = fields.get("name", "Anonymous")
                feedback = fields.get("feedback", "(empty)")

                await send("interaction_followup", interaction_token=itk,
                    content=f"Thanks {name}! Your feedback was received.",
                    embed={
                        "title": "Feedback Submitted",
                        "color": "57F287",
                        "fields": [
                            {"name": "From", "value": name, "inline": True},
                            {"name": "Message", "value": feedback, "inline": False},
                        ],
                        "footer": f"Submitted by {data.get('user', '?')}",
                    })

            # ── Voice/other events (just log) ──
            elif event in ("voice_state", "member_join", "member_remove"):
                log(f"Event: {event} — {json.dumps(data)[:100]}")

    except KeyboardInterrupt:
        print("\nShutting down...", file=sys.stderr)
    finally:
        proc.terminate()


# ── Test Functions ──

async def test_buttons(send, ctx):
    ch = ctx.get("channel_id", ACTIVE_CHANNEL)
    await send("send", channel_id=ch,
        content="**Button Test** — try each one:",
        components=[
            [
                {"type": "button", "label": "Approve", "style": "success", "custom_id": "btn_approve", "emoji": "✅"},
                {"type": "button", "label": "Reject", "style": "danger", "custom_id": "btn_reject", "emoji": "❌"},
                {"type": "button", "label": "Secret (ephemeral)", "style": "secondary", "custom_id": "btn_secret", "emoji": "🤫"},
                {"type": "button", "label": "Disable All", "style": "primary", "custom_id": "btn_disable"},
            ],
            [
                {"type": "button", "label": "Open Docs", "style": "link", "url": "https://github.com/DevRohit06/discli"},
            ],
        ])


async def test_selects(send, ctx):
    ch = ctx.get("channel_id", ACTIVE_CHANNEL)

    # String select
    await send("send", channel_id=ch,
        content="**Select Test 1/4** — String select (pick a color):",
        components=[[
            {"type": "select", "custom_id": "color_select", "placeholder": "Choose a color...",
             "options": [
                 {"label": "Red", "value": "red", "emoji": "🔴", "description": "Warm color"},
                 {"label": "Blue", "value": "blue", "emoji": "🔵", "description": "Cool color"},
                 {"label": "Green", "value": "green", "emoji": "🟢", "description": "Nature color"},
                 {"label": "Yellow", "value": "yellow", "emoji": "🟡", "description": "Bright color"},
             ]},
        ]])

    # User select
    await send("send", channel_id=ch,
        content="**Select Test 2/4** — User select:",
        components=[[
            {"type": "user_select", "custom_id": "user_pick", "placeholder": "Pick a user..."},
        ]])

    # Role select
    await send("send", channel_id=ch,
        content="**Select Test 3/4** — Role select:",
        components=[[
            {"type": "role_select", "custom_id": "role_pick", "placeholder": "Pick a role..."},
        ]])

    # Channel select
    await send("send", channel_id=ch,
        content="**Select Test 4/4** — Channel select:",
        components=[[
            {"type": "channel_select", "custom_id": "channel_pick", "placeholder": "Pick a channel..."},
        ]])


async def test_modal_trigger(send, ctx):
    ch = ctx.get("channel_id", ACTIVE_CHANNEL)
    await send("send", channel_id=ch,
        content="**Modal Test** — click the button to open a form:",
        components=[[
            {"type": "button", "label": "Open Feedback Form", "style": "primary", "custom_id": "menu_modal", "emoji": "📝"},
        ]])


async def test_embeds(send, ctx):
    ch = ctx.get("channel_id", ACTIVE_CHANNEL)

    # Simple embed
    await send("send", channel_id=ch, content="**Embed Test 1/3** — Basic:",
        embed={"title": "Simple Embed", "description": "Just title and description", "color": "5865F2"})

    # Full embed
    await send("send", channel_id=ch, content="**Embed Test 2/3** — Full:",
        embed={
            "title": "Full Embed",
            "description": "This embed has everything!",
            "color": "ED4245",
            "footer": {"text": "Footer text", "icon_url": "https://cdn.discordapp.com/embed/avatars/0.png"},
            "thumbnail": "https://picsum.photos/80/80",
            "image": "https://picsum.photos/400/200",
            "author": {"name": "discli bot", "icon_url": "https://cdn.discordapp.com/embed/avatars/1.png"},
            "fields": [
                {"name": "Inline 1", "value": "Value 1", "inline": True},
                {"name": "Inline 2", "value": "Value 2", "inline": True},
                {"name": "Inline 3", "value": "Value 3", "inline": True},
                {"name": "Full Width", "value": "This field takes the full width", "inline": False},
            ],
        })

    # Embed + buttons combo
    await send("send", channel_id=ch, content="**Embed Test 3/3** — Embed + Buttons:",
        embed={
            "title": "Action Required",
            "description": "Please approve or reject this request.",
            "color": "FEE75C",
        },
        components=[[
            {"type": "button", "label": "Approve", "style": "success", "custom_id": "btn_approve"},
            {"type": "button", "label": "Reject", "style": "danger", "custom_id": "btn_reject"},
        ]])


async def test_streaming(send, ctx, streams):
    ch = ctx.get("channel_id", ACTIVE_CHANNEL)
    msg_id = ctx.get("message_id")

    await send("stream_start", channel_id=ch, reply_to=msg_id)
    await asyncio.sleep(0.5)  # Wait for stream_id

    sid = streams.get("last")
    if not sid:
        await send("send", channel_id=ch, content="Error: no stream_id received")
        return

    text = "This message is being streamed word by word, just like an AI typing out a response in real-time. Pretty cool, right?"
    for word in text.split():
        await send("stream_chunk", stream_id=sid, content=word + " ")
        await asyncio.sleep(0.15)

    await send("stream_end", stream_id=sid)


if __name__ == "__main__":
    asyncio.run(main())

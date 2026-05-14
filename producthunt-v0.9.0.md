# Product Hunt Forum Post — discli v0.9.0

## Title

v0.9.0 is out: discli can now join Discord voice calls and transcribe them live

## Body

Hey everyone, posting an update to anyone who followed the launch.

v0.9.0 just shipped and it's the release I'm most excited about. The headline: discli can now sit in a Discord voice channel, transcribe every speaker live with their display names, and stream the transcript to disk or to your AI agent in real time. Meeting notes that write themselves, from the terminal.

### What's new in v0.9.0

- **Voice in, voice out.** New `voice` CLI: join, leave, speak (TTS), play, listen (STT), pause / resume, status, where, members.
- **Live transcription.** Plug in Deepgram, OpenAI Whisper, or local faster-whisper. Transcripts arrive as JSONL events you can pipe anywhere.
- **TTS providers.** ElevenLabs and OpenAI baked in. Your bot can actually talk back.
- **Interactive UIs.** New `interact` engine for modals, multi-step workflows, and live dashboards inside Discord, all driven from your CLI process.
- **`discli doctor`.** One command that checks your token, intents, voice deps, and FFmpeg setup before you waste an hour debugging.
- **Permission profiles** updated with `voice` and `interact` scopes so you can sandbox agents that have these new powers.
- **Docs.** New voice guide, meeting transcription use case, and a fully rebuilt README.

### What a transcriber looks like

```python
import json, subprocess

proc = subprocess.Popen(
    ["discli", "--json", "serve"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
)

for cmd in [
    {"action": "voice_connect", "channel_id": 1016638171854938152},
    {"action": "voice_listen", "stt": "deepgram"},
]:
    proc.stdin.write(json.dumps(cmd) + "\n")
proc.stdin.flush()

for line in proc.stdout:
    e = json.loads(line)
    if e.get("event") == "voice_speech_detected" and e.get("is_final"):
        print(f"{e['user_id']}: {e['text']}")
```

That's the whole loop. Pipe it into Claude, GPT, your own summarizer, a Notion page, a Slack channel, whatever you want.

### Links

- GitHub release: https://github.com/DevRohit06/discli/releases/tag/v0.9.0
- Install: `pip install -U discord-cli-agent`
- Voice guide: https://discli.dev/guides/voice
- Meeting transcription walkthrough: https://discli.dev/use-cases/meeting-transcription
- `discli doctor` reference: https://discli.dev/reference/cli-commands

### Tell me what you'd build

Genuinely curious what people will do with voice + JSONL. Ambient meeting summaries? Voice-controlled agents? A standup bot that listens and posts the recap? If you ship something with this, drop a link, I'd love to see it.

Cheers,
Rohit

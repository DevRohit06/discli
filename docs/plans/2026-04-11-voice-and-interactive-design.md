# Voice & Interactive Features Design

**Date:** 2026-04-11
**Status:** Approved
**Approach:** Layered Modules (engines separate from CLI/serve)

## Summary

Add full-duplex voice (TTS speak + STT listen/transcribe), audio playback, and rich interactive components (modals, multi-step workflows, persistent dashboards) to discli. Both CLI commands and serve mode JSONL actions for all features.

## Voice Engine

### Dependencies

Required:
- `PyNaCl` — discord.py voice encryption
- `discord-ext-voice-recv` — voice receive support (discord.py doesn't support it natively)
- `silero-vad` — voice activity detection
- `audioop-lts` — PCM audio manipulation (Python 3.13+ compatible)

TTS providers (optional extras):
- `elevenlabs` — best quality, ~200ms TTFB, streaming (recommended default)
- `openai` — solid middle ground
- `piper-tts` — local/offline, lightweight

STT providers (optional extras):
- `deepgram-sdk` — real-time WebSocket streaming, ~100-300ms (recommended default)
- `openai` — Whisper API, batch only
- `faster-whisper` — local, near-real-time with VAD

### Architecture (`src/discli/voice_engine.py`)

- **`VoiceEngine`** — connection pool (one voice client per guild), exposes async methods for connect/disconnect/move/speak/play/listen
- **`TTSProvider` protocol** — `async synthesize(text, voice, speed) -> AsyncIterator[bytes]` (streaming PCM chunks)
- **`STTProvider` protocol** — `async transcribe(audio_stream) -> AsyncIterator[TranscriptionResult]` (streaming partial + final results)
- **`AudioPlayer`** — per-connection queue-based player. Handles TTS output + file/URL playback. Supports interrupt priority.
- **`AudioListener`** — wraps discord-ext-voice-recv, per-user PCM buffers, silero-vad for speech segmentation, feeds segments to STT provider
- **`VoiceSession`** — full-duplex: simultaneous listen + speak on one connection

### Configuration (`~/.discli/config.json`)

```json
{
  "voice": {
    "tts_provider": "elevenlabs",
    "tts_voice": "default",
    "stt_provider": "deepgram",
    "vad_threshold": 0.5,
    "silence_duration_ms": 800,
    "playback_volume": 1.0
  }
}
```

API keys via env vars: `ELEVENLABS_API_KEY`, `DEEPGRAM_API_KEY`, `OPENAI_API_KEY`.

### CLI Commands (`commands/voice.py`)

- `discli voice join <channel>` / `leave` / `move` / `status`
- `discli voice speak <text> [--voice] [--speed]`
- `discli voice play <source> [--volume]` (file path or URL)
- `discli voice stop` / `pause` / `resume`
- `discli voice listen [--duration] [--continuous]`
- `discli voice converse [--channel]` — full duplex mode

### Serve Mode Actions

- `voice_connect`, `voice_disconnect`, `voice_move`
- `voice_speak`, `voice_play`, `voice_stop`, `voice_pause`, `voice_resume`
- `voice_listen_start`, `voice_listen_stop`
- `voice_set_config`

### Serve Mode Events

- `voice_transcription` — `{user_id, username, text, confidence, channel_id, is_partial}`
- `voice_playback_started` / `voice_playback_finished`
- `voice_connected` / `voice_disconnected`
- `voice_user_speaking` / `voice_user_silent`

## Interactive Engine

### Architecture (`src/discli/interact_engine.py`)

**Modals & Forms:**
- `Modal` class — builds Discord modals with text inputs (short/paragraph), validation rules
- Serve action: `modal_send {trigger_interaction_id, title, fields}`
- Serve event: `modal_submit {custom_id, user_id, values}`

**Multi-Step Workflows:**
- `Workflow` class — sequence of steps (message, select, modal, confirm), tracks user state per `(user_id, workflow_id)`
- Supports conditional branching based on user input
- Configurable per-step timeout
- Serve action: `workflow_start {user_id, channel_id, workflow_definition}` / `workflow_cancel`
- Serve events: `workflow_step_completed`, `workflow_finished`, `workflow_timeout`

**Persistent Dashboards:**
- `Dashboard` class — auto-updating message with embeds + components
- Pagination, role menus, live counters
- State in memory with optional JSON file persistence
- Serve action: `dashboard_create` / `dashboard_update` / `dashboard_delete`
- Serve event: `dashboard_interaction`

**Interaction Router:**
Central dispatcher for `on_interaction` events, routes by `custom_id` prefix:
- `modal:` → modal handler
- `wf:` → workflow handler
- `dash:` → dashboard handler
- `voice:` → voice engine

### CLI Commands (`commands/interact.py`)

- `discli interact modal <title> --field "Name:short:required" ...`
- `discli interact workflow <definition.json>`
- `discli interact dashboard create|update|delete|list`

## Integration

**Serve mode:** Both engines initialized lazily. Actions registered as thin handlers in serve.py's dispatch table. Events flow through existing JSONL emission system. Everything on the existing asyncio event loop.

**CLI:** Commands follow existing pattern (Click group -> async action -> `run_discord()`). Persistent commands (listen, converse) run until Ctrl+C or --duration.

**Security (security.py):**
- New permission scopes: `voice`, `interact`
- `readonly`: can view status but not connect/send
- `chat`: gets `interact` but not `voice`
- `full`: gets everything
- `moderation`: gets `voice` (monitoring) + `interact`
- All actions audit-logged

**Error handling:**
- Voice connection failures → clear error in JSONL/CLI
- Provider failures → fallback to next provider if available, otherwise error event
- Workflow timeouts → cleanup state + event

## Dependency Groups (`pyproject.toml`)

```toml
[project.optional-dependencies]
voice = ["PyNaCl", "discord-ext-voice-recv", "silero-vad", "audioop-lts", "elevenlabs", "deepgram-sdk"]
local-voice = ["PyNaCl", "discord-ext-voice-recv", "silero-vad", "audioop-lts", "piper-tts", "faster-whisper"]
openai-voice = ["PyNaCl", "discord-ext-voice-recv", "silero-vad", "audioop-lts", "openai"]
interact = []
dev = ["pytest", "pytest-asyncio"]
```

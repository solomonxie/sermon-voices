# English TTS backend: try VoiceStudio alongside XTTS v2

## Problem
Phase 3 (`src/process_translation.py`) generates the English cloned-voice
audio via Coqui XTTS v2, loaded in-process (`TTS.api`). We want to try
[VoiceStudio](https://github.com/debpalash/VoiceStudio) — a local,
open-source "ElevenLabs alternative" with voice cloning and 16 TTS engines
behind an OpenAI-compatible REST API — as an alternative backend, and
compare quality/speed before deciding whether to switch.

## Goals
- Add VoiceStudio as a second, selectable TTS backend for Phase 3.
- Keep today's XTTS v2 path as the default — this is a trial, not a
  confirmed migration.
- Reuse the existing flow: 60s speaker sample → cloned voice → chunked
  synthesis → concatenated `audio_en.mp3`.

## Non-goals
- Not touching ASR (Phase 1) or translation (Phase 3's LLM step).
- Not evaluating all 16 VoiceStudio engines — start with its default
  (OmniVoice).
- Not changing output directory layout or metadata schema.
- Not deciding the final default backend — that's Phase 4 of the plan.

## Options considered
1. **Keep XTTS v2 only** — no new dependency, but doesn't answer the
   question the user is asking (try VoiceStudio).
2. **Call VoiceStudio's local REST API** (Docker container, OpenAI-compatible
   `/v1/audio/speech`) from a new client module — decouples the heavy TTS
   runtime from this repo's Python/venv, easy to toggle. Cost: a service
   dependency (container must be running) and an unconfirmed voice-cloning
   endpoint (VoiceStudio's public docs cover synthesis, not profile
   creation — needs a short spike).
3. **Vendor VoiceStudio's engine code directly** — tighter integration, no
   server hop, but VoiceStudio is a full desktop app (React + FastAPI), not
   designed to be imported as a library. High integration cost for a trial.

## Decision
Option 2. New `src/tts_voicestudio.py` client talks to the local VoiceStudio
container over HTTP; Phase 3 picks a backend via a `TTS_BACKEND` env var
(default `xtts_v2`) so the existing pipeline is unaffected until someone
opts in.

## Risks / open questions
- Voice-profile-creation endpoint/schema isn't documented publicly — Phase 1
  of the implementation plan is a spike to find it (FastAPI auto-docs at
  `localhost:3900/docs`, or the VoiceStudio source).
- Zero-shot cloning quality from a ~60s Chinese-accented sample, on
  OmniVoice specifically, is unverified — that's the point of Phase 4.
- Container lifecycle: who starts/stops it (a `make` target vs. manual) is
  undecided — pick this in Phase 3.
- VoiceStudio's app is AGPL-3.0; we only call its local HTTP API, not
  embedding its code, but worth a one-line note in the README.

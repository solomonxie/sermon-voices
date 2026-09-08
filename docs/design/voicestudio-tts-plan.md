# Implementation plan: VoiceStudio TTS backend

See `docs/design/voicestudio-tts.md` for why.

## Phase 1: Spike VoiceStudio's API surface
The voice-cloning/profile-creation endpoint isn't in VoiceStudio's public
docs (only `/v1/audio/speech` synthesis is). Everything downstream depends
on knowing that shape, so it comes first.

- [ ] T1.1 Run the VoiceStudio Docker container locally (`docker run -d -p
      127.0.0.1:3900:3900 -v omnivoice-data:/app/omnivoice_data --name
      voicestudio palashdeb/omnivoice-studio:stable`); confirm
      `/v1/audio/speech` responds with a stock/default voice — depends: none
- [ ] T1.2 Find and document the voice-profile creation endpoint (request/
      response shape, form fields, reference-audio limits) by reading
      `localhost:3900/docs` (FastAPI auto-docs) or the VoiceStudio repo
      source — write findings into this doc's Phase 1 notes — depends: T1.1
- [ ] T1.3 Manually clone a voice from an existing sermon's `_sample.mp3`
      and synthesize one English chunk end-to-end (curl or a throwaway
      script); listen and compare against that sermon's existing
      `audio_en.mp3` (XTTS v2) — depends: T1.2

## Phase 2: Client wrapper
Isolate the VoiceStudio calls behind one module so the trial doesn't touch
the existing XTTS v2 code path.

- [ ] T2.1 Add `src/tts_voicestudio.py`: `create_voice_profile(speaker_wav)
      -> profile_id` and `synthesize(text, profile_id, out_path)`, per the
      Phase 1 findings — depends: T1.2
- [ ] T2.2 Reuse `split_text()` and the pydub chunk-concat pattern already
      in `src/process_translation.py` (extract to `src/common.py` if both
      backends need it) — depends: T2.1

## Phase 3: Wire into the pipeline
Make the backend selectable without changing default behavior — the XTTS v2
path stays the known-good baseline until Phase 4 says otherwise.

- [ ] T3.1 Add a `TTS_BACKEND` env var (default `xtts_v2`, opt-in
      `voicestudio`) read in `process_tts()`, dispatching to
      `tts_voicestudio.synthesize()` when set — depends: T2.2
- [ ] T3.2 Decide + document container lifecycle (manual `docker run` vs. a
      `make` target) — depends: T1.1
- [ ] T3.3 Update `.env.example`, `README.md`, `DESIGN.md` with the new
      backend option and its Docker prerequisite — depends: T3.1, T3.2

## Phase 4: Evaluate
Compare against the XTTS v2 baseline before touching the default.

- [ ] T4.1 Re-run Phase 3 for 2-3 already-processed sermons under both
      backends; collect `audio_en.mp3` samples side by side — depends: T3.1
- [ ] T4.2 Decide the default backend on quality/speed/resource tradeoffs.
      If VoiceStudio wins, flip the default and drop the XTTS v2 path in a
      follow-up (out of scope here) — depends: T4.1

#!/usr/bin/env python3
"""Transcribe output/ episodes to timestamped captions and publish them beside the S3 audio.

Local ASR only (FunASR Paraformer-zh + FSMN-VAD + CT-Transformer punctuation, Bible
hotword biasing). For each episode three artifacts are written into its local folder
and the two caption files are uploaded next to the already-published .mp3:

  <seq>_<title>.vtt   canonical transcript   text/vtt
  <seq>_<title>.lrc   lyrics-aware players   text/plain
  asr_segments.json   raw timestamps, local only (lets formats be rebuilt without re-ASR)

Resumable at two levels: an episode whose .vtt and .lrc already exist on S3 is skipped,
and within an episode each ~10min window is checkpointed to asr_segments.partial.json.

The MPS allocator never returns the pool it grows during inference (~3.7GB per 20min
window, unaffected by batch size), so a long-lived worker inevitably OOMs and every later
episode then fails too. Instead the worker stops once the pool would exceed
--mem-ceiling-gb and exits 75; run_captions.sh restarts it until it exits 0.

Usage:
  scripts/run_captions.sh                      # the real run: restarts until complete
  venv/bin/python3 scripts/transcribe_to_captions.py [--only DIR/DIR] [--speaker NAME]
      [--limit N] [--device mps|cpu] [--mem-ceiling-gb N] [--local-only] [--force] [--dry-run]
"""
import argparse
import datetime
import gc
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from publish_bible_audio_to_s3 import BUCKET, SPEAKERS, iter_episodes, s3_key, s3_uri

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOTWORD_FILE = os.path.join(ROOT, "output", "bible_hotwords_combined_zh.txt")
LANG = "zh-CN"
LOG_DIR = "/tmp/sermon-captions"
WAV_CACHE = "/tmp/sermon-captions/wav"

EXIT_MORE_WORK = 75
WINDOW_SECS = 1200.0
WINDOW_SEARCH = 45.0
MAX_CUE_CHARS = 28
MAX_CUE_SECS = 8.0
MIN_CUE_SECS = 1.0
SPLIT_PUNCT = "，,、；;"
END_PUNCT = "。？！?!"


_log_fh = None
_trace_fh = None


def log(msg):
    line = f"{datetime.datetime.now():%H:%M:%S} {msg}"
    print(line, flush=True)
    if _log_fh:
        _log_fh.write(line + "\n")
        _log_fh.flush()


def trace(**fields):
    if _trace_fh:
        fields["at"] = datetime.datetime.now().isoformat(timespec="seconds")
        _trace_fh.write(json.dumps(fields, ensure_ascii=False) + "\n")
        _trace_fh.flush()


def open_logs():
    global _log_fh, _trace_fh
    os.makedirs(LOG_DIR, exist_ok=True)
    path = os.path.join(LOG_DIR, "captions.log")
    _trace_fh = open(os.path.join(LOG_DIR, "progress.jsonl"), "a", encoding="utf-8")
    return path


def remote_caption_keys():
    """One paginated listing instead of a head-object per episode."""
    keys = set()
    token = None
    while True:
        cmd = ["aws", "s3api", "list-objects-v2", "--bucket", BUCKET, "--prefix", "bible-audio/",
               "--query", "{k:Contents[].Key,t:NextContinuationToken}", "--output", "json"]
        if token:
            cmd += ["--starting-token", token]
        out = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
        keys.update(k for k in (out.get("k") or []) if k.endswith(".vtt") or k.endswith(".lrc"))
        token = out.get("t")
        if not token:
            return keys


def fmt_hms(secs):
    h, rem = divmod(int(max(secs, 0)), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}m{s:02d}s"


def load_s3_credentials():
    for line in open(os.path.join(ROOT, ".env"), encoding="utf-8"):
        line = line.strip()
        if line.startswith("S3_") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)
    for src, dst in (("S3_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID"), ("S3_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY")):
        if os.environ.get(src):
            os.environ[dst] = os.environ[src]
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")


def build_model(device):
    os.environ["MODELSCOPE_CACHE"] = os.path.expanduser("~/llm_models/modelscope")
    os.environ["HF_HOME"] = os.path.expanduser("~/llm_models/huggingface")
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    import logging

    logging.getLogger().setLevel(logging.ERROR)
    from funasr import AutoModel

    return AutoModel(
        model="paraformer-zh",
        vad_model="fsmn-vad",
        punc_model="ct-punc",
        device=device,
        disable_update=True,
        disable_pbar=True,
        disable_log=True,
        vad_kwargs={"max_single_segment_time": 20000},
    )


def cached_wav(key):
    """A worker usually restarts mid-episode; without this the mp3 is re-decoded each time."""
    import hashlib

    os.makedirs(WAV_CACHE, exist_ok=True)
    return os.path.join(WAV_CACHE, hashlib.sha1(key.encode()).hexdigest() + ".wav")


def sweep_wav_cache(max_age_hours=12):
    if not os.path.isdir(WAV_CACHE):
        return
    cutoff = time.time() - max_age_hours * 3600
    for name in os.listdir(WAV_CACHE):
        path = os.path.join(WAV_CACHE, name)
        if os.path.getmtime(path) < cutoff:
            os.remove(path)


def decode_to_wav(mp3_path, wav_path):
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", mp3_path,
         "-ar", "16000", "-ac", "1", "-f", "wav", wav_path],
        check=True,
    )


def audio_duration(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def window_cuts(wav_path, duration):
    """Cut points near each WINDOW_SECS mark, snapped to the quietest spot nearby.

    Long episodes (some run 150min) exhaust MPS memory in a single pass, so they are
    transcribed in windows. Snapping to silence keeps cuts out of the middle of a word.
    """
    import numpy as np
    import soundfile as sf

    cuts = [0.0]
    t = WINDOW_SECS
    while duration - t > WINDOW_SECS / 2:
        lo, hi = max(t - WINDOW_SEARCH, cuts[-1] + 30.0), min(t + WINDOW_SEARCH, duration)
        try:
            audio, sr = sf.read(wav_path, start=int(lo * 16000), stop=int(hi * 16000), dtype="float32")
            hop = sr // 10
            frames = audio[: len(audio) // hop * hop].reshape(-1, hop)
            quietest = int(np.argmin(np.abs(frames).mean(axis=1)))
            cuts.append(lo + (quietest + 0.5) * hop / sr)
        except Exception:
            cuts.append(t)
        t = cuts[-1] + WINDOW_SECS
    cuts.append(duration)
    return cuts


class Budget:
    """Stops the worker before the MPS pool gets big enough to push the machine into swap.

    Pool size is the real constraint, not audio length, so it is polled directly; the
    audio limit is only a fallback for --device cpu, which does not leak.
    """

    def __init__(self, limit_secs, ceiling_gb):
        self.limit, self.ceiling, self.spent = limit_secs, ceiling_gb, 0.0
        self.prev = 0.0
        self.step = 0.0

    def baseline(self):
        """Call once the model is resident; before that the pool reads 0 and the first
        window's growth would wrongly include the model's own footprint."""
        self.prev = self.pool_gb()

    def spend(self, secs):
        self.spent += secs

    def note_window(self):
        """Track per-window growth so the ceiling is a peak, not a floor it overshoots."""
        now = self.pool_gb()
        self.step = max(self.step, now - self.prev)
        self.prev = now

    def pool_gb(self):
        import torch

        if hasattr(torch, "mps") and torch.backends.mps.is_available():
            return torch.mps.driver_allocated_memory() / 2**30
        return 0.0

    def exhausted(self):
        return self.pool_gb() + max(self.step, 0.5) >= self.ceiling or self.spent >= self.limit


class BudgetReached(Exception):
    """Raised to end the worker cleanly so a fresh one can reclaim the MPS pool."""


def transcribe(model, wav_path, duration, partial_path, budget):
    kwargs = {"batch_size_s": 200, "sentence_timestamp": True}
    if os.path.isfile(HOTWORD_FILE):
        kwargs["hotword"] = HOTWORD_FILE

    cuts = window_cuts(wav_path, duration)
    sentences, first = [], 0
    if os.path.isfile(partial_path):
        saved = json.load(open(partial_path, encoding="utf-8"))
        if saved.get("cuts") == cuts:
            sentences, first = saved["sentences"], saved["done"]
            log(f"      resuming at window {first + 1}/{len(cuts) - 1}")

    for i, (start, end) in enumerate(zip(cuts, cuts[1:])):
        if i < first:
            continue
        if end - start < 1.0:
            continue
        if budget.exhausted():
            json.dump({"cuts": cuts, "done": i, "sentences": sentences},
                      open(partial_path, "w", encoding="utf-8"), ensure_ascii=False)
            raise BudgetReached(f"window {i + 1}/{len(cuts) - 1}, pool {budget.pool_gb():.1f}GB")
        chunk = wav_path + f".{int(start)}.wav"
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}",
                        "-t", f"{end - start:.3f}", "-i", wav_path, "-c", "copy", chunk], check=True)
        try:
            res = model.generate(input=chunk, **kwargs)
            offset = int(start * 1000)
            for sent in res[0].get("sentence_info") or []:
                sent["start"] += offset
                sent["end"] += offset
                sent["timestamp"] = [[a + offset, b + offset] for a, b in sent.get("timestamp") or []]
                sentences.append(sent)
            del res
        finally:
            os.path.exists(chunk) and os.remove(chunk)
            release_memory()
        budget.spend(end - start)
        budget.note_window()
        json.dump({"cuts": cuts, "done": i + 1, "sentences": sentences},
                  open(partial_path, "w", encoding="utf-8"), ensure_ascii=False)
    return sentences


def release_memory():
    """MPS does not reclaim between episodes on its own; without this a long run OOMs."""
    gc.collect()
    import torch

    if hasattr(torch, "mps") and torch.backends.mps.is_available():
        torch.mps.empty_cache()


def split_sentence(sentence):
    """Break an over-long sentence at internal punctuation, keeping token timestamps."""
    text, stamps = sentence["text"], sentence.get("timestamp") or []
    if len(text) <= MAX_CUE_CHARS and (sentence["end"] - sentence["start"]) / 1000.0 <= MAX_CUE_SECS:
        return [sentence]

    pieces, buf, tok = [], "", 0
    piece_start = sentence["start"]
    for ch in text:
        buf += ch
        is_token = ch not in SPLIT_PUNCT and ch not in END_PUNCT
        if is_token:
            tok += 1
        if ch in SPLIT_PUNCT and len(buf) >= MAX_CUE_CHARS // 2:
            end = stamps[tok - 1][1] if 0 < tok <= len(stamps) else sentence["end"]
            pieces.append({"text": buf, "start": piece_start, "end": end})
            buf, piece_start = "", end
    if buf.strip():
        pieces.append({"text": buf, "start": piece_start, "end": sentence["end"]})
    return pieces or [sentence]


def build_cues(sentences, duration):
    cues = []
    for s in sentences:
        for piece in split_sentence(s):
            text = piece["text"].strip()
            if text:
                cues.append({"text": text, "start": piece["start"] / 1000.0, "end": piece["end"] / 1000.0})

    merged = []
    for cue in cues:
        prev = merged[-1] if merged else None
        too_short = prev and (prev["end"] - prev["start"]) < MIN_CUE_SECS
        fits = prev and len(prev["text"]) + len(cue["text"]) <= MAX_CUE_CHARS
        if too_short and fits and cue["end"] - prev["start"] <= MAX_CUE_SECS:
            prev["text"] += cue["text"]
            prev["end"] = cue["end"]
        else:
            merged.append(cue)

    for i, cue in enumerate(merged):
        limit = merged[i + 1]["start"] if i + 1 < len(merged) else duration
        if cue["end"] <= cue["start"]:
            cue["end"] = min(cue["start"] + MIN_CUE_SECS, limit)
        cue["end"] = min(max(cue["end"], cue["start"] + 0.2), max(limit, cue["start"] + 0.2))
    return merged


def vtt_time(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def lrc_time(t):
    m, s = divmod(max(t, 0), 60)
    return f"[{int(m):02d}:{s:05.2f}]"


def render_vtt(cues, meta):
    head = ["WEBVTT", "", f"NOTE {meta['title']} — {meta['preacher']} / {meta['series']} [{LANG}]", ""]
    body = []
    for i, cue in enumerate(cues, 1):
        body += [str(i), f"{vtt_time(cue['start'])} --> {vtt_time(cue['end'])}", cue["text"], ""]
    return "\n".join(head + body)


def render_lrc(cues, meta, duration):
    m, s = divmod(duration, 60)
    lines = [
        f"[ti:{meta['title']}]",
        f"[ar:{meta['preacher']}]",
        f"[al:{meta['series']}]",
        "[by:sermon-voices]",
        f"[length:{int(m):02d}:{int(s):02d}]",
        "",
    ]
    lines += [f"{lrc_time(c['start'])}{c['text']}" for c in cues]
    lines.append(lrc_time(duration))
    return "\n".join(lines) + "\n"


def upload(path, key, content_type, dry_run):
    if dry_run:
        log(f"      [dry-run] -> {s3_uri(key)} ({content_type})")
        return
    subprocess.run(
        ["aws", "s3", "cp", "--only-show-errors", "--content-type", content_type, path, s3_uri(key)],
        check=True,
    )


def process(model, edir, apath, meta, key, args, budget):
    base = os.path.splitext(os.path.basename(key))[0]
    vtt_path = os.path.join(edir, base + ".vtt")
    lrc_path = os.path.join(edir, base + ".lrc")
    json_path = os.path.join(edir, "asr_segments.json")
    partial_path = os.path.join(edir, "asr_segments.partial.json")

    duration = audio_duration(apath)
    if os.path.isfile(json_path) and not args.force:
        sentences = json.load(open(json_path, encoding="utf-8"))["sentences"]
        log("      reusing asr_segments.json")
    else:
        wav_path = cached_wav(key)
        if not os.path.isfile(wav_path):
            decode_to_wav(apath, wav_path + ".part")
            os.replace(wav_path + ".part", wav_path)
        sentences = transcribe(model, wav_path, duration, partial_path, budget)
        json.dump({"duration": duration, "sentences": sentences}, open(json_path, "w", encoding="utf-8"),
                  ensure_ascii=False)
        for stale in (partial_path, wav_path):
            os.path.exists(stale) and os.remove(stale)

    cues = build_cues(sentences, duration)
    open(vtt_path, "w", encoding="utf-8").write(render_vtt(cues, meta))
    open(lrc_path, "w", encoding="utf-8").write(render_lrc(cues, meta, duration))
    if not args.local_only:
        upload(vtt_path, os.path.splitext(key)[0] + ".vtt", "text/vtt; charset=utf-8", args.dry_run)
        upload(lrc_path, os.path.splitext(key)[0] + ".lrc", "text/plain; charset=utf-8", args.dry_run)
    return duration, len(cues)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--speaker", choices=SPEAKERS)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--device", default="mps", choices=["mps", "cpu"])
    ap.add_argument("--mem-ceiling-gb", type=float, default=12.0,
                    help="restart before the pool would exceed this; ~12 gives a 10GB peak")
    ap.add_argument("--max-audio-secs", type=float, default=14400.0,
                    help="fallback stop for --device cpu, which does not leak")
    ap.add_argument("--local-only", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    load_s3_credentials()
    open_logs()
    sweep_wav_cache()
    log(f"trace: {LOG_DIR}/progress.jsonl")

    episodes = list(iter_episodes(args.only, args.speaker))
    remote = set() if args.local_only else remote_caption_keys()
    log(f"{len(episodes)} local episodes; {len(remote)} caption objects already on S3")

    todo = []
    for e in episodes:
        meta = json.load(open(e[4], encoding="utf-8"))
        key = s3_key(meta, e[2])
        stem = os.path.splitext(key)[0]
        if not args.force and not args.local_only and f"{stem}.vtt" in remote and f"{stem}.lrc" in remote:
            continue
        todo.append((e, meta, key))
    skipped = len(episodes) - len(todo)
    if args.limit:
        todo = todo[: args.limit]
    log(f"skipping {skipped} already published; {len(todo)} to transcribe")
    trace(event="start", todo=len(todo), skipped=skipped, device=args.device)

    model = None
    done = failed = 0
    audio_secs = 0.0
    budget = Budget(args.max_audio_secs, args.mem_ceiling_gb)
    t_start = time.time()

    for i, ((speaker, series, ep, edir, mpath, apath), meta, key) in enumerate(todo, 1):
        log(f"[{i}/{len(todo)}] {key}")
        if model is None:
            log(f"      loading model on {args.device} ...")
            model = build_model(args.device)
            budget.baseline()
        t0 = time.time()
        try:
            duration, ncues = process(model, edir, apath, meta, key, args, budget)
            done += 1
            audio_secs += duration
            el = time.time() - t0
            elapsed = time.time() - t_start
            rate = elapsed / i
            log(f"      {ncues} cues, {fmt_hms(duration)} audio in {el:.0f}s "
                f"(rtf {el / duration:.3f}) | {done} ok / {failed} fail / {len(todo) - i} left "
                f"| eta {fmt_hms(rate * (len(todo) - i))}")
            trace(event="ok", key=key, secs=round(el, 1), audio=round(duration, 1), cues=ncues,
                  done=done, failed=failed, left=len(todo) - i)
        except BudgetReached as e:
            log(f"      checkpointed ({e}); restarting worker to reclaim memory")
            trace(event="budget", key=key)
            sys.exit(EXIT_MORE_WORK)
        except Exception as e:
            failed += 1
            log(f"      [FAIL] {type(e).__name__}: {e}")
            trace(event="fail", key=key, error=f"{type(e).__name__}: {e}")
            if "out of memory" in str(e):
                log("      OOM: pool is unrecoverable in-process, restarting worker")
                sys.exit(EXIT_MORE_WORK)
        finally:
            release_memory()

        if budget.exhausted():
            log(f"      pool {budget.pool_gb():.1f}GB after {fmt_hms(budget.spent)}; restarting worker")
            trace(event="budget", key=key)
            sys.exit(EXIT_MORE_WORK)

    log(f"finished: done={done} skipped={skipped} failed={failed} "
        f"audio={fmt_hms(audio_secs)} wall={fmt_hms(time.time() - t_start)}")
    trace(event="end", done=done, skipped=skipped, failed=failed)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

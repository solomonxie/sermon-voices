#!/usr/bin/env python3
"""Embed ID3 tags into output/{hua-xian,stephen-tong} episodes in place.

Same tags as publish_bible_audio_to_s3.py writes to its S3 copies, applied to
the local original.mp3 instead. ffmpeg -c copy (no re-encode), written to a
temp beside the target then atomically renamed, so an interrupt leaves the
original untouched. Original mtime is preserved. Already-tagged files are
skipped, so a killed run can simply be re-run.

Usage:
  venv/bin/python3 scripts/embed_tags_in_place.py [--only DIR/DIR] [--speaker NAME] [--force] [--dry-run]
"""
import argparse
import json
import os
import subprocess
import sys

from publish_bible_audio_to_s3 import SPEAKERS, build_tags, iter_episodes

PROBE_KEYS = ("artist", "album", "title")


def current_tags(path):
    r = subprocess.run(
        ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return {}
    return json.loads(r.stdout).get("format", {}).get("tags", {})


def already_tagged(path, tags):
    have = {k.lower(): v for k, v in current_tags(path).items()}
    return all(have.get(k) == tags[k] for k in PROBE_KEYS if k in tags)


def retag(path, tags):
    tmp = f"{path}.retag.tmp.mp3"
    stat = os.stat(path)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", path, "-c", "copy", "-id3v2_version", "3"]
    for k, v in tags.items():
        cmd += ["-metadata", f"{k}={v}"]
    cmd.append(tmp)
    try:
        subprocess.run(cmd, check=True)
        os.replace(tmp, path)
        os.utime(path, (stat.st_atime, stat.st_mtime))
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--speaker", choices=SPEAKERS)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    total = tagged = skipped = failed = 0
    for speaker, series, ep, edir, mpath, apath in iter_episodes(args.only, args.speaker):
        total += 1
        tags = build_tags(json.load(open(mpath, encoding="utf-8")))
        label = f"{speaker}/{series}/{ep}"
        if args.dry_run:
            print(f"[dry-run] {label} tags={tags}")
            continue
        if not args.force and already_tagged(apath, tags):
            skipped += 1
            print(f"[skip] {label} (tagged)")
            continue
        try:
            retag(apath, tags)
            tagged += 1
            print(f"[ok] {label}")
        except subprocess.CalledProcessError as e:
            failed += 1
            print(f"[FAIL] {label}: {e}", file=sys.stderr)

    print(f"\ntotal={total} tagged={tagged} skipped={skipped} failed={failed}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

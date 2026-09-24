#!/usr/bin/env python3
"""Tag and upload output/{hua-xian,stephen-tong} episodes to S3.

Reads AWS creds from env (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY), never
from this file. One episode at a time: ffmpeg tags a scratch temp copy,
`aws s3 cp` uploads it, temp is removed. Skips keys already on S3 (resumable).

Usage:
  venv/bin/python3 scripts/publish_bible_audio_to_s3.py [--only DIR/DIR] [--speaker NAME] [--force] [--dry-run]

  --only hua-xian/five-solas   restrict to one local series folder (testing)
  --speaker stephen-tong       restrict to one speaker (all their series)
  --force                      re-upload even if the S3 key already exists
  --dry-run                    print planned S3 keys/tags, do nothing
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(ROOT, "output")
SPEAKERS = ["hua-xian", "stephen-tong"]
BUCKET = "slmx-archives2"
PREFIX = "bible-audio"
GENRE = "Christian Sermon"


def iter_episodes(only=None, speaker_filter=None):
    for speaker in SPEAKERS:
        if speaker_filter and speaker != speaker_filter:
            continue
        base = os.path.join(OUTPUT_DIR, speaker)
        for series in sorted(os.listdir(base)):
            if only and f"{speaker}/{series}" != only:
                continue
            sdir = os.path.join(base, series)
            if not os.path.isdir(sdir):
                continue
            for ep in sorted(os.listdir(sdir)):
                edir = os.path.join(sdir, ep)
                mpath = os.path.join(edir, "metadata.json")
                apath = os.path.join(edir, "original.mp3")
                if os.path.isfile(mpath) and os.path.isfile(apath):
                    yield speaker, series, ep, edir, mpath, apath


def build_tags(meta):
    tags = {
        "artist": meta["preacher"],
        "album": meta["series"],
        "title": meta["title"],
        "track": str(int(meta["sequence"])),
        "genre": GENRE,
    }
    created_at = meta.get("created_at", "00000000")
    if created_at and created_at != "00000000":
        tags["date"] = created_at[:4]
    scripture = meta.get("scripture", "")
    if scripture and not scripture.startswith("Unknown Book"):
        tags["comment"] = scripture
    return tags


def s3_key(meta, ep):
    seq = str(meta["sequence"]).strip()
    title = meta["title"].strip()
    return f"{PREFIX}/{meta['preacher']}/{meta['series']}/{seq}_{title}.mp3"


def s3_uri(key):
    return f"s3://{BUCKET}/{key}"


def exists_on_s3(key):
    r = subprocess.run(
        ["aws", "s3api", "head-object", "--bucket", BUCKET, "--key", key],
        capture_output=True,
    )
    return r.returncode == 0


def tag_and_upload(apath, key, tags, dry_run):
    if dry_run:
        print(f"[dry-run] {apath} -> {s3_uri(key)} tags={tags}")
        return
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", apath, "-c", "copy", "-id3v2_version", "3"]
        for k, v in tags.items():
            cmd += ["-metadata", f"{k}={v}"]
        cmd.append(tmp_path)
        subprocess.run(cmd, check=True)
        subprocess.run(["aws", "s3", "cp", "--only-show-errors", tmp_path, s3_uri(key)], check=True)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--speaker", choices=SPEAKERS)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.dry_run and not (os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY")):
        sys.exit("AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY must be set in the environment")

    total = uploaded = skipped = failed = 0
    for speaker, series, ep, edir, mpath, apath in iter_episodes(args.only, args.speaker):
        total += 1
        meta = json.load(open(mpath, encoding="utf-8"))
        key = s3_key(meta, ep)
        if not args.force and not args.dry_run and exists_on_s3(key):
            skipped += 1
            print(f"[skip] {key} (exists)")
            continue
        tags = build_tags(meta)
        try:
            tag_and_upload(apath, key, tags, args.dry_run)
            uploaded += 1
            print(f"[ok] {key}")
        except subprocess.CalledProcessError as e:
            failed += 1
            print(f"[FAIL] {key}: {e}", file=sys.stderr)

    print(f"\ntotal={total} uploaded={uploaded} skipped={skipped} failed={failed}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()

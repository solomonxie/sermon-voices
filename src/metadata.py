import os
import re
import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from .models import PreacherMetadata, Sermon, SeriesInfo, ScriptureReference, AudioMetadata, PreacherInfo
from .bible_books import get_english_name

# Required libraries
try:
    from mutagen.mp3 import MP3
except ImportError:
    MP3 = None

from .llm import LLMService

def calculate_hash(file_path: str) -> str:
    """Calculates SHA-256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def extract_audio_info(file_path: str) -> Dict[str, Any]:
    """Extracts duration, bitrate, etc. using mutagen."""
    if not MP3:
        return {}
    try:
        audio = MP3(file_path)
        return {
            "duration_seconds": int(audio.info.length),
            "bitrate": audio.info.bitrate // 1000,
            "sample_rate": audio.info.sample_rate,
            "channels": audio.info.channels,
            "format": "mp3"
        }
    except Exception as e:
        print(f"Error extracting audio info from {file_path}: {e}")
        return {}

def parse_file_path(file_path: str, llm: Optional[LLMService] = None) -> Optional[Dict[str, Any]]:
    """Generic file path parser with LLM fallback."""
    filename = os.path.basename(file_path)
    
    # 1. Try a broad regex for common patterns (YYMMDD_Title_Num_Verse) on filename
    # Pattern: 20230621传道书042（7章6节）烧荆棘的爆声.mp3
    p1 = r'(\d{8})([^0-9]+)(\d+)(?:（(\d+)章(\d+)节）)?(.+)\.mp3'
    m1 = re.search(p1, filename)
    if m1:
        date_str, series, num, ch, vs, title = m1.groups()
        return {
            "date": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
            "series_name": series.strip(),
            "series_number": int(num),
            "chapter": int(ch) if ch else 0,
            "verse": int(vs) if vs else 0,
            "title": title.strip()
        }

    # 2. Try another common pattern (Series Num.mp3)
    p2 = r'([^0-9]+)(\d+)\.mp3'
    m2 = re.search(p2, filename)
    if m2:
        series, num = m2.groups()
        return {
            "series_name": series.strip(),
            "series_number": int(num),
            "title": series.strip()
        }

    # 3. LLM Fallback (now with full path context)
    if llm:
        print(f"  ? Fallback to LLM for path: {file_path}")
        data = llm.extract_sermon_metadata(file_path)
        if data:
            # Normalize fields to match our expectations
            return {
                "preacher_name": str(data.get("preacher_name") or ""),
                "title": str(data.get("title") or ""),
                "title_en": str(data.get("title_en") or ""),
                "series_name": str(data.get("series_name") or ""),
                "series_name_en": str(data.get("series_name_en") or ""),
                "series_number": int(data.get("series_number") or 0),
                "chapter": int(data.get("chapter") or 0),
                "verse": int(data.get("verse") or data.get("verse_start") or 0),
                "verse_end": int(data.get("verse_end") or 0),
                "date": str(data.get("date") or "")
            }

    # 4. Minimal fallback
    name = os.path.splitext(filename)[0]
    return {
        "title": name,
        "series_name": "Misc"
    }

def extract_preacher_metadata(preacher_dir: str, llm: Optional[LLMService] = None) -> PreacherMetadata:
    preacher_name = os.path.basename(preacher_dir)
    preacher_name_en = preacher_name
    if llm and any('\u4e00' <= c <= '\u9fff' for c in preacher_name):
        preacher_name_en = llm.translate_to_english(preacher_name)
    
    preacher_info = PreacherInfo(
        name=preacher_name,
        name_en=preacher_name_en
    )
    metadata = PreacherMetadata(
        preacher=preacher_info,
        last_updated=datetime.utcnow().isoformat() + "Z"
    )

    for root, _, files in os.walk(preacher_dir):
        for file in files:
            if file.endswith(".mp3"):
                file_path = os.path.join(root, file)
                
                # Use generic parser with LLM fallback
                sermon_data = parse_file_path(file_path, llm=llm)
                
                if sermon_data:
                    # Use incremental-like ID based on counter instead of hash if requested
                    # But for extraction, we still might want hashes to avoid duplicates.
                    # User specifically asked for integer IDs in the refined json.
                    # I'll stick to hashes for extraction (safer) and let the refinement script do the 1, 2, 3...
                    sermon_id = hashlib.md5(file_path.encode()).hexdigest()[:12]
                    audio_info = extract_audio_info(file_path)
                    
                    # Improve context-aware extraction
                    title = sermon_data.get("title", "")
                    title_en = sermon_data.get("title_en", "")
                    series_name = sermon_data.get("series_name", "")
                    series_name_en = sermon_data.get("series_name_en", "")
                    
                    # If we have an LLM, we should probably use a better prompt for the initial extraction too
                    # But the user wants a separate refinement script for existing ones.
                    # For future ones, let's make it better:
                    if llm and not title_en:
                        # Use the refinement logic even for new ones
                        summary_dict = {"title": title, "series": {"name": series_name}}
                        refined = llm.refine_sermon_metadata(summary_dict, preacher_name)
                        if refined:
                            title_en = refined.get("title_en", "")
                            series_name_en = refined.get("series_en", "")
                            sermon_data["chapter"] = refined.get("chapter", 0)
                            sermon_data["verse"] = refined.get("verse_start", 0)
                            sermon_data["verse_end"] = refined.get("verse_end", 0)

                    if not series_name_en:
                        series_name_en = get_english_name(series_name) or ""

                    sermon = Sermon(
                        id=sermon_id,
                        original_path=os.path.relpath(file_path, "."),
                        audio_hash=calculate_hash(file_path),
                        title=title,
                        title_en=title_en,
                        date=sermon_data.get("date", ""),
                        duration_seconds=audio_info.get("duration_seconds", 0),
                        file_size_bytes=os.path.getsize(file_path),
                        series=SeriesInfo(
                            name=series_name,
                            name_en=series_name_en,
                            number=sermon_data.get("series_number", 0)
                        ),
                        audio_metadata=AudioMetadata(**audio_info)
                    )
                    
                    # Add scripture reference if parsed
                    if sermon_data.get("chapter"):
                        sermon.scripture_references.append(ScriptureReference(
                            book=series_name_en,
                            book_zh=series_name,
                            chapter=sermon_data.get("chapter", 0),
                            verse_start=sermon_data.get("verse", 0),
                            verse_end=sermon_data.get("verse_end") or sermon_data.get("verse", 0)
                        ))
                    
                    metadata.sermons[sermon_id] = sermon
                    metadata.preacher.total_sermons += 1

    return metadata

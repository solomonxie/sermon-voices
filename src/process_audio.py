import os
import re
import json
import sqlite3
import argparse
import subprocess
from datetime import timedelta

import torch
from pydub import AudioSegment
from funasr import AutoModel
from dotenv import load_dotenv

load_dotenv()

from src.common import ask_llm, safe_remove
from src.constants import BIBLE_EN_TO_ZH, ZH_TO_ABBREV_MAP

# Audio processing config
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["MODELSCOPE_CACHE"] = os.path.expanduser('~/llm_models/modelscope')
BIBLE_DB_PATH = "output/bible_rag.db"

def main(audio_path) -> None:

    print(f"\n--- Phase 2: Audio Transcription & Refinement (SenseVoice) ---")
    sermon_dir = os.path.dirname(audio_path)
    final_lyric = os.path.join(sermon_dir, "transcription_zh_lyric.txt")
    final_zh = os.path.join(sermon_dir, "transcript_zh.txt")
    llm_log_path = os.path.join(sermon_dir, "llm_log.txt")

    if os.path.exists(final_zh):
        print(f"✅ Already processed: {final_zh}")
        return

    # 0. Load Metadata Profile
    metadata = load_sermon_context(sermon_dir)
    print(f"📝 Loaded context: {metadata.get('preacher')} - {metadata.get('title')}")

    # 1. Preprocess
    cleaned_audio_path = preprocess_audio(audio_path)

    # 2. VAD Split -> ~1min chunks
    chunks = vad_split(cleaned_audio_path)

    # 3. transcribe -> error picking -> refine -> finalize
    transcribe_and_refine(cleaned_audio_path, chunks, sermon_dir, metadata, llm_log_path)

    print(f"✅ Workflow complete. Results saved to:\n   - {final_lyric}\n   - {final_zh}")

def load_sermon_context(sermon_dir: str) -> dict:
    """Load metadata.json and profile.json for LLM context."""
    context = {}
    
    # Sermon-specific metadata
    meta_path = os.path.join(sermon_dir, "metadata.json")
    if os.path.exists(meta_path):
        with open(meta_path, 'r', encoding='utf-8') as f:
            context.update(json.load(f))
            
    # Preacher profile
    preacher_dir = os.path.dirname(os.path.dirname(sermon_dir))
    profile_path = os.path.join(preacher_dir, "profile.json")
    if os.path.exists(profile_path):
        with open(profile_path, 'r', encoding='utf-8') as f:
            profile = json.load(f)
            context["profile"] = profile
            
    return context

def preprocess_audio(audio_path: str) -> str:
    """Preprocess audio using ffmpeg: noise reduction, normalization, filter."""
    print(f"🧹 Preprocessing audio: {audio_path}")
    output_path = audio_path.replace(".mp3", "_cleaned.wav")
    if os.path.exists(output_path):
        return output_path

    cmd = [
        "ffmpeg", "-i", audio_path,
        "-af", "highpass=f=200,lowpass=f=3000,afftdn,loudnorm",
        "-ar", "16000", "-ac", "1",
        output_path, "-y"
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path

def vad_split(audio_path: str) -> list[tuple[int, int]]:
    """Split audio using FunASR FSMN-VAD into ~1min chunks."""
    print(f"🎙️ VAD splitting (FunASR)...")
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = AutoModel(model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch", device=device, disable_update=True)
    
    res = model.generate(input=audio_path, batch_size_s=300)
    segments = res[0]['value']  # [[start, end], ...] in ms
            
    # Group into ~1min chunks
    chunks = []
    if not segments: return chunks
    
    curr_s, curr_e = segments[0]
    for i in range(1, len(segments)):
        s, e = segments[i]
        if e - curr_s <= 60000: # 60 seconds
            curr_e = e
        else:
            chunks.append((curr_s, curr_e))
            curr_s, curr_e = s, e
    chunks.append((curr_s, curr_e))
    
    print(f"✅ Split into {len(chunks)} chunks.")
    return chunks

def transcribe_and_refine(audio_path: str, chunks: list[tuple[int, int]], sermon_dir: str, metadata: dict, log_path: str) -> None:
    """Workflow: transcribe -> error picking -> refine -> finalize."""
    # SenseVoiceSmall is generally more accurate for this content but has MPS float64 issues.
    # Forcing CPU to ensure stability and better quality.
    device = "cpu"
    print(f"🚀 Loading SenseVoiceSmall on {device}...")
    sv_model = AutoModel(model="iic/SenseVoiceSmall", device=device, disable_update=True)
    
    audio = AudioSegment.from_file(audio_path)
    
    final_lyric_path = os.path.join(sermon_dir, "transcription_zh_lyric.txt")
    final_zh_path = os.path.join(sermon_dir, "transcript_zh.txt")
    
    safe_remove(final_lyric_path)
    safe_remove(final_zh_path)
    safe_remove(log_path)

    full_refined_text = []

    for i, (start_ms, end_ms) in enumerate(chunks):
        print(f"\n📦 Chunk {i+1}/{len(chunks)} ({start_ms/1000:.1f}s - {end_ms/1000:.1f}s)")
        
        chunk_audio = audio[start_ms:end_ms]
        chunk_wav = os.path.join(sermon_dir, f"chunk_{i}.wav")
        chunk_audio.export(chunk_wav, format="wav")
        
        # 3.1 Transcribe
        res = sv_model.generate(input=chunk_wav, cache={}, language="zh", use_itn=True)
        raw_text = re.sub(r'<\|.*?\|>', '', res[0]['text']).strip()
        
        # 3.2 Error Picking (Corrected Original Transcript)
        corrected_text = error_picking(raw_text, metadata, sermon_dir, log_path)
        
        # 3.3 Refine (Polished Text for Final Transcript)
        refined_text = refine_text(corrected_text, metadata, sermon_dir, log_path)
        full_refined_text.append(refined_text)
        
        # 3.4 Finalize Lyric (Original Corrected Text with Timestamps)
        entry = f"[{format_timestamp(start_ms/1000)} --> {format_timestamp(end_ms/1000)}] {corrected_text}"
        with open(final_lyric_path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
            
        safe_remove(chunk_wav)

    # 3.5 Global Finalize (Plain Text Refined Transcript)
    with open(final_zh_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(full_refined_text))

def error_picking(text: str, metadata: dict, sermon_dir: str, log_path: str) -> str:
    """Identify and fix obvious ASR errors using context and Bible RAG."""
    if not text or len(text.strip()) < 2:
        return text

    bible_context = get_bible_verses_by_ref(scripture_ref=metadata.get('scripture'))
    
    prompt = f"""
    Identify and fix obvious ASR transcription errors in this sermon segment.
    
    CONTEXT:
    Preacher: {metadata.get('preacher')}
    Series: {metadata.get('series')}
    Scripture: {metadata.get('scripture')}
    Accent: {metadata.get('profile', {}).get('accent', 'Standard Mandarin')}
    Bible Context: {bible_context}
    
    Segment: {text}
    
    Rules:
    1. Fix homophones, typos, and misheard biblical terms.
    2. Correct names and locations based on the preacher profile.
    3. Keep the text as literal as possible to what was spoken, just fixed.
    4. Return ONLY the corrected text.
    5. If the segment is too short, contains only noise, or no errors are found, return the original text as is.
    
    Output JSON: {{"data": "corrected text..."}}
    """
    res = ask_llm(prompt, log_path=log_path)
    corrected = res.get("data")
    
    # Fallback if LLM returns a failure message, empty, or un-parsable result
    if not corrected or "无法识别" in corrected or "内容缺失" in corrected or len(corrected.strip()) == 0:
        return text
        
    return corrected

def refine_text(text: str, metadata: dict, sermon_dir: str, log_path: str) -> str:
    """Polish the text for better flow and style."""
    if not text or len(text.strip()) < 2:
        return text

    prompt = f"""
    Refine and polish this sermon segment for publication.
    
    CONTEXT:
    Preacher: {metadata.get('preacher')}
    Series: {metadata.get('series')}
    Scripture: {metadata.get('scripture')}
    Profile: {json.dumps(metadata.get('profile', {}), ensure_ascii=False)}
    
    Segment: {text}
    
    Rules:
    1. Remove stammers, filler words, and duplicated phrases or sentences with similar meanings.
    2. Improve sentence structure and punctuation while keeping the preacher's original tone.
    3. Ensure consistency with biblical terminology.
    4. Return ONLY the refined text.
    5. Keep original language (mandarin)
    6. If the segment contains no meaningful content or cannot be refined, return the original text as is.
    
    Output JSON: {{"data": "refined text..."}}
    """
    res = ask_llm(prompt, log_path=log_path)
    refined = res.get("data")

    if not refined or len(refined.strip()) == 0:
        return text

    return refined

def format_timestamp(seconds: float) -> str:
    """Format seconds to HH:MM:SS.mmm"""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

def get_bible_verses_by_ref(scripture_ref: str | None = None) -> str:
    """
    Retrieves Bible verses based on a scripture reference.
    e.g. "John ch3:v16", "Jude ch1"
    """
    if not scripture_ref or not os.path.exists(BIBLE_DB_PATH):
        return ""

    # Parse reference: "Book chChapter:vVerse" or "Book chChapter"
    match = re.match(r"^(.*?)(?:\s+ch(\d+))?(?::v(\d+))?$", scripture_ref)
    if not match:
        return ""
    
    book_en, chapter, verse = match.groups()
    book_en = ' '.join(book_en.strip().split()) # Normalize spaces
    book_zh = BIBLE_EN_TO_ZH.get(book_en)
    if not book_zh:
        return ""
    
    abbrev = ZH_TO_ABBREV_MAP.get(book_zh)

    conn = sqlite3.connect(BIBLE_DB_PATH)
    cursor = conn.cursor()
    
    query = "SELECT book, chapter, verse, text FROM verses WHERE (book = ? OR book = ?)"
    params = [book_zh, abbrev]
    
    if chapter:
        query += " AND chapter = ?"
        params.append(chapter)
    if verse:
        query += " AND verse = ?"
        params.append(verse)
        
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    results = [f"{b} {c}:{v} - \"{t}\"" for b, c, v, t in rows]
    return "; ".join(results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Phase 2: Audio Transcription & Refinement (Refactored)")
    default_audio = "output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original.mp3"
    parser.add_argument("audio_path", nargs="?", default=default_audio, help="Path to the original.mp3 file to process")
    args = parser.parse_args()
    main(args.audio_path)

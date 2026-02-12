import os
import re
import json
import math
import hashlib
import sqlite3
import argparse
import tempfile
import subprocess
from glob import glob
from time import time
from datetime import timedelta

import gc
import torch
from pydub import AudioSegment

from src.common import ask_llm, safe_remove, get_custom_instructions, safe_write, safe_replace, string_similarity, retry
from src.constants import OUTPUT_ROOT, BIBLE_HOTWORDS_PATH, CHRISTIAN_HOTWORDS_PATH

# Audio processing
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
BIBLE_DB_PATH = "output/bible_rag.db"

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2: Audio Transcription & Refinement")
    parser.add_argument("audio_path", help="Path to the original.mp3 file to process")
    args = parser.parse_args()
    # Set ModelScope cache directory
    os.environ["MODELSCOPE_CACHE"] = os.path.expanduser('~/llm_models/modelscope')

    print(f"\n--- Phase 2: Audio Transcription & Refinement ---")
    process_sermon(args.audio_path)


def preprocess_audio(audio_path: str) -> str:
    """Preprocess audio using ffmpeg: noise reduction, normalization, filter."""
    print(f"🧹 Preprocessing audio: {audio_path}")
    output_path = audio_path.replace(".mp3", "_preprocessed.mp3")
    if os.path.exists(output_path):
        return output_path
    
    # ffmpeg command for: 
    # 1. highpass=f=200: remove low frequency noise
    # 2. lowpass=f=3000: remove high frequency noise (keep voice range)
    # 3. afftdn: noise reduction
    # 4. loudnorm: normalize volume
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-af", "highpass=f=200,lowpass=f=3000,afftdn,loudnorm",
        "-ar", "16000", "-ac", "1",
        output_path, "-y"
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def split_audio_vad(audio_path: str) -> list[dict]:
    """Split audio using Silero VAD for better speech segment detection."""
    from silero_vad import load_silero_vad, get_speech_timestamps
    import torch
    
    print(f"🎙️ VAD splitting: {audio_path}")
    model = load_silero_vad()
    
    # Load audio as tensor
    import librosa
    wav, sr = librosa.load(audio_path, sr=16000)
    wav_tensor = torch.from_numpy(wav)
    
    # Get speech timestamps
    speech_timestamps = get_speech_timestamps(wav_tensor, model, sampling_rate=16000)
    # Returns list of {'start': sample_idx, 'end': sample_idx}
    
    # Convert to ms
    segments = []
    for ts in speech_timestamps:
        segments.append({
            "start": int(ts['start'] / 16),
            "end": int(ts['end'] / 16)
        })
    return segments


def process_sermon(audio_path: str) -> None:
    sermon_dir = os.path.dirname(audio_path)
    final_zh = os.path.join(sermon_dir, 'transcript_zh.txt')
    final_lyric = os.path.join(sermon_dir, 'transcript_zh.lrc')

    # Checkpoint: Skip if already processed or audio missing
    if os.path.exists(final_zh) or not os.path.exists(audio_path):
        return

    print(f"\n⚙️ Processing: {audio_path}")
    
    # Preprocess
    audio_path = preprocess_audio(audio_path)

    # 2. Sequential processing
    lyric_tmp = os.path.join(sermon_dir, 'transcript_lyric_tmp.lrc')
    zh_tmp = os.path.join(sermon_dir, 'transcript_zh_tmp.txt')
    
    safe_remove(lyric_tmp)
    safe_remove(zh_tmp)

    segments = split_audio_vad(audio_path)
    audio = AudioSegment.from_file(audio_path)
    
    # Group segments into blocks to maintain context (max ~30s per block)
    max_block_ms = 30000
    blocks = []
    current_block = []
    current_block_ms = 0
    
    for seg in segments:
        dur = seg['end'] - seg['start']
        if current_block_ms + dur > max_block_ms and current_block:
            blocks.append(current_block)
            current_block = []
            current_block_ms = 0
        current_block.append(seg)
        current_block_ms += dur
    if current_block:
        blocks.append(current_block)
    
    all_lyric_segments = []
    
    # Initialize models
    from faster_whisper import WhisperModel
    from funasr import AutoModel
    import torch
    
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    
    print("🚀 Loading Whisper-turbo model (GPU not supported for faster-whisper on Mac, using CPU)...")
    # ctranslate2 (faster-whisper) doesn't support MPS yet
    whisper_model = WhisperModel("deepdml/faster-whisper-large-v3-turbo-ct2", device="cpu", compute_type="int8")
    
    print(f"🚀 Loading SenseVoiceSmall model on {device}...")
    sensevoice_model = AutoModel(model="iic/SenseVoiceSmall", device=device, disable_update=True)
    
    preacher_dir = os.path.dirname(os.path.dirname(sermon_dir))
    profile_path = os.path.join(preacher_dir, "profile.json")
    preacher_metadata = {}
    if os.path.exists(profile_path):
        with open(profile_path, 'r', encoding='utf-8') as f:
            preacher_metadata = json.load(f)

    for idx, block in enumerate(blocks):
        block_start = block[0]['start']
        block_end = block[-1]['end']
        print(f"\n📦 Processing block {idx+1}/{len(blocks)} ({block_start/1000:.1f}s - {block_end/1000:.1f}s)")
        
        refined_block, lyric_segments = process_block(
            block, audio, whisper_model, sensevoice_model, preacher_metadata
        )
        
        all_lyric_segments.extend(lyric_segments)
        safe_write(zh_tmp, refined_block)
        
        # Overwrite lyric file with full segment list
        os.makedirs(os.path.dirname(lyric_tmp), exist_ok=True)
        with open(lyric_tmp, 'w', encoding='utf-8') as f:
            f.write("\n".join(all_lyric_segments) + "\n")

    # Finalize
    safe_replace(zh_tmp, final_zh)
    safe_replace(lyric_tmp, final_lyric)
    print(f"✅ Saved transcript and lyric files.")


def process_block(block: list[dict], audio: AudioSegment, whisper_model, sensevoice_model, preacher_metadata: dict) -> tuple[str, list[str]]:
    """Process a single block of audio: transcribe, cross-ref, and refine."""
    block_start = block[0]['start']
    block_end = block[-1]['end']
    block_audio = audio[block_start:block_end]
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        block_audio.export(f.name, format="wav")
        block_path = f.name
    
    lyric_segments = []
    block_text = ""
    
    try:
        segments_w, _ = whisper_model.transcribe(block_path, beam_size=5, language="zh", initial_prompt="讲道, 圣经, 福音, 神, 耶稣")
        
        for s in segments_w:
            abs_start = block_start / 1000 + s.start
            abs_end = block_start / 1000 + s.end
            text = s.text.strip()
            if not text: continue
            
            # Confidence cross-reference
            if s.avg_logprob < -1.0:
                print(f"⚠️ Low confidence: \"{text}\" ({s.avg_logprob:.2f})")
                text = cross_reference_segment(block_audio, s.start, s.end, text, sensevoice_model, preacher_metadata)
            
            lyric_segments.append(f"[{format_timestamp(abs_start)} --> {format_timestamp(abs_end)}] {text}")
            block_text += text + " "
        
        refined_block = refine_chunk(block_text, preacher_metadata)
        return refined_block, lyric_segments
        
    finally:
        safe_remove(block_path)


def cross_reference_segment(block_audio: AudioSegment, start_s: float, end_s: float, whisper_text: str, sensevoice_model, preacher_metadata: dict) -> str:
    """Cross-reference a low-confidence segment with SenseVoice."""
    seg_audio = block_audio[start_s*1000 : end_s*1000]
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as sf:
        seg_audio.export(sf.name, format="wav")
        res_sv = sensevoice_model.generate(input=sf.name, batch_size_s=300)
        text_sv = re.sub(r'<\|.*?\|>', '', res_sv[0].get('text', '')).strip()
        safe_remove(sf.name)
    
    if text_sv and text_sv != whisper_text:
        print(f"⚖️ Judging: W:\"{whisper_text}\" vs SV:\"{text_sv}\"")
        return judge_transcriptions(whisper_text, text_sv, preacher_metadata)
    return whisper_text


def format_timestamp(seconds: float) -> str:
    """Format seconds to HH:MM:SS.mmm"""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def refine_chunk(text: str, preacher_metadata: dict) -> str:
    """Refine a chunk of text using Bible RAG and LLM."""
    if not text.strip(): return ""
    
    # 1. Look up Bible verses via RAG
    bible_verses = lookup_bible_rag(text)
    
    # 2. Refine with LLM
    prompt = f"""
    Refine the following Chinese sermon transcript segment.
    PREACHER PROFILE: {json.dumps(preacher_metadata, ensure_ascii=False)}
    BIBLE CONTEXT (CUV): {bible_verses}
    
    RULES:
    1. Fix ASR errors, especially names and biblical terms.
    2. Maintain the preacher's original style and tone.
    3. Remove stammers and fillers.
    4. Ensure smooth flow between sentences.
    
    Segment: {text}
    
    Output JSON: {{"data": "refined text..."}}
    """
    res = ask_llm(prompt)
    return res.get("data") or text


def judge_transcriptions(text_whisper: str, text_sensevoice: str, preacher_metadata: dict) -> str:
    """Use LLM to judge between two transcription versions."""
    prompt = f"""
    As an expert in Christian sermons, judge between these two ASR transcription versions of the same audio segment.
    PREACHER PROFILE: {json.dumps(preacher_metadata, ensure_ascii=False)}
    
    Version A (Whisper): {text_whisper}
    Version B (SenseVoice): {text_sensevoice}
    
    Analyze which version is more grammatically correct and consistent with a sermon context and the preacher's profile. You can combine them if needed to get the most accurate result.
    
    Output JSON: {{"data": "final result..."}}
    """
    res = ask_llm(prompt)
    return res.get("data") or text_whisper


def lookup_bible_rag(text: str) -> str:
    """Look up Bible verses using Pinyin-based RAG."""
    if not os.path.exists(BIBLE_DB_PATH) or not text.strip():
        return ""
    
    # 1. Extract keywords for better RAG lookup
    prompt = f"""
    从讲道内容中提取2-3个最核心的圣经人物、地名或神学关键词，用于圣经原文检索。
    如果发现明显的语音识别错误（例如“耶稣撒冷”应为“耶路撒冷”），请在关键词中输出更正后的圣经术语。
    
    输出JSON格式: {{"keywords": ["关键词1", "关键词2"]}}
    内容: {text[:500]}
    """
    res = ask_llm(prompt)
    keywords = res.get("keywords") or res.get("data") or []
    if isinstance(keywords, str):
        keywords = keywords.split()
    
    print(f"🔍 Extracted Bible keywords: {keywords}")
    
    if not keywords:
        return ""

    from scripts.generate_bible_rag import get_pinyin
    conn = sqlite3.connect(BIBLE_DB_PATH)
    cursor = conn.cursor()
    
    results = []
    seen = set()
    
    for kw in keywords:
        # Clean keyword
        kw = re.sub(r'[^\w\s]', '', kw).strip()
        if not kw: continue
        
        py = get_pinyin(kw)
        print(f"  - Searching pinyin: {py} for keyword: {kw}")
        if len(py) < 4: continue # skip too short pinyin
        
        # Search for pinyin in verses
        cursor.execute("SELECT book, chapter, verse, text FROM verses WHERE pinyin LIKE '%' || ? || '%'", (py,))
        rows = cursor.fetchall()
        print(f"  - Found {len(rows)} potential matches for {py}")
        for r in rows:
            key = f"{r[0]}{r[1]}{r[2]}"
            if key not in seen:
                results.append(f"{r[0]} {r[1]}:{r[2]} - \"{r[3]}\"")
                seen.add(key)
            if len(results) >= 10: break
        if len(results) >= 10: break
    
    conn.close()
    res_str = "; ".join(results)
    print(f"📖 RAG Results: {len(results)} verses found.")
    return res_str


if __name__ == '__main__':
    main()

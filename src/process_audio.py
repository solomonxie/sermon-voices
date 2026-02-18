import os
import re
import json
import sqlite3
import argparse
import subprocess
from glob import glob
from datetime import timedelta

import torch
from pydub import AudioSegment
from funasr import AutoModel
from dotenv import load_dotenv

load_dotenv()

from src.common import ask_llm, safe_remove
from src.constants import OUTPUT_ROOT, BOOK_MAP, BIBLE_EN_TO_ZH, ZH_TO_ABBREV_MAP

# Audio processing config
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["MODELSCOPE_CACHE"] = os.path.expanduser('~/llm_models/modelscope')
BIBLE_DB_PATH = "output/bible_rag.db"
BIBLE_CACHE = None  # (embeddings, texts, pinyin_texts)

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
    device = "mps" if torch.backends.mps.is_available() else "cpu"
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
    bible_context = bible_lookup_hybrid(text, sermon_dir, scripture_ref=metadata.get('scripture'))
    
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
    
    Output JSON: {{"data": "corrected text..."}}
    """
    res = ask_llm(prompt, log_path=log_path)
    return res.get("data") or text

def refine_text(text: str, metadata: dict, sermon_dir: str, log_path: str) -> str:
    """Polish the text for better flow and style."""
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
    
    Output JSON: {{"data": "refined text..."}}
    """
    res = ask_llm(prompt, log_path=log_path)
    return res.get("data") or text

def format_timestamp(seconds: float) -> str:
    """Format seconds to HH:MM:SS.mmm"""
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    millis = int(td.microseconds / 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

# --- Bible RAG Utility Functions ---

def load_bible_cache():
    global BIBLE_CACHE
    if BIBLE_CACHE is not None: return
    if not os.path.exists(BIBLE_DB_PATH): return

    import numpy as np
    import pickle
    conn = sqlite3.connect(BIBLE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT book, chapter, verse, text, pinyin, embedding FROM verses WHERE embedding IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()

    embeddings, metadata = [], []
    for r in rows:
        book, chap, ver, txt, py, emb_blob = r
        embeddings.append(np.array(pickle.loads(emb_blob)))
        metadata.append({"ref": f"{book} {chap}:{ver}", "text": txt, "pinyin": py})
    BIBLE_CACHE = (np.array(embeddings), metadata)

def bible_lookup_hybrid(text: str, sermon_dir: str = None, scripture_ref: str = None) -> str:
    if not text.strip(): return ""
    load_bible_cache()
    if not BIBLE_CACHE: return ""

    import numpy as np
    from scripts.generate_bible_rag import generate_embedding, get_pinyin
    from src.common import string_similarity

    embeddings, metadata = BIBLE_CACHE
    
    # Filter by scripture reference if provided
    if scripture_ref:
        # Parse scripture_ref (e.g., "Romans ch1:v1", "Ephesians ch1", "1 Corinthians 13")
        match = re.match(r"([\d\s\w]+)\s*(?:ch(\d+))?(?::v(\d+))?", scripture_ref, re.IGNORECASE)
        if match:
            book_name_en, chapter, verse = match.groups()
            book_name_en = book_name_en.strip()
            
            # Normalize book name (e.g., "1 Corinthians" -> "1 Corinthians")
            book_name_en_normalized = ' '.join(book_name_en.split())
            book_name_zh = BIBLE_EN_TO_ZH.get(book_name_en_normalized)
            abbrev = ZH_TO_ABBREV_MAP.get(book_name_zh)

            if book_name_zh:
                filtered_indices = []
                for i, meta in enumerate(metadata):
                    # Parse meta['ref'] (e.g., "创世记 1:1", "1co 1:1")
                    ref_match = re.match(r"^(.*?)\s+(\d+):(\d+)$", meta['ref'])
                    if ref_match:
                        b, c, v = ref_match.groups()
                        if (b == book_name_zh or b == abbrev) and \
                           (not chapter or c == chapter) and \
                           (not verse or v == verse):
                            filtered_indices.append(i)
                
                if filtered_indices:
                    embeddings = embeddings[filtered_indices]
                    metadata = [metadata[i] for i in filtered_indices]

    query_emb = generate_embedding(text[:500])
    if not query_emb: return ""
    query_vec = np.array(query_emb)

    norms = np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_vec)
    similarities = np.dot(embeddings, query_vec) / (norms + 1e-9)

    top_indices = np.argsort(similarities)[-50:][::-1]
    candidates = [(similarities[i], metadata[i]) for i in top_indices]

    query_py = get_pinyin(re.sub(r'[^\w\s]', '', text).strip())
    reranked = []
    for sim_sem, meta in candidates:
        sim_py = string_similarity(query_py, meta['pinyin']) if query_py and meta['pinyin'] else 0.0
        final_score = (sim_sem * 0.4) + (sim_py * 0.6)
        reranked.append((final_score, meta))

    reranked.sort(key=lambda x: x[0], reverse=True)
    top_verses = [f"{r[1]['ref']} - \"{r[1]['text']}\"" for r in reranked[:5] if r[0] > 0.2]
    return "; ".join(top_verses)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Phase 2: Audio Transcription & Refinement (Refactored)")
    default_audio = "output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original.mp3"
    parser.add_argument("audio_path", nargs="?", default=default_audio, help="Path to the original.mp3 file to process")
    args = parser.parse_args()
    main(args.audio_path)

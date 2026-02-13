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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from src.common import ask_llm, safe_remove, get_custom_instructions, safe_write, safe_replace, string_similarity, retry
from src.constants import OUTPUT_ROOT, BIBLE_HOTWORDS_PATH, CHRISTIAN_HOTWORDS_PATH

# Audio processing
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
BIBLE_DB_PATH = "output/bible_rag.db"
BIBLE_CACHE = None # (embeddings, texts, pinyin_texts)

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
    output_path = audio_path.replace(".mp3", "_cleaned.wav")
    if os.path.exists(output_path):
        return output_path

    # Cleanup old mp3 if exists
    old_mp3 = audio_path.replace(".mp3", "_cleaned.mp3")
    if os.path.exists(old_mp3):
        os.remove(old_mp3)

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

    # Convert to ms and filter short segments
    segments = []
    min_dur_ms = 100
    for ts in speech_timestamps:
        start_ms = int(ts['start'] / 16)
        end_ms = int(ts['end'] / 16)
        if end_ms - start_ms >= min_dur_ms:
            segments.append({
                "start": start_ms,
                "end": end_ms,
                "spk": "SPEAKER_00"
            })
    return segments


def run_diarization(audio_path: str, sermon_dir: str) -> list[dict]:
    """Identify speakers and extract 10s samples using pyannote.audio."""
    from pyannote.audio import Pipeline
    import torch
    from pydub import AudioSegment
    
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        print("❌ HF_TOKEN not found in environment. Diarization will fail.")
        segments = split_audio_vad(audio_path)
        return segments

    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    print(f"🚀 Loading pyannote.audio pipeline on {device}...")
    
    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=hf_token
        )
        pipeline.to(device)
    except Exception as e:
        if "403" in str(e):
            print(f"❌ Failed to load pyannote pipeline: 403 Client Error.")
            print("💡 This usually means you need to accept the model's user conditions on Hugging Face.")
            print("Please visit the following URLs and accept the terms:")
            print("1. https://hf.co/pyannote/speaker-diarization-3.1")
            print("2. https://hf.co/pyannote/segmentation-3.0")
            print('3. https://hf.co/pyannote/speaker-diarization-community-1')
            print("Also, ensure your HF_TOKEN in .env is valid: https://hf.co/settings/tokens")
        else:
            print(f"❌ Failed to load pyannote pipeline: {e}")
        return split_audio_vad(audio_path)
    
    print(f"🛰️ Processing diarization (full audio)...")
    try:
        diarization = pipeline(audio_path)
    except Exception as e:
        print(f"❌ Diarization failed: {e}")
        return split_audio_vad(audio_path)
    
    # Handle both Annotation (older) and DiarizeOutput (newer) types
    annotation = diarization
    if hasattr(diarization, "speaker_diarization"):
        annotation = diarization.speaker_diarization

    segments = []
    speaker_samples = {} # spk_id -> [AudioSegment]
    
    audio = AudioSegment.from_file(audio_path)
    
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        start_ms = int(turn.start * 1000)
        end_ms = int(turn.end * 1000)
        segments.append({"start": start_ms, "end": end_ms, "spk": speaker})
        
        # Collect samples for unique speakers from the first 10 minutes
        if start_ms < 600000: # 10 minutes
            if speaker not in speaker_samples:
                speaker_samples[speaker] = []
            
            dur = end_ms - start_ms
            if dur > 3000 and sum(len(s) for s in speaker_samples[speaker]) < 10000:
                speaker_samples[speaker].append(audio[start_ms:end_ms])

    # Export speaker samples
    for spk, chunks in speaker_samples.items():
        if chunks:
            sample_audio = chunks[0]
            for c in chunks[1:]: sample_audio += c
            sample_audio = sample_audio[:10000] # Max 10s
            sample_path = os.path.join(sermon_dir, f"{name_to_slug(spk)}.mp3")
            sample_audio.export(sample_path, format="mp3")
            print(f"🎙️ Saved speaker sample: {sample_path}")
            
    return segments


def name_to_slug(name: str) -> str:
    return name.lower().replace(" ", "_").replace("speaker_", "speaker")


def split_by_speaker(lyric_path: str, sermon_dir: str):
    """Split the lyric file into individual speaker files."""
    if not os.path.exists(lyric_path): return
    
    speaker_files = {} # spk -> list of lines
    
    with open(lyric_path, 'r', encoding='utf-8') as f:
        for line in f:
            # Format: [HH:MM:SS.mmm --> HH:MM:SS.mmm] SPEAKER: Content
            match = re.search(r'\] (.*?): (.*)', line)
            if match:
                spk = match.group(1).strip()
                content = match.group(2).strip()
                if spk not in speaker_files:
                    speaker_files[spk] = []
                speaker_files[spk].append(content)
    
    for spk, lines in speaker_files.items():
        spk_slug = name_to_slug(spk)
        spk_path = os.path.join(sermon_dir, f"transcript_{spk_slug}.txt")
        with open(spk_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n")
        print(f"📝 Saved speaker transcript: {spk_path}")


def process_sermon(audio_path: str) -> None:
    sermon_dir = os.path.dirname(audio_path)
    final_zh = os.path.join(sermon_dir, 'transcript_zh.txt')
    final_lyric = os.path.join(sermon_dir, 'transcript_zh.lrc.txt')

    # Checkpoint: Skip if already processed or audio missing
    if os.path.exists(final_zh) or not os.path.exists(audio_path):
        return

    print(f"\n⚙️ Processing: {audio_path}")

    # Preprocess
    audio_path = preprocess_audio(audio_path)

    # 1. Diarization (pyannote.audio)
    print(f"🎙️ Diarizing: {audio_path}")
    speaker_segments = run_diarization(audio_path, sermon_dir)
    
    # 2. Sequential processing
    lyric_tmp = os.path.join(sermon_dir, 'transcript_tmp.lrc.txt')
    zh_tmp = os.path.join(sermon_dir, 'transcript_refine_tmp.txt')
    whisper_tmp = os.path.join(sermon_dir, 'transcript_whisper_tmp.txt')
    pinyin_log = os.path.join(sermon_dir, 'transcript_bible_pinyin_lookup_tmp.txt')
    rag_log = os.path.join(sermon_dir, 'transcript_bible_rag_lookup_tmp.txt')

    for f in [lyric_tmp, zh_tmp, whisper_tmp, pinyin_log, rag_log]:
        safe_remove(f)

    audio = AudioSegment.from_file(audio_path)

    # Group segments into blocks to maintain context (max ~30s per block)
    # We use speaker segments from diarization instead of VAD
    max_block_ms = 30000
    blocks = []
    current_block = []
    current_block_ms = 0

    for seg in speaker_segments:
        dur = seg['end'] - seg['start']
        # Also break block if speaker changes
        if (current_block_ms + dur > max_block_ms or (current_block and current_block[-1]['spk'] != seg['spk'])) and current_block:
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
        speaker = block[0]['spk']
        print(f"\n📦 Processing block {idx+1}/{len(blocks)} [{speaker}] ({block_start/1000:.1f}s - {block_end/1000:.1f}s)")

        refined_block, lyric_segments = process_block(
            block, audio, whisper_model, sensevoice_model, preacher_metadata, sermon_dir, speaker
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
    
    # Split by speaker
    split_by_speaker(final_lyric, sermon_dir)
    
    print(f"✅ Saved transcript and lyric files.")


def process_block(block: list[dict], audio: AudioSegment, whisper_model, sensevoice_model, preacher_metadata: dict, sermon_dir: str, speaker: str) -> tuple[str, list[str]]:
    """Process a single block of audio: transcribe, cross-ref, and refine."""
    block_start = block[0]['start']
    block_end = block[-1]['end']
    block_audio = audio[block_start:block_end]
    whisper_log = os.path.join(sermon_dir, 'transcript_whisper_tmp.txt')
    refine_log = os.path.join(sermon_dir, 'transcript_refine_tmp.txt')

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

            trace_entry = f"[{abs_start:.1f}s-{abs_end:.1f}s] W: \"{text}\" (prob: {s.avg_logprob:.2f})"

            # Confidence cross-reference
            if s.avg_logprob < -1.0:
                print(f"⚠️ Low confidence: \"{text}\" ({s.avg_logprob:.2f})")
                text = cross_reference_segment(block_audio, s.start, s.end, text, sensevoice_model, preacher_metadata)

            safe_write(whisper_log, text)
            lyric_segments.append(f"[{format_timestamp(abs_start)} --> {format_timestamp(abs_end)}] {speaker}: {text}")
            block_text += text + " "

        refined_block = refine_chunk(block_text, preacher_metadata, sermon_dir, speaker)
        return refined_block, lyric_segments

    finally:
        safe_remove(block_path)


def cross_reference_segment(block_audio: AudioSegment, start_s: float, end_s: float, whisper_text: str, sensevoice_model, preacher_metadata: dict) -> str:
    """Cross-reference a low-confidence segment with SenseVoice."""
    duration_ms = (end_s - start_s) * 1000
    if duration_ms < 100:
        print(f"⏩ Segment too short for cross-reference ({duration_ms:.1f}ms), skipping.")
        return whisper_text

    seg_audio = block_audio[start_s*1000 : end_s*1000]

    # Safety Check: SenseVoice crashes on empty or extremely short audio
    # A waveform length of 0 triggers AssertionError: choose a window size 0 that is [2, 0]
    if len(seg_audio) == 0:
        print(f"⏩ Segment is empty ({duration_ms:.1f}ms), skipping SenseVoice.")
        return whisper_text

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as sf:
        seg_audio.export(sf.name, format="wav")
        try:
            res_sv = sensevoice_model.generate(input=sf.name, batch_size_s=300)
            text_sv = re.sub(r'<\|.*?\|>', '', res_sv[0].get('text', '')).strip()
        except Exception as e:
            print(f"⚠️ SenseVoice failed for segment {start_s:.1f}s-{end_s:.1f}s: {e}")
            text_sv = ""
        finally:
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


def refine_chunk(text: str, preacher_metadata: dict, sermon_dir: str = None, speaker: str = "SPEAKER_00") -> str:
    """Refine a chunk of text using Bible RAG and LLM."""
    if not text.strip(): return ""

    # 1. Look up Bible verses via Hybrid RAG
    bible_context = bible_lookup_hybrid(text, sermon_dir)
    bible_verses = f"BIBLE MATCHES: {bible_context}"

    if bible_context:
        print(f"📖 Bible context found:\n{bible_verses}")

    # 2. Refine with LLM
    prompt = f"""
    Refine the following Chinese sermon transcript segment.
    SPEAKER: {speaker}
    PREACHER PROFILE: {json.dumps(preacher_metadata, ensure_ascii=False)}
    BIBLE CONTEXT (CUV): {bible_verses}

    RULES:
    1. Fix ASR errors, especially names and biblical terms.
    2. Maintain the preacher's original style and tone.
    3. Remove stammers, fillers, and duplicated phrases or sentences with similar meanings.
    4. Ensure smooth flow between sentences.
    5. Output the refined text prefixed with the speaker label, e.g., "{speaker}: refined text..."

    Segment: {text}

    Output JSON: {{"data": "{speaker}: refined text..."}}
    """
    res = ask_llm(prompt)
    return res.get("data") or f"{speaker}: {text}"


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


def load_bible_cache():
    """Load Bible embeddings and text into memory for fast hybrid search."""
    global BIBLE_CACHE
    if BIBLE_CACHE is not None: return

    if not os.path.exists(BIBLE_DB_PATH):
        print("⚠️ Bible DB missing.")
        return

    import numpy as np
    import pickle

    conn = sqlite3.connect(BIBLE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT book, chapter, verse, text, pinyin, embedding FROM verses WHERE embedding IS NOT NULL")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("⚠️ No Bible embeddings to cache.")
        return

    embeddings = []
    metadata = []
    for r in rows:
        book, chap, ver, txt, py, emb_blob = r
        embeddings.append(np.array(pickle.loads(emb_blob)))
        metadata.append({
            "ref": f"{book} {chap}:{ver}",
            "text": txt,
            "pinyin": py
        })

    BIBLE_CACHE = (np.array(embeddings), metadata)
    print(f"📚 Bible cache loaded: {len(metadata)} verses.")


def calculate_pinyin_similarity(text1_py: str, text2_py: str) -> float:
    """Calculate similarity between two Pinyin strings using string distance."""
    # Using normalized edit distance for robust matching
    from src.common import string_similarity
    if not text1_py or not text2_py: return 0.0
    return string_similarity(text1_py, text2_py)


def bible_lookup_hybrid(text: str, sermon_dir: str = None) -> str:
    """Hybrid Bible lookup: Semantic Retrieve + Pinyin Rerank."""
    if not text.strip(): return ""
    load_bible_cache()
    if not BIBLE_CACHE: return ""

    import numpy as np
    from scripts.generate_bible_rag import generate_embedding, get_pinyin

    # 1. Semantic Retrieval (Top 50)
    query_emb = generate_embedding(text[:500])
    if not query_emb: return ""
    query_vec = np.array(query_emb)

    embeddings, metadata = BIBLE_CACHE
    # Cosine similarities
    norms = np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_vec)
    similarities = np.dot(embeddings, query_vec) / norms

    # Get top 50 candidates
    top_indices = np.argsort(similarities)[-50:][::-1]
    candidates = [(similarities[i], metadata[i]) for i in top_indices]

    # 2. Pinyin Reranking
    query_py = get_pinyin(re.sub(r'[^\w\s]', '', text).strip())
    reranked = []
    for sim_sem, meta in candidates:
        sim_py = calculate_pinyin_similarity(query_py, meta['pinyin'])
        # Hybrid score (weighted combination)
        final_score = (sim_sem * 0.4) + (sim_py * 0.6)
        reranked.append((final_score, meta))

    reranked.sort(key=lambda x: x[0], reverse=True)

    # Log results
    if sermon_dir:
        pinyin_log = os.path.join(sermon_dir, 'transcript_bible_pinyin_lookup_tmp.txt')
        rag_log = os.path.join(sermon_dir, 'transcript_bible_rag_lookup_tmp.txt')
        # Log semantic top results
        safe_write(rag_log, "\n".join([f"{c[0]:.3f} {c[1]['ref']}: {c[1]['text']}" for c in candidates[:10]]))
        # Log pinyin top results
        safe_write(pinyin_log, "\n".join([f"{r[0]:.3f} {r[1]['ref']}: {r[1]['text']}" for r in reranked[:10]]))

    top_verses = [f"{r[1]['ref']} - \"{r[1]['text']}\"" for r in reranked[:5] if r[0] > 0.2]
    return "; ".join(top_verses)


def bible_lookup_pinyin(text: str) -> str:
    """Look up Bible verses using Pinyin-based phonetic matching (Legacy)."""
    return bible_lookup_hybrid(text)


def bible_lookup_rag(text: str) -> str:
    """Look up Bible verses using semantic embeddings (Legacy)."""
    return bible_lookup_hybrid(text)


def lookup_bible_verses(text: str) -> str:
    """Backward compatibility for legacy calls."""
    return bible_lookup_pinyin(text)


if __name__ == '__main__':
    main()

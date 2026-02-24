import os
import re
import json
import sqlite3
import argparse
import subprocess
from datetime import timedelta
from functools import lru_cache

import torch
import whisperx
from pydub import AudioSegment
from funasr import AutoModel
from dotenv import load_dotenv

load_dotenv()

# Device and MPS Patching
DEVICE = "mps"
_orig_cumsum = torch.cumsum
torch.cumsum = lambda input, *args, **kwargs: _orig_cumsum(input, *args, **{**kwargs, "dtype": torch.float32}) if kwargs.get("dtype") == torch.float64 else _orig_cumsum(input, *args, **kwargs)

from src.common import ask_llm, safe_remove
from src.constants import BIBLE_EN_TO_ZH, ZH_TO_ABBREV_MAP

# --- Globals ---
# Audio processing config
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["MODELSCOPE_CACHE"] = os.path.expanduser('~/llm_models/modelscope')
os.environ["HF_HOME"] = os.path.expanduser('~/llm_models/huggingface')
BIBLE_DB_PATH = "output/bible_rag.db"

# Model cache
MODEL_CACHE = {}
COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"

def main(audio_path) -> None:
    print(f"\n--- Phase 2: Audio Transcription & Refinement (Multi-ASR) ---")
    sermon_dir = os.path.dirname(audio_path)
    final_lyric = os.path.join(sermon_dir, "transcription_zh_lyric.txt")
    final_zh = os.path.join(sermon_dir, "transcript_zh.txt")
    llm_log_path = os.path.join(sermon_dir, "llm_log.txt")

    if os.path.exists(final_zh):
        print(f"✅ Already processed: {final_zh}")
        return

    # 0. Load sermon context
    context_info = load_and_build_context(sermon_dir)
    context_str = context_info["context_str"]
    print(f"📝 Loaded context for: {context_info['preacher']} - {context_info['title']}")

    # 1. Preprocess audio
    cleaned_audio_path = preprocess_audio(audio_path)

    # 2. VAD Split -> ~1min chunks
    chunks = vad_split(cleaned_audio_path)

    # 3. Transcribe -> Merge -> Refine -> Finalize
    transcribe_and_refine(cleaned_audio_path, chunks, sermon_dir, context_str, llm_log_path)

    print(f"✅ Workflow complete. Results saved to:\n   - {final_lyric}\n   - {final_zh}")

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
    vad_model = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
    model = AutoModel(model=vad_model, device=DEVICE, disable_update=True)
    
    res = model.generate(input=audio_path, batch_size_s=300)
    segments = res[0]['value'] if res else []
            
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

def transcribe_and_refine(audio_path: str, chunks: list, sermon_dir: str, context_str: str, llm_log_path: str) -> None:
    """Workflow: transcribe -> merge -> error picking -> refine -> finalize."""
    audio = AudioSegment.from_file(audio_path)
    
    final_lyric_path = os.path.join(sermon_dir, "transcription_zh_lyric.txt")
    final_zh_path = os.path.join(sermon_dir, "transcript_zh.txt")
    
    safe_remove(final_lyric_path)
    safe_remove(final_zh_path)
    # safe_remove(llm_log_path) # Retain LLM log across chunks
    if os.path.exists(llm_log_path): # Clear log for new run
        os.remove(llm_log_path)

    full_refined_text = []

    for i, (start_ms, end_ms) in enumerate(chunks):
        print(f"\n📦 Chunk {i+1}/{len(chunks)} ({start_ms/1000:.1f}s - {end_ms/1000:.1f}s)")
        
        chunk_wav = os.path.join(sermon_dir, f"chunk_{i}.wav")
        chunk_audio = audio[start_ms:end_ms]
        chunk_audio.export(chunk_wav, format="wav")
        
        # 3.1 Transcribe with multiple models
        transcriptions = {
            "sensevoice": transcribe_with_sensevoice(chunk_wav),
            "whisperx": transcribe_with_whisperx(chunk_wav),
            "paraformer": transcribe_with_paraformer_zh(chunk_wav),
            "funasr_nano": transcribe_with_funasr_nano(chunk_wav),
            # "glm_nano": transcribe_with_glm_asr_nano(chunk_wav),
        }
        
        # 3.2 Merge transcriptions using LLM
        merged_text = merge_transcriptions(transcriptions, context_str, llm_log_path)
        
        # 3.3 Error Picking (Corrected Original Transcript)
        corrected_text = error_picking(merged_text, context_str, llm_log_path)
        
        # 3.4 Refine (Polished Text for Final Transcript)
        refined_text = refine_text(corrected_text, context_str, llm_log_path)
        full_refined_text.append(refined_text)
        
        # 3.5 Finalize Lyric (Original Corrected Text with Timestamps)
        entry = f"[{format_timestamp(start_ms/1000)} --> {format_timestamp(end_ms/1000)}] {corrected_text}"
        with open(final_lyric_path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")
            
        safe_remove(chunk_wav)

    # 3.6 Global Finalize (Plain Text Refined Transcript)
    with open(final_zh_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(full_refined_text))


def transcribe_with_sensevoice(audio_path: str) -> str:
    """Transcribe with SenseVoiceSmall."""
    model = _get_model("iic/SenseVoiceSmall", device=DEVICE, disable_update=True)
    res = model.generate(input=audio_path, cache={}, language="zh", use_itn=True)
    return re.sub(r'<\|.*?\|>', '', res[0]['text']).strip() if res else ""

def transcribe_with_whisperx(audio_path: str) -> str:
    """Transcribe with WhisperX (faster-whisper)."""
    # WhisperX doesn't support MPS, use CPU instead.
    model = _get_model("base", is_whisper=True, device="cpu", compute_type=COMPUTE_TYPE, download_root=os.path.expanduser('~/llm_models/whisperx'))
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio, batch_size=16)
    return result["text"].strip() if result and "text" in result else ""

def transcribe_with_paraformer_zh(audio_path: str) -> str:
    """Transcribe with Paraformer-large."""
    model_id = "iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch"
    model = _get_model(model_id, device=DEVICE, disable_update=True)
    res = model.generate(input=audio_path, cache={})
    return res[0]["text"].strip() if res else ""

def transcribe_with_funasr_nano(audio_path: str) -> str:
    """Transcribe with Fun-ASR-Nano-2512."""
    model_id = "FunAudioLLM/Fun-ASR-Nano-2512"
    print(f"🚀 Using Fun-ASR-Nano-2512 (model: {model_id})")
    model = _get_model(model_id, device=DEVICE, disable_update=True)
    res = model.generate(input=audio_path, cache={})
    return res[0]["text"].strip() if res else ""

def transcribe_with_glm_asr_nano(audio_path: str) -> str:
    """Transcribe with GLM-ASR-Nano-2512.
    Note: Requires transformers>=5.0.0.dev0, which conflicts with qwen-asr (requires 4.57.6).
    """
    model_id = "zai-org/GLM-ASR-Nano-2512"
    print(f"🚀 Using GLM-ASR-Nano-2512 (model: {model_id})")
    print(f"⚠️ Skipping GLM-ASR-Nano-2512: It requires transformers>=5.0.0.dev0 (git branch),")
    print(f"⚠️ which conflicts with the project's qwen-asr dependency (requires 4.57.6).")
    # To run this in an isolated environment, use the transformers API:
    # processor = AutoProcessor.from_pretrained(model_id)
    # model = AutoModelForSeq2SeqLM.from_pretrained(model_id)
    # inputs = processor.apply_transcription_request(audio_array)
    # outputs = model.generate(**inputs, max_new_tokens=128)
    return ""

def _get_model(model_name: str, is_whisper: bool = False, **kwargs):
    if model_name not in MODEL_CACHE:
        print(f"🚀 Loading {model_name} on {kwargs.get('device', DEVICE)}...")
        if is_whisper or "whisper" in model_name:
            MODEL_CACHE[model_name] = whisperx.load_model(model_name, **kwargs)
        else:
            MODEL_CACHE[model_name] = AutoModel(model=model_name, **kwargs)
    return MODEL_CACHE[model_name]

def merge_transcriptions(texts: dict, context_str: str, log_path: str) -> str:
    """Merge multiple ASR transcriptions using an LLM."""
    if not any(texts.values()):
        return ""

    valid_texts = {k: v for k, v in texts.items() if v}
    if len(valid_texts) == 1:
        return list(valid_texts.values())[0]

    transcriptions_formatted = "\n".join([f"- {model_name}: {text}" for model_name, text in valid_texts.items()])

    prompt = f"""
    Please merge the following ASR transcriptions for a sermon segment into a single, accurate version.

    CONTEXT:
    {context_str}

    TRANSCRIPTIONS:
    {transcriptions_formatted}

    RULES:
    1. Analyze the transcriptions to identify the most likely correct words and phrases.
    2. Pay attention to context (preacher, scripture) to resolve discrepancies.
    3. Synthesize the best parts of each transcription. Do not just pick one.
    4. Return ONLY the merged and corrected text.
    5. If all inputs are noisy or nonsensical, return an empty string.

    Output JSON: {{"data": "merged text..."}}
    """
    res = ask_llm(prompt, log_path=log_path)
    merged = res.get("data", "")
    return merged if merged else list(valid_texts.values())[0]


def error_picking(text: str, context_str: str, log_path: str) -> str:
    """Identify and fix obvious ASR errors using context and Bible RAG."""
    if not text or len(text.strip()) < 2:
        return text
    
    prompt = f"""
    Identify and fix obvious ASR transcription errors in this sermon segment.
    
    CONTEXT:
    {context_str}
    
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
    
    if not corrected or "无法识别" in corrected or "内容缺失" in corrected or len(corrected.strip()) == 0:
        return text
        
    return corrected

def refine_text(text: str, context_str: str, log_path: str) -> str:
    """Polish the text for better flow and style."""
    if not text or len(text.strip()) < 2:
        return text

    prompt = f"""
    Refine and polish this sermon segment for publication.
    
    CONTEXT:
    {context_str}
    
    Segment: {text}
    
    Rules:
    1. Remove stammers, filler words, and duplicated phrases or sentences with similar meanings.
    2. Improve sentence structure and punctuation while keeping the preacher's original tone.
    3. Ensure consistency with biblical terminology.
    4. Return ONLY the refined text.
    5. Keep original language (mandarin).
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

def _load_json(path: str) -> dict:
    """Safely load a JSON file, returning an empty dict if not found."""
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_and_build_context(sermon_dir: str) -> dict:
    """
    Loads context from metadata/profile files, gets Bible context,
    and returns a dictionary with the pre-formatted context string and metadata.
    """
    # Load raw data
    metadata = _load_json(os.path.join(sermon_dir, "metadata.json"))
    preacher_dir = os.path.dirname(os.path.dirname(sermon_dir))
    profile = _load_json(os.path.join(preacher_dir, "profile.json"))

    # Get related data
    scripture_ref = metadata.get('scripture')
    bible_context = get_bible_verses_by_ref(scripture_ref)

    # Build context string
    preacher = metadata.get('preacher', 'Unknown Preacher')
    series = metadata.get('series', 'Unknown Series')
    accent = profile.get('accent', 'Standard Mandarin')
    
    context_lines = [
        f"Preacher: {preacher}",
        f"Series: {series}",
        f"Scripture: {scripture_ref or 'Unknown Scripture'}",
        f"Accent: {accent}",
    ]
    if bible_context:
        context_lines.append(f"Bible Context: {bible_context}")
    
    return {
        "context_str": "\n".join(context_lines),
        "preacher": preacher,
        "title": metadata.get('title', 'Unknown Title'),
    }

@lru_cache(maxsize=1)
def get_bible_verses_by_ref(scripture_ref: str | None = None) -> str:
    """
    Retrieves Bible verses based on a scripture reference.
    e.g. "John ch3:v16", "Jude ch1"
    Caches the result for the entire run.
    """
    if not scripture_ref or not os.path.exists(BIBLE_DB_PATH):
        return ""

    match = re.match(r"^(.*?)(?:\s+ch(\d+))?(?::v(\d+))?$", scripture_ref)
    if not match: return ""
    
    book_en, chapter, verse = match.groups()
    book_en = ' '.join(book_en.strip().split())
    book_zh = BIBLE_EN_TO_ZH.get(book_en)
    if not book_zh: return ""
    
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
    parser = argparse.ArgumentParser(description="Phase 2: Audio Transcription & Refinement (Multi-ASR)")
    default_audio = "output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original.mp3"
    parser.add_argument("audio_path", nargs="?", default=default_audio, help="Path to the original.mp3 file to process")
    args = parser.parse_args()
    main(args.audio_path)

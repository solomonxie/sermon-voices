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

from src.common import ask_llm, safe_remove
from src.constants import BIBLE_EN_TO_ZH, ZH_TO_ABBREV_MAP

# Mitigate macOS objc duplicate class warnings
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

load_dotenv()

# --- Globals ---
# Audio processing config
os.environ["MODELSCOPE_CACHE"] = os.path.expanduser('~/llm_models/modelscope')
os.environ["HF_HOME"] = os.path.expanduser('~/llm_models/huggingface')
BIBLE_DB_PATH = "output/bible_rag.db"

# Device and MPS Patching
DEVICE = "mps"
_orig_cumsum = torch.cumsum


def patched_cumsum(input, *args, **kwargs):
    if kwargs.get("dtype") == torch.float64:
        return _orig_cumsum(input, *args, **{**kwargs, "dtype": torch.float32})
    return _orig_cumsum(input, *args, **kwargs)


torch.cumsum = patched_cumsum

# Model cache
MODEL_CACHE = {}
COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"


def main(audio_path) -> None:
    print("\n--- Phase 2: Audio Transcription & Refinement (Multi-ASR) ---")
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

    # 2. VAD Split -> ~5min chunks
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
    """Split audio using FunASR FSMN-VAD into ~5min chunks."""
    print("🎙️ VAD splitting (FunASR)...")
    vad_model = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"
    model = AutoModel(model=vad_model, device=DEVICE, disable_update=True)

    res = model.generate(input=audio_path, batch_size_s=300)
    segments = res[0]['value'] if res else []

    # Group into ~5min chunks
    chunks = []
    if not segments:
        return chunks

    curr_s, curr_e = segments[0]
    for i in range(1, len(segments)):
        s, e = segments[i]
        if e - curr_s <= 300000: # 300 seconds (5 min)
            curr_e = e
        else:
            chunks.append((curr_s, curr_e))
            curr_s, curr_e = s, e
    chunks.append((curr_s, curr_e))

    print(f"✅ Split into {len(chunks)} chunks.")
    return chunks


def transcribe_and_refine(audio_path: str, chunks: list, sermon_dir: str,
                         context_str: str, llm_log_path: str) -> None:
    """Workflow: transcribe base -> find bad timeframes -> targeted multi-ASR
    -> assemble -> perfection loop -> refine."""
    audio = AudioSegment.from_file(audio_path)

    final_lyric_path = os.path.join(sermon_dir, "transcription_zh_lyric.txt")
    final_zh_path = os.path.join(sermon_dir, "transcript_zh.txt")

    safe_remove(final_lyric_path)
    safe_remove(final_zh_path)
    if os.path.exists(llm_log_path): # Clear log for new run
        os.remove(llm_log_path)

    full_refined_text = []

    for i, (start_ms, end_ms) in enumerate(chunks):
        print(f"\n📦 Chunk {i+1}/{len(chunks)} ({start_ms/1000:.1f}s - {end_ms/1000:.1f}s)")

        chunk_wav = os.path.join(sermon_dir, f"chunk_{i}.wav")
        chunk_audio = audio[start_ms:end_ms]
        chunk_audio.export(chunk_wav, format="wav")

        # 3.1 Transcribe base with timestamps (WhisperX)
        print("   -> Getting base transcription with timestamps...")
        base_segments = transcribe_base_with_timestamps(chunk_wav)

        # 3.2 Find inaccurate timeframes via LLM
        print("   -> Evaluating initial transcription quality with LLM...")
        bad_timeframes = find_inaccurate_timeframes(base_segments, context_str, llm_log_path)

        # 3.3 Targeted multi-ASR on bad timeframes
        corrected_segments_map = {}
        if bad_timeframes:
            print(f"   -> Found {len(bad_timeframes)} inaccurate timeframes. Running targeted multi-ASR fixes...")
            for tf in bad_timeframes:
                s_time = max(0.0, float(tf.get('start', 0.0)) - 0.5)
                e_time = min(len(chunk_audio) / 1000.0, float(tf.get('end', 0.0)) + 0.5)

                if s_time >= e_time:
                    continue

                print(f"      -> Fixing timeframe: [{s_time:.1f} - {e_time:.1f}]")
                slice_wav = os.path.join(sermon_dir, f"slice_{s_time}_{e_time}.wav")
                slice_audio = chunk_audio[int(s_time*1000):int(e_time*1000)]
                slice_audio.export(slice_wav, format="wav")

                transcriptions = {
                    "sensevoice": transcribe_with_sensevoice(slice_wav),
                    "whisperx": transcribe_with_whisperx(slice_wav),
                    "paraformer": transcribe_with_paraformer_zh(slice_wav),
                    "funasr_nano": transcribe_with_funasr_nano(slice_wav),
                    "openai_api": transcribe_with_openai_api(slice_wav),
                    "groq": transcribe_with_groq(slice_wav),
                    "deepgram": transcribe_with_deepgram(slice_wav),
                    "hf_inference": transcribe_with_hf_inference(slice_wav),
                    "google_chirp": transcribe_with_google_chirp3(slice_wav),
                }

                merged = merge_transcriptions(transcriptions, context_str, llm_log_path)
                corrected_segments_map[(s_time, e_time)] = merged
                safe_remove(slice_wav)

        # 3.4 Assemble and Loop until Perfect
        print("   -> Assembling and verifying transcription quality...")
        max_retries = 3
        current_text = assemble_corrected_chunk(base_segments, corrected_segments_map, context_str, llm_log_path)

        for attempt in range(max_retries):
            print(f"   -> Quality check (attempt {attempt + 1})...")
            is_perfect, feedback = judge_transcription_quality(current_text, context_str, llm_log_path)

            if is_perfect:
                print("   ✅ Transcription judged as perfect.")
                break

            print(f"   ⚠️ Not perfect yet: {feedback}")
            new_bad_timeframes = find_timeframes_from_feedback(current_text, feedback, base_segments, llm_log_path)
            if not new_bad_timeframes:
                break

            print(f"   -> Retrying {len(new_bad_timeframes)} problematic areas...")
            new_corrections = {}
            for tf in new_bad_timeframes:
                s_time, e_time = tf['start'], tf['end']
                slice_wav = os.path.join(sermon_dir, f"retry_{attempt}_{s_time}_{e_time}.wav")
                slice_audio = chunk_audio[int(s_time*1000):int(e_time*1000)]
                slice_audio.export(slice_wav, format="wav")

                transcriptions = {
                    "sensevoice": transcribe_with_sensevoice(slice_wav),
                    "whisperx": transcribe_with_whisperx(slice_wav),
                    "paraformer": transcribe_with_paraformer_zh(slice_wav),
                    "google_chirp": transcribe_with_google_chirp3(slice_wav),
                    "openai_api": transcribe_with_openai_api(slice_wav),
                }
                new_corrections[(s_time, e_time)] = merge_transcriptions(transcriptions, context_str, llm_log_path)
                safe_remove(slice_wav)

            current_text = assemble_corrected_chunk([{'text': current_text}], new_corrections, context_str, llm_log_path)

        # 3.5 Final Error Picking & Refine
        print("   -> Running final error picking and refinement...")
        corrected_text = error_picking(current_text, context_str, llm_log_path)
        refined_text = refine_text(corrected_text, context_str, llm_log_path)
        full_refined_text.append(refined_text)

        # 3.6 Finalize Lyric
        entry = f"[{format_timestamp(start_ms/1000)} --> {format_timestamp(end_ms/1000)}] {corrected_text}"
        with open(final_lyric_path, "a", encoding="utf-8") as f:
            f.write(entry + "\n")

        safe_remove(chunk_wav)

    # 3.7 Global Finalize
    with open(final_zh_path, "w", encoding="utf-8") as f:
        f.write("\n\n".join(full_refined_text))


def transcribe_with_sensevoice(audio_path: str) -> str:
    """Transcribe with SenseVoiceSmall."""
    model = _get_model("iic/SenseVoiceSmall", device=DEVICE,
                       disable_update=True)
    res = model.generate(input=audio_path, cache={}, language="zh",
                         use_itn=True)
    return re.sub(r'<\|.*?\|>', '', res[0]['text']).strip() if res else ""


def transcribe_with_whisperx(audio_path: str) -> str:
    """Transcribe with WhisperX (faster-whisper)."""
    root = os.path.expanduser('~/llm_models/whisperx')
    model = _get_model("base", is_whisper=True, device="cpu",
                       compute_type=COMPUTE_TYPE,
                       download_root=root)
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio, batch_size=16)
    return result["text"].strip() if result and "text" in result else ""


def transcribe_with_paraformer_zh(audio_path: str) -> str:
    """Transcribe with Paraformer-large."""
    model_id = "iic/speech_paraformer-large_asr_nat-zh-cn-" \
               "16k-common-vocab8404-pytorch"
    model = _get_model(model_id, device=DEVICE, disable_update=True)
    res = model.generate(input=audio_path, cache={})
    return res[0]["text"].strip() if res else ""


def transcribe_with_funasr_nano(audio_path: str) -> str:
    """Transcribe with Fun-ASR-Nano-2512."""
    model_id = "FunAudioLLM/Fun-ASR-Nano-2512"
    model = _get_model(model_id, device=DEVICE, disable_update=True)
    res = model.generate(input=audio_path, cache={})
    return res[0]["text"].strip() if res else ""


def transcribe_with_openai_api(audio_path: str) -> str:
    """Transcribe with OpenAI Whisper-1 API."""
    if not os.getenv("OPENAI_API_KEY"):
        return ""
    from openai import OpenAI
    client = OpenAI()
    try:
        with open(audio_path, "rb") as f:
            res = client.audio.transcriptions.create(
                model="whisper-1", file=f, language="zh"
            )
        return res.text.strip()
    except Exception as e:
        print(f"⚠️ OpenAI API Error: {e}")
        return ""


def transcribe_with_groq(audio_path: str) -> str:
    """Transcribe with Groq (Whisper-large-v3) API."""
    if not os.getenv("GROQ_API_KEY"):
        return ""
    from groq import Groq
    client = Groq()
    try:
        with open(audio_path, "rb") as f:
            res = client.audio.transcriptions.create(
                model="whisper-large-v3", file=f, language="zh"
            )
        return res.text.strip()
    except Exception as e:
        print(f"⚠️ Groq API Error: {e}")
        return ""


def transcribe_with_deepgram(audio_path: str) -> str:
    """Transcribe with Deepgram (Nova-2) API."""
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        return ""
    from deepgram import DeepgramClient, FileSource, PrerecordedOptions
    try:
        deepgram = DeepgramClient(api_key)
        with open(audio_path, "rb") as file:
            buffer_data = file.read()
        payload: FileSource = {"buffer": buffer_data}
        options = PrerecordedOptions(model="nova-2", smart_format=True,
                                     language="zh-CN")
        res = deepgram.listen.rest.v("1").transcribe_file(payload, options)
        return res.results.channels[0].alternatives[0].transcript.strip()
    except Exception as e:
        print(f"⚠️ Deepgram API Error: {e}")
        return ""


def transcribe_with_hf_inference(audio_path: str) -> str:
    """Transcribe with Hugging Face Inference API."""
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        return ""
    import requests
    model_id = "openai/whisper-large-v3-turbo"
    api_url = f"https://api-inference.huggingface.co/models/{model_id}"
    headers = {"Authorization": f"Bearer {hf_token}"}
    try:
        with open(audio_path, "rb") as f:
            data = f.read()
        response = requests.post(api_url, headers=headers, data=data)
        if response.status_code == 200:
            return response.json().get("text", "").strip()
        return ""
    except Exception:
        return ""


def transcribe_with_google_chirp3(audio_path: str) -> str:
    """Transcribe with Google Cloud STT V2 (Chirp 3)."""
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return ""
    try:
        from google.cloud.speech_v2 import SpeechClient
        from google.cloud.speech_v2.types import cloud_speech
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        client = SpeechClient()
        with open(audio_path, "rb") as f:
            audio_content = f.read()
        config = cloud_speech.RecognitionConfig(
            auto_decoding_config=cloud_speech.AutoDetectDecodingConfig(),
            language_codes=["cmn-Hans-CN"], model="chirp",
        )
        request = cloud_speech.RecognizeRequest(
            recognizer=f"projects/{project_id}/locations/global/recognizers/_",
            config=config, content=audio_content,
        )
        response = client.recognize(request=request)
        return " ".join([r.alternatives[0].transcript
                         for r in response.results]).strip()
    except Exception as e:
        print(f"⚠️ Google Chirp Error: {e}")
        return ""


def transcribe_base_with_timestamps(audio_path: str) -> list[dict]:
    """Transcribe with WhisperX and return timestamped segments."""
    root = os.path.expanduser('~/llm_models/whisperx')
    model = _get_model("base", is_whisper=True, device="cpu",
                       compute_type=COMPUTE_TYPE,
                       download_root=root)
    audio = whisperx.load_audio(audio_path)
    result = model.transcribe(audio, batch_size=16)
    return result.get("segments", [])


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
    valid_texts = {k: v for k, v in texts.items() if v}
    if not valid_texts:
        return ""
    if len(valid_texts) == 1:
        return list(valid_texts.values())[0]

    transcriptions_formatted = "\n".join([f"- {m}: {t}"
                                          for m, t in valid_texts.items()])
    prompt = f"Merge these ASR transcriptions. CONTEXT:\n{context_str}\n\n" \
             f"TRANSCRIPTIONS:\n{transcriptions_formatted}\n\n" \
             'Return JSON: {"data": "merged text..."}'
    res = ask_llm(prompt, log_path=log_path)
    return res.get("data", list(valid_texts.values())[0])


def find_inaccurate_timeframes(segments: list[dict], context_str: str,
                               log_path: str) -> list[dict]:
    """Identify timeframes that need re-transcription."""
    if not segments:
        return []
    formatted = "\n".join([f"[{s['start']:.1f} - {s['end']:.1f}] {s['text']}"
                           for s in segments])
    prompt = f"Analyze transcription. Identify inaccuracy. CONTEXT:\n" \
             f"{context_str}\n\nTRANSCRIPTION:\n{formatted}\n\n" \
             'Return JSON: {"data": [{"start": 10.5, "end": 25.0}]}'
    res = ask_llm(prompt, log_path=log_path)
    return res.get("data", [])


def judge_transcription_quality(text: str, context_str: str,
                               log_path: str) -> tuple[bool, str]:
    """Judge if transcription is perfect."""
    prompt = f"Evaluate transcription. CONTEXT:\n{context_str}\n\n" \
             f"TEXT:\n{text}\n\nReturn JSON: " \
             '{"is_perfect": true/false, "feedback": "..."}'
    res = ask_llm(prompt, log_path=log_path)
    return res.get("is_perfect", True), res.get("feedback", "")


def find_timeframes_from_feedback(text: str, feedback: str,
                                 segments: list[dict],
                                 log_path: str) -> list[dict]:
    """Map feedback to timeframes."""
    formatted = "\n".join([f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}"
                           for s in segments])
    prompt = f"Identify timeframes. FEEDBACK:\n{feedback}\n\n" \
             f"SEGMENTS:\n{formatted}\n\nReturn JSON: " \
             '{"data": [{"start": 10.5, "end": 15.0}]}'
    res = ask_llm(prompt, log_path=log_path)
    return res.get("data", [])


def assemble_corrected_chunk(base_segments: list[dict], corrected_map: dict,
                             context_str: str, log_path: str) -> str:
    """Weave corrections into base text."""
    base_text = " ".join([s.get('text', '') for s in base_segments])
    if not corrected_map:
        return base_text
    corr_str = "\n".join([f"[{s:.1f}-{e:.1f}]: {t}"
                          for (s, e), t in corrected_map.items()])
    prompt = f"Assemble final text. BASE:\n{base_text}\n\n" \
             f"CORRECTIONS:\n{corr_str}\n\n" \
             'Return JSON: {"data": "assembled text..."}'
    res = ask_llm(prompt, log_path=log_path)
    return res.get("data", base_text)


def error_picking(text: str, context_str: str, log_path: str) -> str:
    """Fix obvious ASR errors."""
    if not text or len(text.strip()) < 2:
        return text
    prompt = f"Fix ASR errors. CONTEXT:\n{context_str}\n\n" \
             f"TEXT: {text}\n\n" \
             'Return JSON: {"data": "corrected..."}'
    res = ask_llm(prompt, log_path=log_path)
    return res.get("data", text)


def refine_text(text: str, context_str: str, log_path: str) -> str:
    """Polish the text."""
    if not text or len(text.strip()) < 2:
        return text
    prompt = f"Refine text. CONTEXT:\n{context_str}\n\n" \
             f"TEXT: {text}\n\n" \
             'Return JSON: {"data": "refined text..."}'
    res = ask_llm(prompt, log_path=log_path)
    return res.get("data", text)


def format_timestamp(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    ts = int(td.total_seconds())
    return f"{ts//3600:02d}:{(ts%3600)//60:02d}:{ts%60:02d}." \
           f"{int(td.microseconds/1000):03d}"


def load_and_build_context(sermon_dir: str) -> dict:
    metadata = _load_json(os.path.join(sermon_dir, "metadata.json"))
    preacher_dir = os.path.dirname(os.path.dirname(sermon_dir))
    profile = _load_json(os.path.join(preacher_dir, "profile.json"))
    scripture_ref = metadata.get('scripture')
    bible_context = get_bible_verses_by_ref(scripture_ref)
    preacher = metadata.get('preacher', 'Unknown Preacher')
    context_str = f"Preacher: {preacher}\nSeries: {metadata.get('series')}\n" \
                  f"Scripture: {scripture_ref}\n" \
                  f"Accent: {profile.get('accent')}"
    if bible_context:
        context_str += f"\nBible Context: {bible_context}"
    return {
        "context_str": context_str,
        "preacher": preacher,
        "title": metadata.get('title')
    }


def _load_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


@lru_cache(maxsize=1)
def get_bible_verses_by_ref(scripture_ref: str | None = None) -> str:
    if not scripture_ref or not os.path.exists(BIBLE_DB_PATH):
        return ""
    match = re.match(r"^(.*?)(?:\s+ch(\d+))?(?::v(\d+))?$", scripture_ref)
    if not match:
        return ""
    book_en, chapter, verse = match.groups()
    book_zh = BIBLE_EN_TO_ZH.get(book_en.strip())
    if not book_zh:
        return ""
    conn = sqlite3.connect(BIBLE_DB_PATH)
    cursor = conn.cursor()
    query = "SELECT book, chapter, verse, text FROM verses " \
            "WHERE (book = ? OR book = ?)"
    params = [book_zh, ZH_TO_ABBREV_MAP.get(book_zh)]
    if chapter:
        query += " AND chapter = ?"
        params.append(chapter)
    if verse:
        query += " AND verse = ?"
        params.append(verse)
    cursor.execute(query, params)
    results = [f"{b} {c}:{v} - \"{t}\"" for b, c, v, t in cursor.fetchall()]
    conn.close()
    return "; ".join(results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "audio_path",
        nargs="?",
        default="output/stephen-tong/ephesians/"
        "001_answers-to-questions-on-ephesians-0-a/"
        "original.mp3"
    )
    args = parser.parse_args()
    main(args.audio_path)


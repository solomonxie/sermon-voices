import os
import json
import math
import argparse
import tempfile
from glob import glob
from time import time

import gc
import torch
from pydub import AudioSegment

from src.common import ask_llm, safe_remove, get_custom_instructions, safe_write, safe_replace
from src.constants import OUTPUT_ROOT, MODELSCOPE_CACHE

ASR_MODEL = None

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2: Audio Transcription & Refinement")
    parser.add_argument("audio_path", help="Path to the original.mp3 file to process")
    args = parser.parse_args()

    print(f"\n--- Phase 2: Audio Transcription & Refinement ---")
    process_sermon(args.audio_path)


def process_sermon(audio_path: str) -> None:
    """
    Processes a single sermon: Split -> Transcribe -> Refine -> Finalize.
    """
    sermon_dir = os.path.dirname(audio_path)
    final_zh = os.path.join(sermon_dir, 'transcript_zh.txt')

    # Checkpoint: Skip if already processed or audio missing
    if os.path.exists(final_zh) or not os.path.exists(audio_path):
        return

    print(f"\n⚙️ Processing: {audio_path}")

    # 1. Split audio into 1-min chunks
    chunk_paths = split_audio(audio_path)

    # 2. Sequential processing
    orig_tmp = os.path.join(sermon_dir, 'transcript_original_tmp.txt')
    punc_tmp = os.path.join(sermon_dir, 'transcript_punc_tmp.txt')
    zh_tmp = os.path.join(sermon_dir, 'transcript_zh_tmp.txt')

    safe_remove(orig_tmp)
    safe_remove(punc_tmp)
    safe_remove(zh_tmp)

    prev_context = ""
    for chunk_path in chunk_paths:
        prev_context = process_chunk(chunk_path, prev_context=prev_context)

    # 3. Finalize: replace tmp with final and cleanup
    safe_replace(zh_tmp, final_zh)
    if os.path.exists(final_zh):
        print(f"✅ Saved refined ZH transcript: {final_zh}")
        # Cleanup intermediate steps
        safe_remove(orig_tmp)
        safe_remove(punc_tmp)

    print(f"✅ Audio processing complete: {audio_path}")


def split_audio(audio_path: str) -> list[str]:
    """
    Splits original.mp3 into 30-second chunks with no overlap.
    Saves to a 'chunks/' subfolder as WAV (16kHz, mono).
    """
    sermon_dir = os.path.dirname(audio_path)
    chunks_dir = os.path.join(sermon_dir, 'chunks')
    os.makedirs(chunks_dir, exist_ok=True)

    print(f"🎙️ Splitting audio: {audio_path}")
    audio = AudioSegment.from_file(audio_path)

    total_ms = len(audio)
    chunk_ms = 60 * 1000  # 60 seconds - Qwen3-ASR handles longer audio well
    overlap_ms = 0 # No overlap to prevent repetitions

    chunk_paths = []
    # Step through with precisely chunk_ms intervals
    for i, start_ms in enumerate(range(0, total_ms, chunk_ms)):
        end_ms = min(start_ms + chunk_ms, total_ms)
        chunk_name = f"chunk_{i:03d}.wav"
        cp = os.path.join(chunks_dir, chunk_name)

        # Only export if doesn't exist to save time
        if not os.path.exists(cp):
            chunk = audio[start_ms:end_ms]
            # Qwen3-ASR works with 16kHz mono PCM
            chunk = chunk.set_frame_rate(16000).set_channels(1)
            chunk.export(cp, format="wav", codec="pcm_s16le")

        chunk_paths.append(cp)
        if end_ms >= total_ms: break

    return sorted(chunk_paths)


def process_chunk(audio_path: str, prev_context: str = "") -> str:
    """
    Processes a single audio chunk: Transcribe -> Refine -> Append.
    Returns the refined ZH text to be used as context for the next chunk.
    """
    print(f"🎙️ Reading chunk: {os.path.basename(audio_path)}")
    sermon_dir = os.path.dirname(os.path.dirname(audio_path))
    orig_tmp = os.path.join(sermon_dir, 'transcript_original_tmp.txt')
    punc_tmp = os.path.join(sermon_dir, 'transcript_punc_tmp.txt')
    zh_tmp = os.path.join(sermon_dir, 'transcript_zh_tmp.txt')
    
    # Load custom instructions for this preacher
    preacher_dir = os.path.dirname(os.path.dirname(sermon_dir))
    transcript_instr = get_custom_instructions(preacher_dir, "transcript.md")

    # 1. Transcribe
    text = transcribe_audio(audio_path)
    if not text.strip(): return ""
    
    safe_write(orig_tmp, text)

    # 1.5 Enhance Punctuation
    text_punc = enhance_punctuation(text)
    safe_write(punc_tmp, text_punc)

    # 2. Refine (ZH)
    refined_zh = refine_text(text_punc, custom_instructions=transcript_instr, prev_context=prev_context)
    
    safe_write(zh_tmp, refined_zh)
            
    return refined_zh


def get_asr_model(force_cpu: bool = False):
    """
    Lazy loader for Qwen3-ASR-0.6B.
    """
    global ASR_MODEL
    if ASR_MODEL is not None:
        return ASR_MODEL

    from qwen_asr import Qwen3ASRModel
    
    # Set ModelScope cache directory
    os.environ["MODELSCOPE_CACHE"] = MODELSCOPE_CACHE
    
    print(f"🚀 Loading Qwen3-ASR-0.6B from ModelScope...")
    
    start = time()
    
    # Use transformers backend (simpler, no vLLM required)
    ASR_MODEL = Qwen3ASRModel.from_pretrained(
        "Qwen/Qwen3-ASR-0.6B",
        dtype=torch.bfloat16,
        device_map="auto",
        max_inference_batch_size=8,
        max_new_tokens=512,
    )
    
    print(f"\tASR Model loaded in {time()-start:,.0f}s")
    return ASR_MODEL


PUNC_MODEL = None

def get_punc_model():
    """
    Lazy loader for ct-punc model via FunASR.
    """
    global PUNC_MODEL
    if PUNC_MODEL is not None:
        return PUNC_MODEL

    from funasr import AutoModel # Import only when needed to avoid conflicts
    print(f"🚀 Loading ct-punc (Punctuation)...")
    funasr_root = os.path.expanduser("~/llm_models/funasr")
    os.environ["MODELSCOPE_CACHE"] = funasr_root

    start = time()
    PUNC_MODEL = AutoModel(
        model="iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
        device="cuda" if torch.cuda.is_available() else "cpu",
        disable_update=True
    )
    print(f"\tPunctuation Model loaded in {time()-start:,.0f}s")
    return PUNC_MODEL


def transcribe_audio(audio_path: str) -> str:
    """
    Transcribes audio using Qwen3-ASR with memory safety.
    """
    model = get_asr_model()
    
    # Qwen3-ASR has a much simpler API
    results = model.transcribe(
        audio=audio_path,
        language=None,  # Auto-detect language (Chinese or English)
    )
    
    # Immediate cleanup for MPS stability
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    gc.collect()

    if not results: return ""
    # results[0] contains the transcription result
    return results[0].text.strip()


def enhance_punctuation(text: str) -> str:
    """
    Enhances punctuation of a text segment using ct-punc.
    """
    print(f"💉 Enhancing punctuation...")
    model = get_punc_model()
    res = model.generate(input=text)
    return res[0].get('text', text).strip()


def refine_text(text: str, custom_instructions: str = "", prev_context: str = "") -> str:
    """
    Refines Chinese transcript for biblical accuracy and punctuation.
    """
    print(f"✍️ Refining ZH text segment...")

    context_prefix = ""
    if prev_context.strip():
        # Only take the last bit of the previous context to avoid bloating the prompt
        context_tail = prev_context[-300:] if len(prev_context) > 300 else prev_context
        context_prefix = f"\nPREVIOUS CONTEXT (for flow and transition only):\n...{context_tail}\n--- END PREVIOUS CONTEXT ---\n"

    prompt = f"""
    Refine this Chinese sermon transcript based on the following rules:
    1. BIBLICAL CONTEXT: Ensure all terms, names, and theological concepts follow Chinese Union Version (CUV) or standard biblical terminology.
    2. BIBLICAL NAMES: Prioritize biblical names over phonetic or common Chinese names (e.g., '彼得' instead of phonetically similar names, or '锡安' instead of '西安').
    3. PUNCTUATION & FLOW: Improve punctuation for readability. Separate text into logical paragraphs.
    4. CONTEXTUAL SENSE: Each sentence MUST make sense in the surrounding context. Correct grammatical errors. Rephrase sentences to make them clear, natural, and professional.
    5. REDUNDANCY REMOVAL: Aggressively remove oral repetitions, filler words, and meaningfully identical phrases. Consolidate repeated points into a single, cohesive statement.
    6. TONE & STYLE: Maintain the preacher's original tone, depth, and "voice."
       - DO NOT turn the transcript into a structural summary or an essay.
       - This is a TRANSCRIPT, not a summary. Keep the first-person perspective if present.
    7. TRANSITIONS: Use the provided 'PREVIOUS CONTEXT' to ensure the current chunk flows naturally from the last sentence of the previous segment. Do NOT repeat content already present in the previous context.
    8. POLISH: Polish each sentence to make it more smooth and more biblical.

    Output MUST be a valid JSON object with a single key 'refined_text' containing the refined content.
    Do NOT include any markdown formatting, preamble, or footer.
    {custom_instructions}
    {context_prefix}

    Content to Refine:
    {text}
    """
    data = ask_llm(prompt, num_ctx=10240)
    return data.get('refined_text', text)
    

if __name__ == '__main__':
    main()

import os
import json
import math
import tempfile
from glob import glob
from time import time

import gc
import torch
from qwen_asr import Qwen3ASRModel

from pydub import AudioSegment
from src.common import ask_llm, safe_remove, get_custom_instructions, safe_write, safe_replace
from src.constants import OUTPUT_ROOT

ASR_MODEL = None

def main() -> None:
    print(f"\n--- Phase 2: Audio Transcription & Refinement ---")
    metadata_files = glob(os.path.join(OUTPUT_ROOT, '**/metadata.json'), recursive=True)
    # debug---------- (optional: user had one break in draft)
    metadata_files = [
        'output/hua-xian/acts/001_do-not-leave-jerusalem/metadata.json',
        'output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/metadata.json',
    ]

    for metadata_path in sorted(metadata_files):
        process_sermon(metadata_path)


def process_sermon(metadata_path: str) -> None:
    """
    Processes a single sermon: Split -> Transcribe -> Refine -> Finalize.
    """
    sermon_dir = os.path.dirname(metadata_path)
    audio_path = os.path.join(sermon_dir, 'original.mp3')
    final_zh = os.path.join(sermon_dir, 'transcript_zh.txt')

    # Checkpoint: Skip if already processed or audio missing
    if os.path.exists(final_zh) or not os.path.exists(audio_path):
        return

    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    print(f"\n⚙️ Processing: {metadata.get('title')} ({metadata_path})")

    # 1. Split audio into 1-min chunks
    chunk_paths = split_audio(metadata_path)

    # 2. Sequential processing
    orig_tmp = os.path.join(sermon_dir, 'transcript_original_tmp.txt')
    punc_tmp = os.path.join(sermon_dir, 'transcript_punc_tmp.txt')
    zh_tmp = os.path.join(sermon_dir, 'transcript_zh_tmp.txt')

    safe_remove(orig_tmp)
    safe_remove(punc_tmp)
    safe_remove(zh_tmp)

    prev_context = ""
    for chunk_path in chunk_paths:
        try:
            prev_context = process_chunk(chunk_path, prev_context=prev_context)
        except Exception as e:
            print(f"❌ Error processing chunk {chunk_path}: {str(e)}")
            prev_context = ""

    # 3. Finalize: replace tmp with final and cleanup
    safe_replace(zh_tmp, final_zh)
    if os.path.exists(final_zh):
        print(f"✅ Saved refined ZH transcript: {final_zh}")
        # Cleanup intermediate steps
        safe_remove(orig_tmp)
        safe_remove(punc_tmp)

    print(f"✅ Audio processing complete: {metadata['title']}")


def split_audio(metadata_path: str) -> list[str]:
    """
    Splits original.mp3 into 1-minute chunks with no overlap.
    Saves to a 'chunks/' subfolder.
    """
    sermon_dir = os.path.dirname(metadata_path)
    audio_path = os.path.join(sermon_dir, 'original.mp3')
    chunks_dir = os.path.join(sermon_dir, 'chunks')
    os.makedirs(chunks_dir, exist_ok=True)

    print(f"🎙️ Splitting audio: {audio_path}")
    audio = AudioSegment.from_file(audio_path)

    total_ms = len(audio)
    chunk_ms = 60 * 1000  # 1 minute
    overlap_ms = 0 # No overlap to prevent repetitions

    chunk_paths = []
    # Step through with precisely chunk_ms intervals
    for i, start_ms in enumerate(range(0, total_ms, chunk_ms)):
        end_ms = min(start_ms + chunk_ms, total_ms)
        chunk_name = f"chunk_{i:03d}.mp3"
        cp = os.path.join(chunks_dir, chunk_name)

        # Only export if doesn't exist to save time
        if not os.path.exists(cp):
            chunk = audio[start_ms:end_ms]
            chunk.export(cp, format="mp3")

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
    Lazy loader for Qwen3-ASR-1.7B via qwen-asr library.
    """
    global ASR_MODEL
    if ASR_MODEL is not None:
        # If we already have a model and it's on the wrong device, we'd need to reload. 
        # But for now, we assume once it's on CPU it stays there if forced.
        if force_cpu and next(ASR_MODEL.model.parameters()).device.type != 'cpu':
             ASR_MODEL = None
        else:
            return ASR_MODEL

    print(f"🚀 Loading Qwen3-ASR-1.7B (ASR)...")
    
    huggingface_root = os.path.expanduser("~/llm_models/huggingface")
    os.environ["HF_HOME"] = huggingface_root
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
    
    # Optimization for MPS memory pressure: Set both Low and High to avoid "invalid ratio" errors
    # Low must be <= High. Default low is often 1.4, so setting high to 0.7 triggers error.
    os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.7"
    os.environ["PYTORCH_MPS_LOW_WATERMARK_RATIO"] = "0.5"

    start = time()
    
    # Device and dtype optimization for Mac/MPS, CUDA, or CPU
    if torch.backends.mps.is_available() and not force_cpu:
        print(f"\tUsing Apple Silicon (MPS) acceleration")
        device_map = "mps"
        dtype = torch.float16
    elif torch.cuda.is_available() and not force_cpu:
        print(f"\tUsing CUDA acceleration")
        device_map = "auto"
        dtype = torch.bfloat16
    else:
        print(f"\tUsing CPU (Slow but Stable)")
        device_map = None
        dtype = torch.float32

    ASR_MODEL = Qwen3ASRModel.from_pretrained(
        "Qwen/Qwen3-ASR-1.7B",
        dtype=dtype,
        device_map=device_map,
        max_inference_batch_size=1, # Reduced for memory stability
        cache_dir=huggingface_root,
    )
    
    # Suppress "Setting `pad_token_id` to `eos_token_id`" warning
    if ASR_MODEL.model.config.pad_token_id is None:
        ASR_MODEL.model.config.pad_token_id = ASR_MODEL.model.config.eos_token_id

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
    Transcribes audio using Qwen3-ASR with memory safety and fallbacks.
    """
    try:
        model = get_asr_model()
        results = model.transcribe(
            audio=audio_path,
            language=None, # auto language detection
        )
        
        # Immediate cleanup for MPS stability
        if torch.backends.mps.is_available():
            torch.mps.empty_cache()
        gc.collect()

        if not results: return ""
        return " ".join([entry.text for entry in results]).strip()
    except Exception as e:
        # Check if it's a memory or backend error
        err_msg = str(e)
        if any(kw in err_msg for kw in ["MPS", "Memory", "buffer", "command buffer"]):
            print(f"⚠️ ASR Backend Error: {err_msg}. Falling back to CPU...")
            model = get_asr_model(force_cpu=True)
            results = model.transcribe(audio=audio_path, language=None)
            return " ".join([entry.text for entry in results]).strip()
        raise e


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
    try:
        data = ask_llm(prompt, num_ctx=8192)
        return data.get('refined_text', text)
    except Exception as e:
        print(f"⚠️ Refinement failed, using original text: {e}")
        return text




if __name__ == '__main__':
    main()

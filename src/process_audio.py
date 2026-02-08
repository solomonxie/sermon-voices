import os
import json
import math
import tempfile
from glob import glob
from time import time
from src.common import ask_llm, safe_remove, get_custom_instructions
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
        sermon_dir = os.path.dirname(metadata_path)
        final_zh = os.path.join(sermon_dir, 'transcript_zh.txt')
        
        # Checkpoint: Skip if already processed
        if os.path.exists(final_zh):
            continue
            
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        print(f"\n⚙️ Processing: {metadata.get('title')} ({metadata_path})")
        
        # 1. Split audio into 1-min chunks with 10s overlap
        chunk_paths = split_audio(metadata_path)
        
        # 2. Sequential processing
        zh_tmp = os.path.join(sermon_dir, 'transcript_zh_tmp.txt')
        
        safe_remove(zh_tmp)
            
        # Load custom instructions for this preacher
        preacher_dir = os.path.dirname(os.path.dirname(sermon_dir))
        transcript_instr = get_custom_instructions(preacher_dir, "transcript.md")

        prev_context = ""
        for chunk_path in chunk_paths:
            try:
                prev_context = process_chunk(chunk_path, zh_tmp, transcript_instr, prev_context=prev_context)
            except Exception as e:
                print(f"❌ Error processing chunk {chunk_path}: {str(e)}")
                prev_context = ""
            
        # 3. Finalize: move tmp to final
        if os.path.exists(zh_tmp):
            os.replace(zh_tmp, final_zh)
            print(f"✅ Saved refined ZH transcript: {final_zh}")

        print(f"✅ Audio processing complete: {metadata['title']}")


def split_audio(metadata_path: str) -> list[str]:
    """
    Splits original.mp3 into 1-minute chunks with no overlap.
    Saves to a 'chunks/' subfolder.
    """
    from pydub import AudioSegment
    sermon_dir = os.path.dirname(metadata_path)
    audio_path = os.path.join(sermon_dir, 'original.mp3')
    chunks_dir = os.path.join(sermon_dir, 'chunks')
    os.makedirs(chunks_dir, exist_ok=True)

    if not os.path.exists(audio_path):
        return []

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


def process_chunk(audio_path: str, zh_tmp_path: str, transcript_instr: str = "", prev_context: str = "") -> str:
    """
    Processes a single audio chunk: Transcribe -> Refine -> Append.
    Returns the refined ZH text to be used as context for the next chunk.
    """
    print(f"🎙️ Reading chunk: {os.path.basename(audio_path)}")
    
    # 1. Transcribe
    text = transcribe_audio(audio_path)
    if not text.strip(): return

    # 1.5 Enhance Punctuation
    text = enhance_punctuation(text)

    # 2. Refine (ZH)
    refined_zh = refine_text(text, custom_instructions=transcript_instr, prev_context=prev_context)
    with open(zh_tmp_path, 'a', encoding='utf-8') as f:
        f.write(refined_zh + "\n\n")
    
    return refined_zh


def get_asr_model():
    """
    Lazy loader for Paraformer-large.
    """
    global ASR_MODEL
    if ASR_MODEL is not None:
        return ASR_MODEL

    import torch
    from funasr import AutoModel
    
    print(f"🚀 Loading Paraformer-large (ASR)...")
    funasr_root = os.path.expanduser("~/llm_models/funasr")
    os.environ["MODELSCOPE_CACHE"] = funasr_root
    
    start = time()
    ASR_MODEL = AutoModel(
        model="iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        # punc_model="iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
        device="cuda" if torch.cuda.is_available() else "cpu",
        disable_update=True
    )
    print(f"\tASR Model loaded in {time()-start:,.0f}s")
    return ASR_MODEL


PUNC_MODEL = None

def get_punc_model():
    """
    Lazy loader for ct-punc model.
    """
    global PUNC_MODEL
    if PUNC_MODEL is not None:
        return PUNC_MODEL

    import torch
    from funasr import AutoModel
    
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
    Transcribes audio using Paraformer-large.
    """
    model = get_asr_model()
    res = model.generate(input=audio_path)
    if not res: return ""
    return res[0].get('text', '').strip()


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

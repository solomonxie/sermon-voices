import os
import json
import math
import tempfile
from glob import glob
from time import time
from src.common import ask_llm, safe_remove
from src.constants import OUTPUT_ROOT

ASR_MODEL = None

def main() -> None:
    print(f"\n--- Phase 2: Audio Transcription, Refinement & Translation ---")
    metadata_files = glob(os.path.join(OUTPUT_ROOT, '**/metadata.json'), recursive=True)
    
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
        en_tmp = os.path.join(sermon_dir, 'translation_en_tmp.txt')
        
        safe_remove(zh_tmp)
        safe_remove(en_tmp)
            
        for chunk_path in chunk_paths:
            try:
                process_chunk(chunk_path, zh_tmp, en_tmp)
            except Exception as e:
                print(f"❌ Error processing chunk {chunk_path}: {str(e)}")
            # break # debug---------- (optional: user had one break in draft)
            
        # 3. Finalize: move tmp to final
        if os.path.exists(zh_tmp):
            os.replace(zh_tmp, final_zh)
            print(f"✅ Saved refined ZH transcript: {final_zh}")
            
        final_en = os.path.join(sermon_dir, 'translation_en.txt')
        if os.path.exists(en_tmp):
            os.replace(en_tmp, final_en)
            print(f"✅ Saved translation: {final_en}")

        print(f"✅ Audio processing complete: {metadata['title']}")
        # break # debug---------- (keep the outer break for now as in draft)


def split_audio(metadata_path: str) -> list[str]:
    """
    Splits original.mp3 into 1-minute chunks with 10s overlap.
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
    overlap_ms = 10 * 1000 # 10 seconds
    
    chunk_paths = []
    # Step through with (chunk_ms - overlap_ms) to maintain overlap
    for i, start_ms in enumerate(range(0, total_ms, chunk_ms - overlap_ms)):
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


def process_chunk(audio_path: str, zh_tmp_path: str, en_tmp_path: str) -> None:
    """
    Processes a single audio chunk: Transcribe -> Refine -> Translate -> Append.
    """
    print(f"🎙️ Reading chunk: {os.path.basename(audio_path)}")
    
    # 1. Transcribe
    text = transcribe_audio(audio_path)
    if not text.strip(): return

    # 1.5 Enhance Punctuation
    text = enhance_punctuation(text)

    # 2. Refine (ZH)
    refined_zh = refine_text(text)
    with open(zh_tmp_path, 'a', encoding='utf-8') as f:
        f.write(refined_zh + "\n\n")

    # 3. Translate (EN)
    translated_en = translate_text(refined_zh)
    with open(en_tmp_path, 'a', encoding='utf-8') as f:
        f.write(translated_en + "\n\n")


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
    if not res: return text
    return res[0].get('text', text).strip()


def refine_text(text: str) -> str:
    """
    Refines Chinese transcript for biblical accuracy and punctuation.
    """
    print(f"✍️ Refining ZH text segment...")
    prompt = f"""
    Refine this Chinese sermon transcript based on the following rules:
    1. BIBLICAL CONTEXT: Ensure all terms, names, and theological concepts follow Chinese Union Version (CUV) or standard biblical terminology. 
    2. BIBLICAL NAMES: Prioritize biblical names over phonetic or common Chinese names (e.g., '彼得' instead of phonetically similar names).
    3. PUNCTUATION & FLOW: Improve punctuation for readability. Separate text into logical paragraphs.
    4. CONTEXTUAL SENSE: Each sentence MUST make sense in the surrounding context. Correct grammatical errors.
    5. CLEANUP: Remove nonsensical filler words, duplicate characters, or artifacts from transcription.
    
    Keep the content faithful to the original speech but make it professional and readable.

    Return ONLY the refined text in the 'refined_text' key of a JSON object.

    Content:
    {text}
    """
    data = ask_llm(prompt, num_ctx=8192)
    return data.get('refined_text', str(data))


def translate_text(text: str) -> str:
    """
    Translates ZH text to EN (Biblical and Professional style).
    """
    print(f"🌐 Translating to English...")
    prompt = f"""
    Translate the following Chinese sermon transcript to English based on these rules:
    1. BIBLICAL ACCURACY: Strictly follow biblical context. Use established English biblical names and terms (e.g., 'Zion' instead of 'Xi'an').
    2. NATIVE FLUENCY: Use professional, natural English suitable for a sermon.
    3. GRAMMATICAL CORRECTNESS: Ensure every phrase and sentence is grammatically correct and makes common sense.
    4. PRESERVE MEANING: Maintain the speaker's original intent and theological depth.

    Return ONLY the translation in the 'translation' key of a JSON object.

    Content:
    {text}
    """
    data = ask_llm(prompt, num_ctx=8192)
    return data.get('translation', str(data))


if __name__ == '__main__':
    main()

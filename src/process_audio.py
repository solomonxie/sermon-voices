import os
import re
import json
import math
import argparse
import tempfile
from glob import glob
from time import time

import gc
import torch
from pydub import AudioSegment

from src.common import ask_llm, safe_remove, get_custom_instructions, safe_write, safe_replace, string_similarity, retry
from src.constants import OUTPUT_ROOT, FUNASR_MODEL_ROOT

ASR_MODEL = None
# FunASR(Modelscope) model Root
os.environ["MODELSCOPE_CACHE"] = FUNASR_MODEL_ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2: Audio Transcription & Refinement")
    parser.add_argument("audio_path", help="Path to the original.mp3 file to process")
    args = parser.parse_args()
    # Set ModelScope cache directory
    os.environ["MODELSCOPE_CACHE"] = os.path.expanduser('~/llm_models/modelscope')

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
    errors_tmp = os.path.join(sermon_dir, 'transcript_errors_tmp.txt')
    zh_tmp = os.path.join(sermon_dir, 'transcript_zh_tmp.txt')

    safe_remove(orig_tmp)
    safe_remove(punc_tmp)
    safe_remove(errors_tmp)
    safe_remove(zh_tmp)

    for chunk_path in chunk_paths:
        process_chunk(chunk_path)

    # 3. Finalize: replace tmp with final and cleanup
    safe_replace(zh_tmp, final_zh)
    print(f"✅ Saved refined ZH transcript: {final_zh}")
    print(f"✅ Audio processing complete: {audio_path}")


def split_audio(audio_path: str) -> list[str]:
    sermon_dir = os.path.dirname(audio_path)
    chunks_dir = os.path.join(sermon_dir, 'chunks')
    os.makedirs(chunks_dir, exist_ok=True)
    print(f"🎙️ Splitting audio using VAD: {audio_path}")
    from funasr import AutoModel
    vad_model = AutoModel(
        model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        device="mps",  # if torch.backends.mps.is_available() else "cpu",
        disable_update=True
    )
    res = vad_model.generate(
        input=audio_path,
        max_end_silence_time=500,
        max_single_segment_time=60000,
    )
    audio = AudioSegment.from_file(audio_path)
    for chunk_idx, seg in enumerate(res[0]['value']):  # [[start, end], ...] in ms
        start_ms, end_ms = seg
        path = os.path.join(chunks_dir, f"chunk_{chunk_idx:03d}.mp3")
        chunk = audio[start_ms:end_ms]
        chunk = chunk.set_frame_rate(16000).set_channels(1)
        chunk.export(path, format="mp3", codec="libmp3lame")
    return sorted(glob(os.path.join(chunks_dir, "chunk_*.mp3")))


@retry(retries=3, delay=5.0)
def process_chunk(audio_path: str) -> str:
    print(f"🎙️ Reading chunk: {os.path.basename(audio_path)}")
    sermon_dir = os.path.dirname(os.path.dirname(audio_path))
    orig_tmp = os.path.join(sermon_dir, 'transcript_original_tmp.txt')
    errors_tmp = os.path.join(sermon_dir, 'transcript_errors_tmp.txt')
    zh_tmp = os.path.join(sermon_dir, 'transcript_zh_tmp.txt')
    
    preacher_dir = os.path.dirname(os.path.dirname(sermon_dir))
    transcript_instr = get_custom_instructions(preacher_dir, "transcript.md")
    
    # 1. Transcribe
    text = transcribe_audio(audio_path)
    if not text.strip(): return ""
    safe_write(orig_tmp, text)
    
    # 2. Bible Verse Lookup
    bible_context = lookup_bible_verses(text)
    
    # 3. Iterative Refinement
    refined_zh = text
    ralph_wiggum_loops = 5
    for i in range(ralph_wiggum_loops):
        print(f"🔄 Ralph Wiggum correction loop {i+1}/{ralph_wiggum_loops}...")
        errors = pick_zh_errors(refined_zh)
        safe_write(errors_tmp, f'Errors ({i=}):\n' + errors)
        
        if not errors.strip():
            print("✨ No more errors found.")
            break
            
        extra_context = f"""
            --- START BIBLE VERSE REFERENCE (CUV) ---
            {bible_context}
            --- END BIBLE VERSE REFERENCE ---
            --- START CUSTOM INSTRUCTIONS ---
            {transcript_instr}
            --- END CUSTOM INSTRUCTIONS ---
            --- START IDENTIFIED ERRORS ---
            {errors}
            --- END IDENTIFIED ERRORS ---
        """
        last_text = refined_zh
        refined_zh = refine_text(refined_zh, extra_context=extra_context)

        similarity = string_similarity(refined_zh, last_text)
        if similarity >= 0.999:
            print(f"⏹️ Text stabilized ({similarity:.1%} similarity), finishing loop.")
            break
            
    safe_write(zh_tmp, refined_zh)
    return refined_zh


def lookup_bible_verses(text: str) -> str:
    """
    Identifies related CUV Bible verses based on the transcription.
    """
    print(f"📖 Looking up related Bible verses...")
    prompt = f"""
    Based on the following sermon transcription segment, identify any related Bible verses (Chinese Union Version - CUV).
    For each sentence or idea, find the most likely verse it is referencing or quoting.
    
    Output the verses in the following format:
    - [Book Name] [Chapter]:[Verse] - [Full Verse Text in CUV]
    
    Transcription:
    {text}
    
    Output MUST be a JSON object: {{"verses": ["Verse 1 reference - text", "Verse 2 reference - text", ...]}}
    If no clear verses are found, return {{"verses": []}}.
    Do NOT include markdown, preamble, or explanations.
    """
    data = ask_llm(prompt, num_ctx=10240)
    verses = data.get('verses', [])
    return "\n".join(verses)


def transcribe_audio(audio_path: str) -> str:
    """
    Transcribes audio using SenseVoiceSmall with hotwords and memory safety.
    """
    from funasr import AutoModel
    # Load hotwords
    hotwords = ""
    hotwords_path = os.path.join(OUTPUT_ROOT, 'bible_hotwords_5000_zh.txt')
    if os.path.exists(hotwords_path):
        with open(hotwords_path, 'r', encoding='utf-8') as f:
            hotwords = " ".join([line.strip() for line in f if line.strip()])
    # FunASR AutoModel API with hotwords and ITN (Inverse Text Normalization)
    if ASR_MODEL is not None:
        model = ASR_MODEL
    else:
        model = AutoModel(model="FunAudioLLM/Fun-ASR-Nano-2512", device="mps", disable_update=True)
    results = model.generate(input=audio_path, hotword=hotwords, use_itn=True)
    if not results: return ""
    # Extract text from results and strip ASR event tags (e.g., <|zh|><|NEUTRAL|>)
    text = results[0].get('text', '').strip()
    text = re.sub(r'<\|.*?\|>', '', text)
    return text.strip()


def pick_zh_errors(text: str) -> str:
    """
    Identifies errors in the transcript (grammar, biblical facts, stammers).
    """
    print(f"🔍 Picking errors from transcript...")
    prompt = f"""
    Analyze the Chinese sermon transcript and identify errors. Be concise.

    ERROR CATEGORIES:
    - Grammar/Phrasing: Unnatural Mandarin or wrong words.
    - Biblical Facts: Book names, figures, places, or verse numbers (match CUV).
    - Fillers/Stammers: "这个这个", "呃", "嗯", "啊".
    - Sense: Non-sense words or incomplete sentences.

    Transcript:
    {text}

    Output JSON: {{"errors": ["- Error with suggestion", ...]}}
    """
    data = ask_llm(prompt, num_ctx=10240)
    errors = data.get('errors', [])
    return "\n".join(errors)


def refine_text(text: str, extra_context: str) -> str:
    """
    Refines Chinese transcript for biblical accuracy and punctuation.
    """
    print(f"✍️ Refining ZH text segment...")
    prompt = f"""
    Refine the Chinese sermon transcript.
    
    PRIMARY RULES:
    1. PRESERVE ORIGINAL WORDING & STYLE. Do NOT paraphrase.
    2. CORRECT biblical terms/names to CUV standard.
    3. Use the provided BIBLE VERSE REFERENCE as a baseline for accuracy.
    4. Fix punctuation and obvious ASR errors.
    5. Remove stammers and fillers (呃, 嗯, 那个).

    {extra_context}

    Original transcript:
    {text}

    Output JSON: {{"refined_text": "..."}}
    """
    data = ask_llm(prompt, num_ctx=10240)
    return data.get('refined_text', text)


if __name__ == '__main__':
    main()

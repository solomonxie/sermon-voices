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
from src.constants import OUTPUT_ROOT

ASR_MODEL = None


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

    prev_context = ""
    for chunk_path in chunk_paths:
        prev_context = process_chunk(chunk_path, prev_context=prev_context)

    # 3. Finalize: replace tmp with final and cleanup
    safe_replace(zh_tmp, final_zh)
    print(f"✅ Saved refined ZH transcript: {final_zh}")
    print(f"✅ Audio processing complete: {audio_path}")


def split_audio(audio_path: str) -> list[str]:
    """
    Splits original.mp3 into 30-second chunks with no overlap.
    Saves to a 'chunks/' subfolder as MP3 (16kHz, mono).
    """
    sermon_dir = os.path.dirname(audio_path)
    chunks_dir = os.path.join(sermon_dir, 'chunks')
    os.makedirs(chunks_dir, exist_ok=True)

    print(f"🎙️ Splitting audio: {audio_path}")
    audio = AudioSegment.from_file(audio_path)

    total_ms = len(audio)
    chunk_ms = 60 * 1000  # 1 minute
    overlap_ms = 5 * 1000 # 5 seconds overlap

    chunk_paths = []
    # Step through with precisely chunk_ms intervals
    for i, start_ms in enumerate(range(0, total_ms, chunk_ms)):
        end_ms = min(start_ms + chunk_ms, total_ms)
        chunk_name = f"chunk_{i:03d}.mp3"
        cp = os.path.join(chunks_dir, chunk_name)

        # Only export if doesn't exist to save time
        if not os.path.exists(cp):
            chunk = audio[start_ms:end_ms]
            # Qwen3-ASR works with 16kHz mono PCM
            chunk = chunk.set_frame_rate(16000).set_channels(1)
            chunk.export(cp, format="mp3", codec="libmp3lame")

        chunk_paths.append(cp)
        if end_ms >= total_ms: break

    return sorted(chunk_paths)

@retry(retries=3, delay=5.0)
def process_chunk(audio_path: str, prev_context: str = "") -> str:
    """
    Processes a single audio chunk: Transcribe -> Refine -> Append.
    Returns the refined ZH text to be used as context for the next chunk.
    """
    print(f"🎙️ Reading chunk: {os.path.basename(audio_path)}")
    sermon_dir = os.path.dirname(os.path.dirname(audio_path))
    orig_tmp = os.path.join(sermon_dir, 'transcript_original_tmp.txt')
    punc_tmp = os.path.join(sermon_dir, 'transcript_punc_tmp.txt')
    errors_tmp = os.path.join(sermon_dir, 'transcript_errors_tmp.txt')
    zh_tmp = os.path.join(sermon_dir, 'transcript_zh_tmp.txt')
    # Load custom instructions for this preacher
    preacher_dir = os.path.dirname(os.path.dirname(sermon_dir))
    transcript_instr = get_custom_instructions(preacher_dir, "transcript.md")
    # 1. Transcribe
    text = transcribe_audio(audio_path)
    if not text.strip(): return ""
    safe_write(orig_tmp, text)
    # 1.6 & 2. Iterative Refinement (until no more errors found or max loops reached)
    refined_zh = text
    ralph_wiggum_loops = 5
    for i in range(ralph_wiggum_loops):
        print(f"🔄 Ralph Wiggum correction loop {i+1}/{ralph_wiggum_loops}...")
        errors = pick_zh_errors(refined_zh)
        # Write latest errors to tmp for inspection
        safe_write(errors_tmp, f'Errors ({i=}):\n' + errors)
        if not errors.strip():
            print("✨ No more errors found.")
        extra_context = """
            --- START CUSTOM INSTRUCTIONS ---
            {custom_instructions}
            --- END CUSTOM INSTRUCTIONS ---
            --- START PREVIOUS CONTEXT ---
            {prev_context}
            --- END PREVIOUS CONTEXT ---
            --- START IDENTIFIED ERRORS ---
            {errors}
            --- END IDENTIFIED ERRORS ---
        """
        last_text = refined_zh
        refined_zh = refine_text(refined_zh, extra_context=extra_context)

        # Break if the LLM made negligible changes (99% similarity)
        similarity = string_similarity(refined_zh, last_text)
        if similarity >= 0.999:
            print(f"⏹️ Text stabilized ({similarity:.1%} similarity), finishing loop.")
            break
    safe_write(zh_tmp, refined_zh)
    return refined_zh


def transcribe_audio(audio_path: str) -> str:
    """
    Transcribes audio using SenseVoiceSmall with hotwords and memory safety.
    """
    # Load hotwords
    hotwords = ""
    hotwords_path = os.path.join(OUTPUT_ROOT, 'bible_hotwords_5000_zh.txt')
    if os.path.exists(hotwords_path):
        with open(hotwords_path, 'r', encoding='utf-8') as f:
            hotwords = " ".join([line.strip() for line in f if line.strip()])
    # FunASR AutoModel API with hotwords and ITN (Inverse Text Normalization)
    model = get_asr_model()
    results = model.generate(input=audio_path, hotword=hotwords, use_itn=True)
    if not results: return ""
    # Extract text from results and strip ASR event tags (e.g., <|zh|><|NEUTRAL|>)
    text = results[0].get('text', '').strip()
    text = re.sub(r'<\|.*?\|>', '', text)
    return text.strip()


def pick_zh_errors(text: str) -> str:
    """
    Identifies errors in the transcript (grammar, biblical facts, stammers).
    Returns a bulleted list of errors.
    """
    print(f"🔍 Picking errors from transcript...")
    prompt = f"""
    You are an expert editor for Chinese sermon transcripts.
    Analyze the following punctuated transcript text and identify ANY errors.

    ERROR CATEGORIES TO FIND:
    - Grammarly Errors (Mandarin): Incorrect grammar, unnatural phrasing, or wrong word choices.
    - Sentence Errors: Incomplete sentences, run-on sentences, or structural issues.
    - Biblical Fact Errors: Incorrect Bible book names, figure names, place names, or verse numbers.
    - Stammers and Fillers: Repetitive words from hesitations (e.g., "这这个这个", "还有还有", "呃", "嗯", "啊", "呢") that should be flagged.
    - Punctuation Errors: Missing or incorrect punctuation that affects meaning.
    - Biblical name errors: Madarin sermon is based off CUV Bible, so biblical name should match CUV Bible names.
    - Context: You need to check the whole paragraph for context to determine if there are errors.
    - Suggestion: You can also provide suggestion of fix of each error based on the context.

    Transcript to analyze:
    {text}

    Output MUST be a bulleted list of identified errors in JSON format: {{"errors": ["- Error 1", "- Error 2", ...]}}
    If no errors are found, return {{"errors": []}}.
    Do NOT include markdown, preamble, or explanations.
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
    You are refining a Chinese sermon transcript. Your PRIMARY goal is to PRESERVE the original speaker's exact words and speaking style.

    CRITICAL RULES - DO NOT VIOLATE:
    1. PRESERVE ORIGINAL WORDING: Do NOT rephrase, rewrite, or paraphrase unless there is an obvious transcription error
    2. KEEP REPETITIONS: Preachers intentionally repeat for emphasis - do NOT remove repetitions
    3. KEEP SPEAKER'S STYLE: Maintain informal language, colloquialisms, and the speaker's unique voice
    4. DO NOT SUMMARIZE: This is a transcript, not a summary - keep ALL content
    5. DO NOT ADD CONTENT: Do not add explanations, interpretations, or theological commentary

    WHAT YOU SHOULD FIX (ONLY):
    - Punctuation: Add periods, commas, question marks for readability
    - Biblical terms: Correct to Chinese Union Version standard (彼得, 保罗, 耶路撒冷, 使徒行传, etc.)
    - Obvious ASR errors: Fix characters that clearly dont make sense (e.g., 耶鲁撒冷 → 耶路撒冷)
    - Paragraph breaks: Separate into logical paragraphs for readability
    - Flow: Ensure smooth transition from previous context (do NOT repeat previous content)
    - Repeat: If the speaker stammers, repeat the word or phrase, remove it. e.g., "其他地方还还有没有难点" → "其他地方还有没有难点"; "这这个这个" → "这个"
    - Fillers: Remove all spoken fillers and hesitation markers. e.g., '呃', '嗯', '那个', '就是', '啊', '呢' as fillers.

    {extra_context}

    Original transcript (PRESERVE the speaker's exact words):
    {text}

    Output MUST be valid JSON: {{"refined_text": "..."}}
    Do NOT include markdown, preamble, or explanations.
    """
    data = ask_llm(prompt, num_ctx=10240)
    return data.get('refined_text', text)


def get_asr_model():
    if ASR_MODEL is not None:
        return ASR_MODEL
    from funasr import AutoModel
    device = "mps"  # 'mps' if torch.backends.mps.is_available() else "cpu"
    model = AutoModel(
        model="iic/SenseVoiceSmall",
        device=device,
        disable_update=True
    )
    return model


if __name__ == '__main__':
    main()

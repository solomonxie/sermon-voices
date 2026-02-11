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
from src.constants import OUTPUT_ROOT, BIBLE_HOTWORDS_PATH, CHRISTIAN_HOTWORDS_PATH


# Audio processing
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2: Audio Transcription & Refinement")
    parser.add_argument("audio_path", help="Path to the original.mp3 file to process")
    args = parser.parse_args()
    # Set ModelScope cache directory
    os.environ["MODELSCOPE_CACHE"] = os.path.expanduser('~/llm_models/modelscope')

    print(f"\n--- Phase 2: Audio Transcription & Refinement ---")
    process_sermon(args.audio_path)


def process_sermon(audio_path: str) -> None:
    sermon_dir = os.path.dirname(audio_path)
    final_zh = os.path.join(sermon_dir, 'transcript_zh.txt')

    # Checkpoint: Skip if already processed or audio missing
    if os.path.exists(final_zh) or not os.path.exists(audio_path):
        return

    print(f"\n⚙️ Processing: {audio_path}")

    # 2. Sequential processing
    orig_tmp = os.path.join(sermon_dir, 'transcript_original_tmp.txt')
    punc_tmp = os.path.join(sermon_dir, 'transcript_punc_tmp.txt')
    errors_tmp = os.path.join(sermon_dir, 'transcript_errors_tmp.txt')
    bible_tmp = os.path.join(sermon_dir, 'transcript_bible_tmp.txt')
    refined_tmp = os.path.join(sermon_dir, 'transcript_refined_tmp.txt')
    zh_tmp = os.path.join(sermon_dir, 'transcript_zh_tmp.txt')
    current_segment_mp3 = os.path.join(sermon_dir, 'current_segment_tmp.mp3')

    safe_remove(orig_tmp)
    safe_remove(punc_tmp)
    safe_remove(errors_tmp)
    safe_remove(bible_tmp)
    safe_remove(refined_tmp)
    safe_remove(zh_tmp)
    safe_remove(current_segment_mp3)

    # 1. Get audio segments
    segments = split_audio(audio_path)
    audio = AudioSegment.from_file(audio_path)

    # Accumulate segments into batches (approx. 1 minute chunks)
    current_batch = []
    current_batch_duration = 0
    chunk_limit_ms = 60000 # 1 minute chunks
    batches = []

    for start_ms, end_ms in segments:
        duration = end_ms - start_ms
        if current_batch_duration + duration > chunk_limit_ms and current_batch:
            batches.append(current_batch)
            current_batch = []
            current_batch_duration = 0

        current_batch.append((start_ms, end_ms))
        current_batch_duration += duration

    if current_batch:
        batches.append(current_batch)

    for i, batch in enumerate(batches):
        batch_start_ms = batch[0][0]
        batch_end_ms = batch[-1][1]

        start_time = time()
        print(f"\n📦 Processing batch {i+1}/{len(batches)} ({batch_start_ms/1000:.1f}s - {batch_end_ms/1000:.1f}s)")

        # Merge batch segments into one chunk
        chunk_audio = audio[batch_start_ms:batch_end_ms]
        chunk_audio = chunk_audio.set_frame_rate(16000).set_channels(1)
        chunk_audio.export(current_segment_mp3, format="mp3", codec="libmp3lame")

        process_segment(current_segment_mp3)

        elapsed = time() - start_time
        print(f"⏱️ Batch {i+1} processed in {elapsed:.1f}s")

    # 3. Finalize: replace tmp with final and cleanup
    safe_replace(zh_tmp, final_zh)
    print(f"✅ Saved refined ZH transcript: {final_zh}")
    print(f"✅ Audio processing complete: {audio_path}")


def split_audio(audio_path: str) -> list[tuple[int, int]]:
    print(f"🎙️ Splitting audio using VAD: {audio_path}")
    from funasr import AutoModel
    vad_model = AutoModel(
        model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        device="mps",  # if torch.backends.mps.is_available() else "cpu",
        disable_update=True
    )
    res = vad_model.generate(
        input=audio_path,
        max_end_silence_time=800,
        max_single_segment_time=60000,
    )
    return res[0]['value']  # [[start, end], ...] in ms


@retry(retries=3, delay=5.0)
def process_segment(audio_path: str) -> str:
    print(f"🎙️ Reading segment: {os.path.basename(audio_path)}")
    sermon_dir = os.path.dirname(audio_path)
    orig_tmp = os.path.join(sermon_dir, 'transcript_original_tmp.txt')
    punc_tmp = os.path.join(sermon_dir, 'transcript_punc_tmp.txt')
    errors_tmp = os.path.join(sermon_dir, 'transcript_errors_tmp.txt')
    bible_tmp = os.path.join(sermon_dir, 'transcript_bible_tmp.txt')
    refined_tmp = os.path.join(sermon_dir, 'transcript_refined_tmp.txt')
    zh_tmp = os.path.join(sermon_dir, 'transcript_zh_tmp.txt')

    preacher_dir = os.path.dirname(os.path.dirname(sermon_dir))
    transcript_instr = get_custom_instructions(preacher_dir, "transcript.md")

    # Load hotwords
    hotwords = []
    for path in [BIBLE_HOTWORDS_PATH]:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                hotwords.extend([line.strip() for line in f if line.strip()])
    hotwords_str = " ".join(hotwords)

    # 1. Transcribe
    text = transcribe_audio(audio_path, hotwords=hotwords_str)
    if not text.strip(): return ""
    safe_write(orig_tmp, text)

    # 1.1 Restore Punctuation
    text = enhance_punctuation(text)
    safe_write(punc_tmp, text)

    # 2. Bible Verse Lookup
    bible_context = lookup_bible_verses(text)
    safe_write(bible_tmp, bible_context)

    # 3. Iterative Refinement
    refined_zh = text
    ralph_wiggum_loops = 3
    for i in range(ralph_wiggum_loops):
        print(f"🔄 Ralph Wiggum correction loop {i+1}/{ralph_wiggum_loops}...")
        errors = pick_zh_errors(refined_zh)
        safe_write(errors_tmp, f'Errors (i={i}):\n' + errors)
        safe_write(refined_tmp, f'Refined Text (i={i}):\n{refined_zh}\n\n')

        if not errors.strip() and i > 0:
            print("✨ No more errors found.")
            break

        extra_context = f"""
            --- START CUSTOM INSTRUCTIONS ---
            {transcript_instr}
            --- END CUSTOM INSTRUCTIONS ---
            --- START BIBLE REFERENCE (CUV) ---
            {bible_context}
            --- END BIBLE REFERENCE (CUV) ---
            --- START IDENTIFIED ERRORS ---
            {errors}
            --- END IDENTIFIED ERRORS ---
        """
        last_text = refined_zh
        refined_zh = refine_text(refined_zh, extra_context=extra_context)

        score, reason = judge_refinement(refined_zh, last_text)
        print(f"⭐️ Stabilization Score: {score:.1%} | Reason: {reason}")
        if score >= 0.99:
            print(f"⏹️ Text stabilized ({score:.1%} similarity), finishing loop.")
            break

    safe_write(zh_tmp, refined_zh)
    return refined_zh


def lookup_bible_verses(text: str) -> str:
    print(f"📖 Looking up related Bible verses...")
    prompt = f"""
    从以下的讲道内容中，找出所有引用的圣经出处。
    格式:
    - [圣经书名] [章]:[节] - "[经文]"

    讲道内容:
    {text}

    输出必须是如下格式的JSON对象:
    {{
      "data": "[书名] [章]:[节] - [经文]; [书名] [章]:[节] - [经文];..."
    }}

    如果没有找到明确的经文，返回 {{"data": ""}}。
    不要包含markdown、前言或解释。
    """
    data = ask_llm(prompt, model='qwen3:4b-thinking-2507-q8_0')
    return str(data.get('data', ''))


def transcribe_audio(audio_path: str, hotwords: str = "") -> str:
    from funasr import AutoModel

    # Models are cached in ~/llm_models/modelscope
    print(f"🎙️ Transcribing: {os.path.basename(audio_path)} (hotwords: {len(hotwords)} chars)")

    # Initialize model (ModelScope cache is handled via environment variable in main)
    model = AutoModel(
        model="paraformer-zh",
        device="mps", # if torch.backends.mps.is_available() else "cpu",
        disable_update=True
    )

    try:
        # res = model.generate(input=audio_path, cache={}, language="auto", use_itn=True, hotwords=hotwords)
        res = model.generate(input=audio_path, batch_size_s=300, hotwords=hotwords)
        text = res[0].get('text', '').strip()
        # Clean up SenseVoice tags if present (e.g., <|zh|><|NEUTRAL|><|Speech|>)
        text = re.sub(r'<\|.*?\|>', '', text).strip()
        return text
    except Exception as e:
        raise RuntimeError(f"❌ Transcribe Error: {e}")


def enhance_punctuation(text: str) -> str:
    from funasr import AutoModel
    print(f"✍️ Restoring punctuation with CT-Punc...")
    model = AutoModel(model="ct-punc", device="mps", disable_update=True)
    try:
        res = model.generate(input=text)
        return res[0].get('text', text).strip()
    except Exception as e:
        print(f"❌ CT-Punc Error: {e}")
        return text


def pick_zh_errors(text: str) -> str:
    print(f"🔍 Picking errors from transcript...")
    prompt = f"""
    Analyze the Chinese sermon transcript and identify issues for transforming it into a polished article/paper.

    PRIMARY GOAL:
    Find ASR errors, logical inconsistencies, and flow problems that hinder reading clarity. **Respect the original punctuations unless they are clearly incorrect ASR artifacts.**

    ERROR CATEGORIES:
    - Fillers/Stammers: "这个这个", "呃", "嗯", "啊", "那个那个" (mark these for removal).
    - Logical Gaps: Phrasing that lacks context or seems disconnected from the surrounding text.
    - Punctuation/Paragraphing: Missing logical breaks or incorrect punctuation for a formal article.
    - Repetitions: Redundant phrases or stutters that should be streamlined.

    Transcript:
    {text}

    Output JSON: {{"data": "issue: suggestion;\nissue: suggestion; ..."}}
    """
    data = ask_llm(prompt, model='qwen3:4b-thinking-2507-q8_0')
    return str(data.get('data')) or str(data)


def refine_text(text: str, extra_context: str) -> str:
    print(f"✍️ Refining ZH text segment...")
    prompt = f"""
    Refine the Chinese sermon transcript.
    PRIMARY RULES:
    1. PRESERVE ORIGINAL WORDING & STYLE. Do NOT paraphrase.
    2. CORRECT biblical terms/names to Chinese Union Version (CUV).
    3. Use the provided Bible verse reference to correct biblical terms/names/sentences.
    4. Fix punctuation and obvious ASR errors, separate paragraphs based on context.
    5. Remove stammers and fillers (呃, 嗯, 那个).
    6. Do NOT add any additional content.

    {extra_context}

    Original transcript:
    {text}

    Output JSON: {{"data": "..."}}
    """
    data = ask_llm(prompt)
    return data.get('data', text)


def judge_refinement(text: str, last_text: str) -> tuple[float, str]:
    print(f"⚖️ Judging refinement stabilization...")
    prompt = f"""
    Compare the following two versions of a sermon transcript.
    Evaluate if the refinement has stabilized (i.e., no more significant corrections are needed).

    Previous Version:
    {last_text}

    Current Version:
    {text}

    A score of 1.0 means the text is identical or only has trivial punctuation changes.
    A score below 0.9 means significant meaningful changes were still made.

    Return a JSON object:
    {{
        "score": 0.0-1.0,
        "reason": "Brief explanation of why the score was given"
    }}
    """
    data = ask_llm(prompt)
    score = float(data.get('score') or 0.0)
    reason = data.get('reason') or data.get('data') or 'No reason provided'
    return score, reason


if __name__ == '__main__':
    main()

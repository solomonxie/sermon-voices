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

    # 1. Get audio segments
    segments = split_audio(audio_path)
    audio = AudioSegment.from_file(audio_path)

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

    for i, (start_ms, end_ms) in enumerate(segments):
        print(f"\n📦 Processing segment {i+1}/{len(segments)} ({start_ms/1000:.1f}s - {end_ms/1000:.1f}s)")
        # Export segment to tmp file
        segment_audio = audio[start_ms:end_ms]
        segment_audio = segment_audio.set_frame_rate(16000).set_channels(1)
        segment_audio.export(current_segment_mp3, format="mp3", codec="libmp3lame")
        
        process_segment(current_segment_mp3)

    # 3. Finalize: replace tmp with final and cleanup
    safe_replace(zh_tmp, final_zh)
    safe_remove(current_segment_mp3)
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
        max_end_silence_time=1000,
        max_single_segment_time=60000,
    )
    return res[0]['value']  # [[start, end], ...] in ms


@retry(retries=3, delay=5.0)
def process_segment(audio_path: str) -> str:
    print(f"🎙️ Reading segment: {os.path.basename(audio_path)}")
    sermon_dir = os.path.dirname(audio_path)
    orig_tmp = os.path.join(sermon_dir, 'transcript_original_tmp.txt')
    errors_tmp = os.path.join(sermon_dir, 'transcript_errors_tmp.txt')
    bible_tmp = os.path.join(sermon_dir, 'transcript_bible_tmp.txt')
    refined_tmp = os.path.join(sermon_dir, 'transcript_refined_tmp.txt')
    zh_tmp = os.path.join(sermon_dir, 'transcript_zh_tmp.txt')
    
    preacher_dir = os.path.dirname(os.path.dirname(sermon_dir))
    transcript_instr = get_custom_instructions(preacher_dir, "transcript.md")
    
    # 1. Transcribe
    text = transcribe_audio(audio_path)
    if not text.strip(): return ""
    safe_write(orig_tmp, text)
    
    # 2. Bible Verse Lookup
    bible_context = lookup_bible_verses(text)
    safe_write(bible_tmp, bible_context)
    
    # 3. Iterative Refinement
    refined_zh = text
    ralph_wiggum_loops = 5
    for i in range(ralph_wiggum_loops):
        print(f"🔄 Ralph Wiggum correction loop {i+1}/{ralph_wiggum_loops}...")
        errors = pick_zh_errors(refined_zh)
        safe_write(errors_tmp, f'Errors (i={i}):\n' + errors)
        safe_write(refined_tmp, f'Refined Text (i={i}):\n{refined_zh}\n\n')
        
        if not errors.strip():
            print("✨ No more errors found.")
            break
            
        extra_context = f"""
            --- START CUSTOM INSTRUCTIONS ---
            {transcript_instr}
            --- END CUSTOM INSTRUCTIONS ---
            --- START IDENTIFIED ERRORS ---
            {errors}
            --- END IDENTIFIED ERRORS ---
            --- START BIBLE VERSE REFERENCE (CUV) ---
            {bible_context}
            --- END BIBLE VERSE REFERENCE ---
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
    """
    Identifies related CUV Bible verses based on the transcription.
    """
    print(f"📖 Looking up related Bible verses...")
    prompt = f"""
    Based on the following sermon transcription segment, identify any related Bible verses (Chinese Union Version - CUV).
    For each sentence or idea, find the most likely verse it is referencing or quoting.
    
    Output the verses in the following format:
    - [Book Name (Chinese)] [Chapter]:[Verse Range] - "[Full Verse Text in Chinese Union Version - CUV]"
    
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
    # NOTE: Fun-ASR-Nano-2512 costs too much memory but has similar accuracy to SenseVoiceSmall
    # model = AutoModel(model="FunAudioLLM/Fun-ASR-Nano-2512", device="mps", disable_update=True)
    if ASR_MODEL is not None:
        model = ASR_MODEL
    else:
        model = AutoModel(model="iic/SenseVoiceSmall", device="mps", disable_update=True)
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
    2. CORRECT biblical terms/names to Chinese Union Version (CUV).
    3. Use the provided Bible verse reference to correct biblical terms/names/sentences.
    4. Fix punctuation and obvious ASR errors, separate paragraphs based on context.
    5. Remove stammers and fillers (呃, 嗯, 那个).
    6. Do NOT add any additional content.

    {extra_context}

    Original transcript:
    {text}

    Output JSON: {{"refined_text": "..."}}
    """
    data = ask_llm(prompt, num_ctx=10240)
    return data.get('refined_text', text)


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
    data = ask_llm(prompt, num_ctx=10240)
    return float(data.get('score', 0.0)), data.get('reason', 'No reason provided')


if __name__ == '__main__':
    main()

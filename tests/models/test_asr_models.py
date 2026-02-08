import pytest
import os
import json
import gc
import torch
from time import time
from qwen_asr import Qwen3ASRModel
from src.common import ask_llm

JUDGE_MODEL = 'qwen3'


# Pass these samples to tests using @pytest.mark.parametrize
SAMPLES = [
    {
        'path': './tests/models/sample01.mp3',
        'transcript': """[PLACEHOLDER: Please provide the ideal transcript for sample01.mp3 here]"""
    },
    {
        'path': './tests/models/sample02.mp3',
        'transcript': """[PLACEHOLDER: Please provide the ideal transcript for sample02.mp3 here]"""
    },
]

def judge_asr_accuracy(expected: str, actual: str) -> float:
    """
    Uses an LLM to judge the accuracy of the ASR output compared to the expected transcript.
    Returns a score between 0.0 and 1.0.
    """
    if not expected.strip() or "[PLACEHOLDER" in expected:
        print("⚠️ Skipping judgment: Ideal transcript placeholder not filled.")
        return 1.0  # Assume pass if no reference is provided yet
        
    prompt = f"""
    Judge the accuracy of the following ASR (Automatic Speech Recognition) output against the expected transcript.
    The ASR output might have minor punctuation differences or oral filler words, which should be tolerated. 
    However, missing theological terms, incorrect biblical names, or significant meaning changes should result in a lower score.

    Expected Transcript:
    {expected}

    ASR Output:
    {actual}

    Return a JSON object with a single key 'score' containing a value between 0.0 and 1.0, 
    where 1.0 is a perfect match (ignoring minor fluff) and 0.0 is completely wrong.
    Do not include any explanation.
    """
    res = ask_llm(prompt, model=JUDGE_MODEL)
    return float(res.get('score', 0.0))


@pytest.mark.parametrize("sample", SAMPLES)
def test_qwen3_asr(sample):
    global QWEN3_ASR_MODEL
    if QWEN3_ASR_MODEL is None:
        print(f"\n🚀 Loading Qwen3-ASR-1.7B...")
        huggingface_root = os.path.expanduser("~/llm_models/huggingface")
        os.environ["HF_HOME"] = huggingface_root
        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
        os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.7"
        os.environ["PYTORCH_MPS_LOW_WATERMARK_RATIO"] = "0.5"
        
        # Device and dtype optimization for Mac/MPS, CUDA, or CPU
        if torch.backends.mps.is_available():
            device_map = "mps"
            dtype = torch.float16
        elif torch.cuda.is_available():
            device_map = "auto"
            dtype = torch.bfloat16
        else:
            device_map = None
            dtype = torch.float32

        QWEN3_ASR_MODEL = Qwen3ASRModel.from_pretrained(
            "Qwen/Qwen3-ASR-1.7B",
            dtype=dtype,
            device_map=device_map,
            max_inference_batch_size=1,
            cache_dir=huggingface_root,
        )
        # Suppress "Setting `pad_token_id` to `eos_token_id`" warning
        if QWEN3_ASR_MODEL.model.config.pad_token_id is None:
            QWEN3_ASR_MODEL.model.config.pad_token_id = QWEN3_ASR_MODEL.model.config.eos_token_id

    model = QWEN3_ASR_MODEL
    audio_path = sample['path']
    expected = sample['transcript']

    if not os.path.exists(audio_path):
        pytest.skip(f"Audio not found: {audio_path}")

    print(f"🎙️ Transcribing: {audio_path}")
    results = model.transcribe(audio=audio_path)
    actual = " ".join([entry.text for entry in results]).strip()
    
    # Cleanup memory
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    gc.collect()

    print(f"📄 Result: {actual[:100]}...")

    score = judge_asr_accuracy(expected, actual)
    print(f"⭐️ Accuracy Score: {score:.2f}")
    assert score >= 0.8

@pytest.mark.parametrize("sample", SAMPLES)
def test_funasr_paraformer_zh(sample):
    from funasr import AutoModel
    print(f"\n🚀 Loading FunASR Paraformer-ZH...")
    funasr_root = os.path.expanduser("~/llm_models/funasr")
    os.environ["MODELSCOPE_CACHE"] = funasr_root

    start = time()
    model = AutoModel(
        model="iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        device="cuda" if torch.cuda.is_available() else "cpu",
        disable_update=True
    )
    print(f"✅ FunASR Model loaded in {time()-start:,.2f}s")

    audio_path = sample['path']
    expected = sample['transcript']
    
    if not os.path.exists(audio_path):
        pytest.skip(f"Audio not found: {audio_path}")

    print(f"🎙️ Transcribing with FunASR: {audio_path}")
    res = model.generate(input=audio_path)
    actual = res[0].get('text', '').strip()
    print(f"📄 Result: {actual[:100]}...")

    score = judge_asr_accuracy(expected, actual)
    print(f"⭐️ Accuracy Score: {score:.2f}")
    assert score >= 0.8


def test_funasr_punc_ct():
    pass
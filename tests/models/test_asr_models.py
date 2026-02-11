import pytest
import os
import json
from time import time
from src.common import ask_llm
from src.constants import FUNASR_MODEL_ROOT, FIREREDASR_MODEL_ROOT

JUDGE_MODEL = 'qwen2.5:7b'

# FunASR(Modelscope) model Root
os.environ["MODELSCOPE_CACHE"] = FUNASR_MODEL_ROOT

# Pass these samples to tests using @pytest.mark.parametrize
SAMPLES = [
    {
        'path': './tests/models/sample01.mp3',
        'transcript': """
            那么使徒是普世大公教会、有形教会的奠基人，就从圣经来看的话，这个使徒是普世有形大公教会的奠基人。
            那么他是有形教会的奠基人，那么根基是谁？
            根基是耶稣基督。
            那么奠基人就是使徒，他是有形教会的奠基人。
            在以夫所书的2章20节，里面是这么说的，说你们，当然这就是你们圣徒了。
            那么圣徒被建立在使徒和先知的根基上，由耶稣基督亲自为房角石，全房靠他联络得合适，渐渐成为主的圣殿。
            也就是说教会是建立在基督这块房角石上，那么是由使徒和先知打下的根基。
            那么先知打下的是旧约的根基。 那么新约的根基由谁打下来，就由这就由使徒来打下来。
        """
    },
    {
        'path': './tests/models/sample02.mp3',
        'transcript': """
            先低头闭目，我们来做一个祷告:
            慈爱得天父、爱我们的主耶稣基督，我们感谢你、我们赞美你。
            感谢主你真正是在荒野的当中开道路的神。
            感谢主我们能够由这一场查经，完全是出于主的恩典。
            我们没有奢望太多，当我们大家都有这样感动得时候，这件事就这么成了。
            主你为我们预备的场所、为我们预备的时间。（我们）特别地感恩。
            我们要把以下的时间，恭恭敬敬地交在主你的手中，恳求主你使用我们。
            恳求主你让我们在这次的、以后每周二的查经当中，让我们能够真正是收获不下于每周五的查经收获。
            恳求主也是保守我们每一个人，让我们每一个人能够在圣经当中学到生命的力量。
            求主与我们同在，听我们的祷告，奉我主耶稣基督的名。
            阿门。
        """
    },
    # {
    #     'path': './tests/models/sample03.mp3',
    #     'transcript': """[PLACEHOLDER: Please provide the ideal transcript for sample02.mp3 here]"""
    # },
]

def judge_asr_accuracy(expected: str, actual: str) -> tuple[float, str]:
    """
    Uses an LLM to judge the accuracy of the ASR output compared to the expected transcript.
    Returns a tuple of (score, reason) where score is between 0.0 and 1.0.
    """
    if not expected.strip() or "[PLACEHOLDER" in expected:
        print("⚠️ Skipping judgment: Ideal transcript placeholder not filled.")
        return 1.0, "Skipped: no reference transcript"
    prompt = f"""
    Judge the accuracy of the following ASR (Automatic Speech Recognition) output against the expected transcript.
    The ASR output might have minor punctuation differences or oral filler words, which should be tolerated.
    However, missing theological terms, incorrect biblical names, or significant meaning changes should result in a lower score.

    Expected Transcript:
    {expected}

    ASR Output:
    {actual}

    Return a JSON object with two keys:
    - 'score': a value between 0.0 and 1.0, where 1.0 is a perfect match (ignoring minor fluff) and 0.0 is completely wrong.
    - 'reason': a brief explanation of the score, highlighting key differences if any.
    """
    res = ask_llm(prompt, model=JUDGE_MODEL)
    return float(res.get('score', 0.0)), res.get('reason', 'No reason provided')


@pytest.mark.parametrize("sample", SAMPLES)
def test_qwen3_asr(sample):
    from qwen_asr import Qwen3ASRModel
    print(f"\n🚀 Loading Qwen3-ASR-1.7B...")
    huggingface_root = os.path.expanduser("~/llm_models/huggingface")
    os.environ["HF_HOME"] = huggingface_root
    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

    # Device and dtype optimization for Mac/MPS, CUDA, or CPU
    QWEN3_ASR_MODEL = Qwen3ASRModel.from_pretrained(
        "Qwen/Qwen3-ASR-1.7B",
        dtype="mp3",
        max_inference_batch_size=1,
        cache_dir=huggingface_root,
    )
    # Suppress "Setting `pad_token_id` to `eos_token_id`" warning
    if QWEN3_ASR_MODEL.model.config.pad_token_id is None:
        QWEN3_ASR_MODEL.model.config.pad_token_id = QWEN3_ASR_MODEL.model.config.eos_token_id
    audio_path = sample['path']
    expected = sample['transcript']
    if not os.path.exists(audio_path):
        pytest.skip(f"Audio not found: {audio_path}")
    print(f"🎙️ Transcribing: {audio_path}")
    results = QWEN3_ASR_MODEL.transcribe(audio=audio_path)
    actual = " ".join([entry.text for entry in results]).strip()
    print(f"📄 Result: {actual[:100]}...")
    score, reason = judge_asr_accuracy(expected, actual)
    print(f"⭐️ Accuracy Score: {score:.2f}")
    print(f"📝 Reason: {reason}")
    print(f"📊 Expected: {expected.strip()[:200]}")
    print(f"📊 Actual:   {actual[:200]}")
    assert score >= 0.8, f"Score {score:.2f} < 0.8 | Reason: {reason}"

@pytest.mark.parametrize("sample", SAMPLES)
def test_funasr_paraformer_zh(sample):
    from funasr import AutoModel
    print(f"\n🚀 Loading FunASR Paraformer-ZH...")
    start = time()
    model = AutoModel(
        model="iic/speech_paraformer-large-vad-punc_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        device="mps",
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

    score, reason = judge_asr_accuracy(expected, actual)
    print(f"⭐️ Accuracy Score: {score:.2f}")
    print(f"📝 Reason: {reason}")
    print(f"📊 Expected: {expected.strip()[:200]}")
    print(f"📊 Actual:   {actual[:200]}")
    assert score >= 0.8, f"Score {score:.2f} < 0.8 | Reason: {reason}"


# @pytest.mark.parametrize("sample", SAMPLES)
# def test_funasr_nano(sample):
#     """
#     NOTE: Fun-ASR-Nano-2512 costs too much memory but has similar accuracy to iic/SenseVoiceSmall.
#     This test is kept for comparison purposes, but SenseVoiceSmall is preferred for production use.
    
#     Need to fix lib: venv/lib/python3.11/site-packages/funasr/models/fun_asr_nano/model.py
#     -from ctc import CTC
#     -from tools.utils import forced_align
#     +from .ctc import CTC
#     +from .tools.utils import forced_align
#     """
#     from funasr import AutoModel
#     print(f"\n🚀 Loading FunASR Nano-2512...")

#     start = time()
#     model = AutoModel(model="FunAudioLLM/Fun-ASR-Nano-2512", device="mps", disable_update=False)
#     print(f"✅ FunASR Nano Loaded in {time()-start:,.2f}s")

#     audio_path = sample['path']
#     expected = sample['transcript']
    
#     if not os.path.exists(audio_path):
#         pytest.skip(f"Audio not found: {audio_path}")

#     print(f"🎙️ Transcribing with FunASR Nano: {audio_path}")
#     res = model.generate(input=audio_path)
#     actual = res[0].get('text', '').strip()
#     print(f"📄 Result: {actual[:100]}...")

#     score = judge_asr_accuracy(expected, actual)
#     print(f"⭐️ Accuracy Score: {score:.2f}")
#     assert score >= 0.8


@pytest.mark.parametrize("sample", SAMPLES)
def test_sensevoice_small(sample):
    from funasr import AutoModel
    print(f"\n🚀 Loading SenseVoiceSmall...")
    start = time()
    model = AutoModel(
        model="iic/SenseVoiceSmall",
        device="mps",
        disable_update=True
    )
    print(f"✅ SenseVoiceSmall Model loaded in {time()-start:,.2f}s")

    audio_path = sample['path']
    expected = sample['transcript']

    if not os.path.exists(audio_path):
        pytest.skip(f"Audio not found: {audio_path}")

    print(f"🎙️ Transcribing with SenseVoiceSmall: {audio_path}")
    res = model.generate(input=audio_path)
    actual = res[0].get('text', '').strip()
    print(f"📄 Result: {actual[:100]}...")

    score, reason = judge_asr_accuracy(expected, actual)
    print(f"⭐️ Accuracy Score: {score:.2f}")
    print(f"📝 Reason: {reason}")
    print(f"📊 Expected: {expected.strip()[:200]}")
    print(f"📊 Actual:   {actual[:200]}")
    assert score >= 0.8, f"Score {score:.2f} < 0.8 | Reason: {reason}"


def test_funasr_punc_ct():
    pass


@pytest.mark.parametrize("sample", SAMPLES)
def test_firered_asr(sample):
    from fireredasr.models.fireredasr import FireRedAsr

    model_dir = os.path.join(FIREREDASR_MODEL_ROOT, "FireRedASR-LLM-L")
    if not os.path.exists(model_dir):
        pytest.skip(f"Model not found: {model_dir}")

    print(f"\n🚀 Loading FireRedASR-LLM-L...")
    model = FireRedAsr.from_pretrained("llm", model_dir)

    audio_path = sample['path']
    expected = sample['transcript']

    if not os.path.exists(audio_path):
        pytest.skip(f"Audio not found: {audio_path}")

    # FireRedASR expectations: batch_uttid, batch_wav_path, params
    batch_uttid = ["chunk"]
    batch_wav_path = [audio_path]
    print(f"🎙️ Transcribing with FireRedASR: {audio_path}")
    results = model.transcribe(
        batch_uttid,
        batch_wav_path,
        {
            "use_gpu": 1,
            "beam_size": 3,
            "decode_max_len": 0,
            "decode_min_len": 0,
            "repetition_penalty": 3.0,
            "llm_length_penalty": 1.0,
            "temperature": 1.0
        }
    )
    actual = results[0].strip()

    # Cleanup memory
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    gc.collect()

    print(f"📄 Result: {actual[:100]}...")

    score, reason = judge_asr_accuracy(expected, actual)
    print(f"⭐️ Accuracy Score: {score:.2f}")
    print(f"📝 Reason: {reason}")
    print(f"📊 Expected: {expected.strip()[:200]}")
    print(f"📊 Actual:   {actual[:200]}")
    assert score >= 0.8, f"Score {score:.2f} < 0.8 | Reason: {reason}"

"""
- Goal: test different ASR models and use LLM to judge the accuracy (softly) with "matching-score".
- It will not call functions from other modules but directly call official libs to make the call
"""
import pytest

JUDGET_MODEL = 'qwen3'

# Pass these samples to tests using using @pytest.mark.parametrize
SAMPLES = [
    {
        'path': './tests/models/sample01.mp3',
        'transcript': """
        """
    },
    SAMPLE_2 = {
        'path': './tests/models/sample02.mp3',
        'transcript': """
        """
    },
]


def test_qwen3_asr():
    # from ... import ...
    score = 0
    assert score > 0.9


def test_funasr_paraformer_zh():
    # from ... import ...
    score = 0
    assert score > 0.9


def test_firedasr():
    # from ... import ...
    score = 0
    assert score > 0.9


def test_sensevoice_1_5_B():
    # from ... import ...
    score = 0
    assert score > 0.9


def test_tencen_16kzh():
    # from ... import ...
    score = 0
    assert score > 0.9


def test_whisper_large_v3():
    """ Known issue: madarin content was poisioned with `请不吝点赞 订阅 转发 打赏支持明镜与点栏目`}
`"""
    # from ... import ...
    score = 0
    assert score > 0.9


# def test_qwen3_asr():
#     from funasr import AutoModel
#     print(f"🚀 Loading Qwen3-ASR-1.7B...")
#     funasr_root = os.path.expanduser("~/llm_models/funasr")
#     os.environ["MODELSCOPE_CACHE"] = funasr_root

#     start = time()
#     try:
#         model = AutoModel(
#             model="iic/Qwen3-ASR-1.7B",
#             device="cuda" if torch.cuda.is_available() else "cpu",
#             disable_update=True
#         )
#         print(f"✅ ASR Model loaded in {time()-start:,.2f}s")
        
#         # Test with a very small chunk if available
#         test_audio = "output/hua-xian/acts/001_do-not-leave-jerusalem/chunks/chunk_000.mp3"
#         if os.path.exists(test_audio):
#             print(f"🎙️ Transcribing test audio: {test_audio}")
#             res = model.generate(input=test_audio)
#             print(f"📄 Result: {res[0].get('text', '')}")
#         else:
#             print(f"⚠️ Test audio not found at {test_audio}")
            
#     except Exception as e:
#         print(f"❌ Error: {str(e)}")

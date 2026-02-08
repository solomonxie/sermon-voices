"""
- Goal: test different ASR models and use LLM to judge the accuracy (softly) with "matching-score".
- It will not call functions from other modules but directly call official libs to make the call
"""
import pytest

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
    score = 0
    assert score > 0.9


def test_funasr_paraformer_zh():
    score = 0
    assert score > 0.9


def test_firedasr():
    score = 0
    assert score > 0.9


def test_sensevoice_1_5_B():
    score = 0
    assert score > 0.9


def test_tencen_16kzh():
    score = 0
    assert score > 0.9


def test_whisper_large_v3():
    """ Known issue: madarin content was poisioned with `请不吝点赞 订阅 转发 打赏支持明镜与点栏目`}
`"""
    score = 0
    assert score > 0.9

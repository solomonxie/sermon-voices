import pytest
from src.process_audio import lookup_bible_verses

def test_lookup_bible_verses_accuracy():
    from src.common import string_similarity
    transcript = """
        不要离开耶古撒冷，要等候负所应急的，就是你们听见我说过的约翰是用水施洗，但不多几日，你们要受圣名的洗忆。好，我们读了这段经文，感觉难点有没有这块有没有难点。
    """
    result = lookup_bible_verses(transcript)
    expected_text = """
        使徒行传 1:4-5 耶稣和他们聚集的时候，嘱咐他们说：不要离开耶路撒冷，要等候父所应许的，就是你们听见我说过的。约翰是用水施洗，但不多几日，你们要受圣灵的洗。
    """
    similarity = string_similarity(result, expected_text)
    assert similarity >= 0.99, f"Similarity: {similarity}, Result: {result}, Expected: {expected_text}"

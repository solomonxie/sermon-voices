import pytest
from src.process_audio import lookup_bible_verses

def test_lookup_bible_verses_accuracy():
    from src.common import string_similarity
    transcript = """
        不要离开耶古撒冷，要等候负所应急的，就是你们听见我说过的约翰是用水施洗，但不多几日，你们要受圣名的洗忆。好，我们读了这段经文，感觉难点有没有这块有没有难点。
    """
    result = lookup_bible_verses(transcript)
    # Check if the correct verse from Acts (使徒行传) is found
    # (Note: Pinyin match might return multiple, so we check for the presence of the key verse)
    assert "使徒行传" in result or "耶路撒冷" in result, f"Result did not contain expected context: {result}"

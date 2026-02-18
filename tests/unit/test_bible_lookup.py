import pytest
from src.process_audio import get_bible_verses_by_ref

def test_get_bible_verses_by_ref_single_verse():
    """
    Tests get_bible_verses_by_ref with a specific single verse reference.
    """
    scripture_ref = "John ch3:v16"
    result = get_bible_verses_by_ref(scripture_ref=scripture_ref)
    expected = '约翰福音 3:16 - "「神愛世人，甚至將他的獨生子賜給他們，叫一切信他的，不至滅亡，反得永生。"'
    assert expected in result

def test_get_bible_verses_by_ref_chapter():
    """
    Tests get_bible_verses_by_ref with a chapter reference.
    """
    scripture_ref = "Jude ch1"
    result = get_bible_verses_by_ref(scripture_ref=scripture_ref)
    # Jude only has one chapter, so it should return all verses.
    # I will just check for a few verses.
    assert "犹大书 1:1" in result
    assert "犹大书 1:25" in result

def test_get_bible_verses_by_ref_no_ref():
    """
    Tests get_bible_verses_by_ref with no scripture reference.
    """
    result = get_bible_verses_by_ref(scripture_ref=None)
    assert result == ""

def test_get_bible_verses_by_ref_invalid_ref():
    """
    Tests get_bible_verses_by_ref with an invalid scripture reference.
    """
    scripture_ref = "Invalid Reference"
    result = get_bible_verses_by_ref(scripture_ref=scripture_ref)
    assert result == ""

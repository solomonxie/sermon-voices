import pytest
from src.process_audio import bible_lookup_hybrid

def test_bible_lookup_with_scripture_ref():
    """
    Tests the bible_lookup_hybrid function with a specific scripture reference
    to ensure it correctly filters the search.
    """
    text = "神爱世人，甚至将他的独生子赐给他们"
    scripture_ref = "John ch3:v16"
    
    # This requires the bible rag db to be generated.
    # The test will fail if it's not present.
    result = bible_lookup_hybrid(text, scripture_ref=scripture_ref)
    
    # We expect to see John 3:16 in the results.
    assert "约翰福音 3:16" in result
    
    # We don't expect to see many other verses.
    # This is a bit brittle, but for a first pass it's ok.
    # With a specific reference, the result should be very precise.
    result_list = [r for r in result.split(';') if r.strip()]
    assert len(result_list) <= 2

def test_bible_lookup_without_scripture_ref():
    """
    Tests the bible_lookup_hybrid function without a scripture reference
    to ensure it still returns relevant results from the whole Bible.
    """
    text = "神爱世人，甚至将他的独生子赐给他们"
    
    result = bible_lookup_hybrid(text)
    
    assert "约翰福音 3:16" in result

def test_bible_lookup_chapter_only_ref():
    """
    Tests the bible_lookup_hybrid function with a chapter-only scripture reference.
    """
    text = "爱是恒久忍耐，又有恩慈"
    scripture_ref = "1 Corinthians ch13"
    
    result = bible_lookup_hybrid(text, scripture_ref=scripture_ref)
    
    assert "哥林多前书 13:4" in result
    
    # Check if other verses from the same chapter are also found
    assert "哥林多前书 13:" in result
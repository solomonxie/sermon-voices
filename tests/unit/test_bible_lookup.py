import pytest
from src.process_audio import lookup_bible_verses

def test_lookup_bible_verses(monkeypatch):
    # Mock ask_llm to avoid actual API calls during unit test
    def mock_ask_llm(*args, **kwargs):
        return {
            "verses": ["John 3:16 - 神愛世人，甚至將祂的獨生子賜给他们，叫一切信祂的，不致灭亡，反得永生。"]
        }
    
    monkeypatch.setattr("src.process_audio.ask_llm", mock_ask_llm)
    
    transcript = "我们要讲到神爱世人，甚至将他的独生子赐给他们。"
    result = lookup_bible_verses(transcript)
    
    assert "John 3:16" in result
    assert "神愛世人" in result

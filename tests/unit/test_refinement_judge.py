import pytest
from unittest.mock import patch, MagicMock
from src.process_audio import judge_refinement

@patch('src.process_audio.ask_llm')
def test_judge_refinement_stabilized(mock_ask_llm):
    # Mock LLM response for stabilization (identical text)
    mock_ask_llm.return_value = {
        "score": 1.0,
        "reason": "The text is identical."
    }
    
    text = "耶和华是我的牧者"
    last_text = "耶和华是我的牧者"
    
    score, reason = judge_refinement(text, last_text)
    
    assert score == 1.0
    assert reason == "The text is identical."
    mock_ask_llm.assert_called_once()

@patch('src.process_audio.ask_llm')
def test_judge_refinement_not_stabilized(mock_ask_llm):
    # Mock LLM response for not stabilized (meaningful change)
    mock_ask_llm.return_value = {
        "score": 0.5,
        "reason": "Major corrections made to biblical terms."
    }
    
    text = "耶和华是我的牧者"
    last_text = "上帝是我的牧者" # 'God' vs 'Jehovah'
    
    score, reason = judge_refinement(text, last_text)
    
    assert score == 0.5
    assert reason == "Major corrections made to biblical terms."

@patch('src.process_audio.ask_llm')
def test_judge_refinement_invalid_response(mock_ask_llm):
    # Mock LLM response with missing fields
    mock_ask_llm.return_value = {}
    
    score, reason = judge_refinement("a", "b")
    
    assert score == 0.0
    assert reason == "No reason provided"

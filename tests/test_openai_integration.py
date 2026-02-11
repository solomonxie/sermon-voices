import os
import pytest
from unittest.mock import MagicMock, patch
from src.common import ask_llm, load_dotenv

@patch("src.process_audio.OPENAI_CLIENT")
def test_transcribe_audio(mock_client):
    # Mock response
    mock_response = MagicMock()
    mock_client.audio.transcriptions.create.return_value = "This is a test transcript."
    
    from src.process_audio import transcribe_audio
    result = transcribe_audio("dummy.mp3")
    assert result == "This is a test transcript."
    mock_client.audio.transcriptions.create.assert_called_once()
def test_ask_llm_json(mock_client):
    # Mock response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='{"result": "success"}'))]
    mock_client.chat.completions.create.return_value = mock_response
    
    result = ask_llm("test prompt")
    assert result == {"result": "success"}
    mock_client.chat.completions.create.assert_called_once()

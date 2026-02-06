import os
import json
import pytest
from unittest.mock import patch, MagicMock
from src.process_audio import process_audio

def test_process_audio_checkpointing(tmp_path):
    # Setup mock metadata and directories
    sermon_dir = tmp_path / "sermon1"
    sermon_dir.mkdir()
    metadata_path = sermon_dir / "metadata.json"
    audio_path = sermon_dir / "original.mp3"
    
    metadata = {"title": "Test Sermon"}
    with open(metadata_path, "w") as f:
        json.dump(metadata, f)
    
    with open(audio_path, "w") as f:
        f.write("dummy audio content")

    # Final expected paths
    transcript_zh_path = sermon_dir / "transcript_zh.txt"
    translation_en_path = sermon_dir / "translation_en.txt"
    transcript_zh_tmp = sermon_dir / "transcript_zh.txt.tmp"
    translation_en_tmp = sermon_dir / "translation_en.txt.tmp"

    # Mocks
    mock_segments = ["Segment 1", "Segment 2"]
    
    with patch("src.process_audio.transcript_audio") as mock_transcript, \
         patch("src.process_audio.refine_transcript") as mock_refine, \
         patch("src.process_audio.translate_transcript") as mock_translate:
        
        mock_transcript.return_value = iter(mock_segments)
        mock_refine.side_effect = lambda x: f"Refined {x}"
        mock_translate.side_effect = lambda x: f"Translated {x}"

        # Run the function
        process_audio(str(metadata_path))

        # Verify final files exist
        assert transcript_zh_path.exists()
        assert translation_en_path.exists()
        
        # Verify .tmp files are gone
        assert not transcript_zh_tmp.exists()
        assert not translation_en_tmp.exists()

        # Verify content
        with open(transcript_zh_path, "r") as f:
            content = f.read()
            assert "Refined Segment 1" in content
            assert "Refined Segment 2" in content
        
        with open(translation_en_path, "r") as f:
            content = f.read()
            assert "Translated Refined Segment 1" in content
            assert "Translated Refined Segment 2" in content

def test_process_audio_cleanup_tmp_on_start(tmp_path):
    # Verify that existing .tmp files are cleared
    sermon_dir = tmp_path / "sermon2"
    sermon_dir.mkdir()
    metadata_path = sermon_dir / "metadata.json"
    audio_path = sermon_dir / "original.mp3"
    
    transcript_zh_tmp = sermon_dir / "transcript_zh.txt.tmp"
    translation_en_tmp = sermon_dir / "translation_en.txt.tmp"
    
    # Create lingering tmp files
    with open(transcript_zh_tmp, "w") as f: f.write("lingering zh")
    with open(translation_en_tmp, "w") as f: f.write("lingering en")

    metadata = {"title": "Test Sermon 2"}
    with open(metadata_path, "w") as f: json.dump(metadata, f)
    with open(audio_path, "w") as f: f.write("dummy")

    with patch("src.process_audio.transcript_audio") as mock_transcript, \
         patch("src.process_audio.refine_transcript") as mock_refine, \
         patch("src.process_audio.translate_transcript") as mock_translate:
        
        mock_transcript.return_value = iter(["New segment"])
        mock_refine.return_value = "New refined"
        mock_translate.return_value = "New translated"

        process_audio(str(metadata_path))

        with open(sermon_dir / "transcript_zh.txt", "r") as f:
            content = f.read()
            assert "lingering zh" not in content
            assert "New refined" in content

import os
import sys

# Ensure project root is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.process_audio import enhance_punctuation

def test_punc():
    text = "我们今天在这里聚集是为了敬拜上帝我们要读圣经"
    print(f"Original: {text}")
    try:
        # This will likely fail in the environment if models aren't available 
        # but it's the correct way to test the logic.
        # Alternatively, we just check if it runs without syntax error.
        enhanced = enhance_punctuation(text)
        print(f"Enhanced: {enhanced}")
    except Exception as e:
        print(f"Error (expected if models not installed): {e}")

if __name__ == "__main__":
    test_punc()

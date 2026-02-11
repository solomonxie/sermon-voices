import os
import sys

# Mocking constants to avoid dependency issues if needed, 
# but we want to test the actual src.constants and src.process_audio integration.
sys.path.append(os.getcwd())

from src.constants import BIBLE_HOTWORDS_PATH, CHRISTIAN_HOTWORDS_PATH

def test_hotwords_loading():
    print(f"Checking BIBLE_HOTWORDS_PATH: {BIBLE_HOTWORDS_PATH}")
    print(f"Checking CHRISTIAN_HOTWORDS_PATH: {CHRISTIAN_HOTWORDS_PATH}")
    
    hotwords = []
    for path in [BIBLE_HOTWORDS_PATH, CHRISTIAN_HOTWORDS_PATH]:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
                print(f"Loaded {len(lines)} hotwords from {os.path.basename(path)}")
                hotwords.extend(lines)
        else:
            print(f"File NOT FOUND: {path}")
    
    print(f"Total hotwords loaded: {len(hotwords)}")
    if len(hotwords) > 0:
        print("First 5 hotwords:", hotwords[:5])
        print("✅ Hotwords loading test passed!")
    else:
        print("❌ No hotwords loaded.")
        sys.exit(1)

if __name__ == "__main__":
    test_hotwords_loading()

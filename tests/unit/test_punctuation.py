import sys
import os

# Ensure src is in the path
sys.path.append(os.getcwd())

from src.process_audio import enhance_punctuation

def test_restore_punctuation():
    test_text = "这是一段没有标点符号的中文文本我们要看看它是否能被正确地加上标点"
    print(f"Input: {test_text}")
    punctuated_text = enhance_punctuation(test_text)
    print(f"Output: {punctuated_text}")
    
    # Basic check: should contain some punctuation
    punctuation_marks = ["，", "。", "！", "？", "、", "；", "："]
    has_punctuation = any(mark in punctuated_text for mark in punctuation_marks)
    
    if has_punctuation:
        print("✅ Punctuation restoration successful.")
    else:
        print("❌ Punctuation restoration failed (no punctuation marks found).")

if __name__ == "__main__":
    test_restore_punctuation()

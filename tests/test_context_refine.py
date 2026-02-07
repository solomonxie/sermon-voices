import os
import sys

# Add src to path
sys.path.append(os.getcwd())

from src.process_audio import refine_text

def test_context_awareness():
    text1 = "弟兄姐妹平安，今天我们要讲的是使徒行传。使徒这两个字的意思就是被差遣的人。"
    refined1 = refine_text(text1)
    print(f"Refined 1: {refined1}")
    
    text2 = "被差遣的人，就是使徒。那使徒在大公教会中是奠基人。"
    refined2 = refine_text(text2, prev_context=refined1)
    print(f"Refined 2: {refined2}")
    
    # Check if Refined 2 repeats the first sentence of text 2 which is overlapping in meaning with Refined 1
    if "被差遣的人" in refined2 and "被差遣的人" in refined1:
         print("Warning: Potential repetition detected, but let's see if LLM handled it.")
    else:
         print("Success: LLM likely removed the overlapping meaning.")

if __name__ == "__main__":
    try:
        test_context_awareness()
    except Exception as e:
        print(f"Test failed: {e}")

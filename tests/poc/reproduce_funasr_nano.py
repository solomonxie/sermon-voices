
import os
import sys
from funasr import AutoModel

try:
    print("Trying to load FunAudioLLM/Fun-ASR-Nano-2512 with funasr...")
    model = AutoModel(model="FunAudioLLM/Fun-ASR-Nano-2512", disable_update=True)
    print("Success!")
except Exception as e:
    print(f"Failed: {e}")

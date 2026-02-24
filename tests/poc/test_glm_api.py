
import os
import sys
import torch
import librosa
from transformers import AutoModelForSeq2SeqLM, AutoProcessor

model_id = "zai-org/GLM-ASR-Nano-2512"
print(f"Loading {model_id}...")

processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
model = AutoModelForSeq2SeqLM.from_pretrained(model_id, trust_remote_code=True)

# Try with file path directly to processor, which didn't work before, or try apply_chat_template?
audio_file = "output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original_cleaned.wav"

try:
    if not os.path.exists(audio_file):
        print(f"File {audio_file} missing. Using dummy array.")
        import numpy as np
        audio_array = np.zeros(16000, dtype=np.float32)
        sr = 16000
    else:
        audio_array, sr = librosa.load(audio_file, sr=16000, duration=5.0)

    print("Methods on processor:")
    for attr in dir(processor):
        if not attr.startswith("_"):
             print(attr)

    if hasattr(processor, "apply_transcription_request"):
        print("Using apply_transcription_request")
        inputs = processor.apply_transcription_request(audio_array)
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=128)
        print(processor.batch_decode(outputs, skip_special_tokens=True)[0])
    elif hasattr(processor, "__call__"):
        print("Using standard __call__ with audios=...")
        # ASR processors usually take audio= or audios=
        inputs = processor(audio=audio_array, sampling_rate=16000, return_tensors="pt")
        with torch.no_grad():
            outputs = model.generate(**inputs, max_new_tokens=128)
        print(processor.batch_decode(outputs, skip_special_tokens=True)[0])
        
except Exception as e:
    import traceback
    traceback.print_exc()


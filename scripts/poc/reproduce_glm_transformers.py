
import torch
import soundfile as sf
import librosa
from transformers import AutoModelForSeq2SeqLM, AutoProcessor

print("Attempting to load zai-org/GLM-ASR-Nano-2512 with transformers...")

# It looks like the model architecture might not be AutoModelForSeq2SeqLM, let's try
# to use AutoModel first if Seq2Seq fails or just standard AutoModelForSpeechSeq2Seq
try:
    processor = AutoProcessor.from_pretrained("zai-org/GLM-ASR-Nano-2512", trust_remote_code=True)
    model = AutoModelForSeq2SeqLM.from_pretrained("zai-org/GLM-ASR-Nano-2512", trust_remote_code=True)
    print("Loaded model successfully!")
    
    # We need a dummy audio array
    import numpy as np
    audio_array = np.zeros(16000, dtype=np.float32) # 1 sec silent audio at 16kHz
    
    # Or, following the example from google search:
    # processor.apply_transcription_request might be specific to this processor.
    # Let's check what methods the processor has.
    inputs = processor(audio_array, sampling_rate=16000, return_tensors="pt")
    
    with torch.no_grad():
        outputs = model.generate(**inputs, max_new_tokens=128)
        
    transcription = processor.batch_decode(outputs, skip_special_tokens=True)[0]
    print(f"Transcription: {transcription}")
except Exception as e:
    print(f"Failed with standard transformers API: {e}")


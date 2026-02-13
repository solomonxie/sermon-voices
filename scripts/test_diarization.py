
import os
import torch
from funasr import AutoModel
from pydub import AudioSegment
import tempfile

# Set environment variables
os.environ["MODELSCOPE_CACHE"] = os.path.expanduser('~/llm_models/modelscope')

def test_diarization(audio_path):
    print(f"Loading diarization model...")
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = AutoModel(
        model="iic/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        vad_model="iic/speech_fsmn_vad_zh-cn_16k_common",
        punc_model="iic/punc_ct-transformer_zh-cn-common",
        spk_model="iic/speech_campplus_sv_zh-cn_16k-common",
        device=device,
        disable_update=True
    )
    
    # Load first 30 seconds for quick test
    audio = AudioSegment.from_file(audio_path)
    sample_ms = 30 * 1000 
    sample_audio = audio[:sample_ms]
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        sample_audio.export(tf.name, format="wav")
        tmp_path = tf.name
        
    print(f"Running diarization on {tmp_path}...")
    try:
        res = model.generate(input=tmp_path, batch_size_s=300)
        print("Diarization Result:", res)
        if res and "sentence_info" in res[0]:
            print("Found sentence_info with speaker labels!")
            for sentence in res[0]["sentence_info"]:
                print(f"[{sentence['start']}-{sentence['end']}] Spk {sentence.get('spk', '??')}: {sentence['text']}")
    except Exception as e:
        print(f"Diarization failed: {e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

if __name__ == "__main__":
    # Use an existing audio file for testing if possible
    test_audio = "output/stephen-tong/ephesians/001_ephesians/original.mp3"
    if os.path.exists(test_audio):
        test_diarization(test_audio)
    else:
        print(f"Test audio not found: {test_audio}")

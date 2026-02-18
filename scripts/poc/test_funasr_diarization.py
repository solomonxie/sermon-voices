"""
POC script to test FunASR audio diarization.
Stack: paraformer-large, fsmn-vad, ct-punc, cam++ (diarization)
-> result: doesn't work, can't distinguish between two mandarin speakers
"""
import os
import torch
from funasr import AutoModel
from pydub import AudioSegment

# Set ModelScope cache directory as requested
os.environ["MODELSCOPE_CACHE"] = os.path.expanduser('~/llm_models/modelscope')

def main():
    # 1. Configuration
    audio_file = "/Users/solomonxie/workspace/personal/sermon-voices/output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original.mp3"
    
    if not os.path.exists(audio_file):
        print(f"❌ Audio file not found: {audio_file}")
        return

    # Force CPU because Paraformer uses float64 in some operations (cumsum), 
    # which is not supported on Apple Silicon MPS yet.
    device = "cpu"
    print(f"🚀 Loading FunASR models from {os.environ['MODELSCOPE_CACHE']} on {device}...")

    # Using the exact model names found in the cache
    model = AutoModel(
        model="iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
        vad_model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
        punc_model="iic/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
        spk_model="iic/speech_campplus_sv_zh-cn_16k-common",
        device=device,
        disable_update=True
    )

    # 2. Run Diarization & Transcription
    print(f"🎙️ Processing diarization: {audio_file}")
    # batch_size_s is for VAD/ASR batching
    res = model.generate(input=audio_file, batch_size_s=300)

    # 3. Process and Print Results
    if not res:
        print("❌ No transcription results found.")
        return

    result = res[0]
    print("\n--- Transcription Results ---")
    
    sentences = result.get('sentence_info', [])
    if not sentences:
        print("Full text:", result.get('text', ''))
        sentences = [{
            'text': result.get('text', ''),
            'start': 0,
            'end': 0,
            'spk': 0
        }]

    # 4. Extract Speaker Segments
    audio = AudioSegment.from_file(audio_file)
    speaker_bins = {}
    
    print("\n--- Segments ---")
    for seg in sentences:
        speaker = str(seg.get('spk', 'unknown'))
        start_ms = seg.get('start', 0)
        end_ms = seg.get('end', 0)
        text = seg.get('text', '')
        
        print(f"[{start_ms/1000:.2f}s - {end_ms/1000:.2f}s] Speaker {speaker}: {text}")
        
        if end_ms > start_ms:
            excerpt = audio[start_ms:end_ms]
            if speaker not in speaker_bins:
                speaker_bins[speaker] = AudioSegment.empty()
            speaker_bins[speaker] += excerpt

    # 5. Export Speaker Audios
    for speaker, combined_audio in speaker_bins.items():
        output_filename = audio_file.replace('.mp3', f'_funasr_spk{speaker}.wav')
        combined_audio.export(output_filename, format="wav")
        print(f"✅ Saved speaker sample: {output_filename} ({len(combined_audio)/1000:.1f}s)")

if __name__ == "__main__":
    main()

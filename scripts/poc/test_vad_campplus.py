"""
Not working.
"""

import os
import torch
import numpy as np
from pydub import AudioSegment
from funasr import AutoModel
from sklearn.cluster import KMeans

def main() -> None:
    # 1. Setup
    audio_path = "/Users/solomonxie/workspace/personal/sermon-voices/output/stephen-tong/ephesians/001_answers-to-questions-on-ephesians-0-a/original.mp3"
    if not os.path.exists(audio_path):
        audio_path = audio_path.replace(".mp3", "_cleaned.wav")
    
    if not os.path.exists(audio_path):
        print(f"Error: Audio file not found at {audio_path}")
        return

    output_dir = os.path.dirname(audio_path)
    
    # 2. Extract first 5 minutes
    print(f"Loading {audio_path}...")
    audio = AudioSegment.from_file(audio_path)
    five_minutes_ms = 5 * 60 * 1000
    audio_5min = audio[:five_minutes_ms]
    
    # Silero VAD works best with 16kHz mono
    audio_16k = audio_5min.set_frame_rate(16000).set_channels(1)
    samples = np.array(audio_16k.get_array_of_samples(), dtype=np.float32) / 32768.0
    
    # 3. VAD Split
    print("Loading Silero VAD...")
    model_vad, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad')
    (get_speech_timestamps, _, _, _, _) = utils
    
    print("Running VAD...")
    speech_timestamps = get_speech_timestamps(torch.from_numpy(samples), model_vad, sampling_rate=16000)
    print(f"Found {len(speech_timestamps)} speech segments.")

    # 4. Extract Embeddings with FunASR CampPlus
    print("Loading FunASR CampPlus model...")
    # Force CPU for stability on Mac
    spk_model = AutoModel(model="iic/speech_campplus_sv_zh-cn_16k-common", device="cpu")
    
    embeddings = []
    valid_segments = []
    
    print("Extracting embeddings for each segment...")
    for i, ts in enumerate(speech_timestamps):
        start_ms = int(ts['start'] / 16)
        end_ms = int(ts['end'] / 16)
        
        # Skip segments too short for meaningful embedding (at least 0.5s)
        if end_ms - start_ms < 500:
            continue
            
        # Export segment to temporary wav for FunASR
        segment_audio = audio_5min[start_ms:end_ms]
        temp_segment_path = os.path.join(output_dir, f"_temp_seg_{i}.wav")
        segment_audio.export(temp_segment_path, format="wav")
        
        try:
            # FunASR generate returns a list of dicts
            res = spk_model.generate(input=temp_segment_path)
            if res and 'spk_embedding' in res[0]:
                emb = res[0]['spk_embedding']
                # Convert to numpy and ensure it's a 1D vector
                if isinstance(emb, list):
                    emb = np.array(emb)
                if isinstance(emb, torch.Tensor):
                    emb = emb.cpu().numpy()
                
                # Squeeze to remove extra dimensions like (1, 192) or (1, 1, 192)
                emb = np.squeeze(emb)
                
                if emb.ndim == 1:
                    embeddings.append(emb)
                    valid_segments.append((start_ms, end_ms))
                else:
                    print(f"Warning: Segment {i} produced unexpected embedding shape {emb.shape}")
        except Exception as e:
            print(f"Error extracting embedding for segment {i}: {e}")
            
        if os.path.exists(temp_segment_path):
            os.remove(temp_segment_path)

    if not embeddings:
        print("No embeddings extracted.")
        return

    # 5. Cluster Embeddings
    print(f"Clustering {len(embeddings)} segments (k=2)...")
    embeddings_np = np.stack(embeddings) # Use stack to ensure 2D array (N, D)

    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings_np)
    
    # 6. Export Speaker Samples
    speaker_audio = {}
    
    for i, label in enumerate(labels):
        start_ms, end_ms = valid_segments[i]
        if label not in speaker_audio:
            speaker_audio[label] = AudioSegment.empty()
        speaker_audio[label] += audio_5min[start_ms:end_ms]
        
    for label, combined in speaker_audio.items():
        sample_path = os.path.join(output_dir, f"sample_campplus_spk_{label}.wav")
        combined.export(sample_path, format="wav")
        duration = len(combined) / 1000.0
        print(f"Saved speaker sample: {sample_path} ({duration:.2f}s)")

    print("Success.")

if __name__ == "__main__":
    main()

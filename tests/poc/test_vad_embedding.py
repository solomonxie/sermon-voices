"""
Not working.
"""
import os
import torch
import numpy as np
from pydub import AudioSegment
from dotenv import load_dotenv
from sklearn.cluster import KMeans
from pyannote.audio import Model, Inference

def main() -> None:
    # 1. Setup
    load_dotenv()
    access_token = os.getenv("HF_TOKEN")
    if not access_token:
        print("Error: HF_TOKEN not found in .env")
        return

    # Audio file path
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
    # Get speech segments (in samples)
    # Using 16000 sampling rate as specified
    speech_timestamps = get_speech_timestamps(torch.from_numpy(samples), model_vad, sampling_rate=16000)
    print(f"Found {len(speech_timestamps)} speech segments.")

    # 4. Compute Embeddings for each segment
    print("Loading Pyannote Embedding model...")
    embedding_model = Model.from_pretrained("pyannote/embedding", use_auth_token=access_token)
    inference = Inference(embedding_model, window="whole")
    
    # Use MPS if available
    device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    embedding_model.to(device)
    
    embeddings = []
    valid_segments = []
    
    print("Computing embeddings...")
    for ts in speech_timestamps:
        start_ms = int(ts['start'] / 16) # 16 samples per ms at 16kHz
        end_ms = int(ts['end'] / 16)
        
        # Skip very short segments (less than 0.5s) as they are bad for embeddings
        if end_ms - start_ms < 500:
            continue
            
        # Export segment to temporary wav for Inference
        segment_audio = audio_5min[start_ms:end_ms]
        temp_segment_path = os.path.join(output_dir, "_temp_seg.wav")
        segment_audio.export(temp_segment_path, format="wav")
        
        try:
            emb = inference(temp_segment_path)
            embeddings.append(emb)
            valid_segments.append((start_ms, end_ms))
        except Exception as e:
            print(f"Error computing embedding for segment {start_ms}-{end_ms}: {e}")
            
        if os.path.exists(temp_segment_path):
            os.remove(temp_segment_path)

    if not embeddings:
        print("No valid speech segments found for embedding.")
        return

    # 5. Cluster Embeddings
    print("Clustering embeddings (k=2)...")
    embeddings_np = np.array(embeddings)
    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings_np)
    
    # 6. Merge and Export
    speaker_audio = {0: AudioSegment.empty(), 1: AudioSegment.empty()}
    
    for i, label in enumerate(labels):
        start_ms, end_ms = valid_segments[i]
        speaker_audio[label] += audio_5min[start_ms:end_ms]
        
    for label, combined in speaker_audio.items():
        sample_path = os.path.join(output_dir, f"sample_v2_spk_{label}.wav")
        combined.export(sample_path, format="wav")
        print(f"Saved speaker sample: {sample_path} ({len(combined)/1000:.2f}s)")

    print("Done.")

if __name__ == "__main__":
    main()

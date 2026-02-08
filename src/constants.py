import os

# Model Constants
DEFAULT_MODEL = 'Qwen3-4B-Thinking-2507'

# Path Constants
OUTPUT_ROOT = './output'
BLOBS_ROOT = './blobs'
PROCESSED_LOG = os.path.join(OUTPUT_ROOT, 'processed.txt')
TRANSLATION_MAP_PATH = os.path.join(OUTPUT_ROOT, 'translation_map.txt')

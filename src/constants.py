import os

# Model Constants
DEFAULT_MODEL = 'qwen3:4b-instruct-2507-q8_0'

# Path Constants
OUTPUT_ROOT = './output'
BLOBS_ROOT = './blobs'
PROCESSED_LOG = os.path.join(OUTPUT_ROOT, 'processed.txt')
TRANSLATION_MAP_PATH = os.path.join(OUTPUT_ROOT, 'translation_map_zh_en.txt')
BIBLE_HOTWORDS_PATH = os.path.join(OUTPUT_ROOT, 'bible_hotwords_5000_zh.txt')
CHRISTIAN_HOTWORDS_PATH = os.path.join(OUTPUT_ROOT, 'christian_verbal_hotwords_zh.txt')
FIREREDASR_MODEL_ROOT = os.path.expanduser('~/llm_models/fireredasr')
FUNASR_MODEL_ROOT = os.path.expanduser('~/llm_models/funasr')
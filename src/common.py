import ollama
import json
import re
import os

from src.constants import DEFAULT_MODEL, TRANSLATION_MAP_PATH


def ask_llm(prompt: str, num_ctx: int = 4096, model: str = None, temperature: float = 0.0) -> dict:
    """ Centralized helper for Ollama LLM communication. """
    try:
        response = ollama.generate(
            model=model or DEFAULT_MODEL,
            prompt=prompt,
            format='json',
            options={
                "temperature": temperature,
                "show_think": True,
                "num_ctx": num_ctx,
                # "num_thread": 4,
                # Ollama on M1/Metal handles GPU acceleration automatically.
                # Removing num_thread allows the server to optimize for hardware.
            }
        )
    except Exception as e:
        print(f"⚠️ LLM Error with model {model or DEFAULT_MODEL}: {e}")
        raise e
    content = response['response']
    # Remove <think>...</think> tags
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    try:
        data = json.loads(content)
    except Exception as e:
        print(f'Failed to load answer to json: {content}\n{e}')
        raise e
    return data


def load_translation_cache() -> dict[str, str]:
    """ Loads the translation map from output/translation_map.txt. """
    cache = {}
    if os.path.exists(TRANSLATION_MAP_PATH):
        try:
            with open(TRANSLATION_MAP_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    if ':' in line:
                        original, translation = line.split(':', 1)
                        cache[original.strip()] = translation.strip()
        except Exception as e:
            print(f"⚠️ Error loading translation cache: {e}")
    return cache

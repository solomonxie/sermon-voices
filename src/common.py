import ollama
import json
import time
import re
import os
import functools
from typing import Callable, Any

from src.constants import DEFAULT_MODEL, TRANSLATION_MAP_PATH


def retry(retries: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
    """
    Decorator that retries a function call.
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            for i in range(retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    print(f"⚠️ Retry {i+1}/{retries} for {func.__name__} due to {type(e).__name__}: {e}")
                    if i < retries - 1:
                        time.sleep(delay * (2 ** i))  # Exponential backoff
            raise last_exception
        return wrapper
    return decorator


@retry(retries=3, delay=2.0)
def ask_llm(prompt: str, num_ctx: int = 4096, model: str = None, temperature: float = 0.0) -> dict:
    """ Centralized helper for Ollama LLM communication. """
    try:
        response = ollama.generate(
            model=model or DEFAULT_MODEL,
            prompt=prompt,
            format='json',
            options={
                "temperature": temperature,
                "show_think": False,
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

    # Robust JSON extraction: try to find the first '{' and last '}'
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        content = match.group(0)

    try:
        return json.loads(content)
    except Exception as e:
        print(f"❌ Failed to parse LLM response as JSON: {e}")
        print(f"--- Raw Content ---\n{content}\n-----------------")
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\n{content[:1000]}...")


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


def pad_numbers(text: str) -> str:
    """
    Ensures there is a space between numbers and adjacent words/characters.
    Example: "Title01" -> "Title 01", "20230621Title" -> "20230621 Title"
    """
    if not text:
        return text
    # Add space between non-digit and digit
    text = re.sub(r'([^\s\d])(\d+)', r'\1 \2', text)
    # Add space between digit and non-digit
    text = re.sub(r'(\d+)([^\s\d])', r'\1 \2', text)
    # Collapse multiple spaces
    return re.sub(r'\s+', ' ', text).strip()


def get_custom_instructions(preacher_dir: str, instruction_file: str) -> str:
    """
    Reads custom instructions from a specific .md file in the preacher's directory if it exists.
    """
    instruction_path = os.path.join(preacher_dir, instruction_file)
    if os.path.exists(instruction_path):
        try:
            with open(instruction_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return f"\n\nCUSTOM INSTRUCTIONS:\n{content}"
        except Exception as e:
            print(f"⚠️ Error reading custom instructions from {instruction_path}: {e}")
    return ""


def safe_remove(path: str):
    """ Safely removes a file if it exists. """
    if os.path.exists(path):
        os.remove(path)


def safe_write(path: str, text: str):
    """ Writes text to a file, ensuring the directory exists. Appends text. """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(text + "\n\n")


def safe_replace(src_path: str, dest_path: str):
    """ Safely replaces dest_path with src_path if src_path exists. """
    if os.path.exists(src_path):
        os.replace(src_path, dest_path)


def string_similarity(s1: str, s2: str) -> float:
    """
    Calculates the similarity between two strings using the Levenshtein distance algorithm.
    Returns a score between 0.0 (completely different) and 1.0 (identical).
    """
    s1 = s1.strip()
    s2 = s2.strip()
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    # Ensure s1 is the longer string to save space
    if len(s1) < len(s2):
        s1, s2 = s2, s1

    distances = list(range(len(s2) + 1))
    for i1, c1 in enumerate(s1):
        distances_ = [i1 + 1]
        for i2, c2 in enumerate(s2):
            if c1 == c2:
                distances_.append(distances[i2])
            else:
                distances_.append(1 + min((distances[i2], distances[i2 + 1], distances_[-1])))
        distances = distances_

    distance = distances[-1]
    max_len = max(len(s1), len(s2))
    return 1.0 - (distance / max_len)

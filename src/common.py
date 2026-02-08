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
        raise e


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

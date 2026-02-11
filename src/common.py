import ollama
import json
import time
import re
import os
import functools
from typing import Callable, Any

from openai import OpenAI
from dotenv import load_dotenv

from src.constants import DEFAULT_MODEL, TRANSLATION_MAP_PATH

# Load environment variables from .env file
load_dotenv()

# Global OpenAI client
OPENAI_CLIENT = None
if os.getenv("OPENAI_API_KEY"):
    OPENAI_CLIENT = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def retry(retries: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
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
def ask_llm(prompt: str, num_ctx: int = 10240, model: str = None, temperature: float = 0.0) -> dict:
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
    # Remove <think>...</think> tags if present
    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
    
    # Robust JSON extraction: look for the outermost {}
    match = re.search(r'(\{.*\})', content, re.DOTALL)
    if match:
        content = match.group(1)
    
    # Basic cleanup for common LLM JSON mishaps
    content = content.replace('“', '"').replace('”', '"')

    try:
        return json.loads(content)
    except Exception as e:
        print(f"❌ Failed to parse LLM response as JSON: {e}\nFall back to returning default structure.")
        return {'data': content}


@retry(retries=3, delay=2.0)
def ask_openai(prompt: str, model: str = None, temperature: float = 0.0) -> dict:
    global OPENAI_CLIENT
    if not OPENAI_CLIENT:
        if os.getenv("OPENAI_API_KEY"):
            OPENAI_CLIENT = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        else:
            raise ValueError("OPENAI_API_KEY not found in environment variables.")

    target_model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    
    try:
        response = OPENAI_CLIENT.chat.completions.create(
            model=target_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            response_format={"type": "json_object"}
        )
    except Exception as e:
        print(f"⚠️ OpenAI Error with model {target_model}: {e}")
        raise e

    content = response.choices[0].message.content.strip()
    match = re.search(r'\{.*\}', content, re.DOTALL)
    if match:
        content = match.group(0)
    content = content.replace('“', '"').replace('”', '"')

    try:
        return json.loads(content)
    except Exception as e:
        print(f"❌ Failed to parse OpenAI response as JSON: {e}")
        raise ValueError(f"Failed to parse OpenAI response as JSON: {e}\n{content[:1000]}...")


def load_translation_cache() -> dict[str, str]:
    cache = {}
    if os.path.exists(TRANSLATION_MAP_PATH):
        try:
            with open(TRANSLATION_MAP_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    if ':' in line:
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            original, translation = parts
                            cache[original.strip()] = translation.strip()
        except Exception as e:
            print(f"⚠️ Error loading translation cache: {e}")
    return cache


def pad_numbers(text: str) -> str:
    if not text:
        return text
    # Add space between non-digit and digit
    text = re.sub(r'([^\s\d])(\d+)', r'\1 \2', text)
    # Add space between digit and non-digit
    text = re.sub(r'(\d+)([^\s\d])', r'\1 \2', text)
    # Collapse multiple spaces
    return re.sub(r'\s+', ' ', text).strip()


def get_custom_instructions(preacher_dir: str, instruction_file: str) -> str:
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
    if os.path.exists(path):
        os.remove(path)


def safe_write(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(text + "\n\n")


def safe_replace(src_path: str, dest_path: str):
    if os.path.exists(src_path):
        os.replace(src_path, dest_path)


def string_similarity(s1: str, s2: str) -> float:
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

import ollama
import json
import re
import os

DEFAULT_MODEL = 'qwen3:8b'


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

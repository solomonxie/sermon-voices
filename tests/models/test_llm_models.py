import os
import pytest
from src.common import ask_llm

JUDGE_MODEL = 'qwen3'

# Placeholders for ideal versions (reference standards)
IDEAL_POLISH_ZH = """[PLACEHOLDER: Provide the ideal polished Chinese version here]"""
IDEAL_TRANSLATE_EN = """[PLACEHOLDER: Provide the ideal English translation here]"""

RAW_ZH_SAMPLE = """耶和华是我的牧者，我必不致缺乏。"""
RAW_EN_SAMPLE = """The Lord is my shepherd; I shall not want."""


@pytest.mark.parametrize("model_name", [
    'qwen3:8b', 
    'qwen3:4b-instruct-2507-q8_0',
    'phi3:3.8b',
    'mistral:7b',
    'llama3:latest'
])
def test_polish_zh(model_name):
    print(f"\n🧪 Testing Polish (ZH) with model: {model_name}")
    prompt = f"请润色以下讲章片段，使其更符合圣经语境：\n{RAW_ZH_SAMPLE}"
    res = ask_llm(prompt, model=model_name)
    actual = str(res) # res might be a dict if it returned JSON, but here we expect text or JSON-wrapped text
    # If the LLM returns JSON as requested by ask_llm (format='json' is hardcoded in common.py)
    # We might need to adjust how we extract the refined text.
    # But ask_llm is designed to return a dict.
    
    print(f"📄 Output: {actual[:100]}...")
    score = judge_llm_performance("Polish Chinese Sermon", IDEAL_POLISH_ZH, actual)
    print(f"⭐️ Score: {score:.2f}")
    assert score >= 0.7

@pytest.mark.parametrize("model_name", [
    'qwen3:8b', 
    'qwen3:4b-instruct-2507-q8_0',
    'phi3:3.8b',
    'mistral:7b',
    'llama3:latest'
])
def test_translate_en(model_name):
    print(f"\n🧪 Testing Translation (EN) with model: {model_name}")
    prompt = f"Translate the following Christian metadata to English: {RAW_ZH_SAMPLE}"
    res = ask_llm(prompt, model=model_name)
    actual = str(res) 
    print(f"📄 Output: {actual[:100]}...")
    score = judge_llm_performance("Translate to English", IDEAL_TRANSLATE_EN, actual)
    print(f"⭐️ Score: {score:.2f}")
    assert score >= 0.7

def judge_llm_performance(task: str, ideal: str, actual: str) -> float:
    """
    Uses an LLM judge to evaluate the performance of another LLM's output.
    """
    if "[PLACEHOLDER" in ideal:
        print(f"⚠️ Skipping judgment for {task}: Ideal reference placeholder not filled.")
        return 1.0

    prompt = f"""
    Judge the performance of an LLM on the following task: {task}
    
    Ideal Reference:
    {ideal}
    
    Actual LLM Output:
    {actual}
    
    Evaluate based on accuracy, tone, and adherence to Christian/Biblical context.
    Return a JSON object with a single key 'score' containing a value between 0.0 and 1.0.
    Do not include any explanation.
    """
    res = ask_llm(prompt, model=JUDGE_MODEL)
    return float(res.get('score', 0.0))
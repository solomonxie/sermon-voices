"""
- Goal: test different LLM models and then use LLM to judge the accuracy (softly) with "matching-score".
- It will not call functions from other modules but directly call official libs to make the call
models:
    qwen3, phi3, mistral:7b, llamma3, qwen3:4b-2507....
"""
import pytest

JUDGET_MODEL = 'qwen3'


def test_polish_zh_qwen3():
    # from ... import ...
    score = 0
    assert score > 0.9


def test_polish_zh_qwen3_4b_2507_instruct():
    # from ... import ...
    score = 0
    assert score > 0.9


def test_polish_zh_llamma3():
    # from ... import ...
    score = 0
    assert score > 0.9


def test_translate_en_qwen3():
    # from ... import ...
    score = 0
    assert score > 0.9


def test_translate_en_qwen3_4b_2507_instruct():
    # from ... import ...
    score = 0
    assert score > 0.9


def test_translate_en_llamma3():
    # from ... import ...
    score = 0
    assert score > 0.9

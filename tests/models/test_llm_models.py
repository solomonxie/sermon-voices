"""
- Goal: test different LLM models and then use LLM to judge the accuracy (softly) with "matching-score".
- It will not call functions from other modules but directly call official libs to make the call
"""
import pytest


def test_polish_zh_qwen3():
    score = 0
    assert score > 0.9


def test_polish_zh_qwen3_4b_2507_instruct():
    score = 0
    assert score > 0.9


def test_polish_zh_llamma3():
    score = 0
    assert score > 0.9


def test_translate_en_qwen3():
    score = 0
    assert score > 0.9


def test_translate_en_qwen3_4b_2507_instruct():
    score = 0
    assert score > 0.9


def test_translate_en_llamma3():
    score = 0
    assert score > 0.9

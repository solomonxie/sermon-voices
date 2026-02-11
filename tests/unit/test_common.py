import pytest
from src.common import retry

def test_retry_success():
    @retry(retries=3, delay=0.1)
    def succeed():
        return "success"
    
    assert succeed() == "success"

def test_retry_eventual_success():
    calls = 0
    
    @retry(retries=3, delay=0.1)
    def fail_twice():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ValueError("Failure")
        return "success"
    
    assert fail_twice() == "success"
    assert calls == 3

def test_retry_max_failures():
    calls = 0
    
    @retry(retries=3, delay=0.1)
    def always_fail():
        nonlocal calls
        calls += 1
        raise ValueError(f"Failure {calls}")
    
    with pytest.raises(ValueError, match="Failure 3"):
        always_fail()
    assert calls == 3

def test_retry_specific_exceptions():
    calls = 0
    
    @retry(retries=3, delay=0.1, exceptions=(ValueError,))
    def raise_runtime_error():
        nonlocal calls
        calls += 1
        raise RuntimeError("Immediate failure")
        
    with pytest.raises(RuntimeError, match="Immediate failure"):
        raise_runtime_error()
    assert calls == 1

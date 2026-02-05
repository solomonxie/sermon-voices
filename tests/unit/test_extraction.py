import pytest
from src.main import extract_preacher, extract_series, extract_title, extract_scriptures, extract_sequence, extract_created_at

MODELS = [
    "qwen3:8b",  # PASSED EVERY TEST
    # "qwen2.5:7b",  # failed 1 test
    # "qwen2.5-coder:7b",  # failed 1 test
    # "llama3.1:8b",  # failed some tests
    # "llama3.2:3b",  # failed some tests
    # "llama3:latest"  # failed some tests
    # "phi3:3.8b",  # failed some tests
    # "mistral:7b",  # FAILED EVERY TEST
]

@pytest.mark.parametrize("model", MODELS)
def test_extract_preacher(model):
    path = './blobs/华贤/4传1-93全（rar文件）/密码20232024/20230621传道书042（7章6节）烧荆棘的爆声.mp3'
    preacher = extract_preacher(path, model=model)
    assert preacher == '华贤', f"Model {model} failed"

@pytest.mark.parametrize("model", MODELS)
def test_extract_series(model):
    path = './blobs/华贤/4传1-93全（rar文件）/密码20232024/20230621传道书042（7章6节）烧荆棘的爆声.mp3'
    series = extract_series(path, model=model)
    assert series == '传道书', f"Model {model} failed"

@pytest.mark.parametrize("model", MODELS)
def test_extract_title(model):
    path = './blobs/华贤/4传1-93全（rar文件）/密码20232024/20230621传道书042（7章6节）烧荆棘的爆声.mp3'
    title = extract_title(path, model=model)
    assert title == '烧荆棘的爆声', f"Model {model} failed"

@pytest.mark.parametrize("model", MODELS)
def test_extract_scriptures(model):
    path = './blobs/华贤/4传1-93全（rar文件）/密码20232024/20230621传道书042（7章6节）烧荆棘的爆声.mp3'
    scriptures = extract_scriptures(path, model=model)
    assert scriptures == 'Ecclesiastes ch7:v6', f"Model {model} failed"

@pytest.mark.parametrize("model", MODELS)
def test_extract_sequence(model):
    path = './blobs/华贤/4传1-93全（rar文件）/密码20232024/20230621传道书042（7章6节）烧荆棘的爆声.mp3'
    sequence = extract_sequence(path, model=model)
    assert sequence == '042', f"Model {model} failed"

@pytest.mark.parametrize("model", MODELS)
def test_extract_preacher2(model):
    path = 'blobs/唐崇荣/《唐崇荣-约翰福音》/约翰福音第01讲.mp3'
    preacher = extract_preacher(path, model=model)
    assert preacher == '唐崇荣', f"Model {model} failed"

@pytest.mark.parametrize("model", MODELS)
def test_extract_series2(model):
    path = 'blobs/唐崇荣/《唐崇荣-约翰福音》/约翰福音第01讲.mp3'
    series = extract_series(path, model=model)
    assert series == '约翰福音', f"Model {model} failed"

@pytest.mark.parametrize("model", MODELS)
def test_extract_title2(model):
    path = 'blobs/唐崇荣/《唐崇荣-约翰福音》/约翰福音第01讲.mp3'
    title = extract_title(path, model=model)
    assert title == '约翰福音第01讲', f"Model {model} failed"

@pytest.mark.parametrize("model", MODELS)
def test_extract_scriptures2(model):
    path = 'blobs/唐崇荣/《唐崇荣-约翰福音》/约翰福音第01讲.mp3'
    scriptures = extract_scriptures(path, model=model)
    assert scriptures == 'Unknown', f"Model {model} failed"

@pytest.mark.parametrize("model", MODELS)
def test_extract_sequence2(model):
    path = 'blobs/唐崇荣/《唐崇荣-约翰福音》/约翰福音第01讲.mp3'
    sequence = extract_sequence(path, model=model)
    assert sequence == '001', f"Model {model} failed"

@pytest.mark.parametrize("model", MODELS)
def test_extract_created_at(model):
    path = './blobs/华贤/4传1-93全（rar文件）/密码20232024/20230621传道书042（7章6节）烧荆棘的爆声.mp3'
    created_at = extract_created_at(path, model=model)
    assert created_at == '20230621', f"Model {model} failed"

@pytest.mark.parametrize("model", MODELS)
def test_extract_created_at2(model):
    path = 'blobs/唐崇荣/《唐崇荣-约翰福音》/约翰福音第01讲.mp3'
    created_at = extract_created_at(path, model=model)
    assert created_at == '00000000', f"Model {model} failed"

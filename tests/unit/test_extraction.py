
from src.main import ask_llm
from src.main import extract_preacher, extract_series, extract_title, extract_scriptures


def test_extract_preacher():
    path = './blobs/华贤/4传1-93全（rar文件）/密码20232024/20230621传道书042（7章6节）烧荆棘的爆声.mp3'
    preacher = extract_preacher(path)
    assert preacher == '华贤'


def test_extract_series():
    path = './blobs/华贤/4传1-93全（rar文件）/密码20232024/20230621传道书042（7章6节）烧荆棘的爆声.mp3'
    series = extract_series(path)
    assert series == '传道书'


def test_extract_title():
    path = './blobs/华贤/4传1-93全（rar文件）/密码20232024/20230621传道书042（7章6节）烧荆棘的爆声.mp3'
    title = extract_title(path)
    assert title == '烧荆棘的爆声'


def test_extract_scriptures():
    path = './blobs/华贤/4传1-93全（rar文件）/密码20232024/20230621传道书042（7章6节）烧荆棘的爆声.mp3'
    scriptures = extract_scriptures(path)
    assert scriptures == 'Ecclesiastes ch7:v6'


def test_extract_preacher2():
    path = 'blobs/唐崇荣/《唐崇荣-约翰福音》/约翰福音第01讲.mp3'
    preacher = extract_preacher(path)
    assert preacher == '唐崇荣'


def test_extract_series2():
    path = 'blobs/唐崇荣/《唐崇荣-约翰福音》/约翰福音第01讲.mp3'
    series = extract_series(path)
    assert series == '约翰福音'


def test_extract_title2():
    path = 'blobs/唐崇荣/《唐崇荣-约翰福音》/约翰福音第01讲.mp3'
    title = extract_title(path)
    assert title == '约翰福音第01讲'


def test_extract_scriptures2():
    path = 'blobs/唐崇荣/《唐崇荣-约翰福音》/约翰福音第01讲.mp3'
    scriptures = extract_scriptures(path)
    assert scriptures == 'Unknown'

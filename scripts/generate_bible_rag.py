import os
import sqlite3
import requests
import json
import re
from pypinyin import pinyin, Style

BIBLE_JSON_URL = "https://raw.githubusercontent.com/thiagobodruk/bible/master/json/zh_cuv.json"
DB_PATH = "output/bible_rag.db"
BIBLE_HOTWORDS_PATH = "output/bible_hotwords_5000_zh.txt"
CHRISTIAN_HOTWORDS_PATH = "output/christian_verbal_hotwords_zh.txt"

BOOK_MAP = {
    "gn": "创世记", "ex": "出埃及记", "lv": "利未记", "nm": "民数记", "dt": "申命记",
    "js": "约书亚记", "jg": "士师记", "rt": "路得记", "1s": "撒母耳记上", "2s": "撒母耳记下",
    "1k": "列王纪上", "2k": "列王纪下", "1c": "历代志上", "2c": "历代志下", "ez": "以斯拉记",
    "ne": "尼希米记", "es": "以斯帖记", "jb": "约伯记", "ps": "诗篇", "pr": "箴言",
    "ec": "传道书", "sn": "雅歌", "is": "以赛亚书", "jr": "耶利米书", "lm": "耶利米哀歌",
    "ek": "以西结书", "dn": "但以理书", "hs": "何西阿书", "jl": "约珥书", "am": "阿摩司书",
    "ob": "俄巴底亚书", "jn": "约拿书", "mi": "弥迦书", "na": "那鸿书", "hk": "哈巴谷书",
    "zp": "西番雅书", "hg": "哈该书", "zc": "撒迦利亚书", "ml": "玛拉基书",
    "mt": "马太福音", "mk": "马可福音", "lk": "路加福音", "jo": "约翰福音", "ac": "使徒行传",
    "rm": "罗马书", "1co": "哥林多前书", "2co": "哥林多后书", "gl": "加拉太书", "ep": "以弗所书",
    "ph": "腓立比书", "cl": "歌罗西书", "1ts": "帖撒罗尼迦前书", "2ts": "帖撒罗尼迦后书",
    "1tm": "提摩太前书", "2tm": "提摩太后书", "tt": "提多书", "pl": "腓利门书", "hb": "希伯来书",
    "jm": "雅各书", "1pe": "彼得前书", "2pe": "彼得后书", "1jn": "约翰一书", "2jn": "约翰二书",
    "3jn": "约翰三书", "jd": "犹大书", "rv": "启示录"
}

def get_pinyin(text: str) -> str:
    """Convert Chinese text to Pinyin without tones, joining with empty string."""
    py_list = pinyin(text, style=Style.NORMAL)
    return "".join([item[0] for item in py_list])

def setup_db() -> sqlite3.Connection:
    """Initialize SQLite database for Bible RAG."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verses table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS verses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        book TEXT,
        chapter INTEGER,
        verse INTEGER,
        text TEXT,
        pinyin TEXT
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pinyin ON verses(pinyin)')
    
    # Hotwords table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS hotwords (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        word TEXT,
        pinyin TEXT,
        type TEXT
    )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hotword_pinyin ON hotwords(pinyin)')
    
    conn.commit()
    return conn

def download_bible() -> list:
    """Download CUV Bible JSON."""
    print(f"Downloading Bible from {BIBLE_JSON_URL}...")
    response = requests.get(BIBLE_JSON_URL)
    response.raise_for_status()
    # The JSON sometimes has a BOM at the beginning
    content = response.text.lstrip('\ufeff')
    return json.loads(content)

def insert_bible(conn: sqlite3.Connection, bible_data: list):
    """Insert Bible verses into database."""
    print("Inserting Bible verses and generating pinyin...")
    cursor = conn.cursor()
    for book_data in bible_data:
        abbrev = book_data['abbrev'].lower()
        book_name = BOOK_MAP.get(abbrev, abbrev)
        for chapter_idx, chapter_verses in enumerate(book_data['chapters']):
            chapter_num = chapter_idx + 1
            for verse_idx, verse_text in enumerate(chapter_verses):
                verse_num = verse_idx + 1
                # Clean up verse text (sometimes has extra spaces)
                clean_text = re.sub(r'\s+', '', verse_text)
                py = get_pinyin(clean_text)
                cursor.execute(
                    'INSERT INTO verses (book, chapter, verse, text, pinyin) VALUES (?, ?, ?, ?, ?)',
                    (book_name, chapter_num, verse_num, clean_text, py)
                )
    conn.commit()

def insert_hotwords(conn: sqlite3.Connection):
    """Insert hotwords from local files."""
    cursor = conn.cursor()
    for path, word_type in [(BIBLE_HOTWORDS_PATH, 'bible'), (CHRISTIAN_HOTWORDS_PATH, 'christian')]:
        if os.path.exists(path):
            print(f"Inserting hotwords from {path}...")
            with open(path, 'r', encoding='utf-8') as f:
                for line in f:
                    word = line.strip()
                    if word:
                        py = get_pinyin(word)
                        cursor.execute(
                            'INSERT INTO hotwords (word, pinyin, type) VALUES (?, ?, ?)',
                            (word, py, word_type)
                        )
    conn.commit()

def main():
    conn = setup_db()
    try:
        # Check if already populated
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM verses')
        if cursor.fetchone()[0] == 0:
            bible_data = download_bible()
            insert_bible(conn, bible_data)
        else:
            print("Bible already exists in DB.")
            
        cursor.execute('SELECT COUNT(*) FROM hotwords')
        if cursor.fetchone()[0] == 0:
            insert_hotwords(conn)
        else:
            print("Hotwords already exist in DB.")
            
        print(f"✅ Bible RAG generated at {DB_PATH}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()

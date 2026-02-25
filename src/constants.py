import os

# Model Constants
DEFAULT_MODEL = 'qwen3:4b-instruct-2507-q8_0'

# Path Constants
OUTPUT_ROOT = './output'
BLOBS_ROOT = './blobs'
PROCESSED_LOG = os.path.join(OUTPUT_ROOT, 'processed.txt')
TRANSLATION_MAP_PATH = os.path.join(OUTPUT_ROOT, 'translation_map_zh_en.txt')
BIBLE_HOTWORDS_PATH = os.path.join(OUTPUT_ROOT, 'bible_hotwords_5000_zh.txt')
CHRISTIAN_HOTWORDS_PATH = os.path.join(OUTPUT_ROOT, 'christian_verbal_hotwords_zh.txt')
FIREREDASR_MODEL_ROOT = os.path.expanduser('~/llm_models/fireredasr')
FUNASR_MODEL_ROOT = os.path.expanduser('~/llm_models/funasr')

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
    "1tm": "提摩太前書", "2tm": "提摩太后书", "tt": "提多书", "pl": "腓利门书", "hb": "希伯来书",
    "jm": "雅各书", "1pe": "彼得前书", "2pe": "彼得后书", "1jn": "约翰一书", "2jn": "约翰二书",
    "3jn": "约翰三书", "jd": "犹大书", "rv": "启示录"
}
ZH_TO_ABBREV_MAP = {v: k for k, v in BOOK_MAP.items()}

BIBLE_EN_TO_ZH = {
    "Genesis": "创世记", "Exodus": "出埃及记", "Leviticus": "利未记", "Numbers": "民数记", "Deuteronomy": "申命记",
    "Joshua": "约书亚记", "Judges": "士师记", "Ruth": "路得记", "1 Samuel": "撒母耳记上", "2 Samuel": "撒母耳记下",
    "1 Kings": "列王纪上", "2 Kings": "列王纪下", "1 Chronicles": "历代志上", "2 Chronicles": "历代志下", "Ezra": "以斯拉记",
    "Nehemiah": "尼希米记", "Esther": "以斯帖记", "Job": "约伯记", "Psalms": "诗篇", "Proverbs": "箴言",
    "Ecclesiastes": "传道书", "Song of Solomon": "雅歌", "Isaiah": "以赛亚书", "Jeremiah": "耶利米书", "Lamentations": "耶利米哀歌",
    "Ezekiel": "以西结书", "Daniel": "但以理书", "Hosea": "何西阿书", "Joel": "约珥书", "Amos": "阿摩司书",
    "Obadiah": "俄巴底亚书", "Jonah": "约拿书", "Micah": "弥迦书", "Nahum": "那鸿书", "Habakkuk": "哈巴谷书",
    "Zephaniah": "西番雅书", "Haggai": "哈该书", "Zechariah": "撒迦利亚书", "Malachi": "玛拉基书",
    "Matthew": "马太福音", "Mark": "马可福音", "Luke": "路加福音", "John": "约翰福音", "Acts": "使徒行传",
    "Romans": "罗马书", "1 Corinthians": "哥林多前书", "2 Corinthians": "哥林多后书", "Galatians": "加拉太书", "Ephesians": "以弗所书",
    "Philippians": "腓立比书", "Colossians": "歌罗西书", "1 Thessalonians": "帖撒罗尼迦前书", "2 Thessalonians": "帖撒罗尼迦后书",
    "1 Timothy": "提摩太前书", "2 Timothy": "提摩太后书", "Titus": "提多书", "Philemon": "腓利门书", "Hebrews": "希伯来书",
    "James": "雅各书", "1 Peter": "彼得前书", "2 Peter": "彼得后书", "1 John": "约翰一书", "2 John": "约翰二书",
    "3 John": "约翰三书", "Jude": "犹大书", "Revelation": "启示录"
}

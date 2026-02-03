"""
Bible Book Mapping Utility
Maps Chinese Bible book names (full and abbreviated) to English names.
"""

BIBLE_BOOKS = {
    # Old Testament
    "Genesis": {"zh": "创世记", "abbr": ["创"]},
    "Exodus": {"zh": "出埃及记", "abbr": ["出"]},
    "Leviticus": {"zh": "利未记", "abbr": ["利"]},
    "Numbers": {"zh": "民数记", "abbr": ["民"]},
    "Deuteronomy": {"zh": "申命记", "abbr": ["申"]},
    "Joshua": {"zh": "约书亚记", "abbr": ["约"]},
    "Judges": {"zh": "士师记", "abbr": ["士"]},
    "Ruth": {"zh": "路得记", "abbr": ["得"]},
    "1 Samuel": {"zh": "撒母耳记上", "abbr": ["撒上"]},
    "2 Samuel": {"zh": "撒母耳记下", "abbr": ["撒下"]},
    "1 Kings": {"zh": "列王纪上", "abbr": ["王上"]},
    "2 Kings": {"zh": "列王纪下", "abbr": ["王下"]},
    "1 Chronicles": {"zh": "历代志上", "abbr": ["代上"]},
    "2 Chronicles": {"zh": "历代志下", "abbr": ["代下"]},
    "Ezra": {"zh": "以斯拉记", "abbr": ["拉"]},
    "Nehemiah": {"zh": "尼希米记", "abbr": ["尼"]},
    "Esther": {"zh": "以斯帖记", "abbr": ["帖"]},
    "Job": {"zh": "约伯记", "abbr": ["伯"]},
    "Psalms": {"zh": "诗篇", "abbr": ["诗"]},
    "Proverbs": {"zh": "箴言", "abbr": ["箴"]},
    "Ecclesiastes": {"zh": "传道书", "abbr": ["传"]},
    "Song of Solomon": {"zh": "雅歌", "abbr": ["歌"]},
    "Isaiah": {"zh": "以赛亚书", "abbr": ["赛"]},
    "Jeremiah": {"zh": "耶利米书", "abbr": ["耶"]},
    "Lamentations": {"zh": "耶利米哀歌", "abbr": ["哀"]},
    "Ezekiel": {"zh": "以西结书", "abbr": ["结"]},
    "Daniel": {"zh": "但以理书", "abbr": ["但"]},
    "Hosea": {"zh": "何西阿书", "abbr": ["何"]},
    "Joel": {"zh": "约珥书", "abbr": ["珥"]},
    "Amos": {"zh": "阿摩司书", "abbr": ["摩"]},
    "Obadiah": {"zh": "俄巴底亚书", "abbr": ["俄"]},
    "Jonah": {"zh": "约拿书", "abbr": ["拿"]},
    "Micah": {"zh": "弥迦书", "abbr": ["弥"]},
    "Nahum": {"zh": "那鸿书", "abbr": ["鸿"]},
    "Habakkuk": {"zh": "哈巴谷书", "abbr": ["哈"]},
    "Zephaniah": {"zh": "西番雅书", "abbr": ["番"]},
    "Haggai": {"zh": "哈该书", "abbr": ["该"]},
    "Zechariah": {"zh": "撒迦利亚书", "abbr": ["亚"]},
    "Malachi": {"zh": "玛拉基书", "abbr": ["玛"]},

    # New Testament
    "Matthew": {"zh": "马太福音", "abbr": ["太"]},
    "Mark": {"zh": "马可福音", "abbr": ["可"]},
    "Luke": {"zh": "路加福音", "abbr": ["路"]},
    "John": {"zh": "约翰福音", "abbr": ["约"]},
    "Acts": {"zh": "使徒行传", "abbr": ["徒"]},
    "Romans": {"zh": "罗马书", "abbr": ["罗"]},
    "1 Corinthians": {"zh": "哥林多前书", "abbr": ["林前"]},
    "2 Corinthians": {"zh": "哥林多后书", "abbr": ["林后"]},
    "Galatians": {"zh": "加拉太书", "abbr": ["加"]},
    "Ephesians": {"zh": "以弗所书", "abbr": ["弗"]},
    "Philippians": {"zh": "腓立比书", "abbr": ["腓"]},
    "Colossians": {"zh": "歌罗西书", "abbr": ["西"]},
    "1 Thessalonians": {"zh": "帖撒罗尼迦前书", "abbr": ["帖前"]},
    "2 Thessalonians": {"zh": "帖撒罗尼迦后书", "abbr": ["帖后"]},
    "1 Timothy": {"zh": "提摩太前书", "abbr": ["提前"]},
    "2 Timothy": {"zh": "提摩太后书", "abbr": ["提后"]},
    "Titus": {"zh": "提多书", "abbr": ["多"]},
    "Philemon": {"zh": "腓利门书", "abbr": ["门"]},
    "Hebrews": {"zh": "希伯来书", "abbr": ["来"]},
    "James": {"zh": "雅各书", "abbr": ["雅"]},
    "1 Peter": {"zh": "彼得前书", "abbr": ["彼前"]},
    "2 Peter": {"zh": "彼得后书", "abbr": ["彼后"]},
    "1 John": {"zh": "约翰一书", "abbr": ["约一"]},
    "2 John": {"zh": "约翰二书", "abbr": ["约二"]},
    "3 John": {"zh": "约翰三书", "abbr": ["约三"]},
    "Jude": {"zh": "犹大书", "abbr": ["犹"]},
    "Revelation": {"zh": "启示录", "abbr": ["启"]},
}

# Inverse mapping for quick lookup
ZH_TO_EN = {}
for en, data in BIBLE_BOOKS.items():
    ZH_TO_EN[data["zh"]] = en
    for abbr in data["abbr"]:
        ZH_TO_EN[abbr] = en

def get_english_name(name):
    """Returns the English name for a given Chinese name or abbreviation."""
    return ZH_TO_EN.get(name)

def get_chinese_name(en_name):
    """Returns the Chinese name for a given English name."""
    return BIBLE_BOOKS.get(en_name, {}).get("zh")

if __name__ == "__main__":
    # Test cases
    print(f"创 -> {get_english_name('创')}")
    print(f"马太福音 -> {get_english_name('马太福音')}")
    print(f"Genesis -> {get_chinese_name('Genesis')}")

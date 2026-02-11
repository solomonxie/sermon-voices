import os
import csv
import urllib.request
from typing import List, Dict, Set, Optional

# Bible Books and Aliases (Chinese Union Version)
BIBLE_BOOKS = {
    "创世记": ["创"], "出埃及记": ["出"], "利未记": ["利"], "民数记": ["民"], "申命记": ["申"],
    "约书亚记": ["书"], "士师记": ["士"], "路得记": ["得"],
    "撒母耳记上": ["撒上"], "撒母耳记下": ["撒下"],
    "列王纪上": ["列上"], "列王纪下": ["列下"],
    "历代志上": ["历上"], "历代志下": ["历下"],
    "以斯拉记": ["拉"], "尼希米记": ["尼"], "以斯帖记": ["帖"],
    "约伯记": ["伯"], "诗篇": ["诗"], "箴言": ["箴"], "传道书": ["传"], "雅歌": ["歌"],
    "以赛亚书": ["赛"], "耶利米书": ["耶"], "耶利米哀歌": ["哀"],
    "以西结书": ["结"], "但以理书": ["但"],
    "何西阿书": ["何"], "约珥书": ["珥"], "阿摩司书": ["摩"], "俄巴底亚书": ["俄"],
    "约拿书": ["拿"], "弥迦书": ["弥"], "那鸿书": ["鸿"], "哈巴谷书": ["哈"],
    "西番雅书": ["番"], "哈该书": ["该"], "撒迦利亚书": ["亚"], "玛拉基书": ["玛"],
    "马太福音": ["太"], "马可福音": ["可"], "路加福音": ["路"], "约翰福音": ["约"],
    "使徒行传": ["徒"], "罗马书": ["罗"],
    "哥林多前书": ["林前"], "哥林多后书": ["林后"],
    "加拉太书": ["加"], "以弗所书": ["弗"], "腓立比书": ["腓"], "歌罗西书": ["西"],
    "帖撒罗尼迦前书": ["帖前"], "帖撒罗尼迦后书": ["帖后"],
    "提摩太前书": ["提前"], "提摩太后书": ["提后"],
    "提多书": ["多"], "腓利门书": ["门"], "希伯来书": ["来"], "雅各书": ["雅"],
    "彼得前书": ["彼前"], "彼得后书": ["彼后"],
    "约翰一书": ["约一"], "约翰二书": ["约二"], "约翰三书": ["约三"],
    "犹大书": ["犹"], "启示录": ["启"]
}

# Common Biblical terms to enrich the hot words list
COMMON_TERMS = [
    "耶稣", "基督", "上帝", "耶和华", "神", "主", "救主", "圣灵", "天父", "圣父", "圣子",
    "弥赛亚", "以马内利", "至高者", "万军之耶和华", "救赎", "福音", "真理", "生命", "道路",
    "牧者", "恩典", "信心", "盼望", "公义", "圣洁", "荣耀", "永生", "审判", "悔改", "重生",
    "洗礼", "圣餐", "祈祷", "祷告", "赞美", "敬拜", "团契", "教会", "祭坛", "圣所", "至圣所",
    "圣殿", "律法", "诫命", "先知", "使徒", "门徒", "祭司", "大祭司", "长老", "执事", "牧师",
    "传道", "法利赛人", "撒都该人", "罪人", "外邦人", "犹太人", "以色列人", "创世", "洪水",
    "方舟", "出埃及", "旷野", "迦南", "应许之地", "十诫", "士师", "列王", "被掳", "归回",
    "智慧", "启示", "异象", "神迹", "比喻", "教训", "十字架", "宝血", "埋葬", "复活", "升天",
    "再临", "末世", "新天新地", "圣经", "和合本"
]

NAMES_TSV_URL = "https://raw.githubusercontent.com/BibleNLP/biblical-names-data/master/names.tsv"
DICT_CSV_URL = "https://raw.githubusercontent.com/SuzanaK/biblical_dictionary/master/biblical_dictionary.csv"

def is_chinese(text: str) -> bool:
    if not text:
        return False
    return all('\u4e00' <= char <= '\u9fff' for char in text)

def fetch_content(url: str) -> Optional[str]:
    try:
        print(f"Fetching from {url}...")
        with urllib.request.urlopen(url) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def collect_names() -> Set[str]:
    all_names = set()

    # Source 1: Names TSV
    content = fetch_content(NAMES_TSV_URL)
    if content:
        reader = csv.reader(content.splitlines(), delimiter='\t')
        for row in reader:
            # Try to get Chinese name (usually in col 5 or 6, simplified preferred if known)
            for idx in [5]:
                if len(row) > idx:
                    name = row[idx].strip()
                    if is_chinese(name):
                        all_names.add(name)

    # Source 2: Biblical Dictionary CSV
    content = fetch_content(DICT_CSV_URL)
    if content:
        reader = csv.reader(content.splitlines(), delimiter=';')
        for row in reader:
            # Column 2 is Chinese Simplified
            for idx in [2]:
                if len(row) > idx:
                    name = row[idx].strip()
                    if is_chinese(name):
                        all_names.add(name)

    return all_names

def generate_hot_words():
    # 1. Collect Book Names and Aliases
    books_data = set()
    for book, aliases in BIBLE_BOOKS.items():
        books_data.add(book)
        for alias in aliases:
            books_data.add(alias)
    
    # 2. Collect Names from external sources
    external_names = collect_names()
    
    # 3. Collect Common Terms
    common_terms = set(COMMON_TERMS)
    
    # 4. Merge and Deduplicate
    all_words = list(books_data | external_names | common_terms)
    
    # Sort for consistency
    all_words.sort()
    
    print(f"Total unique words collected: {len(all_words)}")
    
    # 5. Save files with different scales
    scales = [1000, 3000, 5000]
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    
    for scale in scales:
        words_to_save = all_words[:scale]
        filename = os.path.join(output_dir, f"bible_hotwords_{scale}_zh.txt")
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(words_to_save))
        print(f"Saved {len(words_to_save)} words to {filename}")

if __name__ == "__main__":
    generate_hot_words()

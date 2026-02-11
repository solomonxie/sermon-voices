import os

# Common Chinese Christian verbal and theological terms
# Includes Simplified and Traditional versions for maximum ASR coverage
CHRISTIAN_TERMS = [
    "耶稣", "基督教", "耶和华", "圣灵", "祷告", "敬拜", "赞美", "荣耀", "恩典", "拯救", "救恩",
    "十字架", "复活", "升天", "再临", "永生", "天国", "天堂", "地狱", "审判", "公义", "信实",
    "慈爱", "怜悯", "圣洁", "罪恶", "悔改", "重生", "得救", "称义", "成圣", "蒙召", "使徒",
    "先知", "牧师", "传道", "教师", "门徒", "基督徒", "信徒", "长老", "执事", "同工", "团契",
    "教会", "圣殿", "会幕", "约柜", "祭坛", "祭司", "献祭", "律法", "圣经", "旧约", "新约",
    "福音", "启示录", "十诫", "主祷文", "圣餐", "洗礼", "奉献", "宣教", "差传", "灵修",
    "默想", "读经", "证道", "礼拜", "安息日", "主日", "逾越节", "五旬节", "住棚节", "圣诞节",
    "受难节", "复活节", "异象", "属灵", "生命", "权柄", "恩赐", "信心", "爱心", "盼望",
    "忍耐", "节制", "温柔", "良善", "喜乐", "和平", "谦卑", "顺服", "饶恕", "医治", "释放",
    "见证", "灵命", "平安", "祝福", "咒诅", "撒旦", "魔鬼", "窄门", "羔羊", "狮子", "根基",
    "磐石", "活水", "灵粮", "平安夜", "受难日", "三位一体", "阿门", "以马内利", "哈利路亚",
    "保惠师", "训慰师", "查经", "诗歌", "神学", "教义", "教父", "大公教会", "受洗", "受浸",
    "天父", "圣父", "圣子",
    "创世记", "出埃及记", "利未记", "民数记", "申记", "约书亚记", "士师记", "路得记", "撒母耳记",
    "列王纪", "历代志", "以斯拉记", "尼希米记", "以斯帖记", "约伯记", "诗篇", "箴言", "传道书",
    "雅歌", "以赛亚书", "耶利米书", "耶利米哀歌", "以西结书", "但以理书", "何西阿书", "约珥书",
    "阿摩司书", "俄巴底亚书", "约拿书", "弥迦书", "那鸿书", "哈巴谷书", "西番雅书", "哈该书",
    "撒迦利亚书", "玛拉基书", "马太福音", "马可福音", "路加福音", "约翰福音", "使徒行传",
    "罗马书", "哥林多前书", "哥林多后书", "加拉太书", "以弗所书", "腓立比书", "歌罗西书",
    "帖撒罗尼迦前书", "帖撒罗尼迦后书", "提摩太前书", "提摩太后书", "提多书", "腓利门书",
    "希伯来书", "雅各书", "彼得前书", "彼得后书", "约翰一书", "约翰二书", "约翰三书",
    "犹大书", "启示录",
    "低头闭目", "应许", "锡安",
]

def main():
    output_dir = "output"
    verbal_file = os.path.join(output_dir, "christian_verbal_hotwords_zh.txt")
    bible_5000_file = os.path.join(output_dir, "bible_hotwords_1000_zh.txt")
    combined_file = os.path.join(output_dir, "bible_hotwords_combined_zh.txt")

    # 1. Save verbal terms
    with open(verbal_file, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(set(CHRISTIAN_TERMS))))
    print(f"✅ Saved verbal hotwords: {verbal_file}")

    # 2. Merge with bible_hotwords_5000
    all_terms = set(CHRISTIAN_TERMS)
    if os.path.exists(bible_5000_file):
        with open(bible_5000_file, "r", encoding="utf-8") as f:
            for line in f:
                term = line.strip()
                if term:
                    all_terms.add(term)
        print(f"📖 Loaded bible hotwords from: {bible_5000_file}")
    else:
        print(f"⚠️ {bible_5000_file} not found. Skipping merge.")

    # 3. Save combined list
    with open(combined_file, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(all_terms)))
    print(f"✅ Saved combined hotwords: {combined_file}")

if __name__ == "__main__":
    main()

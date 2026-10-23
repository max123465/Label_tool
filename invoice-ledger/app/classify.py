from __future__ import annotations

DEFAULT_CATEGORIES = ["餐飲", "交通", "日用品", "娛樂", "醫療", "居家", "其他"]

KEYWORDS: dict[str, list[str]] = {
    "餐飲": [
        "便當", "飯", "麵", "粥", "咖啡", "拿鐵", "美式", "茶", "奶茶", "飲料", "豆漿", "牛奶", "鮮奶",
        "漢堡", "薯條", "雞", "牛肉", "豬", "排骨", "魚", "蝦", "蛋", "早餐", "午餐", "晚餐", "套餐",
        "披薩", "壽司", "火鍋", "麻辣", "滷味", "鹽酥雞", "水餃", "鍋貼", "包子", "饅頭", "麵包",
        "吐司", "蛋糕", "甜點", "布丁", "冰", "三明治", "飯糰", "御飯糰", "沙拉", "果汁", "可樂",
        "汽水", "礦泉水", "啤酒", "零食", "餅乾", "洋芋片", "巧克力", "泡麵", "優格", "水果",
        "香蕉", "蘋果", "便利商店", "麥當勞", "肯德基", "摩斯", "星巴克", "路易莎", "85度C",
        "50嵐", "清心", "迷客夏", "可不可", "鼎泰豐", "拉麵", "餐廳", "小吃", "食品", "吃",
    ],
    "交通": [
        "加油", "汽油", "無鉛", "柴油", "中油", "台塑石油", "全國加油", "停車", "高鐵", "台鐵",
        "捷運", "悠遊卡", "一卡通", "加值", "計程車", "客運", "公車", "Uber", "洗車", "ETC",
        "機車", "輪胎", "保養",
    ],
    "日用品": [
        "衛生紙", "面紙", "抽取", "洗髮", "沐浴", "牙膏", "牙刷", "洗衣", "柔軟精", "清潔",
        "垃圾袋", "電池", "濕紙巾", "洗碗", "洗手", "衛生棉", "尿布", "保鮮膜", "塑膠袋", "購物袋",
        "刮鬍", "化妝", "乳液", "防曬", "屈臣氏", "康是美", "寶雅", "文具", "筆",
    ],
    "娛樂": [
        "電影", "影城", "威秀", "秀泰", "國賓", "遊戲", "KTV", "錢櫃", "好樂迪", "門票", "票",
        "書", "雜誌", "Netflix", "Steam", "玩具", "樂園", "健身", "運動", "誠品", "博客來",
    ],
    "醫療": [
        "藥", "診所", "醫院", "掛號", "藥局", "維他命", "維生素", "口罩", "保健", "眼藥",
        "OK繃", "酸痛", "感冒", "藥膏", "牙醫", "眼科", "大樹", "杏一", "丁丁",
    ],
    "居家": [
        "家具", "IKEA", "宜家", "特力屋", "HOLA", "燈泡", "燈", "水電", "電費", "水費", "瓦斯",
        "寢具", "枕頭", "棉被", "床", "收納", "五金", "廚具", "鍋具", "碗", "盤", "杯", "毛巾",
        "窗簾", "地墊", "家電", "電器", "燦坤", "全國電子", "延長線",
    ],
}


def classify(merchant: str | None, items: list[dict], categories: list[str]) -> str | None:
    """Keyword-based guess; returns None when nothing matched."""
    scores: dict[str, float] = {}

    def hit(text: str, weight: float):
        for cat, words in KEYWORDS.items():
            if cat not in categories:
                continue
            if any(w.lower() in text.lower() for w in words):
                scores[cat] = scores.get(cat, 0) + weight

    total = 0.0
    for item in items:
        amount = abs((item.get("qty") or 1) * (item.get("price") or 0)) or 1
        total += amount
        hit(item.get("name") or "", amount)
    if merchant:
        # Items outweigh the store name: a convenience store also sells tissues.
        hit(merchant, total * 0.4 if total else 1)

    if not scores:
        return None
    return max(scores, key=scores.get)

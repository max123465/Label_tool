#!/usr/bin/env python3
"""Build the 2027/4/15–5/4 chill South Island budget workbook (2 pax)."""

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUT_DIR = Path(__file__).resolve().parent
FILES = [
    OUT_DIR / "NZ_South_Island_chill_2pax_2027apr.xlsx",
    OUT_DIR / "紐西蘭南島chill行程_兩人_2027四五.xlsx",
    Path("/opt/cursor/artifacts/NZ_South_Island_chill_2pax_2027apr.xlsx"),
]

YELLOW = PatternFill("solid", fgColor="FFF3B0")
HEADER = PatternFill("solid", fgColor="1F4E79")
SECTION = PatternFill("solid", fgColor="D6E3F0")
ORANGE = PatternFill("solid", fgColor="F8CBAD")
GREEN = PatternFill("solid", fgColor="C6EFCE")
LIGHT = PatternFill("solid", fgColor="F2F2F2")
WHITE = PatternFill("solid", fgColor="FFFFFF")
THIN = Border(
    left=Side(style="thin", color="B0B0B0"),
    right=Side(style="thin", color="B0B0B0"),
    top=Side(style="thin", color="B0B0B0"),
    bottom=Side(style="thin", color="B0B0B0"),
)
WRAP = Alignment(wrap_text=True, vertical="center")
CENTER = Alignment(wrap_text=True, vertical="center", horizontal="center")
HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(name="Calibri", bold=True, size=16, color="1F4E79")
H2_FONT = Font(name="Calibri", bold=True, size=13, color="1F4E79")
BOLD = Font(name="Calibri", bold=True, size=11)
NORMAL = Font(name="Calibri", size=11)
NZD = '"NZ$"#,##0'
TWD = '"NT$"#,##0'
INT = "#,##0"
KM = "0"

DAYS = [
    # day, date, dow, stay, drive, km, daytime, activity, act, hotel, food, fuel, stay_tip, note, risk
    (1, "2027/4/17", "六", "基督城", "當地", 30,
     "凌晨抵 CHC，休息到中午。機場取車、超市補貨、植物園或 New Brighton 散步。不排活動。",
     "—", 0, 160, 100, 8,
     "機場 / 市區 motel",
     "第一天右駕，只開短程。租車櫃台約 08:00 開門。", False),
    (2, "2027/4/18", "日", "凱庫拉", "CHC→Kaikoura 2.5h", 180,
     "沿海 SH1 北上。下午半島步道、看海豹。傍晚龍蝦。不趕賞鯨。",
     "—", 0, 150, 130, 40,
     "Sudima / Anchor Inn 海濱",
     "週日路況單純。賞鯨留到週一，取消還有隔天緩衝。", False),
    (3, "2027/4/19", "一", "凱庫拉", "當地", 40,
     "上午 Whale Watch（建議 10:30）。下午發呆、海岸。若取消，改訂 4/20 早班再出發。",
     "凱庫拉觀鯨 Ocean Cabin", 370, 150, 140, 10,
     "連住第 2 晚",
     "官網 NZ$185／人至 2027/9/30。看不到鯨退 80%。暈船藥自備。", False),
    (4, "2027/4/20", "二", "霍基蒂卡", "經 Hanmer＋Lewis Pass 6.5h", 420,
     "經漢默泉泡湯 1.5–2h（不必過夜），再走 Lewis Pass 到西岸。夠力再停 Pancake Rocks。",
     "漢默泉泡湯（可選）", 80, 140, 130, 90,
     "Hokitika motel",
     "全行程最長車日。漢默泡湯當中途休息。沿路加油。", True),
    (5, "2027/4/21", "三", "弗蘭茲約瑟夫", "Hokitika→Franz 2h", 160,
     "上午 Hokitika Gorge（免費、水色很美）。午後抵冰川村報到、走谷底步道遠看冰。",
     "—", 0, 180, 130, 35,
     "Franz 中價 motel",
     "Heli-hike 明天。今天只適應西岸天氣。", False),
    (6, "2027/4/22", "四", "弗蘭茲約瑟夫", "當地", 20,
     "直升機冰川健行（半天，裝備全含）。取消則改 4/23。下午回房休息。",
     "Franz heli-hike", 1798, 180, 130, 6,
     "連住",
     "官網至 2027/9/30 為 NZ$899／人。西岸取消率高，所以連住 3 晚。", True),
    (7, "2027/4/23", "五", "弗蘭茲約瑟夫", "Franz↔Fox 往返", 50,
     "天氣備援日。能飛就補 heli-hike；不能就黎明去 Lake Matheson 拍鏡面。整天可以很閒。",
     "—", 0, 180, 130, 12,
     "連住第 3 晚",
     "這晚是為冰川天氣買的保險，不要再往前趕。", False),
    (8, "2027/4/24", "六", "箭鎮", "Franz→Haast→Wanaka→Arrowtown 5h", 400,
     "Haast Pass 本身是景。Wanaka 咖啡＋That Wanaka Tree。傍晚進箭鎮住下來。",
     "—", 0, 230, 140, 85,
     "箭鎮村內 B&B／motel，不要住皇后鎮",
     "Haast 前加油。週六箭鎮較擠，先入住，楓葉留明天清晨。", True),
    (9, "2027/4/25", "日", "箭鎮", "當地／Lake Hayes", 40,
     "07:30 前走 Buckingham Street、中國村、Arrow River。再到 Lake Hayes 拍倒影。下午發呆。",
     "—", 0, 230, 140, 10,
     "連住",
     "4 月下旬是箭鎮金黃高峰。主要是楊樹、橡樹、楓香，不是台灣那種楓。", False),
    (10, "2027/4/26", "一", "箭鎮", "可去皇后鎮或 Glenorchy", 80,
     "週一比較空。可去 Glenorchy 湖灣，或皇后鎮散步。不跳傘、不彈跳。酒莊要有指定駕駛。",
     "—", 0, 230, 140, 18,
     "連住第 3 晚",
     "Arrowtown Autumn Festival 是 4/15–18，你們會錯過人潮，楓葉通常還在。", False),
    (11, "2027/4/27", "二", "蒂阿瑙", "Arrowtown→Te Anau 2.5h", 190,
     "中午前出發即可。超市補米佛隔日食物（沿路沒店）。晚上想去再訂螢火蟲洞，不勉強。",
     "螢火蟲洞（可選，表內未列）", 0, 180, 130, 42,
     "Distinction / Lakefront",
     "螢火蟲洞約 NZ$145–154／人。累了就看湖。", False),
    (12, "2027/4/28", "三", "蒂阿瑙", "Te Anau↔Milford 往返 5h", 240,
     "07:00 自駕 SH94：Mirror Lakes、Homer Tunnel。訂 11:10 或 13:30 小船。傍晚回蒂阿瑙。",
     "米佛峽灣遊船（自駕＋船）", 376, 180, 130, 52,
     "連住",
     "Mitre Peak／Cruise Milford 約 NZ$179–188。不要買皇后鎮巴士一日遊。", True),
    (13, "2027/4/29", "四", "普卡基／Twizel", "經 Cromwell＋Lindis 6h", 400,
     "回程不繞但尼丁。Lindis Pass 秋天很美。Omarama 可停熱湯池。傍晚抵普卡基看牛奶藍。",
     "Omarama Hot Tubs（可選）", 0, 200, 130, 85,
     "普卡基湖景 cabin 或 Twizel motel",
     "Twizel 有超市、比較好住；湖景要訂普卡基路邊。", True),
    (14, "2027/4/30", "五", "普卡基／Twizel", "Pukaki↔Mt Cook 往返 1.5h", 140,
     "庫克山一日：早上 Hooker Valley（免費必走），下午 Glacier Explorers 冰河湖船。",
     "庫克山 Glacier Explorers", 438, 200, 140, 30,
     "連住，看得到庫克山最好",
     "船是 NZ$219／人，從 2026/10/1。隱士只上去吃飯／報到，不必硬住。", False),
    (15, "2027/5/1", "六", "蒂卡波", "Pukaki→Tekapo 50min", 70,
     "普卡基再看一次日出。慢慢開到蒂卡波。下午湖邊、Tekapo Springs。教堂等人少再拍。",
     "蒂卡波溫泉（可選）", 0, 230, 130, 16,
     "湖景 motel；無景房不值得",
     "牧羊人教堂日出比日落空。這兩晚就是發呆用的。", False),
    (16, "2027/5/2", "日", "蒂卡波", "當地", 25,
     "整天留著。想觀星就訂 Dark Sky 約翰山 Summit；雲多可改 Crater 或自己看。",
     "Dark Sky 約翰山 Summit", 478, 230, 130, 6,
     "連住第 2 晚",
     "Summit 約 NZ$219–239。天氣不好有室內備援。", False),
    (17, "2027/5/3", "一", "基督城", "Tekapo→CHC 3.5h", 230,
     "上午離開。還車前加滿油。住機場附近。有力氣才去阿卡羅阿看企鵝，不排進預算。",
     "—", 0, 160, 120, 50,
     "CHC 機場 10 分鐘內 motel",
     "5/4 15:00 起飛，不要 5/4 早上才從蒂卡波出發。", False),
    (18, "2027/5/4", "二", "回台", "還車→機場", 20,
     "11:00 前還車，13:00 到機場。CHC 15:00 起飛。",
     "—", 0, 0, 80, 6,
     "無住宿",
     "國際／轉機都請預留 2 小時以上。", False),
]


def style_header(ws, row, cols):
    for col in range(1, cols + 1):
        cell = ws.cell(row, col)
        cell.fill = HEADER
        cell.font = HEADER_FONT
        cell.alignment = CENTER
        cell.border = THIN


def apply_border_font(cell, font=NORMAL, fill=None, align=WRAP, num=None):
    cell.font = font
    cell.alignment = align
    cell.border = THIN
    if fill is not None:
        cell.fill = fill
    if num:
        cell.number_format = num


def set_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def add_sheet_overview(wb):
    ws = wb.create_sheet("01_總覽")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "紐西蘭南島 chill 行程｜兩人｜2027/4/15 去、5/4 回"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:F1")
    ws.row_dimensions[1].height = 28

    ws["A2"] = "黃色格子可改。改人數、匯率、機票，後面各表會跟著算。"
    ws["A2"].font = Font(name="Calibri", italic=True, size=11, color="666666")
    ws.merge_cells("A2:F2")

    labels = [
        (4, "人數", 2, "人"),
        (5, "匯率（1 NZD）", 18, "TWD"),
        (6, "機票一人（含稅，請改成實際票價）", 40000, "TWD"),
        (7, "租車日數", 18, "天"),
        (8, "租車本體／天", 58, "NZD"),
        (9, "全險／零自負額／天", 32, "NZD"),
        (10, "餐食兩人／天（平均）", 128, "NZD"),
    ]
    ws["A3"] = "可改假設"
    ws["A3"].font = H2_FONT
    for r, (row, label, val, unit) in enumerate(labels):
        ws.cell(row, 1, label)
        apply_border_font(ws.cell(row, 1), BOLD, SECTION)
        ws.cell(row, 2, val)
        fmt = TWD if unit == "TWD" else (NZD if unit == "NZD" else INT)
        apply_border_font(ws.cell(row, 2), BOLD, YELLOW, CENTER, fmt)
        ws.cell(row, 3, unit)
        apply_border_font(ws.cell(row, 3), NORMAL, LIGHT, CENTER)

    ws["A12"] = "兩人總表（連動每日表）"
    ws["A12"].font = H2_FONT
    headers = ["項目", "兩人 NZD", "兩人 TWD", "每人 TWD", "備註"]
    for i, h in enumerate(headers, 1):
        ws.cell(13, i, h)
    style_header(ws, 13, 5)

    rows = [
        ("機票", "='01_總覽'!B4*'01_總覽'!B6/'01_總覽'!B5", "實際訂位後改 B6"),
        ("NZeTA + IVL", 234, "NZ$17/23 + NZ$100，兩人"),
        ("旅遊保險", 420, "約 20 天、兩人"),
        ("住宿 17 晚", "=SUM('02_每日行程'!I3:I20)", "含箭鎮／蒂卡波秋季溢價"),
        ("租車本體", "=B7*B8", "CHC 取還、小車自排"),
        ("租車全險", "=B7*B9", "零自負額＋建議含玻璃／輪胎"),
        ("油錢", "=SUM('02_每日行程'!K3:K20)", "約 2,760 km"),
        ("餐食", "=SUM('02_每日行程'!J3:J20)", "兩人三餐"),
        ("活動（表內 5 項）", "=SUM('02_每日行程'!H3:H20)", "賞鯨＋冰川＋米佛＋探險＋觀星"),
        ("雜支／停車／洗衣", 250, "米佛停車場等"),
    ]
    for i, (name, val, note) in enumerate(rows):
        r = 14 + i
        ws.cell(r, 1, name)
        apply_border_font(ws.cell(r, 1), NORMAL, WHITE)
        c = ws.cell(r, 2, val)
        apply_border_font(c, NORMAL, WHITE, CENTER, NZD)
        ws.cell(r, 3, f"=B{r}*$B$5")
        apply_border_font(ws.cell(r, 3), NORMAL, WHITE, CENTER, TWD)
        ws.cell(r, 4, f"=C{r}/$B$4")
        apply_border_font(ws.cell(r, 4), NORMAL, WHITE, CENTER, TWD)
        ws.cell(r, 5, note)
        apply_border_font(ws.cell(r, 5), NORMAL, WHITE)

    total_r, buf_r = 24, 25
    ws.cell(total_r, 1, "合計")
    apply_border_font(ws.cell(total_r, 1), BOLD, SECTION)
    ws.cell(total_r, 2, "=SUM(B14:B23)")
    apply_border_font(ws.cell(total_r, 2), BOLD, SECTION, CENTER, NZD)
    ws.cell(total_r, 3, f"=B{total_r}*$B$5")
    apply_border_font(ws.cell(total_r, 3), BOLD, SECTION, CENTER, TWD)
    ws.cell(total_r, 4, f"=C{total_r}/$B$4")
    apply_border_font(ws.cell(total_r, 4), BOLD, SECTION, CENTER, TWD)
    apply_border_font(ws.cell(total_r, 5), BOLD, SECTION)

    ws.cell(buf_r, 1, "含 10% 緩衝")
    apply_border_font(ws.cell(buf_r, 1), BOLD, GREEN)
    ws.cell(buf_r, 2, f"=B{total_r}*1.1")
    apply_border_font(ws.cell(buf_r, 2), BOLD, GREEN, CENTER, NZD)
    ws.cell(buf_r, 3, f"=B{buf_r}*$B$5")
    apply_border_font(ws.cell(buf_r, 3), BOLD, GREEN, CENTER, TWD)
    ws.cell(buf_r, 4, f"=C{buf_r}/$B$4")
    apply_border_font(ws.cell(buf_r, 4), BOLD, GREEN, CENTER, TWD)
    ws.cell(buf_r, 5, "票價／全險／秋季住宿都可能再漲")
    apply_border_font(ws.cell(buf_r, 5), NORMAL, GREEN)

    ws["A27"] = "這次跟上一版 14 天的差別"
    ws["A27"].font = H2_FONT
    notes = [
        "4/15 23:55 起飛，4/17 凌晨到基督城；5/4 15:00 從基督城回。南島 17 晚、18 個白天。",
        "路線改 chill：凱庫拉 2 晚、弗蘭茲 3 晚、箭鎮 3 晚、普卡基＋蒂卡波 4 晚。砍皮克頓、但尼丁、奧瑪魯。",
        "箭鎮 4 月下旬是金黃季。2027 Autumn Festival 是 4/15–18，你們 4/24 才到，人較少、葉子通常還在。",
        "租車全險不便宜（約每天 NZ$25–35），但南島標準自負額 NZ$3,000–6,000，建議買。18 天全險大約 NZ$576／NT$10,368。",
    ]
    for i, t in enumerate(notes):
        ws.cell(28 + i, 1, t)
        ws.merge_cells(start_row=28 + i, start_column=1, end_row=28 + i, end_column=5)
        ws.cell(28 + i, 1).alignment = WRAP
        ws.row_dimensions[28 + i].height = 32

    set_widths(ws, [42, 16, 16, 16, 48])
    ws.freeze_panes = "A14"
    ws.row_dimensions[13].height = 22
    return ws


def add_sheet_daily(wb):
    ws = wb.create_sheet("02_每日行程")
    ws["A1"] = "18 天 chill 逐日｜黃色＝可改數字｜橘色列＝車程或天氣風險"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:P1")
    headers = [
        "日", "日期", "星期", "過夜", "車程", "公里", "白天行程", "指定活動",
        "活動兩人 NZD", "住宿兩人 NZD", "餐食兩人 NZD", "油錢 NZD",
        "租車日攤 NZD", "當天兩人 NZD", "當天兩人 TWD", "住宿建議／備註",
    ]
    for i, h in enumerate(headers, 1):
        ws.cell(2, i, h)
    style_header(ws, 2, 16)

    for i, d in enumerate(DAYS):
        r = 3 + i
        day, date, dow, stay, drive, km, daytime, activity, act, hotel, food, fuel, tip, note, risk = d
        fill = ORANGE if risk else (LIGHT if i % 2 else WHITE)
        values = [day, date, dow, stay, drive, km, daytime, activity, act, hotel, food, fuel]
        for c, v in enumerate(values, 1):
            cell = ws.cell(r, c, v)
            font = BOLD if c == 1 else NORMAL
            num = KM if c == 6 else (NZD if c >= 9 else None)
            apply_border_font(cell, font, fill, WRAP if c in (5, 7, 8, 16) else CENTER, num)
            if c in (9, 10, 11, 12):
                cell.fill = YELLOW
        ws.cell(r, 13, f"=('01_總覽'!$B$8+'01_總覽'!$B$9)")
        apply_border_font(ws.cell(r, 13), NORMAL, fill, CENTER, NZD)
        ws.cell(r, 14, f"=I{r}+J{r}+K{r}+L{r}+M{r}")
        apply_border_font(ws.cell(r, 14), BOLD, fill, CENTER, NZD)
        ws.cell(r, 15, f"=N{r}*'01_總覽'!$B$5")
        apply_border_font(ws.cell(r, 15), NORMAL, fill, CENTER, TWD)
        ws.cell(r, 16, f"{tip}｜{note}")
        apply_border_font(ws.cell(r, 16), NORMAL, fill, WRAP)
        ws.row_dimensions[r].height = 48

    r = 21
    ws.cell(r, 1, "合計")
    apply_border_font(ws.cell(r, 1), BOLD, SECTION, CENTER)
    for c in range(2, 6):
        apply_border_font(ws.cell(r, c), BOLD, SECTION)
    ws.cell(r, 6, "=SUM(F3:F20)")
    apply_border_font(ws.cell(r, 6), BOLD, SECTION, CENTER, INT)
    apply_border_font(ws.cell(r, 7), BOLD, SECTION)
    apply_border_font(ws.cell(r, 8), BOLD, SECTION)
    for c, letter in ((9, "I"), (10, "J"), (11, "K"), (12, "L"), (13, "M"), (14, "N")):
        ws.cell(r, c, f"=SUM({letter}3:{letter}20)")
        apply_border_font(ws.cell(r, c), BOLD, SECTION, CENTER, NZD)
    ws.cell(r, 15, "=N21*'01_總覽'!$B$5")
    apply_border_font(ws.cell(r, 15), BOLD, SECTION, CENTER, TWD)
    apply_border_font(ws.cell(r, 16), BOLD, SECTION)
    ws.row_dimensions[r].height = 22
    ws.row_dimensions[2].height = 24

    set_widths(ws, [6, 12, 6, 16, 28, 8, 46, 28, 14, 14, 14, 12, 14, 14, 14, 52])
    ws.freeze_panes = "A3"
    ws.auto_filter.ref = "A2:P20"
    return ws


def add_sheet_stays(wb):
    ws = wb.create_sheet("03_住宿")
    ws["A1"] = "17 晚住宿｜黃色可改單價"
    ws["A1"].font = TITLE_FONT
    headers = ["區塊", "晚數", "日期", "建議房型", "兩人／晚 NZD", "小計 NZD", "小計 TWD", "為什麼這樣住"]
    for i, h in enumerate(headers, 1):
        ws.cell(2, i, h)
    style_header(ws, 2, 8)
    blocks = [
        ("基督城（抵達）", 1, "4/17", "機場或市區 motel", 160, "紅眼抵達，只求能睡"),
        ("凱庫拉", 2, "4/18–19", "海濱 motel", 150, "賞鯨備援＋龍蝦"),
        ("霍基蒂卡", 1, "4/20", "中價 motel", 140, "拆開西岸長途"),
        ("弗蘭茲約瑟夫", 3, "4/21–23", "村內 motel", 180, "冰川天氣緩衝"),
        ("箭鎮", 3, "4/24–26", "村內、能走去主街", 230, "楓葉季住村裡，清晨沒人"),
        ("蒂阿瑙", 2, "4/27–28", "湖濱 motel", 180, "米佛自駕基地"),
        ("普卡基／Twizel", 2, "4/29–30", "能看庫克山的 cabin／motel", 200, "庫克山一日來回，比隱士便宜"),
        ("蒂卡波", 2, "5/1–2", "湖景", 230, "教堂＋觀星，無景房不要"),
        ("基督城（出發）", 1, "5/3", "機場 10 分鐘內", 160, "5/4 15:00 班機"),
    ]
    for i, (name, nights, dates, room, rate, why) in enumerate(blocks):
        r = 3 + i
        fill = LIGHT if i % 2 else WHITE
        ws.cell(r, 1, name)
        apply_border_font(ws.cell(r, 1), BOLD, fill)
        ws.cell(r, 2, nights)
        apply_border_font(ws.cell(r, 2), NORMAL, fill, CENTER, INT)
        ws.cell(r, 3, dates)
        apply_border_font(ws.cell(r, 3), NORMAL, fill, CENTER)
        ws.cell(r, 4, room)
        apply_border_font(ws.cell(r, 4), NORMAL, fill)
        ws.cell(r, 5, rate)
        apply_border_font(ws.cell(r, 5), NORMAL, YELLOW, CENTER, NZD)
        ws.cell(r, 6, f"=B{r}*E{r}")
        apply_border_font(ws.cell(r, 6), BOLD, fill, CENTER, NZD)
        ws.cell(r, 7, f"=F{r}*'01_總覽'!$B$5")
        apply_border_font(ws.cell(r, 7), NORMAL, fill, CENTER, TWD)
        ws.cell(r, 8, why)
        apply_border_font(ws.cell(r, 8), NORMAL, fill)
    r = 12
    ws.cell(r, 1, "合計")
    apply_border_font(ws.cell(r, 1), BOLD, SECTION)
    ws.cell(r, 2, "=SUM(B3:B11)")
    apply_border_font(ws.cell(r, 2), BOLD, SECTION, CENTER, INT)
    for c in (3, 4, 5, 8):
        apply_border_font(ws.cell(r, c), BOLD, SECTION)
    ws.cell(r, 6, "=SUM(F3:F11)")
    apply_border_font(ws.cell(r, 6), BOLD, SECTION, CENTER, NZD)
    ws.cell(r, 7, "=F12*'01_總覽'!$B$5")
    apply_border_font(ws.cell(r, 7), BOLD, SECTION, CENTER, TWD)
    set_widths(ws, [22, 8, 14, 32, 16, 14, 14, 40])
    ws.freeze_panes = "A3"
    return ws


def add_sheet_car(wb):
    ws = wb.create_sheet("04_租車與全險")
    ws["A1"] = "基督城取還｜18 天｜小車自排＋全險"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:D1")

    headers = ["項目", "數字", "單位", "說明"]
    for i, h in enumerate(headers, 1):
        ws.cell(3, i, h)
    style_header(ws, 3, 4)
    rows = [
        ("取車", "2027/4/17 約 10:00", "", "凌晨到、睡醒再取。Major 品牌機場櫃台早上開門。"),
        ("還車", "2027/5/4 約 11:00", "", "15:00 起飛，11:00 還、13:00 到機場。"),
        ("日數", "='01_總覽'!B7", "天", "超過 24h 可能被算 19 天，預留 18。"),
        ("本體／天", "='01_總覽'!B8", "NZD", "4–5 月小車自排、14 天以上大約 NZ$45–70。"),
        ("全險／天", "='01_總覽'!B9", "NZD", "本地品牌零自負額大約 NZ$25–35；Hertz SuperCover 常到 NZ$46。"),
        ("本體小計", "=B6*B7", "NZD", ""),
        ("全險小計", "=B6*B8", "NZD", "約 NT$10,000–12,000。看起來貴，但標準自負額是 NZ$3,000–6,000。"),
        ("租車＋全險", "=B9+B10", "NZD", "兩人分攤大約每人 NT$14,600。"),
        ("預估公里", "=SUM('02_每日行程'!F3:F20)", "km", "含米佛往返、庫克山一日。"),
        ("油耗假設", 8, "L/100km", "小車自排、有山路。"),
        ("油價假設", 2.4, "NZD/L", "4–5 月南島常見區間。"),
        ("油錢試算", "=B12*B13/100*B14", "NZD", "跟每日表油錢加總可能差幾十塊，屬估價。"),
        ("不買全險的風險", 3500, "NZD", "典型 excess；刷卡還會被預扣同等金額。"),
    ]
    for i, (name, val, unit, note) in enumerate(rows):
        r = 4 + i
        fill = YELLOW if name in ("油耗假設", "油價假設") else WHITE
        apply_border_font(ws.cell(r, 1, name), BOLD, SECTION if i >= 5 else LIGHT)
        cell = ws.cell(r, 2, val)
        num = NZD if "NZD" in str(unit) or name.endswith("小計") or "險" in name or name == "油錢試算" or name == "租車＋全險" or name == "不買全險的風險" else (INT if unit in ("天", "km") else None)
        if name == "油價假設":
            num = "0.00"
        if name == "油耗假設":
            num = "0.0"
        apply_border_font(cell, BOLD, fill, CENTER, num)
        apply_border_font(ws.cell(r, 3, unit), NORMAL, WHITE, CENTER)
        apply_border_font(ws.cell(r, 4, note), NORMAL, WHITE)

    ws["A19"] = "怎麼買比較不虧"
    ws["A19"].font = H2_FONT
    tips = [
        "1. 先比 Apex / Ezi / Omega / GO / JUCY 的「含 Super／Ultra Cover」總價，不要只看車資。",
        "2. 南島一定要確認玻璃與輪胎有沒有包含；碎石路彈石很常見。",
        "3. 第三方（RentalCover 等）日費較低，但出事要先墊自負額再理賠，chill 旅程不建議。",
        "4. 信用卡租車險常常排除紐澳、或排除單一車輛事故／玻璃，不要假設有保。",
        "5. CHC–CHC 來回，沒有單程調車費。不要皇后鎮還車。",
        "6. 18 天全險大約是車資的 50–55%。貴，但相對一次刮傷／擋風玻璃動輒 NZ$1,500–3,500，划算。",
    ]
    for i, t in enumerate(tips):
        ws.cell(20 + i, 1, t)
        ws.merge_cells(start_row=20 + i, start_column=1, end_row=20 + i, end_column=4)
        ws.cell(20 + i, 1).alignment = WRAP
        ws.row_dimensions[20 + i].height = 28
    set_widths(ws, [22, 22, 10, 72])
    return ws


def add_sheet_activities(wb):
    ws = wb.create_sheet("05_活動")
    ws["A1"] = "這次有排進行程的活動｜官網價（一人）"
    ws["A1"].font = TITLE_FONT
    headers = ["日", "活動", "一人 NZD", "兩人 NZD", "兩人 TWD", "官網／備註"]
    for i, h in enumerate(headers, 1):
        ws.cell(2, i, h)
    style_header(ws, 2, 6)
    acts = [
        ("D3 4/19", "凱庫拉觀鯨 Ocean Cabin", 185, "https://whalewatch.co.nz/ 價至 2027/9/30。建議週一 10:30。"),
        ("D4 4/20", "漢默泉泡湯（可選）", 40, "中途休息，不必過夜。官網約 NZ$38–42。"),
        ("D6 4/22", "Franz Josef heli-hike", 899, "官網至 2027/9/30。4/23 當備援。"),
        ("D12 4/28", "米佛遊船（自駕＋船）", 188, "Mitre Peak／Cruise Milford 約 179–188。訂 11:10 或 13:30。"),
        ("D14 4/30", "庫克山 Glacier Explorers", 219, "2026/10/1 起 NZ$219。不要訂成 Tasman heli-hike。"),
        ("D16 5/2", "Dark Sky 約翰山 Summit", 239, "官網 219–239。可改 Crater NZ$129。"),
    ]
    for i, (day, name, price, note) in enumerate(acts):
        r = 3 + i
        fill = LIGHT if i % 2 else WHITE
        apply_border_font(ws.cell(r, 1, day), NORMAL, fill, CENTER)
        apply_border_font(ws.cell(r, 2, name), BOLD, fill)
        apply_border_font(ws.cell(r, 3, price), NORMAL, YELLOW, CENTER, NZD)
        ws.cell(r, 4, f"=C{r}*'01_總覽'!$B$4")
        apply_border_font(ws.cell(r, 4), NORMAL, fill, CENTER, NZD)
        ws.cell(r, 5, f"=D{r}*'01_總覽'!$B$5")
        apply_border_font(ws.cell(r, 5), NORMAL, fill, CENTER, TWD)
        apply_border_font(ws.cell(r, 6, note), NORMAL, fill)
    r = 9
    apply_border_font(ws.cell(r, 1, "合計"), BOLD, SECTION)
    apply_border_font(ws.cell(r, 2), BOLD, SECTION)
    ws.cell(r, 3, "=SUM(C3:C8)")
    apply_border_font(ws.cell(r, 3), BOLD, SECTION, CENTER, NZD)
    ws.cell(r, 4, "=SUM(D3:D8)")
    apply_border_font(ws.cell(r, 4), BOLD, SECTION, CENTER, NZD)
    ws.cell(r, 5, "=D9*'01_總覽'!$B$5")
    apply_border_font(ws.cell(r, 5), BOLD, SECTION, CENTER, TWD)
    apply_border_font(ws.cell(r, 6, "漢默若不去，把 D4 活動改 0"), NORMAL, SECTION)

    ws["A11"] = "這次故意沒排、想加再加"
    ws["A11"].font = H2_FONT
    extras = [
        ("蒂阿瑙螢火蟲洞", 145, "D11 晚上。累了就睡。"),
        ("奧瑪魯小藍企鵝", 70, "這條 chill 線不繞東岸。若很想看，5/3 改阿卡羅阿 Pohatu。"),
        ("隱士飯店山景 1 晚", 340, "普卡基已能看庫克山。只想住一次再把 D14 改住隱士。"),
    ]
    headers2 = ["可選", "一人 NZD", "怎麼加"]
    for i, h in enumerate(headers2, 1):
        ws.cell(12, i, h)
    style_header(ws, 12, 3)
    for i, (name, price, how) in enumerate(extras):
        r = 13 + i
        apply_border_font(ws.cell(r, 1, name), NORMAL, WHITE)
        apply_border_font(ws.cell(r, 2, price), NORMAL, WHITE, CENTER, NZD)
        apply_border_font(ws.cell(r, 3, how), NORMAL, WHITE)
    set_widths(ws, [22, 36, 14, 14, 14, 62])
    return ws


def add_sheet_copy(wb):
    ws = wb.create_sheet("06_可複製")
    ws["A1"] = "可全選複製到 Google 試算表"
    ws["A1"].font = TITLE_FONT
    headers = ["日", "日期", "過夜", "車程", "公里", "行程摘要", "活動",
               "活動NZD", "住宿NZD", "餐食NZD", "油錢NZD", "租車NZD", "當天NZD"]
    for i, h in enumerate(headers, 1):
        ws.cell(2, i, h)
    style_header(ws, 2, 13)
    for i, d in enumerate(DAYS):
        r = 3 + i
        day, date, dow, stay, drive, km, daytime, activity, act, hotel, food, fuel, tip, note, risk = d
        fill = ORANGE if risk else WHITE
        for c, v in enumerate([day, f"{date} {dow}", stay, drive, km, daytime, activity], 1):
            apply_border_font(ws.cell(r, c, v), NORMAL, fill, WRAP if c in (4, 6) else CENTER, INT if c == 5 else None)
        ws.cell(r, 8, f"='02_每日行程'!I{r}")
        ws.cell(r, 9, f"='02_每日行程'!J{r}")
        ws.cell(r, 10, f"='02_每日行程'!K{r}")
        ws.cell(r, 11, f"='02_每日行程'!L{r}")
        ws.cell(r, 12, f"='02_每日行程'!M{r}")
        ws.cell(r, 13, f"='02_每日行程'!N{r}")
        for c in range(8, 14):
            apply_border_font(ws.cell(r, c), NORMAL, YELLOW if c <= 11 else fill, CENTER, NZD)
        ws.row_dimensions[r].height = 36
    set_widths(ws, [6, 14, 16, 28, 8, 52, 28, 12, 12, 12, 12, 12, 12])
    ws.freeze_panes = "A3"
    return ws


def add_sheet_help(wb):
    ws = wb.create_sheet("00_使用說明", 0)
    ws["A1"] = "怎麼用這份表"
    ws["A1"].font = TITLE_FONT
    lines = [
        "1. 先改 01_總覽 的黃色格子：實際機票、匯率、租車報價。",
        "2. 02_每日行程 的活動／住宿／餐食／油錢也是黃底，可依訂房改。",
        "3. 橘色列是長途或看天氣的日子：4/20 西岸、4/22 冰川、4/24 Haast、4/28 米佛、4/29 回麥肯齊。",
        "4. 班機：2027/4/15 23:55 台北出發，2027/4/17 凌晨到基督城；2027/5/4 15:00 基督城回。",
        "5. 下載：GitHub 檔案頁按 Download raw file。兩個 xlsx 是同一本。",
    ]
    for i, line in enumerate(lines):
        ws.cell(3 + i, 1, line)
        ws.cell(3 + i, 1).alignment = WRAP
        ws.row_dimensions[3 + i].height = 22
    set_widths(ws, [110])
    return ws


def write_csvs():
    daily_path = OUT_DIR / "每日行程花費.csv"
    copy_path = OUT_DIR / "可複製_每日與總表.csv"
    with daily_path.open("w", encoding="utf-8") as f:
        f.write("日,日期,星期,過夜,車程,公里,白天行程,指定活動,活動兩人NZD,住宿兩人NZD,餐食兩人NZD,油錢NZD,備註\n")
        for d in DAYS:
            day, date, dow, stay, drive, km, daytime, activity, act, hotel, food, fuel, tip, note, risk = d
            flag = "高風險," if risk else ""
            daytime = daytime.replace(",", "，")
            activity = activity.replace(",", "，")
            f.write(
                f"{day},{date},{dow},{stay},{drive},{km},{daytime},{activity},"
                f"{act},{hotel},{food},{fuel},{flag}{tip} {note}\n"
            )
    with copy_path.open("w", encoding="utf-8") as f:
        f.write("【表A】每日（兩人 NZD）\n")
        f.write("日,日期,過夜,活動NZD,住宿NZD,餐食NZD,油錢NZD\n")
        for d in DAYS:
            day, date, dow, stay, drive, km, daytime, activity, act, hotel, food, fuel, tip, note, risk = d
            f.write(f"{day},{date} {dow},{stay},{act},{hotel},{food},{fuel}\n")
        f.write("【表B】總表請看 Excel 01_總覽（公式連動）\n")


def main():
    wb = Workbook()
    default = wb.active
    wb.remove(default)
    add_sheet_help(wb)
    add_sheet_overview(wb)
    add_sheet_daily(wb)
    add_sheet_stays(wb)
    add_sheet_car(wb)
    add_sheet_activities(wb)
    add_sheet_copy(wb)
    write_csvs()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    Path("/opt/cursor/artifacts").mkdir(parents=True, exist_ok=True)
    for path in FILES:
        path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(path)
        print("wrote", path)


if __name__ == "__main__":
    main()

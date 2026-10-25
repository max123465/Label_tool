#!/usr/bin/env python3
"""Draw the chill South Island driving map (PNG + SVG)."""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

DIR = Path(__file__).resolve().parent
COAST_PATH = DIR / "south_island_coast.json"
PNG_PATH = DIR / "south_island_route_map.png"
SVG_PATH = DIR / "south_island_route_map.svg"
ARTIFACT = Path("/opt/cursor/artifacts/south_island_route_map.png")
FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"

# Soft print palette — land / sea / route
OCEAN = (214, 226, 232)
LAND = (236, 227, 210)
LAKE = (168, 196, 208)
COAST = (78, 92, 99)
ROUTE = (184, 78, 32)
SIDE = (47, 99, 112)
INK = (28, 48, 58)
MUTED = (90, 106, 114)
OVERNIGHT = (28, 48, 58)
PAPER = (246, 242, 235)
WHITE = (255, 255, 255)

LAKES = {
    "Te Anau": [
        (167.70, -45.08), (167.82, -45.10), (167.83, -45.28),
        (167.75, -45.42), (167.66, -45.31), (167.68, -45.16),
    ],
    "Wakatipu": [
        (168.62, -45.02), (168.76, -45.03), (168.73, -45.18),
        (168.71, -45.34), (168.63, -45.33), (168.54, -45.16),
    ],
    "Wanaka": [
        (168.99, -44.54), (169.22, -44.57), (169.20, -44.73),
        (169.08, -44.76), (168.97, -44.66),
    ],
    "Pukaki": [
        (170.13, -43.91), (170.23, -43.91), (170.26, -44.20),
        (170.16, -44.23),
    ],
    "Tekapo": [
        (170.46, -43.87), (170.53, -43.87), (170.54, -44.03),
        (170.47, -44.04),
    ],
}

LAT_REF = -43.8
LON0, LON1 = 166.15, 174.55
LAT0, LAT1 = -46.95, -40.25
W, H = 1680, 2280
PAD = (70, 200, 210, 210)  # L T R B

# Overnight stays and day stops: lon, lat, label, kind, label offset
STOPS = [
    ("chc", 172.6362, -43.5321, "基督城", "overnight", 18, -8, "4/17、5/3"),
    ("kai", 173.6814, -42.4008, "凱庫拉", "overnight", 16, -6, "4/18–19 賞鯨"),
    ("han", 172.8286, -42.5227, "漢默泉", "pass", 16, 10, "4/20 過路泡湯"),
    ("hok", 170.9667, -42.7167, "霍基蒂卡", "overnight", -122, -10, "4/20"),
    ("fra", 170.1819, -43.3881, "弗蘭茲", "overnight", -108, 16, "4/21–23 冰川"),
    ("wan", 169.1321, -44.7042, "瓦納卡", "pass", 16, -22, "4/24 過路"),
    ("arr", 168.8347, -44.9406, "箭鎮", "overnight", -92, 18, "4/24–26 楓葉"),
    ("tea", 167.7178, -45.4160, "蒂阿瑙", "overnight", -108, 10, "4/27–28"),
    ("mil", 167.9256, -44.6714, "米佛峽灣", "side", -128, -20, "4/28 當日來回"),
    ("oma", 169.9667, -44.4869, "Omarama", "pass", 16, 12, "4/29 可泡湯"),
    ("puk", 170.2093, -44.1683, "普卡基", "overnight", 16, -4, "4/29–30"),
    ("mtc", 170.0963, -43.7340, "庫克山", "side", -18, -28, "4/30 當日來回"),
    ("tek", 170.4774, -44.0047, "蒂卡波", "overnight", 16, 10, "5/1–2 觀星"),
]

MAIN_ROUTE = [
    # CHC → Kaikoura (SH1)
    (172.6362, -43.5321),
    (172.7310, -43.1560),
    (173.2740, -42.8130),
    (173.6814, -42.4008),
    # Kaikoura → Hanmer → Lewis → Hokitika
    (173.2000, -42.5200),
    (172.8286, -42.5227),
    (172.4000, -42.3800),
    (172.1810, -42.3350),
    (171.8650, -42.1160),
    (171.2110, -42.4500),
    (170.9667, -42.7167),
    # West coast south
    (170.8140, -42.8960),
    (170.3650, -43.2620),
    (170.1819, -43.3881),
    (170.0180, -43.4640),
    (169.78, -43.58),
    (169.60, -43.60),
    (169.35, -43.72),
    (169.0560, -43.8810),
    (169.3560, -44.1070),
    (169.2320, -44.2330),
    (169.1321, -44.7042),
    (168.9500, -44.8740),
    (168.8347, -44.9406),
    # Arrowtown → Te Anau
    (168.7390, -45.0180),
    (168.7140, -45.3330),
    (168.6790, -45.4570),
    (168.2480, -45.6670),
    (167.7178, -45.4160),
]

AFTER_MILFORD = [
    (167.7178, -45.4160),
    (168.2480, -45.6670),
    (168.4480, -45.7410),
    (168.5970, -45.5130),
    (168.7140, -45.3330),
    (168.7390, -45.0180),
    (169.2000, -45.0380),
    (169.4270, -44.8470),
    (169.6110, -44.5910),
    (169.9667, -44.4869),
    (170.1010, -44.2580),
    (170.2093, -44.1683),
    (170.4774, -44.0047),
    (170.8290, -44.1010),
    (171.2440, -44.0920),
    (171.7490, -43.9050),
    (172.0230, -43.7560),
    (172.6362, -43.5321),
]

MILFORD = [
    (167.7178, -45.4160),
    (167.8230, -45.2090),
    (167.9810, -44.7720),
    (167.9256, -44.6714),
]

MT_COOK = [
    (170.2093, -44.1683),
    (170.1358, -44.0891),
    (170.0963, -43.7340),
]


def project_raw(lon: float, lat: float) -> tuple[float, float]:
    x = (lon - LON0) * math.cos(math.radians(LAT_REF))
    y = LAT1 - lat
    return x, y


def scale() -> tuple[float, float, float, float]:
    xs, ys = zip(*(project_raw(lon, lat) for lon, lat in ((LON0, LAT0), (LON1, LAT1), (LON0, LAT1), (LON1, LAT0))))
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    pl, pt, pr, pb = PAD
    sx = (W - pl - pr) / (maxx - minx)
    sy = (H - pt - pb) / (maxy - miny)
    s = min(sx, sy)
    ox = pl + ((W - pl - pr) - (maxx - minx) * s) / 2 - minx * s
    oy = pt + ((H - pt - pb) - (maxy - miny) * s) / 2 - miny * s
    return s, ox, oy, s


def xy(lon: float, lat: float, s: float, ox: float, oy: float) -> tuple[float, float]:
    x, y = project_raw(lon, lat)
    return x * s + ox, y * s + oy


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, size=size, index=0)


def polyline(pts: list[tuple[float, float]], s: float, ox: float, oy: float) -> list[tuple[float, float]]:
    return [xy(lon, lat, s, ox, oy) for lon, lat in pts]


def draw_dashed(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]], fill, width: int, dash=18, gap=12):
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy) or 1
        ux, uy = dx / dist, dy / dist
        pos = 0.0
        on = True
        while pos < dist:
            seg = dash if on else gap
            end = min(pos + seg, dist)
            if on:
                draw.line(
                    [(x1 + ux * pos, y1 + uy * pos), (x1 + ux * end, y1 + uy * end)],
                    fill=fill,
                    width=width,
                    joint="curve",
                )
            pos = end
            on = not on


def render_png(coast: list[list[float]], s: float, ox: float, oy: float) -> Image.Image:
    img = Image.new("RGB", (W, H), OCEAN)
    draw = ImageDraw.Draw(img)
    land = [xy(lon, lat, s, ox, oy) for lon, lat in coast]
    draw.polygon(land, fill=LAND, outline=COAST)
    draw.line(land + [land[0]], fill=COAST, width=3, joint="curve")
    for ring in LAKES.values():
        draw.polygon(polyline(ring, s, ox, oy), fill=LAKE, outline=(120, 150, 162))

    main = polyline(MAIN_ROUTE, s, ox, oy) + polyline(AFTER_MILFORD, s, ox, oy)[1:]
    draw.line(main, fill=ROUTE, width=7, joint="curve")
    draw_dashed(draw, polyline(MILFORD, s, ox, oy), SIDE, 5)
    draw_dashed(draw, polyline(MT_COOK, s, ox, oy), SIDE, 5)

    title = font(42)
    sub = font(22)
    body = font(20)
    small = font(16)
    draw.text((70, 48), "紐西蘭南島  chill 自駕路線", font=title, fill=INK)
    draw.text((70, 108), "2027/4/17 凌晨到基督城  ·  5/4 15:00 回程  ·  兩人 17 晚", font=sub, fill=MUTED)

    for _key, lon, lat, label, kind, dx, dy, note in STOPS:
        px, py = xy(lon, lat, s, ox, oy)
        if kind == "overnight":
            draw.ellipse((px - 9, py - 9, px + 9, py + 9), fill=OVERNIGHT, outline=WHITE, width=2)
        else:
            draw.ellipse((px - 7, py - 7, px + 7, py + 7), fill=WHITE, outline=SIDE, width=3)
        draw.text((px + dx, py + dy - 18), label, font=body, fill=INK)
        draw.text((px + dx, py + dy + 6), note, font=small, fill=MUTED)

    # legend
    ly = H - 168
    draw.rectangle((60, ly, W - 60, H - 48), fill=PAPER, outline=COAST, width=1)
    draw.line((90, ly + 38, 170, ly + 38), fill=ROUTE, width=7)
    draw.text((184, ly + 24), "過夜行車線（順時針）", font=small, fill=INK)
    draw_dashed(draw, [(400, ly + 38), (480, ly + 38)], SIDE, 5)
    draw.text((494, ly + 24), "當日來回：米佛、庫克山", font=small, fill=INK)
    draw.ellipse((800, ly + 29, 818, ly + 47), fill=OVERNIGHT, outline=WHITE, width=2)
    draw.text((828, ly + 24), "過夜城鎮", font=small, fill=INK)
    draw.ellipse((980, ly + 29, 996, ly + 45), fill=WHITE, outline=SIDE, width=3)
    draw.text((1008, ly + 24), "過路／一日景點", font=small, fill=INK)
    draw.text(
        (90, ly + 70),
        "路線沿 SH1、Lewis Pass、西岸、Haast、箭鎮、蒂阿瑙、Lindis Pass 回麥肯齊盆地。海岸線簡化自 OpenStreetMap。",
        font=small,
        fill=MUTED,
    )
    return img


def svg_path(pts: list[tuple[float, float]]) -> str:
    return "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def render_svg(coast: list[list[float]], s: float, ox: float, oy: float) -> str:
    land = [xy(lon, lat, s, ox, oy) for lon, lat in coast]
    main = polyline(MAIN_ROUTE, s, ox, oy) + polyline(AFTER_MILFORD, s, ox, oy)[1:]
    mil = polyline(MILFORD, s, ox, oy)
    mtc = polyline(MT_COOK, s, ox, oy)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        f'<rect width="{W}" height="{H}" fill="#d6e2e8"/>',
        f'<path d="{svg_path(land)} Z" fill="#ece3d2" stroke="#4e5c63" stroke-width="3" stroke-linejoin="round"/>',
    ]
    for ring in LAKES.values():
        lake_pts = polyline(ring, s, ox, oy)
        parts.append(
            f'<path d="{svg_path(lake_pts)} Z" fill="#a8c4d0" stroke="#7896a2" stroke-width="1"/>'
        )
    parts += [
        f'<path d="{svg_path(main)}" fill="none" stroke="#b84e20" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>',
        f'<path d="{svg_path(mil)}" fill="none" stroke="#2f6370" stroke-width="5" stroke-dasharray="16 12" stroke-linecap="round"/>',
        f'<path d="{svg_path(mtc)}" fill="none" stroke="#2f6370" stroke-width="5" stroke-dasharray="16 12" stroke-linecap="round"/>',
        '<text x="70" y="78" font-family="WenQuanYi Micro Hei, Noto Sans CJK, sans-serif" font-size="42" fill="#1c303a">紐西蘭南島  chill 自駕路線</text>',
        '<text x="70" y="120" font-family="WenQuanYi Micro Hei, Noto Sans CJK, sans-serif" font-size="22" fill="#5a6a72">2027/4/17 凌晨到基督城  ·  5/4 15:00 回程  ·  兩人 17 晚</text>',
    ]
    for _key, lon, lat, label, kind, dx, dy, note in STOPS:
        px, py = xy(lon, lat, s, ox, oy)
        if kind == "overnight":
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="9" fill="#1c303a" stroke="#fff" stroke-width="2"/>')
        else:
            parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="7" fill="#fff" stroke="#2f6370" stroke-width="3"/>')
        parts.append(
            f'<text x="{px + dx:.1f}" y="{py + dy:.1f}" font-family="WenQuanYi Micro Hei, Noto Sans CJK, sans-serif" font-size="20" fill="#1c303a">{label}</text>'
        )
        parts.append(
            f'<text x="{px + dx:.1f}" y="{py + dy + 22:.1f}" font-family="WenQuanYi Micro Hei, Noto Sans CJK, sans-serif" font-size="15" fill="#5a6a72">{note}</text>'
        )
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    coast = json.loads(COAST_PATH.read_text())
    s, ox, oy, _ = scale()
    img = render_png(coast, s, ox, oy)
    PNG_PATH.parent.mkdir(parents=True, exist_ok=True)
    img.save(PNG_PATH, "PNG", optimize=True)
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    img.save(ARTIFACT, "PNG", optimize=True)
    SVG_PATH.write_text(render_svg(coast, s, ox, oy), encoding="utf-8")
    print("wrote", PNG_PATH)
    print("wrote", SVG_PATH)
    print("wrote", ARTIFACT)


if __name__ == "__main__":
    main()

"""Home-screen icon drawn in code, so no binary assets live in the repo."""

from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw


@lru_cache(maxsize=4)
def png(size: int) -> bytes:
    s = size / 180
    img = Image.new("RGB", (size, size), (15, 118, 110))
    d = ImageDraw.Draw(img)
    left, right, top, bottom = 50 * s, 130 * s, 32 * s, 140 * s
    teeth = 5
    width = (right - left) / teeth
    outline = [(left, top), (right, top), (right, bottom)]
    for i in range(teeth):
        x = right - i * width
        outline += [(x - width / 2, bottom - 9 * s), (x - width, bottom)]
    d.polygon(outline, fill=(255, 255, 255))
    for i, w in enumerate((56, 44, 50, 30)):
        y = top + (20 + i * 17) * s
        d.rounded_rectangle((left + 12 * s, y, left + (12 + w) * s, y + 7 * s), radius=3 * s, fill=(153, 205, 196))
    d.ellipse((104 * s, 102 * s, 146 * s, 144 * s), fill=(251, 191, 36))
    d.text((119 * s, 108 * s), "$", fill=(120, 53, 15))
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()

"""Genera el banner (2560x1440) y el avatar (800x800) del canal en channel/."""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import *  # noqa: F401,F403
from render import Backgrounds, rounded, text_img  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "channel")
os.makedirs(OUT, exist_ok=True)

bgs = Backgrounds(42)
base = bgs.frame("sunset", 0.2).convert("RGBA")

# ---- banner: zona segura central 1546x423
banner = base.resize((2560, 1440), Image.LANCZOS)
title, _ = text_img(CHANNEL_NAME, F_BLACK_IT, 190, grad=(YELLOW, PINK), stroke=10, stroke_fill=(20, 6, 40), glow=PINK)
stars, _ = text_img("★★★★★★", F_BLACK, 70, fill=YELLOW, stroke=4, stroke_fill=(20, 6, 40))
sub, _ = text_img("GUÍAS · NOTICIAS · TRUCOS DE GTA 6", F_XBOLD, 54, fill=WHITE, stroke=4, stroke_fill=(20, 6, 40))
cy = 720
banner.alpha_composite(stars, ((2560 - stars.width) // 2, cy - 230))
banner.alpha_composite(title, ((2560 - title.width) // 2, cy - title.height // 2 - 20))
banner.alpha_composite(sub, ((2560 - sub.width) // 2, cy + 120))
banner.convert("RGB").save(os.path.join(OUT, "banner_2560x1440.png"))

# ---- avatar
av = base.crop((560, 120, 1360, 920)).resize((800, 800), Image.LANCZOS)
d = ImageDraw.Draw(av)
six, _ = text_img("6", F_BLACK_IT, 520, grad=(YELLOW, PINK), stroke=14, stroke_fill=(20, 6, 40), glow=PINK)
av.alpha_composite(six, ((800 - six.width) // 2, (800 - six.height) // 2 - 30))
st, _ = text_img("★★★★★★", F_BLACK, 70, fill=YELLOW, stroke=4, stroke_fill=(20, 6, 40))
av.alpha_composite(st, ((800 - st.width) // 2, 640))
av.convert("RGB").save(os.path.join(OUT, "avatar_800x800.png"))
print("ok")

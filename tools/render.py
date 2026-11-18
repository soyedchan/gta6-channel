"""Renderiza un vídeo completo a partir de su guion YAML.

Uso:  python3 tools/render.py videos/01-hora-de-salida [--preview]

Genera en la carpeta del vídeo:
  video.mp4, miniatura.png, subtitulos.srt, metadatos.md, guion.md
"""
import math
import os
import subprocess
import sys
from functools import lru_cache

import numpy as np
import soundfile as sf
import yaml
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audio  # noqa: E402
from config import *  # noqa: E402,F401,F403

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MX = 140  # margen lateral


# ============================================================ utilidades

@lru_cache(maxsize=None)
def font(path, size):
    return ImageFont.truetype(path, size)


def ease(p):
    p = max(0.0, min(1.0, p))
    return 1 - (1 - p) ** 3


def ease_back(p):
    p = max(0.0, min(1.0, p))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


def lerp(a, b, t):
    return a + (b - a) * t


def mixc(c1, c2, t):
    return tuple(int(lerp(a, b, t)) for a, b in zip(c1, c2))


def vgradient(w, h, stops):
    """stops: lista de (pos 0..1, color). Devuelve Image RGB."""
    ys = np.linspace(0, 1, h)
    arr = np.zeros((h, 3))
    pos = [s[0] for s in stops]
    for ch in range(3):
        arr[:, ch] = np.interp(ys, pos, [s[1][ch] for s in stops])
    img = np.repeat(arr[:, None, :], w, axis=1).astype(np.uint8)
    return Image.fromarray(img, "RGB")


def hgradient(w, h, c1, c2):
    xs = np.linspace(0, 1, w)
    arr = np.stack([np.interp(xs, [0, 1], [c1[i], c2[i]]) for i in range(3)], axis=1)
    img = np.repeat(arr[None, :, :], h, axis=0).astype(np.uint8)
    return Image.fromarray(img, "RGB")


def wrap(text, fnt, maxw):
    words = str(text).split()
    lines, cur = [], ""
    for w_ in words:
        test = (cur + " " + w_).strip()
        if fnt.getlength(test) <= maxw or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def text_img(text, path, size, fill=WHITE, grad=None, maxw=None, align="left",
             stroke=0, stroke_fill=(0, 0, 0), shadow=True, glow=None, spacing=1.12, fit=None):
    """Renderiza texto (multilínea con ajuste) a una imagen RGBA recortada."""
    if fit:  # reduce el tamaño hasta que quepa en `fit` líneas
        while size > 30:
            f = font(path, size)
            if len(wrap(text, f, maxw)) <= fit:
                break
            size -= 6
    f = font(path, size)
    lines = []
    for para in str(text).split("\n"):
        lines += wrap(para, f, maxw) if maxw else [para]
    asc, desc = f.getmetrics()
    lh = int((asc + desc) * spacing)
    widths = [f.getlength(l) for l in lines]
    tw = int(max(widths)) if widths else 1
    pad = 30 + stroke + (24 if glow else 0)
    W_, H_ = tw + pad * 2, lh * len(lines) + pad * 2
    mask = Image.new("L", (W_, H_), 0)
    md = ImageDraw.Draw(mask)
    smask = Image.new("L", (W_, H_), 0)
    sd = ImageDraw.Draw(smask)
    for i, l in enumerate(lines):
        x = pad + {"left": 0, "center": (tw - widths[i]) / 2, "right": tw - widths[i]}[align]
        y = pad + i * lh
        md.text((x, y), l, font=f, fill=255)
        if stroke:
            sd.text((x, y), l, font=f, fill=255, stroke_width=stroke, stroke_fill=255)
    out = Image.new("RGBA", (W_, H_), (0, 0, 0, 0))
    if glow:
        g = (smask if stroke else mask).filter(ImageFilter.GaussianBlur(18))
        gl = Image.new("RGBA", (W_, H_), glow + (0,))
        gl.putalpha(g.point(lambda v: int(v * 0.9)))
        out = Image.alpha_composite(out, gl)
    if shadow:
        sh = (smask if stroke else mask).filter(ImageFilter.GaussianBlur(6))
        shl = Image.new("RGBA", (W_, H_), (0, 0, 0, 0))
        shl.paste((0, 0, 0, 255), (6, 8), sh.point(lambda v: int(v * 0.7)))
        out = Image.alpha_composite(out, shl)
    if stroke:
        st = Image.new("RGBA", (W_, H_), stroke_fill + (0,))
        st.putalpha(smask)
        out = Image.alpha_composite(out, st)
    if grad:
        fill_img = vgradient(W_, H_, [(0.25, grad[0]), (0.8, grad[1])]).convert("RGBA")
    else:
        fill_img = Image.new("RGBA", (W_, H_), fill + (255,))
    fill_img.putalpha(mask)
    out = Image.alpha_composite(out, fill_img)
    bbox = out.getbbox() or (0, 0, 1, 1)
    out = out.crop(bbox)
    return out, lh


def rounded(w, h, r=26, fill=(22, 14, 52, 225), outline=None, width=3, accent=None):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w - 1, h - 1), r, fill=fill, outline=outline, width=width)
    if accent:
        bar = Image.new("RGBA", (10, h), accent + (255,))
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255)
        layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        layer.paste(bar, (0, 0))
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), m))
        img = Image.alpha_composite(img, layer)
    return img


def badge_circle(label, d=86, c1=PINK, c2=ORANGE, size=44):
    img = Image.new("RGBA", (d, d), (0, 0, 0, 0))
    g = vgradient(d, d, [(0, c1), (1, c2)]).convert("RGBA")
    m = Image.new("L", (d, d), 0)
    ImageDraw.Draw(m).ellipse((0, 0, d - 1, d - 1), fill=255)
    g.putalpha(m)
    img = Image.alpha_composite(img, g)
    t, _ = text_img(label, F_BLACK, size, shadow=False)
    img.alpha_composite(t, ((d - t.width) // 2, (d - t.height) // 2))
    return img


def compose(base, items):
    """items: lista de (img, (x,y)). Pega sobre RGBA."""
    for im, (x, y) in items:
        base.alpha_composite(im, (int(x), int(y)))
    return base


# ============================================================ fondos animados

def _palm(h, flip=False, color=(8, 4, 20, 255)):
    w = int(h * 0.9)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # tronco curvado
    top = (w * 0.55, h * 0.18)
    for i in range(60):
        t = i / 59
        x = lerp(w * 0.35, top[0], t) + math.sin(t * 2.6) * w * 0.08
        y = lerp(h, top[1], t)
        r = lerp(h * 0.03, h * 0.014, t)
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)
    cx, cy = top[0] + math.sin(2.6) * w * 0.08, top[1]
    # hojas
    for ang in [-170, -140, -110, -70, -40, -10, 15, 200]:
        a = math.radians(ang)
        L = h * 0.42
        pts_up, pts_dn = [], []
        for i in range(20):
            t = i / 19
            px = cx + math.cos(a) * L * t
            py = cy + math.sin(a) * L * t + (L * 0.55) * t * t
            thick = h * 0.035 * math.sin(math.pi * min(1, t * 1.1)) + 1
            nx, ny = -math.sin(a), math.cos(a)
            pts_up.append((px + nx * thick, py + ny * thick))
            pts_dn.append((px - nx * thick, py - ny * thick))
        d.polygon(pts_up + pts_dn[::-1], fill=color)
    if flip:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
    return img


class Backgrounds:
    HZ = 640  # horizonte del atardecer

    def __init__(self, seed=0):
        rng = np.random.default_rng(seed)
        self.rng_seed = seed
        # ---- atardecer synthwave
        sky = vgradient(W, H, [(0, (16, 6, 48)), (0.32, (88, 22, 120)), (0.52, (220, 60, 120)),
                               (self.HZ / H, (255, 150, 70)), (self.HZ / H + 0.001, (24, 8, 46)),
                               (1, (8, 4, 22))]).convert("RGBA")
        d = ImageDraw.Draw(sky)
        for _ in range(140):
            x, y = rng.integers(0, W), rng.integers(0, int(self.HZ * 0.6))
            b = int(rng.integers(120, 255))
            d.point((int(x), int(y)), fill=(b, b, b, 255))
        # sol con franjas
        R = 250
        sun = vgradient(2 * R, 2 * R, [(0, YELLOW), (0.55, ORANGE), (1, PINK)]).convert("RGBA")
        m = Image.new("L", (2 * R, 2 * R), 0)
        md = ImageDraw.Draw(m)
        md.ellipse((0, 0, 2 * R - 1, 2 * R - 1), fill=255)
        for i in range(7):
            y0 = int(R * 1.0 + i * i * 4.2 + i * 14)
            md.rectangle((0, y0, 2 * R, y0 + 4 + i * 2), fill=0)
        sun.putalpha(m)
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse((960 - R - 120, self.HZ - R - 120 - 60, 960 + R + 120, self.HZ + R + 120 - 60),
                                     fill=(255, 90, 120, 120))
        glow = glow.filter(ImageFilter.GaussianBlur(70))
        sky = Image.alpha_composite(sky, glow)
        sunlayer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sunlayer.alpha_composite(sun, (960 - R, self.HZ - 2 * R + 60))
        cut = Image.new("L", (W, H), 0)
        ImageDraw.Draw(cut).rectangle((0, 0, W, self.HZ), fill=255)
        sunlayer.putalpha(ImageChops.multiply(sunlayer.getchannel("A"), cut))
        sky = Image.alpha_composite(sky, sunlayer)
        # montañas lejanas
        mt = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        pts = [(0, self.HZ)]
        x = 0
        while x < W:
            x += int(rng.integers(60, 160))
            pts.append((x, self.HZ - int(rng.integers(20, 110))))
        pts += [(W, self.HZ), (0, self.HZ)]
        ImageDraw.Draw(mt).polygon(pts, fill=(60, 14, 70, 200))
        sky = Image.alpha_composite(sky, mt)
        self.sunset = sky.convert("RGB")
        self.sunset_dim = Image.eval(self.sunset, lambda v: int(v * 0.42))
        self.palms = []
        for (h, x, flip) in [(900, -120, False), (700, 160, False), (880, W - 700, True), (640, W - 900, True)]:
            p = _palm(h, flip)
            self.palms.append((p, (x, H - h + 40)))
        self.palm_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for p, pos in self.palms:
            self.palm_layer.alpha_composite(p, pos)
        self.palm_rgb = self.palm_layer.convert("RGB")
        self.palm_mask = self.palm_layer.getchannel("A")
        self.palm_rgb_dim = Image.eval(self.palm_rgb, lambda v: int(v * 0.42))

        # ---- ciudad nocturna
        cy = 760
        city = vgradient(W, H, [(0, (6, 4, 24)), (0.55, (50, 16, 84)), (cy / H, (120, 30, 110)),
                                (cy / H + 0.001, (10, 6, 30)), (1, (4, 2, 14))]).convert("RGBA")
        d = ImageDraw.Draw(city)
        for _ in range(120):
            x, y = rng.integers(0, W), rng.integers(0, 420)
            b = int(rng.integers(100, 230))
            d.point((int(x), int(y)), fill=(b, b, b, 255))
        sk = Image.new("RGBA", (W, cy), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sk)
        self.windows = []
        x = -20
        while x < W:
            bw = int(rng.integers(50, 150))
            bh = int(rng.integers(120, 470)) if rng.random() > 0.15 else int(rng.integers(480, 600))
            col = (int(rng.integers(12, 26)), int(rng.integers(8, 18)), int(rng.integers(30, 52)), 255)
            sd.rectangle((x, cy - bh, x + bw, cy), fill=col)
            if rng.random() < 0.3:
                sd.rectangle((x + bw // 2 - 2, cy - bh - 50, x + bw // 2 + 2, cy - bh), fill=col)
                sd.ellipse((x + bw // 2 - 4, cy - bh - 56, x + bw // 2 + 4, cy - bh - 48), fill=RED + (255,))
            for wy in range(cy - bh + 14, cy - 10, 22):
                for wx in range(x + 8, x + bw - 10, 16):
                    if rng.random() < 0.28:
                        c = [(255, 210, 120), (120, 230, 255), (255, 120, 200)][int(rng.integers(0, 3)) if rng.random() < 0.3 else 0]
                        sd.rectangle((wx, wy, wx + 7, wy + 11), fill=c + (255,))
                        self.windows.append((wx, wy, col))
            x += bw + int(rng.integers(2, 14))
        city.alpha_composite(sk, (0, 0))
        refl = sk.transpose(Image.FLIP_TOP_BOTTOM).filter(ImageFilter.GaussianBlur(4))
        refl.putalpha(refl.getchannel("A").point(lambda v: int(v * 0.35)))
        city.alpha_composite(refl.crop((0, 0, W, H - cy)), (0, cy))
        self.city = Image.eval(city.convert("RGB"), lambda v: int(v * 0.62))

        # ---- bokeh
        self.bokeh_base = vgradient(W, H, [(0, (12, 6, 34)), (0.6, (34, 10, 60)), (1, (8, 4, 20))])
        self.bokeh = [(rng.uniform(0, 480), rng.uniform(0, 270), rng.uniform(10, 42), rng.uniform(-6, 6),
                       rng.uniform(-3, 3), [PINK, CYAN, PURPLE, ORANGE][int(rng.integers(0, 4))],
                       rng.uniform(0.25, 0.6)) for _ in range(26)]

    def frame(self, kind, t):
        if kind in ("sunset", "sunset_dim"):
            dim = kind == "sunset_dim"
            img = (self.sunset_dim if dim else self.sunset).copy()
            d = ImageDraw.Draw(img)
            col = (110, 24, 90) if dim else (255, 60, 170)
            phase = (t * 0.6) % 1.0
            N = 14
            for k in range(N):
                p = (k + phase) / N
                y = self.HZ + (H - self.HZ) * p ** 2.4
                d.line((0, y, W, y), fill=col, width=max(1, int(1 + p * 3)))
            for i in range(-14, 15):
                xb = 960 + i * 260
                d.line((960 + i * 18, self.HZ, xb, H), fill=col, width=2)
            img.paste(self.palm_rgb_dim if dim else self.palm_rgb, (0, 0), self.palm_mask)
            return img
        if kind == "city":
            img = self.city.copy()
            d = ImageDraw.Draw(img)
            rng = np.random.default_rng(int(t * 3))
            for i in rng.integers(0, max(1, len(self.windows)), 25):
                wx, wy, col = self.windows[int(i)]
                d.rectangle((wx, wy, wx + 7, wy + 11), fill=tuple(int(c * 0.62) for c in col[:3]))
            rng2 = np.random.default_rng(int(t * 8))
            for _ in range(40):
                y = int(rng2.integers(770, H))
                x = int(rng2.integers(0, W))
                c = [(150, 40, 110), (30, 120, 150), (150, 110, 50)][int(rng2.integers(0, 3))]
                d.line((x, y, x + int(rng2.integers(20, 90)), y), fill=c, width=2)
            return img
        # bokeh
        small = Image.new("RGB", (480, 270), (0, 0, 0))
        d = ImageDraw.Draw(small)
        for (x, y, r, vx, vy, c, a) in self.bokeh:
            px = (x + vx * t) % 560 - 40
            py = (y + vy * t + 8 * math.sin(t * 0.5 + x)) % 330 - 30
            col = tuple(int(v * a) for v in c)
            d.ellipse((px - r, py - r, px + r, py + r), fill=col)
        small = small.filter(ImageFilter.GaussianBlur(5))
        big = small.resize((W, H), Image.BILINEAR)
        return ImageChops.screen(self.bokeh_base, big)


# ============================================================ elementos

class El:
    def __init__(self, img, x, y, t_in, anim="up", dur=0.5, t_out=None):
        self.rgb = img.convert("RGB")
        self.a = img.getchannel("A")
        self.w, self.h = img.size
        self.x, self.y = int(x), int(y)
        self.t_in, self.anim, self.dur, self.t_out = t_in, anim, dur, t_out
        self.src = img

    def draw(self, frame, t):
        if t < self.t_in:
            return
        p = (t - self.t_in) / self.dur
        alpha = ease(p)
        if self.t_out is not None and t > self.t_out:
            alpha *= 1 - ease((t - self.t_out) / 0.3)
            if alpha <= 0.01:
                return
        x, y = self.x, self.y
        rgb, a = self.rgb, self.a
        if p < 1:
            e = ease(p)
            if self.anim == "up":
                y += int((1 - e) * 60)
            elif self.anim == "left":
                x -= int((1 - e) * 120)
            elif self.anim == "right":
                x += int((1 - e) * 120)
            elif self.anim == "down":
                y -= int((1 - e) * 60)
            elif self.anim == "pop":
                s = max(0.05, ease_back(p) * 0.4 + 0.6 if p < 1 else 1)
                s = 0.6 + 0.4 * ease_back(p)
                nw, nh = max(1, int(self.w * s)), max(1, int(self.h * s))
                im = self.src.resize((nw, nh), Image.BILINEAR)
                rgb, a = im.convert("RGB"), im.getchannel("A")
                x += (self.w - nw) // 2
                y += (self.h - nh) // 2
        if alpha < 0.999:
            a = a.point(lambda v, k=alpha: int(v * k))
        frame.paste(rgb, (x, y), a)


class Dyn:
    """Elemento dinámico: fn(frame, t) llamado desde t_in."""

    def __init__(self, fn, t_in=0):
        self.fn, self.t_in = fn, t_in

    def draw(self, frame, t):
        if t >= self.t_in:
            self.fn(frame, t)


# ============================================================ escenas

def heading(sc, t0, accent=PINK):
    out = []
    y = 92
    if sc.get("kicker"):
        k, _ = text_img(sc["kicker"].upper(), F_XBOLD, 34, fill=accent, shadow=False)
        out.append(El(k, MX - 30, y - 30, t0, "left"))
        y += 40
    if sc.get("heading"):
        h, _ = text_img(sc["heading"], F_BLACK_IT, 78, maxw=W - 2 * MX, fit=1)
        out.append(El(h, MX - 30, y - 30, t0 + 0.08, "left"))
        bar = hgradient(220, 8, accent, ORANGE).convert("RGBA")
        out.append(El(bar, MX, y + h.height - 46, t0 + 0.2, "left"))
        y += h.height - 10
    return out, y + 30


def scene_title(sc, ts, t0, dur=0):
    els = []
    if sc.get("kicker"):
        k, _ = text_img(sc["kicker"].upper(), F_XBOLD, 40, shadow=False)
        pill = rounded(k.width + 30, k.height + 6, r=(k.height + 6) // 2, fill=PINK + (255,))
        pill.alpha_composite(k, (15 - 30 + 30, 3))
        els.append(El(pill, (W - pill.width) / 2, 230, t0, "down"))
    title, _ = text_img(sc["title"], F_BLACK_IT, sc.get("size", 150), grad=(YELLOW, PINK), maxw=1660,
                        align="center", stroke=7, stroke_fill=(20, 6, 40), glow=PINK, fit=2)
    els.append(El(title, (W - title.width) / 2, 540 - title.height / 2, t0 + 0.15, "pop", 0.6))
    if sc.get("subtitle"):
        s, _ = text_img(sc["subtitle"], F_BOLD, 50, maxw=1500, align="center", fill=WHITE, stroke=3,
                        stroke_fill=(20, 6, 40))
        els.append(El(s, (W - s.width) / 2, 540 + title.height / 2 + 10, ts[min(1, len(ts) - 1)] if len(ts) > 1 else t0 + 0.6, "up"))
    return els


def item_card(text, sub, idx, width, check=False, accent=CYAN):
    f_main = 50 if not sub else 46
    t, _ = text_img(text, F_BOLD, f_main, maxw=width - 200, shadow=False)
    s = None
    if sub:
        s, _ = text_img(sub, F_SEMI, 34, fill=SOFT, maxw=width - 200, shadow=False)
    inner = t.height + (s.height + 8 if s else 0)
    h = max(124, inner + 44)
    card = rounded(width, h, fill=(20, 12, 48, 228), outline=(80, 50, 140, 255), width=2, accent=accent)
    if check:
        b = Image.new("RGBA", (72, 72), (0, 0, 0, 0))
        ImageDraw.Draw(b).rounded_rectangle((2, 2, 70, 70), 16, outline=accent + (255,), width=6)
    else:
        b = badge_circle(str(idx), 82)
    card.alpha_composite(b, (40, (h - b.height) // 2))
    ty = (h - inner) // 2
    card.alpha_composite(t, (150, ty))
    if s:
        card.alpha_composite(s, (150, ty + t.height + 8))
    return card


def tick_img(color=GREEN):
    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line((18, 52, 42, 76, 88, 16), fill=color + (255,), width=14, joint="curve")
    return img


def reveal_times(n, ts, sc, t0, dur):
    at = sc.get("at")
    if at:
        return [ts[min(a, len(ts) - 1)] + 0.1 for a in at]
    if len(ts) >= n + 1:
        return [ts[i + 1] + 0.1 for i in range(n)]
    if len(ts) == n:
        return [ts[i] + 0.15 for i in range(n)]
    span = dur * 0.75
    return [t0 + 0.6 + i * span / max(1, n) for i in range(n)]


def scene_list(sc, ts, t0, dur, check=False):
    els, y = heading(sc, t0, CYAN if check else PINK)
    items = sc["items"]
    times = reveal_times(len(items), ts, sc, t0, dur)
    cards = []
    for i, it in enumerate(items):
        text, sub = (it, None) if isinstance(it, str) else (it["text"], it.get("sub"))
        cards.append(item_card(text, sub, i + 1, W - 2 * MX, check=check,
                               accent=[CYAN, PINK, ORANGE, YELLOW, PURPLE, GREEN][i % 6]))
    gap = 22
    total = sum(c.height for c in cards) + gap * (len(cards) - 1)
    avail = H - 80 - y
    if total > avail:
        gap = 10
        total = sum(c.height for c in cards) + gap * (len(cards) - 1)
    yy = y + max(0, (avail - total) // 2)
    for i, c in enumerate(cards):
        els.append(El(c, MX, yy, times[i], "left"))
        if check:
            tk = tick_img()
            els.append(El(tk, MX + 40 - 12, yy + (c.height - 72) // 2 - 18, times[i] + 0.35, "pop", 0.4))
        yy += c.height + gap
    return els


def scene_stat(sc, ts, t0, dur):
    els, y = heading(sc, t0, ORANGE)
    val = str(sc["value"])
    t_val = ts[min(sc.get("value_at", 0), len(ts) - 1)] + 0.1
    size = sc.get("size", 290)
    big, _ = text_img(val, F_BLACK_IT, size, grad=(YELLOW, PINK), stroke=8, stroke_fill=(20, 6, 40), glow=PINK)
    cy = 470 if sc.get("heading") else 420
    bx, by = (W - big.width) / 2, cy - big.height / 2
    count = sc.get("count")
    if count:
        num = float(count)
        prefix, suffix = sc.get("prefix", ""), sc.get("suffix", "")
        cache = {}

        def draw(frame, t, num=num, prefix=prefix, suffix=suffix):
            p = ease((t - t_val) / 1.3)
            v = int(round(num * p))
            if v not in cache:
                cache[v] = text_img(f"{prefix}{v}{suffix}", F_BLACK_IT, size, grad=(YELLOW, PINK), stroke=8,
                                    stroke_fill=(20, 6, 40), glow=PINK)[0]
            im = cache[v]
            frame.paste(im.convert("RGB"), (int((W - im.width) / 2), int(cy - im.height / 2)), im.getchannel("A"))
        els.append(Dyn(draw, t_val))
    else:
        els.append(El(big, bx, by, t_val, "pop", 0.6))
    ly = cy + big.height / 2 + 10
    if sc.get("label"):
        l, _ = text_img(sc["label"], F_BLACK, 62, maxw=1600, align="center")
        els.append(El(l, (W - l.width) / 2, ly, ts[min(sc.get("label_at", 0), len(ts) - 1)] + 0.5, "up"))
        ly += l.height
    if sc.get("detail"):
        dd, _ = text_img(sc["detail"], F_SEMI, 40, fill=SOFT, maxw=1500, align="center")
        els.append(El(dd, (W - dd.width) / 2, ly, ts[min(sc.get("detail_at", 1), len(ts) - 1)] + 0.2, "up"))
    return els


def scene_table(sc, ts, t0, dur):
    els, y = heading(sc, t0, CYAN)
    rows = sc["rows"]
    times = reveal_times(len(rows), ts, sc, t0, dur)
    n = len(rows)
    avail = H - 70 - y
    rh = min(112, (avail - 12 * (n - 1)) // n)
    fs = 46 if rh >= 96 else 38
    yy = y + max(0, (avail - (rh * n + 12 * (n - 1))) // 2)
    for i, r in enumerate(rows):
        left, right = r[0], r[1]
        hl = len(r) > 2 and r[2]
        card = rounded(W - 2 * MX, rh, r=20, fill=((60, 16, 70, 235) if hl else (20, 12, 48, 225)),
                       outline=(PINK + (255,)) if hl else (70, 46, 130, 255), width=3 if hl else 2)
        lt, _ = text_img(left, F_BOLD, fs, shadow=False, maxw=1000, fit=1)
        rt, _ = text_img(right, F_BLACK, fs, fill=YELLOW if hl else CYAN, shadow=False, maxw=820, fit=1)
        card.alpha_composite(lt, (30, (rh - lt.height) // 2))
        card.alpha_composite(rt, (card.width - rt.width - 30, (rh - rt.height) // 2))
        els.append(El(card, MX, yy, times[i], "up"))
        yy += rh + 12
    return els


def _compare_layout(col, acc, cw, fs):
    parts, yy = [], 34
    tt, _ = text_img(col["title"], F_BLACK_IT, 64, fill=acc, maxw=cw - 60, fit=1, shadow=False)
    parts.append((tt, ((cw - tt.width) // 2, yy)))
    yy += tt.height + 28
    if col.get("price"):
        pt, _ = text_img(col["price"], F_BLACK, 80, fill=YELLOW, shadow=False)
        parts.append((pt, ((cw - pt.width) // 2, yy)))
        yy += pt.height + 36
    dot = Image.new("RGBA", (18, 18), (0, 0, 0, 0))
    ImageDraw.Draw(dot).ellipse((0, 0, 17, 17), fill=acc + (255,))
    for it in col["items"]:
        bt, _ = text_img(it, F_SEMI, fs, maxw=cw - 120, shadow=False)
        parts.append((dot, (44, yy + fs // 4)))
        parts.append((bt, (80, yy)))
        yy += bt.height + int(fs * 0.7)
    return parts, yy + 10


def scene_compare(sc, ts, t0, dur):
    els, y = heading(sc, t0, PINK)
    cols = sc["columns"]
    times = reveal_times(len(cols), ts, sc, t0, dur)
    cw = (W - 2 * MX - 60) // 2
    avail = H - 80 - y
    for fs in (46, 42, 38, 34, 30):
        lays = [_compare_layout(c, [CYAN, PINK][i % 2], cw, fs) for i, c in enumerate(cols)]
        ch = max(h for _, h in lays)
        if ch <= avail:
            break
    ch = min(ch, avail)
    top = y + (avail - ch) // 2
    for i, (parts, _) in enumerate(lays):
        acc = [CYAN, PINK][i % 2]
        card = rounded(cw, ch, r=30, fill=(20, 12, 48, 232), outline=acc + (255,), width=4)
        for im, pos in parts:
            if pos[1] + im.height <= ch:
                card.alpha_composite(im, pos)
        els.append(El(card, MX + i * (cw + 60), top, times[i], "left" if i == 0 else "right"))
    if sc.get("vs", True) and len(cols) == 2:
        vs = badge_circle("VS", 120, YELLOW, ORANGE, 52)
        els.append(El(vs, (W - 120) / 2, top + ch / 2 - 60, times[1] + 0.3, "pop", 0.45))
    return els


def scene_timeline(sc, ts, t0, dur):
    els, y = heading(sc, t0, ORANGE)
    evs = sc["events"]
    n = len(evs)
    times = reveal_times(n, ts, sc, t0, dur)
    ly = 560
    edge = {2: 420, 3: 300, 4: 240}.get(n, 200)
    x0, x1 = MX + edge, W - MX - edge
    xs = [x0 + (x1 - x0) * (i / (n - 1) if n > 1 else 0.5) for i in range(n)]

    def line(frame, t):
        d = ImageDraw.Draw(frame)
        p = ease((t - t0) / max(0.8, (times[-1] - t0)))
        d.line((x0 - 40, ly, x0 - 40 + (x1 - x0 + 80) * p, ly), fill=(110, 70, 180), width=8)
    els.append(Dyn(line, t0))
    slot = (x1 - x0) / max(1, n - 1) if n > 1 else 800
    for i, ev in enumerate(evs):
        dot = badge_circle("", 46, PINK, ORANGE)
        els.append(El(dot, xs[i] - 23, ly - 23, times[i], "pop", 0.4))
        tw_ = min(460, max(260, slot - 20))
        dt, _ = text_img(ev["date"], F_BLACK_IT, 58 if n <= 4 else 46, fill=YELLOW, maxw=tw_ + 40, align="center", fit=2)
        dx = min(max(xs[i] - dt.width / 2, MX - 30), W - MX + 30 - dt.width)
        els.append(El(dt, dx, ly - 50 - dt.height, times[i] + 0.05, "down"))
        tx, _ = text_img(ev["text"], F_SEMI, 40 if n <= 4 else 34, maxw=tw_, align="center")
        tx_x = min(max(xs[i] - tx.width / 2, MX - 30), W - MX + 30 - tx.width)
        els.append(El(tx, tx_x, ly + 40, times[i] + 0.15, "up"))
    return els


# silueta aproximada de una península (ilustración propia, no es el mapa del juego)
PEN = [(0, 8), (20, 6), (40, 4), (52, 8), (62, 11), (67, 15), (70, 26), (74, 38), (79, 52), (84, 66), (87, 78),
       (86, 88), (81, 94), (76, 95), (71, 90), (66, 80), (61, 68), (57, 56), (53, 44), (51, 34), (47, 25), (40, 21),
       (30, 19), (16, 21), (6, 19), (0, 18)]


def scene_map(sc, ts, t0, dur):
    els, y = heading(sc, t0, CYAN)
    bx0, by0, bw, bh = 820, 150, 1000, 900
    mp = Image.new("RGBA", (bw + 100, bh + 100), (0, 0, 0, 0))

    def P(px, py):
        return (50 + px / 90 * bw, 50 + py / 100 * bh)
    pts = [P(*p) for p in PEN]
    glow = Image.new("RGBA", mp.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).line(pts + [pts[0]], fill=PINK + (255,), width=14)
    glow = glow.filter(ImageFilter.GaussianBlur(14))
    mp.alpha_composite(glow)
    d = ImageDraw.Draw(mp)
    d.polygon(pts, fill=(18, 40, 60, 235))
    for gx in range(0, mp.width, 40):
        for gy in range(0, mp.height, 40):
            pass
    d.line(pts + [pts[0]], fill=PINK + (255,), width=4)
    # cayos
    for i in range(9):
        cx, cy = P(74 - i * 3.2, 97 + i * 0.25)
        d.ellipse((cx - 10, cy - 5, cx + 10, cy + 5), fill=(18, 40, 60, 255), outline=PINK + (255,), width=2)
    # lago
    lx, ly = P(72, 62)
    d.ellipse((lx - 34, ly - 26, lx + 34, ly + 26), fill=(30, 90, 140, 255))
    els.append(El(mp, bx0 - 50, by0 - 50, t0 + 0.1, "fade", 0.8))
    regs = sc["regions"]
    times = reveal_times(len(regs), ts, sc, t0, dur)
    for i, r in enumerate(regs):
        px, py = P(*r["pos"])
        pin = badge_circle(str(i + 1), 54, YELLOW, PINK, 28)
        els.append(El(pin, bx0 - 50 + px - 27, by0 - 50 + py - 27, times[i], "pop", 0.45))
        lab, _ = text_img(r["name"], F_BLACK, 40, stroke=5, stroke_fill=(10, 6, 30), shadow=False)
        side = r.get("side", "right")
        lx_ = {"right": px + 34, "left": px - 34 - lab.width, "up": px - lab.width / 2, "down": px - lab.width / 2}[side]
        ly_ = {"up": py - 40 - lab.height, "down": py + 34}.get(side, py - lab.height / 2)
        els.append(El(lab, bx0 - 50 + lx_, by0 - 50 + ly_, times[i] + 0.1, "fade", 0.4))
        # panel izquierdo con la descripción
        t_out = times[i + 1] - 0.15 if i + 1 < len(regs) else None
        name, _ = text_img(r["name"], F_BLACK_IT, 76, grad=(YELLOW, PINK), maxw=620, fit=2, stroke=4,
                           stroke_fill=(20, 6, 40))
        desc, _ = text_img(r.get("desc", ""), F_SEMI, 40, fill=SOFT, maxw=620)
        panel = Image.new("RGBA", (680, name.height + desc.height + 20), (0, 0, 0, 0))
        panel.alpha_composite(name, (0, 0))
        panel.alpha_composite(desc, (0, name.height - 10))
        els.append(El(panel, MX - 30, max(y, 420 - panel.height // 3), times[i], "left", 0.45, t_out))
    if sc.get("disclaimer", True):
        dis, _ = text_img("Ilustración aproximada, no es el mapa oficial", F_SEMI, 26, fill=SOFT, shadow=False)
        els.append(El(dis, MX - 30, H - 95, t0 + 0.5, "fade"))
    return els


def silhouette(color):
    img = Image.new("RGBA", (560, 640), (0, 0, 0, 0))
    ring = Image.new("RGBA", (560, 560), (0, 0, 0, 0))
    g = vgradient(560, 560, [(0, color), (1, PURPLE)]).convert("RGBA")
    m = Image.new("L", (560, 560), 0)
    ImageDraw.Draw(m).ellipse((0, 0, 559, 559), fill=255)
    ImageDraw.Draw(m).ellipse((16, 16, 543, 543), fill=0)
    g.putalpha(m)
    ring.alpha_composite(g)
    glow = ring.filter(ImageFilter.GaussianBlur(16))
    img.alpha_composite(glow, (0, 40))
    img.alpha_composite(ring, (0, 40))
    d = ImageDraw.Draw(img)
    inner = Image.new("RGBA", (560, 560), (0, 0, 0, 0))
    di = ImageDraw.Draw(inner)
    di.ellipse((24, 24, 536, 536), fill=(24, 14, 54, 255))
    di.ellipse((190, 110, 370, 300), fill=(8, 4, 20, 255))
    di.ellipse((90, 300, 470, 640), fill=(8, 4, 20, 255))
    mm = Image.new("L", (560, 560), 0)
    ImageDraw.Draw(mm).ellipse((24, 24, 536, 536), fill=255)
    inner.putalpha(ImageChops.multiply(inner.getchannel("A"), mm))
    img.alpha_composite(inner, (0, 40))
    q, _ = text_img("?", F_BLACK_IT, 120, fill=color, shadow=False)
    img.alpha_composite(q, (280 - q.width // 2, 40 + 210 - q.height // 2 - 10))
    return img


def scene_profile(sc, ts, t0, dur):
    els = []
    acc = tuple(sc.get("color", PINK))
    sil = silhouette(acc)
    els.append(El(sil, MX, 220, t0, "pop", 0.6))
    k, _ = text_img(sc.get("kicker", "").upper(), F_XBOLD, 36, fill=acc, shadow=False)
    els.append(El(k, 780, 200, t0 + 0.1, "right"))
    nm, _ = text_img(sc["name"], F_BLACK_IT, 120, grad=(WHITE, acc), maxw=1000, fit=1, stroke=5,
                     stroke_fill=(20, 6, 40))
    els.append(El(nm, 760, 240, t0 + 0.2, "right"))
    traits = sc.get("traits", [])
    times = reveal_times(len(traits), ts, sc, t0, dur)
    yy = 240 + nm.height + 10
    for i, tr in enumerate(traits):
        tt, _ = text_img(tr, F_SEMI, 46, maxw=980, shadow=False)
        chip = rounded(tt.width + 70, tt.height + 4, r=26, fill=(24, 14, 56, 235), outline=acc + (255,), width=3)
        chip.alpha_composite(tt, (35, 2))
        els.append(El(chip, 780, yy, times[i], "right"))
        yy += chip.height + 22
    return els


def scene_quote(sc, ts, t0, dur):
    els = []
    acc = tuple(sc.get("color", YELLOW))
    if sc.get("label"):
        k, _ = text_img(sc["label"].upper(), F_BLACK, 44, shadow=False, fill=NAVY)
        pill = rounded(k.width + 50, k.height + 16, r=(k.height + 16) // 2, fill=acc + (255,))
        pill.alpha_composite(k, (25, 8))
        els.append(El(pill, (W - pill.width) / 2, 250, t0, "pop", 0.45))
    q, _ = text_img(sc["text"], F_BLACK_IT, sc.get("size", 84), maxw=1560, align="center", stroke=5,
                    stroke_fill=(20, 6, 40), fit=4)
    els.append(El(q, (W - q.width) / 2, 560 - q.height / 2 + 30, t0 + 0.2, "up", 0.6))
    if sc.get("detail"):
        dd, _ = text_img(sc["detail"], F_SEMI, 40, fill=SOFT, maxw=1400, align="center")
        els.append(El(dd, (W - dd.width) / 2, 560 + q.height / 2 + 50, ts[min(1, len(ts) - 1)] + 0.2, "up"))
    return els


def scene_outro(sc, ts, t0, dur):
    els = []
    t, _ = text_img(sc.get("title", "¿Te ha servido?"), F_BLACK_IT, 110, grad=(YELLOW, PINK), stroke=6,
                    stroke_fill=(20, 6, 40), glow=PINK, maxw=1600, align="center", fit=2)
    els.append(El(t, (W - t.width) / 2, 170, t0, "pop", 0.6))
    sub, _ = text_img("SUSCRÍBETE", F_BLACK, 64, shadow=False)
    btn = rounded(sub.width + 160, sub.height + 50, r=(sub.height + 50) // 2, fill=(230, 30, 60, 255))
    ImageDraw.Draw(btn).polygon([(40, 30), (40, btn.height - 30), (40 + 50, btn.height // 2)], fill=WHITE)
    btn.alpha_composite(sub, (115, 25))
    els.append(El(btn, (W - btn.width) / 2, 470, ts[min(1, len(ts) - 1)] if len(ts) > 1 else t0 + 0.7, "pop", 0.5))
    if sc.get("next"):
        nx, _ = text_img("PRÓXIMO VÍDEO", F_XBOLD, 30, fill=CYAN, shadow=False)
        nt, _ = text_img(sc["next"], F_BOLD, 46, maxw=1300, align="center", fit=2, shadow=False)
        card = rounded(max(nt.width, nx.width) + 100, nx.height + nt.height + 64, r=26,
                       fill=(20, 12, 48, 235), outline=CYAN + (255,), width=3)
        card.alpha_composite(nx, ((card.width - nx.width) // 2, 20))
        card.alpha_composite(nt, ((card.width - nt.width) // 2, nx.height + 34))
        els.append(El(card, (W - card.width) / 2, 680, ts[min(2, len(ts) - 1)] + 0.1, "up"))
    return els


BUILDERS = {
    "title": scene_title, "bullets": scene_list, "checklist": lambda *a: scene_list(*a, check=True),
    "stat": scene_stat, "table": scene_table, "compare": scene_compare, "timeline": scene_timeline,
    "map": scene_map, "profile": scene_profile, "quote": scene_quote, "outro": scene_outro,
}
DEFAULT_BG = {"title": "sunset", "outro": "sunset", "map": "bokeh", "profile": "city"}


# ============================================================ timeline + render

def build_timeline(spec):
    scenes = spec["scenes"]
    t = 0.0
    voice, plan, subs, chapters = [], [], [], []
    rot = ["city", "sunset_dim", "bokeh"]
    k = 0
    for i, sc in enumerate(scenes):
        start = t
        lead = 0.7 if i == 0 else 0.55
        cur = start + lead
        ts = []
        for line in sc["say"]:
            a = audio.say(line)
            ts.append(cur)
            voice.append((cur, a))
            d = len(a) / SR
            subs.append((cur, cur + d, line))
            gap = 0.30 if line.rstrip().endswith((".", "?", "!", ":")) else 0.18
            cur += d + gap
        end = cur + sc.get("hold", 0.5)
        if sc.get("chapter"):
            chapters.append((start, sc["chapter"]))
        bg = sc.get("bg") or DEFAULT_BG.get(sc["type"])
        if not bg:
            bg = rot[k % 3]
            k += 1
        plan.append(dict(sc=sc, start=start, end=end, ts=ts, bg=bg))
        t = end
    return plan, voice, subs, chapters, t


def fmt_ts(s, srt=True):
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if srt:
        return f"{int(h):02d}:{int(m):02d}:{int(sec):02d},{int((sec - int(sec)) * 1000):03d}"
    return f"{int(m)}:{int(sec):02d}" if h < 1 else f"{int(h)}:{int(m):02d}:{int(sec):02d}"


def write_srt(subs, path):
    out, n = [], 1
    for (a, b, text) in subs:
        words = text.split()
        chunks, cur = [], ""
        for w_ in words:
            if len(cur) + len(w_) + 1 > 84 and cur:
                chunks.append(cur)
                cur = w_
            else:
                cur = (cur + " " + w_).strip()
        chunks.append(cur)
        total = sum(len(c) for c in chunks)
        t = a
        for c in chunks:
            d = (b - a) * len(c) / total
            lines = wrap(c, font(F_SEMI, 40), 900)
            out.append(f"{n}\n{fmt_ts(t)} --> {fmt_ts(t + d)}\n" + "\n".join(lines) + "\n")
            n += 1
            t += d
    open(path, "w", encoding="utf-8").write("\n".join(out))


class Renderer:
    def __init__(self, spec, plan, total, seed):
        self.spec, self.plan, self.total = spec, plan, total
        self.bgs = Backgrounds(seed)
        self.els = []
        for p in plan:
            sc = p["sc"]
            b = BUILDERS[sc["type"]]
            dur = p["end"] - p["start"]
            els = b(sc, p["ts"], p["start"] + (0.15 if sc["type"] != "title" else 0.3), dur)
            if sc.get("source"):
                s, _ = text_img("Fuente: " + sc["source"], F_SEMI, 26, fill=SOFT, shadow=True)
                els.append(El(s, MX - 30, H - 95, p["start"] + 0.6, "fade"))
            self.els.append(els)
        bug, _ = text_img("★ " + CHANNEL_NAME, F_BLACK_IT, 30, fill=WHITE, shadow=True)
        bug.putalpha(bug.getchannel("A").point(lambda v: int(v * 0.85)))
        self.bug = El(bug, W - bug.width - 30, 18, -1, "fade", 0.01)
        self.bar = hgradient(W, 8, PINK, CYAN)

    def scene_frame(self, i, t):
        p = self.plan[i]
        img = self.bgs.frame(p["bg"], t)
        for e in self.els[i]:
            e.draw(img, t)
        return img

    def frame(self, t):
        idx = 0
        for i, p in enumerate(self.plan):
            if t >= p["start"]:
                idx = i
        img = self.scene_frame(idx, t)
        # transición (barrido diagonal) alrededor de cada corte
        TR = 0.32
        for j in range(1, len(self.plan)):
            T = self.plan[j]["start"]
            if T - TR <= t < T + TR:
                u = (t - (T - TR)) / (2 * TR)
                cx = -700 + u * (W + 1400)
                other = self.scene_frame(j - 1 if t >= T else j, t)
                old, new = (other, img) if t >= T else (img, other)
                mask = Image.new("L", (W, H), 0)
                ImageDraw.Draw(mask).polygon([(0, 0), (cx + 150, 0), (cx - 150, H), (0, H)], fill=255)
                img = Image.composite(new, old, mask)
                d = ImageDraw.Draw(img)
                for k, (col, off, wd) in enumerate([(PINK, 0, 120), (PURPLE, 120, 60), (CYAN, 180, 30)]):
                    x = cx - off
                    d.polygon([(x + 150, 0), (x + 150 + wd, 0), (x - 150 + wd, H), (x - 150, H)], fill=col)
        self.bug.draw(img, t)
        pw = int(W * t / self.total)
        if pw > 0:
            img.paste(self.bar.crop((0, 0, pw, 8)), (0, H - 8))
        return img


def thumbnail(spec, bgs, path):
    th = spec.get("thumb", {})
    bg = bgs.frame(th.get("bg", "sunset"), 0.3).convert("RGBA")
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for x in range(0, W, 4):
        a = int(200 * max(0, 1 - x / (W * 0.75)))
        sd.rectangle((x, 0, x + 4, H), fill=(8, 2, 24, a))
    img = Image.alpha_composite(bg, shade)
    # estrellas (nivel de búsqueda) arriba
    star = text_img("★★★★★★", F_BLACK, 70, fill=YELLOW, stroke=4, stroke_fill=(20, 6, 40), shadow=True)[0]
    img.alpha_composite(star, (70, 40))
    tag = th.get("tag", "GTA 6")
    tg, _ = text_img(tag, F_BLACK_IT, 74, fill=WHITE, shadow=False)
    pill = rounded(tg.width + 50, tg.height + 20, r=24, fill=PINK + (255,))
    pill.alpha_composite(tg, (25, 10))
    img.alpha_composite(pill, (70, 150))
    big, _ = text_img(th.get("big", spec["meta"]["title"]), F_BLACK_IT, 210, grad=(YELLOW, ORANGE), maxw=1250,
                      stroke=12, stroke_fill=(10, 2, 20), glow=PINK, fit=3, spacing=0.98)
    img.alpha_composite(big, (40, 150 + pill.height + 10))
    if th.get("sticker"):
        st, _ = text_img(th["sticker"], F_BLACK, 120, fill=NAVY, shadow=False)
        s = rounded(st.width + 70, st.height + 40, r=30, fill=CYAN + (255,), outline=WHITE + (255,), width=6)
        s.alpha_composite(st, (35, 20))
        s = s.rotate(8, expand=True, resample=Image.BICUBIC)
        img.alpha_composite(s, (W - s.width - 90, H - s.height - 110))
    img.convert("RGB").resize((1280, 720), Image.LANCZOS).save(path, quality=95)


def write_docs(spec, plan, chapters, total, vdir):
    m = spec["meta"]
    ch = "\n".join(f"{fmt_ts(t, srt=False)} {name}" for t, name in chapters)
    desc = m["description"].strip()
    sources = "\n".join(f"- {s}" for s in spec.get("sources", []))
    md = f"""# {m['title']}

**Duración:** {fmt_ts(total, srt=False)}  ·  **Publicar:** {spec.get('publish', 'jueves 19/11/2026')}

## Título (copiar)
```
{m['title']}
```

## Descripción (copiar)
```
{desc}

⏱️ CAPÍTULOS
{ch}

📌 Fuentes consultadas: ver comentario fijado.
🔔 Suscríbete a {CHANNEL_NAME} para guías de GTA 6 cada día.

{' '.join(m.get('hashtags', ['#GTA6', '#GTAVI']))}
```

## Etiquetas (copiar)
```
{', '.join(m['tags'])}
```

## Comentario fijado
```
{m.get('pinned', '¿Qué es lo primero que vas a hacer en GTA 6? Te leo 👇')}

Fuentes:
{sources}
```

## Ajustes de subida
- Subtítulos: sube `subtitulos.srt` (Español).
- Miniatura: `miniatura.png` (1280×720).
- Categoría: Videojuegos · Juego: Grand Theft Auto VI.
- Pantalla final (últimos 15 s): botón de suscripción + vídeo "{m.get('endscreen', 'Lista de reproducción GTA 6')}".
- Contenido alterado/sintético: **No** (narración con voz sintética, gráficos originales; no muestra personas ni hechos reales falsos).
"""
    open(os.path.join(vdir, "metadatos.md"), "w", encoding="utf-8").write(md)
    g = [f"# Guion — {m['title']}\n"]
    for p in plan:
        sc = p["sc"]
        g.append(f"\n## [{fmt_ts(p['start'], srt=False)}] {sc.get('chapter') or sc.get('heading') or sc.get('title') or sc['type']}")
        g.append(f"*Escena: {sc['type']} · Fondo: {p['bg']}*\n")
        for line in sc["say"]:
            g.append(f"> {line}")
    open(os.path.join(vdir, "guion.md"), "w", encoding="utf-8").write("\n".join(g) + "\n")


def render(vdir, preview=False):
    spec = yaml.safe_load(open(os.path.join(vdir, "script.yaml"), encoding="utf-8"))
    seed = int(spec.get("seed", 0))
    plan, voice, subs, chapters, total = build_timeline(spec)
    sfx = []
    for j, p in enumerate(plan[1:], 1):
        sfx.append((p["start"] - 0.3, audio.whoosh(j)))
    mixw = audio.mix(total, voice, sfx, seed)
    build = os.path.join(ROOT, "build", os.path.basename(vdir))
    os.makedirs(build, exist_ok=True)
    wav = os.path.join(build, "mix.wav")
    sf.write(wav, mixw[: int(total * SR)], SR)
    write_srt(subs, os.path.join(vdir, "subtitulos.srt"))
    write_docs(spec, plan, chapters, total, vdir)
    r = Renderer(spec, plan, total, seed)
    thumbnail(spec, r.bgs, os.path.join(vdir, "miniatura.png"))
    if preview:  # fotogramas de muestra
        for i, p in enumerate(plan):
            t = min(p["end"] - 0.05, p["ts"][-1] + 1.2 if p["ts"] else p["start"] + 1)
            r.frame(t).save(os.path.join(build, f"scene{i:02d}.jpg"), quality=85)
        return total
    out = os.path.join(vdir, "video.mp4")
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "faster", "-crf", "21",
           "-tune", "animation", "-pix_fmt", "yuv420p", "-threads", "2", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
           "-ar", "48000", "-movflags", "+faststart", "-shortest", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    nframes = int(total * FPS)
    for f in range(nframes):
        proc.stdin.write(r.frame(f / FPS).tobytes())
        if f % 900 == 0:
            print(f"{os.path.basename(vdir)}: {f}/{nframes}", flush=True)
    proc.stdin.close()
    proc.wait()
    print(f"OK {out} {fmt_ts(total, srt=False)}")
    return total


if __name__ == "__main__":
    render(sys.argv[1], preview="--preview" in sys.argv)

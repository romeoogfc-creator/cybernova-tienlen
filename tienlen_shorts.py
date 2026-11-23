#!/usr/bin/env python3
"""
Tiến Lên Nova Shorts maker (version 5: never-ending "Đố bạn" what-if videos with answers).
"""
import argparse
import asyncio
import datetime
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import zlib

from PIL import Image, ImageDraw, ImageFont

try:
    import numpy as np
    import fx_audio
    HAVE_AUDIO = True
except Exception:
    HAVE_AUDIO = False

HERE = os.path.dirname(os.path.abspath(__file__))
MADE_LOG = os.path.join(HERE, 'made_lessons.json')
W, H, FPS = 1080, 1920, 30
SCENE_Y, SCENE_H = 430, 880
STEP_PAD = 0.06
GOLD, WHITE, SOFT = (255, 215, 0), (255, 255, 255), (200, 211, 234)
RED, BLACK = (200, 30, 40), (20, 22, 30)
DEFAULT_VOICE = 'vi-VN-HoaiMyNeural'
CHANNEL_HANDLE = '@CybernovaGame'
GAME_LINK = 'https://tienlennova.com/vi.html'      # the game's website (Vietnamese home page with the Play button)


def font(size, bold=True):
    p = os.path.join(HERE, 'fonts', 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')
    return ImageFont.truetype(p, size) if os.path.exists(p) else ImageFont.load_default()


def tw(draw, s, f):
    return draw.textlength(s, font=f)


def wrap(draw, s, f, max_w):
    words, lines, cur = s.split(' '), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if tw(draw, t, f) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def ease_out_cubic(p):
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def ease_out_back(p, s=1.9):
    p = min(1.0, max(0.0, p))
    q = p - 1
    return 1 + q * q * ((s + 1) * q + s)


def text_sprite(text, size, fill=WHITE, stroke=5, shadow=True):
    f = font(size)
    d = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
    w = int(d.textlength(text, font=f)) + 2 * stroke + 24
    h = int(size * 1.35) + 2 * stroke + 16
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    dd = ImageDraw.Draw(im)
    if shadow:
        dd.text((stroke + 12 + 5, stroke + 6 + 7), text, font=f, fill=(110, 0, 10, 255), stroke_width=stroke, stroke_fill=(110, 0, 10, 255))
    dd.text((stroke + 12, stroke + 6), text, font=f, fill=fill + (255,), stroke_width=stroke, stroke_fill=(25, 4, 8, 255))
    return im


def make_background():
    if HAVE_AUDIO:
        y = np.linspace(0, 1, H)[:, None]
        t = np.abs(y - 0.45) / 0.55
        ones = np.ones((1, W))
        arr = np.stack([(95 - 62 * t) * ones, (14 - 9 * t) * ones, (26 - 16 * t) * ones], axis=2).clip(0, 255).astype('uint8')
        img = Image.fromarray(arr)
    else:
        img = Image.new('RGB', (W, H), (60, 9, 16))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([22, 22, W - 22, H - 22], radius=40, outline=(212, 175, 55), width=5)
    return img


def make_hook_background():
    img = Image.new('RGB', (W, H), (14, 2, 5))
    if HAVE_AUDIO:
        yy, xx = np.mgrid[0:H, 0:W]
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H * 0.42) / (H * 0.42)) ** 2)
        glow = np.clip(1 - r, 0, 1) ** 1.4
        arr = np.stack([22 + 150 * glow, 3 + 18 * glow, 8 + 26 * glow], axis=2).clip(0, 255).astype('uint8')
        img = Image.fromarray(arr)
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    rnd = random.Random(5)
    cx, cy = W / 2, H * 0.42
    for _ in range(46):
        a = rnd.uniform(0, 2 * math.pi)
        wid = rnd.uniform(0.012, 0.04)
        p1 = (cx + math.cos(a - wid) * 2600, cy + math.sin(a - wid) * 2600)
        p2 = (cx + math.cos(a + wid) * 2600, cy + math.sin(a + wid) * 2600)
        od.polygon([(cx, cy), p1, p2], fill=(255, 120, 40, rnd.randint(14, 34)))
    img = Image.alpha_composite(img.convert('RGBA'), ov).convert('RGB')
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 170], fill=(0, 0, 0))
    d.rectangle([0, H - 170, W, H], fill=(0, 0, 0))
    d.rectangle([0, 166, W, 172], fill=(212, 175, 55))
    d.rectangle([0, H - 172, W, H - 166], fill=(212, 175, 55))
    f = font(36)
    s = 'CYBERNOVA GAME  ·  TIẾN LÊN MIỀN NAM'
    d.text(((W - tw(d, s, f)) / 2, 66), s, font=f, fill=(230, 200, 120))
    return img


def card_image(spec, size=(170, 240), glow=False):
    if spec == 'BACK':                                   # a face-down card (an opponent's hidden card)
        cw, ch = size
        im = Image.new('RGBA', (cw + 20, ch + 20), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([10, 10, cw + 9, ch + 9], radius=18, fill=(40, 52, 110), outline=(255, 255, 255), width=5)
        for k in range(-ch, cw, 22):
            d.line([(10 + k, 10), (10 + k + ch, 10 + ch)], fill=(70, 90, 170), width=6)
        d.rounded_rectangle([24, 24, cw - 5, ch - 5], radius=12, outline=(255, 215, 0), width=3)
        f = font(int(ch * 0.3))
        d.text((10 + (cw - d.textlength('?', font=f)) / 2, 10 + ch * 0.3), '?', font=f, fill=(255, 215, 0))
        return im
    rank, suit = spec[:-1], spec[-1]
    red = suit in '♥♦'
    cw, ch = size
    im = Image.new('RGBA', (cw + 20, ch + 20), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if glow:
        d.rounded_rectangle([0, 0, cw + 19, ch + 19], radius=26, fill=(255, 215, 0, 130))
    d.rounded_rectangle([10, 10, cw + 9, ch + 9], radius=18, fill=(252, 252, 252), outline=(255, 215, 0) if glow else (150, 150, 160), width=6 if glow else 3)
    col = RED if red else BLACK
    fr, fs, fb = font(int(ch * 0.2)), font(int(ch * 0.17)), font(int(ch * 0.48))
    d.text((22, 14), rank, font=fr, fill=col)
    d.text((24, 14 + int(ch * 0.2)), suit, font=fs, fill=col)
    sw = d.textlength(suit, font=fb)
    d.text((10 + (cw - sw) / 2, 10 + ch * 0.28), suit, font=fb, fill=col)
    corner = Image.new('RGBA', (int(cw * 0.5), int(ch * 0.42)), (0, 0, 0, 0))
    cd = ImageDraw.Draw(corner)
    cd.text((6, 2), rank, font=fr, fill=col)
    cd.text((8, 2 + int(ch * 0.2)), suit, font=fs, fill=col)
    corner = corner.rotate(180)
    im.alpha_composite(corner, (cw + 10 - corner.width, ch + 10 - corner.height))
    return im


def _fit_sprite(text, max_w, start_size, fill, stroke):
    size = start_size
    while size > 40:
        sp = text_sprite(text, size, fill, stroke=stroke)
        if sp.width <= max_w:
            return sp
        size -= 6
    return text_sprite(text, 40, fill, stroke=stroke)


def make_cover(lesson, path, size=(1080, 1920)):
    cw, chh = size
    wide = cw > chh
    yy, xx = np.mgrid[0:chh, 0:cw]
    cx, cy = cw / 2, chh * (0.50 if wide else 0.44)
    r = np.sqrt(((xx - cx) / (cw / 2)) ** 2 + ((yy - cy) / (chh * 0.5)) ** 2)
    glow = np.clip(1 - r * 0.85, 0, 1) ** 1.3
    vig = np.clip(1.15 - r * 0.45, 0.25, 1)
    arr = np.stack([(18 + 235 * glow) * vig, (2 + 70 * glow ** 1.6) * vig, (10 + 30 * glow) * vig], axis=2).clip(0, 255).astype('uint8')
    img = Image.fromarray(arr).convert('RGBA')
    ov = Image.new('RGBA', size, (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    rnd = random.Random(zlib.crc32(lesson['id'].encode('utf-8')))
    for _ in range(40):
        a = rnd.uniform(0, 2 * math.pi)
        wid = rnd.uniform(0.01, 0.05)
        od.polygon([(cx, cy), (cx + math.cos(a - wid) * 3000, cy + math.sin(a - wid) * 3000), (cx + math.cos(a + wid) * 3000, cy + math.sin(a + wid) * 3000)], fill=(255, 190, 60, rnd.randint(18, 48)))
    for _ in range(70):
        x, y, s = rnd.uniform(0, cw), rnd.uniform(0, chh), rnd.uniform(3, 10)
        od.ellipse([x - s, y - s, x + s, y + s], fill=(255, 225, 120, rnd.randint(110, 230)))
    img = Image.alpha_composite(img, ov)

    specs = []
    for st in lesson['steps']:
        for g in (st.get('scene') or {}).get('groups', []):
            for c in g.get('cards', []):
                if c not in specs and c != 'BACK':
                    specs.append(c)
    big = [c for c in specs if c.startswith('2')] + [c for c in specs if not c.startswith('2')]
    specs = (big + ['2♥', '2♦', 'A♠', 'K♥', 'Q♣'])[:5] if len(big) < 5 else big[:5]
    csz = (250, 355) if not wide else (190, 270)
    base_y = chh * 0.80 if not wide else chh * 0.86
    n = len(specs)
    for i, sp in enumerate(specs):
        ang = (i - (n - 1) / 2) * (13 if not wide else 11)
        card = card_image(sp, csz, glow=True).rotate(-ang, expand=True, resample=Image.BICUBIC)
        px = int(cx + (i - (n - 1) / 2) * csz[0] * (0.62) - card.width / 2)
        py = int(base_y - card.height / 2 - abs(i - (n - 1) / 2) * (22 if not wide else 14))
        sh = Image.new('RGBA', card.size, (0, 0, 0, 0))
        sh.paste((0, 0, 0, 150), mask=card.split()[3])
        img.alpha_composite(sh, (px + 10, py + 16))
        img.alpha_composite(card, (px, py))

    lines = (lesson.get('hook') or {}).get('lines') or [lesson['title'].upper()]
    max_w = int(cw * 0.94)
    sprites = []
    for k, ln in enumerate(lines):
        sprites.append(_fit_sprite(ln, max_w, 190 if not wide else 120, GOLD if k % 2 == 0 else WHITE, 9))
    total_h = sum(sp.height for sp in sprites) - 20 * (len(sprites) - 1)
    layer = Image.new('RGBA', (cw, total_h + 60), (0, 0, 0, 0))
    y = 20
    for sp in sprites:
        layer.alpha_composite(sp, ((cw - sp.width) // 2, y))
        y += sp.height - 20
    layer = layer.rotate(3.5, resample=Image.BICUBIC, expand=False)
    top = int(chh * (0.12 if not wide else 0.10))
    img.alpha_composite(layer, (0, top))

    d = ImageDraw.Draw(img)
    f = font(44 if not wide else 30)
    s = 'CYBERNOVA GAME'
    pw = int(tw(d, s, f)) + 70
    d.rounded_rectangle([(cw - pw) // 2, 26, (cw + pw) // 2, 26 + (84 if not wide else 58)], radius=40, fill=(212, 175, 55))
    d.text(((cw - tw(d, s, f)) / 2, 40 if not wide else 32), s, font=f, fill=(25, 4, 8))
    if not wide:
        pr = 82
        pcx, pcy = cw // 2, int(chh * 0.62)
        d.ellipse([pcx - pr - 12, pcy - pr - 12, pcx + pr + 12, pcy + pr + 12], fill=(0, 0, 0, 120))
        d.ellipse([pcx - pr, pcy - pr, pcx + pr, pcy + pr], fill=(255, 215, 0), outline=(255, 255, 255), width=6)
        d.polygon([(pcx - 28, pcy - 48), (pcx - 28, pcy + 48), (pcx + 52, pcy)], fill=(25, 4, 8))
        f2 = font(54)
        s2 = 'XEM NGAY'
        d.rounded_rectangle([cw // 2 - 190, chh - 170, cw // 2 + 190, chh - 80], radius=44, fill=(200, 30, 40), outline=(255, 215, 0), width=5)
        d.text(((cw - tw(d, s2, f2)) / 2, chh - 160), s2, font=f2, fill=WHITE)
    img.convert('RGB').save(path, quality=93)
    return path


class Item:
    def __init__(self, img, cx, cy, delay=0.0, anim='pop', dur=0.30, pulse=False, loop=None, sound=None, to=None):
        self.img, self.cx, self.cy, self.delay, self.anim, self.dur, self.pulse, self.loop, self.sound, self.to = img, cx, cy, delay, anim, dur, pulse, loop, sound, to


def build_items(scene):
    kind = scene.get('type', 'bullets')
    items = []
    if kind == 'ranks':
        order = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']
        hi = set(scene.get('highlight', []))
        f = font(64)
        n = 0
        for ri, row in enumerate([order[:7], order[7:]]):
            total = len(row) * 120 + (len(row) - 1) * 16
            x0 = (W - total) / 2
            for i, r in enumerate(row):
                on = r in hi
                im = Image.new('RGBA', (126, 136), (0, 0, 0, 0))
                d = ImageDraw.Draw(im)
                d.rounded_rectangle([3, 3, 123, 133], radius=22, fill=(255, 215, 0) if on else (250, 250, 252), outline=(255, 255, 255), width=3)
                d.text(((126 - d.textlength(r, font=f)) / 2, 30), r, font=f, fill=BLACK)
                items.append(Item(im, x0 + i * 136 + 60, 150 + ri * 160 + 65, delay=0.04 * n, anim='pop', dur=0.26, pulse=on, sound='card' if n % 3 == 0 else None))
                n += 1
        items.append(Item(text_sprite('NHỎ  ➜  LỚN', 52, SOFT, 3, False), W / 2, 590, delay=0.7, anim='fade', dur=0.25))
        items.append(Item(text_sprite('Heo (số 2) là lá lớn nhất', 40, GOLD if hi else SOFT, 3, False), W / 2, 680, delay=0.9, anim='fade', dur=0.25))
    elif kind == 'suits':
        names = [('♠', 'Bích', BLACK), ('♣', 'Chuồn', BLACK), ('♦', 'Rô', RED), ('♥', 'Cơ', RED)]
        for i, (sym, nm, col) in enumerate(names):
            im = Image.new('RGBA', (216, 326), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.rounded_rectangle([3, 3, 213, 323], radius=26, fill=(250, 250, 252), outline=(255, 255, 255), width=3)
            fb, fn = font(150), font(44)
            d.text(((216 - d.textlength(sym, font=fb)) / 2, 30), sym, font=fb, fill=col)
            d.text(((216 - d.textlength(nm, font=fn)) / 2, 240), nm, font=fn, fill=BLACK)
            items.append(Item(im, 75 + i * 240 + 105, 320, delay=0.15 * i, anim='drop', dur=0.32, sound='card'))
        items.append(Item(text_sprite('NHỎ  ➜  LỚN', 52, SOFT, 3, False), W / 2, 640, delay=0.8, anim='fade', dur=0.25))
    elif kind == 'money':
        amount = scene.get('amount', '4 điểm')

        def badge(txt, fill, size=230):
            im = Image.new('RGBA', (size, size), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            d.ellipse([6, 6, size - 6, size - 6], fill=fill, outline=(255, 255, 255), width=8)
            f = font(int(size * 0.5))
            d.text(((size - d.textlength(txt, font=f)) / 2, size * 0.2), txt, font=f, fill=(255, 255, 255))
            return im

        xl, xr, yy = 235, 845, 260
        items.append(Item(badge(scene.get('loser_rank', '4'), (190, 40, 50)), xl, yy, delay=0.0, anim='pop', dur=0.3))
        items.append(Item(badge(scene.get('winner_rank', '1'), (212, 160, 20)), xr, yy, delay=0.15, anim='pop', dur=0.3))
        items.append(Item(text_sprite(scene.get('loser', 'VỀ BÉT'), 54, WHITE, 4), xl, yy + 165, delay=0.2, anim='fade', dur=0.2))
        items.append(Item(text_sprite(scene.get('winner', 'NHẤT'), 54, GOLD, 4), xr, yy + 165, delay=0.3, anim='fade', dur=0.2))
        coin = Image.new('RGBA', (96, 96), (0, 0, 0, 0))
        cd = ImageDraw.Draw(coin)
        cd.ellipse([2, 2, 93, 93], fill=(255, 205, 40), outline=(160, 110, 0), width=5)
        cd.ellipse([17, 17, 78, 78], outline=(190, 135, 10), width=5)
        for k in range(9):
            items.append(Item(coin, xl, yy, delay=0.7 + 0.13 * k, anim='fly', dur=0.75, to=(xr, yy), sound='card' if k % 3 == 0 else None))
        items.append(Item(text_sprite('- ' + amount, 74, (255, 90, 90), 5), xl, yy + 300, delay=0.7, anim='pop', dur=0.3, loop='throb'))
        items.append(Item(text_sprite('+ ' + amount, 74, (90, 255, 140), 5), xr, yy + 300, delay=1.9, anim='pop', dur=0.3, loop='throb', sound='ding'))
        for i, ln in enumerate(scene.get('lines', [])):
            items.append(Item(text_sprite(ln, 58, WHITE if i else GOLD, 4), W / 2, 640 + i * 78, delay=2.3 + 0.25 * i, anim='fade', dur=0.25))
    elif kind == 'cards':
        groups = scene['groups']
        gh = 390
        y = (SCENE_H - gh * len(groups)) / 2 + 10
        t0 = 0.0
        for g in groups:
            cards, hi = g['cards'], set(g.get('highlight', []))
            n = len(cards)
            items.append(Item(text_sprite(g.get('label', ''), 44, GOLD if hi else WHITE, 3, False), W / 2, y + 28, delay=t0, anim='fade', dur=0.2))
            cw, chh = 170, 240
            room = 900 if n <= 8 else 1010                      # a full 13-card hand gets the whole width so '10' stays readable
            step = (cw + 12) if n * (cw + 12) <= room else (room - cw) / max(1, n - 1)
            total = step * (n - 1) + cw
            x0 = (W - total) / 2
            drop_delay = 0.045 if n > 6 else 0.10
            for i, c in enumerate(cards):
                up = i in hi
                im = card_image(c, (cw, chh), glow=up)
                items.append(Item(
                    im,
                    x0 + i * step + cw / 2,
                    y + 100 + chh / 2 - (26 if up else 0),
                    delay=t0 + 0.08 + drop_delay * i,
                    anim='drop',
                    dur=0.22,
                    pulse=up,
                    sound='card'
                ))
            t0 += 0.08 + drop_delay * n + 0.25
            y += gh
    else:
        lines = scene.get('lines', [])
        size = 96
        d0 = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
        while size > 40:
            f = font(size)
            if max(d0.textlength(ln, font=f) for ln in lines) <= 900:
                break
            size -= 4
        lh = int(size * 1.4)
        y = (SCENE_H - lh * len(lines)) / 2 + lh / 2
        for i, ln in enumerate(lines):
            col = GOLD if (i == 0 and len(lines) > 1) or ln.startswith('= ') else WHITE
            items.append(Item(text_sprite(ln, size, col, 4), W / 2, y + i * lh, delay=0.20 * i, anim='slide_l' if i % 2 == 0 else 'slide_r', dur=0.30, sound='pop'))
    return items


def draw_item(frame, it, local, z, sx, sy):
    q = local - it.delay
    if q < 0:
        return
    p = min(1.0, q / it.dur)
    scale, alpha, dx, dy = 1.0, 1.0, 0.0, 0.0
    if it.anim == 'pop':
        scale = 0.35 + 0.65 * ease_out_back(p)
        alpha = min(1.0, p * 3)
    elif it.anim == 'drop':
        dy = -(1 - ease_out_cubic(p)) * 170
        scale = 0.75 + 0.25 * ease_out_back(p)
        alpha = min(1.0, p * 4)
    elif it.anim == 'slide_l':
        dx = -(1 - ease_out_cubic(p)) * 280
        alpha = min(1.0, p * 3)
    elif it.anim == 'slide_r':
        dx = (1 - ease_out_cubic(p)) * 280
        alpha = min(1.0, p * 3)
    elif it.anim == 'fade':
        alpha = p
    elif it.anim == 'fly' and it.to:
        if p >= 1:
            return
        e = ease_out_cubic(p)
        dx = (it.to[0] - it.cx) * e
        dy = (it.to[1] - it.cy) * e - math.sin(math.pi * p) * 150
    if it.pulse and p >= 1:
        scale *= 1 + 0.045 * math.sin((q - it.dur) * 8)
    if it.loop == 'bob':
        dy += 14 * math.sin(local * 7)
    elif it.loop == 'throb' and p >= 1:
        scale *= 1 + 0.045 * math.sin(local * 9)
    cx = W / 2 + (it.cx + dx - W / 2) * z + sx
    cy = SCENE_Y + SCENE_H / 2 + (it.cy + dy - SCENE_H / 2) * z + sy
    s = scale * z
    sp = it.img
    if abs(s - 1) > 0.01:
        sp = sp.resize((max(1, int(sp.width * s)), max(1, int(sp.height * s))), Image.BILINEAR)
    pos = (int(cx - sp.width / 2), int(cy - sp.height / 2))
    mask = sp if alpha > 0.995 else sp.getchannel('A').point(lambda v, a=alpha: int(v * a))
    frame.paste(sp, pos, mask)


class Step:
    pass


def est_seconds(say):
    return max(2.2, len(say) / 12.5)


def word_times(say, dur, tokens):
    words = say.split()
    if not words:
        return []
    total_chars = sum(len(w) for w in words) + len(words) - 1
    starts_chars, c = [], 0
    for w in words:
        starts_chars.append(c)
        c += len(w) + 1
    if tokens:
        pos, marks = 0, []
        for st, tx in tokens:
            marks.append((pos, st))
            pos += len(tx) + 1
        marks.append((max(pos, total_chars), tokens[-1][0] + 0.3))
        out = []
        for sc in starts_chars:
            sc2 = sc * (marks[-1][0] / max(1, total_chars))
            t = marks[-1][1]
            for a, b in zip(marks, marks[1:]):
                if a[0] <= sc2 <= b[0]:
                    t = a[1] + (b[1] - a[1]) * ((sc2 - a[0]) / max(1e-6, (b[0] - a[0])))
                    break
            out.append(0.03 + t)
        return out
    lo, hi = 0.08, max(0.4, dur - 0.10)
    return [lo + (hi - lo) * (sc / max(1, total_chars)) for sc in starts_chars]


def plan_lesson(lesson, cfg, voice):
    raw = []
    hook = lesson.get('hook')
    if hook:
        raw.append({'kind': 'hook', 'say': hook['say'], 'lines': hook['lines'], 'fx': ['impact'], 'scene': {}})
    for st in lesson['steps']:
        raw.append({'kind': 'scene', 'say': st['say'], 'scene': st['scene'], 'fx': st.get('fx', [])})
    steps, t = [], 0.0
    for i, r in enumerate(raw):
        is_last = (i == len(raw) - 1)
        s = Step()
        v = voice[i] if voice else None
        speech = v['dur'] if v else est_seconds(r['say'])
        s.kind, s.say, s.fx = r['kind'], r['say'], r['fx']
        s.start = t
        pad = 0.02 if is_last else STEP_PAD
        s.dur = max(1.8 if s.kind == 'hook' else 1.4, speech + pad)
        s.speech = speech
        s.tokens = v['tokens'] if v else []
        s.words = s.say.split()
        s.wtimes = word_times(s.say, speech, s.tokens)
        s.items = build_items(r['scene']) if s.kind == 'scene' else []
        s.has_hl = bool(s.kind == 'scene' and any(g.get('highlight') for g in r['scene'].get('groups', [])))
        s.hook_sprites = []
        if s.kind == 'hook':
            d0 = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
            for li, ln in enumerate(r['lines']):
                size = 170
                while size > 50 and d0.textlength(ln, font=font(size)) > 920:
                    size -= 6
                s.hook_sprites.append(text_sprite(ln, size, GOLD if li == 0 else WHITE, 8))
        steps.append(s)
        t += s.dur
    return steps, t


def sound_events(steps):
    ev = []
    for s in steps:
        t0 = s.start
        if s.kind == 'hook':
            ev += [(t0 + 0.0, 'whoosh', 0.8), (t0 + 0.14, 'impact', 1.0), (t0 + 0.34, 'pop', 0.7), (t0 + 0.62, 'ding', 0.35)]
        else:
            ev += [(t0 - 0.02, 'whoosh', 0.55), (t0 + 0.04, 'pop', 0.55)]
            if 'impact' in s.fx:
                ev.append((t0 + 0.10, 'impact', 0.95))
            if s.has_hl:
                ev.append((t0 + 0.85, 'ding', 0.5))
            for it in s.items:
                if it.sound:
                    ev.append((t0 + it.delay + 0.04, it.sound, 0.5 if it.sound == 'card' else 0.35))
    return ev


class Renderer:
    def __init__(self, lesson, steps, total):
        self.lesson, self.steps, self.total = lesson, steps, total
        bg = make_background()
        d = ImageDraw.Draw(bg)
        title = lesson['title']
        size = 70
        for size in (70, 64, 58, 52):
            f = font(size)
            lines = wrap(d, title, f, 940)
            if len(lines) == 1:
                break
        y = 100
        for ln in lines[:3]:
            d.text(((W - tw(d, ln, f)) / 2, y), ln, font=f, fill=GOLD, stroke_width=4, stroke_fill=(30, 5, 10))
            y += int(size * 1.22)
        f2 = font(34, False)
        s = 'CYBERNOVA GAME  ·  Tiến Lên Miền Nam'
        d.text(((W - tw(d, s, f2)) / 2, y + 8), s, font=f2, fill=SOFT)
        f3 = font(38)
        d.text(((W - tw(d, CHANNEL_HANDLE, f3)) / 2, 1788), CHANNEL_HANDLE, font=f3, fill=GOLD)
        f4 = font(28, False)
        s4 = 'Chip ảo · chỉ để giải trí'
        d.text(((W - tw(d, s4, f4)) / 2, 1845), s4, font=f4, fill=(150, 160, 185))
        self.bg = bg
        self.hook_bg = make_hook_background()
        self.cap_cache = {}
        self.dummy = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        self.cap_font = font(56)

    def step_at(self, t):
        for s in self.steps:
            if s.start <= t < s.start + s.dur:
                return s
        return self.steps[-1]

    def caption(self, s, cur):
        key = (id(s), cur)
        if key in self.cap_cache:
            return self.cap_cache[key]
        f = self.cap_font
        d = self.dummy
        lines, line, wid = [], [], 0
        space = tw(d, ' ', f)
        for i, w in enumerate(s.words):
            ww = tw(d, w, f)
            if line and wid + space + ww > 900:
                lines.append(line)
                line, wid = [], 0
            wid += (space if line else 0) + ww
            line.append((i, w, ww))
        if line:
            lines.append(line)
        lh = 74
        bh = lh * len(lines) + 46
        im = Image.new('RGBA', (W - 100, bh), (0, 0, 0, 0))
        dd = ImageDraw.Draw(im, 'RGBA')
        dd.rounded_rectangle([0, 0, W - 101, bh - 1], radius=28, fill=(0, 0, 0, 135))
        y = 23
        for ln in lines:
            total = sum(w[2] for w in ln) + space * (len(ln) - 1)
            x = (W - 100 - total) / 2
            for i, w, ww in ln:
                col = GOLD if i == cur else WHITE
                dd.text((x, y), w, font=f, fill=col, stroke_width=3, stroke_fill=(0, 0, 0))
                x += ww + space
            y += lh
        self.cap_cache[key] = im
        return im

    def render(self, t):
        s = self.step_at(t)
        local = max(0.0, t - s.start)
        hook = s.kind == 'hook'
        frame = (self.hook_bg if hook else self.bg).copy()
        z, sx, sy = 1.0 + 0.05 * (local / max(0.5, s.dur)), 0.0, 0.0
        if not hook and local < 0.22:
            z += 0.10 * (1 - local / 0.22) ** 2
        if hook:
            amp = 20 * max(0.0, 1 - local / 0.45)
            sx, sy = amp * math.sin(local * 71), amp * math.cos(local * 83)
        elif 'impact' in s.fx and local < 0.4:
            amp = 14 * (1 - local / 0.4)
            sx, sy = amp * math.sin(local * 80), amp * math.cos(local * 67)
        if hook:
            self.draw_hook(frame, s, local, z, sx, sy)
        else:
            for it in s.items:
                draw_item(frame, it, local, z, sx, sy)
        if s.words:
            cur = 0
            for i, wt in enumerate(s.wtimes):
                if local >= wt:
                    cur = i
            if local < s.wtimes[0] - 0.02:
                cur = -1
            cap = self.caption(s, cur)
            p = min(1.0, local / 0.22)
            top = (1215 if hook else 1330) + (420 - cap.height) // 2 + int((1 - ease_out_cubic(p)) * 40)
            if p < 1:
                frame.paste(cap, (50, top), cap.getchannel('A').point(lambda v, a=p: int(v * a)))
            else:
                frame.paste(cap, (50, top), cap)
        d = ImageDraw.Draw(frame)
        y0 = 178 if hook else 38
        d.rounded_rectangle([40, y0, W - 40, y0 + 10], radius=5, fill=(70, 20, 28))
        d.rounded_rectangle([40, y0, 40 + max(12, int((W - 80) * t / self.total)), y0 + 10], radius=5, fill=GOLD)
        if local < 0.14 and not (hook and local < 0.05):
            a = (0.5 if hook else 0.30) * (1 - local / 0.14)
            frame.paste((255, 255, 255), (0, 0, W, H), Image.new('L', (W, H), int(255 * a)))
        return frame

    def draw_hook(self, frame, s, local, z, sx, sy):
        d = ImageDraw.Draw(frame)
        if 0.10 < local < 0.70:
            p = (local - 0.10) / 0.60
            r = 80 + 950 * ease_out_cubic(p)
            d.ellipse([W / 2 - r + sx, 760 - r + sy, W / 2 + r + sx, 760 + r + sy], outline=(255, 190, 70), width=max(2, int(16 * (1 - p))))
        y = 640
        for li, sp in enumerate(s.hook_sprites):
            q = local - 0.20 * li
            if q < 0:
                continue
            p = min(1.0, q / 0.22)
            scale = (1 + 0.28 * (1 - ease_out_cubic(p))) * (1 + 0.05 * (local / max(0.5, s.dur)))
            alpha = min(1.0, 0.8 + p)
            im = sp.resize((int(sp.width * scale), int(sp.height * scale)), Image.BILINEAR) if abs(scale - 1) > 0.01 else sp
            pos = (int(W / 2 - im.width / 2 + sx), int(y - im.height / 2 + sy))
            frame.paste(im, pos, im if alpha > 0.995 else im.getchannel('A').point(lambda v, a=alpha: int(v * a)))
            y += int(sp.height * 0.95)
        self.sparks(frame, local, 9, 300, 1400)
        if int(local * 3) % 2 == 0:
            f = font(40)
            msg = 'XEM HẾT NHÉ  ▼'
            d.text(((W - tw(d, msg, f)) / 2, H - 120), msg, font=f, fill=GOLD)

    def sparks(self, frame, local, seed, y_lo, y_hi):
        rnd = random.Random(seed)
        d = ImageDraw.Draw(frame)
        for _ in range(22):
            x = rnd.uniform(80, W - 80)
            y0 = rnd.uniform(y_lo, y_hi)
            sp = rnd.uniform(60, 190)
            r = rnd.uniform(3, 8)
            ph = rnd.uniform(0, 6)
            y = y_lo + ((y0 - y_lo) - local * sp) % (y_hi - y_lo)
            k = 0.5 + 0.5 * math.sin(local * 5 + ph)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, int(190 + 50 * k), int(60 + 100 * k)))


def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode != 0:
        raise RuntimeError('command failed: ' + ' '.join(cmd[:6]) + '...\n' + r.stderr.decode('utf-8', 'ignore')[-1500:])
    return r.stdout.decode('utf-8', 'ignore')


def audio_seconds(path):
    return float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', path]).strip())


def detect_encoder():
    """Auto-detects available hardware H.264 encoder (NVENC / QSV / AMF) with libx264 fallback."""
    candidates = [
        ('h264_nvenc', ['-c:v', 'h264_nvenc', '-preset', 'p4', '-cq', '21']),
        ('h264_qsv', ['-c:v', 'h264_qsv', '-global_quality', '22']),
        ('h264_amf', ['-c:v', 'h264_amf', '-quality', 'balanced']),
    ]
    for name, flags in candidates:
        test_cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'nullsrc=s=256x256:d=0.1:r=30'] + flags + ['-f', 'null', '-']
        r = subprocess.run(test_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            return name, flags
    return 'libx264', ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20']


def trim_silence(mp3_path):
    """Reverse-silence stripping to guarantee zero trailing padding and seamless snap loops."""
    trimmed = mp3_path + '.trim.mp3'
    af = (
        'silenceremove=start_periods=1:start_duration=0.01:start_threshold=-45dB,'
        'areverse,'
        'silenceremove=start_periods=1:start_duration=0.02:start_threshold=-45dB,'
        'areverse'
    )
    r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', mp3_path, '-af', af, trimmed], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r.returncode == 0 and os.path.exists(trimmed) and os.path.getsize(trimmed) > 400:
        os.replace(trimmed, mp3_path)
    elif os.path.exists(trimmed):
        os.remove(trimmed)


VOICE_LOG = os.path.join(HERE, 'voice_log.txt')
EDGE_BROKEN = False


def log_voice(msg):
    try:
        with open(VOICE_LOG, 'a', encoding='utf-8') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M:%S  ') + msg + '\n')
    except Exception:
        pass


async def edge_voice(text, path, voice, rate):
    import edge_tts
    try:
        com = edge_tts.Communicate(text, voice, rate=rate, boundary='WordBoundary')
    except TypeError:
        com = edge_tts.Communicate(text, voice, rate=rate)
    tokens = []
    with open(path, 'wb') as f:
        async for ch in com.stream():
            if ch['type'] == 'audio':
                f.write(ch['data'])
            elif ch['type'] == 'WordBoundary':
                tokens.append((ch['offset'] / 1e7, ch['text']))
    if not os.path.exists(path) or os.path.getsize(path) < 800:
        raise RuntimeError('the voice service returned no audio')
    return tokens


def gtts_voice(text, path):
    from gTTS import gTTS
    gTTS(text, lang='vi').save(path)
    if not os.path.exists(path) or os.path.getsize(path) < 800:
        raise RuntimeError('gTTS returned no audio')
    return []


def windows_voice(text, path):
    if os.name != 'nt':
        raise RuntimeError('not Windows')
    wav = path + '.wav'
    txt = path + '.txt'
    with open(txt, 'w', encoding='utf-8') as f:
        f.write(text)
    ps = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'vi*' } | Select-Object -First 1; "
          "if (-not $v) { Write-Error 'no Vietnamese Windows voice'; exit 3 }; $s.SelectVoice($v.VoiceInfo.Name); "
          "$s.SetOutputToWaveFile('%s'); $s.Speak([IO.File]::ReadAllText('%s', [Text.Encoding]::UTF8)); $s.Dispose()" % (wav.replace("'", "''"), txt.replace("'", "''")))
    r = subprocess.run(['powershell', '-NoProfile', '-Command', ps], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(wav):
        raise RuntimeError('Windows voice: ' + (r.stderr or 'failed').strip()[:120])
    run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, path])
    return []


async def make_voice(text, path, voice, rate):
    if os.environ.get('TL_FAKE_VOICE'):
        run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=%.2f' % est_seconds(text), '-filter:a', 'volume=0.05', path])
        return []
    global EDGE_BROKEN
    errors = []
    for _ in range(0 if EDGE_BROKEN else 2):
        try:
            tokens = await asyncio.wait_for(edge_voice(text, path, voice, rate), 25)
            trim_silence(path)
            return tokens
        except Exception as e:
            errors.append('edge-tts: ' + (str(e).strip().replace('\n', ' ')[:200] or 'timed out'))
            log_voice(errors[-1])
            await asyncio.sleep(1)
    else:
        if not EDGE_BROKEN and errors:
            EDGE_BROKEN = True
    for name, fn in (('gTTS', gtts_voice), ('Windows voice', windows_voice)):
        try:
            tokens = fn(text, path)
            trim_silence(path)
            log_voice('used the %s fallback' % name)
            print('   (Microsoft voice failed, using the %s instead)' % name)
            return tokens
        except Exception as e:
            errors.append('%s: %s' % (name, str(e).strip().replace('\n', ' ')[:200]))
            log_voice(errors[-1])
    raise RuntimeError(' | '.join(errors[-3:]))


def collect_voice(lesson, voice, rate, tmp):
    texts = ([lesson['hook']['say']] if lesson.get('hook') else []) + [s['say'] for s in lesson['steps']]
    infos, files = [], []
    for i, tx in enumerate(texts):
        mp3 = os.path.join(tmp, f'v{i}.mp3')
        print('   voice %d/%d ...' % (i + 1, len(texts)), flush=True)
        tokens = asyncio.run(make_voice(tx, mp3, voice, rate))
        infos.append({'dur': audio_seconds(mp3), 'tokens': tokens})
        files.append(mp3)
    return infos, files


def build_short(lesson, cfg, outdir, voice_on, voice, rate, tmp):
    t_start = time.time()
    infos, files = (None, [])
    if voice_on:
        try:
            infos, files = collect_voice(lesson, voice, rate, tmp)
        except Exception as e:
            print('\n   [!] NO VOICE: every voice service failed, so this video was NOT made (it would be silent).')
            print('       Reason: %s' % str(e)[:300])
            raise SystemExit(3)
    t_voice = time.time() - t_start
    steps, total = plan_lesson(lesson, cfg, infos)
    seed = zlib.crc32(lesson['id'].encode('utf-8'))
    wav = None
    if HAVE_AUDIO:
        parts = [(s.start + 0.03, fx_audio.decode(f)) for s, f in zip(steps, files)]
        wav = os.path.join(tmp, 'mix.wav')
        fx_audio.mix(parts, sound_events(steps), total, os.path.join(HERE, 'music'), seed, wav)
    else:
        print('   (numpy is not installed: making the video without music and sound effects.)')
    t_audio = time.time() - t_start - t_voice
    os.makedirs(outdir, exist_ok=True)
    final = os.path.join(outdir, f"{lesson['id']}.mp4")
    r = Renderer(lesson, steps, total)
    n = int(math.ceil(total * FPS))
    enc_name, enc_flags = detect_encoder()
    print(f'   encoding with {enc_name} ...', flush=True)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-']
    if wav:
        cmd += ['-i', wav, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '160k']
    else:
        cmd += ['-f', 'lavfi', '-i', 'anullsrc=r=44100:cl=stereo', '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '96k']
    cmd += enc_flags + ['-pix_fmt', 'yuv420p', '-shortest', '-movflags', '+faststart', final]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        for k in range(n):
            proc.stdin.write(r.render(k / FPS).tobytes())
            if k % 150 == 0:
                print('   ... %d%%' % (100 * k // n), end='\r')
        proc.stdin.close()
    finally:
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError('ffmpeg could not write the video')
    seconds = audio_seconds(final)

    base_tags = [
        'Shorts', 'TienLen', 'Tiến Lên', 'Tiến Lên Miền Nam', 'game bài',
        'cách chơi tiến lên', 'luật tiến lên', 'mẹo chơi tiến lên',
        'chặt heo', 'tới trắng', 'game bài chiến thuật', 'CybernovaGame'
    ]
    tags = list(dict.fromkeys(base_tags + lesson.get('hashtags', [])))[:15]

    raw_title = lesson['title'].strip()
    if '#shorts' not in raw_title.lower():
        clean_title = f"{raw_title} #tienlenmiennam #shorts"
    else:
        clean_title = raw_title

    first = lesson['hook']['say'] if lesson.get('hook') else lesson['steps'][0]['say']
    desc_hashtags = ' '.join('#' + t.replace(' ', '') for t in ['tienlenmiennam', 'gamebai', 'shorts'] + lesson.get('hashtags', [])[:2])
    desc = (
        f"{first}\n\n"
        f"▶ Chơi Tiến Lên Nova miễn phí: {GAME_LINK}\n"
        f"(Link cũng có ở phần Giới thiệu kênh {CHANNEL_HANDLE})\n"
        f"(Chip ảo · chỉ để giải trí · không đổi thưởng)\n\n"
        f"{desc_hashtags}"
    )

    meta = {
        'title': clean_title,
        'description': desc,
        'tags': tags,
        'categoryId': '20',
        'seconds': round(seconds, 1),
        'lesson': lesson['id'],
        'voice': bool(files)
    }
    with open(final.replace('.mp4', '.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print('   time: voice %.0f s, music and effects %.0f s, drawing and encoding %.0f s, total %.0f s' % (t_voice, t_audio, time.time() - t_start - t_voice - t_audio, time.time() - t_start))
    return final, seconds, bool(files)


# ===================================================================================================
#  "ĐỐ BẠN" WHAT-IF SHORTS: a never-ending supply of situations.
#  14 kinds of situation x random cards = thousands of different videos. Every video:
#  hook question -> the cards -> "A or B? comment below" -> the ANSWER with the reason.
#  Answers follow the rules of the game (Tiến Lên Nova, southern rules). Words: "điểm", never "cược"/"tiền".
# ===================================================================================================
WI_RANKS = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']
WI_SUITS = ['♠', '♣', '♦', '♥']                      # low -> high
WI_SUIT_NAME = {'♠': 'bích', '♣': 'chuồn', '♦': 'rô', '♥': 'cơ'}
WI_RED = ('♦', '♥')


def _wi_val(card):
    return WI_RANKS.index(card[:-1]) * 4 + WI_SUITS.index(card[-1])


class _Deck:
    """Hands out distinct cards for one scenario."""
    def __init__(self, rnd):
        self.rnd, self.used = rnd, set()

    def take(self, rank, suit=None):
        suits = [suit] if suit else self.rnd.sample(WI_SUITS, 4)
        for s in suits:
            c = rank + s
            if c not in self.used:
                self.used.add(c)
                return c
        raise ValueError('no card left: ' + rank)

    def pair(self, rank):
        return [self.take(rank), self.take(rank)]

    def low_single(self, avoid=()):
        r = self.rnd.choice([x for x in WI_RANKS[:6] if x not in avoid])
        return self.take(r)


def _say_card(c):
    r, s = c[:-1], c[-1]
    r = {'J': 'J', 'Q': 'Q', 'K': 'K', 'A': 'Át', '2': 'heo'}.get(r, r)
    return ('heo ' + WI_SUIT_NAME[s]) if r == 'heo' else (r + ' ' + WI_SUIT_NAME[s])


def _say_rank(r):
    return {'A': 'Át', '2': 'heo'}.get(r, r)


def _sorted(cards):
    return sorted(cards, key=_wi_val)


def _three_pairs(d, rnd, avoid_top=11):
    i = rnd.randint(0, avoid_top - 3)          # pairs i, i+1, i+2 (never reaching the 2)
    return [c for k in range(3) for c in d.pair(WI_RANKS[i + k])], WI_RANKS[i]


def _four_pairs(d, rnd):
    i = rnd.randint(0, 8)
    return [c for k in range(4) for c in d.pair(WI_RANKS[i + k])], WI_RANKS[i]


def _quad(d, rank):
    return [d.take(rank, s) for s in WI_SUITS]


# Each builder returns: key, q (short question for the title), hook (2 short lines), say_hook,
# groups [(label, cards)], say_cards, opts (A, B), ans 'A'/'B', reveal (2-3 short lines), say_ans,
# check: facts for the rules check (verified against the game engine by the test script).
def _wi_chop_red_two(rnd):
    d = _Deck(rnd)
    two = d.take('2', rnd.choice(WI_RED))
    mine, low = _three_pairs(d, rnd)
    extra = [d.low_single(avoid=(low,)) for _ in range(2)]
    return dict(key='chop_red_two', q='Có ba đôi thông, chặt heo đỏ hay để dành?',
                hook=['HEO ĐỎ!', 'CHẶT HAY GIỮ?'],
                say_hook='Đối thủ vừa đánh %s. Bạn có ba đôi thông. Chặt hay để dành?' % _say_card(two),
                groups=[('ĐỐI THỦ VỪA ĐÁNH', [two]), ('BÀI CỦA BẠN (TỚI LƯỢT BẠN)', _sorted(mine + extra))],
                say_cards='Tới lượt bạn. Ba đôi thông của bạn chặt được một con heo.',
                opts=('A. CHẶT NGAY', 'B. ĐỂ DÀNH'), ans='A',
                reveal=['ĐÁP ÁN: A', 'Heo đỏ bị chặt mất 8 điểm', 'Bạn còn giành quyền đi'],
                say_ans='Đáp án A! Heo đỏ bị chặt mất tám điểm, và bạn còn giành được quyền đi tiếp. Thời cơ như vậy không nên bỏ.',
                check=[('beats', mine, [two], True)])


def _wi_black_before_red(rnd):
    d = _Deck(rnd)
    ace = d.take('A')
    black, red = d.take('2', rnd.choice(('♠', '♣'))), d.take('2', rnd.choice(WI_RED))
    rest = [d.low_single() for _ in range(3)]
    return dict(key='black_before_red', q='Chặn Át bằng heo đen hay heo đỏ?',
                hook=['HEO ĐEN', 'HAY HEO ĐỎ?'],
                say_hook='Đối thủ đánh %s. Bạn có hai con heo, một đen một đỏ. Đánh con nào?' % _say_card(ace),
                groups=[('ĐỐI THỦ VỪA ĐÁNH', [ace]), ('BÀI CỦA BẠN', _sorted([black, red] + rest))],
                say_cards='Hai con heo đều chặn được Át. Nhưng bàn bên kia vẫn còn nhiều bài, có thể đang giữ hàng.',
                opts=('A. ĐÁNH ' + black, 'B. ĐÁNH ' + red), ans='A',
                reveal=['ĐÁP ÁN: A', 'Bị chặt: heo đen mất 4', 'heo đỏ mất tới 8 điểm'],
                say_ans='Đáp án A! Nếu bị chặt, heo đen chỉ mất bốn điểm, heo đỏ mất tới tám. Giữ heo đỏ, con lớn hơn, cho sau.',
                check=[('beats', [black], [ace], True), ('beats', [red], [black], True)])


def _wi_one_card_left(rnd):
    d = _Deck(rnd)
    single = d.take(rnd.choice(WI_RANKS[:5]))
    pr = rnd.choice([r for r in WI_RANKS[5:11]])
    pair = d.pair(pr)
    other = [d.take(rnd.choice(WI_RANKS[6:11])) for _ in range(2)]
    return dict(key='one_card_left', q='Đối thủ còn 1 lá: đi lẻ hay đi đôi?',
                hook=['CÒN 1 LÁ!', 'ĐI GÌ BÂY GIỜ?'],
                say_hook='Đối thủ chỉ còn đúng một lá. Bạn được đi trước. Đi lá lẻ hay đi đôi?',
                groups=[('ĐỐI THỦ CÒN', ['?']), ('BÀI CỦA BẠN (BẠN ĐI TRƯỚC)', _sorted([single] + pair + other))],
                say_cards='Bạn có một lá %s lẻ và một đôi %s.' % (_say_card(single), _say_rank(pr)),
                opts=('A. ĐI LẺ ' + single, 'B. ĐI ĐÔI ' + pr), ans='B',
                reveal=['ĐÁP ÁN: B', 'Người còn 1 lá không', 'chặn được đôi!'],
                say_ans='Đáp án B! Người còn một lá không thể chặn một đôi. Đi lẻ lúc này là dâng chiến thắng cho họ.',
                check=[('type', pair, 'PAIR')])


def _wi_last_two_cards(rnd):
    d = _Deck(rnd)
    two = d.take('2')
    low = d.take(rnd.choice(WI_RANKS[:6]))
    return dict(key='last_two_cards', q='Còn heo và 1 lá nhỏ: đánh lá nào trước?',
                hook=['CÒN 2 LÁ:', 'ĐÁNH LÁ NÀO?'],
                say_hook='Bạn còn hai lá: %s và %s. Đối thủ còn một lá. Bạn đi trước, đánh lá nào?' % (_say_card(two), _say_card(low)),
                groups=[('ĐỐI THỦ CÒN', ['?']), ('BÀI CỦA BẠN (BẠN ĐI TRƯỚC)', _sorted([two, low]))],
                say_cards='Hai lá, hai lựa chọn. Đánh sai là về bét.',
                opts=('A. ĐÁNH ' + low + ' TRƯỚC', 'B. ĐÁNH HEO TRƯỚC'), ans='B',
                reveal=['ĐÁP ÁN: B', 'Heo giành lại lượt', 'rồi bạn về bằng ' + low],
                say_ans='Đáp án B! Đánh heo trước để giành lượt, rồi về bằng lá nhỏ. Đi lá nhỏ trước, đối thủ chặn rồi về, bạn còn bị thối heo.',
                check=[])


def _wi_quad_vs_pair_twos(rnd):
    d = _Deck(rnd)
    p2 = [d.take('2', s) for s in rnd.sample(WI_SUITS, 2)]
    q = _quad(d, rnd.choice(WI_RANKS[2:11]))
    return dict(key='quad_vs_pair_twos', q='Tứ quý có chặt được đôi heo không?',
                hook=['TỨ QUÝ', 'CHẶT ĐÔI HEO?'],
                say_hook='Đối thủ đánh đôi heo. Bạn đang cầm tứ quý. Chặt được không?',
                groups=[('ĐỐI THỦ VỪA ĐÁNH', _sorted(p2)), ('BÀI CỦA BẠN', q)],
                say_cards='Tứ quý chặt được một con heo. Còn đôi heo thì sao?',
                opts=('A. CHẶT ĐƯỢC', 'B. KHÔNG CHẶT ĐƯỢC'), ans='B',
                reveal=['ĐÁP ÁN: B', 'Đôi heo chỉ bị chặt', 'bằng BỐN ĐÔI THÔNG'],
                say_ans='Đáp án B! Theo luật miền Nam, đôi heo chỉ bị chặt bằng bốn đôi thông. Tứ quý phải bỏ lượt.',
                check=[('beats', q, p2, False)])


def _wi_three_pairs_vs_pair_twos(rnd):
    d = _Deck(rnd)
    p2 = [d.take('2', s) for s in rnd.sample(WI_SUITS, 2)]
    mine, _ = _three_pairs(d, rnd)
    return dict(key='three_pairs_vs_pair_twos', q='Ba đôi thông có chặt được đôi heo?',
                hook=['BA ĐÔI THÔNG', 'CHẶT ĐÔI HEO?'],
                say_hook='Đối thủ đánh đôi heo. Bạn có ba đôi thông. Chặt được không?',
                groups=[('ĐỐI THỦ VỪA ĐÁNH', _sorted(p2)), ('BÀI CỦA BẠN', _sorted(mine))],
                say_cards='Ba đôi thông chặt được một con heo. Nhưng đây là đôi heo.',
                opts=('A. CHẶT ĐƯỢC', 'B. KHÔNG CHẶT ĐƯỢC'), ans='B',
                reveal=['ĐÁP ÁN: B', 'Ba đôi thông chỉ chặt', 'được MỘT con heo'],
                say_ans='Đáp án B! Ba đôi thông chỉ chặt được một con heo. Muốn chặt đôi heo, bạn cần bốn đôi thông.',
                check=[('beats', mine, p2, False), ('beats', mine, [p2[0]], True)])


def _wi_four_pairs_out_of_turn(rnd):
    d = _Deck(rnd)
    two = d.take('2')
    mine, _ = _four_pairs(d, rnd)
    return dict(key='four_pairs_out_of_turn', q='Chưa tới lượt mà có bốn đôi thông: chặt được không?',
                hook=['CHƯA TỚI LƯỢT', 'CHẶT ĐƯỢC KHÔNG?'],
                say_hook='Đối thủ vừa đánh %s, nhưng chưa tới lượt bạn. Bạn có bốn đôi thông. Chặt ngay được không?' % _say_card(two),
                groups=[('ĐỐI THỦ VỪA ĐÁNH', [two]), ('BÀI CỦA BẠN (CHƯA TỚI LƯỢT)', _sorted(mine))],
                say_cards='Ba đôi thông và tứ quý phải chờ tới lượt. Bốn đôi thông thì khác.',
                opts=('A. CHẶT NGAY', 'B. PHẢI CHỜ TỚI LƯỢT'), ans='A',
                reveal=['ĐÁP ÁN: A', 'Bốn đôi thông được chặt', 'cả khi chưa tới lượt'],
                say_ans='Đáp án A! Bốn đôi thông mạnh đến mức được chặt ngay cả khi chưa tới lượt. Chặt liền kẻo người khác giành mất.',
                check=[('beats', mine, [two], True), ('type', mine, '4PAIR_STRAIGHT')])


def _wi_quad_on_quad(rnd):
    d = _Deck(rnd)
    lo = rnd.randint(1, 9)
    hi = rnd.randint(lo + 1, 11)
    theirs, mine = _quad(d, WI_RANKS[lo]), _quad(d, WI_RANKS[hi])
    return dict(key='quad_on_quad', q='Tứ quý %s chặt chồng tứ quý %s được không?' % (WI_RANKS[hi], WI_RANKS[lo]),
                hook=['CHẶT CHỒNG', 'TỨ QUÝ?'],
                say_hook='Đối thủ vừa dùng tứ quý %s chặt heo. Tới lượt bạn, bạn có tứ quý %s. Chặt chồng được không?' % (_say_rank(WI_RANKS[lo]), _say_rank(WI_RANKS[hi])),
                groups=[('ĐỐI THỦ VỪA CHẶT BẰNG', theirs), ('BÀI CỦA BẠN (TỚI LƯỢT BẠN)', mine)],
                say_cards='Tứ quý gặp tứ quý. Ai lớn hơn?',
                opts=('A. CHẶT CHỒNG ĐƯỢC', 'B. KHÔNG ĐƯỢC'), ans='A',
                reveal=['ĐÁP ÁN: A', 'Tứ quý lớn chặt tứ quý nhỏ', 'Chặt chồng ăn 6 điểm'],
                say_ans='Đáp án A! Tứ quý lớn chặt được tứ quý nhỏ. Đây là chặt chồng, ăn sáu điểm, và bạn giành quyền đi.',
                check=[('beats', mine, theirs, True)])


def _wi_compare_pairs(rnd):
    d = _Deck(rnd)
    r = rnd.choice(WI_RANKS[:12])
    s = WI_SUITS[:]
    rnd.shuffle(s)
    a, b = [r + s[0], r + s[1]], [r + s[2], r + s[3]]
    win = 'A' if max(map(_wi_val, a)) > max(map(_wi_val, b)) else 'B'
    top = max(a + b, key=_wi_val)
    return dict(key='compare_pairs', q='Hai đôi %s, đôi nào lớn hơn?' % r,
                hook=['HAI ĐÔI %s' % r, 'ĐÔI NÀO LỚN?'],
                say_hook='Hai đôi %s giống hệt nhau về số. Đôi nào lớn hơn?' % _say_rank(r),
                groups=[('ĐÔI A', _sorted(a)), ('ĐÔI B', _sorted(b))],
                say_cards='Cùng số thì phải nhìn chất bài.',
                opts=('A. ĐÔI A', 'B. ĐÔI B'), ans=win,
                reveal=['ĐÁP ÁN: ' + win, 'Đôi có ' + top + ' thắng', 'Bích < Chuồn < Rô < Cơ'],
                say_ans='Đáp án %s! Đôi được so bằng lá lớn nhất. Đôi có %s thắng. Thứ tự chất: bích, chuồn, rô, cơ.' % (win, _say_card(top)),
                check=[('beats', a if win == 'A' else b, b if win == 'A' else a, True)])


def _wi_compare_straights(rnd):
    i = rnd.randint(0, 8)
    n = 3
    ranks = WI_RANKS[i:i + n]
    sa, sb = rnd.sample(WI_SUITS, 2)
    a = [ranks[0] + rnd.choice(WI_SUITS), ranks[1] + rnd.choice(WI_SUITS), ranks[2] + sa]
    b = [ranks[0] + rnd.choice([x for x in WI_SUITS if ranks[0] + x != a[0]]), ranks[1] + rnd.choice([x for x in WI_SUITS if ranks[1] + x != a[1]]), ranks[2] + sb]
    win = 'A' if _wi_val(a[2]) > _wi_val(b[2]) else 'B'
    top = a[2] if win == 'A' else b[2]
    label = '-'.join(ranks)
    return dict(key='compare_straights', q='Hai sảnh %s, sảnh nào thắng?' % label,
                hook=['HAI SẢNH', 'AI THẮNG?'],
                say_hook='Hai sảnh %s, cùng số y hệt. Sảnh nào thắng?' % ' '.join(_say_rank(x) for x in ranks),
                groups=[('SẢNH A', a), ('SẢNH B', b)],
                say_cards='Cùng số thì nhìn lá nào?',
                opts=('A. SẢNH A', 'B. SẢNH B'), ans=win,
                reveal=['ĐÁP ÁN: ' + win, 'Chỉ so lá CAO NHẤT', top + ' lớn hơn'],
                say_ans='Đáp án %s! Sảnh chỉ so lá cao nhất. %s lớn hơn, các lá khác không quan trọng.' % (win, _say_card(top)),
                check=[('beats', a if win == 'A' else b, b if win == 'A' else a, True)])


def _wi_straight_with_two(rnd):
    opts = [['K', 'A', '2'], ['Q', 'K', 'A', '2'], ['J', 'Q', 'K', 'A', '2'], ['A', '2', '3'], ['2', '3', '4']]
    ranks = rnd.choice(opts)
    d = _Deck(rnd)
    cards = [d.take(r) for r in ranks]
    label = '-'.join(ranks)
    return dict(key='straight_with_two', q='%s có phải là sảnh không?' % label,
                hook=[label, 'LÀ SẢNH KHÔNG?'],
                say_hook='%s. Đây có phải là một sảnh không?' % ' '.join('heo' if r == '2' else ('Át' if r == 'A' else r) for r in ranks),
                groups=[('BỘ BÀI NÀY', cards)],
                say_cards='Nhiều người chơi lâu năm vẫn trả lời sai câu này.',
                opts=('A. LÀ SẢNH', 'B. KHÔNG PHẢI SẢNH'), ans='B',
                reveal=['ĐÁP ÁN: B', 'Heo không bao giờ', 'nằm trong sảnh'],
                say_ans='Đáp án B! Trong Tiến Lên, heo không bao giờ nằm trong sảnh. Sảnh cao nhất kết thúc ở Át.',
                check=[('type', cards, None)])


def _wi_six_pairs(rnd):
    d = _Deck(rnd)
    ranks = rnd.sample(WI_RANKS, 7)
    cards = [c for r in ranks[:6] for c in d.pair(r)] + [d.take(ranks[6])]
    return dict(key='six_pairs', q='Chia bài có sáu đôi: thắng trắng không?',
                hook=['SÁU ĐÔI', 'THẮNG TRẮNG?'],
                say_hook='Vừa chia bài, bạn có sáu đôi. Bạn thắng luôn hay vẫn phải đánh?',
                groups=[('BÀI VỪA CHIA', _sorted(cards))],
                say_cards='Đếm kỹ nhé: một, hai, ba, bốn, năm, sáu đôi.',
                opts=('A. TỚI TRẮNG', 'B. VẪN PHẢI ĐÁNH'), ans='A',
                reveal=['ĐÁP ÁN: A', 'Sáu đôi là TỚI TRẮNG', 'Mỗi người trả 4 điểm'],
                say_ans='Đáp án A! Sáu đôi là tới trắng, thắng ngay khi chia bài. Mỗi người còn lại trả bốn điểm.',
                check=[('pairs', cards, 6)])


def _wi_dragon(rnd):
    d = _Deck(rnd)
    run = [d.take(r) for r in WI_RANKS[:12]]
    cards = run + [d.take(rnd.choice(WI_RANKS))]
    return dict(key='dragon_straight', q='Có đủ từ 3 đến Át: thắng trắng không?',
                hook=['SẢNH RỒNG!', 'THẮNG LUÔN?'],
                say_hook='Vừa chia bài, bạn có đủ các lá từ ba đến Át. Thắng luôn được không?',
                groups=[('BÀI VỪA CHIA', _sorted(cards))],
                say_cards='Ba, bốn, năm, sáu, bảy, tám, chín, mười, J, Q, K, Át.',
                opts=('A. TỚI TRẮNG', 'B. VẪN PHẢI ĐÁNH'), ans='A',
                reveal=['ĐÁP ÁN: A', 'Sảnh rồng 3 đến Át', 'là TỚI TRẮNG'],
                say_ans='Đáp án A! Đủ mười hai lá từ ba đến Át là sảnh rồng, tới trắng ngay khi chia bài.',
                check=[('type', _sorted(run), 'STRAIGHT')])


def _wi_avoid_cong(rnd):
    d = _Deck(rnd)
    low = d.take(rnd.choice(WI_RANKS[:4]))
    mid_r = rnd.choice(WI_RANKS[5:10])
    mid = d.take(mid_r)
    rest = []
    for _ in range(4):
        r = rnd.choice([x for x in WI_RANKS[:12] if x != mid_r])
        try:
            rest.append(d.take(r))
        except ValueError:
            pass
    return dict(key='avoid_cong', q='Chưa đánh lá nào, đối thủ còn 2 lá: bỏ hay đánh?',
                hook=['NGUY CƠ', 'BỊ CÓNG!'],
                say_hook='Bạn chưa đánh lá nào, mà đối thủ chỉ còn hai lá. Họ vừa đánh %s. Bỏ lượt hay đánh?' % _say_card(low),
                groups=[('ĐỐI THỦ VỪA ĐÁNH', [low]), ('BÀI CỦA BẠN (CHƯA ĐÁNH LÁ NÀO)', _sorted([mid] + rest))],
                say_cards='Bạn có thể chặn bằng lá %s.' % _say_card(mid),
                opts=('A. BỎ LƯỢT GIỮ BÀI', 'B. ĐÁNH ' + mid + ' NGAY'), ans='B',
                reveal=['ĐÁP ÁN: B', 'Chưa ra lá nào mà họ về', 'là bạn bị CÓNG!'],
                say_ans='Đáp án B! Nếu họ về khi bạn chưa đánh lá nào, bạn bị cóng và phạt rất nặng. Ra một lá là thoát cóng.',
                check=[('beats', [mid], [low], True)])


WHATIF_BUILDERS = [_wi_chop_red_two, _wi_black_before_red, _wi_one_card_left, _wi_last_two_cards, _wi_quad_vs_pair_twos,
                   _wi_three_pairs_vs_pair_twos, _wi_four_pairs_out_of_turn, _wi_quad_on_quad, _wi_compare_pairs,
                   _wi_compare_straights, _wi_straight_with_two, _wi_six_pairs, _wi_dragon, _wi_avoid_cong]


def whatif_lesson(sc):
    """Turns a scenario into a lesson the renderer understands."""
    sig = '|'.join(c for _, cards in sc['groups'] for c in cards) + '|' + sc['ans']
    sid = 'whatif_%s_%06x' % (sc['key'], zlib.crc32(sig.encode('utf-8')) & 0xffffff)
    groups = [{'label': lbl, 'cards': cards} for lbl, cards in sc['groups'] if cards != ['?']]
    if len(groups) < len(sc['groups']):                      # "the opponent has 1 card": shown as a face-down card
        groups.insert(0, {'label': sc['groups'][0][0] + ' 1 LÁ', 'cards': ['BACK']})
    ans_i = 0 if sc['ans'] == 'A' else 1
    return {
        'id': sid,
        'title': 'Đố bạn: ' + sc['q'],
        'hashtags': ['DoBanTienLen', 'MeoChoiTienLen', 'CybernovaGame'],
        'hook': {'say': sc['say_hook'], 'lines': sc['hook']},
        'steps': [
            {'say': sc['say_cards'], 'scene': {'type': 'cards', 'groups': groups}},
            {'say': 'Bạn chọn A hay B? Bình luận ngay, đáp án ở đây!',
             'scene': {'type': 'bullets', 'lines': [sc['opts'][0], sc['opts'][1], '= A HAY B? BÌNH LUẬN!']}},
            {'say': sc['say_ans'], 'fx': ['impact'],
             'scene': {'type': 'bullets', 'lines': [sc['reveal'][0] + '  ✔', sc['opts'][ans_i]] + sc['reveal'][1:]}},
        ],
        '_scenario': sc,
    }


def generate_procedural_scenario(made=None, rnd=None):
    """A new what-if video that was never made before. Rotates through the kinds of situation
    (the least-used kind first), then picks fresh random cards until the video is new."""
    made = made or {}
    rnd = rnd or random.Random()
    used = {}
    for k in made:
        if k.startswith('whatif_'):
            kind = k[len('whatif_'):].rsplit('_', 1)[0]
            used[kind] = used.get(kind, 0) + 1
    probe = {b: b(random.Random(0))['key'] for b in WHATIF_BUILDERS}
    least = min(used.get(probe[b], 0) for b in WHATIF_BUILDERS)
    pool = [b for b in WHATIF_BUILDERS if used.get(probe[b], 0) == least]
    rnd.shuffle(pool)
    rest = sorted(WHATIF_BUILDERS, key=lambda b: (used.get(probe[b], 0), rnd.random()))   # if a kind has run out of new cards, the next least-used kind
    for b in pool + rest:
        for _ in range(60):
            lesson = whatif_lesson(b(rnd))
            if lesson['id'] not in made:
                return lesson
    raise RuntimeError('could not find a new scenario')


def preview(lesson, cfg, outdir):
    steps, total = plan_lesson(lesson, cfg, None)
    r = Renderer(lesson, steps, total)
    times = [('hook', min(steps[0].start + 0.45, total - 0.1))]
    if len(steps) > 1:
        times.append(('scene', min(steps[1].start + 1.2, total - 0.1)))
    if len(steps) > 2:
        times.append(('end', min(steps[-1].start + steps[-1].dur * 0.6, total - 0.1)))
    os.makedirs(outdir, exist_ok=True)
    for name, t in times:
        r.render(max(0.0, t)).save(os.path.join(outdir, f"{lesson['id']}_{name}.png"))


MADE_HISTORY = os.path.join(HERE, 'made_history.txt')     # permanent backup: one line per video, never shortened


def read_made():
    """Every video ever made, so nothing is made twice. Combines three memories:
    made_lessons.json, the permanent made_history.txt, and the video files in output_renders."""
    made = {}
    try:
        made.update(json.load(open(MADE_LOG, encoding='utf-8')))
    except Exception:
        pass
    try:
        for ln in open(MADE_HISTORY, encoding='utf-8'):
            parts = ln.rstrip('\n').split('\t')
            if len(parts) >= 2 and parts[1] and parts[1] not in made:
                made[parts[1]] = parts[0] + ' (history)'
    except Exception:
        pass
    try:
        for root, _dirs, files in os.walk(os.path.join(HERE, 'output_renders')):
            for fn in files:
                if fn.endswith('.mp4') and fn[:-4] not in made:
                    made[fn[:-4]] = 'found in output_renders'
    except Exception:
        pass
    try:                                            # anything not yet in the permanent history (e.g. the first 10 lessons) is copied there
        known = set()
        if os.path.exists(MADE_HISTORY):
            known = {ln.split('\t')[1] for ln in open(MADE_HISTORY, encoding='utf-8') if ln.count('\t') >= 1}
        missing = [k for k in made if k not in known]
        if missing:
            with open(MADE_HISTORY, 'a', encoding='utf-8') as f:
                for k in missing:
                    f.write('%s\t%s\t%s\n' % (made[k], k, ''))
    except Exception:
        pass
    return made


def write_made(d, new_id=None, title=''):
    tmp = MADE_LOG + '.tmp'
    json.dump(d, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.replace(tmp, MADE_LOG)                       # written in one go, so a crash cannot leave a half-written file
    if new_id:
        with open(MADE_HISTORY, 'a', encoding='utf-8') as f:
            f.write('%s\t%s\t%s\n' % (d.get(new_id, ''), new_id, title))


def check():
    ok = True
    for tool in ('ffmpeg', 'ffprobe'):
        p = shutil.which(tool)
        print(('  OK   ' if p else '  MISSING ') + tool + (' (' + p + ')' if p else '  (install ffmpeg and add it to PATH)'))
        ok &= bool(p)
    enc_name, _ = detect_encoder()
    print('  OK   video encoder:', enc_name)
    print('  OK   pillow')
    print('  OK   numpy' if HAVE_AUDIO else '  MISSING numpy')
    print('  OK   fonts' if os.path.exists(os.path.join(HERE, 'fonts', 'DejaVuSans-Bold.ttf')) else '  MISSING fonts folder')
    return ok and HAVE_AUDIO


def main():
    ap = argparse.ArgumentParser(description='Tiến Lên Shorts maker')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--lesson', action='append')
    ap.add_argument('--preview', action='store_true')
    ap.add_argument('--no-voice', action='store_true')
    ap.add_argument('--reset-log', action='store_true')
    ap.add_argument('--voice', default=DEFAULT_VOICE)
    ap.add_argument('--rate', default='+0%')
    ap.add_argument('--out')
    ap.add_argument('--whatif', action='store_true', help='make a new "Đố bạn" what-if video now')
    ap.add_argument('--preview-whatif', type=int, metavar='N', help='save pictures of N new what-if videos (nothing is recorded)')
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(HERE, 'lessons.json'), encoding='utf-8'))
    lessons = {l['id']: l for l in cfg['lessons']}
    made = read_made()
    if a.list:
        for l in cfg['lessons']:
            print('  %-14s %s  %s' % (l['id'], l['title'], ('MADE ' + made[l['id']]) if l['id'] in made else 'not made yet'))
        return
    if a.reset_log:
        print('The list of made videos is kept on purpose so nothing is ever made twice.')
        print('To really start over, delete made_lessons.json AND made_history.txt by hand.')
        return
    if a.check:
        sys.exit(0 if check() else 1)
    if a.preview_whatif:
        outdir = a.out or os.path.join(HERE, 'output_renders', 'whatif_preview_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
        seen = dict(made)
        for _ in range(a.preview_whatif):
            l = generate_procedural_scenario(seen)
            seen[l['id']] = 'preview'
            preview(l, cfg, outdir)
            print('  ', l['id'], ' ', l['title'])
        print('Pictures saved in', outdir)
        return
    if a.whatif:
        auto_l = generate_procedural_scenario(made)
        lessons[auto_l['id']] = auto_l
        ids = [auto_l['id']]
        print('New what-if video:', auto_l['title'])
    elif a.all:
        ids = list(lessons)
    elif a.lesson:
        ids = a.lesson
    elif a.preview:
        ids = list(lessons)
    else:
        todo = [i for i in lessons if i not in made]
        if not todo:
            auto_l = generate_procedural_scenario(made)
            lessons[auto_l['id']] = auto_l
            ids = [auto_l['id']]
            print('All %d rules lessons are done. New what-if video: %s' % (len(cfg['lessons']), auto_l['title']))
        else:
            ids = todo[:1]
            print('Next lesson: %s (%d of %d)' % (lessons[ids[0]]['title'], len(made) + 1, len(lessons)))

    stamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    outdir = a.out or os.path.join(HERE, 'output_renders', 'tienlen_batch_' + stamp)
    if a.preview:
        for i in ids:
            preview(lessons[i], cfg, outdir)
            make_cover(lessons[i], os.path.join(outdir, i + '_cover.png'))
            make_cover(lessons[i], os.path.join(outdir, i + '_cover_wide.png'), (1280, 720))
        print('Pictures saved in', outdir)
        return
    for i in ids:
        print('Making', i, '...')
        with tempfile.TemporaryDirectory(prefix='tl_') as tmp:
            path, sec, v = build_short(lessons[i], cfg, outdir, not a.no_voice, a.voice, a.rate, tmp)
        print('   done: %s  (%.1f s, %s)' % (os.path.relpath(path, HERE), sec, 'with voice' if v else 'no voice'))
        try:
            make_cover(lessons[i], os.path.join(outdir, i + '_cover.png'))
            make_cover(lessons[i], os.path.join(outdir, i + '_cover_wide.png'), (1280, 720))
            print('   cover pictures: %s_cover.png (vertical) and %s_cover_wide.png' % (i, i))
        except Exception as e:
            print('   (could not make the cover picture: %s)' % e)
        made[i] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        write_made(made, i, lessons[i]['title'])
        if sec > 30:
            print('   NOTE: runtime is %.1f s (over 30 s target).' % sec)
    print('\nAll finished. Folder:', outdir)


if __name__ == '__main__':
    main()
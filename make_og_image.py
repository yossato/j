# -*- coding: utf-8 -*-
"""OGP用画像（1200x630）を生成する"""
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630
ACCENT = (47, 85, 151)       # var(--accent)
ACCENT_DARK = (30, 58, 110)
BG = (247, 248, 250)
WHITE = (255, 255, 255)
MUTED = (200, 212, 232)

FONT_PATH = "/System/Library/Fonts/Hiragino Sans GB.ttc"

def font(size, index=0):
    return ImageFont.truetype(FONT_PATH, size, index=index)

img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)

# 背景の対角グラデーション風ブロック
for y in range(H):
    t = y / H
    r = int(ACCENT[0] + (ACCENT_DARK[0] - ACCENT[0]) * t)
    g = int(ACCENT[1] + (ACCENT_DARK[1] - ACCENT[1]) * t)
    b = int(ACCENT[2] + (ACCENT_DARK[2] - ACCENT[2]) * t)
    draw.line([(0, y), (W, y)], fill=(r, g, b))

# 右下に薄い円の装飾
overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
odraw = ImageDraw.Draw(overlay)
odraw.ellipse([W - 420, H - 420, W + 220, H + 220], fill=(255, 255, 255, 18))
odraw.ellipse([-180, -180, 280, 280], fill=(255, 255, 255, 14))
img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
draw = ImageDraw.Draw(img)

PAD = 72

# ロゴ風バッジ
badge_font = font(30)
draw.rounded_rectangle([PAD, 64, PAD + 200, 64 + 54], radius=27, fill=WHITE)
draw.text((PAD + 28, 64 + 11), "JRE CARD", font=badge_font, fill=ACCENT)

# タイトル
title_font = font(74)
draw.text((PAD, 170), "JRE優待店", font=title_font, fill=WHITE)
draw.text((PAD, 260), "駅ビル タグ検索", font=title_font, fill=WHITE)

# サブタイトル
sub_font = font(34)
draw.text((PAD, 372), "品川・川崎・横浜・有楽町・東京駅の店舗を", font=sub_font, fill=MUTED)
draw.text((PAD, 416), "駅・施設・ジャンルとフリーワードで検索", font=sub_font, fill=MUTED)

# タグ風チップを並べる
chip_font = font(28)
chips = ["衣料", "メガネ", "生活雑貨", "子供服", "レストラン", "コスメ"]
x = PAD
y = 492
for c in chips:
    bbox = draw.textbbox((0, 0), c, font=chip_font)
    w = bbox[2] - bbox[0]
    chip_w = w + 44
    if x + chip_w > W - PAD:
        x = PAD
        y += 64
    draw.rounded_rectangle([x, y, x + chip_w, y + 50], radius=25, fill=(255, 255, 255, 230))
    draw.text((x + 22, y + 11), c, font=chip_font, fill=ACCENT_DARK)
    x += chip_w + 14

img.save("docs/og-image.png")
print("saved docs/og-image.png", img.size)

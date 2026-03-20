#!/usr/bin/env python3
"""
伸懶腰傳統整復推拿會館 - 師傅團隊介紹圖片生成器
用 Pillow 製作三欄兩列的師傅團隊介紹圖片
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

# ─── 設定 ───────────────────────────────────────────
OUTPUT_PATH = "/home/ubuntu/line_chatbot_aka/team_photo.png"

# 品牌色彩
BG_COLOR = (245, 237, 227)       # 暖米色 #F5EDE3
TITLE_COLOR = (232, 114, 42)     # 橘色 #E8722A
NAME_COLOR = (92, 61, 30)        # 深棕色 #5C3D1E
SLOGAN_COLOR = (140, 120, 100)   # 灰棕色
CARD_BG = (255, 255, 255)        # 白色卡片
CARD_SHADOW = (220, 210, 200)    # 卡片陰影
CIRCLE_BORDER = (232, 114, 42)   # 圓形邊框橘色

# 師傅資料
MASTERS = [
    {"name": "芸芸", "slogan": "啟動舒緩，回歸平衡", "photo": "/home/ubuntu/upload/IMG_7144.jpeg"},
    {"name": "大可", "slogan": "智慧洞察，突破不適", "photo": "/home/ubuntu/upload/IMG_7143.jpeg"},
    {"name": "阿YA", "slogan": "柔式手法，壓力釋放", "photo": "/home/ubuntu/upload/IMG_6852.jpeg"},
    {"name": "阿駿", "slogan": "科班底蘊，重塑平衡", "photo": "/home/ubuntu/upload/IMG_6795.jpeg"},
    {"name": "阿瑜", "slogan": "溫柔以待，自在生活", "photo": "/home/ubuntu/upload/IMG_6851.jpeg"},
]

# 佈局參數
CANVAS_WIDTH = 1200
COLS = 3
CARD_WIDTH = 340
CARD_HEIGHT = 380
PHOTO_SIZE = 200
CARD_MARGIN_X = 40
CARD_MARGIN_Y = 30
HEADER_HEIGHT = 140
BOTTOM_PADDING = 60

# ─── 字型載入 ──────────────────────────────────────
def load_font(size, bold=False):
    """載入字型，優先使用系統中文字型"""
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJKtc-Bold.otf" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJKtc-Regular.otf",
        "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            return ImageFont.truetype(fp, size)
    # fallback: 嘗試安裝
    return ImageFont.load_default()


def create_circular_photo(photo_path, size, name=""):
    """將照片裁切為圓形，帶橘色邊框"""
    border_width = 6
    total_size = size + border_width * 2

    # 建立圓形遮罩
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, size - 1, size - 1), fill=255)

    if os.path.exists(photo_path):
        # 載入照片
        photo = Image.open(photo_path).convert("RGB")
        # 裁切為正方形（取中心）
        w, h = photo.size
        min_dim = min(w, h)
        left = (w - min_dim) // 2
        top = (h - min_dim) // 2
        photo = photo.crop((left, top, left + min_dim, top + min_dim))
        photo = photo.resize((size, size), Image.LANCZOS)
    else:
        # 照片不存在時，生成帶名字的佔位圖
        colors = [(180, 150, 120), (160, 140, 130), (170, 145, 125), (155, 135, 115), (165, 150, 130)]
        idx = hash(name) % len(colors)
        photo = Image.new("RGB", (size, size), colors[idx])
        draw = ImageDraw.Draw(photo)
        font = load_font(48, bold=True)
        bbox = draw.textbbox((0, 0), name, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(((size - tw) // 2, (size - th) // 2), name, fill=(255, 255, 255), font=font)

    # 套用圓形遮罩
    photo.putalpha(mask)

    # 建立帶邊框的圖片
    result = Image.new("RGBA", (total_size, total_size), (0, 0, 0, 0))
    result_draw = ImageDraw.Draw(result)
    # 畫橘色邊框圓
    result_draw.ellipse((0, 0, total_size - 1, total_size - 1), fill=CIRCLE_BORDER + (255,))
    # 貼上圓形照片
    result.paste(photo, (border_width, border_width), photo)

    return result


def create_master_card(master, card_w, card_h, photo_size):
    """建立單個師傅的卡片"""
    card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)

    # 繪製圓角卡片背景
    corner_radius = 20
    # 先畫白色圓角矩形
    draw.rounded_rectangle(
        [(0, 0), (card_w - 1, card_h - 1)],
        radius=corner_radius,
        fill=CARD_BG + (255,),
        outline=(235, 225, 215, 255),
        width=2
    )

    # 貼上圓形照片
    circular_photo = create_circular_photo(master["photo"], photo_size, master["name"])
    photo_x = (card_w - circular_photo.width) // 2
    photo_y = 25
    card.paste(circular_photo, (photo_x, photo_y), circular_photo)

    # 師傅名字
    name_font = load_font(36, bold=True)
    name_bbox = draw.textbbox((0, 0), master["name"], font=name_font)
    name_w = name_bbox[2] - name_bbox[0]
    name_x = (card_w - name_w) // 2
    name_y = photo_y + circular_photo.height + 15
    draw.text((name_x, name_y), master["name"], fill=NAME_COLOR + (255,), font=name_font)

    # 標語
    slogan_font = load_font(20, bold=False)
    slogan_bbox = draw.textbbox((0, 0), master["slogan"], font=slogan_font)
    slogan_w = slogan_bbox[2] - slogan_bbox[0]
    slogan_x = (card_w - slogan_w) // 2
    slogan_y = name_y + 48
    draw.text((slogan_x, slogan_y), master["slogan"], fill=SLOGAN_COLOR + (255,), font=slogan_font)

    return card


def main():
    # 計算畫布高度
    rows = 2
    total_cards_width = COLS * CARD_WIDTH + (COLS - 1) * CARD_MARGIN_X
    start_x = (CANVAS_WIDTH - total_cards_width) // 2
    canvas_height = HEADER_HEIGHT + rows * CARD_HEIGHT + (rows - 1) * CARD_MARGIN_Y + BOTTOM_PADDING

    # 建立畫布
    canvas = Image.new("RGBA", (CANVAS_WIDTH, canvas_height), BG_COLOR + (255,))
    draw = ImageDraw.Draw(canvas)

    # ─── 頂部標題區 ───
    # 主標題
    title_font = load_font(42, bold=True)
    title_text = "伸懶腰傳統整復推拿會館"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_w = title_bbox[2] - title_bbox[0]
    title_x = (CANVAS_WIDTH - title_w) // 2
    draw.text((title_x, 25), title_text, fill=TITLE_COLOR + (255,), font=title_font)

    # 副標題
    subtitle_font = load_font(26, bold=False)
    subtitle_text = "專業師傅團隊"
    subtitle_bbox = draw.textbbox((0, 0), subtitle_text, font=subtitle_font)
    subtitle_w = subtitle_bbox[2] - subtitle_bbox[0]
    subtitle_x = (CANVAS_WIDTH - subtitle_w) // 2
    draw.text((subtitle_x, 80), subtitle_text, fill=NAME_COLOR + (255,), font=subtitle_font)

    # 裝飾線
    line_w = 120
    line_y = 115
    draw.line(
        [(CANVAS_WIDTH // 2 - line_w, line_y), (CANVAS_WIDTH // 2 + line_w, line_y)],
        fill=TITLE_COLOR + (180,),
        width=2
    )

    # ─── 排列師傅卡片 ───
    for i, master in enumerate(MASTERS):
        row = i // COLS
        col = i % COLS

        if row == 1 and i >= 3:
            # 第二列只有 2 張卡片，置中排列
            remaining = len(MASTERS) - 3
            row2_total_width = remaining * CARD_WIDTH + (remaining - 1) * CARD_MARGIN_X
            row2_start_x = (CANVAS_WIDTH - row2_total_width) // 2
            col_in_row2 = i - 3
            x = row2_start_x + col_in_row2 * (CARD_WIDTH + CARD_MARGIN_X)
        else:
            x = start_x + col * (CARD_WIDTH + CARD_MARGIN_X)

        y = HEADER_HEIGHT + row * (CARD_HEIGHT + CARD_MARGIN_Y)

        card = create_master_card(master, CARD_WIDTH, CARD_HEIGHT, PHOTO_SIZE)
        canvas.paste(card, (x, y), card)

    # 轉為 RGB 並儲存
    final = canvas.convert("RGB")
    final.save(OUTPUT_PATH, "PNG", quality=95)
    print(f"團隊介紹圖片已儲存至：{OUTPUT_PATH}")
    print(f"圖片尺寸：{final.size[0]} x {final.size[1]}")


if __name__ == "__main__":
    main()

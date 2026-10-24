"""用 Pillow 画应用图标（托盘图标 / 桌面快捷方式的 .ico 共用）。"""
from PIL import Image, ImageDraw


def make_icon(size=256):
    s = size * 4  # 超采样抗锯齿
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    # 渐变底：粉 → 蓝紫
    grad = Image.new("RGBA", (s, s))
    top, bot = (255, 154, 190), (112, 150, 255)
    px = grad.load()
    for y in range(s):
        t = y / (s - 1)
        c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)) + (255,)
        for x in range(s):
            px[x, y] = c
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, s - 1, s - 1), radius=int(s * 0.23), fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)
    # 白色剪贴板
    d.rounded_rectangle((s * .26, s * .22, s * .74, s * .80), radius=int(s * .07), fill=(255, 255, 255, 245))
    d.rounded_rectangle((s * .38, s * .15, s * .62, s * .29), radius=int(s * .05), fill=(255, 255, 255, 255),
                        outline=(120, 140, 230, 255), width=max(2, int(s * .012)))
    for i, w in enumerate((.36, .36, .24)):  # 文字行
        y = s * (.42 + i * .12)
        d.rounded_rectangle((s * .33, y, s * (.33 + w), y + s * .04), radius=int(s * .02), fill=(150, 160, 235, 255))
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "icon.ico"
    make_icon(256).save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])

"""生成程序图标 icon.ico（纯标准库，无 Pillow 依赖）。"""
import struct
import os

SIZES = [256, 64, 48, 32, 16]
BG_TOP = (37, 99, 235)      # #2563eb
BG_BOT = (29, 78, 216)      # #1d4ed8
FG = (255, 255, 255)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rounded_alpha(x, y, size, radius):
    """圆角矩形覆盖率（1 内 / 0 外），用距离场近似。"""
    cx = min(max(x, radius), size - radius)
    cy = min(max(y, radius), size - radius)
    dx, dy = x - cx, y - cy
    d = (dx * dx + dy * dy) ** 0.5
    if d <= radius - 0.5:
        return 1.0
    if d >= radius + 0.5:
        return 0.0
    return radius + 0.5 - d


def render(size):
    ss = 2
    px = [[(0, 0, 0, 0)] * size for _ in range(size)]
    radius = size * 0.24
    cx, cy = size * 0.44, size * 0.44
    r_out, r_in = size * 0.27, size * 0.185
    hx0, hy0 = size * 0.60, size * 0.60
    hx1, hy1 = size * 0.80, size * 0.80
    hw = size * 0.055

    for y in range(size):
        for x in range(size):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in range(ss):
                for sx in range(ss):
                    fx = x + (sx + 0.5) / ss
                    fy = y + (sy + 0.5) / ss
                    a = rounded_alpha(fx, fy, size, radius)
                    if a <= 0:
                        continue
                    bg = lerp(BG_TOP, BG_BOT, fy / size)
                    col = list(bg) + [a]
                    # 放大镜：外环
                    d = ((fx - cx) ** 2 + (fy - cy) ** 2) ** 0.5
                    ring = 1.0 if r_in <= d <= r_out else 0.0
                    # 放大镜柄
                    vx, vy = hx1 - hx0, hy1 - hy0
                    L2 = vx * vx + vy * vy
                    t = ((fx - hx0) * vx + (fy - hy0) * vy) / L2
                    if 0 <= t <= 1:
                        px_, py_ = hx0 + t * vx, hy0 + t * vy
                        if ((fx - px_) ** 2 + (fy - py_) ** 2) ** 0.5 <= hw:
                            ring = 1.0
                    if ring > 0:
                        col = [FG[0], FG[1], FG[2], a]
                    acc[0] += col[0]
                    acc[1] += col[1]
                    acc[2] += col[2]
                    acc[3] += col[3]
            n = ss * ss
            px[y][x] = (int(acc[2] / n), int(acc[1] / n), int(acc[0] / n), int(acc[3] / n))
    return px


def bmp_bytes(px, size):
    """ICO 里的 BMP：40 字节头 + BGRA 自下而上 + AND 掩码。"""
    hdr = struct.pack('<IiiHHIIiiII', 40, size, size * 2, 1, 32, 0,
                      size * size * 4, 0, 0, 0, 0)
    body = bytearray()
    for y in range(size - 1, -1, -1):
        for x in range(size):
            b, g, r, a = px[y][x]
            body += bytes((b, g, r, a))
    mask_row = ((size + 31) // 32) * 4
    body += b'\x00' * (mask_row * size)
    return hdr + bytes(body)


def main():
    images = []
    for s in SIZES:
        images.append((s, bmp_bytes(render(s), s)))
    out = bytearray(struct.pack('<HHH', 0, 1, len(images)))
    offset = 6 + 16 * len(images)
    for s, data in images:
        w = 0 if s >= 256 else s
        h = 0 if s >= 256 else s
        out += struct.pack('<BBBBHHII', w, h, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    for _, data in images:
        out += data
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.ico')
    open(p, 'wb').write(bytes(out))
    print('icon.ico', len(out), 'bytes')


if __name__ == '__main__':
    main()

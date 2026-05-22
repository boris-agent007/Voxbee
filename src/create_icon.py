# Copyright (C) 2026 Boris Shkylnikov
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This file is part of Vox Bee.
#
# Vox Bee is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3.
#
# Vox Bee is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Vox Bee. If not, see <https://www.gnu.org/licenses/>.

"""
VoxBee — Material Flat Design Edition
Плоский стиль Android Material Design.
Рендер 1536px → LANCZOS.
"""

from PIL import Image, ImageDraw, ImageFilter, ImageChops
import math


# ═══════════════════════════════════════════════════════
#  ГЕОМЕТРИЯ
# ═══════════════════════════════════════════════════════

def hex_pts(cx, cy, r, rot=-30):
    return [(cx + r * math.cos(math.radians(60 * i + rot)),
             cy + r * math.sin(math.radians(60 * i + rot)))
            for i in range(6)]


def cubic(p0, p1, p2, p3, n=60):
    pts = []
    for i in range(n + 1):
        t = i / n; u = 1 - t
        pts.append((
            u**3*p0[0] + 3*u**2*t*p1[0] + 3*u*t**2*p2[0] + t**3*p3[0],
            u**3*p0[1] + 3*u**2*t*p1[1] + 3*u*t**2*p2[1] + t**3*p3[1]))
    return pts


def quad(p0, p1, p2, n=40):
    pts = []
    for i in range(n + 1):
        t = i / n; u = 1 - t
        pts.append((
            u**2*p0[0] + 2*u*t*p1[0] + t**2*p2[0],
            u**2*p0[1] + 2*u*t*p1[1] + t**2*p2[1]))
    return pts


def I(pt):
    return (int(pt[0]), int(pt[1]))


# ═══════════════════════════════════════════════════════
#  КОНТУРЫ КРЫЛЬЕВ (без жилок — flat)
# ═══════════════════════════════════════════════════════

def forewing(ax, ay, s, L, W):
    leading = cubic((ax, ay), (ax + s*L*0.15, ay - W*0.92),
                    (ax + s*L*0.55, ay - W*0.74),
                    (ax + s*L*0.97, ay - W*0.10), 70)
    trailing = cubic((ax + s*L*0.97, ay - W*0.10),
                     (ax + s*L*0.72, ay + W*0.42),
                     (ax + s*L*0.22, ay + W*0.32),
                     (ax, ay), 70)
    return leading + trailing[1:]


def hindwing(ax, ay, s, L, W):
    leading = cubic((ax, ay), (ax + s*L*0.12, ay - W*0.68),
                    (ax + s*L*0.45, ay - W*0.52),
                    (ax + s*L*0.88, ay - W*0.06), 50)
    trailing = cubic((ax + s*L*0.88, ay - W*0.06),
                     (ax + s*L*0.62, ay + W*0.40),
                     (ax + s*L*0.18, ay + W*0.30),
                     (ax, ay), 50)
    return leading + trailing[1:]


def poly_outline(draw, pts, color, width):
    """Контур замкнутого полигона из точек."""
    for i in range(len(pts)):
        draw.line([pts[i], pts[(i + 1) % len(pts)]],
                  fill=color, width=width)




def compound_eye(master, ex, ey, r_eye, cell_r, body_mask, RS):
    """Фасеточный глаз в форме шестиугольника из мини-сот.
    ex, ey — центр глаза; r_eye — радиус внешнего шестиугольника;
    cell_r — радиус одной ячейки; body_mask — маска тела для клиппинга.
    """
    eye_layer = Image.new('RGBA', (RS, RS), (0, 0, 0, 0))
    ed = ImageDraw.Draw(eye_layer)

    # Маска формы глаза — ШЕСТИУГОЛЬНИК (flat top, rot=0)
    eye_mask = Image.new('L', (RS, RS), 0)
    eye_hex = [I(p) for p in hex_pts(ex, ey, r_eye, rot=0)]
    ImageDraw.Draw(eye_mask).polygon(eye_hex, fill=255)

    # Тёмная подложка глаза (шестиугольник)
    ed.polygon(eye_hex, fill=(18, 12, 8))

    # Тонкая обводка глаза
    poly_outline(ed, eye_hex, (8, 4, 2), max(int(r_eye * 0.06), 1))

    # Заполняем сотовой сеткой
    col_w = cell_r * math.sqrt(3)
    row_h = cell_r * 1.5
    wall = max(int(cell_r * 0.25), 1)

    row_i = 0
    y = ey - r_eye
    while y <= ey + r_eye:
        off = col_w / 2 if row_i % 2 else 0
        x = ex - r_eye + off
        while x <= ex + r_eye:
            # Проверяем попадание в шестиугольник (приближение через расстояние)
            dx = abs(x - ex)
            dy = abs(y - ey)
            # Точная проверка для flat-top hex
            if dy <= r_eye * 0.866 and dx <= r_eye - dy * 0.577:
                if dy < r_eye * 0.78 or dx < (r_eye * 0.866 - dy) * 1.1:
                    # Стенка ячейки (тёмная)
                    outer = [I(p) for p in hex_pts(x, y, cell_r, rot=0)]
                    ed.polygon(outer, fill=(12, 8, 5))
                    # Внутренность — тёмно-бордовый, к краю темнее
                    inner_h = [I(p) for p in hex_pts(x, y, cell_r - wall, rot=0)]
                    dist = math.hypot(x - ex, y - ey) / r_eye
                    bright = int(60 - dist * 35)
                    ed.polygon(inner_h, fill=(bright + 30, bright + 8, bright))
            x += col_w
        y += row_h
        row_i += 1

    # Клиппинг по шестиугольнику глаза и маске тела
    combined = ImageChops.darker(eye_mask, body_mask)
    eye_layer.putalpha(ImageChops.darker(eye_layer.split()[3], combined))
    return Image.alpha_composite(master, eye_layer)



# ═══════════════════════════════════════════════════════
#  MATERIAL SHADOW (key + ambient)
# ═══════════════════════════════════════════════════════

def material_shadow(RS, rect, radius, elevation):
    """Два слоя тени: key (резкая снизу) + ambient (мягкая вокруг)."""
    shadow = Image.new('RGBA', (RS, RS), (0, 0, 0, 0))
    l, t, r, b = rect

    # Key shadow — направленная (свет сверху → тень вниз)
    key = Image.new('RGBA', (RS, RS), (0, 0, 0, 0))
    off = max(elevation, 2)
    ImageDraw.Draw(key).rounded_rectangle(
        [l + 1, t + off, r + 1, b + off],
        radius=radius, fill=(0, 0, 0, 38))
    key = key.filter(ImageFilter.GaussianBlur(elevation * 1.5))

    # Ambient shadow — мягкая вокруг
    amb = Image.new('RGBA', (RS, RS), (0, 0, 0, 0))
    spread = max(elevation // 2, 1)
    ImageDraw.Draw(amb).rounded_rectangle(
        [l - spread, t - spread, r + spread, b + spread],
        radius=radius + spread, fill=(0, 0, 0, 16))
    amb = amb.filter(ImageFilter.GaussianBlur(elevation * 2.5))

    shadow = Image.alpha_composite(shadow, amb)
    shadow = Image.alpha_composite(shadow, key)
    return shadow


# ═══════════════════════════════════════════════════════
#  ГЛАВНАЯ ФУНКЦИЯ
# ═══════════════════════════════════════════════════════

def create_icon(filename='voxbee.ico', variant='ready'):
    RS = 1536
    SIZES = [16, 24, 32, 48, 64, 128, 256]
    master = Image.new('RGBA', (RS, RS), (0, 0, 0, 0))
    cx = cy = RS // 2

    # ─── Material Design Palette ───
    # Amber (основной цвет пчелы)
    AMBER_500   = (255, 193, 7)        # стандартный Material Amber
    AMBER_600   = (255, 179, 0)        # чуть теплее — основной
    AMBER_700   = (255, 160, 0)        # тёмный акцент
    AMBER_300   = (255, 213, 79)       # светлый акцент
    AMBER_100   = (255, 236, 179)      # бледный

    # Brown (полоски пчелы)
    BROWN_800   = (78, 52, 22)

    # Blue Grey (фон)
    BG_900      = (32, 37, 48)         # внутренность шестиугольника
    BG_100      = (255, 255, 255)

    # Grey (стойка)
    GREY_400    = (158, 158, 158)
    GREY_300    = (189, 189, 189)


    # Green (рамка — трава)
    GREEN_600   = (67, 160, 71)         # Material Green 600 — сочная трава
    GREEN_700   = (56, 142, 60)         # Material Green 700 — кромка
    GREEN_800   = (46, 125, 50)         # Material Green 800 — тёмный акцент    

    
    # Frame, body, stem colors — зависят от варианта
    if variant == 'recording':
        FRAME_COLOR = (0, 174, 239)      # Windows Security Cyan
        FRAME_EDGE  = (0, 155, 215)      # кромка чуть темнее
        BODY_COLOR  = (0, 188, 255)      # тело пчелы — яркий голубой
        STEM_COLOR  = (0, 155, 215)      # стебель — голубой
        LEAF_COLOR  = (0, 174, 239)      # листья — голубой
        LEAF_VEIN   = (0, 140, 195)      # жилки — темнее
        ARC_COLOR   = (0, 174, 239)      # дуга — голубой
    else:
        FRAME_COLOR = AMBER_600          # рамка жёлтая = в цвет пчелы
        FRAME_EDGE  = AMBER_700          # кромка чуть темнее
        BODY_COLOR  = AMBER_600
        STEM_COLOR  = AMBER_700          # стебель жёлтый
        LEAF_COLOR  = AMBER_600          # листья жёлтые
        LEAF_VEIN   = AMBER_700          # жилки чуть темнее
        ARC_COLOR   = AMBER_700          # дуга жёлтая

    # Крылья — нейтральный холодный
    WING_FILL   = (255, 255, 255, 140)
    WING_STROKE = (255, 255, 255, 255)

    # Соты

    HONEY_FILL  = (255, 210, 55, 65)      # ярче, насыщеннее
    HONEY_LINE  = (255, 225, 85, 90)      # тёплая жёлтая обводка

    R_OUT = RS * 0.499
    R_IN  = RS * 0.425

    # ══════════════════════════════════════════
    #  1 · ШЕСТИУГОЛЬНАЯ РАМКА — flat solid
    # ══════════════════════════════════════════
    draw = ImageDraw.Draw(master)

    # Рамка: один плоский цвет
    draw.polygon([I(p) for p in hex_pts(cx, cy, R_OUT)],
                 fill=FRAME_COLOR)
    # Внутренность: тёмный фон
    draw.polygon([I(p) for p in hex_pts(cx, cy, R_IN)],
                 fill=BG_100)

    # Тонкая внутренняя кромка (Material «outline»)
    inner_line = [I(p) for p in hex_pts(cx, cy, R_IN + 1)]
    poly_outline(draw, inner_line, FRAME_EDGE, width=2)

    # ══════════════════════════════════════════
    #  2 · МЕДОВЫЕ СОТЫ — flat, яркие, жёлтая обводка
    # ══════════════════════════════════════════
    hex_mask = Image.new('L', (RS, RS), 0)
    ImageDraw.Draw(hex_mask).polygon(
        [I(p) for p in hex_pts(cx, cy, R_IN - 2)], fill=255)

    comb = Image.new('RGBA', (RS, RS), (0, 0, 0, 0))
    cd = ImageDraw.Draw(comb)

    cr = RS * 0.033
    col_w = cr * math.sqrt(3)
    row_h = cr * 1.5
    wall = max(int(RS * 0.003), 2)     # толщина стенки

    row_i = 0
    y_pos = cy - R_IN * 0.92
    while y_pos < cy + R_IN * 0.92:
        off = col_w / 2 if row_i % 2 else 0
        x_pos = cx - R_IN * 0.92 + off
        while x_pos < cx + R_IN * 0.92:
            if math.hypot(x_pos - cx, y_pos - cy) < R_IN * 0.88:
                # Внешний шестиугольник = стенка (жёлтая)
                outer = [I(p) for p in hex_pts(x_pos, y_pos,
                                                cr, rot=-30)]
                inner = [I(p) for p in hex_pts(x_pos, y_pos,
                                                cr - wall, rot=-30)]
                if variant == 'recording':
                    cd.polygon(outer, fill=(0, 120, 180, 150))
                    cd.polygon(inner, fill=(0, 160, 230, 202))
                else:
                    cd.polygon(outer, fill=(255, 205, 55, 150))
                    cd.polygon(inner, fill=(255, 200, 45, 202))
            x_pos += col_w
        y_pos += row_h
        row_i += 1

    comb.putalpha(ImageChops.darker(comb.split()[3], hex_mask))
    master = Image.alpha_composite(master, comb)

    # ── Параметры тела ──
    BW  = RS * 0.248;  BH = RS * 0.375
    BT  = cy - RS * 0.188;  BB = BT + BH
    BL  = cx - BW / 2;      BR = cx + BW / 2
    RAD = int(BW * 0.50)
    W_ATT = BT + BH * 0.22

    
    body_cy = int(BT + BH * 0.5)

    # ══════════════════════════════════════════
    #  2.5 · СТЕБЕЛЬ С ЛИСТЬЯМИ
    # ══════════════════════════════════════════
    stem_layer = Image.new('RGBA', (RS, RS), (0, 0, 0, 0))
    sd = ImageDraw.Draw(stem_layer)

    stem_w = max(int(RS * 0.042), 7)

    arc_bottom = int(BB + RS * 0.14 * 1.2 - RS * 0.085)
    stem_top_y = arc_bottom - max(int(RS * 0.022), 1)
    stem_bot_y = int(cy + R_OUT * 0.94)

    stem_curve = cubic(
        (cx, stem_bot_y),
        (cx + RS * 0.010, stem_bot_y - (stem_bot_y - stem_top_y) * 0.35),
        (cx - RS * 0.008, stem_bot_y - (stem_bot_y - stem_top_y) * 0.65),
        (cx, stem_top_y), 50)

    for j in range(len(stem_curve) - 1):
        sd.line([I(stem_curve[j]), I(stem_curve[j + 1])],
                fill=STEM_COLOR, width=stem_w)

    # ─── Листья ───
    leaf_defs = [
        (-1, 0.35, RS * 0.095, RS * 0.042, 35),  # Нижний левый
        ( 1, 0.55, RS * 0.105, RS * 0.052, 30),  # Средний правый (самый большой)
        (-1, 0.75, RS * 0.085, RS * 0.042, 40),  # Верхний левый
    ]

    # Цвет жилок — чуть темнее листа, но не резко
    VEIN = LEAF_VEIN

    for side, frac, l_len, l_wid, angle in leaf_defs:
        idx = int(frac * (len(stem_curve) - 1))
        ax_l, ay_l = stem_curve[idx]

        angle_rad = math.radians(angle) if side == -1 else -math.radians(angle)
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)

        tip = (ax_l + side * l_len * cos_a,
               ay_l + side * l_len * sin_a)

        c_up = (ax_l + side * l_len * 0.45 * cos_a - l_wid * 1.2 * sin_a,
                ay_l + side * l_len * 0.45 * sin_a + l_wid * 1.2 * cos_a)
        c_dn = (ax_l + side * l_len * 0.45 * cos_a + l_wid * 0.85 * sin_a,
                ay_l + side * l_len * 0.45 * sin_a - l_wid * 0.85 * cos_a)

        upper_c = quad((ax_l, ay_l), c_up, tip, 30)
        lower_c = quad(tip, c_dn, (ax_l, ay_l), 30)
        leaf_poly = [I(p) for p in upper_c + lower_c[1:]]

        # Заливка листа
        sd.polygon(leaf_poly, fill=LEAF_COLOR)

        # ── Жилки поверх листа ──
        mdx = tip[0] - ax_l
        mdy = tip[1] - ay_l
        ml = math.hypot(mdx, mdy) or 1
        ux, uy = mdx / ml, mdy / ml
        nx, ny = -uy, ux

        # Главная жилка — слегка изогнутая дуга
        mv = quad((ax_l, ay_l),
                  (ax_l + mdx * 0.5 + nx * l_wid * 0.03,
                   ay_l + mdy * 0.5 + ny * l_wid * 0.03),
                  tip, 25)
        for j in range(len(mv) - 1):
            sd.line([I(mv[j]), I(mv[j + 1])], fill=VEIN, width=1)

        # Боковые жилки — 5 пар, плавные дуги от центра к краю
        for vi, vf in enumerate((0.18, 0.32, 0.46, 0.60, 0.76)):
            # Точка на главной жилке
            pt_idx = int(vf * (len(mv) - 1))
            vx, vy = mv[pt_idx]

            # Касательная к главной жилке в этой точке
            pt_next = mv[min(pt_idx + 1, len(mv) - 1)]
            tx = pt_next[0] - vx
            ty = pt_next[1] - vy
            tl = math.hypot(tx, ty) or 1
            tx, ty = tx / tl, ty / tl
            # Нормаль к касательной
            tnx, tny = -ty, tx

            # Длина убывает к кончику, но достаёт ~65% до края
            progress = vf
            vlen = l_wid * (0.38 - progress * 0.40)

            # Угол отхода от перпендикуляра: 30° к кончику листа
            fwd = 0.58 * (0.6 + progress * 0.6)  # ближе к tip → сильнее загиб

            for ns in (1, -1):
                # Конечная точка — отклонена к кончику
                e_x = vx + tnx * ns * vlen + tx * vlen * fwd
                e_y = vy + tny * ns * vlen + ty * vlen * fwd

                # Две контрольные точки для S-образной кривой (cubic)
                # Сначала отходит почти перпендикулярно, потом загибается к tip
                c1_x = vx + tnx * ns * vlen * 0.45 + tx * vlen * 0.08
                c1_y = vy + tny * ns * vlen * 0.45 + ty * vlen * 0.08
                c2_x = vx + tnx * ns * vlen * 0.75 + tx * vlen * fwd * 0.7
                c2_y = vy + tny * ns * vlen * 0.75 + ty * vlen * fwd * 0.7

                cv = cubic((vx, vy), (c1_x, c1_y),
                           (c2_x, c2_y), (e_x, e_y), 16)
                for j in range(len(cv) - 1):
                    sd.line([I(cv[j]), I(cv[j + 1])],
                            fill=VEIN, width=1)

    stem_layer.putalpha(ImageChops.darker(stem_layer.split()[3], hex_mask))
    master = Image.alpha_composite(master, stem_layer)

    # ══════════════════════════════════════════════════════
    #  3 · КРЫЛЬЯ — 4 крыла (2 пары: нижние + верхние поверх)
    # ══════════════════════════════════════════════════════
    WL = RS * 0.32
    WW = RS * 0.18
    ow = max(int(RS * 0.0015), 1)     # outline width

    wings = Image.new('RGBA', (RS, RS), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wings)

    # 📍 Функция поворота крыла вокруг точки крепления
    def rotate_wing(pts, center_x, center_y, angle_deg):
        """Поворот крыла вокруг точки крепления."""
        import math
        angle = math.radians(angle_deg)
        rotated = []
        for px, py in pts:
            dx = px - center_x
            dy = py - center_y
            rx = center_x + dx * math.cos(angle) - dy * math.sin(angle)
            ry = center_y + dx * math.sin(angle) + dy * math.cos(angle)
            rotated.append((rx, ry))
        return rotated

    for sign in (-1, 1):
        ax = cx + sign * BW * 0.12

        # ── ВТОРАЯ ПАРА КРЫЛЬЕВ (нижние, опущены + СИЛЬНО прижаты) ──
        # 📍 Рисуем ПЕРВЫМИ — будут ПОД верхними
        wing2_offset_y = RS * 0.055
        ax2 = cx + sign * BW * 0.09

        # Переднее крыло 2 (нижнее) — поворот 22° к телу
        fw2_raw = forewing(ax, W_ATT, sign, WL, WW)
        fw2 = [I(p) for p in rotate_wing(fw2_raw, ax, W_ATT, sign * 22)]
        fw2 = [(p[0] + sign * (ax2 - ax), p[1] + wing2_offset_y) for p in fw2]
        wd.polygon(fw2, fill=(255, 255, 255, 140))
        poly_outline(wd, fw2, (255, 255, 255, 200), ow)

        # ── ПЕРВАЯ ПАРА КРЫЛЬЕВ (верхние, слегка прижаты) ──
        # 📍 Рисуем ПОСЛЕДНИМИ — будут ПОВЕРХ нижних
        # Переднее крыло 1 — поворот 8° к телу (лёгкий)
        fw1_raw = forewing(ax, W_ATT, sign, WL, WW)
        fw1 = [I(p) for p in rotate_wing(fw1_raw, ax, W_ATT, sign * 8)]
        wd.polygon(fw1, fill=(255, 255, 255, 140))
        poly_outline(wd, fw1, (255, 255, 255, 200), ow)

    master = Image.alpha_composite(master, wings)
    # ══════════════════════════════════════════
    #  4 · ТЕНЬ ТЕЛА — Material elevation dp8
    # ══════════════════════════════════════════
    elev = int(RS * 0.009)
    body_rect = [int(BL), int(BT), int(BR), int(BB)]
    shadow = material_shadow(RS, body_rect, RAD, elev)
    master = Image.alpha_composite(master, shadow)

    # ══════════════════════════════════════════
    #  5 · ТЕЛО — flat fill, один цвет
    # ══════════════════════════════════════════
    body_m = Image.new('L', (RS, RS), 0)
    ImageDraw.Draw(body_m).rounded_rectangle(
        body_rect, radius=RAD, fill=255)

    draw = ImageDraw.Draw(master)
    draw.rounded_rectangle(body_rect, radius=RAD, fill=BODY_COLOR)

    # ══════════════════════════════════════════
    #  6 · СЕТКА МИКРОФОНА — flat uniform dots
    # ══════════════════════════════════════════
    mesh = Image.new('RGBA', (RS, RS), (0, 0, 0, 0))
    md = ImageDraw.Draw(mesh)
    dot_r = max(int(RS * 0.003), 2)
    sp = int(RS * 0.017)
    bcy = BT + BH / 2
    erx, ery = BW * 0.36, BH * 0.38
    row = 0
    for y in range(int(BT + BH * 0.10), int(BB - BH * 0.10), sp):
        ox = sp // 2 if row % 2 else 0
        for x in range(int(BL + BW * 0.15) + ox,
                       int(BR - BW * 0.15), sp):
            if ((x - cx) / erx) ** 2 + ((y - bcy) / ery) ** 2 < 1.0:
                md.ellipse([x - dot_r, y - dot_r,
                            x + dot_r, y + dot_r],
                           fill=(0, 0, 0, 22))
        row += 1
    mesh.putalpha(ImageChops.darker(mesh.split()[3], body_m))
    master = Image.alpha_composite(master, mesh)

    # ══════════════════════════════════════════
    #  7 · ПОЛОСКИ ПЧЕЛЫ — flat crisp bands
    # ══════════════════════════════════════════

    sw = max(int(RS * 0.014), 2)
    for frac in (0.34, 0.49, 0.64):
        sl = Image.new('RGBA', (RS, RS), (0, 0, 0, 0))
        yy = int(BT + BH * frac)
        ImageDraw.Draw(sl).rectangle(
            [int(BL), yy - sw // 2, int(BR), yy + sw // 2],
            fill=(0, 0, 0, 255))
        sl.putalpha(ImageChops.darker(sl.split()[3], body_m))
        master = Image.alpha_composite(master, sl)


    # ══════════════════════════════════════════
    #  8 · ГЛАЗА — фасеточные (шестиугольники-соты)
    # ══════════════════════════════════════════
    eye_r = max(int(RS * 0.032), 5)
    eye_cell = max(int(RS * 0.006), 2)
    ey = int(BT + BH * 0.06)
    for s in (-1, 1):
        ex = int(cx + s * BW * 0.22)
        master = compound_eye(master, ex, ey, eye_r, eye_cell,
                              body_m, RS)

    draw = ImageDraw.Draw(master)    

    # ══════════════════════════════════════════
    #  9 · УСИКИ — чёрные, надломленные
    # ══════════════════════════════════════════
    aw = max(int(RS * 0.004), 2)
    for s in (-1, 1):
        # Основание
        bx = cx + s * BW * 0.15
        by = BT + BH * 0.022

        # Первый сегмент (scape) — вверх и чуть в сторону
        mid_x = bx + s * RS * 0.032
        mid_y = by - RS * 0.058

        # Второй сегмент (flagellum) — резкий излом наружу
        tip_x = mid_x + s * RS * 0.072
        tip_y = mid_y - RS * 0.042

        draw.line([I((bx, by)), I((mid_x, mid_y))],
                  fill=(0, 0, 0), width=aw)
        draw.line([I((mid_x, mid_y)), I((tip_x, tip_y))],
                  fill=(0, 0, 0), width=aw)

    # ══════════════════════════════════════════
    # 10 · ДЕРЖАТЕЛЬ (сферическая дуга) — плавное закругление как у капсулы
    # ══════════════════════════════════════════
    holder_layer = Image.new('RGBA', (RS, RS), (0, 0, 0, 0))
    hd = ImageDraw.Draw(holder_layer)

    # Геометрия
    holder_offset = RS * 0.00     # СМЕЩЕНИЕ ВСЕЙ ЧАШИ: + вниз, - вверх
    holder_w = BW * 1.25          # Ширина дуги
    holder_depth = RS * 0.05      # Глубина дуги
    tip_offset = BH * 0.25        # Подъём концов
    line_w = max(int(RS * 0.032), 6)

    base_y = BB + holder_offset
    
    # Координаты
    bottom_y = base_y + holder_depth
    top_y = base_y - tip_offset
    
    left_tip = (cx - holder_w / 2, top_y)
    right_tip = (cx + holder_w / 2, top_y)
    bottom_center = (cx, bottom_y)

    # ═══ СФЕРИЧЕСКАЯ ДУГА ═══
    # Для плавного закругления контрольные точки должны быть:
    # - Горизонтально: шире от центра (0.40-0.45 от ширины)
    # - Вертикально: на уровне дна или чуть выше
    
    # Левая половина
    left_curve = cubic(
        left_tip,
        (left_tip[0] - RS*0.015, top_y + holder_depth * 0.35),   # Контр. точка 1 — выше
        (cx - holder_w * 0.42, bottom_y + RS*0.005),             # Контр. точка 2 — шире!
        bottom_center,
        n=40
    )

    # Правая половина
    right_curve = cubic(
        bottom_center,
        (cx + holder_w * 0.42, bottom_y + RS*0.005),             # Контр. точка 1 — шире!
        (right_tip[0] + RS*0.015, top_y + holder_depth * 0.35),  # Контр. точка 2 — выше
        right_tip,
        n=40
    )

    # Сборка
    full_path = left_curve + right_curve[1:]

    # Отрисовка
    for i in range(len(full_path) - 1):
        hd.line([I(full_path[i]), I(full_path[i + 1])],
                fill=ARC_COLOR, width=line_w)

    # Скругления на концах
    cap_r = line_w // 2
    hd.ellipse([left_tip[0] - cap_r, left_tip[1] - cap_r,
                left_tip[0] + cap_r, left_tip[1] + cap_r],
               fill=ARC_COLOR)
    hd.ellipse([right_tip[0] - cap_r, right_tip[1] - cap_r,
                right_tip[0] + cap_r, right_tip[1] + cap_r],
               fill=ARC_COLOR)

    # Клиппинг
    holder_layer.putalpha(ImageChops.darker(holder_layer.split()[3], hex_mask))
    master = Image.alpha_composite(master, holder_layer)
    # ✅ Все листья — только на стебле, строго ПОД этой дугой (см. секцию 2.5)
    # ══════════════════════════════════════════
    #  GRAYSCALE ДЛЯ OFF
    # ══════════════════════════════════════════
    if variant == 'off':
        r, g, b, a = master.split()
        gray = master.convert('L')
        master = Image.merge('RGBA', (gray, gray, gray, a))

    # ══════════════════════════════════════════
    #  ЭКСПОРТ
    # ══════════════════════════════════════════
    imgs = [master.resize((s, s), Image.LANCZOS) for s in SIZES]
    imgs[-1].save(filename, format='ICO',
                  sizes=[(s, s) for s in SIZES],
                  append_images=imgs[:-1])
    print(f'✅ {filename} — {len(SIZES)} размеров')

    if variant == 'ready':
        master.resize((512, 512), Image.LANCZOS).save(
            filename.replace('.ico', '_preview.png'))
        master.save(filename.replace('.ico', '_full.png'))
        print(f'✅ preview  512×512')
        print(f'✅ full    1536×1536')


def create_all_icons():
    """Генерирует все варианты иконок: ready, off, recording."""
    create_icon('voxbee.ico', variant='ready')
    create_icon('voxbee_off.ico', variant='off')
    create_icon('voxbee_recording.ico', variant='recording')

def create_png_icons_for_readme():
    """Создаёт PNG иконки 64×64 для README (серая, жёлтая, синяя)."""
    SIZE = 64

    master_ready = Image.new('RGBA', (1536, 1536), (0, 0, 0, 0))

    variants = [
        ('voxbee_off.ico', 'bee_grey.png'),
        ('voxbee.ico', 'bee_yellow.png'),
        ('voxbee_recording.ico', 'bee_blue.png')
    ]
    
    for ico_file, png_file in variants:
        if os.path.exists(ico_file):
            img = Image.open(ico_file)
            img = img.resize((SIZE, SIZE), Image.LANCZOS)
            img.save(png_file, 'PNG', optimize=True)
            print(f'✅ {png_file} ({SIZE}×{SIZE})')
        else:
            print(f'⚠️  {ico_file} не найден, пропущен')


if __name__ == '__main__':
    import os
    create_all_icons()
    create_png_icons_for_readme()
    os.startfile('voxbee_preview.png')

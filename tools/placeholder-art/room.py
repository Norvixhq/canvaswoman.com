"""Renders simple, softly lit interior elevations with a painting hung at true scale."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from paint import noise, hex2rgb, smoothstep, to_image, F


def _shadow_layer(size, boxes, blur, opacity):
    layer = Image.new('L', size, 0)
    d = ImageDraw.Draw(layer)
    for b, r in boxes:
        d.rounded_rectangle(b, radius=r, fill=255)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    return layer.point(lambda v: int(v * opacity))


def _darken(base, mask, color=(20, 16, 12)):
    dark = Image.new('RGB', base.size, color)
    return Image.composite(dark, base, mask)


def render_room(art, art_w_in, art_h_in, W=2000, H=1500, wall='#ECE6DC', floor='#B79B7C',
                furniture='sofa', seed=0, light_from='left'):
    rng = np.random.default_rng(seed)
    floor_frac = 0.84
    floor_y = int(H * floor_frac)
    furn_w_in, furn_h_in = (84, 32) if furniture == 'sofa' else (72, 30)
    gap_in, top_margin_in = 9, 14
    visible_w_in = max(128, art_w_in * 2.5, furn_w_in * 1.45)
    ppi = W / visible_w_in
    need_in = furn_h_in + gap_in + art_h_in + top_margin_in
    if need_in * ppi > floor_y:
        ppi = floor_y / need_in
    P = lambda inches: int(round(inches * ppi))

    # ---- wall
    yy, xx = np.mgrid[0:H, 0:W].astype(F)
    base = hex2rgb(wall)
    lx = xx / W if light_from == 'left' else 1 - xx / W
    light = 0.94 + 0.08 * (1 - lx) - 0.05 * (yy / floor_y) ** 2
    shaft = np.clip(1 - np.abs((xx - (W * 0.2 if light_from == 'left' else W * 0.8)) + (yy - H * 0.2) * 0.55) / (W * 0.16), 0, 1)
    shaft = shaft * smoothstep(0, H * 0.2, yy) * (1 - smoothstep(floor_y * 0.6, floor_y, yy))
    plaster = (noise(H, W, 160, rng, 4) - 0.5) * 0.03
    wall_rgb = base[None, None, :] * (light + shaft * 0.05 + plaster)[..., None]
    # ---- floor
    ft = np.clip((yy - floor_y) / (H - floor_y + 1), 0, 1)
    grain = noise(H, W, 40, rng, 3)
    grain = np.asarray(Image.fromarray(grain, 'F').resize((W // 8, H), Image.BILINEAR).resize((W, H), Image.BICUBIC))
    fl = hex2rgb(floor)[None, None, :] * (0.92 + 0.1 * grain[..., None] - 0.12 * ft[..., None])
    planks = np.zeros((H, W), F)
    for k in range(1, 9):
        py = floor_y + (H - floor_y) * (k / 9) ** 1.5
        planks += np.exp(-((yy - py) / 1.2) ** 2) * 0.18
    fl *= (1 - planks[..., None])
    refl = np.exp(-((xx - W * 0.5) / (W * 0.35)) ** 2) * (1 - ft) * 0.05
    fl += refl[..., None]
    img = np.where((yy < floor_y)[..., None], wall_rgb, fl)
    contact = np.exp(-np.clip(yy - floor_y, 0, None) / 10.0) * (yy >= floor_y) * 0.2
    img *= (1 - contact[..., None])
    room = to_image(img)
    d = ImageDraw.Draw(room)

    # baseboard
    bb_h = P(4)
    bb_col = tuple(int(c * 255 * 1.02) if c * 1.02 < 1 else 255 for c in base)
    d.rectangle([0, floor_y - bb_h, W, floor_y], fill=bb_col)
    d.line([0, floor_y - bb_h, W, floor_y - bb_h], fill=tuple(int(c * 255 * 0.86) for c in base), width=2)

    cx = W // 2
    furn_top = floor_y - P(furn_h_in)

    # ---- furniture shadows on floor/wall
    fw = P(furn_w_in)
    sh = _shadow_layer(room.size, [((cx - fw // 2 - P(2), floor_y - P(3), cx + fw // 2 + P(2), floor_y + P(5)), P(3))], P(3), 0.55)
    room = _darken(room, sh)
    wall_sh = _shadow_layer(room.size, [((cx - fw // 2 + P(2), furn_top + P(3), cx + fw // 2 + P(4), floor_y), P(4))], P(5), 0.18)
    room = _darken(room, wall_sh)
    d = ImageDraw.Draw(room)

    if furniture == 'sofa':
        fabric = '#D6CCBC'
        dark = '#BDB2A1'
        x0, x1 = cx - fw // 2, cx + fw // 2
        leg_h = P(4)
        seat_y = floor_y - P(17)
        arm_y = floor_y - P(25)
        arm_w = P(7)
        d.rectangle([x0 + P(4), floor_y - leg_h, x0 + P(6), floor_y], fill='#3A2E25')
        d.rectangle([x1 - P(6), floor_y - leg_h, x1 - P(4), floor_y], fill='#3A2E25')
        d.rounded_rectangle([x0 + arm_w - P(1), furn_top, x1 - arm_w + P(1), seat_y + P(2)], radius=P(4), fill=dark)
        cw = (x1 - x0 - 2 * arm_w) // 3
        for i in range(3):
            bx = x0 + arm_w + i * cw
            d.rounded_rectangle([bx + P(0.6), furn_top + P(1.5), bx + cw - P(0.6), seat_y], radius=P(3.5), fill=fabric)
            d.line([bx + P(2), furn_top + P(3), bx + cw - P(2), furn_top + P(3)], fill='#E3DBCF', width=max(2, P(0.5)))
        d.rounded_rectangle([x0 + arm_w - P(1), seat_y - P(1), x1 - arm_w + P(1), floor_y - leg_h], radius=P(2.5), fill=fabric)
        d.line([x0 + arm_w, seat_y + P(4), x1 - arm_w, seat_y + P(4)], fill=dark, width=max(2, P(0.35)))
        for ax in (x0, x1 - arm_w):
            d.rounded_rectangle([ax, arm_y, ax + arm_w, floor_y - leg_h], radius=P(3), fill=fabric)
            d.line([ax + P(1.5), arm_y + P(1.2), ax + arm_w - P(1.5), arm_y + P(1.2)], fill='#E3DBCF', width=max(2, P(0.5)))
        for (px, col, rot) in [(x0 + arm_w + P(4), '#B7704F', -6), (x1 - arm_w - P(22), '#98A38E', 5)]:
            pil = Image.new('RGBA', (P(20), P(17)), (0, 0, 0, 0))
            pd = ImageDraw.Draw(pil)
            pd.rounded_rectangle([0, 0, P(18), P(15)], radius=P(4), fill=col)
            pil = pil.rotate(rot, expand=True, resample=Image.BICUBIC)
            room.paste(pil, (px, seat_y - P(14)), pil)
    else:
        wood = '#6E4C34'
        x0, x1 = cx - fw // 2, cx + fw // 2
        leg_h = P(6)
        d.rectangle([x0 + P(3), floor_y - leg_h, x0 + P(4.5), floor_y], fill='#1F1A16')
        d.rectangle([x1 - P(4.5), floor_y - leg_h, x1 - P(3), floor_y], fill='#1F1A16')
        d.rectangle([x0, furn_top, x1, floor_y - leg_h], fill=wood)
        step = max(4, P(1.6))
        for fx in range(x0 + P(1), x1 - P(1), step):
            d.line([fx, furn_top + P(2.5), fx, floor_y - leg_h - P(1.5)], fill='#5B3E2A', width=max(1, step // 3))
        d.line([x0, furn_top, x1, furn_top], fill='#8A6649', width=max(2, P(0.8)))
        for k in (1, 2, 3):
            lx = x0 + fw * k // 4
            d.line([lx, furn_top + P(1), lx, floor_y - leg_h], fill='#4A3222', width=max(2, P(0.5)))
        vx = x0 + P(12)
        d.ellipse([vx - P(5), furn_top - P(12), vx + P(5), furn_top], fill='#ECE6DB')
        d.rectangle([vx - P(1.6), furn_top - P(16), vx + P(1.6), furn_top - P(10)], fill='#ECE6DB')
        bx = x1 - P(22)
        d.rectangle([bx, furn_top - P(2), bx + P(12), furn_top], fill='#A8876A')
        d.rectangle([bx + P(1), furn_top - P(3.6), bx + P(11), furn_top - P(2)], fill='#3E4A45')
        d.ellipse([bx + P(14), furn_top - P(3.5), bx + P(22), furn_top + P(0.5)], fill='#C9BDAA')

    # ---- painting
    aw, ah = P(art_w_in), P(art_h_in)
    ay1 = furn_top - P(gap_in)
    ay0 = ay1 - ah
    ax0 = cx - aw // 2
    soft = _shadow_layer(room.size, [((ax0 + P(0.8), ay0 + P(1.2), ax0 + aw + P(0.8), ay1 + P(1.6)), 0)], P(2.2), 0.42)
    room = _darken(room, soft)
    tight = _shadow_layer(room.size, [((ax0 + 2, ay0 + 3, ax0 + aw + 3, ay1 + 5), 0)], 3, 0.35)
    room = _darken(room, tight)
    art_r = art.convert('RGB').resize((aw, ah), Image.LANCZOS)
    room.paste(art_r, (ax0, ay0))
    d = ImageDraw.Draw(room)
    d.line([ax0 + aw - 1, ay0, ax0 + aw - 1, ay1], fill=(0, 0, 0), width=1)

    # gentle vignette + grain for a photographic finish
    arr = np.asarray(room).astype(F) / 255
    vig = 1 - 0.1 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H * 0.45) / H) ** 2)
    arr = arr * vig[..., None] + (rng.random((H, W)).astype(F)[..., None] - 0.5) * 0.012
    return to_image(arr)

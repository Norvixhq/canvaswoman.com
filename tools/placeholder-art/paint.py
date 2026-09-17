"""
Procedural PLACEHOLDER artwork for the Canvas Woman build.
These images stand in for Sreeparna Poddar's real paintings until photography
is supplied. Nothing here depicts her actual work.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

F = np.float32


def hex2rgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], F) / 255.0


def noise(h, w, scale, rng, octaves=4, persistence=0.5):
    total = np.zeros((h, w), F)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        cw = max(2, int(w / scale * (2 ** o)))
        ch = max(2, int(h / scale * (2 ** o)))
        g = rng.random((ch + 1, cw + 1)).astype(F)
        layer = np.asarray(Image.fromarray(g, 'F').resize((w, h), Image.BICUBIC))
        total += layer * amp
        norm += amp
        amp *= persistence
    t = total / norm
    t = (t - t.min()) / (t.max() - t.min() + 1e-6)
    return t


def ramp(t, stops):
    pos = np.array([s[0] for s in stops], F)
    cols = np.stack([hex2rgb(s[1]) for s in stops])
    out = np.empty(t.shape + (3,), F)
    for c in range(3):
        out[..., c] = np.interp(t, pos, cols[:, c])
    return out


def warp(t, dx, dy):
    h, w = t.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(F)
    return ndi.map_coordinates(t, [yy + dy, xx + dx], order=1, mode='reflect')


def smear(img, angle, length, steps=6):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(F)
    dx, dy = np.cos(angle).astype(F), np.sin(angle).astype(F)
    multi = img.ndim == 3
    acc = img.copy()
    n = 1
    for s in range(1, steps + 1):
        d = length * s / steps
        for sign in (1, -1):
            cy, cx = yy + sign * dy * d, xx + sign * dx * d
            if multi:
                for c in range(img.shape[2]):
                    acc[..., c] += ndi.map_coordinates(img[..., c], [cy, cx], order=1, mode='reflect')
            else:
                acc += ndi.map_coordinates(img, [cy, cx], order=1, mode='reflect')
            n += 1
    return acc / n


def bristles(h, w, angle, rng, length=40, strength=0.08):
    raw = rng.random((h, w)).astype(F)
    st = smear(raw, angle, length, steps=8)
    st = (st - st.mean()) / (st.std() + 1e-6)
    return 1.0 + strength * np.clip(st, -2.5, 2.5) / 2.5


def shade(height, light=(-0.55, -0.65, 0.55), relief=6.0):
    gy, gx = np.gradient(height * relief)
    nx, ny, nz = -gx, -gy, np.ones_like(height)
    norm = np.sqrt(nx * nx + ny * ny + nz * nz)
    L = np.array(light, F)
    L /= np.linalg.norm(L)
    lam = (nx * L[0] + ny * L[1] + nz * L[2]) / norm
    # specular (view straight on)
    rz = 2 * lam * (nz / norm) - L[2]
    spec = np.clip(rz, 0, 1) ** 24
    return lam.astype(F), spec.astype(F)


def grain(img, rng, amount=0.018):
    h, w = img.shape[:2]
    g = (rng.random((h, w)).astype(F) - 0.5) * amount
    return img + g[..., None]


def canvas_weave(img, rng, amount=0.012):
    h, w = img.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w].astype(F)
    wv = np.sin(xx * 2.1) * np.sin(yy * 2.1) * amount
    return img + wv[..., None]


def to_image(arr):
    return Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB')


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0 + 1e-9), 0, 1)
    return t * t * (3 - 2 * t)


# ----------------------------------------------------------------- ABSTRACT
def azure_reverie(w=1500, h=2000, seed=11):
    rng = np.random.default_rng(seed)
    base = noise(h, w, 900, rng, octaves=5, persistence=0.55)
    dx = (noise(h, w, 700, rng, 3) - 0.5) * 520
    dy = (noise(h, w, 700, rng, 3) - 0.5) * 520
    t = warp(base, dx, dy)
    t = (t - t.min()) / (t.max() - t.min())
    t = 0.5 + 0.5 * np.tanh((t - 0.5) * 3.2)
    stops = [(0.00, '#F2EEE5'), (0.20, '#E4E6E3'), (0.34, '#B9CAD5'), (0.44, '#6F93B3'),
             (0.52, '#2C5680'), (0.60, '#172D48'), (0.66, '#223E60'), (0.74, '#5D86AB'),
             (0.84, '#CFDAE0'), (1.00, '#F4F0E8')]
    img = ramp(t, stops)
    gy, gx = np.gradient(ndi.gaussian_filter(t, 6))
    ang = np.arctan2(gy, gx) + np.pi / 2
    img = smear(img, ang, 26, steps=6)
    img *= bristles(h, w, ang, rng, 50, 0.07)[..., None]
    # gold veins along a band edge
    vein = np.exp(-((t - 0.555) / 0.0045) ** 2) * (noise(h, w, 260, rng, 2) > 0.45)
    height = ndi.gaussian_filter(t, 2) + vein * 0.08 + noise(h, w, 30, rng, 2) * 0.02
    lam, spec = shade(height, relief=14)
    gold = hex2rgb('#B89457')
    img = img * (1 - vein[..., None] * 0.95) + (gold * (0.75 + 0.6 * lam[..., None]) + spec[..., None] * 0.6) * vein[..., None] * 0.95
    img *= (0.9 + 0.12 * lam[..., None])
    img = canvas_weave(grain(img, rng), rng)
    return to_image(img)


def saffron_hour(w=2000, h=1500, seed=5):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(F)
    img = np.ones((h, w, 3), F) * hex2rgb('#86351F')
    img *= (0.9 + 0.2 * noise(h, w, 500, rng, 4))[..., None]

    def band(y0, y1, x0, x1, c1, c2, rough=28, feather=10):
        n1 = (noise(h, w, 180, rng, 3) - 0.5) * rough * 2
        n2 = (noise(h, w, 180, rng, 3) - 0.5) * rough * 2
        m = smoothstep(y0 - feather, y0 + feather, yy + n1) * (1 - smoothstep(y1 - feather, y1 + feather, yy + n2))
        m *= smoothstep(x0 - feather, x0 + feather, xx + n2) * (1 - smoothstep(x1 - feather, x1 + feather, xx + n1))
        tone = noise(h, w, 260, rng, 4)
        col = ramp(tone, [(0, c1), (1, c2)])
        return m, col

    for (y0, y1, x0, x1, c1, c2) in [
        (h * 0.07, h * 0.52, w * 0.06, w * 0.94, '#D98E2B', '#EDB553'),
        (h * 0.58, h * 0.9, w * 0.06, w * 0.94, '#A85A22', '#C7782E'),
        (h * 0.62, h * 0.66, w * 0.12, w * 0.7, '#F0DFC0', '#E8CFA2'),
    ]:
        m, col = band(y0, y1, x0, x1, c1, c2)
        img = img * (1 - m[..., None]) + col * m[..., None]
    ang = np.full((h, w), 0.0, F) + (noise(h, w, 600, rng, 2) - 0.5) * 0.25
    img = smear(img, ang, 34, steps=6)
    img *= bristles(h, w, ang, rng, 70, 0.1)[..., None]
    img = canvas_weave(grain(img, rng, 0.022), rng)
    return to_image(img)


def quiet_monsoon(w=1800, h=1800, seed=21):
    rng = np.random.default_rng(seed)
    img = np.ones((h, w, 3), F) * hex2rgb('#D2CDC3')
    im = Image.fromarray((img * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    palette = ['#5E6B6E', '#8F9D8B', '#2E3334', '#EEEAE1', '#A9B1A8', '#6F7C72']
    for _ in range(140):
        c = palette[rng.integers(len(palette))]
        x = rng.integers(-100, w)
        y = rng.integers(-200, h)
        bw = rng.integers(20, 130)
        bh = rng.integers(160, 700)
        d.rectangle([x, y, x + bw, y + bh], fill=c)
    img = np.asarray(im).astype(F) / 255
    ang = np.full((h, w), np.pi / 2, F) + (noise(h, w, 500, rng, 3) - 0.5) * 0.9
    img = smear(img, ang, 90, steps=8)
    img = smear(img, ang + 0.3, 30, steps=4)
    img *= bristles(h, w, ang, rng, 90, 0.12)[..., None]
    drips = (rng.random((h, w)) > 0.9996).astype(F)
    drips = smear(drips, np.full((h, w), np.pi / 2, F), 180, steps=12) * 40
    img -= np.clip(drips, 0, 0.25)[..., None] * 0.6
    img = canvas_weave(grain(img, rng, 0.02), rng)
    return to_image(img)


# ----------------------------------------------------------------- TEXTURE
def ivory_tide(w=3000, h=3000, seed=3):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(F)
    wv = (noise(h, w, 1400, rng, 3) - 0.5) * 900 + (noise(h, w, 400, rng, 3) - 0.5) * 120
    phase = (yy + wv + xx * 0.18) / 150.0 * 2 * np.pi
    crest = (0.5 + 0.5 * np.sin(phase)) ** 3
    breaks = smoothstep(0.35, 0.6, noise(h, w, 500, rng, 3))
    knife = noise(h, w, 45, rng, 3)
    height = crest * (0.55 + 0.45 * breaks) + knife * 0.12 + noise(h, w, 8, rng, 2) * 0.015
    height = ndi.gaussian_filter(height, 1.2)
    lam, spec = shade(height, relief=22)
    tone = noise(h, w, 1600, rng, 3)
    base = ramp(tone, [(0, '#E6DCCB'), (0.5, '#EFE8DC'), (1, '#F6F1E8')])
    ao = 0.82 + 0.18 * smoothstep(0.0, 0.6, height)
    img = base * (0.78 + 0.3 * lam[..., None]) * ao[..., None] + spec[..., None] * 0.08
    flakes = (noise(h, w, 60, rng, 3) > 0.83) * (noise(h, w, 900, rng, 2) > 0.62)
    flakes = ndi.gaussian_filter(flakes.astype(F), 1.0)
    gold = hex2rgb('#C2A06A') * (0.7 + 0.5 * lam[..., None]) + spec[..., None] * 0.5
    img = img * (1 - flakes[..., None]) + gold * flakes[..., None]
    img = grain(img, rng, 0.012)
    return to_image(img)


def sandstone_lines(w=2000, h=3000, seed=8):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(F)
    bands = noise(h, w, 2200, rng, 2)
    wob = (noise(h, w, 900, rng, 3) - 0.5) * 160
    comb = 0.5 + 0.5 * np.sin((yy + wob) / 11.0 * 2 * np.pi)
    region = smoothstep(0.35, 0.42, np.sin((yy + wob * 2) / 520 * np.pi) * 0.5 + 0.5)
    height = comb * region * 0.6 + (1 - region) * noise(h, w, 70, rng, 3) * 0.35
    height = ndi.gaussian_filter(height + noise(h, w, 10, rng, 2) * 0.03, 1.0)
    lam, spec = shade(height, relief=18)
    base = ramp(bands, [(0, '#C9B391'), (0.45, '#DCCAA8'), (0.8, '#EADFC9'), (1, '#B9A27F')])
    img = base * (0.8 + 0.28 * lam[..., None]) + spec[..., None] * 0.05
    diag = np.exp(-(((xx * 0.55 + yy) - h * 0.62) / 90) ** 2)
    leaf = diag * (noise(h, w, 120, rng, 3) > 0.42)
    leaf = ndi.gaussian_filter(leaf.astype(F), 1.4)
    gold = hex2rgb('#BE9651') * (0.65 + 0.55 * lam[..., None]) + spec[..., None] * 0.55
    img = img * (1 - leaf[..., None]) + gold * leaf[..., None]
    img = grain(img, rng, 0.014)
    return to_image(img)


def terrain_in_gold(w=2400, h=2400, seed=31):
    rng = np.random.default_rng(seed)
    pts = rng.random((170, 2)) * [h, w]
    yy, xx = np.mgrid[0:h, 0:w]
    tree = cKDTree(pts)
    dists, _ = tree.query(np.stack([yy.ravel(), xx.ravel()], 1), k=2, workers=-1)
    d1 = dists[:, 0].reshape(h, w).astype(F)
    d2 = dists[:, 1].reshape(h, w).astype(F)
    edge = d2 - d1
    crack = 1 - smoothstep(0, 16, edge)
    plate = smoothstep(0, 140, edge)
    height = plate * 0.7 + noise(h, w, 90, rng, 4) * 0.25 - crack * 0.4
    height = ndi.gaussian_filter(height, 1.5)
    lam, spec = shade(height, relief=16)
    tone = noise(h, w, 700, rng, 3)
    base = ramp(tone, [(0, '#231F1C'), (0.55, '#3A332C'), (1, '#6B5236')])
    img = base * (0.72 + 0.45 * lam[..., None])
    gold = hex2rgb('#C9A35E') * (0.6 + 0.6 * lam[..., None]) + spec[..., None] * 0.7
    g = np.clip(crack * 1.2, 0, 1)
    img = img * (1 - g[..., None]) + gold * g[..., None]
    img = grain(img, rng, 0.014)
    return to_image(img)


# ----------------------------------------------------------------- LANDSCAPE
def himalayan_morning(w=2400, h=1500, seed=14):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(F)
    t = yy / h
    sky = ramp(t, [(0, '#93A9C0'), (0.28, '#C6C9CF'), (0.45, '#EDCDB6'), (0.6, '#F3DCC6'), (1, '#F3DCC6')])
    clouds = noise(h, w, 600, rng, 4)
    clouds = smear(clouds, np.zeros((h, w), F), 60, 4)
    sky += (smoothstep(0.55, 0.8, clouds) * (1 - smoothstep(0.1, 0.45, t)) * 0.08)[..., None]
    sun = np.exp(-(((xx - w * 0.7) ** 2 + (yy - h * 0.33) ** 2) / (2 * 70 ** 2)))
    halo = np.exp(-(((xx - w * 0.7) ** 2 + (yy - h * 0.33) ** 2) / (2 * 380 ** 2)))
    img = sky + sun[..., None] * hex2rgb('#FFF1DC') * 0.45 + halo[..., None] * 0.06
    layers = [
        (0.46, 0.20, '#B8BCCB', '#C9C8D0', 1.0),
        (0.56, 0.14, '#9098AC', '#B3B4C1', 0.8),
        (0.66, 0.11, '#6A7488', '#8F95A5', 0.6),
        (0.77, 0.08, '#44505F', '#657080', 0.5),
        (0.88, 0.07, '#2C3834', '#46524C', 0.4),
    ]
    for i, (base, amp, c_top, c_mist, mist) in enumerate(layers):
        n = noise(1, w, 420 - i * 50, rng, 5, 0.52)[0]
        ridge = 1 - np.abs(2 * n - 1)
        ridge_y = h * (base - amp * ridge ** 1.4)
        m = smoothstep(ridge_y - 1.5, ridge_y + 1.5, yy)
        depth = np.clip((yy - ridge_y) / (h * 0.12), 0, 1)
        col = ramp(depth * 0.999, [(0, c_top), (1, c_mist)])
        if i < 2:
            snow = (yy - ridge_y < 26) * (ridge[None, :] > 0.72) * m
            col = col * (1 - snow[..., None] * 0.55) + hex2rgb('#F4EEE8') * snow[..., None] * 0.55
        img = img * (1 - m[..., None]) + col * m[..., None]
    ang = (noise(h, w, 500, rng, 2) - 0.5) * 0.2
    img = smear(img, ang, 14, steps=4)
    img *= bristles(h, w, ang, rng, 40, 0.05)[..., None]
    img = canvas_weave(grain(img, rng, 0.016), rng)
    return to_image(img)


def fields_after_rain(w=2100, h=1400, seed=9):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(F)
    hz = h * 0.36
    t = yy / hz
    sky = ramp(np.clip(t, 0, 1), [(0, '#9EA9AA'), (0.6, '#C9CDC8'), (1, '#E2DFD4')])
    cl = noise(h, w, 420, rng, 5)
    sky = sky * (1 - smoothstep(0.55, 0.75, cl)[..., None] * 0.18)
    img = sky
    cols = ['#8C9A63', '#A9A15A', '#5F7042', '#C2A15A', '#7D8B4E', '#6B7A44', '#B39A52', '#56673E']
    y = hz
    k = 0
    while y < h:
        bh = 10 + (y - hz) * 0.34
        wob = (noise(1, w, 300, rng, 3)[0] - 0.5) * (6 + bh * 0.25)
        top = y + wob
        m = smoothstep(top - 1.5, top + 1.5, yy)
        tone = noise(h, w, 240, rng, 3)
        c = ramp(tone, [(0, cols[k % len(cols)]), (1, cols[(k + 3) % len(cols)])])
        img = img * (1 - m[..., None]) + (c * 0.85 + img * 0.15) * m[..., None]
        y += bh
        k += 1
    ang = (noise(h, w, 400, rng, 2) - 0.5) * 0.15
    img = smear(img, ang, 26, steps=5)
    img *= bristles(h, w, ang, rng, 60, 0.08)[..., None]
    img = canvas_weave(grain(img, rng, 0.02), rng)
    return to_image(img)


def riverside_dusk(w=1500, h=2000, seed=17):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(F)
    hz = h * 0.5
    sky_t = np.clip(yy / hz, 0, 1)
    sky = ramp(sky_t, [(0, '#3E4A6B'), (0.35, '#7B6186'), (0.62, '#C27A7E'), (0.85, '#E79A6B'), (1, '#F2C38C')])
    cl = smear(noise(h, w, 380, rng, 4), np.zeros((h, w), F), 80, 5)
    sky = sky * (1 - smoothstep(0.58, 0.8, cl)[..., None] * 0.12)
    water_t = np.clip((yy - hz) / (h - hz), 0, 1)
    refl = ramp(1 - water_t * 0.9, [(0, '#2F3550'), (0.35, '#6A557A'), (0.62, '#A96C73'), (0.85, '#D18A63'), (1, '#E4B07E')])
    ripples = 0.5 + 0.5 * np.sin((yy + (noise(h, w, 200, rng, 3) - 0.5) * 30) / 7.0)
    refl *= (0.86 + 0.14 * ripples[..., None])
    col = np.exp(-((xx - w * 0.58) / 60) ** 2) * (yy > hz) * (ripples > 0.55) * (1 - water_t) ** 0.6
    refl += col[..., None] * hex2rgb('#F6D9A8') * 0.55
    img = np.where((yy < hz)[..., None], sky, refl)
    tree = noise(1, w, 90, rng, 5, 0.6)[0]
    top = hz - 18 - tree * 95
    m = smoothstep(top - 1.5, top + 1.5, yy) * (yy < hz + 14)
    img = img * (1 - m[..., None]) + hex2rgb('#26252F') * m[..., None]
    ang = (noise(h, w, 400, rng, 2) - 0.5) * 0.12
    img = smear(img, ang, 18, steps=4)
    img *= bristles(h, w, ang, rng, 50, 0.06)[..., None]
    img = canvas_weave(grain(img, rng, 0.02), rng)
    return to_image(img)


# ----------------------------------------------------------------- POP
def _supersample(w, h, draw_fn, bg, ss=2):
    im = Image.new('RGB', (w * ss, h * ss), bg)
    d = ImageDraw.Draw(im)
    draw_fn(d, w * ss, h * ss, ss)
    return im.resize((w, h), Image.LANCZOS)


def _painted(im, rng, amount=0.03):
    arr = np.asarray(im).astype(F) / 255
    h, w = arr.shape[:2]
    tone = (noise(h, w, 300, rng, 4) - 0.5) * amount * 2
    arr = arr * (1 + tone[..., None])
    arr = canvas_weave(grain(arr, rng, 0.02), rng, 0.015)
    return to_image(arr)


def marigold_pop(w=1800, h=1800, seed=2):
    rng = np.random.default_rng(seed)

    def draw(d, W, H, ss):
        d.rectangle([0, 0, W, H], fill='#D6336C')
        # halftone field top-right
        step = 46 * ss
        for yy in range(0, H // 2 + step, step):
            for xx in range(W // 2, W + step, step):
                r = (1 - (abs(xx - W) + yy) / (W * 0.9)) * step * 0.42
                if r > 1:
                    d.ellipse([xx - r, yy - r, xx + r, yy + r], fill='#1A1718')
        cx, cy, R = W * 0.42, H * 0.56, W * 0.3
        d.ellipse([cx - R - 40 * ss, cy - R - 40 * ss, cx + R + 40 * ss, cy + R + 40 * ss], fill='#127C7A')
        d.ellipse([cx - R - 14 * ss, cy - R - 14 * ss, cx + R + 14 * ss, cy + R + 14 * ss], fill='#F7EBD8')
        d.ellipse([cx - R, cy - R, cx + R, cy + R], fill='#F2A007')
        for k in range(18):
            a = k / 18 * 2 * np.pi
            px, py = cx + np.cos(a) * R * 0.62, cy + np.sin(a) * R * 0.62
            pr = R * 0.2
            d.ellipse([px - pr, py - pr, px + pr, py + pr], fill='#F7B733' if k % 2 else '#E88E04')
        d.ellipse([cx - R * 0.34, cy - R * 0.34, cx + R * 0.34, cy + R * 0.34], fill='#B4480B')
        d.polygon([(0, H * 0.92), (W * 0.35, H), (0, H)], fill='#1A1718')
        d.pieslice([W * 0.72, H * 0.72, W * 1.28, H * 1.28], 180, 270, fill='#127C7A')
        d.line([W * 0.06, H * 0.12, W * 0.3, H * 0.12], fill='#F7EBD8', width=14 * ss)
        d.line([W * 0.06, H * 0.17, W * 0.22, H * 0.17], fill='#F7EBD8', width=14 * ss)

    return _painted(_supersample(w, h, draw, '#D6336C'), rng)


def city_signals(w=1500, h=1875, seed=4):
    rng = np.random.default_rng(seed)

    def draw(d, W, H, ss):
        d.rectangle([0, 0, W, H], fill='#F4EAD7')
        d.rectangle([0, 0, W * 0.58, H * 0.46], fill='#1F4FA8')
        step = 30 * ss
        for yy in range(0, int(H * 0.46), step):
            for xx in range(0, int(W * 0.58), step):
                r = (yy / (H * 0.46)) * step * 0.45
                if r > 1:
                    d.ellipse([xx - r, yy - r, xx + r, yy + r], fill='#F4EAD7')
        d.rectangle([W * 0.58, 0, W, H * 0.3], fill='#D8352A')
        for k in range(-20, 40):
            x0 = k * 60 * ss
            d.polygon([(x0, H * 0.62), (x0 + 30 * ss, H * 0.62), (x0 + 30 * ss + H * 0.38, H), (x0 + H * 0.38, H)], fill='#1A1718')
        d.rectangle([0, H * 0.46, W, H * 0.62], fill='#F1C232')
        R = W * 0.2
        cx, cy = W * 0.66, H * 0.5
        d.ellipse([cx - R, cy - R, cx + R, cy + R], fill='#D8352A')
        d.pieslice([W * 0.04, H * 0.8, W * 0.46, H * 1.12], 180, 360, fill='#F4EAD7')
        d.rectangle([W * 0.78, H * 0.7, W * 0.9, H * 0.7 + W * 0.12], fill='#1F4FA8')
        d.line([W * 0.08, H * 0.4, W * 0.5, H * 0.4], fill='#1A1718', width=10 * ss)

    return _painted(_supersample(w, h, draw, '#F4EAD7'), rng)


def pink_monsoon(w=2100, h=1400, seed=6):
    rng = np.random.default_rng(seed)

    def draw(d, W, H, ss):
        d.rectangle([0, 0, W, H], fill='#E86A92')
        for k in range(160):
            x = rng.random() * W * 1.2 - W * 0.1
            y = rng.random() * H * 0.9 + H * 0.2
            L = (40 + rng.random() * 80) * ss
            col = '#1D8A8A' if k % 3 else '#F7EDE4'
            d.line([x, y, x - L * 0.45, y + L], fill=col, width=int(9 * ss))
        for cx, cy, s in [(0.22, 0.2, 1.0), (0.62, 0.14, 1.25), (0.9, 0.26, 0.8)]:
            for ox, oy, r in [(-0.09, 0.03, 0.07), (-0.03, -0.02, 0.09), (0.05, 0.0, 0.08), (0.11, 0.04, 0.06), (0.0, 0.05, 0.08)]:
                R = r * W * s * 0.7
                X, Y = (cx + ox * s) * W, (cy + oy * s) * H
                d.ellipse([X - R, Y - R, X + R, Y + R], fill='#F7EDE4')
        for i in range(4):
            rx, ry = (160 + i * 110) * ss, (26 + i * 18) * ss
            cx, cy = W * 0.7, H * 0.86
            d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline='#8E1F47', width=int(7 * ss))

    return _painted(_supersample(w, h, draw, '#E86A92'), rng, 0.04)


PAINTINGS = {
    'azure-reverie': azure_reverie,
    'saffron-hour': saffron_hour,
    'quiet-monsoon': quiet_monsoon,
    'ivory-tide': ivory_tide,
    'sandstone-lines': sandstone_lines,
    'terrain-in-gold': terrain_in_gold,
    'himalayan-morning': himalayan_morning,
    'fields-after-rain': fields_after_rain,
    'riverside-dusk': riverside_dusk,
    'marigold-pop': marigold_pop,
    'city-signals': city_signals,
    'pink-monsoon': pink_monsoon,
}

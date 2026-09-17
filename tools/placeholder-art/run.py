import os, sys, time
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from paint import PAINTINGS
from room import render_room

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'content', 'images', 'paintings')
SIZES_IN = {'azure-reverie': (36, 48), 'saffron-hour': (40, 30), 'quiet-monsoon': (30, 30), 'ivory-tide': (48, 48),
            'sandstone-lines': (24, 36), 'terrain-in-gold': (36, 36), 'himalayan-morning': (48, 30),
            'fields-after-rain': (36, 24), 'riverside-dusk': (30, 40), 'marigold-pop': (30, 30),
            'city-signals': (24, 30), 'pink-monsoon': (36, 24)}
DETAILS = {  # slug: [(x0_frac, y0_frac, crop_w_px)]  -> 4:5 crops
    'azure-reverie': [(0.3, 0.3, 900)], 'ivory-tide': [(0.18, 0.22, 1200), (0.55, 0.42, 1200)],
    'himalayan-morning': [(0.46, 0.08, 1000)], 'saffron-hour': [(0.08, 0.1, 1000)],
    'sandstone-lines': [(0.2, 0.45, 1200)], 'riverside-dusk': [(0.25, 0.32, 1000)],
    'terrain-in-gold': [(0.3, 0.3, 1200)], 'marigold-pop': [(0.18, 0.3, 1000)],
}
ROOMS = {
    'azure-reverie': dict(furniture='sofa', wall='#ECE6DC', floor='#B79B7C', seed=1),
    'ivory-tide': dict(furniture='sideboard', wall='#D6CEC1', floor='#8E7258', seed=2),
    'himalayan-morning': dict(furniture='sofa', wall='#D7D9CF', floor='#B39776', seed=3, light_from='right'),
    'marigold-pop': dict(furniture='sideboard', wall='#EFEBE4', floor='#A98C6D', seed=4),
    'fields-after-rain': dict(furniture='sofa', wall='#E4DED3', floor='#B09372', seed=5, light_from='right'),
    'pink-monsoon': dict(furniture='sideboard', wall='#E8E3DA', floor='#9C7F61', seed=6),
}
only = sys.argv[1:]
for slug, fn in PAINTINGS.items():
    if only and slug not in only: continue
    t = time.time()
    folder = os.path.join(OUT, slug); os.makedirs(folder, exist_ok=True)
    full = fn()
    primary = full.copy(); primary.thumbnail((2000, 2000), Image.LANCZOS)
    primary.save(os.path.join(folder, 'primary.jpg'), quality=90, optimize=True, progressive=True)
    for i, (fx, fy, cw) in enumerate(DETAILS.get(slug, []), start=1):
        W, H = full.size; ch = int(cw * 1.25)
        x0 = min(int(W * fx), W - cw); y0 = min(int(H * fy), H - ch)
        full.crop((x0, y0, x0 + cw, y0 + ch)).save(os.path.join(folder, f'detail-{i}.jpg'), quality=90, optimize=True, progressive=True)
    if slug in ROOMS:
        w_in, h_in = SIZES_IN[slug]
        room = render_room(full, w_in, h_in, **ROOMS[slug])
        room.save(os.path.join(folder, 'room-1.jpg'), quality=88, optimize=True, progressive=True)
    print(f'{slug:20s} {full.size} {time.time()-t:5.1f}s', flush=True)

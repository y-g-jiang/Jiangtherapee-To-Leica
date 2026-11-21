import math
import numpy as np

PROFILE = 'darktable-org/darktable@90d6c8c:data/noiseprofiles.json:Leica/M9:green'
ANCHORS = np.array([
    (80, 2.47033733915763e-6, 1.55858664715361e-8), (160, 2.49443661862630e-6, 1.62367233368578e-8),
    (200, 2.83264081007217e-6, 3.08333955651150e-8), (250, 3.34766335973452e-6, 5.06415379003563e-8),
    (320, 3.32696094423650e-6, 6.80208367255724e-8), (400, 4.02148975497485e-6, 1.12125821441367e-7),
    (500, 3.49247282055736e-6, 1.54190000286517e-7), (640, 4.42170401261388e-6, 2.67652209512430e-7),
    (800, 5.95236454615544e-6, 4.45290346743396e-7), (1000, 8.04003156849463e-6, 6.91790762911113e-7),
    (1250, 1.03080654478507e-5, 1.08266466102976e-6), (1600, 7.94067528500895e-6, 1.42536428040082e-6),
    (2000, 1.33701597020496e-5, 2.41956139003484e-6), (2500, 1.99092284525902e-5, 3.79134154732526e-6)], dtype=np.float64)


def coefficients(iso):
    if not math.isfinite(iso) or iso <= 0:
        raise ValueError('ISO 必须为正数。')
    positions = np.log2(ANCHORS[:, 0])
    return tuple(float(np.interp(math.log2(iso), positions, channel)) for channel in ANCHORS[:, 1:].T)


def strips(photo, iso, strength, seed):
    shot, floor = coefficients(iso)
    if not math.isfinite(strength) or not 0 <= strength <= 2:
        raise ValueError('颗粒强度范围为 0 到 2。')
    height, width = photo.shape[:2]
    rng = np.random.default_rng(seed)
    tail = rng.standard_normal((2, width+2), dtype=np.float32)
    tap = .16
    for top in range(0, height, 64):
        pixels = photo[top:top+64]
        if strength == 0:
            yield pixels
            continue
        raw = np.concatenate((tail, rng.standard_normal((len(pixels), width+2), dtype=np.float32)))
        tail = raw[-2:].copy()
        horizontal = tap * (raw[:, :-2] + raw[:, 2:]) + raw[:, 1:-1]
        field = (tap * (horizontal[:-2] + horizontal[2:]) + horizontal[1:-1]) / (1 + 2*tap*tap)
        luma = (pixels @ np.array([.2126, .7152, .0722], np.float32)) / 65535
        linear = np.where(luma <= .04045, luma/12.92, ((luma+.055)/1.055)**2.4)
        slope = np.where(linear <= .0031308, 12.92, (1.055/2.4) * np.maximum(linear, .0031308)**(1/2.4-1))
        sigma = np.sqrt(shot * linear + floor) * slope * strength * 65535
        headroom = np.minimum(pixels.min(axis=2), 65535-pixels.max(axis=2)).astype(np.float32)
        delta = np.rint(np.clip(sigma * field, -headroom, headroom)).astype(np.int32)
        yield (pixels + delta[:, :, None]).astype(np.uint16)

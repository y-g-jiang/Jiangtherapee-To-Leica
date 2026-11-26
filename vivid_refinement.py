import cv2
import numpy as np

from flat_refinement import check_cancelled


PERIOD = 16
LIMIT = 1.5


def window_mean(values):
    return cv2.blur(values, (33, 33))


def mean_square(values):
    return np.maximum(window_mean(values * values), 0)


def repeat_average(values):
    kernel = np.zeros(4 * PERIOD + 1, np.float32)
    kernel[::PERIOD] = np.array([1, 2, 2, 2, 1], np.float32) / 8
    return cv2.sepFilter2D(values, -1, kernel, kernel)


def estimate(rendered, guide):
    def detail(values):
        return values - cv2.GaussianBlur(values, (0, 0), 6)

    original = detail(guide)
    styled = detail(rendered)
    power = mean_square(original)
    gain = window_mean(original * styled) / (power + 1e-6)
    residual = styled - gain * original
    pattern = repeat_average(residual)
    coherent = np.sqrt(mean_square(pattern))
    total = np.sqrt(mean_square(residual))
    repeatability = np.clip((coherent / (total + .025) - .50) / .32, 0, 1)
    source_phase = repeat_average(original)
    source_repeat = np.sqrt(mean_square(source_phase)).max(axis=2)
    structure = np.sqrt(power).max(axis=2)
    flat = np.clip((1.6 - structure) / 1.2, 0, 1)
    source_veto = np.clip((.22 - source_repeat) / .16, 0, 1)
    protection = cv2.erode(flat * source_veto, np.ones((9, 9), np.uint8))
    return np.clip(-pattern * repeatability, -LIMIT, LIMIT) * protection[..., None]


def balanced(delta, pixels):
    delta = np.clip(delta, -pixels.astype(np.float32), 65535 - pixels.astype(np.int32))
    for channel in range(3):
        changes = delta[..., channel].ravel()
        positive = np.maximum(changes, 0)
        negative = np.maximum(-changes, 0)
        added, removed = positive.sum(dtype=np.float64), negative.sum(dtype=np.float64)
        budget = int(min(added, removed))
        if budget == 0:
            continue
        def allocate(weights, mass):
            cumulative = weights.cumsum(dtype=np.float64) * (budget / mass)
            return np.diff(np.rint(cumulative).astype(np.int64), prepend=0).astype(np.int32)
        transfer = allocate(positive, added) - allocate(negative, removed)
        pixels[..., channel] = pixels[..., channel] + transfer.reshape(pixels.shape[:2])


def refine(output, source, gate, proxy_shape, cancelled, progress=None):
    check_cancelled(cancelled)
    height, width = gate.shape
    rows, cols = min(height, proxy_shape[0]), min(width, proxy_shape[1])
    if min(rows, cols) < 4 * PERIOD:
        return
    def proxy(values):
        return cv2.resize(values, (cols, rows), interpolation=cv2.INTER_AREA).astype(np.float32) / 257
    correction = estimate(proxy(output), proxy(source))
    valid = cv2.resize(gate, (cols, rows), interpolation=cv2.INTER_AREA) == 255
    valid = cv2.erode(valid.astype(np.uint8), np.ones((9, 9), np.uint8))
    correction *= valid[..., None] * np.float32(257)
    group = 4 * PERIOD
    for row in range(0, rows, group):
        check_cancelled(cancelled)
        top, bottom = round(row * height / rows), round(min(rows, row + group) * height / rows)
        for col in range(0, cols, group):
            region = correction[max(0,row-1):row+group+1, max(0,col-1):col+group+1]
            if np.abs(region).max() < .5:
                continue
            left, right = round(col * width / cols), round(min(cols, col + group) * width / cols)
            grid_x, grid_y = np.meshgrid((np.arange(left, right, dtype=np.float32) + .5) * cols / width - .5,
                                         (np.arange(top, bottom, dtype=np.float32) + .5) * rows / height - .5)
            delta = cv2.remap(correction, grid_x, grid_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
            patch = source[max(0,top-1):bottom+1, max(0,left-1):right+1]
            feature = cv2.absdiff(patch, cv2.blur(patch, (3, 3))).max(axis=2)
            offset_y, offset_x = min(top,1), min(left,1)
            texture = feature[offset_y:offset_y+bottom-top, offset_x:offset_x+right-left]
            allow = np.clip((257 - texture.astype(np.float32)) / 192, 0, 1)
            delta *= (allow * (gate[top:bottom,left:right] == 255))[..., None]
            balanced(delta, output[top:bottom,left:right])
        if progress is not None:
            progress(min(rows, row + group), rows)

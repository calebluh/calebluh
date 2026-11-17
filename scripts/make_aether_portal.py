"""One-off: recolor assets/nether-portal.gif into an Aether portal.

Obsidian frame -> glowstone, purple swirl -> pale aether blue. Brightness
is kept per pixel and mapped onto each palette, so the animation is intact.
Run from the repo root:  python scripts/make_aether_portal.py
"""
import numpy as np
from PIL import Image, ImageSequence

SRC = "assets/nether-portal.gif"
OUT = "assets/aether-portal.gif"
PORTAL = (126, 128, 383, 513)  # swirl rectangle inside the frame (x0, y0, x1, y1)

# (luminance stop 0..1, RGB) gradients
GLOWSTONE = [(0.00, (92, 58, 20)), (0.25, (168, 112, 40)), (0.55, (236, 182, 82)), (1.00, (255, 241, 168))]
AETHER = [(0.00, (24, 86, 168)), (0.45, (74, 160, 226)), (0.75, (150, 210, 245)), (1.00, (232, 248, 255))]


def ramp(lum, stops):
    out = np.zeros(lum.shape + (3,), dtype=np.float32)
    xs = [s for s, _ in stops]
    for ch in range(3):
        out[..., ch] = np.interp(lum, xs, [c[ch] for _, c in stops])
    return out


def recolor(frame, frame_range, swirl_range):
    rgb = np.asarray(frame.convert("RGB"), dtype=np.float32)
    lum = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    out = np.empty_like(rgb)
    mask = np.zeros(lum.shape, bool)
    x0, y0, x1, y1 = PORTAL
    mask[y0:y1, x0:x1] = True
    f_lo, f_hi = frame_range
    s_lo, s_hi = swirl_range
    out[~mask] = ramp(np.clip((lum[~mask] - f_lo) / (f_hi - f_lo), 0, 1), GLOWSTONE)
    out[mask] = ramp(np.clip((lum[mask] - s_lo) / (s_hi - s_lo), 0, 1), AETHER)
    return Image.fromarray(out.astype(np.uint8))


def main():
    src = Image.open(SRC)
    frames = [f.convert("RGB") for f in ImageSequence.Iterator(src)]
    durations = [f.info.get("duration", 50) for f in ImageSequence.Iterator(Image.open(SRC))]
    # brightness ranges from the first frame, so every frame shares one mapping
    lum0 = np.asarray(frames[0].convert("L"), dtype=np.float32)
    x0, y0, x1, y1 = PORTAL
    inner = lum0[y0:y1, x0:x1]
    outer = lum0.copy()
    outer[y0:y1, x0:x1] = np.nan
    frame_range = (np.nanpercentile(outer, 2), np.nanpercentile(outer, 99.5))
    swirl_range = (np.percentile(inner, 1), np.percentile(inner, 99.5))
    out = [recolor(f, frame_range, swirl_range) for f in frames]
    out[0].save(OUT, save_all=True, append_images=out[1:], duration=durations, loop=0, optimize=True)
    print(f"wrote {OUT} ({len(out)} frames)")


if __name__ == "__main__":
    main()

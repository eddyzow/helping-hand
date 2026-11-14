"""Sculpt the Duplo car body as a smooth mesh and write sim_assets/car_body.stl.

    python sim_assets/make_car_body.py      # needs scikit-image; the STL is committed, so this is only to change the shape

The shape is described as solid pieces added and carved away (rounded shell, wheel arches, open cockpit,
studs, hitch), then turned into a surface. Sizes in millimetres are estimated from Eddy's photos.
x is forward (bonnet), y is across, z is up.
"""
import struct
from pathlib import Path

import numpy as np
from skimage import measure

STEP = 1.25  # mm between samples


def box(p, centre, half, round_=0.0):
    q = np.abs(p - np.array(centre)) - (np.array(half) - round_)
    return np.linalg.norm(np.maximum(q, 0), axis=-1) + np.minimum(q.max(axis=-1), 0) - round_


def ellipsoid(p, centre, radii):
    k = np.linalg.norm((p - np.array(centre)) / np.array(radii), axis=-1)
    return (k - 1) * min(radii)


def tube_y(p, x, z, radius):  # a cylinder lying across the car
    return np.hypot(p[..., 0] - x, p[..., 2] - z) - radius


def post(p, x, y, radius, z0, z1):  # an upright cylinder
    return np.maximum(np.hypot(p[..., 0] - x, p[..., 1] - y) - radius, np.maximum(z0 - p[..., 2], p[..., 2] - z1))


def smooth_union(a, b, k=3.0):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def car(p):
    tub = np.maximum(box(p, (0, 0, 4), (50, 27, 27), 9), ellipsoid(p, (-4, 0, 2), (58, 31, 31)))  # rounded outside
    shell = np.maximum(tub, -(tub + 4.0))                                      # a 4 mm wall, hollow inside
    for x in (-25, 25):                                                        # fenders bulging over the wheels
        fender = np.maximum(tube_y(p, x, 2, 23), np.abs(np.abs(p[..., 1]) - 24) - 5)
        shell = smooth_union(shell, fender, 4)
    shell = smooth_union(shell, box(p, (-39, 0, 26), (10, 17, 11), 3), 3)      # raised deck at the back
    shell = smooth_union(shell, box(p, (24, 0, 31), (3, 19, 5), 2.5), 3)       # windscreen lip
    shell = np.maximum(shell, -box(p, (-4, 0, 34), (22, 15, 18), 5))           # open cockpit
    for x in (-25, 25):
        shell = np.maximum(shell, -tube_y(p, x, 0, 18))                        # wheel arches
    shell = np.maximum(shell, -p[..., 2])                                      # flat on the table
    shell = np.minimum(shell, box(p, (-24, 0, 21), (3, 16, 9), 2))             # seat back
    for y in (-8, 8):
        shell = np.minimum(shell, post(p, -39, y, 4.7, 30, 41.5))              # two studs on the deck
    shell = np.minimum(shell, post(p, -27, 22, 4.7, 20, 31))                   # one stud on the rear fender
    shell = np.minimum(shell, box(p, (-53, 0, 9), (5, 3, 3), 1))               # hitch arm
    return np.minimum(shell, post(p, -59, 0, 4, 2, 18))                        # hitch peg


def main():
    xs, ys, zs = np.arange(-66, 56, STEP), np.arange(-34, 34.01, STEP), np.arange(-2, 46, STEP)
    grid = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), axis=-1)
    verts, faces, _, _ = measure.marching_cubes(car(grid), 0.0, spacing=(STEP,) * 3)
    verts = (verts + [xs[0], ys[0], zs[0]]) / 1000.0  # metres
    out = Path(__file__).with_name("car_body.stl")
    with open(out, "wb") as f:
        f.write(b"\0" * 80 + struct.pack("<I", len(faces)))
        for tri in verts[faces].astype(np.float32):
            n = np.cross(tri[1] - tri[0], tri[2] - tri[0])
            n = n / (np.linalg.norm(n) or 1)
            f.write(struct.pack("<12fH", *n, *tri.ravel(), 0))
    print(f"{out}: {len(faces)} triangles, {out.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()

"""Map a point on the table or paper to joint angles using hand-taught poses.

A grid is n by n poses taught with the arm, stored row by row: row 0 is the far
edge, column 0 is the left. interpolate() blends the four poses around (u, v),
where u runs 0 (left) to 1 (right) and v runs 0 (far) to 1 (near).

    python grid.py   # self-check
"""


def interpolate(poses: list[dict[str, float]], n: int, u: float, v: float) -> dict[str, float]:
    u, v = min(max(u, 0.0), 1.0), min(max(v, 0.0), 1.0)
    col, row = min(int(u * (n - 1)), n - 2), min(int(v * (n - 1)), n - 2)
    fu, fv = u * (n - 1) - col, v * (n - 1) - row
    a, b = poses[row * n + col], poses[row * n + col + 1]
    c, d = poses[(row + 1) * n + col], poses[(row + 1) * n + col + 1]
    return {
        k: (a[k] * (1 - fu) + b[k] * fu) * (1 - fv) + (c[k] * (1 - fu) + d[k] * fu) * fv
        for k in a
    }


if __name__ == "__main__":
    # a joint that is exactly 10*u + 100*v must come back exactly
    taught = [{"j": 10 * (c / 2) + 100 * (r / 2)} for r in range(3) for c in range(3)]
    for u, v in [(0, 0), (1, 1), (0.25, 0.8), (0.5, 0.5), (0.99, 0.01)]:
        assert abs(interpolate(taught, 3, u, v)["j"] - (10 * u + 100 * v)) < 1e-9, (u, v)
    assert interpolate(taught, 3, 2, -1) == interpolate(taught, 3, 1, 0)  # clamps
    print("grid ok")

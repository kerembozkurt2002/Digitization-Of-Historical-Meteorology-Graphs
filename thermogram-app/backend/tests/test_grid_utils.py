"""utils.grid_utils: clustering, extension, intersection."""

import numpy as np

from utils.grid_utils import (
    cluster_lines,
    extend_lines_to_bounds,
    find_grid_intersections,
    line_intersection,
)


def test_cluster_empty_input_returns_empty_list():
    assert cluster_lines([], "vertical") == []


def test_cluster_merges_nearby_vertical_lines():
    lines = [
        np.array([100, 0, 100, 200]),
        np.array([102, 0, 102, 200]),  # within threshold of the first
        np.array([200, 0, 200, 200]),
    ]
    out = cluster_lines(lines, "vertical", threshold=10)
    xs = sorted(int(line[0]) for line in out)
    # The 100/102 pair must collapse to a single representative.
    assert len(out) == 2
    assert xs[0] in (100, 101)
    assert xs[1] == 200


def test_extend_lines_to_bounds_spans_full_image():
    lines = [np.array([100, 50, 100, 150])]
    out = extend_lines_to_bounds(lines, "vertical", image_shape=(300, 400))
    assert len(out) == 1
    line = out[0]
    # Vertical line must run from y=0 to y=h-1=299 at x=100.
    assert int(line[1]) == 0
    assert int(line[3]) == 299


def test_line_intersection_basic_case():
    p = line_intersection((0, 0), (10, 10), (0, 10), (10, 0))
    assert p is not None
    x, y = p
    assert abs(x - 5) < 1e-6
    assert abs(y - 5) < 1e-6


def test_line_intersection_parallel_returns_none():
    p = line_intersection((0, 0), (10, 0), (0, 5), (10, 5))
    assert p is None


def test_find_grid_intersections_in_bounds():
    v = [np.array([100, 0, 100, 200])]
    h = [np.array([0, 50, 300, 50]), np.array([0, 150, 300, 150])]
    pts = find_grid_intersections(v, h, image_shape=(200, 300))
    assert pts.shape == (2, 2)
    # The crossings are at (100, 50) and (100, 150).
    xs, ys = pts[:, 0], pts[:, 1]
    assert set(np.round(xs).astype(int).tolist()) == {100}
    assert set(np.round(ys).astype(int).tolist()) == {50, 150}

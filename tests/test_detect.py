import math

import numpy as np
import pytest

from weldfinder.detect import Params, detect


def test_plate_end_over_wall(plate_on_wall):
    cands = detect(plate_on_wall, Params(max_gap=5.0))
    # the two long end-face edges (y=0 and y=1.5) of the plate, both 50 mm, gap 1 mm
    assert len(cands) == 2
    for c in cands:
        assert (c.source, c.target) == ("S001", "S000")
        assert c.curve_type == "Line"
        assert c.length == pytest.approx(50.0, abs=0.05)
        assert c.gap_min == pytest.approx(1.0, abs=1e-3)
        assert c.gap_max == pytest.approx(1.0, abs=1e-3)
        p = np.array(c.points)
        assert np.allclose(p[:, 2], 1.0)
        assert sorted(p[:, 0])[0] == pytest.approx(0.0, abs=0.05)
        assert sorted(p[:, 0])[-1] == pytest.approx(50.0, abs=0.05)
    assert sorted(round(c.points[0][1], 2) for c in cands) == [0.0, 1.5]


def test_gap_too_large_gives_nothing(plate_on_wall):
    assert detect(plate_on_wall, Params(max_gap=0.5)) == []


def test_partial_overlap_trims_curve(plate_on_wall):
    # shrink the wall so it only lies under x in [-25, 20]: candidate should be ~20 mm... + gap reach
    from conftest import box
    from weldfinder.step_io import Solid
    wall = Solid("S000", "wall", box(-25, -25, -2, 45, 100, 2))  # x up to 20
    cands = detect([wall, plate_on_wall[1]], Params(max_gap=2.0))
    assert cands
    c = cands[0]
    # points beyond x=20 are > 2 mm away (distance sqrt(1+dx^2) <= 2 -> dx <= 1.73)
    assert c.length == pytest.approx(20 + math.sqrt(3), abs=0.1)


def test_curved_edges_preserved(baffle_in_tube):
    cands = detect(baffle_in_tube, Params(max_gap=5.0))
    assert len(cands) == 2  # top and bottom circle of the baffle rim
    for c in cands:
        assert c.curve_type == "Circle"
        assert c.length == pytest.approx(2 * math.pi * 49, rel=1e-3)
        assert c.gap_mean == pytest.approx(1.0, abs=1e-3)
        r = np.linalg.norm(np.array(c.points)[:, :2], axis=1)
        assert np.allclose(r, 49.0, atol=0.06)  # on the true circle, within chord tol
        assert len(c.points) > 20

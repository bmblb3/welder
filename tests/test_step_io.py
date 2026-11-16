import pytest

from conftest import write_step
from weldfinder.detect import detect
from weldfinder.step_io import load_solids


def test_roundtrip_names_and_detection(plate_on_wall, tmp_path):
    f = tmp_path / "t.stp"
    write_step(plate_on_wall, f)
    solids = load_solids(str(f))
    assert [s.name for s in solids] == ["wall", "plate"]
    assert [s.id for s in solids] == ["S000", "S001"]
    cands = detect(solids)
    assert len(cands) == 2
    assert all(c.gap_mean == pytest.approx(1.0, abs=1e-3) for c in cands)

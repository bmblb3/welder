from weldfinder.catia import CatiaBody, match_visible
from weldfinder.step_io import Solid


def S(i, n):
    return Solid(f"S{i:03d}", n, None)


def test_match_by_name_filters_hidden():
    solids = [S(0, "Shell"), S(1, "Baffle"), S(2, "Tube")]
    bodies = [CatiaBody("tube", True), CatiaBody("Shell", True), CatiaBody("Baffle", False)]
    got, how = match_visible(solids, bodies)
    assert how == "name" and [s.id for s in got] == ["S000", "S002"]


def test_match_by_order_when_names_differ():
    solids = [S(0, "a"), S(1, "b")]
    got, how = match_visible(solids, [CatiaBody("x", False), CatiaBody("y", True)])
    assert how == "order" and [s.id for s in got] == ["S001"]


def test_unmatched_falls_back_to_all():
    solids = [S(0, "a"), S(1, "b"), S(2, "c")]
    got, how = match_visible(solids, [CatiaBody("x", True)])
    assert how.startswith("unmatched") and len(got) == 3
